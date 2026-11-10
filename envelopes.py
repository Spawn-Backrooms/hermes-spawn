"""Build exact job pins from SPAWN snapshots; never accept pins from the model."""
import hashlib
import json
import re

from .spawn_client import SpawnError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise SpawnError("invalid_id", "Expected a SPAWN identifier.")
    return value


def integer(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SpawnError("invalid_snapshot", "Missing or invalid server revision/lease information.")
    return value


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise SpawnError("invalid_snapshot", "Missing or invalid server hash.")
    return value


def stable_key(*parts):
    # Raw IDs may each be 128 characters; hashing keeps the server's 160-byte limit.
    return "hermes:" + digest(list(parts))


def terms(job):
    quote = job.get("quote", {})
    hashes = quote.get("input_manifest_hashes")
    if not isinstance(hashes, list) or len(hashes) > 10:
        raise SpawnError("invalid_snapshot", "Missing immutable input manifest hashes.")
    return {"job_id": identifier(job.get("job_id")), "installation_id": identifier(job.get("installation_id")),
            "order_hash": hash_value(job.get("order_hash")), "quote_hash": hash_value(job.get("quote_hash")),
            "input_manifest_hashes": [hash_value(h) for h in hashes], "grant_epoch": integer(job.get("grant_epoch"))}


def envelope(job, action, arguments=None):
    pins = terms(job)
    revision = integer(job.get("revision"))
    return {"idempotency_key": stable_key(pins["installation_id"], pins["job_id"], action, revision, arguments or {}),
            "expected_revision": revision, "order_hash": pins["order_hash"], "quote_hash": pins["quote_hash"],
            "input_manifest_hashes": pins["input_manifest_hashes"]}


def command_args(job, action, extras=None):
    extras = extras or {}
    allowed = {"accept": set(), "resume": set(), "heartbeat": set(), "progress": {"message", "waiting_for_input"}, "submit": {"manifest_hash", "upload_ids"}, "abandon": {"reason"}}
    if action not in allowed or not isinstance(extras, dict) or set(extras) - allowed[action]:
        raise SpawnError("invalid_command", "Command arguments cannot override authoritative job pins.")
    args = {"job_id": identifier(job.get("job_id")), "envelope": envelope(job, action, extras), **extras}
    if action == "accept":
        args.update(offer_revision=integer(job.get("quote", {}).get("offer_revision")), grant_epoch=integer(job.get("grant_epoch")))
    else:
        args["lease_generation"] = integer(job.get("lease_generation"))
        if action == "resume":
            args["grant_epoch"] = integer(job.get("grant_epoch"))
    return args
