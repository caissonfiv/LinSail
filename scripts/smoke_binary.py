"""Verify frozen CLI, installation and real PTY handoff with no Python on PATH."""
import os
import json
import hashlib
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

binary = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as temp:
    home = Path(temp)
    limited = home / 'path'
    limited.mkdir()
    (limited / 'bash').symlink_to(shutil.which('bash'))
    env = {**os.environ, 'HOME': temp, 'XDG_CONFIG_HOME': str(home / '.config'),
           'PATH': str(limited), 'SHELL': '/bin/bash', 'LINSAIL_BIN_DIR': str(home / '.local/bin')}
    env.pop('LINSAIL_NO_PATH', None)
    for action in ('--version', 'doctor', 'install'):
        subprocess.run([str(binary), action], env=env, check=True, timeout=30)
    installed = home / '.local/bin/linsail'
    master, slave = pty.openpty()
    process = subprocess.Popen([str(installed), '--terminal'], env=env,
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = bytearray()
    def expect(needle):
        deadline = time.monotonic() + 20
        while needle.encode() not in output:
            if time.monotonic() > deadline:
                raise AssertionError('Timed out waiting for ' + needle + ': ' + output.decode(errors='replace'))
            if select.select([master], [], [], 0.2)[0]:
                output.extend(os.read(master, 65536))
        output.clear()
    try:
        expect('启航 ›')
        os.write(master, b'/shell\n')
        expect('── 手动终端：')
        os.write(master, b"printf 'FROZEN_%s\\n' OK; printf 'LIB=%s\\n' \"${LD_LIBRARY_PATH-}\"\n")
        expect('FROZEN_OK')
        os.write(master, b'\x1d')
        expect('启航 ›')
        os.write(master, b'/quit\n')
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
    # Exercise frozen self-replacement and backup validation without networking.
    record_path = installed.with_name('.linsail-install.json')
    record = json.loads(record_path.read_text())
    saved = installed.read_bytes()
    installed.with_name('.linsail-previous').write_bytes(saved)
    record['previous'] = dict(kind='binary', version=record['version'], sha256=hashlib.sha256(saved).hexdigest())
    record_path.write_text(json.dumps(record))
    subprocess.run([str(installed), 'rollback'], env=env, check=True, timeout=40)
    config = home / '.config/linsail/config.json'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"profiles": {}, "active": ""}')
    subprocess.run([str(installed), 'uninstall', '--yes'], env=env, check=True, timeout=30)
    assert not installed.exists() and config.exists()
    assert '# >>> LinSail PATH >>>' not in (home / '.bashrc').read_text()
print('Frozen install and PTY smoke passed with no python/curl/wget on PATH.')
