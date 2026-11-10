import json
import unittest
import sys
import types
from unittest.mock import patch

from tests.support import load

client = load("spawn_client")


class Response:
    def __init__(self, value=None, *, status=200, headers=None, text=None):
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}
        self.text = json.dumps(value) if text is None else text


class ScriptedRequest:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if not self.responses:
            raise AssertionError("Unexpected request or retry")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def rpc(result, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def tool(data):
    return {"structuredContent": {"ok": True, "data": data}}


class TransportTests(unittest.TestCase):
    def assert_error(self, expected, response, *, uncertain=None):
        transport = ScriptedRequest(response)
        with self.assertRaises(client.SpawnError) as caught:
            client.SpawnClient(transport).call_tool("spawn_get_job", {"job_id": "job_1"})
        self.assertEqual(expected, caught.exception.code)
        if uncertain is not None:
            self.assertEqual(uncertain, caught.exception.uncertain)
        self.assertEqual(1, len(transport.calls))
        return caught.exception

    def test_json_and_request_contract(self):
        request = ScriptedRequest(Response(rpc(tool({"job_id": "j1"}))))
        self.assertEqual({"job_id": "j1"}, client.SpawnClient(request).call_tool("spawn_get_job", {"job_id": "j1"}))
        args, kwargs = request.calls[0]
        self.assertEqual(("spawn", "POST", client.MCP_URL), args)
        self.assertEqual(30.0, kwargs["timeout"])
        self.assertEqual({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "spawn_get_job", "arguments": {"job_id": "j1"}}}, kwargs["json"])
        self.assertNotIn("Authorization", kwargs["headers"])
        self.assertIn("text/event-stream", kwargs["headers"]["Accept"])

    def test_sse_multiline_selects_matching_last_event(self):
        text = ': comment\r\nevent: message\r\ndata: {"jsonrpc":"2.0","method":"notifications/progress"}\r\n\r\n'
        text += 'data: {"jsonrpc":"2.0","id":999,"result":{}}\r\n\r\n'
        text += 'data: {"jsonrpc":"2.0","id":1,\r\ndata: "result":{"structuredContent":{"data":{"done":true}}}}\r\n\r\n'
        request = ScriptedRequest(Response(text=text, headers={"CONTENT-TYPE": "text/event-stream; charset=utf-8"}))
        self.assertEqual({"done": True}, client.SpawnClient(request).call_tool("read"))

    def test_text_content_fallback(self):
        result = {"content": [{"type": "image", "data": "ignored"}, {"type": "text", "text": '{"ok":true,"data":{"x":1}}'}]}
        request = ScriptedRequest(Response(rpc(result)))
        self.assertEqual({"x": 1}, client.SpawnClient(request).call_tool("read"))

    def test_auth_error_does_not_echo_html_or_secrets(self):
        error = self.assert_error("not_signed_in", Response(status=401, text="secret HTML token"), uncertain=False)
        self.assertEqual(client.SIGN_IN, error.as_dict()["fix"])
        self.assertNotIn("secret", json.dumps(error.as_dict()))

    def test_beta_access_no_retry_preserves_actionable_fields_only(self):
        payload = {"error": {"code": "BETA_TOKEN_REQUIRED", "balance": 12, "shortfall": 3, "recover_url": "https://spawnbackrooms.com/connect", "token": "secret", "message": "secret"}}
        error = self.assert_error("BETA_TOKEN_REQUIRED", Response(rpc({"isError": True, "structuredContent": payload})), uncertain=False)
        self.assertEqual(3, error.details["shortfall"])
        self.assertEqual(12, error.details["balance"])
        self.assertNotIn("secret", json.dumps(error.as_dict()))

    def test_real_nested_beta_details_are_preserved_and_sanitized(self):
        details = {"current_amount": "12000000", "required_amount": "15000000", "shortfall": "3000000", "recover_url": "https://spawnbackrooms.com/connect", "wallet_address": "private", "token": "secret"}
        error = self.assert_error("BETA_TOKEN_REQUIRED", Response(rpc({"isError": True, "structuredContent": {"error": {"code": "BETA_TOKEN_REQUIRED", "details": details}}})), uncertain=False)
        self.assertEqual({key: details[key] for key in ("current_amount", "required_amount", "shortfall", "recover_url")}, error.details)
        self.assertNotIn("secret", json.dumps(error.as_dict()))
        self.assertNotIn("private", json.dumps(error.as_dict()))

    def test_untrusted_beta_recovery_urls_are_removed(self):
        for url in ("http://spawnbackrooms.com/connect", "https://evil.example/connect", "https://spawnbackrooms.com.evil.example/connect", "https://user:password@spawnbackrooms.com/connect", "javascript:alert(1)"):
            with self.subTest(url=url):
                error = client.mapped_error({"error": {"code": "BETA_TOKEN_REQUIRED", "details": {"shortfall": "1", "recover_url": url}}})
                self.assertEqual("1", error.details["shortfall"])
                self.assertNotIn("recover_url", error.details)

    def test_jsonrpc_internal_error_is_uncertain(self):
        self.assert_error("-32603", Response({"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "Internal failure"}}), uncertain=True)

    def test_unknown_and_internal_tool_errors_are_uncertain(self):
        for code in ("INTERNAL_ERROR", "UNRECOGNIZED_REMOTE_ERROR"):
            with self.subTest(code=code):
                self.assert_error(code, Response(rpc({"isError": True, "structuredContent": {"error": {"code": code}}})), uncertain=True)

    def test_known_precondition_rejection_is_definitive(self):
        for code in ("LEASE_EXPIRED", "JOB_REVISION_CONFLICT", "INVALID_ARGUMENTS"):
            with self.subTest(code=code):
                self.assert_error(code, Response(rpc({"isError": True, "structuredContent": {"error": {"code": code}}})), uncertain=False)

    def test_403_error(self):
        self.assert_error("forbidden", Response({"error": {"code": "forbidden"}}, status=403))

    def test_503_is_uncertain_and_not_retried(self):
        self.assert_error("EXTERNAL_AUTHORITY_UNAVAILABLE", Response({"error": {"code": "EXTERNAL_AUTHORITY_UNAVAILABLE"}}, status=503), uncertain=True)

    def test_beta_check_failure_does_not_suggest_buying(self):
        error = self.assert_error("BETA_TOKEN_CHECK_UNAVAILABLE", Response({"error": {"code": "BETA_TOKEN_CHECK_UNAVAILABLE"}}, status=503))
        self.assertIn("Try later", error.message)

    def test_invalid_json_and_sse_are_safe(self):
        for headers in ({"Content-Type": "application/json"}, {"Content-Type": "text/event-stream"}):
            with self.subTest(headers=headers):
                self.assert_error("invalid_response", Response(text="data: {broken" if "stream" in headers["Content-Type"] else "{broken", headers=headers), uncertain=True)

    def test_wrong_id_version_and_non_objects(self):
        for value in [rpc({}, 99), {"jsonrpc": "1.0", "id": 1, "result": {}}, [], None]:
            with self.subTest(value=value):
                self.assert_error("response_id_mismatch", Response(value), uncertain=True)

    def test_redirects_never_followed(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.assert_error("redirect_refused", Response(status=status, headers={"Location": "https://example.invalid/steal"}, text=""), uncertain=True)

    def test_network_failure_is_safe_and_uncertain(self):
        error = self.assert_error("transport_error", RuntimeError("secret bearer token"), uncertain=True)
        self.assertNotIn("secret", json.dumps(error.as_dict()))

    def test_response_size_limit(self):
        with patch.object(client, "MAX_RESPONSE_BYTES", 20):
            self.assert_error("response_too_large", Response(text="é" * 11), uncertain=True)

    def test_request_limit_prevents_any_network_call(self):
        request = ScriptedRequest()
        with self.assertRaises(client.SpawnError) as caught:
            client.SpawnClient(request).call_tool("write", {"text": "é" * 33000})
        self.assertEqual("request_too_large", caught.exception.code)
        self.assertEqual([], request.calls)

    def test_initialization_fallback_negotiates_session_once(self):
        request = ScriptedRequest(
            Response({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "Not initialized"}}),
            Response(rpc({"protocolVersion": "2025-03-26"}, 2), headers={"Mcp-Session-Id": "session-1"}),
            Response(status=202, text=""),
            Response(rpc(tool({"ready": True}), 4)),
            Response(rpc(tool({"ready": True}), 5)),
        )
        instance = client.SpawnClient(request)
        self.assertEqual({"ready": True}, instance.call_tool("read"))
        instance.call_tool("read")
        bodies = [kwargs["json"] for _, kwargs in request.calls]
        self.assertEqual(["tools/call", "initialize", "notifications/initialized", "tools/call", "tools/call"], [b["method"] for b in bodies])
        self.assertNotIn("id", bodies[2])
        self.assertEqual(bodies[0]["params"], bodies[3]["params"])
        self.assertEqual("2025-03-26", request.calls[3][1]["headers"]["MCP-Protocol-Version"])
        self.assertEqual("session-1", request.calls[3][1]["headers"]["Mcp-Session-Id"])

    def test_unsupported_initialization_protocol_stops(self):
        request = ScriptedRequest(Response({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "initialize first"}}), Response(rpc({"protocolVersion": "future"}, 2)))
        with self.assertRaises(client.SpawnError) as caught:
            client.SpawnClient(request).call_tool("read")
        self.assertEqual("unsupported_protocol", caught.exception.code)
        self.assertEqual(2, len(request.calls))

    def test_malformed_initialization_result_fails_cleanly(self):
        request = ScriptedRequest(Response({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "initialize first"}}), Response(rpc([], 2)))
        with self.assertRaises(client.SpawnError):
            client.SpawnClient(request).call_tool("read")
        self.assertEqual(2, len(request.calls))

    def test_missing_hermes_grant_maps_to_signin_instruction(self):
        auth = types.ModuleType("hermes_cli.auth_constants")
        provider = types.ModuleType("hermes_cli.plugin_provider_requests")
        class AuthError(Exception):
            pass
        class ProviderNotSignedIn(Exception):
            pass
        def refused(*args, **kwargs):
            raise ProviderNotSignedIn("do not expose internal details")
        auth.AuthError = AuthError
        provider.ProviderNotSignedIn = ProviderNotSignedIn
        provider.credentialed_provider_request = refused
        fake_modules = {"hermes_cli": types.ModuleType("hermes_cli"), "hermes_cli.auth_constants": auth, "hermes_cli.plugin_provider_requests": provider}
        with patch.dict(sys.modules, fake_modules):
            with self.assertRaises(client.SpawnError) as caught:
                client.credentialed_request("spawn", "POST", client.MCP_URL)
        self.assertEqual("not_signed_in", caught.exception.code)
        self.assertEqual(client.SIGN_IN, caught.exception.details["fix"])
        self.assertNotIn("internal details", str(caught.exception))

    def test_malformed_error_objects_fail_cleanly(self):
        for value in (None, [], "bad"):
            with self.subTest(value=value):
                request = ScriptedRequest(Response({"jsonrpc": "2.0", "id": 1, "error": value}))
                with self.assertRaises(client.SpawnError):
                    client.SpawnClient(request).call_tool("read")

    def test_malformed_tool_content_fails_cleanly(self):
        for result in ({"content": [None]}, {"content": ["bad"]}, {"content": None}, {"structuredContent": []}, []):
            with self.subTest(result=result):
                self.assert_error("invalid_result", Response(rpc(result)), uncertain=True)


if __name__ == "__main__":
    unittest.main()
