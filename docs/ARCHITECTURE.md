# 架构

```text
自然语言 / CLI
      │
      ▼
Agent（最多 16 步，逐条审批） ─── Provider ─── HTTPS 模型接口
      │                         byok / hosted
      ▼
持久 Bash + PTY ←→ 本机键盘
      │                 Ctrl+] 接管/返回
      └── 独立状态管道 → 完成状态、退出码、工作目录
```

## 模块

- `config.py`：模型配置、URL 校验、用户私有配置写入、子 Shell 环境过滤。
- `provider.py`：标准库 HTTP 客户端，Chat Completions 工具调用协议，拒绝重定向。
- `agent.py`：有限轮次工具循环，审批、拒绝与接管状态，完整工具结果序列。
- `terminal.py`：Linux PTY、Bash 生命周期、原始终端输入、窗口尺寸更新与提示符事件。
- `safety.py`：控制字符处理、精确密钥脱敏与辅助风险提示。
- `cli.py`：配置向导、模型选择、明确的数据发送提示和交互界面。

## 持久会话

通过 `pty.fork()` 启动 `bash --noprofile --rcfile ... -i`。AI 命令写入私有临时脚本，在同一 Bash 内 source，故 `cd` 和 `export` 保留。手动输入也转发至这一 PTY。

`PROMPT_COMMAND` 使用保留的 fd 9 写出退出码及 `$PWD`，以 NUL 分隔。父进程通过单独管道收取状态，避免把输出中的提示符文本误认为完成。任意已授权程序可干扰该协议，出错时停止继续执行。

自动模式限量捕获输出；手动模式关闭捕获。用户返回对话时会中断前台命令并等待提示符，保证不会把下一条命令误投给仍在运行的程序。屏幕程序需用户先退出。

## 协议与扩展

使用 `POST <base_url>/chat/completions`，请求包含 `tools`，响应读取 `tool_calls`，执行结果以 `role=tool` 和匹配的 `tool_call_id` 回传。参考 [OpenAI 官方 Function calling 文档](https://developers.openai.com/api/docs/guides/function-calling)。

后续可新增模型协议适配器、任务模板、交互式输出审查和可选 OS 沙箱，而不改变终端与审批接口。图形桌面不是首版依赖。
