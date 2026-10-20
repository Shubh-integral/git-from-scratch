'''Here we will implement a basic parser + subparser'''

import sys
args = sys.argv

print("Arguments:", args)

if len(args) < 2:
    print("Please provide a command!")

# this block of code is a basic parser because it reads the arguments and figures out what the user wants.
elif args[1] == "commit":
    print("User wants to commit!")

    # a subparser is simply a parser for a specific command.
    # The main parser can recognize the command, But after recognizing the command, we still need to examine the remaining arguments.
    if len(args) >= 4 and args[2] == "-m":
        message = args[3]
        print("Commit message:", message)
    else:
        print("Please provide a commit message!")

'''
This works!

But there's a problem.

You're doing everything manually:
- Checking whether arguments exist using len(args).
- Checking whether the command is commit.
- Checking whether -m exists.
- Extracting the message using args[3].
- Printing errors when something is missing.
Imagine doing this for 20 Git commands!

That's why argparse exists.
'''