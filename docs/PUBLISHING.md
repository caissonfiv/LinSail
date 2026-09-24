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

## 验证与预发布

1. 检查 `Test and build` 工作流全部通过，包括真实 Linux PTY 测试。
2. 在普通用户的 Linux 终端验收：`/shell`、cd/export 保留、Ctrl+]、Ctrl+C、sudo 提示与 SSH。
3. 用实际模型完成至少一个只读任务和一个测试机软件安装任务。
4. 更新版本、变更记录和已知限制，然后推送版本标签：

```bash
git tag v0.1.0a1
git push origin v0.1.0a1
```

`Publish alpha release` 再次运行测试后发布 GitHub Pre-release，附上单文件程序、源码 ZIP、安装脚本与 SHA256。不要在功能未验证时改成稳定版。工作流所需权限仅为该仓库 contents 写入，不含外部部署密钥。

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
