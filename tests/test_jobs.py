import unittest
from unittest.mock import Mock

from tests.support import load
from tests.fake_jobs import FakeSpawn, SpawnError
from tests.fake_proposals import MemoryBackend

Jobs = load("jobs").Jobs
terms = load("envelopes").terms


class JobsTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeSpawn()
        self.jobs = Jobs(client=self.server, config=lambda key, default=None: False if key == "lease_keeper" else default)

    def activate(self, conversation="chat-a"):
        return self.jobs.accept({"job_id": "job-123"}, conversation, terms(self.server.job))

    def deliver(self, conversation="chat-a"):
        return self.jobs.deliver({"job_id": "job-123", "files": [{"name": "review.md", "media_type": "text/markdown", "text": "Hello 🌍"}]}, conversation)

    def test_accept_uses_current_terms_and_records_conversation(self):
        result = self.activate()
        self.assertIn("receipt", result)
        self.assertEqual("job-123", self.jobs.state.get("active", "chat-a")["job_id"])
        self.assertIsNone(self.jobs.state.get("active", "chat-b"))
        sent = self.server.mutations()[0][1]
        self.assertEqual(17, sent["envelope"]["expected_revision"])
        self.assertEqual(9, sent["offer_revision"])
        self.assertEqual(4, sent["grant_epoch"])

    def test_acknowledged_accept_recovers_after_restart_without_new_accept(self):
        backend = MemoryBackend()
        self.jobs.state = load("state").State(backend=backend)
        original = self.server.call_tool
        fail = [False]
        def call(name, args=None):
            if name == "spawn_get_job" and fail[0]:
                fail[0] = False
                raise SpawnError("transport_error", uncertain=True)
            result = original(name, args)
            if name == "spawn_accept_job":
                fail[0] = True
            return result
        self.server.call_tool = call
        accepted = self.activate()
        self.assertIn("warning", accepted)
        state = load("state").State(backend=backend)
        self.jobs = Jobs(client=self.server, state=state, config=lambda key, default=None: False)
        self.jobs.job("job-123", "chat-a")
        self.jobs.progress({"job_id": "job-123", "message": "Continue", "waiting_for_input": False}, "chat-a")
        self.assertEqual(1, sum(name == "spawn_accept_job" for name, _ in self.server.calls))
        self.assertIsNone(state.get("pending", "job-123"))

    def test_acknowledged_accept_recovery_refuses_changed_authority_or_owner(self):
        for change in ("conversation", "grant_epoch", "installation_id", "quote_hash", "lease_generation", "terminal"):
            with self.subTest(change=change):
                self.setUp()
                original = self.server.call_tool
                def call(name, args=None):
                    if name == "spawn_get_job" and self.server.receipts:
                        raise SpawnError("transport_error", uncertain=True)
                    return original(name, args)
                self.server.call_tool = call
                self.activate()
                self.server.call_tool = original
                if change in ("grant_epoch", "lease_generation"):
                    self.server.job[change] += 1
                elif change in ("installation_id", "quote_hash"):
                    self.server.job[change] = "f" * 64
                elif change == "terminal":
                    self.server.job["state"]["execution"] = "cancelled"
                with self.assertRaises(SpawnError):
                    self.jobs.job("job-123", "chat-b" if change == "conversation" else "chat-a")
                self.assertIsNone(self.jobs.state.get("active", "chat-a"))
                self.assertEqual(1, len(self.server.mutations()))

    def test_acknowledged_resume_recovers_after_restart_without_new_resume(self):
        backend = MemoryBackend()
        self.jobs.state = load("state").State(backend=backend)
        self.activate()
        original = self.server.call_tool
        expired, lost = [False], [False]
        def call(name, args=None):
            if name == "spawn_heartbeat" and not expired[0]:
                expired[0] = True
                raise SpawnError("LEASE_EXPIRED")
            if name == "spawn_get_job" and lost[0]:
                lost[0] = False
                raise SpawnError("transport_error", uncertain=True)
            result = original(name, args)
            if name == "spawn_resume_job":
                lost[0] = True
            return result
        self.server.call_tool = call
        args = {"job_id": "job-123", "message": "Continue", "waiting_for_input": False}
        with self.assertRaises(SpawnError):
            self.jobs.progress(args, "chat-a")
        self.jobs = Jobs(client=self.server, state=load("state").State(backend=backend), config=lambda key, default=None: False)
        self.jobs.progress(args, "chat-a")
        self.assertEqual(1, sum(name == "spawn_resume_job" for name, _ in self.server.calls))
        self.assertEqual(self.server.job["lease_generation"], self.jobs.state.get("active", "chat-a")["lease_generation"])

    def test_malformed_accept_acknowledgment_recovers_original_request(self):
        for revision in (None, True, "18", 17):
            with self.subTest(revision=revision):
                self.setUp()
                original = self.server.call_tool
                corrupt = [True]
                def call(name, args=None):
                    result = original(name, args)
                    if name == "spawn_accept_job" and corrupt[0]:
                        corrupt[0] = False
                        return {"revision": revision}
                    return result
                self.server.call_tool = call
                with self.assertRaises(SpawnError) as caught:
                    self.activate()
                self.assertEqual("acknowledgment_unverified", caught.exception.code)
                self.assertTrue(caught.exception.uncertain)
                self.activate()
                sent = [args for name, args in self.server.calls if name == "spawn_accept_job"]
                self.assertEqual(sent[0], sent[1])
                self.assertEqual(1, len(self.server.receipts))

    def test_terms_change_after_approval_sends_no_mutation(self):
        approved = terms(self.server.job)
        self.server.job["quote_hash"] = "f" * 64
        with self.assertRaises(SpawnError) as caught:
            self.jobs.accept({"job_id": "job-123"}, "chat-a", approved)
        self.assertEqual("terms_changed", caught.exception.code)
        self.assertEqual([], self.server.mutations())

    def test_uncertain_accept_retries_identical_envelope(self):
        self.server.fail_once["spawn_accept_job"] = SpawnError("transport_error", uncertain=True)
        with self.assertRaises(SpawnError):
            self.activate()
        self.assertIsNotNone(self.jobs.state.get("pending", "job-123"))
        self.activate()
        calls = [args for name, args in self.server.calls if name == "spawn_accept_job"]
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(18, self.server.job["revision"])
        self.assertIsNone(self.jobs.state.get("pending", "job-123"))

    def test_after_commit_mcp_errors_retain_exact_request(self):
        from tests.test_client import Response, rpc, tool
        for error_kind in ("jsonrpc", "internal_tool", "unknown_tool"):
            with self.subTest(error_kind=error_kind):
                self.setUp()
                injected = []
                def request(provider, method, url, **kwargs):
                    body = kwargs["json"]
                    name = body["params"]["name"]
                    result = self.server.call_tool(name, body["params"]["arguments"])
                    if name == "spawn_accept_job" and not injected:
                        injected.append(True)
                        if error_kind == "jsonrpc":
                            return Response({"jsonrpc": "2.0", "id": body["id"], "error": {"code": -32603, "message": "after commit failure"}})
                        code = "INTERNAL_ERROR" if error_kind == "internal_tool" else "UNKNOWN_FAILURE"
                        return Response(rpc({"isError": True, "structuredContent": {"error": {"code": code}}}, body["id"]))
                    return Response(rpc(tool(result), body["id"]))
                self.jobs.client = load("spawn_client").SpawnClient(request)
                with self.assertRaises(SpawnError) as caught:
                    self.activate()
                self.assertTrue(caught.exception.uncertain)
                self.assertEqual("running", self.server.job["state"]["execution"])
                pending = self.jobs.state.get("pending", "job-123")
                self.assertIsNotNone(pending)
                self.activate()
                sent = [args for name, args in self.server.calls if name == "spawn_accept_job"]
                self.assertEqual(2, len(sent))
                self.assertEqual(sent[0], sent[1])
                self.assertEqual(pending["arguments"], sent[1])
                self.assertEqual(18, self.server.job["revision"])
                self.assertEqual(1, len(self.server.receipts))
                self.assertIsNone(self.jobs.state.get("pending", "job-123"))

    def test_uncertain_pending_blocks_different_action(self):
        self.server.fail_once["spawn_accept_job"] = SpawnError("transport_error", uncertain=True)
        with self.assertRaises(SpawnError):
            self.activate()
        count = len(self.server.mutations())
        with self.assertRaises(SpawnError) as caught:
            self.jobs._command(self.server.job, "abandon", {"reason": "stop"})
        self.assertEqual("pending_outcome", caught.exception.code)
        self.assertEqual(count, len(self.server.mutations()))

    def test_uncertain_accept_cannot_be_replayed_by_another_conversation(self):
        self.server.fail_once["spawn_accept_job"] = SpawnError("transport_error", uncertain=True)
        with self.assertRaises(SpawnError):
            self.activate()
        before = len(self.server.calls)
        pending = self.jobs.state.get("pending", "job-123")
        with self.assertRaises(SpawnError) as caught:
            self.activate("chat-b")
        self.assertEqual("active_elsewhere", caught.exception.code)
        self.assertEqual(before, len(self.server.calls))
        self.assertEqual(pending, self.jobs.state.get("pending", "job-123"))
        self.assertEqual("chat-a", self.jobs.state.get("job_owner", "job-123"))
        self.activate()
        self.assertIsNone(self.jobs.state.get("pending", "job-123"))

    def test_uncertain_progress_cannot_be_replayed_by_another_conversation(self):
        self.activate()
        args = {"job_id": "job-123", "message": "Milestone", "waiting_for_input": False}
        self.server.fail_once["spawn_report_progress"] = SpawnError("transport_error", uncertain=True)
        with self.assertRaises(SpawnError):
            self.jobs.progress(args, "chat-a")
        before = len(self.server.calls)
        pending = self.jobs.state.get("pending", "job-123")
        with self.assertRaises(SpawnError) as caught:
            self.jobs.progress(args, "chat-b")
        self.assertEqual("active_elsewhere", caught.exception.code)
        self.assertEqual(before, len(self.server.calls))
        self.assertEqual(pending, self.jobs.state.get("pending", "job-123"))
        self.jobs.progress(args, "chat-a")
        self.assertIsNone(self.jobs.state.get("pending", "job-123"))

    def test_upload_blocked_while_progress_is_uncertain(self):
        self.activate()
        args = {"job_id": "job-123", "message": "Milestone", "waiting_for_input": False}
        self.server.fail_once["spawn_report_progress"] = SpawnError("transport_error", uncertain=True)
        with self.assertRaises(SpawnError):
            self.jobs.progress(args, "chat-a")
        with self.assertRaises(SpawnError) as caught:
            self.deliver()
        self.assertEqual("pending_outcome", caught.exception.code)
        self.assertNotIn("spawn_upload_text", [name for name, _ in self.server.calls])

    def test_changed_authority_blocks_uncertain_retry(self):
        self.server.fail_once["spawn_accept_job"] = SpawnError("transport_error", uncertain=True)
        with self.assertRaises(SpawnError):
            self.activate()
        self.server.job["grant_epoch"] += 1
        with self.assertRaises(SpawnError) as caught:
            self.activate()
        self.assertEqual("authority_changed", caught.exception.code)

    def test_uncertain_progress_can_replay_exact_action(self):
        self.activate()
        args = {"job_id": "job-123", "message": "Milestone", "waiting_for_input": False}
        self.server.fail_once["spawn_report_progress"] = SpawnError("transport_error", uncertain=True)
        with self.assertRaises(SpawnError):
            self.jobs.progress(args, "chat-a")
        self.jobs.progress(args, "chat-a")
        calls = [args for name, args in self.server.calls if name == "spawn_report_progress"]
        self.assertEqual(2, len(calls))
        self.assertEqual(calls[0], calls[1])
        self.assertIsNone(self.jobs.state.get("pending", "job-123"))

    def test_delivery_hash_verified_and_manifest_conversation_bound(self):
        self.activate()
        result = self.deliver()
        self.assertFalse(result["submitted"])
        self.assertEqual(len("Hello 🌍".encode()), result["files"][0]["size_bytes"])
        self.jobs.remember_active("chat-b", self.server.job)
        with self.assertRaises(SpawnError) as caught:
            self.jobs.finish("submit", {"job_id": "job-123", "manifest_hash": result["manifest_hash"]}, "chat-b", terms(self.server.job))
        self.assertEqual("active_elsewhere", caught.exception.code)
        self.assertNotIn("spawn_submit_result", [name for name, _ in self.server.calls])
        self.jobs.finish("submit", {"job_id": "job-123", "manifest_hash": result["manifest_hash"]}, "chat-a", terms(self.server.job))
        self.assertIsNone(self.jobs.state.get("active", "chat-a"))

    def test_text_manifest_corruption_never_records_delivery(self):
        self.activate()
        original = self.server.call_tool
        def call(name, args=None):
            result = original(name, args)
            if name == "spawn_finalize_manifest":
                return {"manifest_hash": "0" * 64, "manifest": {"job_id": "other", "artifacts": []}}
            return result
        self.server.call_tool = call
        with self.assertRaises(SpawnError) as caught:
            self.deliver()
        self.assertEqual("manifest_unverified", caught.exception.code)
        self.assertIsNone(self.jobs.state.get("delivery", ["chat-a", "job-123", "0" * 64]))

    def test_duplicate_upload_retry_reuses_keys_and_ids(self):
        self.activate()
        first = self.deliver()
        second = self.deliver()
        uploads = [args for name, args in self.server.calls if name == "spawn_upload_text"]
        self.assertEqual(uploads[0], uploads[1])
        self.assertEqual(first, second)

    def test_hash_mismatch_never_finalizes_manifest(self):
        self.activate()
        self.server.corrupt_upload = True
        with self.assertRaises(SpawnError) as caught:
            self.deliver()
        self.assertEqual("upload_authority_mismatch", caught.exception.code)
        self.assertNotIn("spawn_finalize_manifest", [name for name, _ in self.server.calls])

    def test_duplicate_filenames_refused_before_upload(self):
        self.activate()
        item = {"name": "review.md", "media_type": "text/plain", "text": "ok"}
        with self.assertRaises(SpawnError) as caught:
            self.jobs.deliver({"job_id": "job-123", "files": [item, item]}, "chat-a")
        self.assertEqual("duplicate_file", caught.exception.code)
        self.assertNotIn("spawn_upload_text", [name for name, _ in self.server.calls])

    def test_old_lease_manifest_not_submittable(self):
        self.activate()
        result = self.deliver()
        self.server.job["lease_generation"] += 1
        self.jobs.remember_active("chat-a", self.server.job)
        with self.assertRaises(SpawnError) as caught:
            self.jobs.finish("submit", {"job_id": "job-123", "manifest_hash": result["manifest_hash"]}, "chat-a", terms(self.server.job))
        self.assertEqual("manifest_not_owned", caught.exception.code)

    def test_background_terminal_check_preserves_uncertain_finish_replay(self):
        self.activate()
        manifest = self.deliver()["manifest_hash"]
        args = {"job_id": "job-123", "manifest_hash": manifest}
        approved = terms(self.server.job)
        self.server.fail_once["spawn_submit_result"] = SpawnError("transport_error", uncertain=True)
        with self.assertRaises(SpawnError):
            self.jobs.finish("submit", args, "chat-a", approved)
        self.assertEqual("submitted", self.server.job["state"]["execution"])
        with self.assertRaises(SpawnError) as caught:
            self.jobs.heartbeat("job-123", "chat-a", background=True)
        self.assertEqual("pending_outcome", caught.exception.code)
        self.assertIsNotNone(self.jobs.state.get("active", "chat-a"))
        self.assertEqual("chat-a", self.jobs.state.get("job_owner", "job-123"))
        self.jobs.finish("submit", args, "chat-a", approved)
        calls = [args for name, args in self.server.calls if name == "spawn_submit_result"]
        self.assertEqual(2, len(calls))
        self.assertEqual(calls[0], calls[1])
        self.assertIsNone(self.jobs.state.get("pending", "job-123"))
        self.assertIsNone(self.jobs.state.get("job_owner", "job-123"))

    def test_submit_and_abandon_stop_keeper(self):
        for action in ("submit", "abandon"):
            with self.subTest(action=action):
                self.setUp()
                self.activate()
                args = {"job_id": "job-123", "reason": "Owner requested stop"}
                if action == "submit":
                    args = {"job_id": "job-123", "manifest_hash": self.deliver()["manifest_hash"]}
                self.jobs.keeper = Mock()
                self.jobs.finish(action, args, "chat-a", load("envelopes").terms(self.server.job))
                self.jobs.keeper.stop.assert_called_once_with("job-123")
                self.assertIsNone(self.jobs.state.get("active", "chat-a"))

    def test_background_heartbeat_never_overwrites_pending(self):
        self.activate()
        self.jobs.state.set("pending", "job-123", {"intent": "another"})
        before = len(self.server.mutations())
        with self.assertRaises(SpawnError) as caught:
            self.jobs.heartbeat("job-123", "chat-a", background=True)
        self.assertEqual("pending_outcome", caught.exception.code)
        self.assertEqual(before, len(self.server.mutations()))

    def test_terminal_heartbeat_clears_active_without_mutation(self):
        self.activate()
        self.server.job["state"]["execution"] = "submitted"
        before = len(self.server.mutations())
        self.jobs.heartbeat("job-123", "chat-a", background=True)
        self.assertIsNone(self.jobs.state.get("active", "chat-a"))
        self.assertEqual(before, len(self.server.mutations()))


if __name__ == "__main__":
    unittest.main()
