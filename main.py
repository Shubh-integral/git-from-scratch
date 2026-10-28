import argparse
import json
import sys
from pathlib import Path


class GitObjects:

    def __init__(self, object_type, content):
        self.object_type = object_type
        self.content = content

    def hash(self):
        # SHA-1 Hash? header = <type><size>\0<content> and then u hash this header. why is this called header? 
        # why this format: <type><size>\0<content> ? type: to tell diff btw commit, blob or tree | size: to tell how mnany bytes (might be useful to check if file content size matches this -> gives a signal that nothing has been tampered with? content is well content xD )
        pass
    
    def compress(self):
        # use zlib on the header
        pass

    def de_compress(self):
        # classmethod? returns data in bytes...? 
        pass


    pass 


class Repository:
    def __init__(self, path='.'):
        self.path = Path(path).resolve()
        self.git_directory = self.path / ".mygit"
        self.refs_directory = self.git_directory / "refs"
        self.heads_directory = self.refs_directory / "heads"
        self.objects_directory = self.git_directory / "objects"
        self.index_file = self.git_directory / "index"
        self.head_file = self.git_directory / "HEAD"

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

    def add_file(self, path):
        # read the file content
        # create a Blob object from the file content 
        # we will compress the blob object created from the file content - A Git blob is a snapshot of one file's contents, identified by a hash.
        # we will store the compressed blob in the objects db/Folder in our case that we create while initializing ouyr git repo (.mygit/objects)
        # update the index to include this file

        full_path = self.path / path

        if not full_path.exists():
            raise FileNotFoundError(f'Path {path} does not exist')

        content = full_path.read_bytes()

        pass
    
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



def main():
    parser = argparse.ArgumentParser(description="PyGit - A simple git clone!")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    init_parser = subparsers.add_parser("init", help='Initialize a new repository')
 
    add_parser = subparsers.add_parser("add", help="add Files + Directory to the staging area")
    add_parser.add_argument("path", nargs='+', help="Files and Directories to be added    ") # nargs=+ is basically u can add multiple arguments and they will all be parsed into the list[]

    commit_parser = subparsers.add_parser("commit", help='commit the code into the repository')
    commit_parser.add_argument("-m", help="Commit message")
   
    args = parser.parse_args()
    
    if args.command == None:
        parser.print_help()
        return 

    repo = Repository()

    if args.command == "init":
        
        if not repo.init():
            print(f"Repository already exists in {repo.git_directory}", file=sys.stderr)
            sys.exit(1)
        else:
            repo.init()
    
    elif args.command == "add":
        if not repo.git_directory.exists():
            print(f"Not a Git Repository | Please initialize the Repository first using 'git init' command", file=sys.stderr)
            sys.exit(1)

        print(args.path)
        for path in args.path:
            # gotta check if those paths exists or not?
            pass

             


    
main()



