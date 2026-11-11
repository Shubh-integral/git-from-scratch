"""Repository operations. The index is a dictionary of filename -> blob hash."""

import json
import os
import re
from pathlib import Path

from .objects import Blob, Commit, GitObject, Tree


# These directories are implementation details, not files to version.
IGNORED_NAMES = {".mygit", ".git", "__pycache__"}


class Repository:
    def __init__(self, path="."):
        self.path = Path(path).resolve()
        self.git_directory = self.path / ".mygit"
        self.objects_directory = self.git_directory / "objects"
        self.heads_directory = self.git_directory / "refs" / "heads"
        self.index_file = self.git_directory / "index"
        self.head_file = self.git_directory / "HEAD"

    @classmethod
    def discover(cls, path="."):
        current = Path(path).resolve()
        for directory in [current, *current.parents]:
            if (directory / ".mygit").is_dir():
                return cls(directory)
        raise ValueError("Not a PyGit repository. Run 'init' first.")

    def init(self):
        if self.git_directory.exists():
            return False
        self.objects_directory.mkdir(parents=True)
        self.heads_directory.mkdir(parents=True)
        self.save_index({})
        self.head_file.write_text("ref: refs/heads/main\n")
        return True

    # Objects are stored under objects/<first two hash characters>/<remaining hash>.
    def store_object(self, obj):
        object_hash = obj.hash()
        destination = self.objects_directory / object_hash[:2] / object_hash[2:]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(obj.compress())
        return object_hash

    def load_object(self, object_hash, expected_type=None):
        if not re.fullmatch(r"[0-9a-f]{40}", object_hash):
            raise ValueError(f"Invalid object hash: {object_hash}")
        source = self.objects_directory / object_hash[:2] / object_hash[2:]
        obj = GitObject.decompress(source.read_bytes())
        if obj.hash() != object_hash:
            raise ValueError(f"Damaged object: {object_hash}")
        if expected_type and obj.object_type != expected_type:
            raise ValueError(f"Expected a {expected_type}, got a {obj.object_type}.")
        return obj

    def load_index(self):
        if not self.index_file.exists():
            return {}
        return json.loads(self.index_file.read_text())

    def save_index(self, index):
        self.index_file.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")

    def working_files(self):
        """List files without descending into our metadata or the real .git."""
        files = {}
        for directory, folders, filenames in os.walk(self.path):
            for name in folders[:]:
                full_path = Path(directory) / name
                if name in IGNORED_NAMES:
                    folders.remove(name)
                elif full_path.is_symlink():
                    folders.remove(name)
                    filenames.append(name)
            for name in filenames:
                if name not in IGNORED_NAMES:
                    full_path = Path(directory) / name
                    files[full_path.relative_to(self.path).as_posix()] = full_path
        return files

    def check_path(self, filename):
        """Keep tracked paths inside this repository and outside metadata."""
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Path is outside the repository: {filename}")
        if any(part in IGNORED_NAMES for part in relative.parts):
            raise ValueError(f"Cannot track repository metadata: {filename}")
        full_path = self.path / relative
        current = full_path
        while current != self.path:
            if current.is_symlink():
                raise ValueError(f"Symbolic links are not supported: {filename}")
            current = current.parent
        return full_path

    def add(self, paths):
        index = self.load_index()
        working = self.working_files()
        staged = set()

        for path in paths:
            # abspath removes "." and ".." without following symbolic links.
            full_path = Path(os.path.abspath(self.path / path))
            try:
                scope = full_path.relative_to(self.path).as_posix()
            except ValueError:
                raise ValueError(f"Path is outside the repository: {path}") from None
            self.check_path(scope)

            # A directory stages all its files, including tracked deletions.
            def in_scope(name):
                return scope == "." or name == scope or name.startswith(scope + "/")

            old_names = [name for name in index if in_scope(name)]
            new_files = {name: file for name, file in working.items() if in_scope(name)}
            if not full_path.exists() and not old_names:
                raise ValueError(f"Path does not exist: {path}")

            for name in old_names:
                del index[name]
                staged.add(name)
            for name, file in new_files.items():
                self.check_path(name)
                # A file can replace a directory, or a directory can replace a file.
                for old_name in list(index):
                    if name.startswith(old_name + "/"):
                        del index[old_name]
                        staged.add(old_name)
                index[name] = self.store_object(Blob(file.read_bytes()))
                staged.add(name)

        self.save_index(index)
        return len(staged)

    def write_tree(self, entries):
        """Group one directory, save its children, then save the directory itself."""
        files = {}
        folders = {}
        for filename, blob_hash in entries.items():
            name, separator, remaining_path = filename.partition("/")
            if separator:
                if name not in folders:
                    folders[name] = {}
                folders[name][remaining_path] = blob_hash
            else:
                files[name] = blob_hash

        tree_entries = []
        for name, blob_hash in files.items():
            tree_entries.append(("100644", name, blob_hash))
        for name, child_entries in folders.items():
            child_hash = self.write_tree(child_entries)
            tree_entries.append(("40000", name, child_hash))
        return self.store_object(Tree(tree_entries))

    def read_tree(self, tree_hash, prefix=""):
        files = {}
        obj = self.load_object(tree_hash, "tree")
        for mode, name, object_hash in Tree.read_entries(obj.content):
            if name in {"", ".", ".."} or "/" in name:
                raise ValueError("Invalid filename in tree.")
            filename = prefix + name
            # Check stored names before using them to restore working files.
            if any(part in IGNORED_NAMES for part in Path(filename).parts):
                raise ValueError("Tree contains repository metadata.")
            if mode == "40000":
                files.update(self.read_tree(object_hash, filename + "/"))
            elif mode == "100644":
                files[filename] = object_hash
            else:
                raise ValueError(f"Unsupported file mode: {mode}")
        return files

    def current_branch(self):
        head = self.head_file.read_text().strip()
        if head.startswith("ref: refs/heads/"):
            return head.removeprefix("ref: refs/heads/")
        return None

    def head_commit(self):
        branch = self.current_branch()
        if branch is None:
            return self.head_file.read_text().strip()
        branch_file = self.branch_path(branch)
        return branch_file.read_text().strip() if branch_file.is_file() else None

    def commit_headers(self, commit_hash):
        obj = self.load_object(commit_hash, "commit")
        return Commit.read_headers(obj.content)

    def snapshot(self, commit_hash):
        """Read a commit's tree back into a filename -> blob hash dictionary."""
        if not commit_hash:
            return {}
        return self.read_tree(self.commit_headers(commit_hash)["tree"])

    def commit(self, message):
        if not message.strip():
            raise ValueError("Commit message cannot be empty.")
        parent_hash = self.head_commit()
        index = self.load_index()
        if index == self.snapshot(parent_hash):
            raise ValueError("Nothing staged to commit.")

        tree_hash = self.write_tree(index)
        name = os.environ.get("GIT_AUTHOR_NAME", "PyGit User")
        email = os.environ.get("GIT_AUTHOR_EMAIL", "pygit@example.com")
        if any(character in name + email for character in "\r\n<>"):
            raise ValueError("Author name and email cannot contain newlines or angle brackets.")
        obj = Commit(tree_hash, parent_hash, message, f"{name} <{email}>")
        commit_hash = self.store_object(obj)

        branch = self.current_branch()
        if branch is None:
            self.head_file.write_text(commit_hash + "\n")
        else:
            self.branch_path(branch).write_text(commit_hash + "\n")
        return commit_hash

    @staticmethod
    def changes(before, after):
        changes = {}
        for name in sorted(before.keys() | after.keys()):
            if name not in before:
                changes[name] = "added"
            elif name not in after:
                changes[name] = "deleted"
            elif before[name] != after[name]:
                changes[name] = "modified"
        return changes

    def status(self):
        """Staged: compare HEAD to index. Unstaged: compare index to disk."""
        index = self.load_index()
        working_files = self.working_files()
        working = {}
        for name in index:
            if name in working_files:
                file = working_files[name]
                working[name] = "symlink" if file.is_symlink() else Blob(file.read_bytes()).hash()
        return {
            "staged": self.changes(self.snapshot(self.head_commit()), index),
            "unstaged": self.changes(index, working),
            "untracked": sorted(working_files.keys() - index.keys()),
        }

    # HEAD names a branch. Each branch file holds the latest commit on that branch.
    def branch_path(self, name):
        parts = name.split("/")
        forbidden = " ~^:?*[\\"
        if (
            not name or name == "HEAD" or name == "@" or name.startswith("-")
            or ".." in name or "@{" in name or name.endswith(".")
            or any(character in forbidden or ord(character) < 32 or ord(character) == 127
                   for character in name)
            or any(not part or part.startswith(".") or part.endswith(".lock") for part in parts)
        ):
            raise ValueError(f"Invalid branch name: {name}")
        return self.heads_directory / name

    def list_branches(self):
        return sorted(
            file.relative_to(self.heads_directory).as_posix()
            for file in self.heads_directory.rglob("*") if file.is_file()
        )

    def new_branch_path(self, name):
        branch_file = self.branch_path(name)
        if branch_file.exists():
            raise ValueError(f"Branch already exists: {name}")
        for parent in branch_file.parents:
            if parent == self.heads_directory:
                break
            if parent.is_file():
                raise ValueError("A branch already uses part of that name.")
        return branch_file

    def create_branch(self, name):
        branch_file = self.new_branch_path(name)
        commit_hash = self.head_commit()
        if not commit_hash:
            raise ValueError("Make a commit before creating a branch.")
        branch_file.parent.mkdir(parents=True, exist_ok=True)
        branch_file.write_text(commit_hash + "\n")

    def delete_branch(self, name):
        branch_file = self.branch_path(name)
        if name == self.current_branch():
            raise ValueError("Cannot delete the current branch.")
        if not branch_file.is_file():
            raise ValueError(f"Unknown branch: {name}")
        # Only delete a branch if its commits are already in the current history.
        tip = branch_file.read_text().strip()
        current = self.head_commit()
        while current and current != tip:
            current = self.commit_headers(current).get("parent")
        if current != tip:
            raise ValueError("Branch has commits outside the current history; keeping it.")
        branch_file.unlink()
        parent = branch_file.parent
        while parent != self.heads_directory and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

    def resolve_commit(self, target):
        if target == "HEAD":
            commit_hash = self.head_commit()
            if commit_hash:
                return commit_hash
        elif re.fullmatch(r"[0-9a-f]{4,40}", target):
            matches = []
            directory = self.objects_directory / target[:2]
            for file in directory.glob(target[2:] + "*"):
                object_hash = directory.name + file.name
                if file.is_file() and self.load_object(object_hash).object_type == "commit":
                    matches.append(object_hash)
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError("Commit prefix is ambiguous. Use more characters.")
        raise ValueError(f"Unknown branch or commit: {target}")

    def checkout(self, target, create=False):
        if create:
            branch_file = self.new_branch_path(target)
            commit_hash = self.head_commit()
            if not commit_hash:
                raise ValueError("Make a commit before creating a branch.")
            branch = target
        elif target in self.list_branches():
            branch = target
            commit_hash = self.branch_path(target).read_text().strip()
        else:
            branch = None
            commit_hash = self.resolve_commit(target)

        status = self.status()
        if status["staged"] or status["unstaged"]:
            raise ValueError("Commit your staged and unstaged changes before checkout.")

        current = self.load_index()
        destination = self.snapshot(commit_hash)
        removed = current.keys() - destination.keys()
        contents = {}

        # Check every destination before changing any working files.
        for name, object_hash in destination.items():
            full_path = self.check_path(name)
            contents[name] = self.load_object(object_hash, "blob").content
            for parent in full_path.parents:
                if parent == self.path:
                    break
                if parent.is_file() and parent.relative_to(self.path).as_posix() not in removed:
                    raise ValueError(f"Untracked file blocks checkout: {parent.name}")
            if full_path.is_file() and name not in current:
                raise ValueError(f"Checkout would overwrite an untracked file: {name}")
            if full_path.is_dir():
                for child in full_path.rglob("*"):
                    if child.is_symlink() or (
                        child.is_file() and child.relative_to(self.path).as_posix() not in removed
                    ):
                        raise ValueError(f"Checkout would overwrite untracked files in: {name}")

        # Remove files absent from the destination and clean up empty parents.
        for name in sorted(removed, key=lambda name: len(Path(name).parts), reverse=True):
            full_path = self.path / name
            full_path.unlink()
            parent = full_path.parent
            while parent != self.path:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

        for name, content in contents.items():
            full_path = self.path / name
            if full_path.is_dir():
                # Preflight already proved this directory contains no untracked files.
                for child in sorted(full_path.rglob("*"), reverse=True):
                    child.rmdir()
                full_path.rmdir()
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(content)

        self.save_index(destination)
        if create:
            branch_file.parent.mkdir(parents=True, exist_ok=True)
            branch_file.write_text(commit_hash + "\n")
        if branch:
            self.head_file.write_text(f"ref: refs/heads/{branch}\n")
        else:
            self.head_file.write_text(commit_hash + "\n")
        return commit_hash
