"""Synthetic successor drafts: no native approval, execution or payment."""
import copy
import unittest

from tests import test_children as child_fixture
from tests.fake_proposals import MemoryBackend, SpawnError
from tests.support import load

envelope = load("envelopes").envelope
child_args = child_fixture.child_args


class ReplacementServer(child_fixture.ChildServer):
    def __init__(self):
        super().__init__()
        child = {
            **child_args()["children"][0],
            "service_hash": self.candidates[0]["service_hash"],
            "reviewer": self.job["child_commission_plan"]["slots"][0]["reviewer"],
            "result_contract": "text_v1", "state": "revision_requested",
            "input_export_hash": "sha256:" + "3" * 64,
            "attempt": {
                "ordinal": 1, "active": True, "predecessor": None, "successor": None,
                "lifetime_spent_micro_usdc": "500000", "remaining_slot_micro_usdc": "1500000",
                "replacement": {"status": "eligible", "reason": "The original result was rejected and its final cost is recorded.",
                                "closure_hash": "c" * 64},
            },
        }
        self.predecessor = {
            "schema_version": "spawn.external-job-children.v1", "draft_id": "external_children_" + "a" * 40,
            "draft_hash": "b" * 64, "job_id": "job-123", "accepted_terms_hash": "d" * 64,
            "plan_hash": "e" * 64, "installation_id": self.job["installation_id"], "created_at_ms": 1900000000000,
            "approval_required": True, "children": [child],
        }
        self.drafts["predecessor"] = self.predecessor

    def reference(self):
        return {"step_id": "qa", "draft_id": self.predecessor["draft_id"], "draft_hash": self.predecessor["draft_hash"],
                "closure_hash": self.predecessor["children"][0]["attempt"]["replacement"]["closure_hash"]}

    def call_tool(self, name, arguments=None):
        args = copy.deepcopy(arguments or {})
        if name == "spawn_get_child_commissions":
            self.calls.append((name, args))
            for draft in self.drafts.values():
                if draft["draft_id"] == args["draft_id"]:
                    return copy.deepcopy(draft)
            raise SpawnError("EXTERNAL_CHILD_DRAFT_NOT_FOUND")
        if name == "spawn_draft_child_commissions" and args.get("replaces"):
            failure = self.fail_once.pop(name, None)
            result = super().call_tool(name, args)
            for child in result["children"]:
                ref = next(ref for ref in args["replaces"] if ref["step_id"] == child["step_id"])
                child["attempt"] = {
                    "ordinal": 2, "active": True,
                    "predecessor": {key: ref[key] for key in ("draft_id", "draft_hash", "step_id")}, "successor": None,
                    "lifetime_spent_micro_usdc": "500000", "remaining_slot_micro_usdc": "1500000",
                    "replacement": {"status": "requires_finality", "reason": "The current attempt has no final outcome."},
                }
                previous = self.predecessor["children"][0]["attempt"]
                previous["active"] = False
                previous["successor"] = {"draft_id": result["draft_id"], "draft_hash": result["draft_hash"], "step_id": child["step_id"]}
                previous["replacement"] = {"status": "unavailable", "reason": "This attempt already has a successor."}
            self.drafts[args["envelope"]["idempotency_key"]] = copy.deepcopy(result)
            if failure:
                raise failure
            return result
        return super().call_tool(name, args)


class ChildReplacementTests(unittest.TestCase):
    restart = child_fixture.ChildTests.restart
    run_tool = child_fixture.ChildTests.run_tool
    discover = child_fixture.ChildTests.discover

    def setUp(self):
        self.server = ReplacementServer()
        self.backend = MemoryBackend()
        self.restart()

    def args(self):
        args = child_args()
        args["children"][0]["max_budget_micro_usd"] = "1500000"
        args["replaces"] = [self.server.reference()]
        return args

    def read_predecessor(self):
        result = self.run_tool("spawn_get_child_commissions", {"job_id": "job-123", "draft_id": self.server.predecessor["draft_id"]})
        self.assertTrue(result["ok"], result)
        return result

    def ready(self):
        self.discover()
        self.read_predecessor()
        return self.args()

    def approve(self, args):
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("approve", gate and gate.get("action"), gate)
        return gate

    def test_replacement_requires_a_read_canonical_predecessor_and_exact_host_approval(self):
        self.discover()
        args = self.args()
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        self.read_predecessor()
        calls = len(self.server.calls)
        gate = self.approve(args)
        self.assertEqual(calls, len(self.server.calls), "The approval hook must remain network-free")
        for text in (args["replaces"][0]["draft_id"], "b" * 64, "c" * 64, "0.500000", "1.500000", "fresh native"):
            self.assertIn(text, gate["message"])
        result = self.run_tool("spawn_draft_child_commissions", args)
        self.assertTrue(result["ok"], result)
        sent = self.server.child_writes()[0]
        self.assertEqual(args["replaces"], sent["replaces"])
        self.assertEqual(envelope(self.server.job, "draft_children", {"children": sent["children"], "plan_hash": sent["plan_hash"], "replaces": args["replaces"]}), sent["envelope"])
        self.assertEqual(self.server.predecessor["draft_id"], result["children"][0]["attempt"]["predecessor"]["draft_id"])

    def test_unknown_finality_wrong_hash_duplicate_step_and_capacity_block_approval(self):
        for change in ("unknown", "hash", "closure", "duplicate", "foreign_step", "capacity", "inconsistent_budget"):
            with self.subTest(change=change):
                self.setUp()
                args = self.args()
                attempt = self.server.predecessor["children"][0]["attempt"]
                if change == "unknown":
                    attempt["replacement"] = {"status": "requires_finality", "reason": "The work outcome is unknown."}
                elif change == "hash":
                    args["replaces"][0]["draft_hash"] = "9" * 64
                elif change == "closure":
                    args["replaces"][0]["closure_hash"] = "9" * 64
                elif change == "duplicate":
                    args["replaces"].append(copy.deepcopy(args["replaces"][0]))
                elif change == "foreign_step":
                    args["replaces"][0]["step_id"] = "other"
                elif change == "capacity":
                    attempt["ordinal"] = 8
                else:
                    attempt["remaining_slot_micro_usdc"] = "2000000"
                self.discover()
                self.read_predecessor()
                gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
                self.assertEqual("block", gate and gate.get("action"), gate)
                self.assertEqual([], self.server.child_writes())

    def test_changed_closure_or_economics_after_approval_sends_no_draft(self):
        for change in ("closure", "cost", "unknown", "service"):
            with self.subTest(change=change):
                self.setUp()
                args = self.ready()
                self.approve(args)
                attempt = self.server.predecessor["children"][0]["attempt"]
                if change == "closure":
                    attempt["replacement"]["closure_hash"] = "9" * 64
                elif change == "cost":
                    attempt["lifetime_spent_micro_usdc"] = "600000"
                    attempt["remaining_slot_micro_usdc"] = "1400000"
                elif change == "unknown":
                    attempt["replacement"] = {"status": "requires_finality", "reason": "Finality needs reconciliation."}
                else:
                    self.server.candidates[0]["service_hash"] = "sha256:" + "9" * 64
                    self.discover()
                result = self.run_tool("spawn_draft_child_commissions", args)
                self.assertFalse(result["ok"], result)
                self.assertEqual([], self.server.child_writes())
                self.assertIsNone(self.jobs.state.get("pending_children", "job-123"))

    def test_lifetime_cost_and_new_native_cap_fit_original_converted_slot(self):
        self.server.job["child_commission_plan"]["provider_billing"].update(rate_numerator="3", rate_denominator="2")
        self.jobs.snapshot("job-123")
        args = self.ready()
        args["children"][0]["max_budget_micro_usd"] = "1000000"
        self.approve(args)
        args["children"][0]["max_budget_micro_usd"] = "1000001"
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        self.assertEqual([], self.server.child_writes())

    def test_lost_successor_response_replays_exact_envelope_after_restart_and_new_lease(self):
        args = self.ready()
        self.approve(args)
        self.server.fail_once["spawn_draft_child_commissions"] = SpawnError("transport_error", uncertain=True)
        first = self.run_tool("spawn_draft_child_commissions", args)
        self.assertTrue(first.get("outcome_uncertain"), first)
        original = copy.deepcopy(self.server.child_writes()[0])
        self.server.job["lease_generation"] += 1
        self.server.job["revision"] += 3
        self.server.candidates[0]["service_hash"] = "sha256:" + "9" * 64
        self.restart()
        self.discover()
        gate = self.approve(args)
        self.assertIn("c" * 64, gate["message"])
        self.assertIn("sha256:" + "f" * 64, gate["message"])
        before = len(self.server.calls)
        result = self.run_tool("spawn_draft_child_commissions", args)
        self.assertTrue(result["ok"], result)
        self.assertEqual(original, self.server.child_writes()[-1])
        self.assertEqual(2, len(self.server.drafts))
        self.assertFalse(any(name == "spawn_get_child_commissions" for name, _ in self.server.calls[before:]))

    def test_mismatched_successor_receipt_keeps_the_exact_pending_operation(self):
        args = self.ready()
        self.approve(args)
        original = self.server.call_tool
        def malformed(name, arguments=None):
            result = original(name, arguments)
            if name == "spawn_draft_child_commissions":
                result["children"][0]["attempt"]["predecessor"]["draft_hash"] = "9" * 64
            return result
        self.server.call_tool = malformed
        result = self.run_tool("spawn_draft_child_commissions", args)
        self.assertTrue(result.get("outcome_uncertain"), result)
        self.assertEqual(args["replaces"], self.jobs.state.get("pending_children", "job-123")["arguments"]["replaces"])

    def test_a_fresh_device_reads_the_existing_successor_without_creating_another(self):
        args = self.ready()
        self.approve(args)
        self.server.fail_once["spawn_draft_child_commissions"] = SpawnError("transport_error", uncertain=True)
        self.assertTrue(self.run_tool("spawn_draft_child_commissions", args).get("outcome_uncertain"))
        self.backend = MemoryBackend()
        self.restart()
        self.discover()
        previous = self.read_predecessor()
        successor = previous["children"][0]["attempt"]["successor"]
        self.assertIsNotNone(successor)
        gate = self.hooks.pre_tool_call("spawn_draft_child_commissions", args, conversation_id="chat")
        self.assertEqual("block", gate and gate.get("action"))
        recovered = self.run_tool("spawn_get_child_commissions", {"job_id": "job-123", "draft_id": successor["draft_id"]})
        self.assertTrue(recovered["ok"], recovered)
        self.assertEqual(successor["draft_hash"], recovered["draft_hash"])
        self.assertEqual(1, len(self.server.child_writes()))


if __name__ == "__main__":
    unittest.main()
