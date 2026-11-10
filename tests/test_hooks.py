import json
import unittest
from unittest.mock import Mock, patch

from tests.support import load
from tests.fake_jobs import FakeSpawn, SpawnError

Jobs = load("jobs").Jobs
hooks_module = load("hooks")
Hooks = hooks_module.Hooks
Tools = load("tools").Tools
schemas = load("schemas")


class HookTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeSpawn()
        self.jobs = Jobs(client=self.server, config=lambda key, default=None: False if key == "lease_keeper" else default)
        self.hooks = Hooks(self.jobs)
        self.tools = Tools(self.jobs, self.hooks)
        self.jobs.snapshot("job-123")
        self.args = {"job_id": "job-123"}

    def test_exact_gated_tools_and_read_tools_ungated(self):
        self.assertEqual({"spawn_accept", "spawn_submit", "spawn_abandon", "spawn_create_backroom", "spawn_declare_services"}, set(hooks_module.GATED))
        for name in set(schemas.SCHEMAS) - hooks_module.GATED:
            with self.subTest(name=name):
                self.assertIsNone(self.hooks.pre_tool_call(name, {}, conversation_id="chat"))

    def test_approval_gate_contains_exact_terms_and_no_network(self):
        before = len(self.server.calls)
        result = self.hooks.pre_tool_call("spawn_accept", self.args, conversation_id="chat")
        self.assertEqual("approve", result["action"])
        self.assertIn("job-123", result["message"])
        self.assertIn("Review", result["message"])
        self.assertEqual(before, len(self.server.calls))
        self.assertEqual([], self.server.mutations())

    def test_no_preflight_handler_refuses_mutation(self):
        result = json.loads(self.tools.handler("spawn_accept")(self.args, conversation_id="chat"))
        self.assertFalse(result["ok"])
        self.assertEqual("approval_preflight_required", result["error"])
        self.assertEqual([], self.server.mutations())

    def test_preflight_is_exact_and_single_use(self):
        self.hooks.pre_tool_call("spawn_accept", self.args, conversation_id="chat")
        for name, args, conversation in (("spawn_accept", {"job_id": "other"}, "chat"), ("spawn_accept", self.args, "another"), ("spawn_abandon", {**self.args, "reason": "stop"}, "chat")):
            with self.subTest(name=name, args=args, conversation=conversation), self.assertRaises(SpawnError):
                self.hooks.consume_preflight(name, args, conversation)
        pinned = self.hooks.consume_preflight("spawn_accept", self.args, "chat")
        self.assertEqual("a" * 64, pinned["order_hash"])
        with self.assertRaises(SpawnError):
            self.hooks.consume_preflight("spawn_accept", self.args, "chat")

    def test_handler_consumes_preflight_then_mutates_once(self):
        self.hooks.pre_tool_call("spawn_accept", self.args, conversation_id="chat")
        run = self.tools.handler("spawn_accept")
        result = json.loads(run(self.args, conversation_id="chat"))
        self.assertTrue(result["ok"])
        second = json.loads(run(self.args, conversation_id="chat"))
        self.assertEqual("approval_preflight_required", second["error"])
        self.assertEqual(1, len([name for name, _ in self.server.calls if name == "spawn_accept_job"]))

    def test_changed_terms_after_prompt_block_handler(self):
        self.hooks.pre_tool_call("spawn_accept", self.args, conversation_id="chat")
        self.server.job["grant_epoch"] += 1
        result = json.loads(self.tools.handler("spawn_accept")(self.args, conversation_id="chat"))
        self.assertEqual("terms_changed", result["error"])
        self.assertEqual([], self.server.mutations())

    def test_expired_preflight_blocked(self):
        with patch.object(hooks_module.time, "monotonic", return_value=100):
            self.hooks.pre_tool_call("spawn_accept", self.args, conversation_id="chat")
        with patch.object(hooks_module.time, "monotonic", return_value=700):
            with self.assertRaises(SpawnError):
                self.hooks.consume_preflight("spawn_accept", self.args, "chat")

    def test_cron_and_missing_conversation_fail_closed(self):
        ctx = Mock()
        ctx.current_cron_execution.return_value = {"id": "cron"}
        hooks = Hooks(self.jobs, ctx)
        self.assertEqual("block", hooks.pre_tool_call("spawn_accept", self.args, conversation_id="chat")["action"])
        self.assertEqual("block", self.hooks.pre_tool_call("spawn_accept", self.args)["action"])
        self.assertEqual({}, self.jobs.state.preflights)

    def test_no_snapshot_and_invalid_args_fail_closed(self):
        self.jobs.state.set("snapshot", "job-123", None)
        self.assertEqual("block", self.hooks.pre_tool_call("spawn_accept", self.args, conversation_id="chat")["action"])
        self.assertEqual("block", self.hooks.pre_tool_call("spawn_accept", {**self.args, "envelope": {}}, conversation_id="chat")["action"])
        self.assertEqual({}, self.jobs.state.preflights)

    def test_active_context_short_and_scoped(self):
        self.assertIsNone(self.hooks.pre_llm_call(conversation_id="chat"))
        self.jobs.remember_active("chat", self.server.job)
        self.assertIsNone(self.hooks.pre_llm_call(conversation_id="other"))
        context = self.hooks.pre_llm_call(conversation_id="chat")["context"]
        self.assertLessEqual(len(context), 400)
        self.assertIn("job-123", context)
        self.assertIn("Customer content", context)

    def test_context_disabled(self):
        self.jobs.remember_active("chat", self.server.job)
        self.jobs.config = lambda key, default=None: False
        self.assertIsNone(self.hooks.pre_llm_call(conversation_id="chat"))

    def test_tool_invalid_args_and_unexpected_errors_always_json(self):
        result = json.loads(self.tools.handler("spawn_accept")({"job_id": "../bad"}, conversation_id="chat"))
        self.assertEqual("invalid_arguments", result["error"])
        with patch.object(self.jobs, "status", side_effect=RuntimeError("secret token")):
            result = self.tools.handler("spawn_status")({})
        self.assertEqual("plugin_error", json.loads(result)["error"])
        self.assertNotIn("secret", result)


if __name__ == "__main__":
    unittest.main()
