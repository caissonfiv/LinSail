"""User-local installation and idempotent shell PATH integration."""
import os
import shlex
import stat
import sys
import tempfile
from pathlib import Path

START = "# >>> LinSail PATH >>>"
END = "# <<< LinSail PATH <<<"


def path_block(directory, fish=False):
    directory = str(directory)
    if any(c in directory for c in "\n\r\0"):
        raise ValueError("安装目录不能包含换行或空字符。")
    if fish:
        quoted = "'" + directory.replace("\\", "\\\\").replace("'", "\\'") + "'"
        body = f"if not contains -- {quoted} $PATH\n    set -gx PATH {quoted} $PATH\nend"
    else:
        quoted = shlex.quote(directory)
        body = f'case ":${{PATH-}}:" in\n    *:{quoted}:*) ;;\n    *) export PATH={quoted}:"${{PATH-}}" ;;\nesac'
    return f"{START}\n{body}\n{END}\n"


def merge_block(text, block):
    if START not in text and END not in text:
        return text + ("\n" if text and not text.endswith("\n") else "") + "\n" + block
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("发现损坏或重复的 LinSail PATH 标记；请先检查启动文件。")
    start, end = text.index(START), text.index(END)
    if end < start:
        raise ValueError("LinSail PATH 标记顺序错误。")
    end += len(END)
    if text[end:end + 1] == "\n":
        end += 1
    return text[:start] + block + text[end:]


def atomic_write(path, content, mode):
    fd, temporary = tempfile.mkstemp(prefix=".linsail-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configure_path(home, directory, shell="bash", environ=None):
    home, directory = Path(home), Path(directory).absolute()
    env = environ or {}
    shell = Path(shell).name
    if shell in {"bash", "sh", "dash", ""}:
        login = next((home / n for n in (".bash_profile", ".bash_login", ".profile") if (home / n).exists()), home / ".profile")
        targets = [(home / ".bashrc", False), (login, False)]
    elif shell == "zsh":
        root = Path(env.get("ZDOTDIR") or home).expanduser()
        if not root.is_absolute():
            root = home / root
        targets = [(root / ".zshrc", False), (root / ".zprofile", False)]
    elif shell == "fish":
        root = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
        targets = [(root / "fish" / "conf.d" / "linsail.fish", True)]
    else:
        raise ValueError(f"暂不自动修改 {shell} 的启动文件。设置 LINSAIL_NO_PATH=1 跳过，手动将 {directory} 加入 PATH。")
    changes = []
    for path, fish in targets:
        if path.is_symlink():
            raise ValueError(f"不覆盖符号链接 {path}；可设置 LINSAIL_NO_PATH=1 跳过 PATH 配置。")
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        new = merge_block(old, path_block(directory, fish))
        if new != old:
            changes.append((path, old, new))
    for path, old, new in changes:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup = path.with_name(path.name + ".linsail.bak")
            try:
                fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                    handle.write(old)
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        atomic_write(path, new.encode("utf-8"), mode)
    return [str(path) for path, _, _ in changes]


def install():
    if not sys.platform.startswith("linux") or os.geteuid() == 0:
        raise RuntimeError("请在 Linux 下使用普通用户安装，不要使用 sudo。")
    source = Path(sys.argv[0]).resolve()
    if source.suffix != ".pyz":
        raise RuntimeError("请通过官方 install.sh 或 python3 linsail.pyz install 安装。")
    home = Path.home()
    directory = Path(os.environ.get("LINSAIL_BIN_DIR") or home / ".local" / "bin").expanduser().absolute()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "linsail"
    if destination.is_symlink():
        raise ValueError(f"不覆盖现有符号链接：{destination}")
    if os.environ.get("LINSAIL_NO_PATH") != "1":
        for path in configure_path(home, directory, os.environ.get("SHELL", "bash"), os.environ):
            print("已配置 PATH：" + path)
    atomic_write(destination, source.read_bytes(), 0o755)
    print(f"\n启航 LinSail 安装成功：{destination}")
    print("新开终端后直接输入：linsail（首次运行自动配置模型）")
    print("安装子进程不能改变当前终端的 PATH。Bash/Zsh 当前窗口执行：")
    print("export PATH=" + shlex.quote(str(directory)) + ':"$PATH" && linsail')
    if Path(os.environ.get("SHELL", "")).name == "fish":
        print("Fish 当前窗口可先 source 对应的 fish/conf.d/linsail.fish 文件，再运行 linsail。")
