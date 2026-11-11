import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pygit.objects import Blob, GitObject
from pygit.repository import Repository


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = Repository(self.root)
        self.repo.init()

    def write(self, name, content="hello\n"):
        file = self.root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content.encode() if isinstance(content, str) else content)
        return file

    def save(self, name="hello.txt", content="hello\n", message="Save file"):
        self.write(name, content)
        self.repo.add([name])
        return self.repo.commit(message)

    def test_init_and_discovery(self):
        self.assertEqual(self.repo.load_index(), {})
        self.assertEqual(self.repo.current_branch(), "main")
        self.assertIsNone(self.repo.head_commit())
        self.assertFalse(self.repo.init())
        subfolder = self.root / "nested" / "folder"
        subfolder.mkdir(parents=True)
        self.assertEqual(Repository.discover(subfolder).path, self.root)

    def test_objects_round_trip_and_check_hash(self):
        blob = Blob(b"\x00hello\xff")
        restored = GitObject.decompress(blob.compress())
        self.assertEqual(restored.content, blob.content)
        self.assertEqual(restored.hash(), blob.hash())
        object_hash = self.repo.store_object(blob)
        self.assertEqual(self.repo.load_object(object_hash, "blob").content, blob.content)
        with self.assertRaises(ValueError):
            self.repo.load_object(object_hash, "commit")

    def test_add_nested_files_and_skip_metadata(self):
        self.write("nested/deeper/hello.txt")
        self.write("binary.dat", b"\x00\x01\xff")
        self.write(".git/config", "real Git data")
        self.write("__pycache__/ignored.pyc", b"cache")
        self.repo.add(["."])
        self.assertEqual(
            set(self.repo.load_index()), {"nested/deeper/hello.txt", "binary.dat"}
        )
        self.assertEqual((self.root / ".git/config").read_text(), "real Git data")

    def test_commit_saves_staged_bytes_not_later_edits(self):
        self.write("hello.txt", "staged")
        self.repo.add(["hello.txt"])
        self.write("hello.txt", "later edit")
        commit_hash = self.repo.commit("First")
        snapshot = self.repo.snapshot(commit_hash)
        blob = self.repo.load_object(snapshot["hello.txt"], "blob")
        self.assertEqual(blob.content, b"staged")
        self.assertEqual(self.repo.status()["unstaged"], {"hello.txt": "modified"})
        self.assertEqual(self.repo.status()["staged"], {})

    def test_commits_have_tree_parent_message_and_author(self):
        with patch.dict(os.environ, {"GIT_AUTHOR_NAME": "Test User", "GIT_AUTHOR_EMAIL": "test@example.com"}):
            first = self.save()
            second = self.save(content="second", message="Second")
        headers = self.repo.commit_headers(second)
        self.assertEqual(headers["parent"], first)
        self.assertIn("Test User <test@example.com>", headers["author"])
        self.assertNotIn("parent", self.repo.commit_headers(first))
        self.assertTrue(self.repo.load_object(second).content.endswith(b"\n\nSecond\n"))
        self.assertEqual(self.repo.head_commit(), second)
        self.assertEqual(self.repo.current_branch(), "main")

    def test_reject_empty_message_and_unchanged_snapshot(self):
        with self.assertRaisesRegex(ValueError, "Nothing staged"):
            self.repo.commit("Empty")
        self.write("hello.txt")
        self.repo.add(["hello.txt"])
        with self.assertRaisesRegex(ValueError, "message"):
            self.repo.commit("  ")
        first = self.repo.commit("First")
        with self.assertRaisesRegex(ValueError, "Nothing staged"):
            self.repo.commit("Unchanged")
        self.assertEqual(self.repo.head_commit(), first)

    def test_status_distinguishes_all_three_places(self):
        for name in ["modified.txt", "deleted.txt", "removed.txt"]:
            self.write(name, "original")
        self.repo.add(["."])
        self.repo.commit("Initial")
        self.write("modified.txt", "staged")
        (self.root / "deleted.txt").unlink()
        (self.root / "removed.txt").unlink()
        self.write("added.txt")
        self.repo.add(["modified.txt", "deleted.txt", "added.txt"])
        self.write("modified.txt", "unstaged")
        self.write("untracked.txt")
        status = self.repo.status()
        self.assertEqual(status["staged"], {
            "added.txt": "added", "deleted.txt": "deleted", "modified.txt": "modified"
        })
        self.assertEqual(status["unstaged"], {
            "modified.txt": "modified", "removed.txt": "deleted"
        })
        self.assertEqual(status["untracked"], ["untracked.txt"])

    def test_stage_deleted_directory_and_commit_empty_snapshot(self):
        self.save("docs/nested/file.txt")
        shutil.rmtree(self.root / "docs")
        self.repo.add(["docs"])
        self.assertEqual(self.repo.status()["staged"], {"docs/nested/file.txt": "deleted"})
        commit_hash = self.repo.commit("Delete directory")
        self.assertEqual(self.repo.snapshot(commit_hash), {})
        self.assertEqual(self.repo.status(), {"staged": {}, "unstaged": {}, "untracked": []})

    def test_add_rejects_missing_outside_and_metadata_paths(self):
        self.write("valid.txt")
        for paths in [["valid.txt", "missing.txt"], ["../outside"], [".mygit"], [".git"]]:
            with self.subTest(paths=paths):
                with self.assertRaises(ValueError):
                    self.repo.add(paths)
                self.assertEqual(self.repo.load_index(), {})

    def test_branch_and_checkout_restore_nested_files(self):
        first = self.save("docs/deep/file.txt", "main")
        self.repo.create_branch("feature/login")
        self.assertEqual(self.repo.current_branch(), "main")
        self.repo.checkout("feature/login")
        second = self.save("docs/deep/file.txt", "feature")
        self.save("new.txt", "feature only")
        self.write("untracked.txt", "keep me")
        self.repo.checkout("main")
        self.assertEqual((self.root / "docs/deep/file.txt").read_text(), "main")
        self.assertFalse((self.root / "new.txt").exists())
        self.assertEqual((self.root / "untracked.txt").read_text(), "keep me")
        self.assertEqual(self.repo.head_commit(), first)
        self.repo.checkout("feature/login")
        self.assertEqual((self.root / "docs/deep/file.txt").read_text(), "feature")
        self.assertIn("new.txt", self.repo.load_index())
        self.assertEqual(self.repo.commit_headers(second)["parent"], first)

    def test_checkout_create_and_branch_name_validation(self):
        first = self.save()
        self.repo.checkout("topic/nested", create=True)
        self.assertEqual(self.repo.current_branch(), "topic/nested")
        self.assertEqual(self.repo.head_commit(), first)
        for name in ["../bad", "bad..name", "bad name", "a//b", "a.lock", ".hidden", "HEAD"]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.repo.create_branch(name)
        with self.assertRaises(ValueError):
            self.repo.create_branch("topic")
        with self.assertRaises(ValueError):
            self.repo.create_branch("topic/nested/child")

    def test_checkout_rejects_staged_and_unstaged_changes(self):
        first = self.save()
        self.repo.create_branch("other")
        self.write("hello.txt", "unsaved")
        with self.assertRaisesRegex(ValueError, "changes before checkout"):
            self.repo.checkout("other")
        self.repo.add(["hello.txt"])
        with self.assertRaisesRegex(ValueError, "changes before checkout"):
            self.repo.checkout("new-branch", create=True)
        self.assertNotIn("new-branch", self.repo.list_branches())
        self.assertEqual(self.repo.head_commit(), first)
        self.assertEqual((self.root / "hello.txt").read_text(), "unsaved")

    def test_checkout_preserves_untracked_collision_and_head(self):
        self.save()
        self.repo.checkout("feature", create=True)
        self.save("new.txt", "committed")
        self.repo.checkout("main")
        original_index = self.repo.load_index()
        self.write("new.txt", "untracked")
        with self.assertRaisesRegex(ValueError, "untracked"):
            self.repo.checkout("feature")
        self.assertEqual((self.root / "new.txt").read_text(), "untracked")
        self.assertEqual(self.repo.current_branch(), "main")
        self.assertEqual(self.repo.load_index(), original_index)

    def test_checkout_file_and_directory_replacements(self):
        self.save("item", "file")
        self.repo.checkout("directory", create=True)
        (self.root / "item").unlink()
        self.write("item/nested/child.txt", "child")
        self.repo.add(["item"])
        self.repo.commit("File becomes directory")
        self.repo.checkout("main")
        self.assertEqual((self.root / "item").read_text(), "file")
        self.repo.checkout("directory")
        self.assertEqual((self.root / "item/nested/child.txt").read_text(), "child")
        self.write("item/untracked.txt", "keep")
        with self.assertRaisesRegex(ValueError, "untracked"):
            self.repo.checkout("main")
        self.assertEqual((self.root / "item/untracked.txt").read_text(), "keep")

    def test_add_child_path_removes_old_parent_file(self):
        self.save("item", "file")
        (self.root / "item").unlink()
        self.write("item/child.txt", "child")
        self.repo.add(["item/child.txt"])
        self.assertEqual(set(self.repo.load_index()), {"item/child.txt"})
        self.repo.commit("Replace parent")

    def test_detached_checkout_and_commits_keep_branch_unchanged(self):
        first = self.save(content="first")
        second = self.save(content="second")
        self.repo.checkout(first[:7])
        self.assertIsNone(self.repo.current_branch())
        self.assertEqual((self.root / "hello.txt").read_text(), "first")
        detached = self.save(content="detached", message="Detached commit")
        self.assertEqual(self.repo.commit_headers(detached)["parent"], first)
        self.assertEqual(self.repo.head_commit(), detached)
        self.repo.create_branch("rescue")
        self.repo.checkout("main")
        self.assertEqual(self.repo.head_commit(), second)
        self.repo.checkout("rescue")
        self.assertEqual(self.repo.head_commit(), detached)

    def test_safe_branch_deletion(self):
        self.save()
        self.repo.create_branch("old/nested")
        self.repo.delete_branch("old/nested")
        self.assertEqual(self.repo.list_branches(), ["main"])
        self.repo.create_branch("old")
        self.repo.checkout("old")
        self.save(content="divergent")
        self.repo.checkout("main")
        with self.assertRaisesRegex(ValueError, "outside the current history"):
            self.repo.delete_branch("old")
        with self.assertRaisesRegex(ValueError, "current branch"):
            self.repo.delete_branch("main")
        self.assertIn("old", self.repo.list_branches())

    def test_branches_require_a_first_commit(self):
        with self.assertRaisesRegex(ValueError, "Make a commit"):
            self.repo.create_branch("feature")
        with self.assertRaisesRegex(ValueError, "Make a commit"):
            self.repo.checkout("feature", create=True)

    def test_unknown_checkout_does_not_change_files(self):
        first = self.save()
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.repo.checkout("missing")
        self.assertEqual(self.repo.head_commit(), first)
        self.assertEqual((self.root / "hello.txt").read_text(), "hello\n")

    @unittest.skipUnless(hasattr(os, "symlink"), "Requires symbolic links")
    def test_symlinks_are_not_followed_by_add_or_checkout(self):
        self.save()
        self.repo.checkout("feature", create=True)
        self.save("docs/file.txt", "feature")
        self.repo.checkout("main")
        (self.root / "elsewhere").mkdir()
        (self.root / "docs").symlink_to(self.root / "elsewhere", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symbolic links"):
            self.repo.add(["docs"])
        with self.assertRaisesRegex(ValueError, "Symbolic links"):
            self.repo.checkout("feature")
        self.assertFalse((self.root / "elsewhere/file.txt").exists())
        self.assertEqual(self.repo.current_branch(), "main")

    @unittest.skipUnless(shutil.which("git"), "Requires Git for an independent comparison")
    def test_tree_and_commit_objects_match_git_format(self):
        files = {
            "a.c": b"before directory",
            "a/child.txt": b"child",
            "a0.txt": b"after directory",
            "nested/deeper/name with spaces.txt": b"\x00\xffbinary",
            "empty.txt": b"",
        }
        for name, content in files.items():
            self.write(name, content)
        self.repo.add(["."])
        commit_hash = self.repo.commit("Snapshot")

        def git(*args, env=None):
            return subprocess.check_output(
                ["git", *args], cwd=self.root, env=env, text=True
            ).strip()

        git("init", "-q")
        git("add", "--", *files)
        expected_tree = git("write-tree")
        self.assertEqual(self.repo.commit_headers(commit_hash)["tree"], expected_tree)
        environment = dict(os.environ, GIT_OBJECT_DIRECTORY=str(self.repo.objects_directory))
        self.assertEqual(git("cat-file", "-t", commit_hash, env=environment), "commit")
        self.assertIn("Snapshot", git("cat-file", "-p", commit_hash, env=environment))
        reversed_index = dict(reversed(list(self.repo.load_index().items())))
        self.assertEqual(self.repo.write_tree(reversed_index), expected_tree)


if __name__ == "__main__":
    unittest.main()
