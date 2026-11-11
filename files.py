"""Read explicitly named regular files below the session working directory."""
import os
from pathlib import Path
import stat

from .spawn_client import SpawnError


def _workspace_path(relative):
    """Shared lexical guard; both readers still enforce no-follow handle walks."""
    path = Path(relative)
    blocked = {"..", ".git", ".ssh", ".aws", ".codex", ".hermes", ".gnupg", ".config"}
    if (not path.parts or path.is_absolute() or "\\" in str(relative) or "\x00" in str(relative) or
        any(part.casefold() in blocked or part.casefold() == ".env" or
            part.casefold().startswith(".env.") for part in path.parts) or
        path.name.casefold() in {"auth.json", "credentials", "credentials.json", "id_rsa", "id_ed25519"}):
        raise SpawnError("unsafe_path", "Choose an explicit workspace-relative file without traversal or credential paths.")
    return path


def read_workspace_text(cwd, relative):
    path = _workspace_path(relative)
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise SpawnError("safe_path_read_unavailable", "This platform cannot enforce no-symlink reads. Supply explicit text instead.")
    descriptors = []
    try:
        # Resolve the trusted session root once, then walk using directory handles.
        root = Path(cwd).resolve(strict=True)
        current = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(current)
        for part in path.parts[:-1]:
            current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            descriptors.append(current)
        file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        descriptors.append(file_fd)
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32768:
            raise SpawnError("unsafe_file", "Only regular, small UTF-8 text files can be delivered.")
        content = os.read(file_fd, 32769)
        if len(content) > 32768:
            raise SpawnError("file_too_large", "Text exceeds the upload limit.")
        text = content.decode("utf-8")
        if not text or len(text.encode("utf-16-le")) // 2 > 8192:
            raise SpawnError("file_too_large", "Files must contain 1-8192 UTF-16 code units of text.")
        return {"name": path.name, "media_type": {".md": "text/markdown", ".json": "application/json"}.get(path.suffix.lower(), "text/plain"), "text": text}
    except (OSError, UnicodeError, ValueError):
        raise SpawnError("unsafe_path", "File is not readable as a regular UTF-8 file within this workspace; symlinks are refused.") from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


MAX_FILE_BYTES = 5 * 1024 * 1024


def read_workspace_bytes(cwd, relative):
    """No globbing, directory walks, symlink traversal, extraction or execution."""
    path = _workspace_path(relative)
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise SpawnError("safe_path_read_unavailable", "This platform cannot enforce no-symlink file reads.")
    descriptors = []
    try:
        current = os.open(Path(cwd).resolve(strict=True), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(current)
        for part in path.parts[:-1]:
            current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            descriptors.append(current)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        descriptors.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise SpawnError("unsafe_file", "Only regular files can be delivered.")
        if not 0 < before.st_size <= MAX_FILE_BYTES:
            raise SpawnError("file_too_large", "Files must contain 1 byte to 5 MiB.")
        with os.fdopen(os.dup(fd), "rb") as stream:
            content = stream.read(MAX_FILE_BYTES + 1)
        after = os.fstat(fd)
        if (len(content) != before.st_size or before.st_size != after.st_size or
            before.st_mtime_ns != after.st_mtime_ns or before.st_ctime_ns != after.st_ctime_ns):
            raise SpawnError("file_changed", "The file changed while being read. Finish writing it before delivery.")
        return path.name, content
    except (OSError, ValueError):
        raise SpawnError("unsafe_path", "The file is not readable as a regular file within the workspace; symlinks are refused.") from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)
