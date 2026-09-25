#!/bin/sh
# Run from a release directory or download this script on its own.
set -eu
[ "$(uname -s)" = Linux ] || { echo 'LinSail currently supports Linux only.' >&2; exit 1; }
[ "$(id -u)" != 0 ] || { echo '请使用普通用户安装，不要使用 sudo。' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo '需要 Python 3.10+。Ubuntu/Debian: sudo apt install python3；Fedora: sudo dnf install python3；Arch: sudo pacman -S python' >&2; exit 1; }
command -v bash >/dev/null 2>&1 || { echo '需要 Bash，请先用系统包管理器安装 bash。' >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "需要 Python 3.10+，请升级 Python 后重试。")'
release_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 - "$release_dir" <<'PY'
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

version = '0.1.0a2'
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
