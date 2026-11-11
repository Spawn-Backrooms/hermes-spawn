import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tests.support import load
from tests.fake_proposals import ProposalServer, MemoryBackend, SpawnError
from tests.test_client import ScriptedRequest, Response

Jobs = load("jobs").Jobs
Hooks = load("hooks").Hooks
Tools = load("tools").Tools
State = load("state").State
SpawnClient = load("spawn_client").SpawnClient
MIME = "application/vnd.spawn.game-package+zip"


def archive(files=None, compression=zipfile.ZIP_STORED):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=compression, allowZip64=False) as package:
        for name, content in (files or {"index.html": "<!doctype html><canvas></canvas>", "main.js": "console.log('game');", "README.md": "Arrow keys"}).items():
            package.writestr(name, content)
    return out.getvalue()


class PackageServer(ProposalServer):
    def __init__(self):
        super().__init__()
        self.job["state"]["execution"] = "running"
        self.uploads = {}
        self.uploaded = []
        self.prepare_corruption = None

    def call_tool(self, name, arguments=None):
        args = copy.deepcopy(arguments or {})
        if name == "spawn_prepare_upload":
            self.calls.append((name, args))
            upload_id = "upload_" + args["key"][-32:]
            self.uploads.setdefault(upload_id, {"upload_id": upload_id, "job_id": self.job["job_id"],
                "installation_id": self.job["installation_id"], "grant_epoch": self.job["grant_epoch"],
                "lease_generation": args["generation"], "descriptor": copy.deepcopy(args["descriptor"]),
                "expires_at_ms": 4000000000000, "state": "pending"})
            result = copy.deepcopy(self.uploads[upload_id])
            if self.prepare_corruption:
                result[self.prepare_corruption] = "wrong" if self.prepare_corruption == "installation_id" else 999
            return result
        return super().call_tool(name, args)

    def upload_game_package(self, upload_id, raw):
        self.uploaded.append((upload_id, raw))
        record = self.uploads[upload_id]
        assert record["descriptor"]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert record["descriptor"]["size_bytes"] == len(raw)
        record["state"] = "verified"
        if "upload_game_package" in self.fail_once:
            raise self.fail_once.pop("upload_game_package")
        return copy.deepcopy(record)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = archive()
        (self.root / "game.zip").write_bytes(self.raw)
        self.server = PackageServer()
        self.backend = MemoryBackend()
        self.restart()

    def restart(self):
        self.jobs = Jobs(client=self.server, state=State(backend=self.backend), cwd=self.root)
        self.hooks = Hooks(self.jobs)
        self.tools = Tools(self.jobs, self.hooks)
        self.jobs.snapshot("job-123")
        self.jobs.remember_active("chat", self.server.job)

    def run_tool(self, name, args, conversation="chat"):
        return json.loads(self.tools.handler(name)(args, conversation_id=conversation))

    def deliver(self):
        return self.run_tool("spawn_deliver_game_package", {"job_id": "job-123", "path": "game.zip"})

    def test_typed_package_uploads_exact_bytes_and_uses_existing_submission(self):
        result = self.deliver()
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["submitted"])
        self.assertEqual(self.raw, self.server.uploaded[0][1])
        prepared = next(args for name, args in self.server.calls if name == "spawn_prepare_upload")
        self.assertEqual(MIME, prepared["descriptor"]["media_type"])
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), prepared["descriptor"]["sha256"])
        self.assertEqual(len(self.raw), prepared["descriptor"]["size_bytes"])
        args = {"job_id": "job-123", "manifest_hash": result["manifest_hash"]}
        gate = self.hooks.pre_tool_call("spawn_submit", args, conversation_id="chat")
        self.assertEqual("approve", gate["action"])
        submitted = self.run_tool("spawn_submit", args)
        self.assertTrue(submitted["ok"], submitted)
        self.assertEqual("submitted", self.server.job["state"]["execution"])

    def test_unsafe_or_unsupported_zip_is_refused_before_reservation(self):
        for raw in (b"not a zip", archive(compression=zipfile.ZIP_DEFLATED),
                    archive({"../index.html": "bad"}), archive({"readme.md": "missing root"}),
                    archive({"index.html": "ok", "INDEX.HTML": "duplicate"}),
                    archive({"index.html": "ok", "auth.json": "{bad"})):
            (self.root / "game.zip").write_bytes(raw)
            result = self.deliver()
            self.assertEqual("invalid_game_package", result.get("error"), result)
        self.assertEqual({}, self.server.uploads)

    def test_archive_symlink_and_traversal_are_refused(self):
        (self.root / "linked.zip").symlink_to(self.root / "game.zip")
        for path in ("linked.zip", "../game.zip", str(self.root / "game.zip")):
            result = self.run_tool("spawn_deliver_game_package", {"job_id": "job-123", "path": path})
            self.assertEqual("unsafe_path", result.get("error"), result)
        self.assertEqual({}, self.server.uploads)

    def test_wrong_upload_authority_never_transfers_bytes(self):
        for field in ("installation_id", "lease_generation", "grant_epoch"):
            with self.subTest(field=field):
                self.server.prepare_corruption = field
                result = self.deliver()
                self.assertEqual("upload_authority_mismatch", result.get("error"), result)
                self.assertEqual([], self.server.uploaded)

    def test_lost_upload_response_retries_same_file_and_reservation_after_restart(self):
        self.server.fail_once["upload_game_package"] = SpawnError("transport_error", uncertain=True)
        first = self.deliver()
        self.assertTrue(first.get("outcome_uncertain"), first)
        self.restart()
        result = self.deliver()
        self.assertTrue(result["ok"], result)
        self.assertEqual(1, len(self.server.uploads))
        self.assertEqual(self.server.uploaded[0], self.server.uploaded[1])

    def test_uncertain_package_blocks_changed_bytes_and_other_parent_mutations(self):
        self.server.fail_once["upload_game_package"] = SpawnError("transport_error", uncertain=True)
        self.deliver()
        (self.root / "game.zip").write_bytes(archive({"index.html": "changed"}))
        changed = self.deliver()
        self.assertEqual("pending_outcome", changed.get("error"), changed)
        progress = self.run_tool("spawn_progress", {"job_id": "job-123", "message": "Continue", "waiting_for_input": False})
        self.assertEqual("pending_outcome", progress.get("error"), progress)


class PackageTransportTests(unittest.TestCase):
    def test_bridge_uses_native_json_auth_and_exact_bytes_on_fixed_origin(self):
        raw = archive()
        request = ScriptedRequest(Response({"data": {"upload_id": "upload_123", "state": "verified"}}))
        client = SpawnClient(request)
        self.assertTrue(callable(getattr(client, "upload_game_package", None)), "Native game package JSON bridge is missing")
        result = client.upload_game_package("upload_123", raw)
        self.assertEqual("verified", result["state"])
        args, kwargs = request.calls[0]
        self.assertEqual(("spawn", "PUT", "https://spawnbackrooms.com/api/v1/external-work/uploads/upload_123/game-package"), args)
        self.assertEqual({"content_base64": base64.b64encode(raw).decode("ascii")}, kwargs["json"])
        self.assertEqual("application/json", kwargs["headers"]["Content-Type"])
        self.assertNotIn("Authorization", kwargs["headers"])

    def test_bridge_rejects_redirects_and_unbounded_bytes(self):
        request = ScriptedRequest(Response(status=302, text="secret redirect"))
        client = SpawnClient(request)
        self.assertTrue(callable(getattr(client, "upload_game_package", None)), "Native game package JSON bridge is missing")
        with self.assertRaises(SpawnError) as caught:
            client.upload_game_package("upload_123", archive())
        self.assertEqual("redirect_refused", caught.exception.code)
        for identifier, raw in (("../x", archive()), ("upload_123", b"x" * (2 * 1024 * 1024 + 1))):
            with self.assertRaises(SpawnError):
                client.upload_game_package(identifier, raw)
        self.assertEqual(1, len(request.calls))


if __name__ == "__main__":
    unittest.main()
