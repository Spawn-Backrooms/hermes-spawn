"""Opaque file delivery: bounded bytes, immutable fences, exact retry recovery."""
import hashlib

from .envelopes import digest, hash_value, identifier, integer, stable_key, terms
from .files import read_workspace_bytes
from .schemas import DELIVERY_FILE, FILE, validate
from .spawn_client import SpawnError


class FileDelivery:
    def __init__(self, jobs):
        self.jobs, self.state = jobs, jobs.state

    @staticmethod
    def _upload_record(upload, job, descriptor, upload_id=None, *, verified=False):
        if (not isinstance(upload, dict) or upload.get("job_id") != job["job_id"] or
            upload.get("installation_id") != job["installation_id"] or upload.get("grant_epoch") != job["grant_epoch"] or
            upload.get("lease_generation") != job["lease_generation"] or upload.get("descriptor") != descriptor or
            (upload_id is not None and upload.get("upload_id") != upload_id) or
            (verified and upload.get("state") != "verified")):
            raise SpawnError("upload_authority_mismatch", "SPAWN did not confirm this exact file, job, grant and lease.", uncertain=True)
        try:
            return identifier(upload.get("upload_id"))
        except SpawnError:
            raise SpawnError("upload_authority_mismatch", "SPAWN returned an invalid upload identity.", uncertain=True) from None

    @staticmethod
    def _manifest(result, job, artifacts):
        """Verify the returned content as well as its claimed hash, not just a hash-shaped string."""
        try:
            value = result["manifest"]
            claimed = hash_value(result["manifest_hash"])
            # Keep the server's array order for canonical hashing; compare identity
            # separately because localeCompare ordering is owned by the server.
            expected = {"version": 1, "job_id": job["job_id"], "installation_id": job["installation_id"],
                        "grant_epoch": job["grant_epoch"], "lease_generation": job["lease_generation"],
                        "provenance_kind": "external_executor", "artifacts": value["artifacts"]}
            if (value != expected or not isinstance(value["artifacts"], list) or
                sorted(value["artifacts"], key=lambda x: x["upload_id"]) != sorted(artifacts, key=lambda x: x["upload_id"]) or
                digest(value) != claimed):
                raise ValueError("manifest mismatch")
            return claimed
        except (KeyError, TypeError, ValueError, SpawnError):
            raise SpawnError("manifest_unverified", "SPAWN did not confirm the exact file manifest. Retry these same files.", uncertain=True) from None

    def _current(self, job_id, conversation, pins):
        job = self.jobs.snapshot(job_id)
        self.jobs.require_active(conversation, job)
        if {"terms": terms(job), "generation": job["lease_generation"]} != pins:
            raise SpawnError("authority_changed", "The job or lease changed during file delivery. Inspect the parent job.")
        return job

    def deliver(self, args, conversation):
        cwd = self.jobs.cwd
        if cwd is None:
            from agent.runtime_cwd import resolve_agent_cwd
            cwd = resolve_agent_cwd()
        # Preflight every file before any reservation or transfer. Retain only
        # descriptors, then re-read and compare before each bounded upload.
        descriptors = []
        for item in args["files"]:
            validate(item, DELIVERY_FILE)
            filename, raw = read_workspace_bytes(cwd, item["path"])
            name = item.get("name", filename)
            validate(name, FILE["properties"]["name"])
            descriptor = {"name": name, "media_type": "application/octet-stream",
                          "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            if "media_type" in item:
                descriptor["declared_media_type"] = item["media_type"]
            descriptors.append(descriptor)
            del raw
        if not 1 <= len(descriptors) <= 10:
            raise SpawnError("invalid_arguments", "Deliver 1-10 files per manifest.")
        if len({d["name"].casefold() for d in descriptors}) != len(descriptors):
            raise SpawnError("duplicate_file", "Use distinct filenames, including letter case, for every deliverable.")
        job_id = args["job_id"]
        with self.state.for_job(job_id):
            job = self.jobs.snapshot(job_id)
            self.jobs.require_active(conversation, job)
            if any(self.state.get(kind, job_id) for kind in ("pending", "pending_children", "pending_package")):
                raise SpawnError("pending_outcome", "Resolve the pending parent, child or game-package action before file delivery.")
            generation = integer(job["lease_generation"])
            pins = {"terms": terms(job), "generation": generation}
            intent = digest(descriptors)
            pending = self.state.get("pending_files", job_id)
            if pending and (pending["conversation"] != conversation or pending["intent"] != intent):
                raise SpawnError("pending_outcome", "Retry the same filenames, bytes and metadata from the original conversation first.")
            if pending and pending["pins"] != pins:
                raise SpawnError("authority_changed", "File delivery authority changed while unresolved. Inspect the parent job.")
            recovering = pending is not None
            if not pending:
                pending = {"conversation": conversation, "intent": intent, "pins": pins,
                           "arguments": [{"job_id": job_id, "generation": generation,
                                          "key": stable_key(job["installation_id"], job_id, "file", generation, d),
                                          "descriptor": d} for d in descriptors]}
                self.state.set("pending_files", job_id, pending)
            artifacts = []
            try:
                for item, arguments in zip(args["files"], pending["arguments"]):
                    descriptor = arguments["descriptor"]
                    _, raw = read_workspace_bytes(cwd, item["path"])
                    if len(raw) != descriptor["size_bytes"] or hashlib.sha256(raw).hexdigest() != descriptor["sha256"]:
                        raise SpawnError("file_changed", "A file changed after preflight. Retry the original file bytes.")
                    current = self._current(job_id, conversation, pins)
                    prepared = self.jobs.client.call_tool("spawn_prepare_upload", arguments)
                    upload_id = self._upload_record(prepared, current, descriptor)
                    self._current(job_id, conversation, pins)
                    uploaded = self.jobs.client.upload_file(upload_id, raw)
                    del raw
                    self._upload_record(uploaded, current, descriptor, upload_id, verified=True)
                    artifacts.append({"upload_id": upload_id, "descriptor": descriptor})
                uploads = [item["upload_id"] for item in artifacts]
                if len(set(uploads)) != len(uploads):
                    raise SpawnError("upload_authority_mismatch", "SPAWN reused a file upload identity.", uncertain=True)
                self._current(job_id, conversation, pins)
                result = self.jobs.client.call_tool("spawn_finalize_manifest", {"job_id": job_id, "generation": generation, "upload_ids": uploads})
                manifest_hash = self._manifest(result, job, artifacts)
                self._current(job_id, conversation, pins)
            except SpawnError as exc:
                # A definitive response can be retried using descriptor-derived
                # keys. Ambiguous writes retain the exact batch across restarts.
                expired = not exc.uncertain and exc.code in {
                    "LEASE_EXPIRED", "ARTIFACT_LEASE_STALE", "LEASE_GENERATION_STALE", "UPLOAD_EXPIRED"}
                if expired or (not exc.uncertain and not recovering):
                    self.state.set("pending_files", job_id, None)
                if expired:
                    # Only artifact reservations are released locally. They never
                    # submitted a result or spent funds; server bytes remain fenced.
                    exc.details.update(batch_recovery_released=True,
                        next_step="Read spawn_job, then explicitly resume with spawn_progress or abandon. An expired upload cannot be reused; no result was submitted.")
                raise
            self.state.set("delivery", [conversation, job_id, manifest_hash], {
                "manifest_hash": manifest_hash, "upload_ids": uploads, "lease_generation": generation,
                "terms": terms(job), "files": descriptors})
            self.state.set("pending_files", job_id, None)
            return {"manifest_hash": manifest_hash, "upload_ids": uploads, "files": descriptors,
                    "submitted": False, "notice": "Verified download-only files. No preview, execution or malware-safety claim. Submit separately for customer review."}
