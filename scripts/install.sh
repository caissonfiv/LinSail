#!/bin/sh
# Local installer: download the release files first; no curl-to-shell execution.
set -eu
if [ "$(uname -s)" != Linux ]; then
  echo "LinSail currently supports Linux only." >&2
  exit 1
fi
command -v python3 >/dev/null 2>&1 || { echo "Python 3.10+ is required." >&2; exit 1; }
command -v bash >/dev/null 2>&1 || { echo "Bash is required." >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10+ is required")'
release_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install_dir=${LINSAIL_BIN_DIR:-"$HOME/.local/bin"}
python3 - "$release_dir" "$install_dir" <<'PY'
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

release, target_dir = map(Path, sys.argv[1:])
payload = release / "linsail.pyz"
manifest = release / "SHA256SUMS"
if not payload.is_file() or not manifest.is_file():
    sys.exit("Keep install.sh, linsail.pyz and SHA256SUMS in the same directory.")
expected = dict(line.split(None, 1)[::-1] for line in manifest.read_text().splitlines() if line.strip())
if expected.get("linsail.pyz") != hashlib.sha256(payload.read_bytes()).hexdigest():
    sys.exit("Checksum mismatch. Installation cancelled.")
target_dir.mkdir(parents=True, exist_ok=True)
destination = target_dir / "linsail"
if destination.is_symlink():
    sys.exit("Refusing to replace a symlink: " + str(destination))
fd, temporary = tempfile.mkstemp(prefix=".linsail-", dir=target_dir)
try:
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload.read_bytes())
    os.chmod(temporary, 0o755)
    os.replace(temporary, destination)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
print("Installed:", destination)
print("Run:", str(destination) + " configure")
print("Ensure this directory is on PATH:", target_dir)
PY
