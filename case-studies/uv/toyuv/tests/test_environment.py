from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest

from toyuv.environment import Environment
from toyuv.errors import EnvironmentError
from toyuv.operations import lock_project, registry_for
from toyuv.project import add_dependencies, init_project, load_project


class EnvironmentTests(unittest.TestCase):
    def test_sync_installs_importable_files_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "demo")
            project = add_dependencies(project, ["greet-demo"])
            lock = lock_project(project).lock
            environment = Environment(project.environment_path)

            changes = environment.sync(lock, registry_for(project))
            self.assertEqual({change.name for change in changes}, {"greet-demo", "color-demo"})
            self.assertEqual(environment.sync(lock, registry_for(project)), [])

            completed = subprocess.run(
                [
                    str(environment.python_path),
                    "-c",
                    "from greet_demo import greet; print(greet('test'))",
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.strip(), "<blue>Welcome, test!</blue>")

    def test_exact_sync_removes_packages_not_in_new_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "demo")
            project = add_dependencies(project, ["greet-demo"])
            environment = Environment(project.environment_path)
            environment.sync(lock_project(project).lock, registry_for(project))

            text = project.pyproject_path.read_text(encoding="utf-8")
            project.pyproject_path.write_text(
                text.replace('    "greet-demo",\n', ""), encoding="utf-8"
            )
            project = load_project(project.root)
            changes = environment.sync(
                lock_project(project).lock, registry_for(project), exact=True
            )
            self.assertEqual({change.action for change in changes}, {"removed"})

    def test_sync_rejects_a_tampered_dependency_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = init_project(Path(directory) / "demo")
            project = add_dependencies(project, ["greet-demo"])
            lock = lock_project(project).lock
            tampered = replace(
                lock,
                packages=tuple(
                    package for package in lock.packages if package.name != "color-demo"
                ),
            )
            with self.assertRaises(EnvironmentError):
                Environment(project.environment_path).sync(tampered, registry_for(project))


if __name__ == "__main__":
    unittest.main()
