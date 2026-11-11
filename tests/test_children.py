import copy
import json
import unittest

from tests.support import load
from tests.fake_proposals import ProposalServer, MemoryBackend, SpawnError

Jobs = load("jobs").Jobs
Hooks = load("hooks").Hooks
Tools = load("tools").Tools
State = load("state").State


def child_args():
    return {"job_id": "job-123", "children": [{"step_id": "qa", "room_id": "room-qa", "service_id": "service-qa",
            "brief": "Review the supplied game source for collision and reset bugs.", "deliverable": "Reproducible source findings",
            "deadline_at_ms": 4000000000000, "max_budget_micro_usd": "2000000"}]}


class ChildServer(ProposalServer):
    def __init__(self):
        super().__init__()
        self.job["state"]["execution"] = "running"
        self.job["quote"].update(currency="USDC", seller_micro_units="19000000")
        self.job["child_commission_plan"] = {
            "accepted_terms_hash": "d" * 64, "plan_hash": "e" * 64, "terms_ref": "terms-7",
            "slots": [{"step_id": "qa", "role": "qa", "cap_micro_usdc": "2000000", "deadline_at_ms": 4000000000000,
                       "result_contract": "text_v1", "reviewer": {"owner_id": "buyer-1", "project_id": "project-1"}}],
            "provider_billing": {"version": "spawn.accepted-provider-billing.v1", "pricing_revision": "price-v1",
                "provider_currency": "USD", "customer_currency": "USDC", "scale": 6,
                "rate_numerator": "1", "rate_denominator": "1", "rounding": "ceiling", "aggregation": "whole_job",
                "conversion_difference_bearer": "platform", "incurred_generation_costs": "charged_even_if_generation_fails",
                "refund_basis": "unused_only", "cost_recording": "automatic_verified_usage",
                "unused_allocation_release": "after_verified_final_bill_or_unspent_cancellation"},
        }
        self.candidates = [{"room_id": "room-qa", "service_id": "service-qa", "service_hash": "sha256:" + "f" * 64,
                            "name": "Review room", "capabilities": ["coding.diff_review"], "quote_required": True}]
        self.drafts = {}

    def call_tool(self, name, arguments=None):
        args = copy.deepcopy(arguments or {})
        if name == "spawn_find_backrooms":
            self.calls.append((name, args))
            candidates = [c for c in self.candidates if all(cap in c["capabilities"] for cap in args["required_capabilities"])]
            return {"schema_version": "spawn.room-routing.v1", "request": args, "candidates": copy.deepcopy(candidates),
                    "selection_hash": "sha256:" + "a" * 64, "status": "candidates_available" if candidates else "no_eligible_service"}
        if name == "spawn_draft_child_commissions":
            self.calls.append((name, args))
            key = args["envelope"]["idempotency_key"]
            if key in self.drafts:
                return copy.deepcopy(self.drafts[key])
            if args["lease_generation"] != self.job["lease_generation"]:
                raise SpawnError("EXTERNAL_CHILD_LEASE_STALE")
            assert args["accepted_terms_hash"] == self.job["child_commission_plan"]["accepted_terms_hash"]
            assert args["plan_hash"] == self.job["child_commission_plan"]["plan_hash"]
            assert args["envelope"]["expected_revision"] == self.job["revision"]
            assert args["lease_generation"] == self.job["lease_generation"]
            result = {"schema_version": "spawn.external-job-children.v1", "draft_id": "external_children_" + "1" * 40,
                      "draft_hash": "2" * 64, "job_id": "job-123", "accepted_terms_hash": "d" * 64,
                      "plan_hash": "e" * 64, "installation_id": self.job["installation_id"], "created_at_ms": 1900000000000,
                      "children": [{**c, "input_export_hash": "sha256:" + "3" * 64, "state": "awaiting_native_review"} for c in args["children"]],
                      "approval_required": True}
            self.drafts[key] = copy.deepcopy(result)
            if name in self.fail_once:
                raise self.fail_once.pop(name)
            return result
        if name == "spawn_get_child_commissions":
            self.calls.append((name, args))
            return copy.deepcopy(next(iter(self.drafts.values())))
        return super().call_tool(name, args)

    def child_writes(self):
        return [args for name, args in self.calls if name == "spawn_draft_child_commissions"]


class ChildTests(unittest.TestCase):
    def setUp(self):
        self.server = ChildServer()
        self.backend = MemoryBackend()
        self.restart()

    def restart(self):
        self.jobs = Jobs(client=self.server, state=State(backend=self.backend))
        self.hooks = Hooks(self.jobs)
        self.tools = Tools(self.jobs, self.hooks)
        self.jobs.snapshot("job-123")
        self.jobs.remember_active("chat", self.server.job)

    def run_tool(self, name, args, conversation="chat"):
        return json.loads(self.tools.handler(name)(args, conversation_id=conversation))

    def discover(self):
        result = self.run_tool("spawn_find_backrooms", {"required_capabilities": ["coding.diff_review"]})
        self.assertTrue(result["ok"], result)
        return result

    def test_discovery_caches_exact_service_without_inventing_art(self):
        result = self.discover()
        self.assertEqual("service-qa", result["candidates"][0]["service_id"])
        result = self.run_tool("spawn_find_backrooms", {"required_capabilities": ["art.pixel_grid"]})
        self.assertTrue(result["ok"], result)
        self.assertEqual("no_eligible_service", result["status"])
        self.assertEqual([], result["candidates"])
        self.assertEqual([], self.server.child_writes())

    def test_draft_requires_human_approval_of_discovered_service_and_exact_input(self):
        args = child_args()
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        self.discover()
        before = len(self.server.calls)
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        self.assertEqual(before, len(self.server.calls))
        for text in ("2.000000", "buyer-1", "collision and reset", "service-qa", "native review"):
            self.assertIn(text, gate["message"])
        result = self.run_tool("spawn_draft_child_commissions", args)
        self.assertTrue(result["ok"], result)
        sent = self.server.child_writes()[0]
        self.assertEqual("d" * 64, sent["accepted_terms_hash"])
        self.assertEqual("e" * 64, sent["plan_hash"])
        self.assertEqual("sha256:" + "f" * 64, sent["children"][0]["service_hash"])
        self.assertEqual({"owner_id": "buyer-1", "project_id": "project-1"}, sent["children"][0]["reviewer"])
        self.assertTrue(result["approval_required"])
        self.assertEqual("awaiting_native_review", result["children"][0]["state"])

    def test_changed_service_or_parent_plan_after_prompt_sends_no_draft(self):
        for changed in ("service", "plan", "lease", "installation"):
            with self.subTest(changed=changed):
                self.setUp()
                self.discover()
                gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", child_args(), conversation_id="chat")
                self.assertEqual("approve", gate and gate.get("action"))
                if changed == "service":
                    self.server.candidates[0]["service_hash"] = "sha256:" + "9" * 64
                elif changed == "plan":
                    self.server.job["child_commission_plan"]["plan_hash"] = "9" * 64
                elif changed == "lease":
                    self.server.job["lease_generation"] += 1
                else:
                    self.server.job["installation_id"] = "wrong-installation"
                result = self.run_tool("spawn_draft_child_commissions", child_args())
                self.assertFalse(result["ok"], result)
                self.assertEqual([], self.server.child_writes())

    def test_native_budget_conversion_honors_accepted_usdc_cap(self):
        self.server.job["child_commission_plan"]["provider_billing"]["rate_numerator"] = "3"
        self.server.job["child_commission_plan"]["provider_billing"]["rate_denominator"] = "2"
        self.jobs.snapshot("job-123")
        self.discover()
        args = child_args()
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        args["children"][0]["max_budget_micro_usd"] = "1333333"
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        args["children"][0]["max_budget_micro_usd"] = "1333334"
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        self.assertEqual([], self.server.child_writes())

    def test_lost_draft_response_replays_same_envelope_after_restart(self):
        self.discover()
        args = child_args()
        self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.server.fail_once["spawn_draft_child_commissions"] = SpawnError("transport_error", uncertain=True)
        first = self.run_tool("spawn_draft_child_commissions", args)
        self.assertTrue(first.get("outcome_uncertain"), first)
        self.restart()
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        result = self.run_tool("spawn_draft_child_commissions", args)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.server.child_writes()[0], self.server.child_writes()[1])
        self.assertEqual(1, len(self.server.drafts))
        status = self.run_tool("spawn_get_child_commissions", {"job_id": "job-123", "draft_id": result["draft_id"]})
        self.assertTrue(status["ok"], status)
        self.assertEqual(result["draft_id"], status["draft_id"])

    def test_malformed_draft_receipt_keeps_pending_and_blocks_other_job_writes(self):
        self.discover()
        args = child_args()
        self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        original = self.server.call_tool
        def malformed(name, arguments=None):
            result = original(name, arguments)
            if name == "spawn_draft_child_commissions":
                result["draft_hash"] = "invalid"
            return result
        self.server.call_tool = malformed
        result = self.run_tool("spawn_draft_child_commissions", args)
        self.assertTrue(result.get("outcome_uncertain"), result)
        self.assertIsNotNone(self.jobs.state.get("pending_children", "job-123"))

    def test_lost_draft_recovers_old_receipt_after_lease_and_plan_change(self):
        self.discover()
        args = child_args()
        self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.server.fail_once["spawn_draft_child_commissions"] = SpawnError("transport_error", uncertain=True)
        self.assertTrue(self.run_tool("spawn_draft_child_commissions", args).get("outcome_uncertain"))
        original = copy.deepcopy(self.server.child_writes()[0])
        self.server.job["lease_generation"] += 1
        self.server.job["lease_expires_at_ms"] = 1
        self.server.job["revision"] += 4
        self.server.job.pop("child_commission_plan")
        self.jobs = Jobs(client=self.server, state=State(backend=self.backend))
        self.hooks = Hooks(self.jobs)
        self.tools = Tools(self.jobs, self.hooks)
        self.jobs.snapshot("job-123")
        for candidate, conversation in (({**args, "children": [{**args["children"][0], "brief": "Changed export"}]}, "chat"), (args, "other-chat")):
            gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", candidate, conversation_id=conversation)
            self.assertEqual("block", gate and gate.get("action"))
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        result = self.run_tool("spawn_draft_child_commissions", args)
        self.assertTrue(result["ok"], result)
        self.assertEqual(original, self.server.child_writes()[-1])
        self.assertEqual(1, len(self.server.drafts))

    def test_uncommitted_stale_child_recovery_does_not_create_a_new_draft(self):
        self.discover()
        args = child_args()
        original = self.server.call_tool
        def drop_before_commit(name, arguments=None):
            if name == "spawn_draft_child_commissions":
                self.server.call_tool = original
                raise SpawnError("transport_error", uncertain=True)
            return original(name, arguments)
        self.server.call_tool = drop_before_commit
        self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertTrue(self.run_tool("spawn_draft_child_commissions", args).get("outcome_uncertain"))
        self.server.job["lease_generation"] += 1
        self.jobs.snapshot("job-123")
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        result = self.run_tool("spawn_draft_child_commissions", args)
        self.assertEqual("EXTERNAL_CHILD_LEASE_STALE", result.get("error"), result)
        self.assertEqual({}, self.server.drafts)

    def test_disabled_child_feature_returns_clear_preview_guidance(self):
        original = self.server.call_tool
        def disabled(name, arguments=None):
            if name == "spawn_find_backrooms":
                raise SpawnError("EXTERNAL_JOB_CHILDREN_DISABLED")
            return original(name, arguments)
        self.server.call_tool = disabled
        result = self.run_tool("spawn_find_backrooms", {"required_capabilities": ["coding.diff_review"]})
        self.assertEqual("feature_unavailable", result.get("error"), result)

    def test_child_receipt_recovery_rechecks_current_identity_before_old_envelope(self):
        self.discover()
        args = child_args()
        self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.server.fail_once["spawn_draft_child_commissions"] = SpawnError("transport_error", uncertain=True)
        self.run_tool("spawn_draft_child_commissions", args)
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"))
        original = self.server.call_tool
        def replaced_grant(name, arguments=None):
            result = original(name, arguments)
            if name == "spawn_identity":
                result["grant_epoch"] += 1
            return result
        self.server.call_tool = replaced_grant
        result = self.run_tool("spawn_draft_child_commissions", args)
        self.assertEqual("authority_changed", result.get("error"), result)
        self.assertEqual(1, len(self.server.child_writes()))

    def test_uncertain_child_blocks_other_parent_mutations(self):
        self.discover()
        args = child_args()
        self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.server.fail_once["spawn_draft_child_commissions"] = SpawnError("transport_error", uncertain=True)
        self.run_tool("spawn_draft_child_commissions", args)
        progress = self.run_tool("spawn_progress", {"job_id": "job-123", "message": "Continue", "waiting_for_input": False})
        self.assertEqual("pending_outcome", progress.get("error"), progress)
        self.assertFalse(any(name in {"spawn_heartbeat", "spawn_report_progress"} for name, _args in self.server.calls))

    def test_duplicate_room_or_forged_service_hash_is_blocked_before_approval(self):
        self.discover()
        args = child_args()
        args["children"].append(copy.deepcopy(args["children"][0]))
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        args = child_args()
        args["children"][0]["service_hash"] = "sha256:" + "0" * 64
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        self.assertEqual([], self.server.child_writes())


if __name__ == "__main__":
    unittest.main()
