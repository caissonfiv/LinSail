"""Build natively on Ubuntu 22.04 after installing PyInstaller 6.22.3."""
import hashlib
import importlib.metadata
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
arch = {'x86_64': 'x86_64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine())
if sys.platform != 'linux' or not arch:
    raise SystemExit('Build natively on Linux x86_64 or ARM64.')
name = 'linsail-linux-' + arch
notices = 'THIRD_PARTY_NOTICES-linux-' + arch + '.txt'
if importlib.metadata.version('pyinstaller') != '6.22.3':
    raise SystemExit('Build requires pyinstaller==6.22.3')
subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--onefile',
                '--noupx', '--name', name, '--paths', str(ROOT / 'src'),
                '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build'),
                '--specpath', str(ROOT / 'build'), str(ROOT / 'scripts/frozen_entry.py')], check=True)
notice = ['LinSail is MIT licensed. Bundled runtime third-party notices follow.\n']
python_license = next((p for p in [Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt',
                                  Path(sys.base_prefix) / 'LICENSE.txt'] if p.is_file()), None)
if python_license is None:
    raise SystemExit('Python license not found; refusing to publish without notices.')
notice.append(python_license.read_text())
dist = importlib.metadata.distribution('pyinstaller')
for file in dist.files or []:
    if 'COPYING' in str(file) or 'LICENSE' in str(file):
        path = Path(dist.locate_file(file))
        if path.is_file():
            notice.append('\n' + str(file) + '\n' + path.read_text(errors='replace'))
for package in ('libssl3', 'zlib1g', 'libbz2-1.0', 'liblzma5', 'libffi8', 'libexpat1'):
    path = Path('/usr/share/doc') / package / 'copyright'
    if path.is_file():
        notice.append('\n' + package + '\n' + path.read_text())
(ROOT / 'dist' / notices).write_text('\n'.join(notice))
with (ROOT / 'dist/SHA256SUMS').open('a') as handle:
    for filename in (name, notices):
        data = (ROOT / 'dist' / filename).read_bytes()
        handle.write(hashlib.sha256(data).hexdigest() + '  ' + filename + '\n')
print('Built standalone executable with Python included.')
