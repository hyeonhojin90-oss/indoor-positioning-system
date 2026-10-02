import io
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import server


class ServerTests(unittest.TestCase):
    def test_stdio_handshake_and_validation_without_network(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "school_ai_ask", "arguments": {"model": "unknown", "prompt": "test"}}},
        ]
        process = subprocess.run([sys.executable, server.__file__],
                                 input="".join(json.dumps(m) + "\n" for m in messages),
                                 encoding="utf-8", capture_output=True, timeout=10, check=True)
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([r["id"] for r in replies], [1, 2, 3])
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(replies[1]["result"]["tools"][0]["name"], "school_ai_ask")
        self.assertTrue(replies[2]["result"]["isError"])

    def test_exact_payload_and_response(self):
        reply = {"model": "gpt-6-astra", "choices": [{"message": {"content": "검토 완료"},
                  "finish_reason": "stop"}], "usage": {"total_tokens": 10}}
        stream = io.BytesIO(json.dumps(reply).encode("utf-8"))
        with patch.object(server, "api_key", return_value="fake-test-key"), \
             patch.object(server.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = stream
            result = server.ask({"model": "gpt-6-astra", "prompt": "검토", "context": "code"})
            request = opener.return_value.open.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(body["model"], "gpt-6-astra")
            self.assertEqual(body["messages"][0]["content"], "검토\n\nReference context:\ncode")
            self.assertEqual(result["answer"], "검토 완료")

    def test_limits_fail_before_network(self):
        for args in ({"model": "gpt-6-astra", "prompt": "x", "max_tokens": True},
                     {"model": "gpt-6-astra", "prompt": "x" * 20001},
                     {"model": "gpt-6-astra", "prompt": "x", "url": "https://evil.invalid"}):
            with self.assertRaises(ValueError):
                server.validate(args)

    def test_no_key_leak_in_http_error(self):
        error = server.urllib.error.HTTPError(server.ENDPOINT, 401, "Unauthorized", {},
                                            io.BytesIO(b'fake-test-key'))
        with patch.object(server, "api_key", return_value="fake-test-key"), \
             patch.object(server.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = error
            result = server.tool_result({"model": "gpt-6.1-sol", "prompt": "hi"})
            self.assertTrue(result["isError"])
            self.assertNotIn("fake-test-key", json.dumps(result))

    def test_prompt_with_key_is_refused(self):
        with patch.object(server, "api_key", return_value="fake-test-key"):
            result = server.tool_result({"model": "gpt-6.1-sol", "prompt": "fake-test-key"})
            self.assertTrue(result["isError"])


if __name__ == "__main__":
    unittest.main()
