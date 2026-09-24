import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from linsail.agent import Agent
from linsail.config import child_environment, load_config, save_config, validate_endpoint, validate_profile
from linsail.provider import Provider, ProviderError
from linsail.safety import safe_text, validate_command


def tool(command="printf hello", identity="call_1"):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": identity, "type": "function", "function": {
            "name": "shell", "arguments": json.dumps({"command": command, "reason": "Inspect"})}}
    ]}


class FakeProvider:
    key = "test-secret-never-send"

    def __init__(self, replies):
        self.replies = iter(replies)

    def complete(self, _):
        return next(self.replies)


class FakeShell:
    def __init__(self):
        self.commands = []
        self.manual_count = 0

    def run(self, command):
        self.commands.append(command)
        return {"status": "completed", "exit_code": 0, "output": "test-secret-never-send"}

    def manual(self):
        self.manual_count += 1


class SafetyTests(unittest.TestCase):
    def test_endpoint_transport_and_credentials(self):
        for endpoint in ["http://public.example/v1", "https://u:p@example.com", "https://example.com?key=x", "file:///tmp/x"]:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                validate_endpoint(endpoint)
        self.assertEqual(validate_endpoint("http://127.0.0.1:11434/v1/"), "http://127.0.0.1:11434/v1")

    def test_hidden_command_control_rejected(self):
        for command in ["echo \x1b[2J", "echo a\rdo bad", "echo \u202eevil", "\x00", ""]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                validate_command(command)
        self.assertEqual(validate_command("printf '中文'\npwd"), "printf '中文'\npwd")

    def test_display_escapes_removed(self):
        self.assertEqual(safe_text("\x1b[31mhello\x1b[0m\x1b]52;c;secret\x07\u202e"), "hello")

    def test_profile_keys_not_leaked_to_child(self):
        env = {"PATH": "/bin", "MY_CREDENTIAL": "secret", "OPENAI_API_KEY": "secret", "ENV": "bad"}
        self.assertEqual(child_environment({"a": {"key_env": "MY_CREDENTIAL"}}, env), {"PATH": "/bin"})

    def test_config_round_trip_no_secret(self):
        profile = validate_profile({"base_url": "https://example.com/v1", "model": "model", "key_env": "MY_KEY", "kind": "hosted", "api_key": "must not persist"})
        self.assertNotIn("api_key", profile)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            data = {"active": "commercial", "profiles": {"commercial": profile}}
            save_config(data, path)
            self.assertEqual(load_config(path), data)
            self.assertNotIn("must not persist", path.read_text())
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class AgentTests(unittest.TestCase):
    def test_denial_never_executes_and_fulfills_all_tool_ids(self):
        reply = tool()
        reply["tool_calls"] += tool("echo second", "call_2")["tool_calls"]
        shell = FakeShell()
        agent = Agent(FakeProvider([reply]), shell, lambda *_: "no", lambda *_: None)
        agent.run("do something")
        self.assertEqual(shell.commands, [])
        self.assertEqual([m["tool_call_id"] for m in agent.messages if m["role"] == "tool"], ["call_1", "call_2"])

    def test_approved_command_then_final_and_redaction(self):
        shell = FakeShell()
        agent = Agent(FakeProvider([tool(), {"role": "assistant", "content": "Done"}]), shell, lambda *_: "yes", lambda *_: None)
        agent.run("hello")
        self.assertEqual(shell.commands, ["printf hello"])
        result = next(m["content"] for m in agent.messages if m["role"] == "tool")
        self.assertNotIn(FakeProvider.key, result)
        self.assertIn("REDACTED", result)

    def test_manual_handoff_does_not_execute_proposal(self):
        shell = FakeShell()
        agent = Agent(FakeProvider([tool()]), shell, lambda *_: "shell", lambda *_: None)
        agent.run("hello")
        self.assertEqual(shell.commands, [])
        self.assertEqual(shell.manual_count, 1)

    def test_malformed_arguments_fail_closed(self):
        shell = FakeShell()
        reply = tool()
        reply["tool_calls"][0]["function"]["arguments"] = "not json"
        agent = Agent(FakeProvider([reply]), shell, lambda *_: self.fail("must not approve"), lambda *_: None)
        agent.run("hello")
        self.assertEqual(shell.commands, [])

    def test_step_budget(self):
        shell = FakeShell()
        agent = Agent(FakeProvider([tool(identity=str(i)) for i in range(3)]), shell, lambda *_: "yes", lambda *_: None, max_steps=2)
        agent.run("hello")
        self.assertEqual(len(shell.commands), 2)


class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = []
        cls.mode = "ok"

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                content = self.rfile.read(int(self.headers["Content-Length"]))
                cls.requests.append((self.path, self.headers, content))
                if cls.mode == "redirect":
                    self.send_response(307)
                    self.send_header("Location", "/stolen")
                    self.end_headers()
                    return
                if cls.mode == "unauthorized":
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b"sensitive-api-key-reflected")
                    return
                self.send_response(200)
                self.end_headers()
                payload = {"choices": [{"message": tool()}]} if cls.mode == "ok" else {"choices": []}
                self.wfile.write(json.dumps(payload).encode())

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.__class__.mode = "ok"
        self.requests.clear()
        self.provider = Provider(dict(base_url=f"http://127.0.0.1:{self.server.server_port}/v1", model="fake", key_env="TEST_KEY"), "sensitive-api-key-reflected")

    def test_protocol_headers_tool_call_and_secret_redaction(self):
        result = self.provider.complete([{"role": "user", "content": self.provider.key}])
        self.assertEqual(result["tool_calls"][0]["id"], "call_1")
        path, headers, raw = self.requests[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer " + self.provider.key)
        body = json.loads(raw)
        self.assertEqual(body["messages"][0]["content"], "[REDACTED]")
        self.assertEqual(body["tools"][0]["function"]["name"], "shell")

    def test_redirect_never_forwards_credentials(self):
        self.__class__.mode = "redirect"
        with self.assertRaises(ProviderError):
            self.provider.complete([])
        self.assertEqual(len(self.requests), 1)

    def test_http_errors_do_not_leak_body(self):
        self.__class__.mode = "unauthorized"
        with self.assertRaises(ProviderError) as caught:
            self.provider.complete([])
        self.assertNotIn(self.provider.key, str(caught.exception))
        self.assertIn("401", str(caught.exception))

    def test_invalid_response(self):
        self.__class__.mode = "invalid"
        with self.assertRaises(ProviderError):
            self.provider.complete([])


if __name__ == "__main__":
    unittest.main()
