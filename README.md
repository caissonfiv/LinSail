# 启航 LinSail

**用自然语言初始化 Linux，需要时接管同一个终端。**

LinSail 是一个轻量 Linux 终端智能体：你描述任务，它提出命令；你逐条确认，它执行并读取结果，继续检查或修复。你可以随时接管持久 Bash，保留工作目录和环境变量，再回到对话。

**当前版本：0.1.0a3 / Alpha。** 提供内置 Python 的 Linux x86_64 单文件程序，运行无需安装 Python、curl 或 pip。需要 glibc 2.35+、Bash、系统 CA 证书与交互终端；推荐 Ubuntu 22.04+。其他架构可使用原有 Python 3.10+ 版本。

[English](README.en.md) · [架构](docs/ARCHITECTURE.md) · [托管模型接入](docs/HOSTED_MODELS.md) · [发布流程](docs/PUBLISHING.md) · [隐私与执行边界](SECURITY.md)

## 能做什么

- 用中文或其他自然语言提出 Linux 安装、检查和配置任务。
- 通过支持工具调用的 Chat Completions 兼容接口接入模型。
- 支持个人 API Key 与运营方托管模型配置，运行中切换。
- 每条 AI 命令显示原文、用途和常见风险提示；默认不执行。
- 同一个 PTY/Bash 会话内保存 `cd`、`export` 和手动修改的状态。
- `/shell` 手动操作；执行中按 `Ctrl+]` 接管；再按 `Ctrl+]` 返回。
- 直接在目标电脑运行，或 SSH 登录目标电脑后运行。
- 单个 `.pyz` 文件分发、校验和、本地安装脚本、MIT 开源许可。

## 快速开始

推荐下载 Releases 中的 **`linsail-linux-x86_64`**（已内置 Python）。在普通用户终端运行：

```sh
chmod +x linsail-linux-x86_64
./linsail-linux-x86_64 install
export PATH="$HOME/.local/bin:$PATH"
linsail
```

以后直接输入 `linsail`。首次运行自动引导模型配置。也可不安装，直接 `./linsail-linux-x86_64`。

系统有 curl 时，可一键安装并启动（Bash / Zsh）：

```sh
curl -fL https://github.com/caissonfiv/LinSail/releases/download/v0.1.0a3/install.sh -o install.sh && sh install.sh && export PATH="$HOME/.local/bin:$PATH" && linsail
```

没有 curl 但有 wget 时，用下面命令下载脚本，再执行 `sh install.sh`：

```sh
wget -O install.sh https://github.com/caissonfiv/LinSail/releases/download/v0.1.0a3/install.sh
```

两个下载工具都没有时，可通过浏览器下载或从另一台电脑复制文件。运行独立版不依赖它们。离线校验安装：将 `linsail-linux-x86_64`、`install.sh`、`SHA256SUMS` 放在同一目录，执行 `sh install.sh`。请同时保留发行包中的第三方许可说明。

安装到 `~/.local/bin/linsail`，自动配置当前默认 Bash / Zsh / Fish 的 PATH；原有启动文件备份为 `.linsail.bak`。单独运行安装脚本后需要新开终端，或在 Bash / Zsh 执行上面的 `export PATH`。支持 `LINSAIL_BIN_DIR` 自定义目录、`LINSAIL_NO_PATH=1` 跳过启动文件配置。

**兼容范围：** 独立版为 x86_64 / glibc 2.35+，不适用于 Alpine/musl、ARM 或 Windows。需要可执行的临时目录；若 `/tmp` 挂载为 noexec，可设置 `TMPDIR` 指向自己的可执行目录。系统仍需 Bash 和 CA 证书。

**其他架构 / Python 版：** 下载 `linsail.pyz` 后用 `python3 linsail.pyz` 启动，或执行 `sh install-python.sh` 安装。这个备用安装器会检测 Python 3.10+、Bash、curl 和证书；缺少时在 apt-get / dnf 系统上先询问，再用 sudo 安装。可用 `LINSAIL_INSTALL_DEPS=0` 禁止安装依赖。旧发行版的软件源若没有 Python 3.10+，仍需升级系统。

没有模型也可以先体验 Shell：

```bash
linsail --terminal
# 输入 /shell；操作后按 Ctrl+] 返回，再输入 /quit
```

**请用普通用户运行。** 需要管理权限时，让已审批的命令通过 `sudo` 提示输入密码。LinSail 不接受 root 启动。

## 模型配置

运行 `linsail configure`，按提示设置：

| 字段 | 含义 |
| --- | --- |
| 配置名称 | 例如 `personal` 或 `hosted` |
| 类型 | `byok` 自带密钥，或 `hosted` 运营方服务 |
| Base URL | 服务商提供的兼容接口地址，包含 `/v1` 等前缀 |
| 模型 ID | 服务商实际支持且具备工具调用能力的模型 |
| Key 环境变量 | 默认为 `LINSAIL_API_KEY` 或 `LINSAIL_HOSTED_API_KEY` |

启动时可以隐式输入密钥，只保存在本次进程内存。也可以事先设置所配置的环境变量。不要把密钥粘贴在对话中或写入共享脚本。

远程接口要求 HTTPS；本地模型可使用 `http://127.0.0.1:端口/v1`。无需鉴权的本地服务可以在密钥提示处直接回车。模型必须支持 `/chat/completions` 的 `tools` 与 `tool_calls`，不是所有“兼容”服务都完整支持。

配置保存在 `$XDG_CONFIG_HOME/linsail/config.json`，默认 `~/.config/linsail/config.json`。文件不保存 API Key。启动及切换服务时会显示目标接口并征求连接确认。

**托管配置入口已经实现；官方充值、余额、购买页面及托管模型服务尚未上线。** 不需要购买 LinSail 服务也能使用自己的模型接口。

## 使用示例

```text
启航 › 检查这台机器的发行版，以及 Docker 是否已安装

┌─ 待执行命令
读取发行版信息，不修改系统。
cat /etc/os-release
└─ 执行结果将发送给当前模型服务。
执行？[y] 是 / [n] 停止 / [s] 手动接管（默认 n）:
```

以上是交互示意，具体命令由接入的模型提出。

| 操作 | 效果 |
| --- | --- |
| `/shell` | 进入当前 Bash，手动运行命令 |
| `Ctrl+]` | 执行中接管；手动模式中返回对话 |
| `Ctrl+C` | 执行时中断前台命令；对话时中断当前请求 |
| `/new` | 清空模型对话，保留 Shell |
| `/models` | 查看已配置服务 |
| `/use personal` | 切换服务，清空对话但保留 Shell |
| `/help` / `/quit` | 帮助 / 退出 |

手动模式返回会先发送 Ctrl+C，清除未提交的输入并中断前台命令。**不是把任意运行中的程序冻结后交给 AI。** `vim`、`top` 等程序请先正常退出，再按 Ctrl+]。不要用 `exit` 离开受管 Bash；这会结束整个 Shell，会话需要重启。

手动终端输出不会自动上传；回到对话后智能体会重新检查所需状态。自动执行模式支持本地密码提示；使用全屏交互程序请切到 `/shell`。Bash 不加载用户 `.bashrc`，以避免启动钩子与会话控制冲突；从父进程继承的普通环境变量仍保留。

## SSH

```bash
ssh -t your-server
# 在目标服务器安装并运行 LinSail
linsail
```

模型 HTTP 请求从目标机发出。目标机需要能访问所配置接口；`127.0.0.1` 指目标机自身。SSH 断线或 LinSail 退出会挂断受管终端，长期服务应通过系统服务管理器启动。

## 开发与构建

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 dist/linsail.pyz --version
```

构建输出为 `dist/linsail.pyz`、安装脚本、源码 ZIP 和 `SHA256SUMS`。运行和构建只使用标准库。可选 `pip install .` 会使用 setuptools 构建元数据，但普通用户无需 pip。

CI 在 Ubuntu 22.04 / 24.04 和 Python 3.10 / 3.12 上运行，包含真实 PTY 的目录/环境持久化、退出码、大输出、超时恢复、Shell 退出测试。其他发行版与 ARM 仍需实机体验。请以仓库实际 CI 结果为准，不把 Windows 上的跳过测试当成 Linux 通过。

## 目前的边界

- 没有图形桌面、自动回滚、任务恢复或后台守护进程。
- 没有沙箱：批准的命令以当前用户身份执行。风险提示不是防绕过机制。
- 默认每轮最多 16 次模型请求，单命令超时 300 秒；长安装可手动接管。
- 单命令回传末尾最多约 24 KB，完整屏幕输出不写入日志。
- 不保证检测所有敏感输出。不要审批读取凭证或隐私文件的命令。
- `PROMPT_COMMAND`、文件描述符 9 和终端设置是内部协议的一部分，手动改写会破坏会话。
- 未针对所有真实模型和软件安装场景完成验证，欢迎通过 Issues 提交已脱敏的问题。

## 许可

MIT。欢迎使用、修改、分发和商业集成，保留许可声明即可。
