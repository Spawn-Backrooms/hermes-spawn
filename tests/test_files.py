import os
from pathlib import Path
import tempfile
import unittest

from tests.support import load

files = load("files")
schemas = load("schemas")
SpawnError = load("spawn_client").SpawnError


class FilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        return path

    def test_reads_named_nested_utf8_file(self):
        self.write("output/review.md", "café 🌍")
        self.assertEqual({"name": "review.md", "media_type": "text/markdown", "text": "café 🌍"}, files.read_workspace_text(self.root, "output/review.md"))

    def test_utf16_limit_exact_boundary(self):
        self.write("ok.txt", "😀" * 4096)
        self.assertEqual(4096, len(files.read_workspace_text(self.root, "ok.txt")["text"]))
        self.write("big.txt", "😀" * 4096 + "x")
        with self.assertRaises(SpawnError) as caught:
            files.read_workspace_text(self.root, "big.txt")
        self.assertEqual("file_too_large", caught.exception.code)

    def test_schema_uses_utf16_not_codepoint_count(self):
        item = {"name": "out.txt", "media_type": "text/plain", "text": "😀" * 4096}
        schemas.validate(item, schemas.FILE)
        item["text"] += "x"
        with self.assertRaises(SpawnError):
            schemas.validate(item, schemas.FILE)
        item["text"] = "\ud800"
        with self.assertRaises(SpawnError):
            schemas.validate(item, schemas.FILE)

    def test_traversal_absolute_credentials_and_directories_refused(self):
        for name in ("../secret.txt", "/etc/passwd", ".env", ".env.local", "nested/.env.production", "auth.json", ".git/config", ".ssh/id_rsa", ".aws/credentials", ".codex/config.toml", ".hermes/auth.json", ""):
            with self.subTest(name=name), self.assertRaises(SpawnError):
                files.read_workspace_text(self.root, name)
        (self.root / "directory").mkdir()
        with self.assertRaises(SpawnError):
            files.read_workspace_text(self.root, "directory")

    def test_leaf_and_parent_symlinks_refused_even_inside_root(self):
        self.write("real/file.txt", "ok")
        (self.root / "leaf.txt").symlink_to(self.root / "real/file.txt")
        (self.root / "alias").symlink_to(self.root / "real", target_is_directory=True)
        for name in ("leaf.txt", "alias/file.txt"):
            with self.subTest(name=name), self.assertRaises(SpawnError):
                files.read_workspace_text(self.root, name)

    def test_non_utf8_empty_oversized_and_fifo_fail_closed(self):
        (self.root / "binary").write_bytes(b"\xff\xfe")
        self.write("empty", "")
        self.write("oversized", "x" * 32769)
        os.mkfifo(self.root / "pipe")
        for name in ("binary", "empty", "oversized", "pipe"):
            with self.subTest(name=name), self.assertRaises(SpawnError):
                files.read_workspace_text(self.root, name)

    def test_delivery_schema_bounds_number_and_names(self):
        schema = schemas.SCHEMAS["spawn_deliver_text"]["parameters"]
        item = {"name": "ok.txt", "media_type": "text/plain", "text": "ok"}
        for count in (0, 11):
            with self.subTest(count=count), self.assertRaises(SpawnError):
                schemas.validate({"job_id": "j1", "files": [item] * count}, schema)
        for name in ("dir/file.txt", "dir\\file.txt", "bad\x00.txt"):
            with self.subTest(name=name), self.assertRaises(SpawnError):
                schemas.validate({**item, "name": name}, schemas.FILE)


if __name__ == "__main__":
    unittest.main()
