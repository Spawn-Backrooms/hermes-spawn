import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.support import load
from tests.test_packages import PackageServer
from tests.fake_proposals import MemoryBackend, SpawnError
from tests.test_client import ScriptedRequest, Response

Jobs, State, Hooks, Tools = (load(n).__dict__[c] for n, c in (("jobs", "Jobs"), ("state", "State"), ("hooks", "Hooks"), ("tools", "Tools")))
SpawnClient = load("spawn_client").SpawnClient
files = load("files")
digest = load("envelopes").digest


class FileServer(PackageServer):
    def __init__(self):
        super().__init__()
        self.manifest_corruption = None
        self.after_prepare = None
        self.upload_corruption = None
        self.finalize_count = 0

    def call_tool(self, name, arguments=None):
        if name in {"spawn_prepare_upload", "spawn_heartbeat"} and name in self.fail_once:
            raise self.fail_once.pop(name)
        if name == "spawn_finalize_manifest":
            self.calls.append((name, copy.deepcopy(arguments)))
            self.finalize_count += 1
            value = {"version": 1, "job_id": self.job["job_id"], "installation_id": self.job["installation_id"],
                     "grant_epoch": self.job["grant_epoch"], "lease_generation": self.job["lease_generation"],
                     "provenance_kind": "external_executor", "artifacts": [
                         {"upload_id": i, "descriptor": copy.deepcopy(self.uploads[i]["descriptor"])} for i in arguments["upload_ids"]]}
            result = {"manifest": value, "manifest_hash": digest(value)}
            if self.manifest_corruption:
                self.manifest_corruption(result)
            if name in self.fail_once:
                raise self.fail_once.pop(name)
            return result
        result = super().call_tool(name, arguments)
        if name == "spawn_prepare_upload" and self.after_prepare:
            self.after_prepare()
        return result

    def upload_file(self, upload_id, raw):
        result = super().upload_game_package(upload_id, raw)
        if self.upload_corruption:
            self.upload_corruption(result)
        return result


class FileDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server = FileServer()
        self.backend = MemoryBackend()
        self.restart()

    def restart(self):
        self.jobs = Jobs(client=self.server, state=State(backend=self.backend), cwd=self.root)
        self.hooks = Hooks(self.jobs)
        self.tools = Tools(self.jobs, self.hooks)
        self.jobs.snapshot("job-123")
        self.jobs.remember_active("chat", self.server.job)

    def tool(self, name, args, conversation="chat"):
        return json.loads(self.tools.handler(name)(args, conversation_id=conversation))

    def deliver(self, *items, conversation="chat"):
        return self.tool("spawn_deliver_files", {"job_id": "job-123", "files": list(items or [{"path": "output.bin"}])}, conversation)

    def test_any_format_exact_bytes_metadata_manifest_and_approved_submission(self):
        values = {"art.png": b"\x89PNG\x00\xff", "audio.mp3": b"ID3\x00\xf0", "report.pdf": b"%PDF\x00\xfa",
                  "model.blend": b"\x00\xffBLENDER", "index.html": b"<script>not run</script>",
                  "video.mov": bytes(range(256)), "source.docx": b"PK\x00\xff", "bundle.zip": b"opaque zipped bytes",
                  "source.js": b"alert('no execution')", "unknown.future": b"\x00\x01\x02"}
        for name, raw in values.items():
            (self.root / name).write_bytes(raw)
        result = self.deliver(*[{"path": name, "media_type": "application/x-example"} for name in values])
        self.assertTrue(result.get("ok"), result)
        self.assertFalse(result["submitted"])
        self.assertEqual(list(values.values()), [raw for _, raw in self.server.uploaded])
        self.assertTrue(all(d["media_type"] == "application/octet-stream" and d["declared_media_type"] == "application/x-example" for d in result["files"]))
        args = {"job_id": "job-123", "manifest_hash": result["manifest_hash"]}
        self.assertEqual("approval_preflight_required", self.tool("spawn_submit", args)["error"])
        self.assertEqual("approve", self.hooks.pre_tool_call("spawn_submit", args, conversation_id="chat")["action"])
        self.assertTrue(self.tool("spawn_submit", args)["ok"])

    def test_invalid_later_file_prevents_all_reservations(self):
        (self.root / "valid").write_bytes(b"fine")
        result = self.deliver({"path": "valid"}, {"path": "absent"})
        self.assertEqual("unsafe_path", result["error"])
        self.assertEqual({}, self.server.uploads)

    def test_names_mime_and_count_are_validated_before_network(self):
        (self.root / "output.bin").write_bytes(b"x")
        cases = [[], [{"path": "output.bin"}] * 11,
                 [{"path": "output.bin", "name": "../evil"}],
                 [{"path": "output.bin", "name": "bad\nname"}],
                 [{"path": "output.bin", "media_type": "text/html; charset=utf-8"}],
                 [{"path": "output.bin", "media_type": "Text/Html"}],
                 [{"path": "output.bin", "url": "https://example.com"}]]
        for items in cases:
            result = self.tool("spawn_deliver_files", {"job_id": "job-123", "files": items})
            self.assertEqual("invalid_arguments", result["error"], result)
        result = self.deliver({"path": "output.bin", "name": "OUT.bin"}, {"path": "output.bin", "name": "out.bin"})
        self.assertEqual("duplicate_file", result["error"])
        self.assertEqual({}, self.server.uploads)

    def test_limits_are_inclusive_and_oversize_or_empty_are_refused(self):
        for size in (0, files.MAX_FILE_BYTES + 1):
            (self.root / "output.bin").write_bytes(b"x" * size)
            self.assertEqual("file_too_large", self.deliver()["error"])
        (self.root / "output.bin").write_bytes(b"x" * files.MAX_FILE_BYTES)
        self.assertTrue(self.deliver()["ok"])

    def test_relative_named_files_only_and_no_credentials_symlinks_or_devices(self):
        (self.root / "output.bin").write_bytes(b"x")
        (self.root / "link").symlink_to(self.root / "output.bin")
        (self.root / "linked-dir").symlink_to(self.root, target_is_directory=True)
        for name in (".env", "auth.json", "credentials.json", "id_rsa"):
            (self.root / name).write_bytes(b"secret")
        for path in ("../output.bin", str(self.root / "output.bin"), ".env", "auth.json", "credentials.json",
                     "id_rsa", "link", "linked-dir/output.bin", "bad\\name", "."):
            result = self.deliver({"path": path})
            self.assertIn(result.get("error"), {"unsafe_path", "unsafe_file"}, result)
        import os
        os.mkfifo(self.root / "pipe")
        self.assertEqual("unsafe_file", self.deliver({"path": "pipe"})["error"])
        self.assertEqual({}, self.server.uploads)

    def test_active_job_conversation_and_lease_are_required(self):
        (self.root / "output.bin").write_bytes(b"x")
        self.assertEqual("not_active_here", self.deliver(conversation="other")["error"])
        self.jobs.state.set("job_owner", "job-123", "chat")
        self.assertEqual("active_elsewhere", self.deliver(conversation="other")["error"])
        self.server.job["lease_generation"] += 1
        self.assertEqual("lease_changed", self.deliver()["error"])
        self.assertEqual({}, self.server.uploads)

    def test_no_transfer_on_corrupt_reservation_or_changed_authority(self):
        (self.root / "output.bin").write_bytes(b"x")
        self.server.prepare_corruption = "grant_epoch"
        self.assertEqual("upload_authority_mismatch", self.deliver()["error"])
        self.assertEqual([], self.server.uploaded)
        self.server.prepare_corruption = None
        self.server.after_prepare = lambda: self.server.job.update(grant_epoch=99)
        self.assertEqual("authority_changed", self.deliver()["error"])
        self.assertEqual([], self.server.uploaded)

    def test_wrong_upload_bytes_or_identity_never_finalizes(self):
        (self.root / "output.bin").write_bytes(b"x")
        self.server.upload_corruption = lambda r: r["descriptor"].update(sha256="0" * 64)
        result = self.deliver()
        self.assertEqual("upload_authority_mismatch", result["error"])
        self.assertEqual(0, self.server.finalize_count)

    def test_manifest_must_bind_exact_files_fence_and_hash(self):
        (self.root / "output.bin").write_bytes(b"x")
        cases = [lambda r: r.update(manifest_hash="0" * 64),
                 lambda r: r["manifest"].update(job_id="wrong"),
                 lambda r: r["manifest"].update(artifacts=[]),
                 lambda r: r["manifest"].update(lease_generation=999),
                 lambda r: r["manifest"]["artifacts"][0]["descriptor"].update(name="other")]
        for corrupt in cases:
            self.server.manifest_corruption = corrupt
            result = self.deliver()
            self.assertEqual("manifest_unverified", result["error"], result)
            self.assertTrue(result["outcome_uncertain"])
        self.server.manifest_corruption = None
        self.assertTrue(self.deliver()["ok"])
        self.assertEqual(1, len(self.server.uploads))

    def test_lost_upload_or_finalize_response_reuses_batch_across_restart(self):
        (self.root / "output.bin").write_bytes(b"abc\x00")
        for action in ("upload_game_package", "spawn_finalize_manifest"):
            self.server.fail_once[action] = SpawnError("transport_error", uncertain=True)
            self.assertTrue(self.deliver()["outcome_uncertain"])
            self.restart()
            self.assertTrue(self.deliver()["ok"])
        self.assertEqual(1, len(self.server.uploads))
        self.assertTrue(all(raw == b"abc\x00" for _, raw in self.server.uploaded))

    def test_unresolved_batch_blocks_changed_bytes_metadata_and_all_other_mutations(self):
        (self.root / "output.bin").write_bytes(b"abc")
        self.server.fail_once["upload_game_package"] = SpawnError("transport_error", uncertain=True)
        self.deliver()
        self.assertEqual("pending_outcome", self.deliver({"path": "output.bin", "media_type": "image/png"})["error"])
        (self.root / "output.bin").write_bytes(b"changed")
        self.assertEqual("pending_outcome", self.deliver()["error"])
        for name, args in (("spawn_progress", {"job_id": "job-123", "message": "next", "waiting_for_input": False}),
                           ("spawn_deliver_text", {"job_id": "job-123", "files": [{"name": "text", "media_type": "text/plain", "text": "a"}]})):
            self.assertEqual("pending_outcome", self.tool(name, args)["error"])
        self.assertIsNotNone(self.jobs.state.get("pending_files", "job-123"))

    def test_expired_uncertain_batch_releases_only_local_artifact_recovery(self):
        (self.root / "output.bin").write_bytes(b"abc")
        for error in ("LEASE_EXPIRED", "ARTIFACT_LEASE_STALE", "LEASE_GENERATION_STALE", "UPLOAD_EXPIRED"):
            self.server.fail_once["upload_game_package"] = SpawnError("transport_error", uncertain=True)
            self.assertTrue(self.deliver()["outcome_uncertain"])
            self.restart()
            self.server.fail_once["spawn_prepare_upload"] = SpawnError(error)
            result = self.deliver()
            self.assertEqual(error, result["error"])
            self.assertTrue(result["batch_recovery_released"])
            self.assertIsNone(self.jobs.state.get("pending_files", "job-123"))
            self.assertEqual("running", self.server.job["state"]["execution"])
            old_generation = self.server.job["lease_generation"]
            self.server.fail_once["spawn_heartbeat"] = SpawnError("LEASE_EXPIRED")
            result = self.tool("spawn_progress", {"job_id": "job-123", "message": "Resume", "waiting_for_input": False})
            self.assertTrue(result.get("ok"), result)
            self.assertEqual(old_generation + 1, self.server.job["lease_generation"])
            self.assertTrue(self.deliver()["ok"])
        self.assertFalse(any(name == "spawn_submit_result" for name, _ in self.server.calls))

    def test_other_pending_mutations_block_generic_files(self):
        (self.root / "output.bin").write_bytes(b"abc")
        for kind in ("pending", "pending_package", "pending_children"):
            self.jobs.state.set(kind, "job-123", {"unresolved": True})
            self.assertEqual("pending_outcome", self.deliver()["error"])
            self.jobs.state.set(kind, "job-123", None)
        self.assertEqual({}, self.server.uploads)

    def test_file_changed_between_preflight_and_transfer_never_uploads(self):
        (self.root / "output.bin").write_bytes(b"abc")
        target = load("file_delivery")
        with patch.object(target, "read_workspace_bytes", side_effect=[("output.bin", b"abc"), ("output.bin", b"bad")]):
            self.assertEqual("file_changed", self.deliver()["error"])
        self.assertEqual({}, self.server.uploads)

    def test_manifest_from_another_conversation_is_not_submittable(self):
        (self.root / "output.bin").write_bytes(b"abc")
        result = self.deliver()
        self.jobs.remember_active("other", self.server.job)
        args = {"job_id": "job-123", "manifest_hash": result["manifest_hash"]}
        self.hooks.pre_tool_call("spawn_submit", args, conversation_id="other")
        self.assertEqual("manifest_not_owned", self.tool("spawn_submit", args, conversation="other")["error"])


class FileTransportTests(unittest.TestCase):
    def test_exact_native_json_upload_fixed_route_no_tokens_or_content_echo(self):
        request = ScriptedRequest(Response({"data": {"upload_id": "upload_1", "state": "verified"}}))
        value = SpawnClient(request).upload_file("upload_1", b"\x00\xff\x80")
        self.assertEqual("verified", value["state"])
        args, kwargs = request.calls[0]
        self.assertEqual(("spawn", "PUT", "https://spawnbackrooms.com/api/v1/external-work/uploads/upload_1/file"), args)
        self.assertEqual({"content_base64": "AP+A"}, kwargs["json"])
        self.assertNotIn("Authorization", kwargs["headers"])

    def test_invalid_bound_ids_redirects_bad_response_and_ambiguity(self):
        for content in (b"", b"x" * (files.MAX_FILE_BYTES + 1), "not bytes"):
            request = ScriptedRequest()
            with self.assertRaises(SpawnError):
                SpawnClient(request).upload_file("upload_1", content)
            self.assertEqual([], request.calls)
        for response in (Response(status=302, text="secret"), Response(status=500, text="secret"), Response(text="not JSON")):
            with self.assertRaises(SpawnError) as exc:
                SpawnClient(ScriptedRequest(response)).upload_file("upload_1", b"x")
            self.assertTrue(exc.exception.uncertain)
            self.assertNotIn("secret", exc.exception.message)
        with self.assertRaises(SpawnError):
            SpawnClient(ScriptedRequest()).upload_file("../evil", b"x")


if __name__ == "__main__":
    unittest.main()
