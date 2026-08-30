"""A deliberately small requirement language.

Real Python packaging uses PEP 440 versions and PEP 508 requirements. Those standards include
pre-releases, epochs, local versions, URLs, extras, and environment markers. Implementing all of
that would hide the resolver's central idea, so toyuv accepts numeric versions and five comparison
operators only. The limitation is checked eagerly instead of being silently misinterpreted.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering
import re

from toyuv.errors import RequirementError


_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?(?:\.(0|[1-9][0-9]*))?$")
_SPECIFIER_RE = re.compile(r"^(==|>=|<=|>|<)\s*(.+)$")


def normalize_name(name: str) -> str:
    """Apply the important part of Python's package-name normalization.

    Treating `My_Package`, `my.package`, and `my-package` as one identity prevents the resolver
    and installer from selecting or installing the same logical package more than once.
    """

    return re.sub(r"[-_.]+", "-", name).lower()


@total_ordering
@dataclass(frozen=True)
class Version:
    """Comparable three-component numeric version used by the toy registry."""

    parts: tuple[int, int, int]

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = _VERSION_RE.fullmatch(value.strip())
        if not match:
            raise RequirementError(
                f"unsupported version {value!r}; toyuv accepts forms like 1, 1.2, or 1.2.3"
            )
        parts = tuple(int(part or 0) for part in match.groups())
        return cls(parts)  # type: ignore[arg-type]

    def __str__(self) -> str:
        return ".".join(str(part) for part in self.parts)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.parts < other.parts


@dataclass(frozen=True)
class Specifier:
    operator: str
    version: Version

    def allows(self, candidate: Version) -> bool:
        return {
            "==": candidate == self.version,
            ">=": candidate >= self.version,
            "<=": candidate <= self.version,
            ">": candidate > self.version,
            "<": candidate < self.version,
        }[self.operator]

    def __str__(self) -> str:
        return f"{self.operator}{self.version}"


@dataclass(frozen=True)
class Requirement:
    name: str
    specifiers: tuple[Specifier, ...] = ()

    @classmethod
    def parse(cls, value: str) -> "Requirement":
        text = value.strip()
        name_match = _NAME_RE.match(text)
        if not name_match:
            raise RequirementError(f"invalid requirement {value!r}")

        raw_name = name_match.group(0)
        remainder = text[name_match.end() :].strip()
        specifiers: list[Specifier] = []
        if remainder:
            for raw_specifier in remainder.split(","):
                match = _SPECIFIER_RE.fullmatch(raw_specifier.strip())
                if not match:
                    raise RequirementError(
                        f"unsupported requirement {value!r}; extras, URLs, markers, "
                        "and ~= are omitted"
                    )
                specifiers.append(Specifier(match.group(1), Version.parse(match.group(2))))

        return cls(normalize_name(raw_name), tuple(specifiers))

    def allows(self, version: Version) -> bool:
        return all(specifier.allows(version) for specifier in self.specifiers)

    def __str__(self) -> str:
        return self.name + ",".join(str(specifier) for specifier in self.specifiers)
