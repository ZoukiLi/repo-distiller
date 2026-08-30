"""Command-line interface for the teaching workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from toyuv.environment import Environment
from toyuv.errors import ToyuvError
from toyuv.lockfile import read_lock
from toyuv.operations import format_tree, lock_project, sync_project
from toyuv.project import add_dependencies, discover_project, init_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="toyuv", description="A teaching-sized package manager")
    parser.add_argument("--version", action="version", version="toyuv 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a project")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--name")

    add = commands.add_parser("add", help="add dependencies, then lock and sync")
    add.add_argument("requirements", nargs="+")
    add.add_argument("--no-sync", action="store_true")

    lock = commands.add_parser("lock", help="resolve dependencies into toyuv.lock")
    lock.add_argument("--check", action="store_true")
    lock.add_argument("--upgrade", action="store_true")

    sync = commands.add_parser("sync", help="make the environment match the lockfile")
    sync.add_argument("--locked", action="store_true")
    sync.add_argument("--frozen", action="store_true")
    sync.add_argument("--inexact", action="store_true")

    run = commands.add_parser("run", help="lock, sync, then execute a command")
    run.add_argument("--locked", action="store_true")
    run.add_argument("--frozen", action="store_true")
    run.add_argument("program", nargs=argparse.REMAINDER)

    commands.add_parser("tree", help="show the dependency tree from the current lockfile")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except ToyuvError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        project = init_project(Path(args.path), args.name)
        print(f"Initialized {project.name} at {project.root}")
        return 0

    project = discover_project()
    if args.command == "add":
        original = project.pyproject_path.read_bytes()
        project = add_dependencies(project, args.requirements)
        try:
            outcome = lock_project(project)
        except ToyuvError:
            # Resolution failure must not leave an impossible requirement in project metadata.
            project.pyproject_path.write_bytes(original)
            raise
        print(f"Lockfile {outcome.action}: {project.lock_path}")
        if not args.no_sync:
            _, changes = sync_project(project)
            _print_changes(changes)
        return 0

    if args.command == "lock":
        outcome = lock_project(project, check=args.check, upgrade=args.upgrade)
        print(f"Lockfile {outcome.action}: {project.lock_path}")
        return 0

    if args.command == "sync":
        outcome, changes = sync_project(
            project,
            locked=args.locked,
            frozen=args.frozen,
            exact=not args.inexact,
        )
        print(f"Lockfile {outcome.action}: {project.lock_path}")
        _print_changes(changes)
        return 0

    if args.command == "run":
        command = list(args.program)
        if command and command[0] == "--":
            command.pop(0)
        _, changes = sync_project(project, locked=args.locked, frozen=args.frozen, exact=False)
        _print_changes(changes)
        # Child processes inherit stdout but not Python's userspace buffer. Flushing preserves the
        # intuitive order: synchronization messages appear before the command's own output.
        sys.stdout.flush()
        return Environment(project.environment_path).run(command)

    if args.command == "tree":
        lock = read_lock(project.lock_path)
        print(format_tree(lock))
        return 0
    raise AssertionError(f"unhandled command {args.command}")


def _print_changes(changes: list[object]) -> None:
    if not changes:
        print("Environment already matches the lockfile")
        return
    for change in changes:
        action = getattr(change, "action")
        name = getattr(change, "name")
        version = getattr(change, "version")
        print(f"{action.capitalize()} {name}=={version}")
