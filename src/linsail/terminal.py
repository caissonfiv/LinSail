"""Linux PTY with a persistent Bash and an out-of-band prompt status pipe.

This is a convenience boundary, NOT isolation: commands run with the user's rights.
fd 9 and PROMPT_COMMAND are reserved. No shell history or transcript is written.
"""
import contextlib
import errno
import os
import select
import shlex
import shutil
import signal
import struct
import sys
import tempfile
import time
from pathlib import Path

from .safety import safe_text


class Terminal:
    def __init__(self, env=None, display=True, input_fd=None, command_timeout=300):
        if not sys.platform.startswith("linux"):
            raise RuntimeError("终端执行目前仅支持 Linux；Windows 请在 WSL 内运行。")
        import fcntl
        import pty
        import termios

        bash = shutil.which("bash")
        if not bash:
            raise RuntimeError("未找到 Bash。请先通过系统包管理器安装 bash。")
        self.display = display
        self.input_fd = input_fd
        self.timeout = command_timeout
        self.closed = False
        self.ready = False
        self.events = 0
        self.status = None
        self.cwd = os.getcwd()
        self._control_buffer = b""
        self._parts = []
        self._captured = bytearray()
        self._capture_enabled = False
        self._capture_truncated = False
        self._manual_display = False
        self.directory = tempfile.TemporaryDirectory(prefix="linsail-")
        rc = Path(self.directory.name) / "bashrc"
        rc.write_text(
            "HISTFILE=/dev/null\nHISTSIZE=0\nset +o history\n"
            "PS1='linsail-shell \\w \\$ '\nPS2='> '\n"
            "PROMPT_COMMAND='builtin printf \"%s\\0%s\\0\" \"$?\" \"$PWD\" >&9'\n",
            encoding="utf-8",
        )
        control_r, control_w = os.pipe()
        pid, master = pty.fork()
        if pid == 0:
            try:
                os.close(control_r)
                if control_w != 9:
                    os.dup2(control_w, 9)
                    os.close(control_w)
                os.set_inheritable(9, True)
                child_env = dict(os.environ if env is None else env)
                child_env["HISTFILE"] = "/dev/null"
                os.execve(bash, [bash, "--noprofile", "--rcfile", str(rc), "-i"], child_env)
            except BaseException:
                os._exit(127)
        os.close(control_w)
        self.pid, self.master, self.control = pid, master, control_r
        os.set_blocking(master, False)
        os.set_blocking(control_r, False)
        self._old_resize = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, self._resize)
        self._resize()
        try:
            self._wait_prompt(0, 5)
        except BaseException:
            self.close()
            raise

    def _resize(self, *_):
        import fcntl
        import termios
        size = shutil.get_terminal_size((100, 30))
        try:
            fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", size.lines, size.columns, 0, 0))
        except OSError:
            pass

    @contextlib.contextmanager
    def _raw(self):
        import termios
        import tty
        saved = None
        if self.input_fd is not None and os.isatty(self.input_fd):
            saved = termios.tcgetattr(self.input_fd)
            tty.setraw(self.input_fd)
        try:
            yield
        finally:
            if saved is not None:
                termios.tcsetattr(self.input_fd, termios.TCSADRAIN, saved)

    def _write(self, data):
        while data:
            _, writable, _ = select.select([], [self.master], [], 3)
            if not writable:
                raise RuntimeError("终端输入超时。")
            count = os.write(self.master, data)
            data = data[count:]

    def _read(self, fd):
        try:
            data = os.read(fd, 8192)
        except BlockingIOError:
            return
        except OSError as exc:
            if exc.errno == errno.EIO:
                raise RuntimeError("Shell 已退出。请重新启动启航。") from None
            raise
        if not data:
            raise RuntimeError("Shell 控制通道已关闭。")
        if fd == self.control:
            self._control_buffer += data
            if len(self._control_buffer) > 32768:
                raise RuntimeError("Shell 状态通道无效。")
            while b"\0" in self._control_buffer:
                field, self._control_buffer = self._control_buffer.split(b"\0", 1)
                self._parts.append(field)
                if len(self._parts) == 2:
                    try:
                        self.status = int(self._parts[0])
                    except ValueError:
                        raise RuntimeError("Shell 状态损坏，请重新启动。") from None
                    self.cwd = self._parts[1].decode("utf-8", "replace")
                    self._parts.clear()
                    self.events += 1
                    self.ready = True
            return
        if self._capture_enabled:
            self._captured.extend(data)
            if len(self._captured) > 24000:
                del self._captured[:-24000]
                self._capture_truncated = True
        if self.display:
            if self._manual_display:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
            else:
                text = safe_text(data.decode("utf-8", "replace"))
                if self.input_fd is not None:
                    text = text.replace("\n", "\r\n")
                sys.stdout.write(text)
                sys.stdout.flush()

    def _pump(self, timeout=0.1, input_enabled=False):
        fds = [self.master, self.control]
        if input_enabled and self.input_fd is not None:
            fds.append(self.input_fd)
        readable, _, _ = select.select(fds, [], [], timeout)
        for fd in readable:
            if fd == self.input_fd:
                data = os.read(fd, 4096)
                if not data:
                    raise EOFError("终端输入已关闭。")
                if b"\x1d" in data:  # Ctrl+] is local, never forwarded.
                    before, _ = data.split(b"\x1d", 1)
                    if before:
                        self._write(before)
                    return "handoff"
                self.ready = False
                self._write(data)
            else:
                self._read(fd)
        return None

    def _drain(self):
        # A completion can be observed before the last PTY bytes become readable.
        end = time.monotonic() + 0.15
        while time.monotonic() < end:
            readable, _, _ = select.select([self.master, self.control], [], [], 0.02)
            for fd in readable:
                self._read(fd)

    def _wait_prompt(self, previous, timeout, input_enabled=False):
        end = time.monotonic() + timeout
        while self.events <= previous:
            if time.monotonic() >= end:
                raise TimeoutError("未等到 Shell 提示符。")
            if self._pump(input_enabled=input_enabled) == "handoff":
                return "handoff"
        self._drain()
        return "completed"

    def run(self, command):
        if not self.ready or self.closed:
            raise RuntimeError("Shell 尚未就绪；请先进入 /shell 处理正在运行的程序。")
        self._drain()
        script = Path(self.directory.name) / "command.sh"
        script.write_text(command + "\n", encoding="utf-8")
        previous = self.events
        self._captured.clear()
        self._capture_truncated = False
        self._capture_enabled = True
        self.ready = False
        try:
            with self._raw():
                self._write(("builtin source " + shlex.quote(str(script)) + "\n").encode())
                try:
                    outcome = self._wait_prompt(previous, self.timeout, input_enabled=True)
                except TimeoutError:
                    self._write(b"\x03")
                    try:
                        self._wait_prompt(previous, 3)
                    except TimeoutError:
                        self.ready = False
                    outcome = "timeout"
                if outcome == "handoff":
                    self._capture_enabled = False
                    self._manual_loop()
                    return {"status": "manual_handoff", "reason": "User took over; command outcome is unknown. Manual output not shared."}
            output = safe_text(self._captured.decode("utf-8", "replace"))
            return {"status": outcome, "exit_code": self.status if self.ready else None,
                    "cwd": self.cwd, "output": output, "truncated": self._capture_truncated}
        finally:
            self._capture_enabled = False
            script.unlink(missing_ok=True)

    def _manual_loop(self):
        if self.input_fd is None:
            raise RuntimeError("手动接管需要交互终端。")
        self._manual_display = True
        try:
            sys.stdout.write("\r\n── 手动终端：Ctrl+] 返回对话；请先退出 vim/top 等程序 ──\r\n")
            sys.stdout.flush()
            while True:
                if self._pump(input_enabled=True) == "handoff":
                    # Clear partial input and interrupt a foreground command before
                    # giving control back to the agent. Never submit pending text.
                    previous = self.events
                    self._write(b"\x03")
                    try:
                        self._wait_prompt(previous, 2)
                        break
                    except TimeoutError:
                        sys.stdout.write("\r\n当前程序尚未退出，请手动退出后再次按 Ctrl+]。\r\n")
                        sys.stdout.flush()
        finally:
            self._manual_display = False

    def manual(self):
        with self._raw():
            self._manual_loop()

    def close(self):
        if self.closed:
            return
        self.closed = True
        signal.signal(signal.SIGWINCH, self._old_resize)
        # Closing the controlling PTY hangs up its foreground jobs as a terminal does.
        for fd in (self.master, self.control):
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.kill(self.pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        for _ in range(20):
            if os.waitpid(self.pid, os.WNOHANG)[0]:
                break
            time.sleep(0.025)
        else:
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(self.pid, 0)
        self.directory.cleanup()
