"""Bounded local game archives delivered through the existing artifact authority."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import zipfile

from .envelopes import digest, hash_value, identifier, integer, stable_key, terms
from .spawn_client import SpawnError

GAME_PACKAGE_MEDIA_TYPE = "application/vnd.spawn.game-package+zip"
MAX_PACKAGE_BYTES = 2 * 1024 * 1024
EXTENSIONS = {".html", ".css", ".js", ".mjs", ".json", ".txt", ".md", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".wav", ".mp3", ".ogg"}
TEXT_EXTENSIONS = {".html", ".css", ".js", ".mjs", ".json", ".txt", ".md"}


def read_package(cwd, relative):
    path = Path(relative)
    if (path.is_absolute() or not path.parts or path.suffix.lower() != ".zip" or
        any(p in {"..", ".git", ".ssh", ".aws", ".codex", ".hermes", ".env"} or p.startswith(".env.") for p in path.parts)):
        raise SpawnError("unsafe_path", "Choose a workspace-relative .zip file without traversal or credential directories.")
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise SpawnError("safe_path_read_unavailable", "This platform cannot enforce no-symlink package reads.")
    descriptors = []
    try:
        current = os.open(Path(cwd).resolve(strict=True), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(current)
        for part in path.parts[:-1]:
            current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            descriptors.append(current)
        file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        descriptors.append(file_fd)
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_PACKAGE_BYTES:
            raise SpawnError("invalid_game_package", "The game archive must be a regular file of at most 2 MiB.")
        with os.fdopen(os.dup(file_fd), "rb") as stream:
            content = stream.read(MAX_PACKAGE_BYTES + 1)
        if not 0 < len(content) <= MAX_PACKAGE_BYTES:
            raise SpawnError("invalid_game_package", "The game archive exceeds 2 MiB.")
        return path.name, content
    except (OSError, ValueError):
        raise SpawnError("unsafe_path", "The game archive is not a regular file within the workspace; symlinks are refused.") from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def inspect_package(raw):
    """No extraction or execution. The server independently verifies the bytes."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            files = package.infolist()
            if not 1 <= len(files) <= 128 or package.comment or sum(f.file_size for f in files) > 4 * 1024 * 1024:
                raise ValueError("bounds")
            names, offset, central_size = set(), 0, 0
            for item in files:
                name = item.filename
                encoded = name.encode("ascii")
                parts = name.split("/")
                if (not 1 <= len(encoded) <= 160 or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", p) or p.endswith(".") or
                    re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", p.split(".")[0].upper()) for p in parts) or
                    name.casefold() in names or Path(name).suffix.lower() not in EXTENSIONS or item.is_dir() or
                    stat.S_IFMT(item.external_attr >> 16) not in {0, stat.S_IFREG} or
                    item.compress_type != zipfile.ZIP_STORED or item.flag_bits & ~0x800 or item.extra or item.comment or
                    item.file_size != item.compress_size or item.header_offset != offset):
                    raise ValueError("unsupported archive entry")
                header = struct.unpack_from("<IHHHHHIIIHH", raw, offset)
                if (header[0] != 0x04034B50 or header[2] != item.flag_bits or header[3] != 0 or
                    header[6] != item.CRC or header[7] != item.compress_size or header[8] != item.file_size or
                    header[9] != len(encoded) or header[10] != 0 or raw[offset + 30:offset + 30 + len(encoded)] != encoded):
                    raise ValueError("inconsistent entry")
                offset += 30 + len(encoded) + item.file_size
                central_size += 46 + len(encoded)
                names.add(name.casefold())
                content = package.read(item)
                if Path(name).suffix.lower() in TEXT_EXTENSIONS:
                    text = content.decode("utf-8")
                    if "\x00" in text:
                        raise ValueError("text NUL")
                    if Path(name).suffix.lower() == ".json":
                        json.loads(text)
            ending = struct.unpack_from("<IHHHHIIH", raw, len(raw) - 22)
            if ("index.html" not in {f.filename for f in files} or
                ending != (0x06054B50, 0, 0, len(files), len(files), central_size, offset, 0) or
                len(raw) != offset + central_size + 22):
                raise ValueError("noncanonical archive")
            return [f.filename for f in files]
    except (ValueError, UnicodeError, OSError, zipfile.BadZipFile, RuntimeError, struct.error):
        raise SpawnError("invalid_game_package", "Use a canonical ZIP_STORED archive with root index.html, at most 128 portable files, no symlinks or compression, and valid UTF-8/JSON source. The server verifies the archive again.") from None


class Packages:
    def __init__(self, jobs):
        self.jobs, self.state = jobs, jobs.state

    def _upload_record(self, upload, job, descriptor, upload_id=None, *, verified=False):
        if (not isinstance(upload, dict) or upload.get("job_id") != job["job_id"] or
            upload.get("installation_id") != job["installation_id"] or upload.get("grant_epoch") != job["grant_epoch"] or
            upload.get("lease_generation") != job["lease_generation"] or upload.get("descriptor") != descriptor or
            (upload_id and upload.get("upload_id") != upload_id) or (verified and upload.get("state") != "verified")):
            raise SpawnError("upload_authority_mismatch", "SPAWN did not return this exact package's job, grant, lease and hash. No manifest was submitted.", uncertain=True)
        try:
            return identifier(upload.get("upload_id"))
        except SpawnError:
            raise SpawnError("upload_authority_mismatch", "SPAWN returned an invalid package upload identity.", uncertain=True) from None

    def deliver(self, args, conversation):
        cwd = self.jobs.cwd
        if cwd is None:
            from agent.runtime_cwd import resolve_agent_cwd
            cwd = resolve_agent_cwd()
        name, raw = read_package(cwd, args["path"])
        filenames = inspect_package(raw)
        descriptor = {"name": name, "media_type": GAME_PACKAGE_MEDIA_TYPE, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        job_id = args["job_id"]
        with self.state.for_job(job_id):
            job = self.jobs.snapshot(job_id)
            self.jobs.require_active(conversation, job)
            if self.state.get("pending", job_id) or self.state.get("pending_children", job_id):
                raise SpawnError("pending_outcome", "Resolve the pending parent or child action before uploading a package.")
            generation = integer(job["lease_generation"])
            pins = {"terms": terms(job), "generation": generation}
            intent = digest(descriptor)
            pending = self.state.get("pending_package", job_id)
            if pending and (pending["conversation"] != conversation or pending["intent"] != intent):
                raise SpawnError("pending_outcome", "Retry the same package bytes from the original conversation before uploading changed work.")
            if pending and pending["pins"] != pins:
                raise SpawnError("authority_changed", "Package upload authority changed while its outcome was unresolved. Inspect the parent job.")
            if not pending:
                key = stable_key(job["installation_id"], job_id, "game_package", generation, descriptor)
                pending = {"conversation": conversation, "intent": intent, "pins": pins,
                           "arguments": {"job_id": job_id, "generation": generation, "key": key, "descriptor": descriptor}}
                self.state.set("pending_package", job_id, pending)
            try:
                upload = self.jobs.client.call_tool("spawn_prepare_upload", pending["arguments"])
                upload_id = self._upload_record(upload, job, descriptor)
                current = self.jobs.snapshot(job_id)
                self.jobs.require_active(conversation, current)
                if {"terms": terms(current), "generation": current["lease_generation"]} != pins:
                    raise SpawnError("authority_changed", "The job or lease changed before package transfer.")
                uploaded = self.jobs.client.upload_game_package(upload_id, raw)
                self._upload_record(uploaded, current, descriptor, upload_id, verified=True)
                manifest = self.jobs.client.call_tool("spawn_finalize_manifest", {"job_id": job_id, "generation": generation, "upload_ids": [upload_id]})
                try:
                    manifest_hash = hash_value(manifest.get("manifest_hash"))
                except (SpawnError, AttributeError):
                    raise SpawnError("manifest_unverified", "SPAWN did not confirm the package manifest. Retry the same package.", uncertain=True) from None
            except SpawnError as exc:
                if not exc.uncertain:
                    self.state.set("pending_package", job_id, None)
                raise
            files = [{"name": name, "sha256": descriptor["sha256"], "size_bytes": len(raw)}]
            self.state.set("delivery", [conversation, job_id, manifest_hash], {"manifest_hash": manifest_hash,
                           "upload_ids": [upload_id], "lease_generation": generation, "terms": terms(job), "files": files})
            self.state.set("pending_package", job_id, None)
            return {"manifest_hash": manifest_hash, "upload_ids": [upload_id], "files": files,
                    "package_files": filenames, "submitted": False,
                    "notice": "Verified downloadable package. Submit separately for customer review; open the delivered download locally with networking disabled."}
