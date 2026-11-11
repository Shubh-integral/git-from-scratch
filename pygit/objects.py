"""Git objects: blobs hold files, trees hold directories, commits hold snapshots."""

import hashlib
import time
import zlib
from datetime import datetime


class GitObject:
    def __init__(self, object_type, content):
        self.object_type = object_type
        self.content = content

    def data(self):
        header = f"{self.object_type} {len(self.content)}\0".encode()
        return header + self.content

    def hash(self):
        return hashlib.sha1(self.data()).hexdigest()

    def compress(self):
        return zlib.compress(self.data())

    @classmethod
    def decompress(cls, data):
        header, separator, content = zlib.decompress(data).partition(b"\0")
        if not separator:
            raise ValueError("Invalid object header.")
        object_type, size = header.decode("ascii").split(" ")
        if object_type not in {"blob", "tree", "commit"} or int(size) != len(content):
            raise ValueError("Invalid object type or size.")
        return GitObject(object_type, content)


class Blob(GitObject):
    def __init__(self, content):
        super().__init__("blob", content)


class Tree(GitObject):
    def __init__(self, entries):
        # Each entry is (mode, name, hash). Git sorts directories with a final "/".
        def sort_name(entry):
            mode, name, object_hash = entry
            if mode == "40000":
                name += "/"
            return name.encode()

        entries = sorted(entries, key=sort_name)
        content = b""
        for mode, name, object_hash in entries:
            content += f"{mode} {name}\0".encode()
            content += bytes.fromhex(object_hash)
        super().__init__("tree", content)

    @staticmethod
    def read_entries(content):
        entries = []
        while content:
            header, separator, rest = content.partition(b"\0")
            if not separator or len(rest) < 20:
                raise ValueError("Invalid tree entry.")
            mode, name = header.decode().split(" ", 1)
            # A SHA-1 hash is stored as 20 raw bytes, rather than 40 hex characters.
            entries.append((mode, name, rest[:20].hex()))
            content = rest[20:]
        return entries


class Commit(GitObject):
    def __init__(self, tree_hash, parent_hash, message, author):
        timestamp = f"{int(time.time())} {datetime.now().astimezone():%z}"
        lines = [f"tree {tree_hash}"]
        if parent_hash:
            lines.append(f"parent {parent_hash}")
        lines.append(f"author {author} {timestamp}")
        lines.append(f"committer {author} {timestamp}")
        content = "\n".join(lines) + "\n\n" + message + "\n"
        super().__init__("commit", content.encode())

    @staticmethod
    def read_headers(content):
        headers = {}
        for line in content.split(b"\n\n", 1)[0].decode().splitlines():
            name, value = line.split(" ", 1)
            headers[name] = value
        return headers
