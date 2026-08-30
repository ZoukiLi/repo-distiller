"""Expected failures exposed by the command-line interface."""


class DistillerError(Exception):
    """Base class for failures that should not display a traceback by default."""


class SchemaError(DistillerError):
    """A versioned artifact is invalid or unsupported."""


class RepositoryError(DistillerError):
    """A source repository cannot be prepared or inspected safely."""


class CollectorError(DistillerError):
    """A deterministic evidence collector failed."""


class PlanningError(DistillerError):
    """Evidence is insufficient to compile a teaching specification."""


class SynthesisError(DistillerError):
    """An artifact backend failed or returned an incomplete project."""


class VerificationError(DistillerError):
    """A generated teaching project does not satisfy its contract."""
