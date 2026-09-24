# 启航 LinSail 0.1.0a1 — Alpha

自然语言与手动终端接力的 Linux 初始化助手。

- 单文件分发，无第三方 Python 运行依赖。
- 自带 API Key 与托管模型接口配置。
- 模型工具调用、逐条审批、有限轮次执行。
- 同一持久 Bash 内的目录/环境保留与 Ctrl+] 手动接管。
- 本机和 SSH TTY 支持、超时中断与错误提示。
- MIT 开源，附源码、安装脚本和 SHA256SUMS。

需要 Linux、Python 3.10+、Bash 和普通用户交互终端。下载三个文件 `linsail.pyz`、`install.sh`、`SHA256SUMS` 到同一目录，运行 `sh install.sh`。

这是早期测试版本。命令以用户权限运行，并非沙箱。真实模型兼容性、跨发行版初始化、完整屏幕交互仍需更多实机验证。托管付费服务尚未上线。请在测试机先体验，并查看 README 和 SECURITY.md。
