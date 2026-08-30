from contextlib import chdir, redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest

from toyuv.cli import main
from toyuv.project import init_project, load_project


class CliTests(unittest.TestCase):
    def test_failed_add_restores_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "demo")
            with chdir(project.root), redirect_stderr(io.StringIO()) as stderr:
                status = main(
                    ["add", "greet-demo>=2", "legacy-demo", "--no-sync"]
                )
            self.assertEqual(status, 2)
            self.assertIn("cannot select a version", stderr.getvalue())
            self.assertEqual(load_project(project.root).dependencies, ())
            self.assertFalse(project.lock_path.exists())


if __name__ == "__main__":
    unittest.main()
