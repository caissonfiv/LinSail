"""Explicit user-local updates with validated downloads and one-version rollback."""
import contextlib
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
from .installer import atomic_write, path_block
from .provider import tls_context

REPOSITORY = 'caissonfiv/LinSail'
API = 'https://api.github.com/repos/' + REPOSITORY
VERSION = re.compile(r'v?(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?\Z')


def version_key(value):
    match = VERSION.fullmatch(value)
    if not match:
        raise ValueError('版本格式应为 0.1.0 或 0.1.0a4。')
    major, minor, patch, phase, number = match.groups()
    return (int(major), int(minor), int(patch), {None: 3, 'rc': 2, 'b': 1, 'a': 0}[phase], int(number or 0))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sidecars(destination):
    return (destination.with_name('.linsail-install.json'), destination.with_name('.linsail-previous'))


def reject_links(*paths):
    for path in paths:
        if path.is_symlink():
            raise ValueError(f'拒绝修改符号链接：{path}')


@contextlib.contextmanager
def install_lock(directory):
    """The persistent lock inode prevents concurrent upgrades/uninstalls."""
    import fcntl
    path = directory / '.linsail.lock'
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('另一个安装、更新或卸载操作正在进行，请稍后再试。') from None
        yield
    finally:
        os.close(fd)


def read_record(destination):
    state, backup = sidecars(destination)
    reject_links(destination, state, backup)
    record = json.loads(state.read_text(encoding='utf-8'))
    if record.get('path') != str(destination.resolve()) or record.get('schema') != 1:
        raise ValueError('安装记录不匹配，请重新运行官方安装器。')
    if record.get('kind') not in {'binary', 'pyz'} or record.get('sha256') != digest(destination.read_bytes()):
        raise ValueError('已安装文件与记录不一致，未做修改。请重新安装后重试。')
    return record


def deploy(destination, data, kind, version, shell_files):
    """Commit executable and metadata; restore snapshots on an ordinary I/O error."""
    state, backup = sidecars(destination)
    reject_links(destination, state, backup)
    paths = (destination, state, backup)
    before = {p: p.read_bytes() if p.exists() else None for p in paths}
    record = dict(schema=1, path=str(destination.resolve()), kind=kind, version=version,
                  sha256=digest(data), shell_files=shell_files)
    old_record = json.loads(before[state]) if before[state] else None
    if old_record:
        read_record(destination)
    if before[destination] is not None:
        if before[destination] == data and old_record:
            record['previous'] = old_record.get('previous')
        else:
            old_kind = 'binary' if before[destination].startswith(b'\x7fELF') else 'pyz'
            record['previous'] = dict(sha256=digest(before[destination]),
                                      kind=old_record['kind'] if old_record else old_kind,
                                      version=old_record.get('version') if old_record else None)
    try:
        if record.get('previous') and (not old_record or before[destination] != data):
            atomic_write(backup, before[destination], 0o700)
        atomic_write(destination, data, 0o755)
        atomic_write(state, json.dumps(record, ensure_ascii=False, indent=2).encode(), 0o600)
    except OSError:
        for path in paths:
            if before[path] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, before[path], 0o755 if path == destination else 0o600)
        raise


def current_install():
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise RuntimeError('请在 Linux 下以普通用户运行此命令。')
    path = Path(sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]).absolute()
    if path.name != 'linsail' or not sidecars(path)[0].is_file():
        raise RuntimeError('请先用新版安装器安装，再通过 linsail 执行维护命令。')
    reject_links(path)
    return path.resolve()


def fetch(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'LinSail/' + __version__})
    try:
        with urllib.request.urlopen(request, timeout=60, context=tls_context()) as response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('下载超出大小限制，已停止。')
            return data
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise RuntimeError(f'GitHub 下载失败（HTTP {code}）；请检查版本、网络或请求频率。') from None
    except urllib.error.URLError:
        raise RuntimeError('无法连接 GitHub；请检查网络、代理和系统 CA 证书。') from None


def find_release(channel, target=None):
    if target:
        version_key(target)
        version = target.removeprefix('v')
        release = json.loads(fetch(API + '/releases/tags/v' + version, 1_000_000))
        if release.get('draft') or release.get('tag_name') != 'v' + version:
            raise ValueError('发布信息与指定版本不匹配。')
        return version, release
    releases = json.loads(fetch(API + '/releases?per_page=100', 4_000_000))
    if not isinstance(releases, list):
        raise ValueError('发布列表格式无效。')
    eligible = []
    for item in releases:
        tag = item.get('tag_name', '')
        if item.get('draft') or not VERSION.fullmatch(tag):
            continue
        if channel == 'stable' and (item.get('prerelease') or version_key(tag)[3] != 3):
            continue
        eligible.append(item)
    if not eligible:
        raise RuntimeError('该更新通道暂无版本；当前 Alpha 可使用 --channel alpha。')
    release = max(eligible, key=lambda item: version_key(item['tag_name']))
    return release['tag_name'].removeprefix('v'), release


def asset_name(kind):
    if kind == 'pyz':
        return 'linsail.pyz'
    arch = {'x86_64': 'x86_64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine())
    if not arch:
        raise RuntimeError('当前架构没有独立发布包。')
    return 'linsail-linux-' + arch


def checked_download(version, name):
    version_key(version)
    base = f'https://github.com/{REPOSITORY}/releases/download/v{version}/'
    lines = fetch(base + 'SHA256SUMS', 32_768).decode('ascii').splitlines()
    matches = [line.split() for line in lines if len(line.split()) == 2 and line.split()[1] == name]
    if len(matches) != 1 or not re.fullmatch('[0-9a-f]{64}', matches[0][0]):
        raise ValueError('校验清单缺失、重复或无效。')
    data = fetch(base + name, 100_000_000)
    if digest(data) != matches[0][0]:
        raise ValueError('SHA256 校验失败，已安装版本保持不变。')
    return data


def probe(data, kind, directory, expected=None):
    """Only execute a downloaded candidate after its checksum is verified."""
    with tempfile.TemporaryDirectory(prefix='.linsail-check-', dir=directory) as temp:
        path = Path(temp) / ('candidate.pyz' if kind == 'pyz' else 'candidate')
        path.write_bytes(data)
        path.chmod(0o700)
        env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')
        if getattr(sys, 'frozen', False):
            original = env.pop('LD_LIBRARY_PATH_ORIG', None)
            env.pop('LD_LIBRARY_PATH', None)
            if original is not None:
                env['LD_LIBRARY_PATH'] = original
        command = [str(path)] if kind == 'binary' else [sys.executable, str(path)]
        try:
            result = subprocess.run(command + ['--version'], env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=30, check=False)
        except (subprocess.TimeoutExpired, OSError):
            raise RuntimeError('新程序无法启动或启动超时，已安装版本保持不变。') from None
        version = result.stdout.decode('utf-8', errors='replace').strip()
        if result.returncode != 0 or not VERSION.fullmatch(version) or (expected and version != expected):
            raise RuntimeError('新程序启动验证失败，已安装版本保持不变。')
        return version


def update(target=None, channel=None, check=False):
    destination = current_install()
    with install_lock(destination.parent):
        record = read_record(destination)
        channel = channel or ('alpha' if version_key(record['version'])[3] != 3 else 'stable')
        version, release = find_release(channel, target)
        print(f"当前：{record['version']}；目标：{version}（{channel}）")
        if not target and version_key(version) <= version_key(record['version']):
            print('当前已是此通道的最新版本。')
            return
        if check:
            print('仅检查，未下载或更改程序。')
            return
        name = asset_name(record['kind'])
        if name not in {item.get('name') for item in release.get('assets', [])}:
            raise RuntimeError('此版本没有对应架构的安装包，未做修改。')
        data = checked_download(version, name)
        probe(data, record['kind'], destination.parent, version)
        deploy(destination, data, record['kind'], version, record.get('shell_files', []))
        print(f'已更新到 {version}。下次启动生效；可运行 linsail rollback 回退。')


def rollback():
    destination = current_install()
    with install_lock(destination.parent):
        record = read_record(destination)
        previous = record.get('previous')
        backup = sidecars(destination)[1]
        if not previous or not backup.is_file():
            raise RuntimeError('没有可回退的上一版。')
        data = backup.read_bytes()
        if digest(data) != previous['sha256']:
            raise ValueError('上一版文件校验失败，未做修改。')
        if getattr(sys, 'frozen', False) and previous['kind'] == 'pyz':
            raise RuntimeError('上一版是 Python 包，请用 Python 版安装器恢复。')
        version = probe(data, previous['kind'], destination.parent, previous.get('version'))
        deploy(destination, data, previous['kind'], version, record.get('shell_files', []))
        print(f'已回退到 {version}。下次启动生效；用户配置保持不变。')


def uninstall(yes=False):
    destination = current_install()
    with install_lock(destination.parent):
        record = read_record(destination)
        print(f'将移除 {destination} 和上一版程序；保留模型配置和启动文件备份。')
        if not yes and input('确认卸载？[y/N]: ').strip().lower() != 'y':
            print('已取消。')
            return
        for item in record.get('shell_files', []):
            path = Path(item['path'])
            if path.is_symlink() or not path.is_file():
                continue
            text = path.read_text(encoding='utf-8')
            block = path_block(destination.parent, item['fish'])
            if text.count(block) == 1:
                atomic_write(path, text.replace(block, '', 1).encode(), path.stat().st_mode & 0o777)
            else:
                print(f'保留已修改的启动文件，请手动检查 LinSail PATH 标记：{path}')
        state, backup = sidecars(destination)
        destination.unlink()
        backup.unlink(missing_ok=True)
        state.unlink()
        print('已卸载。模型配置和 .linsail.bak 备份保留；新开终端后 PATH 清理生效。')
