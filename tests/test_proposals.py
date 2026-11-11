import copy
import json
import unittest
from unittest.mock import Mock

from tests.support import load
from tests.fake_proposals import ProposalServer, proposal_args, MemoryBackend, SpawnError, NOW, DAY

Jobs = load("jobs").Jobs
Hooks = load("hooks").Hooks
Tools = load("tools").Tools
State = load("state").State


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.server = ProposalServer()
        self.jobs = Jobs(client=self.server)
        self.hooks = Hooks(self.jobs)
        self.tools = Tools(self.jobs, self.hooks)

    def run_tool(self, name, args, conversation="chat"):
        return json.loads(self.tools.handler(name)(args, conversation_id=conversation))

    def test_open_discovery_reads_public_request_without_mutation(self):
        result = self.run_tool("spawn_open_jobs", {})
        self.assertTrue(result["ok"], result)
        self.assertEqual("request-7", result["requests"][0]["request_id"])
        detail = self.run_tool("spawn_open_job", {"request_id": "request-7"})
        self.assertTrue(detail["ok"], detail)
        self.assertEqual(3, detail["request"]["revision"])
        self.assertEqual("c" * 64, detail["request"]["request_hash"])
        self.assertIn("untrusted", detail["notice"].lower())
        self.assertEqual([], self.server.proposal_writes())

    def test_own_proposal_status_remains_readable_after_expiry(self):
        self.server.request["expires_at_ms"] = 1
        result = self.run_tool("spawn_job_proposal", {"request_id": "request-7", "proposal_id": "proposal-2"})
        self.assertTrue(result["ok"], result)
        self.assertEqual("declined", result["status"])
        self.assertEqual([], self.server.proposal_writes())

    def test_old_server_returns_unavailable_without_disabling_assigned_job(self):
        self.server.unavailable.add("spawn_open_jobs")
        result = self.run_tool("spawn_open_jobs", {})
        self.assertEqual("feature_unavailable", result.get("error"), result)
        self.assertIn("assigned", result["message"].lower())
        job = self.run_tool("spawn_job", {"job_id": "job-123"})
        self.assertTrue(job["ok"], job)

    def test_unsupported_new_tool_contract_has_clear_preview_guidance(self):
        original = self.server.call_tool
        def unsupported(name, arguments=None):
            if name == "spawn_open_jobs":
                raise SpawnError(-32602, "Unknown tool")
            return original(name, arguments)
        self.server.call_tool = unsupported
        result = self.run_tool("spawn_open_jobs", {})
        self.assertEqual("feature_unavailable", result.get("error"), result)
        self.assertIn("assigned", result["message"])

    def test_disabled_server_feature_has_clear_preview_guidance(self):
        original = self.server.call_tool
        def disabled(name, arguments=None):
            if name == "spawn_open_jobs":
                raise SpawnError("EXTERNAL_OPEN_JOBS_DISABLED", "Feature disabled")
            return original(name, arguments)
        self.server.call_tool = disabled
        result = self.run_tool("spawn_open_jobs", {})
        self.assertEqual("feature_unavailable", result.get("error"), result)
        self.assertIn("assigned", result["message"])

    def read_request(self):
        result = self.run_tool("spawn_open_job", {"request_id": "request-7"})
        self.assertTrue(result["ok"], result)

    def test_proposal_requires_cached_terms_and_interactive_approval(self):
        args = proposal_args()
        blocked = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertEqual("block", blocked and blocked.get("action"))
        self.read_request()
        result = self.run_tool("spawn_propose_job", args)
        self.assertEqual("approval_preflight_required", result.get("error"), result)
        ctx = Mock()
        ctx.current_cron_execution.return_value = {"id": "cron"}
        blocked = Hooks(self.jobs, ctx).pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertEqual("block", blocked and blocked.get("action"))
        self.assertEqual([], self.server.proposal_writes())

    def test_approval_shows_exact_price_fee_scope_and_child_caps_without_network(self):
        self.read_request()
        before = len(self.server.calls)
        result = self.hooks.pre_tool_call("spawn_propose_job", proposal_args(), conversation_id="chat")
        self.assertEqual("approve", result and result.get("action"))
        for text in ("20.000000 USDC", "1.000000 USDC", "19.000000 USDC", "10.000000 USDC",
                     "2.000000 USDC", "4.000000 USDC", "three connected rooms", "Source and test report",
                     "Reach the locked exit", "Art allowance", "buyer-1", "pixel_grid_v1"):
            self.assertIn(text, result["message"])
        self.assertEqual(before, len(self.server.calls))
        self.assertEqual([], self.server.proposal_writes())

    def test_server_pins_and_reviewer_are_derived_after_approval(self):
        self.read_request()
        args = proposal_args()
        result = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertEqual("approve", result and result.get("action"))
        receipt = self.run_tool("spawn_propose_job", args)
        self.assertTrue(receipt["ok"], receipt)
        self.assertEqual("proposal-2", receipt["proposal_id"])
        sent = self.server.proposal_writes()
        self.assertEqual(1, len(sent))
        self.assertEqual(3, sent[0]["request_revision"])
        self.assertEqual("c" * 64, sent[0]["request_hash"])
        self.assertTrue(sent[0]["idempotency_key"].startswith("hermes:"))
        self.assertEqual({"owner_id": "buyer-1", "project_id": "project-1"}, sent[0]["proposal"]["estimate"]["children"][0]["reviewer"])
        self.assertNotIn("reviewer", args["proposal"]["estimate"]["children"][0])
        consumed = self.run_tool("spawn_propose_job", args)
        self.assertEqual("approval_preflight_required", consumed.get("error"))

    def test_optional_correction_allowance_is_disclosed_and_preserved_exactly(self):
        for allowance in (None, 0, 1, 2, 3):
            with self.subTest(allowance=allowance):
                self.setUp()
                self.read_request()
                args = proposal_args()
                child = args["proposal"]["estimate"]["children"][0]
                if allowance is not None:
                    child["max_correction_attempts"] = allowance
                gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
                self.assertEqual("approve", gate and gate.get("action"))
                self.assertIn(f"paid correction attempts {allowance or 0}", gate["message"])
                self.assertIn("within this cap", gate["message"])
                result = self.run_tool("spawn_propose_job", args)
                self.assertTrue(result["ok"], result)
                sent = self.server.proposal_writes()[0]["proposal"]["estimate"]["children"][0]
                self.assertEqual({**child, "reviewer": self.server.request["buyer"]}, sent)
                if allowance is None:
                    self.assertNotIn("max_correction_attempts", sent)
                else:
                    self.assertEqual(allowance, result["proposal"]["estimate"]["children"][0]["max_correction_attempts"])

    def test_invalid_correction_allowances_are_blocked_before_any_write(self):
        self.read_request()
        for allowance in (-1, 4, True, False, 1.5, "1", None, 9007199254740992):
            with self.subTest(allowance=allowance):
                args = proposal_args()
                args["proposal"]["estimate"]["children"][0]["max_correction_attempts"] = allowance
                gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
                self.assertEqual("block", gate and gate.get("action"))
                result = self.run_tool("spawn_propose_job", args)
                self.assertEqual("invalid_arguments", result.get("error"), result)
        self.assertEqual([], self.server.proposal_writes())

    def test_correction_allowance_needs_exact_approval_and_retains_exact_retry(self):
        backend = MemoryBackend()
        self.jobs = Jobs(client=self.server, state=State(backend=backend))
        self.hooks = Hooks(self.jobs)
        self.tools = Tools(self.jobs, self.hooks)
        self.read_request()
        args = proposal_args()
        args["proposal"]["estimate"]["children"][0]["max_correction_attempts"] = 1
        gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        changed = copy.deepcopy(args)
        changed["proposal"]["estimate"]["children"][0]["max_correction_attempts"] = 2
        self.assertEqual("approval_preflight_required", self.run_tool("spawn_propose_job", changed).get("error"))
        self.assertEqual([], self.server.proposal_writes())
        self.server.fail_once["spawn_propose_job"] = SpawnError("transport_error", uncertain=True)
        self.assertTrue(self.run_tool("spawn_propose_job", args).get("outcome_uncertain"))
        self.jobs = Jobs(client=self.server, state=State(backend=backend))
        self.hooks = Hooks(self.jobs)
        self.tools = Tools(self.jobs, self.hooks)
        gate = self.hooks.pre_tool_call("spawn_propose_job", changed, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        self.assertIn("paid correction attempts 1", gate["message"])
        self.assertTrue(self.run_tool("spawn_propose_job", args)["ok"])
        writes = self.server.proposal_writes()
        self.assertEqual(writes[0], writes[1])
        self.assertEqual(1, len(self.server.proposals))

    def test_changed_request_or_grant_after_prompt_never_sends_proposal(self):
        for change in ("request_hash", "revision", "installation_id", "grant_epoch"):
            with self.subTest(change=change):
                self.setUp()
                self.read_request()
                args = proposal_args()
                gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
                self.assertEqual("approve", gate and gate.get("action"))
                if change == "request_hash":
                    self.server.request[change] = "f" * 64
                elif change == "revision":
                    self.server.request[change] += 1
                elif change == "installation_id":
                    self.server.job[change] = "different-installation"
                else:
                    self.server.job[change] += 1
                result = self.run_tool("spawn_propose_job", args)
                self.assertEqual("terms_changed", result.get("error"), result)
                self.assertEqual([], self.server.proposal_writes())

    def test_over_cap_expired_or_unbounded_proposal_is_blocked_before_approval(self):
        self.read_request()
        cases = []
        over_cap = proposal_args()
        over_cap["proposal"]["estimate"]["contingency_micro_usdc"] = "2000001"
        cases.append(over_cap)
        stale = proposal_args()
        stale["proposal"]["estimate"]["children"][0]["source"]["expires_at_ms"] = 1
        cases.append(stale)
        forged = proposal_args()
        forged["request_hash"] = "f" * 64
        cases.append(forged)
        reviewer = proposal_args()
        reviewer["proposal"]["estimate"]["children"][0]["reviewer"] = {"owner_id": "attacker", "project_id": "project-1"}
        cases.append(reviewer)
        for amount in ("01", "1.5", "-1", "9" * 20):
            invalid = proposal_args()
            invalid["proposal"]["gross_micro_usdc"] = amount
            cases.append(invalid)
        for args in cases:
            with self.subTest(args=args):
                gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
                self.assertEqual("block", gate and gate.get("action"))
        self.assertEqual([], self.server.proposal_writes())

    def test_lost_proposal_response_replays_exact_request_after_restart(self):
        backend = MemoryBackend()
        self.jobs = Jobs(client=self.server, state=State(backend=backend))
        self.hooks, self.tools = Hooks(self.jobs), None
        self.tools = Tools(self.jobs, self.hooks)
        self.read_request()
        args = proposal_args()
        self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.server.fail_once["spawn_propose_job"] = SpawnError("transport_error", uncertain=True)
        first = self.run_tool("spawn_propose_job", args)
        self.assertTrue(first.get("outcome_uncertain"), first)
        self.assertIsNotNone(self.jobs.state.get("pending_proposal", "request-7"))
        self.jobs = Jobs(client=self.server, state=State(backend=backend))
        self.hooks = Hooks(self.jobs)
        self.tools = Tools(self.jobs, self.hooks)
        self.server.request["expires_at_ms"] = 1
        self.server.request["status"] = "selected"
        self.read_request()
        gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        result = self.run_tool("spawn_propose_job", args)
        self.assertTrue(result["ok"], result)
        writes = self.server.proposal_writes()
        self.assertEqual(2, len(writes))
        self.assertEqual(writes[0], writes[1])
        self.assertEqual(1, len(self.server.proposals))
        self.assertIsNone(self.jobs.state.get("pending_proposal", "request-7"))

    def test_uncertain_proposal_blocks_different_terms_and_conversation(self):
        self.read_request()
        args = proposal_args()
        self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.server.fail_once["spawn_propose_job"] = SpawnError("transport_error", uncertain=True)
        self.run_tool("spawn_propose_job", args)
        changed = copy.deepcopy(args)
        changed["proposal"]["scope"] = "Different work"
        for candidate, conversation in ((changed, "chat"), (args, "other-chat")):
            gate = self.hooks.pre_tool_call("spawn_propose_job", candidate, conversation_id=conversation)
            self.assertEqual("block", gate and gate.get("action"))
        self.assertEqual(1, len(self.server.proposal_writes()))

    def test_lost_proposal_recovers_original_receipt_after_request_revision_changes(self):
        self.read_request()
        args = proposal_args()
        self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.server.fail_once["spawn_propose_job"] = SpawnError("transport_error", uncertain=True)
        self.assertTrue(self.run_tool("spawn_propose_job", args).get("outcome_uncertain"))
        original = copy.deepcopy(self.server.proposal_writes()[0])
        self.server.request.update(revision=4, request_hash="9" * 64, status="open")
        self.read_request()
        gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        self.assertIn("revision 3", gate["message"])
        result = self.run_tool("spawn_propose_job", args)
        self.assertTrue(result["ok"], result)
        self.assertEqual(3, result["request_revision"])
        self.assertEqual(original, self.server.proposal_writes()[-1])
        self.assertEqual(1, len(self.server.proposals))

    def test_recovery_never_rebinds_proposal_to_new_grant(self):
        self.read_request()
        args = proposal_args()
        self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.server.fail_once["spawn_propose_job"] = SpawnError("transport_error", uncertain=True)
        self.run_tool("spawn_propose_job", args)
        self.server.job["grant_epoch"] += 1
        self.read_request()
        gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        self.assertEqual(1, len(self.server.proposal_writes()))

    def test_uncommitted_old_revision_recovery_cannot_create_a_new_proposal(self):
        self.read_request()
        args = proposal_args()
        original = self.server.call_tool
        def drop_before_commit(name, arguments=None):
            if name == "spawn_propose_job":
                self.server.call_tool = original
                raise SpawnError("transport_error", uncertain=True)
            return original(name, arguments)
        self.server.call_tool = drop_before_commit
        self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertTrue(self.run_tool("spawn_propose_job", args).get("outcome_uncertain"))
        self.server.request.update(revision=4, request_hash="9" * 64)
        self.read_request()
        self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        result = self.run_tool("spawn_propose_job", args)
        self.assertEqual("OPEN_JOB_CHANGED", result.get("error"), result)
        self.assertEqual({}, self.server.proposals)
        self.assertEqual(3, self.server.proposal_writes()[0]["request_revision"])

    def test_scope_failure_has_explicit_native_reauthorization_guidance(self):
        original = self.server.call_tool
        def deny_new_scope(name, arguments=None):
            if name == "spawn_open_jobs":
                raise SpawnError("OPEN_JOB_SCOPE_REQUIRED")
            return original(name, arguments)
        self.server.call_tool = deny_new_scope
        result = self.run_tool("spawn_open_jobs", {})
        self.assertEqual("scope_upgrade_required", result.get("error"), result)
        self.assertIn("hermes auth add spawn-backrooms:spawn", result["fix"])
        self.assertIn("same installation", result["message"])

    def test_unverified_proposal_response_preserves_exact_pending_request(self):
        self.read_request()
        args = proposal_args()
        self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        original = self.server.call_tool
        def malformed_after_commit(name, arguments=None):
            result = original(name, arguments)
            return {"proposal_id": "proposal-2"} if name == "spawn_propose_job" else result
        self.server.call_tool = malformed_after_commit
        result = self.run_tool("spawn_propose_job", args)
        self.assertTrue(result.get("outcome_uncertain"), result)
        self.assertIsNotNone(self.jobs.state.get("pending_proposal", "request-7"))

    def test_terms_are_normalized_before_approval_to_match_canonical_server_schema(self):
        self.read_request()
        args = proposal_args()
        args["proposal"]["scope"] = "  Exact scope  "
        args["proposal"]["estimate"]["sources"][0]["reference"] = "  Referenced estimate  "
        gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        result = self.run_tool("spawn_propose_job", args)
        self.assertTrue(result["ok"], result)
        sent = self.server.proposal_writes()[0]["proposal"]
        self.assertEqual("Exact scope", sent["scope"])
        self.assertEqual("Referenced estimate", sent["estimate"]["sources"][0]["reference"])

    def test_server_admission_time_sources_and_quote_pins_are_checked_before_approval(self):
        self.read_request()
        cases = []
        horizon = proposal_args()
        horizon["proposal"]["deadline_at_ms"] = NOW + 31 * DAY
        cases.append(horizon)
        source = proposal_args()
        source["proposal"]["estimate"]["sources"][0]["expires_at_ms"] = NOW + DAY
        cases.append(source)
        quote = proposal_args()
        quote["proposal"]["estimate"]["children"][0]["source"]["kind"] = "quote"
        cases.append(quote)
        unsourced = proposal_args()
        unsourced["proposal"]["estimate"]["sources"] = []
        cases.append(unsourced)
        empty = proposal_args()
        empty["proposal"]["scope"] = "  "
        cases.append(empty)
        for index, args in enumerate(cases):
            with self.subTest(case=index):
                gate = self.hooks.pre_tool_call("spawn_propose_job", args, conversation_id="chat")
                self.assertEqual("block", gate and gate.get("action"))
        self.assertEqual([], self.server.proposal_writes())


if __name__ == "__main__":
    unittest.main()
