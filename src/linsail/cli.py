import argparse
import getpass
import json
import os
import platform
import re
import shutil
import sys

from . import __version__
from .agent import Agent
from .config import child_environment, config_path, load_config, save_config, validate_profile
from .provider import Provider, ProviderError
from .safety import safe_text, warnings

HELP = """自然语言直接输入，例如：检查这台机器是否已经安装 Docker
/shell     进入同一个 Bash，Ctrl+] 返回（返回时会中断前台命令）
/new       清空模型对话，保留 Shell 状态
/models    查看模型配置；/use 名称 切换配置并清空对话
/help      帮助
/quit      退出
执行时可输入本机 sudo 密码；Ctrl+C 中断命令；Ctrl+] 接管终端。
每条 AI 命令均需确认。执行结果会发送至当前模型接口。
"""


def ask(label, default=""):
    answer = input(label + (f" [{default}]" if default else "") + ": ").strip()
    return answer or default


def configure():
    data = load_config()
    print("配置模型服务。密钥不写入配置文件，可用环境变量或启动时临时输入。")
    name = ask("配置名称", "personal")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        raise ValueError("名称仅允许 1–40 个字母、数字、下划线或连字符。")
    kind = ask("服务类型 byok=自带密钥 / hosted=运营方服务", "byok")
    base = ask("API Base URL（包含 /v1 等服务前缀）")
    model = ask("模型 ID（须支持工具调用）")
    key_env = ask("API Key 环境变量名称", "LINSAIL_HOSTED_API_KEY" if kind == "hosted" else "LINSAIL_API_KEY")
    profile = validate_profile(dict(base_url=base, model=model, key_env=key_env, kind=kind))
    if name in data["profiles"] and ask("将覆盖此同名配置，输入 yes 确认", "no") != "yes":
        print("已取消。")
        return
    data["profiles"][name] = profile
    data["active"] = name
    save_config(data)
    print(f"已保存到 {config_path()}。运行 linsail 开始。")


def doctor():
    print(f"启航 LinSail {__version__}")
    print(f"系统：{platform.system()} / {platform.machine()}")
    print(f"Python：{platform.python_version()}")
    print(f"Bash：{shutil.which('bash') or '未找到'}")
    print(f"交互终端：{'是' if sys.stdin.isatty() else '否'}")
    print(f"配置：{config_path()}")
    data = load_config()
    for name, p in data["profiles"].items():
        print(safe_text(f"  {name}: {p['kind']} / {p['model']} / {p['base_url']}"))
    print("此检查不会联系模型服务，也不会输出密钥。")


def approval(command, reason):
    print("\n┌─ 待执行命令 ───────────────────────────")
    print(safe_text(reason))
    print("\n" + command)
    for message in warnings(command):
        print("提醒：" + message)
    print("└─ 执行结果将发送给当前模型服务。")
    choice = input("执行？[y] 是 / [n] 停止 / [s] 手动接管（默认 n）: ").strip().lower()
    return {"y": "yes", "s": "shell"}.get(choice, "no")


def connect(profile):
    print(safe_text(f"\n模型：{profile['model']}  ·  {profile['base_url']}"))
    print("自然语言、审批过的命令及其输出将发往此地址；手动终端内容不会自动上传。")
    print("配置的模型密钥会从子 Shell 环境中移除；这不等于文件或进程隔离。")
    key = os.environ.get(profile["key_env"], "")
    if not key:
        key = getpass.getpass("API Key（仅本次保留在内存；本地无鉴权服务可回车）: ")
    if input("连接此服务？[y/N]: ").strip().lower() != "y":
        return None
    return Provider(profile, key)


def chat(profile_name=None, terminal_only=False):
    if not sys.platform.startswith("linux"):
        raise RuntimeError("交互执行仅支持 Linux。请把安装包复制到 Linux，或在 WSL 内运行。")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError("需要交互终端。通过 SSH 使用时请分配终端：ssh -t 主机。")
    if os.geteuid() == 0:
        raise RuntimeError("请用普通用户启动启航；需要管理权限时逐条确认 sudo 命令。")
    data = load_config()
    name = profile_name or data.get("active")
    if not terminal_only and name not in data["profiles"]:
        print("尚未配置模型。先运行 linsail configure；或 linsail --terminal 体验终端接管。")
        return
    provider = None if terminal_only else connect(data["profiles"][name])
    if not terminal_only and provider is None:
        return
    from .terminal import Terminal
    shell = Terminal(env=child_environment(data["profiles"]), input_fd=sys.stdin.fileno())
    agent = Agent(provider, shell, approval) if provider else None
    print(f"\n启航 LinSail {__version__} · Linux 初始化助手 · Alpha\n")
    print(HELP)
    try:
        while True:
            try:
                prompt = input("\n启航 › ").strip()
                if not prompt:
                    continue
                if prompt == "/quit":
                    break
                if prompt == "/help":
                    print(HELP)
                elif prompt == "/shell":
                    shell.manual()
                    if agent:
                        agent.note_manual()
                elif prompt == "/new":
                    if agent:
                        agent.reset()
                    print("对话已清空。Shell 状态仍然保留。")
                elif prompt == "/models":
                    for n, p in data["profiles"].items():
                        print(safe_text(f"{'*' if n == name else ' '} {n}: {p['kind']} / {p['model']}"))
                elif prompt.startswith("/use "):
                    selected = prompt[5:].strip()
                    if selected not in data["profiles"]:
                        print("未找到此配置；退出后用 linsail configure 添加。")
                        continue
                    new_provider = connect(data["profiles"][selected])
                    if new_provider:
                        name, provider = selected, new_provider
                        agent = Agent(provider, shell, approval)
                        print("已切换模型并清空对话。Shell 状态保留。")
                elif prompt.startswith("/"):
                    print("未知命令。输入 /help 查看帮助。")
                elif agent:
                    agent.run(prompt)
                else:
                    print("当前为无模型终端模式。输入 /shell，或 /use 配置名称 连接模型。")
            except KeyboardInterrupt:
                print("\n已中断对话。输入 /quit 退出。")
                if agent:
                    # A cancelled HTTP request/approval may leave incomplete calls.
                    agent.reset()
            except EOFError:
                break
            except ProviderError as exc:
                print("\n" + safe_text(str(exc)))
            except (OSError, RuntimeError) as exc:
                print("\n终端异常：" + safe_text(str(exc)))
                break
    finally:
        shell.close()


def main():
    parser = argparse.ArgumentParser(description="启航 LinSail — 自然语言与手动终端接力的 Linux 助手")
    parser.add_argument("action", nargs="?", choices=["configure", "doctor"])
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--profile", help="使用已保存的模型配置")
    parser.add_argument("--terminal", action="store_true", help="无需 API Key 体验手动终端")
    args = parser.parse_args()
    try:
        if args.action == "configure":
            configure()
        elif args.action == "doctor":
            doctor()
        else:
            chat(args.profile, args.terminal)
    except (ValueError, OSError, RuntimeError) as exc:
        print("错误：" + safe_text(str(exc)), file=sys.stderr)
        raise SystemExit(1)
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        raise SystemExit(130)
