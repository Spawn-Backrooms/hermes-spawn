"""Exercise the same hostile server boundary through all delivery entry points."""
import copy
import tempfile
from pathlib import Path
import unittest

from tests.support import load
from tests.fake_jobs import FakeSpawn, SpawnError
from tests.fake_proposals import MemoryBackend
from tests.test_packages import PackageServer, archive
from tests.test_file_delivery import FileServer

Jobs, State = load("jobs").Jobs, load("state").State
digest = load("envelopes").digest


class ArtifactDeliveryTests(unittest.TestCase):
    def setup_route(self, route):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.server = {"text": FakeSpawn, "game": PackageServer, "files": FileServer}[route]()
        self.backend = MemoryBackend()
        self.route = route
        self.restart()
        self.jobs.accept({"job_id": "job-123"}, "chat", load("envelopes").terms(self.server.job))
        (self.root / "game.zip").write_bytes(archive())
        (self.root / "output.bin").write_bytes(b"a\x00b")

    def restart(self):
        self.jobs = Jobs(client=self.server, state=State(backend=self.backend), cwd=self.root,
                         config=lambda key, default=None: False)

    def deliver(self):
        if self.route == "text":
            return self.jobs.deliver({"job_id": "job-123", "files": [
                {"name": "review.md", "media_type": "text/markdown", "text": "Review 🌍"}]}, "chat")
        if self.route == "game":
            return self.jobs.packages.deliver({"job_id": "job-123", "path": "game.zip"}, "chat")
        return self.jobs.file_delivery.deliver({"job_id": "job-123", "files": [{"path": "output.bin"}]}, "chat")

    def test_all_routes_reject_forged_manifest_then_recover_exact_batch(self):
        for route in ("text", "game", "files"):
            for field in ("job_id", "installation_id", "grant_epoch", "lease_generation", "provenance_kind",
                          "version", "missing", "extra", "upload_id", "name", "media_type", "sha256", "size_bytes", "hash"):
                with self.subTest(route=route, field=field):
                    self.setup_route(route)
                    original = self.server.call_tool
                    claims = []
                    def call(name, args=None):
                        result = original(name, args)
                        if name == "spawn_finalize_manifest":
                            result = copy.deepcopy(result)
                            manifest = result["manifest"]
                            if field == "missing":
                                manifest["artifacts"] = []
                            elif field == "extra":
                                manifest["artifacts"].append(copy.deepcopy(manifest["artifacts"][0]))
                            elif field == "upload_id":
                                manifest["artifacts"][0][field] = "foreign_upload"
                            elif field in ("name", "media_type", "sha256", "size_bytes"):
                                manifest["artifacts"][0]["descriptor"][field] = 99 if field == "size_bytes" else "wrong"
                            elif field != "hash":
                                manifest[field] = True if field == "version" else "wrong"
                            result["manifest_hash"] = "0" * 64 if field == "hash" else digest(manifest)
                            claims.append(result["manifest_hash"])
                        return result
                    self.server.call_tool = call
                    with self.assertRaises(SpawnError) as caught:
                        self.deliver()
                    self.assertEqual("manifest_unverified", caught.exception.code)
                    self.assertTrue(caught.exception.uncertain)
                    self.assertIsNone(self.jobs.state.get("delivery", ["chat", "job-123", claims[0]]))
                    self.server.call_tool = original
                    self.restart()
                    result = self.deliver()
                    self.assertFalse(result["submitted"])
                    finalized = [args for name, args in self.server.calls if name == "spawn_finalize_manifest"]
                    self.assertEqual(finalized[0], finalized[1])
                    self.assertEqual(1, len(self.server.uploads))

    def test_retry_refuses_changed_upload_identity(self):
        for route in ("text", "game", "files"):
            with self.subTest(route=route):
                self.setup_route(route)
                self.server.fail_once["spawn_finalize_manifest"] = SpawnError("transport_error", uncertain=True)
                with self.assertRaises(SpawnError):
                    self.deliver()
                self.restart()
                original = self.server.call_tool
                def call(name, args=None):
                    result = original(name, args)
                    if name in ("spawn_upload_text", "spawn_prepare_upload"):
                        result["upload_id"] = "different_upload"
                    return result
                self.server.call_tool = call
                with self.assertRaises(SpawnError) as caught:
                    self.deliver()
                self.assertEqual("upload_authority_mismatch", caught.exception.code)
                self.assertEqual(1, sum(name == "spawn_finalize_manifest" for name, _ in self.server.calls))

    def test_all_routes_block_changed_current_authority_after_finalization(self):
        for route in ("text", "game", "files"):
            with self.subTest(route=route):
                self.setup_route(route)
                original = self.server.call_tool
                manifest_hash = []
                def call(name, args=None):
                    result = original(name, args)
                    if name == "spawn_finalize_manifest":
                        manifest_hash.append(result["manifest_hash"])
                        self.server.job["grant_epoch"] += 1
                    return result
                self.server.call_tool = call
                with self.assertRaises(SpawnError) as caught:
                    self.deliver()
                self.assertEqual("authority_changed", caught.exception.code)
                self.assertIsNone(self.jobs.state.get("delivery", ["chat", "job-123", manifest_hash[0]]))

    def test_text_upload_requires_complete_descriptor_and_authority(self):
        for field in ("job_id", "installation_id", "grant_epoch", "lease_generation", "state", "name", "media_type", "sha256", "size_bytes"):
            with self.subTest(field=field):
                self.setup_route("text")
                original = self.server.call_tool
                def call(name, args=None):
                    result = original(name, args)
                    if name == "spawn_upload_text":
                        target = result["descriptor"] if field in ("name", "media_type", "sha256", "size_bytes") else result
                        target[field] = "wrong"
                    return result
                self.server.call_tool = call
                with self.assertRaises(SpawnError) as caught:
                    self.deliver()
                self.assertEqual("upload_authority_mismatch", caught.exception.code)
                self.assertFalse(any(name == "spawn_finalize_manifest" for name, _ in self.server.calls))
                self.assertIsNotNone(self.jobs.state.get("pending_text", "job-123"))

    def test_lost_text_response_restarts_with_identical_keys_and_bytes(self):
        for action in ("spawn_upload_text", "spawn_finalize_manifest"):
            with self.subTest(action=action):
                self.setup_route("text")
                self.server.fail_once[action] = SpawnError("transport_error", uncertain=True)
                with self.assertRaises(SpawnError):
                    self.deliver()
                self.restart()
                with self.assertRaises(SpawnError) as caught:
                    self.jobs.deliver({"job_id": "job-123", "files": [
                        {"name": "changed.md", "media_type": "text/markdown", "text": "Review 🌍"}]}, "chat")
                self.assertEqual("pending_outcome", caught.exception.code)
                with self.assertRaises(SpawnError) as caught:
                    self.jobs.progress({"job_id": "job-123", "message": "Continue", "waiting_for_input": False}, "chat")
                self.assertEqual("pending_outcome", caught.exception.code)
                self.deliver()
                uploaded = [args for name, args in self.server.calls if name == "spawn_upload_text"]
                self.assertEqual(uploaded[0], uploaded[1])
                self.assertIsNone(self.jobs.state.get("pending_text", "job-123"))
                self.assertEqual(1, len(self.server.uploads))

    def test_expired_lost_delivery_releases_recovery_and_fences_old_generation(self):
        for route in ("text", "game", "files"):
            upload_action = "spawn_upload_text" if route == "text" else "upload_game_package"
            for lost_action in (upload_action, "spawn_finalize_manifest"):
                for code in ("LEASE_EXPIRED", "ARTIFACT_LEASE_STALE", "LEASE_GENERATION_STALE", "UPLOAD_EXPIRED"):
                    with self.subTest(route=route, lost_action=lost_action, code=code):
                        self.setup_route(route)
                        previous = self.deliver()
                        generation = self.server.job["lease_generation"]
                        self.server.fail_once[lost_action] = SpawnError("transport_error", uncertain=True)
                        with self.assertRaises(SpawnError) as lost:
                            self.deliver()
                        self.assertTrue(lost.exception.uncertain)
                        self.restart()
                        original = self.server.call_tool
                        def call(name, args=None):
                            if name in ("spawn_upload_text", "spawn_prepare_upload"):
                                raise load("spawn_client").mapped_error({"code": code})
                            if name == "spawn_heartbeat" and self.server.job["lease_generation"] == generation:
                                raise SpawnError("LEASE_EXPIRED")
                            return original(name, args)
                        self.server.call_tool = call
                        with self.assertRaises(SpawnError) as expired:
                            self.deliver()
                        self.assertEqual(code, expired.exception.code)
                        self.assertTrue(expired.exception.details.get("batch_recovery_released"))
                        self.assertIsNone(self.jobs.state.get("pending_" + {"text": "text", "game": "package", "files": "files"}[route], "job-123"))
                        self.assertEqual("chat", self.jobs.state.get("job_owner", "job-123"))
                        self.assertEqual(generation, self.server.job["lease_generation"])
                        self.assertEqual(0, sum(name == "spawn_resume_job" for name, _ in self.server.calls))
                        self.restart()
                        self.jobs.progress({"job_id": "job-123", "message": "Resume", "waiting_for_input": False}, "chat")
                        self.assertEqual(generation + 1, self.server.job["lease_generation"])
                        self.assertEqual(1, sum(name == "spawn_resume_job" for name, _ in self.server.calls))
                        with self.assertRaises(SpawnError) as stale:
                            self.jobs.finish("submit", {"job_id": "job-123", "manifest_hash": previous["manifest_hash"]},
                                             "chat", load("envelopes").terms(self.server.job))
                        self.assertEqual("manifest_not_owned", stale.exception.code)
                        self.assertFalse(any(name == "spawn_submit_result" for name, _ in self.server.calls))
                        self.server.call_tool = original
                        current = self.deliver()
                        self.assertNotEqual(previous["manifest_hash"], current["manifest_hash"])
                        self.assertTrue(set(previous["upload_ids"]).isdisjoint(current["upload_ids"]))
                        self.assertTrue(all(upload_id in self.server.uploads for upload_id in previous["upload_ids"]))

    def test_expired_lost_delivery_allows_explicit_abandon(self):
        for route in ("text", "game", "files"):
            with self.subTest(route=route):
                self.setup_route(route)
                self.server.fail_once["spawn_finalize_manifest"] = SpawnError("transport_error", uncertain=True)
                with self.assertRaises(SpawnError):
                    self.deliver()
                self.restart()
                original = self.server.call_tool
                def call(name, args=None):
                    if name in ("spawn_upload_text", "spawn_prepare_upload"):
                        raise SpawnError("ARTIFACT_LEASE_STALE")
                    return original(name, args)
                self.server.call_tool = call
                with self.assertRaises(SpawnError):
                    self.deliver()
                self.restart()
                self.jobs.finish("abandon", {"job_id": "job-123", "reason": "Stop after expired upload"},
                                 "chat", load("envelopes").terms(self.server.job))
                self.assertEqual("cancelled", self.server.job["state"]["execution"])
                self.assertEqual(1, sum(name == "spawn_abandon_job" for name, _ in self.server.calls))
                self.assertFalse(any(name in ("spawn_resume_job", "spawn_submit_result") for name, _ in self.server.calls))
                self.assertTrue(self.server.uploads)

    def test_unproven_expiry_or_other_retry_errors_keep_exact_batch(self):
        for route in ("text", "game", "files"):
            for code, uncertain in (("ARTIFACT_LEASE_STALE", True), ("UPLOAD_EXPIRED", True),
                                    ("transport_error", True), ("INVALID_ARGUMENTS", False)):
                with self.subTest(route=route, code=code, uncertain=uncertain):
                    self.setup_route(route)
                    self.server.fail_once["spawn_finalize_manifest"] = SpawnError("transport_error", uncertain=True)
                    with self.assertRaises(SpawnError):
                        self.deliver()
                    kind = "pending_" + {"text": "text", "game": "package", "files": "files"}[route]
                    pending = self.jobs.state.get(kind, "job-123")
                    self.restart()
                    original = self.server.call_tool
                    def call(name, args=None):
                        if name in ("spawn_upload_text", "spawn_prepare_upload"):
                            raise SpawnError(code, uncertain=uncertain)
                        return original(name, args)
                    self.server.call_tool = call
                    with self.assertRaises(SpawnError) as failed:
                        self.deliver()
                    self.assertEqual(code, failed.exception.code)
                    self.assertNotIn("batch_recovery_released", failed.exception.details)
                    self.assertEqual(pending, self.jobs.state.get(kind, "job-123"))
                    with self.assertRaises(SpawnError) as blocked:
                        self.jobs.progress({"job_id": "job-123", "message": "Continue", "waiting_for_input": False}, "chat")
                    self.assertEqual("pending_outcome", blocked.exception.code)
                    with self.assertRaises(SpawnError) as blocked:
                        self.jobs.finish("abandon", {"job_id": "job-123", "reason": "Stop"},
                                         "chat", load("envelopes").terms(self.server.job))
                    self.assertEqual("pending_outcome", blocked.exception.code)
                    self.server.call_tool = original
                    self.restart()
                    self.deliver()
                    finalized = [args for name, args in self.server.calls if name == "spawn_finalize_manifest"]
                    self.assertEqual(finalized[0], finalized[1])
                    self.assertEqual(1, len(self.server.uploads))
