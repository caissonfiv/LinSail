# 启航 LinSail 0.1.0a2 — Alpha

安装后直接运行 `linsail`，首次运行自动引导模型配置。

- 安装脚本可独立下载程序，并校验 SHA256。
- 自动配置 Bash / Zsh / Fish 的 PATH，备份现有启动文件，重复安装不重复添加。
- 支持自定义安装目录和跳过 PATH 配置。
- 保留单文件、无第三方 Python 运行依赖、本机与 SSH 使用方式。

在普通用户的 Bash / Zsh 终端执行：

```bash
bash -o pipefail -c 'curl -fsSL https://github.com/caissonfiv/LinSail/releases/download/v0.1.0a2/install.sh | sh' && export PATH="$HOME/.local/bin:$PATH" && linsail
```

以后输入 `linsail` 即可。需要 Linux、Python 3.10+、Bash，下载命令需要 curl。仍为 Alpha；付费托管模型服务尚未上线。
