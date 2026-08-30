"""Errors that are safe to show directly to a CLI user."""


class ToyuvError(Exception):
    """Base class for expected package-manager failures.

    Keeping expected errors separate from programming bugs lets the CLI print a concise
    message for a dependency conflict while still exposing a traceback for an actual bug.
    """


class ProjectError(ToyuvError):
    """The current directory is not a valid toyuv project."""


class RequirementError(ToyuvError):
    """A requirement uses syntax outside toyuv's deliberately small subset."""


class ResolutionError(ToyuvError):
    """No single set of package versions satisfies every collected constraint."""


class LockfileError(ToyuvError):
    """The lockfile is missing, stale, or structurally invalid."""


class RegistryError(ToyuvError):
    """The local package index contains invalid or unsafe metadata."""


class EnvironmentError(ToyuvError):
    """The virtual environment cannot be synchronized safely."""
