import importlib.util
import json
import sys
import unittest
from unittest.mock import Mock, patch

from tests.support import ROOT

# A separate proper package executes the real entrypoint without replacing the
# shared transport-test namespace or importing Hermes itself.
NAME = "_hermes_spawn_registration_test"
spec = importlib.util.spec_from_file_location(NAME, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
entry = importlib.util.module_from_spec(spec)
sys.modules[NAME] = entry
spec.loader.exec_module(entry)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.ctx = Mock()
        self.ctx.get_config.side_effect = lambda key, default=None: default
        self.ctx.current_cron_execution.return_value = None
        self.ctx.state.get.side_effect = lambda key, default=None: default

    def test_registration_is_offline_exact_and_cleanup_registered(self):
        with patch.object(entry.Jobs, "snapshot", side_effect=AssertionError("Registration must not call network")), patch.object(entry.LeaseKeeper, "start", side_effect=AssertionError("No background jobs on load")):
            entry.register(self.ctx)
        calls = self.ctx.register_tool.call_args_list
        self.assertEqual(12, len(calls))
        self.assertEqual(set(entry.SCHEMAS), {call.kwargs["name"] for call in calls})
        for call in calls:
            self.assertEqual("spawn-backrooms", call.kwargs["toolset"])
            self.assertIs(call.kwargs["schema"], entry.SCHEMAS[call.kwargs["name"]])
            self.assertTrue(callable(call.kwargs["handler"]))
        self.assertEqual({"pre_tool_call", "pre_llm_call"}, {call.args[0] for call in self.ctx.register_hook.call_args_list})
        self.ctx.register_command.assert_called_once()
        self.ctx.register_cli_command.assert_called_once()
        self.assertEqual("spawn", self.ctx.register_command.call_args.args[0])
        self.assertEqual("spawn", self.ctx.register_cli_command.call_args.args[0])
        skill_name, skill_path = self.ctx.register_skill.call_args.args
        self.assertEqual("work-a-job", skill_name)
        self.assertTrue(skill_path.is_file())
        self.ctx.on_unload.assert_called_once()
        self.ctx.on_unload.call_args.args[0]()

    def test_registered_write_handler_without_gate_fails_closed(self):
        entry.register(self.ctx)
        handler = next(call.kwargs["handler"] for call in self.ctx.register_tool.call_args_list if call.kwargs["name"] == "spawn_accept")
        result = json.loads(handler({"job_id": "job"}, conversation_id="chat", session_id="session"))
        self.assertEqual("approval_preflight_required", result["error"])

    def test_slash_connect_is_read_only_guidance(self):
        entry.register(self.ctx)
        slash = self.ctx.register_command.call_args.args[1]
        self.assertIn("hermes auth add spawn-backrooms:spawn", slash("connect", session_id="session"))
        self.assertIn("Use /spawn", slash("accept job", session_id="session"))


if __name__ == "__main__":
    unittest.main()
