import argparse
import json
import sys
from pathlib import Path
import hashlib, zlib


class GitObjects:

    def __init__(self, object_type, content):
        self.object_type = object_type
        self.content = content

    # SHA-1(header + content) → object ID : That ID is a fingerprint used to identify and retrieve the object. The same object bytes produce the same hash
    def hash(self):
        # SHA-1 Hash? header = <type><size in bytes>\0<content> and then u hash this header. A header is information placed before the actual content to describe it
        # why this format: <type><size>\0<content> ? type: to tell diff btw commit, blob or tree | size: to tell how mnany bytes (might be useful to check if file content size matches this -> gives a signal that nothing has been tampered with? content is well content xD )

        header = f"{self.object_type} {len(self.content)}\0".encode()
        return hashlib.sha1(header + self.content).hexdigest() 
    
    def compress(self):
        # use zlib on the header -> compressing the object for optimal storing
        header = f"{self.object_type} {len(self.content)}\0".encode()
        return zlib.compress(header + self.content)

    @classmethod
    def de_compress(cls, data):
        # here we will de-compress the ibject we compressed in the above function ^
        decompressed = zlib.decompress(data)
        null_idx = decompressed.find(b"\0")
        header = decompressed[:null_idx]
        content = decompressed[null_idx+1:]
        object_type, size = header.split(" ")
        return cls(object_type, content)

class Blob(GitObjects):
    def __init__(self, content):
        super().__init__('blob', content)

    def get_content(self):
        return self.content

class tree(GitObjects):
    def __init__(self, content):
        super().__init__("tree", content)

    def get_content(self):
            return self.content
    
class Repository:
    def __init__(self, path='.'):
        self.path = Path(path).resolve()
        self.git_directory = self.path / ".mygit"
        self.refs_directory = self.git_directory / "refs"
        self.heads_directory = self.refs_directory / "heads"
        self.objects_directory = self.git_directory / "objects"
        self.index_file = self.git_directory / "index"
        self.head_file = self.git_directory / "HEAD"
        self.added_count = 0

    def init(self):
        # creating all the suitable files that are created when we initialize the git repository.

        if self.git_directory.exists():
            return False

        self.git_directory.mkdir()
        self.refs_directory.mkdir()
        self.heads_directory.mkdir()
        self.objects_directory.mkdir()
        self.index_file.write_text(json.dumps({}, indent=2))
        self.head_file.write_text("ref: refs/heads/main\n")

        print(f"Initialized repository in {self.git_directory}")
    
        return True

    def store_object(self, obj):
        object_hash = obj.hash()
        object_dir = self.objects_directory / object_hash[:2]
        object_file = object_dir / object_hash[2:]

        if not object_file.exists():
            if not object_dir.exists():
                object_dir.mkdir()
            object_file.write_bytes(obj.compress())
        return object_hash

    def load_index(self):
        if not self.index_file.exists():
            return {}
        return json.loads(self.index_file.read_text())

    def save_index(self, index):
        self.index_file.write_text(json.dumps(index, indent=2))

    def add_file(self, path):
        # read the file content
        # create a Blob object from the file content 
        # we will compress the blob object created from the file content - A Git blob is a snapshot of one file's contents, identified by a hash.
        # we will store the compressed blob in the objects db/Folder in our case that we create while initializing ouyr git repo (.mygit/objects)
        # update the current state of the index to include this file

        full_path = self.path / path

        if not full_path.exists():
            raise FileNotFoundError(f'Path {path} does not exist')

        content = full_path.read_bytes()
        blob = Blob(content)
        blob_hash = self.store_object(blob)
        index = self.load_index()
        index[str(path)] = blob_hash
        self.save_index(index)
        self.added_count += 1

    def add_directory(self, path):
        full_path = self.path / path

        for file_path in full_path.iterdir():
            if file_path.name == ".mygit":
                continue
            self.add_path(file_path.relative_to(self.path))

    # checking if those paths exist or not - if does, add it in staging area.
    def add_path(self, path):
        full_path = self.path / path

        if not full_path.exists():
            raise FileNotFoundError(f'Path {path} does not exist')

        if full_path.is_file():
            self.add_file(path)
        elif full_path.is_dir():
            self.add_directory(path)
        else:
            raise ValueError(f'{path} is neither a file nor a directory')

    def group_paths(self, entries):
        root_files = {}
        folders = {}

        for filename, blob_hash in sorted(entries.items()):
            name, separator, remaining_path = filename.partition("/")

            if not separator:
                root_files[name] = blob_hash
            else:
                if name not in folders:
                    folders[name] = {}

                folders[name][remaining_path] = blob_hash

        return root_files, folders

    def commit(self, message):
        # create a tree object from the index (staging area)
        index = self.load_index()
        root_files, folders = self.group_paths(index)
        for folder_name, folder_entries in folders.items():
            child_files, child_folders = self.group_paths(folder_entries)

            folders[folder_name] = {
                "files": child_files,
                "folders": child_folders
            }

        print('rott files are ', root_files)
        print('folder', folders)
        
        return root_files, folders



def main():
    parser = argparse.ArgumentParser(description="PyGit - A simple git clone!")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    init_parser = subparsers.add_parser("init", help='Initialize a new repository')
 
    add_parser = subparsers.add_parser("add", help="add Files + Directory to the staging area")
    add_parser.add_argument("path", nargs='+', help="Files and Directories to be added    ") # nargs=+ is basically u can add multiple arguments and they will all be parsed into the list[]

    commit_parser = subparsers.add_parser("commit", help='commit the code into the repository')
    commit_parser.add_argument("-m", help="Commit message", required=True)
   
    args = parser.parse_args()
    
    if args.command == None:
        parser.print_help()
        return 

    repo = Repository()

    if args.command == "init":
        
        if not repo.init():
            print(f"Repository already exists in {repo.git_directory}", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == "add":
        if not repo.git_directory.exists():
            print(f"Not a Git Repository | Please initialize the Repository first using 'git init' command", file=sys.stderr)
            sys.exit(1)

        for path in args.path:
            repo.add_path(path)
        print(f"Added {repo.added_count} files")

    elif args.command == "commit":
        if not repo.git_directory.exists():
                print(f"Not a Git Repository | Please initialize the Repository first using 'git init' command", file=sys.stderr)
                sys.exit(1)

        repo.commit(args.m) 


             


    
if __name__ == "__main__":
    main()



