# 发布到 caissonfiv/LinSail

仓库目标：`https://github.com/caissonfiv/LinSail`。以下命令供维护者在获得仓库权限的环境使用。

## 首次上传

在源码根目录执行，将此项目单独初始化为仓库，避免带入其他本地文件：

```bash
git init -b main
git add .
git commit -m "Initial LinSail alpha"
git remote add origin https://github.com/caissonfiv/LinSail.git
git push -u origin main
```

先在 GitHub 创建空的公开仓库 `LinSail`。不要另外初始化 README 或 License，以免与本地首次提交冲突。项目已包含 MIT 许可。

## 当前发布状态

首个 `v0.1.0a1` Alpha 已通过手动触发的 `Import reviewed source and publish alpha` 工作流完成 Linux 测试、源码提交和公开发布。每次导入需要上传新版本源码包、更新手动工作流中的版本和校验和；导入后删除临时源码包。不要对已完成的版本重复运行。

`Test and build` 是后续持续测试工作流，只有只读仓库权限。**推送标签自动创建 Release 的工作流没有启用。** 后续版本目前由维护者手动发布；如需启用标签自动发布，应另行授权相应仓库写入权限。

## 后续版本验证与手动预发布

1. 检查 `Test and build` 工作流全部通过，包括真实 Linux PTY 测试。
2. 在普通用户的 Linux 终端验收：`/shell`、cd/export 保留、Ctrl+]、Ctrl+C、sudo 提示与 SSH。
3. 用实际模型完成至少一个只读任务和一个测试机软件安装任务。
4. 更新版本、变更记录和已知限制，使用新的版本号创建并推送标签。下面的 `vX.Y.Z` 是需要替换的占位符，不要重复发布首版标签：

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

5. 在 GitHub Releases 页面选择该标签，创建 Pre-release，附上 `python3 scripts/build.py` 生成的单文件程序、源码 ZIP、安装脚本与 SHA256。不要在功能未验证时改成稳定版。

## 安装验证

发布文件全部下载到同一个目录后：

```bash
sha256sum --check SHA256SUMS
sh install.sh
~/.local/bin/linsail --version
```

校验和只能检查下载内容一致性，不能替代发布者签名。未来正式版本应增加构建来源证明、签名、发行版测试和安全报告渠道。

## 卸载

默认安装位置是 `~/.local/bin/linsail`，删除这个文件即可移除程序。配置保留在 `~/.config/linsail`，确认不需要后再手动删除。自定义安装目录或 XDG_CONFIG_HOME 时以实际配置为准。

## 独立版构建

在 Ubuntu 22.04 x86_64，Python 3.12 环境执行：

```sh
python -m pip install pyinstaller==6.22.3
python scripts/build.py
python scripts/build_binary.py
python scripts/smoke_binary.py dist/linsail-linux-x86_64
```

发布 `dist` 中本版本文件，包括 THIRD_PARTY_NOTICES.txt。独立版测试须包含不带 Python/curl 的最小 Linux 容器。
