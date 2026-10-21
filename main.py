import argparse
import json
import sys
from pathlib import Path


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

def main():
    parser = argparse.ArgumentParser(description="PyGit - A simple git clone!")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    init_parser = subparsers.add_parser("init", help='Initialize a new repository')
    commit_parser = subparsers.add_parser("commit", help='commit the code into the repository')
    commit_parser.add_argument("-m", help="Commit message")
   
    args = parser.parse_args()
    
    if args.command == None:
        parser.print_help()
        return 

    if args.command == "init":
        repo = Repository()

        if not repo.init():
            print(f"Repository already exists in {repo.git_directory}", file=sys.stderr)
            sys.exit(1)
    
main()


# git is a cli tool, so we will use argparse to give it that cli capability.
