"""Profiles contain endpoints and key environment names, never API keys."""
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "linsail" / "config.json"


def validate_endpoint(value):
    value = value.strip().rstrip("/")
    url = urlsplit(value)
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("接口地址不能包含用户名、密码、查询参数或片段。")
    if not url.hostname:
        raise ValueError("请输入完整的 API 地址，例如 https://example.com/v1。")
    if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise ValueError("远程接口必须使用 HTTPS；HTTP 仅允许本机回环地址。")
    return value


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError("模型配置必须是对象。")
    endpoint = validate_endpoint(profile.get("base_url", ""))
    model = profile.get("model", "")
    key_env = profile.get("key_env", "")
    if not isinstance(model, str) or not model.strip() or len(model) > 200 or any(ord(c) < 32 for c in model):
        raise ValueError("模型名称无效。")
    if not isinstance(key_env, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key_env):
        raise ValueError("API Key 环境变量名称无效。")
    kind = profile.get("kind", "byok")
    if kind not in {"byok", "hosted"}:
        raise ValueError("模型类型必须是 byok 或 hosted。")
    return dict(base_url=endpoint, model=model.strip(), key_env=key_env, kind=kind)


def load_config(path=None):
    path = Path(path or config_path())
    if not path.exists():
        return {"active": "", "profiles": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise ValueError("配置文件格式无效。")
    data["profiles"] = {name: validate_profile(p) for name, p in data["profiles"].items()}
    return data


def save_config(data, path=None):
    path = Path(path or config_path())
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def child_environment(profiles, environ=None):
    env = dict(os.environ if environ is None else environ)
    secrets = {p["key_env"] for p in profiles.values()}
    # Keep common model credentials out of the managed shell as well.
    secrets.update(k for k in env if k.endswith(("_API_KEY", "_API_TOKEN")))
    for key in secrets:
        env.pop(key, None)
    env.pop("BASH_ENV", None)
    env.pop("ENV", None)
    env.pop("PROMPT_COMMAND", None)
    env.pop("SHELLOPTS", None)
    env.pop("BASHOPTS", None)
    return env
