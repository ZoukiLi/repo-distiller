import tempfile
from pathlib import Path
import unittest

from toyuv.errors import LockfileError
from toyuv.lockfile import read_lock
from toyuv.operations import format_tree, lock_project
from toyuv.project import add_dependencies, init_project, load_project


class ProjectAndLockTests(unittest.TestCase):
    def test_add_updates_only_dependency_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "demo")
            original_hash = project.content_hash
            project = add_dependencies(project, ["greet-demo>=1"])
            self.assertNotEqual(project.content_hash, original_hash)
            self.assertEqual([item.name for item in project.dependencies], ["greet-demo"])
            self.assertIn('name = "demo"', project.pyproject_path.read_text(encoding="utf-8"))

    def test_lock_is_created_then_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "demo")
            project = add_dependencies(project, ["greet-demo"])
            first = lock_project(project)
            second = lock_project(load_project(project.root))
            self.assertEqual(first.action, "created")
            self.assertEqual(second.action, "unchanged")
            lock = read_lock(project.lock_path)
            self.assertEqual(len(lock.packages), 2)
            self.assertTrue(format_tree(lock).isascii())

    def test_locked_mode_rejects_stale_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "demo")
            lock_project(project)
            project = add_dependencies(project, ["greet-demo"])
            with self.assertRaises(LockfileError):
                lock_project(project, check=True)

    def test_invalid_existing_lock_is_not_silently_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "demo")
            project.lock_path.write_text("not json", encoding="utf-8")
            with self.assertRaises(LockfileError):
                lock_project(project)


if __name__ == "__main__":
    unittest.main()
