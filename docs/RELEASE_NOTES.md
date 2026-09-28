# 启航 LinSail 0.1.0a3 — 内置 Python 的独立版

- 新增 `linsail-linux-x86_64` 单文件程序，运行不需要安装 Python、pip 或 curl。
- 下载后 `chmod +x linsail-linux-x86_64`，再执行 `./linsail-linux-x86_64 install`；新开终端输入 `linsail`。
- 主安装器支持 curl / wget 下载及本地校验安装；没有下载工具时可以复制文件到目标机。
- 保留 `.pyz` 与 `install-python.sh`；备用 Python 安装器支持经确认后通过 apt-get / dnf 安装缺失依赖。
- 隔离封装运行库对系统 Bash 子进程的影响。

独立版要求 Linux x86_64、glibc 2.35+、Bash、系统 CA 证书和可执行临时目录；不适用于 ARM、Alpine/musl 或 Windows。仍为 Alpha，付费托管模型服务尚未上线。
