from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_TEST_DIR = ROOT / "state_tests"
REQUIRED_TOP_LEVEL_KEYS = (
    "version:",
    "task:",
    "source:",
    "platform_bindings:",
    "state_dimensions:",
    "cases:",
)


def get_case_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [
        line.strip().removeprefix("- id:").strip()
        for line in text.splitlines()
        if line.startswith("  - id:")
    ]


def validate_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if f"\n{key}" not in f"\n{text}":
            errors.append(f"missing top-level key {key}")

    case_ids = get_case_ids(path)
    if not case_ids:
        errors.append("missing cases")

    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicates:
        errors.append(f"duplicate case ids: {', '.join(duplicates)}")

    if "platform_bindings:\n  android:" not in text or "\n  arkts:" not in text:
        errors.append("missing android/arkts platform bindings")

    return errors


def main() -> int:
    files = sorted(STATE_TEST_DIR.glob("elementx-state-test*.yaml"))
    if len(files) != 5:
        print(f"expected 5 state-test YAML files, found {len(files)}", file=sys.stderr)
        return 1

    failed = False
    for path in files:
        errors = validate_file(path)
        if errors:
            failed = True
            print(f"{path.name}: FAIL")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"{path.name}: OK ({len(get_case_ids(path))} cases)")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
