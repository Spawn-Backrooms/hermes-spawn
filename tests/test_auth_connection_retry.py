import sys
import types
import unittest
from unittest.mock import Mock, patch

from tests.support import load

client = load("spawn_client")


class AuthError(RuntimeError):
    def __init__(self, message, code="oauth_refresh_failed"):
        super().__init__(message)
        self.code = code


class ProviderNotSignedIn(RuntimeError):
    pass


class AuthConnectionRetryTests(unittest.TestCase):
    def invoke(self, side_effect):
        provider = types.ModuleType("hermes_cli.plugin_provider_requests")
        provider.ProviderNotSignedIn = ProviderNotSignedIn
        provider.credentialed_provider_request = Mock(side_effect=side_effect)
        auth = types.ModuleType("hermes_cli.auth_constants")
        auth.AuthError = AuthError
        modules = {
            "hermes_cli": types.ModuleType("hermes_cli"),
            "hermes_cli.auth_constants": auth,
            "hermes_cli.plugin_provider_requests": provider,
        }
        self.provider = provider.credentialed_provider_request
        with patch.dict(sys.modules, modules), patch("time.sleep"):
            return client.credentialed_request("spawn", "POST", client.MCP_URL,
                                             json={"method": "tools/call"})

    def timeout(self):
        return AuthError("spawn-backrooms:spawn: the token request failed (ConnectTimeout).")

    def test_pre_exchange_connect_timeout_retries_then_returns_response(self):
        expected = object()
        self.assertIs(expected, self.invoke([self.timeout(), expected]))
        self.assertEqual(2, self.provider.call_count)
        self.assertEqual(self.provider.call_args_list[0], self.provider.call_args_list[1])

    def test_connect_timeout_retries_are_bounded_and_do_not_request_sign_in(self):
        with self.assertRaises(client.SpawnError) as caught:
            self.invoke([self.timeout(), self.timeout(), self.timeout()])
        self.assertEqual(3, self.provider.call_count)
        self.assertEqual("oauth_connection_timeout", caught.exception.code)
        self.assertTrue(caught.exception.details["retryable"])
        self.assertNotIn("auth add", str(caught.exception.as_dict()))

    def test_unknown_outcomes_and_rejected_grants_are_never_retried(self):
        failures = [
            AuthError("spawn-backrooms:spawn: the token request failed (ReadTimeout)."),
            AuthError("spawn-backrooms:spawn: the token request failed (WriteTimeout)."),
            AuthError("spawn-backrooms:spawn: the token endpoint failed with HTTP 503."),
            AuthError("unrecognized transport failure"),
            AuthError("the token request failed (ConnectTimeout).", "invalid_grant"),
            ProviderNotSignedIn("revoked"),
            PermissionError("not allowed"),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__, message=str(failure)):
                with self.assertRaises(client.SpawnError):
                    self.invoke([failure, object()])
                self.assertEqual(1, self.provider.call_count)

    def test_post_auth_transport_error_is_never_retried(self):
        with self.assertRaisesRegex(RuntimeError, "request outcome unknown"):
            self.invoke([RuntimeError("request outcome unknown"), object()])
        self.assertEqual(1, self.provider.call_count)


if __name__ == "__main__":
    unittest.main()
