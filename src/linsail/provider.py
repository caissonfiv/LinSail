"""Dependency-free Chat Completions tool-calling adapter."""
import json
import urllib.error
import urllib.request

from .config import validate_profile
from .safety import redact

TOOLS = [{"type": "function", "function": {
    "name": "shell", "description": "Propose ONE Bash command for explicit human approval. Runs in a persistent local shell. Output is returned. Never assume approval or success.",
    "parameters": {"type": "object", "properties": {
        "command": {"type": "string", "description": "Exact Bash command; no terminal control characters."},
        "reason": {"type": "string", "description": "Short explanation in the user's language of purpose and relevant changes."},
    }, "required": ["command", "reason"], "additionalProperties": False}
}}]


class ProviderError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("接口发生重定向，已停止以避免凭证被转发；请核对 API 地址。")


class Provider:
    def __init__(self, profile, key="", timeout=60):
        self.profile = validate_profile(profile)
        self.key = key
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def complete(self, messages):
        body = {"model": self.profile["model"], "messages": messages, "tools": TOOLS, "stream": False}
        encoded = redact(json.dumps(body, ensure_ascii=False), [self.key]).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "linsail/0.1.0a1"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        request = urllib.request.Request(self.profile["base_url"] + "/chat/completions", data=encoded, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = response.read(2_000_001)
                if len(payload) > 2_000_000:
                    raise ProviderError("模型响应过大，已停止。")
                data = json.loads(payload)
        except urllib.error.HTTPError as exc:
            messages_by_code = {401: "凭证无效", 403: "没有权限", 402: "账户余额或计费状态不足", 429: "配额不足或请求过于频繁"}
            # Do not echo server error bodies: they may contain reflected credentials.
            raise ProviderError(f"接口 HTTP {exc.code}：{messages_by_code.get(exc.code, '请求失败，请检查模型和接口兼容性')}。") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProviderError(f"接口连接或响应失败（{type(exc).__name__}）。") from None
        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
            calls = message.get("tool_calls") or []
            if content is not None and not isinstance(content, str):
                raise ValueError("content")
            if not isinstance(calls, list) or len(calls) > 8:
                raise ValueError("tools")
            ids = set()
            for call in calls:
                if call["type"] != "function" or not isinstance(call["id"], str) or not call["id"] or call["id"] in ids:
                    raise ValueError("id")
                ids.add(call["id"])
                if not isinstance(call["function"]["arguments"], str) or not isinstance(call["function"]["name"], str):
                    raise ValueError("function")
            if not calls and not content:
                raise ValueError("empty")
            result = {"role": "assistant", "content": content}
            if calls:
                result["tool_calls"] = calls
            return result
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise ProviderError("响应格式无效；模型必须支持 Chat Completions 工具调用。") from None
