import contextlib
import io
import json
import sys
import types
import unittest
from unittest.mock import Mock, patch

from tests.support import load

Commands = load("commands").Commands


def ready_identity():
    return {"installation_id": "install_7", "grant_epoch": 4, "workflow_readiness": {
        "schema_version": "spawn.external-work-readiness.v1", "observed_at_ms": 1900000000000,
        "installation_id": "install_7", "grant_epoch": 4,
        "features": {name: {"state": "ready", "reasons": [], "required_scopes": [], "missing_scopes": []}
                     for name in ("assigned_work", "proposals", "children", "delivery")},
        "limits": {"max_artifacts": 10, "max_file_bytes": 5242880,
                   "max_game_package_bytes": 2097152, "max_child_brief_bytes": 16384}}}


class CommandTests(unittest.TestCase):
    def doctor(self, status, client_id="hermes"):
        tools = Mock()
        tools.handler.return_value.return_value = json.dumps(status)
        commands = Commands(Mock(), tools)
        scope = types.ModuleType("agent.secret_scope")
        scope.get_secret = lambda name: client_id
        output = io.StringIO()
        with patch.dict(sys.modules, {"agent": types.ModuleType("agent"), "agent.secret_scope": scope}), contextlib.redirect_stdout(output):
            exit_code = commands.cli(types.SimpleNamespace(action="doctor"))
        tools.handler.assert_called_once_with("spawn_status")
        return exit_code, json.loads(output.getvalue())

    def test_doctor_requires_true_server_start_work_permission(self):
        for access in ({}, {"start_work": True}, {"actions": {}}, {"actions": {"start_work": {"allowed": False}}}, {"actions": {"start_work": {"allowed": 1}}}):
            with self.subTest(access=access):
                exit_code, result = self.doctor({"ok": True, "access": access, "errors": []})
                self.assertEqual(1, exit_code)
                self.assertFalse(result["beta_start_work_allowed"])
                self.assertFalse(result["ok"])

    def test_doctor_success_requires_matching_public_client(self):
        status = {"ok": True, "identity": ready_identity(), "access": {"actions": {"start_work": {"allowed": True}}}, "errors": []}
        exit_code, result = self.doctor(status)
        self.assertEqual(0, exit_code)
        self.assertTrue(result["beta_start_work_allowed"])
        exit_code, result = self.doctor(status, "wrong-client")
        self.assertEqual(1, exit_code)
        self.assertFalse(result["public_client_configured"])
        self.assertFalse(result["ok"])

    def test_doctor_old_server_does_not_claim_full_readiness(self):
        status = {"ok": True, "identity": {"installation_id": "install_7", "grant_epoch": 4},
                  "access": {"actions": {"start_work": {"allowed": True}}}, "errors": []}
        exit_code, result = self.doctor(status)
        self.assertEqual(1, exit_code)
        self.assertEqual("readiness_unavailable", result["readiness"]["error"])
        self.assertFalse(result["full_workflow_ready"])
        self.assertTrue(result["beta_start_work_allowed"])

    def test_doctor_distinguishes_assigned_work_from_collaboration(self):
        for state in ("disabled", "scope_required", "unavailable"):
            with self.subTest(state=state):
                identity = ready_identity()
                identity["workflow_readiness"]["features"]["children"] = {
                    "state": state, "reasons": ["eligible_services_unavailable" if state == "unavailable" else state],
                    "required_scopes": ["commissions:request"],
                    "missing_scopes": ["commissions:request"] if state == "scope_required" else []}
                exit_code, result = self.doctor({"ok": True, "identity": identity,
                    "access": {"actions": {"start_work": {"allowed": True}}}, "errors": []})
                self.assertEqual(1, exit_code)
                self.assertTrue(result["assigned_work_ready"])
                self.assertFalse(result["full_workflow_ready"])
                self.assertEqual(state, result["readiness"]["features"]["children"]["state"])

    def test_doctor_rejects_malformed_or_foreign_readiness(self):
        for field, bad in (("schema_version", "future"), ("installation_id", "other"),
                           ("grant_epoch", 99), ("observed_at_ms", True), ("features", {}), ("limits", {})):
            with self.subTest(field=field):
                identity = ready_identity()
                identity["workflow_readiness"][field] = bad
                exit_code, result = self.doctor({"ok": True, "identity": identity,
                    "access": {"actions": {"start_work": {"allowed": True}}}, "errors": []})
                self.assertEqual(1, exit_code)
                self.assertEqual("readiness_invalid", result["readiness"]["error"])
                self.assertFalse(result["assigned_work_ready"])

    def test_status_projects_readiness_using_only_existing_reads(self):
        from tests.fake_jobs import FakeSpawn
        server = FakeSpawn()
        identity = ready_identity()
        calls = []
        def call(name, arguments=None):
            calls.append(name)
            if name == "spawn_identity":
                return identity
            if name == "spawn_access_status":
                return {"actions": {"start_work": {"allowed": True}}}
            if name == "spawn_list_rooms":
                return {"rooms": []}
            if name == "spawn_list_jobs":
                return {"jobs": []}
            raise AssertionError("Unexpected readiness call: " + name)
        server.call_tool = call
        status = load("jobs").Jobs(client=server).status()
        self.assertTrue(status["readiness"]["full_workflow_ready"])
        self.assertEqual(identity["workflow_readiness"]["limits"], status["readiness"]["limits"])
        self.assertEqual(["spawn_identity", "spawn_access_status", "spawn_list_rooms", "spawn_list_jobs"], calls)

    def test_doctor_section_errors_are_not_success(self):
        exit_code, _ = self.doctor({"ok": True, "access": {"actions": {"start_work": {"allowed": True}}}, "errors": [{"section": "jobs", "error": "unavailable"}]})
        self.assertEqual(1, exit_code)


if __name__ == "__main__":
    unittest.main()
