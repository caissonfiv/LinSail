"""Build a small, deterministic stdlib-only zipapp and distributable source archive."""
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
VERSION = "0.1.0a1"


def entry(archive, name, content):
    item = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    item.compress_type = zipfile.ZIP_DEFLATED
    item.external_attr = 0o644 << 16
    archive.writestr(item, content)


app = DIST / "linsail.pyz"
with app.open("wb") as handle:
    handle.write(b"#!/usr/bin/env python3\n")
    with zipfile.ZipFile(handle, "w") as archive:
        entry(archive, "__main__.py", "import sys\nif sys.version_info < (3, 10):\n    sys.exit('LinSail requires Python 3.10+')\nfrom linsail.cli import main\nmain()\n")
        for path in sorted((ROOT / "src").rglob("*.py")):
            entry(archive, path.relative_to(ROOT / "src").as_posix(), path.read_bytes())
app.chmod(0o755)
shutil.copyfile(ROOT / "scripts" / "install.sh", DIST / "install.sh")

source = DIST / f"linsail-{VERSION}-source.zip"
with zipfile.ZipFile(source, "w") as archive:
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if path.is_file() and not any(part in {"dist", ".git", "__pycache__", ".venv"} for part in rel.parts):
            entry(archive, "linsail/" + rel.as_posix(), path.read_bytes())

with (DIST / "SHA256SUMS").open("w", encoding="ascii", newline="\n") as handle:
    for path in [app, DIST / "install.sh", source]:
        handle.write(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n")
print(f"Built {app.name}: {app.stat().st_size:,} bytes")
print(f"Built {source.name}: {source.stat().st_size:,} bytes")
