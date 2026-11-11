"""Command-line entry point. Run: python3 main.py --help"""

import argparse
import sys
import zlib
from pathlib import Path

from pygit.repository import Repository


def print_status(repo):
    branch = repo.current_branch()
    if branch:
        print(f"On branch {branch}")
    else:
        print(f"HEAD detached at {repo.head_commit()[:7]}")
    if not repo.head_commit():
        print("No commits yet.")

    status = repo.status()
    for key, title in [
        ("staged", "Changes staged for commit:"),
        ("unstaged", "Changes not staged:"),
    ]:
        if status[key]:
            print(f"\n{title}")
            for name, change in status[key].items():
                print(f"  {change}: {name}")
    if status["untracked"]:
        print("\nUntracked files:")
        for name in status["untracked"]:
            print(f"  {name}")
    if not any(status.values()):
        print("Working tree clean.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="PyGit: a small Git built in Python.")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("init", help="Initialize a repository in this directory")

    add = commands.add_parser("add", help="Stage files, directories, or deletions")
    add.add_argument("paths", nargs="+", help="Paths to stage; use . for everything")

    commit = commands.add_parser("commit", help="Save the staged snapshot")
    commit.add_argument("-m", required=True, help="Commit message")

    commands.add_parser("status", help="Show staged, unstaged, and untracked files")

    branch = commands.add_parser("branch", help="List, create, or delete branches")
    branch.add_argument("name", nargs="?", help="New branch name")
    branch.add_argument("-d", "--delete", action="store_true", help="Delete a merged branch")

    checkout = commands.add_parser("checkout", help="Switch branches or visit a commit")
    checkout.add_argument("target", help="Branch name or commit hash")
    checkout.add_argument("-b", action="store_true", help="Create and switch to a new branch")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "branch" and args.delete and not args.name:
        parser.error("branch -d needs a branch name")

    try:
        if args.command == "init":
            repo = Repository()
            if repo.init():
                print(f"Initialized repository in {repo.git_directory}")
            else:
                print(f"Repository already exists in {repo.git_directory}")
            return 0

        repo = Repository.discover()
        if args.command == "add":
            # Resolve CLI arguments from the caller's directory, including subfolders.
            paths = [str(Path(path).absolute()) for path in args.paths]
            print(f"Staged {repo.add(paths)} path(s).")
        elif args.command == "commit":
            commit_hash = repo.commit(args.m)
            print(f"[{repo.current_branch() or 'detached'} {commit_hash[:7]}] {args.m}")
        elif args.command == "status":
            print_status(repo)
        elif args.command == "branch":
            if args.delete:
                repo.delete_branch(args.name)
                print(f"Deleted branch {args.name}")
            elif args.name:
                repo.create_branch(args.name)
                print(f"Created branch {args.name}")
            else:
                branches = repo.list_branches()
                if not branches:
                    print("No branches yet. Make a commit first.")
                for name in branches:
                    marker = "*" if name == repo.current_branch() else " "
                    print(f"{marker} {name}")
        elif args.command == "checkout":
            commit_hash = repo.checkout(args.target, create=args.b)
            if repo.current_branch():
                print(f"Switched to branch {repo.current_branch()}")
            else:
                print(f"HEAD detached at {commit_hash[:7]}")
    except (ValueError, OSError, UnicodeError, zlib.error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
