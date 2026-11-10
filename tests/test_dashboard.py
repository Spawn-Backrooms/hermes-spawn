"""Offline dashboard checks; no Hermes credentials or SPAWN network calls."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types

import unittest
from unittest.mock import patch


def make_api():
    config = types.ModuleType("hermes_cli.config")
    config.load_config = lambda: {"plugins": {"entries": {"spawn-backrooms": {"settings": {"poll_seconds": 37}}}}}
    package = types.ModuleType("hermes_cli")
    package.__path__ = []
    constants = types.ModuleType("hermes_constants")
    constants.get_hermes_home = lambda: Path("/profile-one")
    path = Path(__file__).resolve().parents[1] / "dashboard" / "plugin_api.py"
    spec = importlib.util.spec_from_file_location("test_spawn_dashboard_api", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"hermes_cli": package, "hermes_cli.config": config, "hermes_constants": constants}):
        spec.loader.exec_module(module)
    return module


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.api = make_api()

    def test_routes_are_read_only(self):
        api = self.api
        assert {route.path for route in api.router.routes} == {"/status", "/jobs", "/jobs/{job_id}", "/earnings"}
        assert all(route.methods == {"GET"} for route in api.router.routes)
        with self.assertRaises(ValueError):
            api._read("spawn_accept_job", {"job_id": "test"})


    def test_status_and_cache_are_profile_scoped(self):
        api = self.api
        calls = []
        def call(name, arguments=None):
            calls.append(name)
            return {"jobs": []} if name == "spawn_list_jobs" else {}
        self.enterContext(patch.object(api, "_read", call))
        assert asyncio.run(api.status())["poll_seconds"] == 37
        assert asyncio.run(api.status())["ok"]
        assert len(calls) == 5
        self.enterContext(patch.object(api, "get_hermes_home", lambda: Path("/profile-two")))
        asyncio.run(api.status())
        assert len(calls) == 10


    def test_failed_identity_stops_and_is_not_cached(self):
        api = self.api
        calls = []
        def call(name, arguments=None):
            calls.append(name)
            raise api.SpawnError("not_signed_in", "Sign in first.")
        self.enterContext(patch.object(api, "_read", call))
        assert asyncio.run(api.status())["error"] == "not_signed_in"
        asyncio.run(api.status())
        assert calls == ["spawn_identity", "spawn_identity"]


    def test_identifier_validation_and_earnings_notice(self):
        api = self.api
        calls = []
        self.enterContext(patch.object(api, "_read", lambda *args: calls.append(args) or {}))
        assert asyncio.run(api.job("../other"))["error"] == "invalid_job_id"
        assert asyncio.run(api.jobs("bad/cursor"))["error"] == "invalid_cursor"
        assert calls == []
        assert asyncio.run(api.earnings())["withdrawals_available"] is False


    def test_unexpected_error_is_sanitized(self):
        api = self.api
        def call(*args):
            raise RuntimeError("secret=do-not-return")
        self.enterContext(patch.object(api, "_read", call))
        result = asyncio.run(api.job("known-id"))
        assert "do-not-return" not in str(result)
        assert result["ok"] is False
