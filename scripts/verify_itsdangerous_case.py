"""Re-run the generic verifier against the portable itsdangerous case-study copy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repo_distiller.jsonio import read_json  # noqa: E402
from repo_distiller.schemas import TeachingSpec  # noqa: E402
from repo_distiller.verification import verify_project  # noqa: E402


CASE = ROOT / "case-studies" / "itsdangerous"
PROJECT = CASE / "toy-itsdangerous"
SPEC = CASE / "teaching-spec.json"
DEFAULT_REPORT = CASE / "verification.json"


def portable(report: dict[str, object]) -> dict[str, object]:
    report["project"] = "case-studies/itsdangerous/toy-itsdangerous"
    for command in report["commands"]:
        command["argv"] = [
            "<python>" if item == sys.executable else item for item in command["argv"]
        ]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="refresh case-studies/itsdangerous/verification.json",
    )
    args = parser.parse_args(argv)
    spec = TeachingSpec.from_dict(read_json(SPEC))
    report = portable(verify_project(PROJECT, spec))
    if args.write_evidence:
        DEFAULT_REPORT.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"itsdangerous case verification passed; wrote {DEFAULT_REPORT}")
    else:
        print(
            "itsdangerous case verification passed: "
            f"{len(report['commands'])} commands, "
            f"{report['metrics']['python_source_lines']} production lines, "
            f"source {report['project_digest']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
