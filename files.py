"""Read only named UTF-8 files below the session working directory."""
import os
from pathlib import Path
import stat

from .spawn_client import SpawnError


def read_workspace_text(cwd, relative):
    path = Path(relative)
    if path.is_absolute() or any(part in {"..", ".git", ".ssh", ".aws", ".codex", ".hermes"} for part in path.parts):
        raise SpawnError("unsafe_path", "Use a workspace-relative path without traversal or credential directories.")
    if not path.parts or path.name == "auth.json" or any(p == ".env" or p.startswith(".env.") for p in path.parts):
        raise SpawnError("unsafe_path", "Credential files cannot be delivered.")
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
