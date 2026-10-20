import argparse
import sys


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

    # init -> creates a .git, which is a hidden directory that sits at the root of a project and serves as the database and metadata container for a Git repository. 
    
main()


# git is a cli tool, so we will use argparse to give it that cli capability.
