import sys

from .model import CONCEPTS


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "concepts":
        for concept in CONCEPTS:
            print(f"{concept['id']}: {concept['name']}")
        return 0
    print("usage: python -m toy_itsdangerous concepts")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
