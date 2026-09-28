#!/bin/sh
# Run from a release directory or download this script on its own.
set -eu
[ "$(uname -s)" = Linux ] || { echo 'LinSail currently supports Linux only.' >&2; exit 1; }
[ "$(id -u)" != 0 ] || { echo '请使用普通用户安装，不要使用 sudo。' >&2; exit 1; }
# Keep this bootstrap POSIX sh: Python and Bash may not exist yet.
python_ready() {
    command -v python3 >/dev/null 2>&1 && python3 -c 'import sys, ssl, urllib.request; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}
set --
python_ready || set -- "$@" python3
command -v bash >/dev/null 2>&1 || set -- "$@" bash
command -v curl >/dev/null 2>&1 || set -- "$@" curl
if ! python_ready || ! python3 -c 'import ssl, sys, pathlib; paths=("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/ca-bundle.pem"); sys.exit(0 if ssl.create_default_context().get_ca_certs() or any(pathlib.Path(p).is_file() and ssl.create_default_context(cafile=p).get_ca_certs() for p in paths) else 1)' >/dev/null 2>&1; then
    set -- "$@" ca-certificates
fi
if [ "$#" -gt 0 ]; then
    printf '需要安装或更新以下系统依赖：'; printf ' %s' "$@"; printf '\n'
    if [ "${LINSAIL_INSTALL_DEPS:-ask}" = 0 ]; then
        echo '已禁用自动安装依赖，请由系统管理员安装以上软件包。' >&2
        exit 1
    fi
    if command -v apt-get >/dev/null 2>&1; then
        manager=apt-get
    elif command -v dnf >/dev/null 2>&1; then
        manager=dnf
    else
        echo '自动安装依赖目前支持 apt-get / dnf。请先通过本机包管理器安装 Python 3.10+、Bash、curl 和 CA 证书，再运行此脚本。' >&2
        exit 1
    fi
    command -v sudo >/dev/null 2>&1 || { echo '未找到 sudo；请联系管理员安装上述依赖，然后用普通用户重新运行。' >&2; exit 1; }
    echo "将通过 sudo $manager 安装以上软件包及其依赖；LinSail 本身仍以普通用户安装。"
    case "${LINSAIL_INSTALL_DEPS:-ask}" in
        1) ;;
        ask)
            if ! ( : </dev/tty ) 2>/dev/null; then
                echo '没有交互终端，未修改系统。确认后可用 LINSAIL_INSTALL_DEPS=1 sh install.sh。' >&2
                exit 1
            fi
            printf '继续安装依赖？[y/N] ' >/dev/tty
            IFS= read -r answer </dev/tty || exit 1
            case "$answer" in y|Y|yes|YES) ;; *) echo '已取消，未安装依赖。'; exit 1;; esac
            ;;
        *) echo 'LINSAIL_INSTALL_DEPS 只能是 ask、1 或 0。' >&2; exit 1;;
    esac
    # Never feed downloaded script bytes to sudo/package-manager stdin.
    if [ "$manager" = apt-get ]; then
        sudo apt-get update </dev/null
        sudo apt-get install -y --no-install-recommends "$@" </dev/null
    else
        sudo dnf install -y "$@" </dev/null
    fi
    hash -r
fi
python_ready || { echo '系统源未提供可用的 Python 3.10+（含 SSL），或 PATH 中的旧 Python 覆盖了系统版本。请升级发行版或修正 PATH 后重试；不会替换系统 Python。' >&2; exit 1; }
command -v bash >/dev/null 2>&1 && command -v curl >/dev/null 2>&1 || { echo '依赖安装后检查失败，请查看包管理器输出。' >&2; exit 1; }
release_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 - "$release_dir" <<'PY'
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

version = '0.1.0a3'
local = pathlib.Path(sys.argv[1])
base = f'https://github.com/caissonfiv/LinSail/releases/download/v{version}'
try:
    with tempfile.TemporaryDirectory(prefix='linsail-install-') as temporary:
        root = pathlib.Path(temporary)
        use_local = all((local / name).is_file() for name in ('linsail.pyz', 'SHA256SUMS'))
        for name in ('linsail.pyz', 'SHA256SUMS'):
            if use_local:
                data = (local / name).read_bytes()
            else:
                print('下载：' + name, flush=True)
                with urllib.request.urlopen(base + '/' + name, timeout=60) as response:
                    data = response.read(5_000_001)
                if len(data) > 5_000_000:
                    raise ValueError('下载文件异常大')
            (root / name).write_bytes(data)
        checksums = dict(line.split(None, 1)[::-1] for line in (root / 'SHA256SUMS').read_text().splitlines() if line.strip())
        app = root / 'linsail.pyz'
        if checksums.get('linsail.pyz') != hashlib.sha256(app.read_bytes()).hexdigest():
            raise ValueError('SHA256 校验失败，安装已取消')
        subprocess.run([sys.executable, str(app), 'install'], check=True)
except (OSError, ValueError, subprocess.CalledProcessError) as error:
    sys.exit('安装失败：' + str(error))
PY
