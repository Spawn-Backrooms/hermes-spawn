"""Stateful offline server seam with immutable pins and deduplicated receipts."""
import copy
import hashlib

from tests.support import load

SpawnError = load("spawn_client").SpawnError


def job_snapshot():
    return {"job_id": "job-123", "installation_id": "install_7", "order_hash": "a" * 64, "quote_hash": "b" * 64,
            "revision": 17, "grant_epoch": 4, "lease_generation": 8, "lease_expires_at_ms": 4000000000000,
            "state": {"execution": "offered"},
            "quote": {"offer_revision": 9, "input_manifest_hashes": [], "deliverable": "Review", "deadline_at_ms": 4000001000000}}


class FakeSpawn:
    def __init__(self):
        self.job = job_snapshot()
        self.calls = []
        self.receipts = {}
        self.fail_once = {}
        self.corrupt_upload = False
        self.uploads = {}

    def call_tool(self, name, arguments=None):
        args = copy.deepcopy(arguments or {})
        self.calls.append((name, args))
        if name == "spawn_get_job":
            return copy.deepcopy(self.job)
        if name == "spawn_identity":
            return {"installation_id": self.job["installation_id"]}
        if name == "spawn_upload_text":
            raw = args["text"].encode("utf-8")
            upload_id = "upload_" + args["key"][-12:]
            record = {"upload_id": upload_id, "job_id": self.job["job_id"],
                      "installation_id": self.job["installation_id"], "grant_epoch": self.job["grant_epoch"],
                      "lease_generation": args["generation"], "state": "verified",
                      "descriptor": {"name": args["name"], "media_type": args["media_type"],
                                     "sha256": "0" * 64 if self.corrupt_upload else hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}}
            self.uploads.setdefault(upload_id, record)
            if name in self.fail_once:
                raise self.fail_once.pop(name)
            return copy.deepcopy(self.uploads[upload_id])
        if name == "spawn_finalize_manifest":
            value = {"version": 1, "job_id": self.job["job_id"], "installation_id": self.job["installation_id"],
                     "grant_epoch": self.job["grant_epoch"], "lease_generation": self.job["lease_generation"],
                     "provenance_kind": "external_executor", "artifacts": [
                         {"upload_id": i, "descriptor": copy.deepcopy(self.uploads[i]["descriptor"])} for i in args["upload_ids"]]}
            if name in self.fail_once:
                raise self.fail_once.pop(name)
            return {"manifest_hash": load("envelopes").digest(value), "manifest": value}
        if name in {"spawn_create_room", "spawn_declare_capabilities"}:
            return {"ok": True}
        if "envelope" not in args:
            raise AssertionError("Unimplemented fake call: " + name)
        envelope = args["envelope"]
        key = envelope["idempotency_key"]
        if key in self.receipts:
            return copy.deepcopy(self.receipts[key])
        assert envelope["expected_revision"] == self.job["revision"], "Stale revision sent for a new operation"
        assert envelope["order_hash"] == self.job["order_hash"]
        assert envelope["quote_hash"] == self.job["quote_hash"]
        assert envelope["input_manifest_hashes"] == self.job["quote"]["input_manifest_hashes"]
        self.job["revision"] += 1
        if name == "spawn_accept_job":
            self.job["lease_generation"] += 1
            self.job["state"]["execution"] = "running"
        if name == "spawn_resume_job":
            self.job["lease_generation"] += 1
        if name == "spawn_submit_result":
            self.job["state"]["execution"] = "submitted"
        if name == "spawn_abandon_job":
            self.job["state"]["execution"] = "cancelled"
        result = {"receipt_id": "receipt_" + key[-12:], "revision": self.job["revision"]}
        self.receipts[key] = copy.deepcopy(result)
        if name in self.fail_once:
            raise self.fail_once.pop(name)
        return result

    def mutations(self):
        return [(name, args) for name, args in self.calls if name != "spawn_get_job" and name != "spawn_identity"]
