"""Opaque file delivery: bounded bytes, immutable fences, exact retry recovery."""
import hashlib

from .envelopes import digest, integer, stable_key, terms
from .artifacts import release_failed_delivery, verify_manifest, verify_upload
from .files import read_workspace_bytes
from .schemas import DELIVERY_FILE, FILE, validate
from .spawn_client import SpawnError


class FileDelivery:
    def __init__(self, jobs):
        self.jobs, self.state = jobs, jobs.state

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
            if any(self.state.get(kind, job_id) for kind in ("pending", "pending_children", "pending_package", "pending_text")):
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
                for index, (item, arguments) in enumerate(zip(args["files"], pending["arguments"])):
                    descriptor = arguments["descriptor"]
                    _, raw = read_workspace_bytes(cwd, item["path"])
                    if len(raw) != descriptor["size_bytes"] or hashlib.sha256(raw).hexdigest() != descriptor["sha256"]:
                        raise SpawnError("file_changed", "A file changed after preflight. Retry the original file bytes.")
                    current = self.jobs.delivery_snapshot(job_id, conversation, pins)
                    prepared = self.jobs.client.call_tool("spawn_prepare_upload", arguments)
                    known_ids = pending.setdefault("upload_ids", [])
                    upload_id = verify_upload(prepared, current, descriptor, known_ids[index] if index < len(known_ids) else None)
                    if index == len(known_ids):
                        known_ids.append(upload_id)
                        self.state.set("pending_files", job_id, pending)
                    self.jobs.delivery_snapshot(job_id, conversation, pins)
                    uploaded = self.jobs.client.upload_file(upload_id, raw)
                    del raw
                    verify_upload(uploaded, current, descriptor, upload_id, verified=True)
                    artifacts.append({"upload_id": upload_id, "descriptor": descriptor})
                uploads = [item["upload_id"] for item in artifacts]
                if len(set(uploads)) != len(uploads):
                    raise SpawnError("upload_authority_mismatch", "SPAWN reused a file upload identity.", uncertain=True)
                self.jobs.delivery_snapshot(job_id, conversation, pins)
                result = self.jobs.client.call_tool("spawn_finalize_manifest", {"job_id": job_id, "generation": generation, "upload_ids": uploads})
                manifest_hash = verify_manifest(result, job, artifacts)
                self.jobs.delivery_snapshot(job_id, conversation, pins)
            except SpawnError as exc:
                release_failed_delivery(self.state, "pending_files", job_id, exc, recovering=recovering)
                raise
            self.state.set("delivery", [conversation, job_id, manifest_hash], {
                "manifest_hash": manifest_hash, "upload_ids": uploads, "lease_generation": generation,
                "terms": terms(job), "files": descriptors})
            self.state.set("pending_files", job_id, None)
            return {"manifest_hash": manifest_hash, "upload_ids": uploads, "files": descriptors,
                    "submitted": False, "notice": "Verified download-only files. No preview, execution or malware-safety claim. Submit separately for customer review."}
