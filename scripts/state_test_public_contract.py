#!/usr/bin/env python3
"""Build the oracle-free state-transition contract exposed to coding agents."""

from __future__ import annotations

from pathlib import Path


BLOCK_KEYS = {
    (4, "runtime_oracle"),
    (4, "mutation_guards"),
    (4, "expect_ui"),
    (4, "parity_assertions"),
    (8, "to_state"),
    (8, "expect_ui"),
}
SCALAR_KEYS = {
    (4, "base_failure_signal"),
}


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def render_public_contract(text: str) -> str:
    """Remove evaluator outputs while retaining fixtures and transition inputs."""
    output = [
        "# Public benchmark input. Expected states and UI assertions are evaluator-private.",
        "# Implement production behavior from the requirement; do not add case-specific test code.",
    ]
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        indent = _indent(line)
        key = stripped.split(":", 1)[0] if ":" in stripped else ""
        if (indent, key) in SCALAR_KEYS:
            index += 1
            continue
        if (indent, key) in BLOCK_KEYS:
            block_indent = indent
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if candidate.strip() and _indent(candidate) <= block_indent:
                    break
                index += 1
            continue
        output.append(line)
        index += 1
    return "\n".join(output).rstrip() + "\n"


def write_public_contract(source: Path, destination: Path) -> None:
    destination.write_text(
        render_public_contract(source.read_text(encoding="utf-8-sig")),
        encoding="utf-8",
    )
