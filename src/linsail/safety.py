"""Display hygiene and advisory warnings; NOT a sandbox or shell parser."""
import re
import unicodedata

ANSI = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-_]")


def safe_text(text):
    text = ANSI.sub("", str(text))
    return "".join(c for c in text if c in "\n\t" or not unicodedata.category(c).startswith("C"))


def redact(text, secrets=()):
    text = str(text)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def validate_command(command):
    if not isinstance(command, str) or not command.strip() or len(command) > 12000:
        raise ValueError("命令为空或超过 12000 字符。")
    if any(unicodedata.category(c).startswith("C") and c not in "\n\t" for c in command):
        raise ValueError("命令包含不可见控制字符，已拒绝。")
    return command


def warnings(command):
    checks = [
        (r"\b(sudo|su|doas)\b", "需要提升权限；密码只在本机终端输入。"),
        (r"\b(rm|mkfs\S*|dd|wipefs|shred|reboot|shutdown)\b", "包含删除、磁盘操作或关机命令，请逐字检查。"),
        (r"\b(curl|wget)\b[\s\S]*[|][\s\S]*\b(sh|bash)\b", "会直接执行下载内容。建议先下载并检查脚本。"),
        (r"\b(ufw|iptables|nft|sshd)\b", "网络或 SSH 配置可能影响远程连接。"),
    ]
    return [message for pattern, message in checks if re.search(pattern, command)]
