from __future__ import annotations

from pathlib import Path


def write_sample_repository(root: Path) -> None:
    (root / "src" / "sampletool").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text(
        """[project]
name = "sampletool"
version = "0.1.0"
requires-python = ">=3.11"
""",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        """# Sample Tool

The tool stores named values and rejects duplicate names.

## Try it

```console
$ python -m sampletool list
```
""",
        encoding="utf-8",
    )
    (root / "src" / "sampletool" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "sampletool" / "store.py").write_text(
        '''"""Core storage mechanism."""

class DuplicateNameError(ValueError):
    pass


class Store:
    def __init__(self):
        self.values = {}

    def add(self, name, value):
        if name in self.values:
            raise DuplicateNameError(name)
        self.values[name] = value
''',
        encoding="utf-8",
    )
    (root / "src" / "sampletool" / "cli.py").write_text(
        '''"""Public command interface."""

from sampletool.store import Store


def main():
    store = Store()
    print(len(store.values))


if __name__ == "__main__":
    main()
''',
        encoding="utf-8",
    )
    (root / "tests" / "test_store.py").write_text(
        "from sampletool.store import Store\n\ndef test_add():\n    s = Store(); s.add('a', 1)\n",
        encoding="utf-8",
    )
