"""Real Linux integration tests. Skipped on Windows; required in release CI."""
import os
import shlex
import sys
import tempfile
import threading
import time
import unittest


@unittest.skipUnless(sys.platform.startswith("linux"), "Requires real Linux PTY")
class TerminalTests(unittest.TestCase):
    def setUp(self):
        from linsail.terminal import Terminal
        self.terminal = Terminal(display=False, command_timeout=5)

    def tearDown(self):
        self.terminal.close()

    def test_directory_and_environment_persist(self):
        with tempfile.TemporaryDirectory(prefix="linsail test '") as directory:
            first = self.terminal.run("cd " + shlex.quote(directory) + "; export LINSAIL_TEST=alive")
            self.assertEqual(first["exit_code"], 0)
            second = self.terminal.run("printf 'VALUE:%s\\n' \"$LINSAIL_TEST\"; pwd")
            self.assertEqual(second["cwd"], directory)
            self.assertIn("VALUE:alive", second["output"])
            self.terminal.run("cd /")

    def test_failed_command_status(self):
        result = self.terminal.run("false")
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["status"], "completed")

    def test_large_output_bounded(self):
        result = self.terminal.run("printf '%050000d\\n' 1")
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["output"]), 24000)

    def test_timeout_recovers_shell(self):
        self.terminal.timeout = 0.3
        result = self.terminal.run("sleep 10")
        self.assertEqual(result["status"], "timeout")
        self.terminal.timeout = 5
        self.assertIn("recovered", self.terminal.run("echo recovered")["output"])

    def test_multiline_and_unicode(self):
        result = self.terminal.run("for n in 1 2; do\n printf '中文-%s\\n' \"$n\"\ndone")
        self.assertIn("中文-2", result["output"])

    def test_shell_exit_does_not_hang(self):
        with self.assertRaises(RuntimeError):
            self.terminal.run("exit")

    def test_manual_input_preserves_exports(self):
        read_fd, write_fd = os.pipe()
        self.terminal.input_fd = read_fd

        def user():
            time.sleep(0.1)
            os.write(write_fd, b"export LINSAIL_MANUAL=present\n")
            time.sleep(0.4)
            os.write(write_fd, b"\x1d")

        thread = threading.Thread(target=user)
        thread.start()
        try:
            self.terminal.manual()
            thread.join(timeout=3)
            self.terminal.input_fd = None
            result = self.terminal.run("printf 'MANUAL:%s\\n' \"$LINSAIL_MANUAL\"")
            self.assertIn("MANUAL:present", result["output"])
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_inflight_handoff_stops_capture(self):
        read_fd, write_fd = os.pipe()
        self.terminal.input_fd = read_fd

        def user():
            time.sleep(0.15)
            os.write(write_fd, b"\x1d")
            time.sleep(0.15)
            os.write(write_fd, b"\x03")
            time.sleep(0.2)
            os.write(write_fd, b"export LINSAIL_HANDOFF=ok\n")
            time.sleep(0.3)
            os.write(write_fd, b"\x1d")

        thread = threading.Thread(target=user)
        thread.start()
        try:
            result = self.terminal.run("sleep 10")
            self.assertEqual(result["status"], "manual_handoff")
            self.assertNotIn("output", result)
            thread.join(timeout=3)
            self.terminal.input_fd = None
            self.assertIn("HANDOFF:ok", self.terminal.run("echo HANDOFF:$LINSAIL_HANDOFF")["output"])
        finally:
            os.close(read_fd)
            os.close(write_fd)


if __name__ == "__main__":
    unittest.main()
