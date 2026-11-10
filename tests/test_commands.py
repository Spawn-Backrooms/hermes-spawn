import contextlib
import io
import json
import sys
import types
import unittest
from unittest.mock import Mock, patch

from tests.support import load

Commands = load("commands").Commands


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
        status = {"ok": True, "access": {"actions": {"start_work": {"allowed": True}}}, "errors": []}
        exit_code, result = self.doctor(status)
        self.assertEqual(0, exit_code)
        self.assertTrue(result["beta_start_work_allowed"])
        exit_code, result = self.doctor(status, "wrong-client")
        self.assertEqual(1, exit_code)
        self.assertFalse(result["public_client_configured"])
        self.assertFalse(result["ok"])

    def test_doctor_section_errors_are_not_success(self):
        exit_code, _ = self.doctor({"ok": True, "access": {"actions": {"start_work": {"allowed": True}}}, "errors": [{"section": "jobs", "error": "unavailable"}]})
        self.assertEqual(1, exit_code)


if __name__ == "__main__":
    unittest.main()
