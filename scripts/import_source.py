"""Import a checksum-reviewed source archive in the manual release workflow."""
import hashlib
import os
import zipfile
from pathlib import Path, PurePosixPath

archive = Path('linsail-0.1.0a4-source.zip')
if hashlib.sha256(archive.read_bytes()).hexdigest() != os.environ['SOURCE_SHA256']:
    raise SystemExit('Source checksum mismatch')
root = Path.cwd().resolve()
with zipfile.ZipFile(archive) as package:
    for item in package.infolist():
        path = PurePosixPath(item.filename)
        if not path.parts or path.parts[0] != 'linsail' or '..' in path.parts:
            raise SystemExit('Invalid archive path')
        relative = Path(*path.parts[1:])
        if not relative.parts or relative.parts[0] in {'.github', '.git'}:
            continue
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise SystemExit('Path escaped repository')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(package.read(item))
archive.unlink()
