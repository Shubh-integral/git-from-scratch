import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "main.py"


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def run_cli(self, *arguments, cwd=None, expected=0):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *arguments],
            cwd=cwd or self.root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def test_help_and_errors_do_not_initialize_repository(self):
        self.assertIn("checkout", self.run_cli().stdout)
        self.assertIn("status", self.run_cli("--help").stdout)
        self.run_cli("status", expected=1)
        self.run_cli("add", "missing", expected=1)
        self.assertFalse((self.root / ".mygit").exists())

    def test_full_command_workflow(self):
        self.run_cli("init")
        self.run_cli("init")
        file = self.root / "hello.txt"
        file.write_text("main")
        self.assertIn("Untracked files:", self.run_cli("status").stdout)
        self.run_cli("add", "hello.txt")
        self.assertIn("added: hello.txt", self.run_cli("status").stdout)
        self.run_cli("commit", "-m", "First")
        self.assertIn("Working tree clean", self.run_cli("status").stdout)
        self.assertIn("* main", self.run_cli("branch").stdout)

        self.run_cli("branch", "saved")
        self.run_cli("checkout", "-b", "feature")
        file.write_text("feature")
        self.run_cli("add", ".")
        self.run_cli("commit", "-m", "Feature")
        self.run_cli("checkout", "main")
        self.assertEqual(file.read_text(), "main")
        self.run_cli("branch", "-d", "saved")
        self.assertNotIn("saved", self.run_cli("branch").stdout)
        self.run_cli("checkout", "feature")
        self.assertEqual(file.read_text(), "feature")

    def test_add_from_subfolder_uses_the_callers_directory(self):
        self.run_cli("init")
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "hello.txt").write_text("hello")
        (self.root / "top.txt").write_text("top")
        self.run_cli("add", ".", cwd=docs)
        index = json.loads((self.root / ".mygit/index").read_text())
        self.assertEqual(set(index), {"docs/hello.txt"})
        self.run_cli("commit", "-m", "Docs", cwd=docs)
        self.assertIn("top.txt", self.run_cli("status", cwd=docs).stdout)

    def test_cli_validation(self):
        self.run_cli("init")
        self.run_cli("commit", expected=2)
        self.run_cli("branch", "-d", expected=2)
        self.run_cli("checkout", "missing", expected=1)
        self.run_cli("branch", "before-first-commit", expected=1)


if __name__ == "__main__":
    unittest.main()
