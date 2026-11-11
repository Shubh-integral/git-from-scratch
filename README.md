# Git from Scratch

A small Git built in Python. It saves file snapshots, tracks changes, and switches
between local branches. Everything is stored in `.mygit`; your real `.git` is left alone.

Requires Python 3.10 or newer. No packages to install.

## Try it

Run these commands from this project's directory:

```sh
python3 main.py init

echo "hello" > hello.txt
python3 main.py add hello.txt
python3 main.py status
python3 main.py commit -m "First commit"

python3 main.py checkout -b feature
echo "hello from feature" > hello.txt
python3 main.py add hello.txt
python3 main.py commit -m "Update greeting"

python3 main.py checkout main
# hello.txt contains "hello" again.
```

## Commands

Run these from the directory containing `main.py`. Initialize once before using the
other commands, and make your first commit before creating branches.

| Run | What it does |
| --- | --- |
| `python3 main.py init` | Create `.mygit` in the current directory |
| `python3 main.py add hello.txt` | Stage an existing file, or its deletion if it was tracked |
| `python3 main.py add hello.txt notes.txt` | Stage multiple files |
| `python3 main.py add docs` | Stage files and tracked deletions inside a folder |
| `python3 main.py add .` | Stage everything in the current directory, including tracked deletions |
| `python3 main.py commit -m "Save greeting"` | Save the staged snapshot |
| `python3 main.py status` | Show staged changes, unstaged changes, and untracked files |
| `python3 main.py branch` | List branches; `*` marks the current branch |
| `python3 main.py branch feature` | Create a branch without switching to it |
| `python3 main.py branch -d feature` | Delete a branch whose commits are in the current history |
| `python3 main.py checkout feature` | Switch to an existing branch |
| `python3 main.py checkout main` | Switch back to the main branch |
| `python3 main.py checkout -b feature` | Create a new branch and switch to it |
| `python3 main.py checkout abc1234` | Visit a commit; replace `abc1234` with its actual hash |
| `python3 main.py --help` | Show all commands |
| `python3 main.py checkout --help` | Show options for one command |

The commands above are examples: replace filenames and branch names with your own.
Use `checkout -b feature` only when `feature` does not exist yet. To visit a commit,
use the hash printed by `commit`; a unique prefix of at least four characters also works.

From another directory, use the full path to `main.py`; commands also work from
subfolders of an initialized repository.

`add` saves the file as it is **at that moment**. Later edits need another `add`.
Checkout requires no staged or unstaged changes. It preserves untracked files and
refuses to overwrite them. To keep commits made with a detached HEAD, create a
branch before switching away.

Commits use `PyGit User <pygit@example.com>` by default. Set `GIT_AUTHOR_NAME` and
`GIT_AUTHOR_EMAIL` to use your own name and email.

## Read the code

- `main.py`: parses commands and prints results.
- `pygit/objects.py`: hashes, compresses, and reads blobs, trees, and commits.
- `pygit/repository.py`: staging, commits, status, branches, and checkout.
- `tests/`: checks the commands and repository behavior.

A **blob** stores file contents. A **tree** lists files and subfolders. A **commit**
points to a tree and its previous commit. The **index** records staged file hashes.
A **branch** points to its latest commit, and **HEAD** names the current branch or commit.

This learning project supports regular files and local history. It does not implement
merging, remotes, `.gitignore` patterns, symlinks, or executable file permissions.
`.git`, `.mygit`, and `__pycache__` are always skipped.

Run the tests:

```sh
python3 -B -m unittest discover -s tests -v
```
