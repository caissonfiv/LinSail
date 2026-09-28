# 启航 LinSail 0.1.0a4 — ARM64 与安装维护

- 新增 ARM64 独立文件，安装脚本自动选择 x86_64 / ARM64，并检查 glibc 2.35+。
- `linsail update --check` 检查更新；`linsail update` 校验和试运行通过后更新。
- `linsail update --to 0.1.0a4` 固定版本；支持 alpha / stable 通道。
- `linsail rollback` 回到保留的上一版。
- `linsail uninstall` 确认后卸载程序，保留模型配置和用户修改的 Shell 内容。
- 并发互斥、写入错误恢复及安装记录校验。

从旧版升级需要先运行本版本安装器。独立版内置 Python，运行及更新无需 curl 或 pip。需要 Linux x86_64 / ARM64、glibc 2.35+、Bash、系统 CA 证书及可执行临时目录。仍为 Alpha，Alpine/musl 暂不提供独立包。
