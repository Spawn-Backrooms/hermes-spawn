"""Exact artifact authority and canonical manifests at the server boundary."""
from .envelopes import digest, hash_value, identifier
from .spawn_client import SpawnError


def release_failed_delivery(state, kind, job_id, error, *, recovering):
    """Release unusable artifact recovery without resolving an uncertain write."""
    expired = not error.uncertain and error.code in {
        "LEASE_EXPIRED", "ARTIFACT_LEASE_STALE", "LEASE_GENERATION_STALE", "UPLOAD_EXPIRED"}
    if expired or (not error.uncertain and not recovering):
        state.set(kind, job_id, None)
    if expired:
        error.details.update(batch_recovery_released=True,
            next_step="Read spawn_job, then explicitly resume with spawn_progress or abandon. An expired upload cannot be reused; no result was submitted.")


def verify_upload(upload, job, descriptor, upload_id=None, *, verified=False):
    if (not isinstance(upload, dict) or upload.get("job_id") != job["job_id"] or
        upload.get("installation_id") != job["installation_id"] or type(upload.get("grant_epoch")) is not int or upload.get("grant_epoch") != job["grant_epoch"] or
        type(upload.get("lease_generation")) is not int or upload.get("lease_generation") != job["lease_generation"] or digest(upload.get("descriptor")) != digest(descriptor) or
        (upload_id is not None and upload.get("upload_id") != upload_id) or
        (verified and upload.get("state") != "verified")):
        raise SpawnError("upload_authority_mismatch", "SPAWN did not confirm this exact file, job, grant and lease.", uncertain=True)
    try:
        return identifier(upload.get("upload_id"))
    except SpawnError:
        raise SpawnError("upload_authority_mismatch", "SPAWN returned an invalid upload identity.", uncertain=True) from None


def verify_manifest(result, job, artifacts):
    """Verify the returned content as well as its claimed hash, not just a hash-shaped string."""
    try:
        value = result["manifest"]
        claimed = hash_value(result["manifest_hash"])
        # Keep the server's array order for canonical hashing; compare identity
        # separately because localeCompare ordering is owned by the server.
        expected = {"version": 1, "job_id": job["job_id"], "installation_id": job["installation_id"],
                    "grant_epoch": job["grant_epoch"], "lease_generation": job["lease_generation"],
                    "provenance_kind": "external_executor", "artifacts": value["artifacts"]}
        if (digest(value) != digest(expected) or not isinstance(value["artifacts"], list) or
            digest(sorted(value["artifacts"], key=lambda x: x["upload_id"])) != digest(sorted(artifacts, key=lambda x: x["upload_id"])) or
            digest(value) != claimed):
            raise ValueError("manifest mismatch")
        return claimed
    except (KeyError, TypeError, ValueError, SpawnError):
        raise SpawnError("manifest_unverified", "SPAWN did not confirm the exact file manifest. Retry these same files.", uncertain=True) from None
