#!/usr/bin/env python3
"""
Audit state-test polarity for the incremental benchmark.

Every testcase in this benchmark must encode a final-version requirement:
the corresponding base mirror should fail it, and the final mirror should pass
it. This catches accidentally added base-negative/control cases that would make
the base pass and pollute the benchmark signal.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
STATE_TEST_DIR = ROOT / "state_tests"
REPORT = ROOT / "verification_reports" / "state_test_polarity_audit.md"


FORBIDDEN_PATTERNS = [
    "base_negative",
    "release_semantics: base",
    "Base mirrors should fail if",
    "base 语义中",
    "base 版本语义中",
]


def main() -> int:
    findings: list[tuple[str, int, str, str]] = []
    total_cases = 0
    final_semantics = 0

    for path in sorted(STATE_TEST_DIR.glob("elementx-state-test*.yaml")):
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("- id:"):
                total_cases += 1
            if stripped == "release_semantics: final":
                final_semantics += 1
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in line:
                    findings.append((path.name, index, pattern, stripped))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    md: list[str] = []
    md.append("# State-Test Polarity Audit")
    md.append("")
    md.append("Benchmark invariant: every testcase is a final-requirement assertion, so base mirrors should fail and final mirrors should pass.")
    md.append("")
    md.append(f"- Total cases: {total_cases}")
    md.append(f"- Explicit final semantics markers: {final_semantics}")
    md.append(f"- Forbidden polarity findings: {len(findings)}")
    md.append("")

    if findings:
        md.append("## Findings")
        for filename, line_no, pattern, text in findings:
            md.append(f"- `{filename}:{line_no}` matched `{pattern}`: `{text}`")
    else:
        md.append("## Result")
        md.append("")
        md.append("PASS: no base-oriented state-test cases were found.")

    REPORT.write_text("\n".join(md) + "\n", encoding="utf-8")

    if findings:
        print(f"FAIL: {len(findings)} polarity issue(s). See {REPORT}")
        return 1
    print(f"PASS: {total_cases} cases are final-oriented. See {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
