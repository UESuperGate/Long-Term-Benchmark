"""Produce explicit immutable Kotlin source manifests from production entrypoints.

Only dependency discovery uses token matching. Runtime compilation always loads
the full unmodified files from the candidate and records their SHA-256 hashes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile


def closure(repository: Path, ref: str, seeds: list[str]) -> list[str]:
    archive = subprocess.check_output([
        "git", "-C", str(repository), "-c", "filter.lfs.process=", "-c", "filter.lfs.smudge=",
        "-c", "filter.lfs.required=false", "archive", ref, "features", "libraries", "services",
    ])
    records = {}
    symbols = defaultdict(set)
    packages = defaultdict(dict)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for entry in tree:
            if not entry.name.endswith(".kt") or "/src/main/" not in entry.name:
                continue
            code = tree.extractfile(entry).read().decode()
            package = re.search(r"^package ([\w.]+)", code, re.M)
            if not package:
                continue
            package = package[1]
            imports = re.findall(r"^import ([\w.*]+)", code, re.M)
            clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.S)
            names = set(re.findall(r"^(?:(?:public|internal|private|open|sealed|data|enum|annotation|value|fun|abstract|inline) )*(?:class|interface|object|typealias) (\w+)", clean, re.M))
            names.update(re.findall(r"^(?:(?:public|internal|private|suspend|inline|tailrec|operator|infix)\s+)*fun (?:<[^\n]+?>\s+)?(?:[^\n(]+\.)?(\w+)\(", clean, re.M))
            names.update(re.findall(r"^(?:internal |private |public )?(?:const )?(?:val|var) (?:[^\n ]+\.)?(\w+)\b", clean, re.M))
            records[entry.name] = package, imports, clean
            for name in names:
                symbols[package + "." + name].add(entry.name)
                packages[package].setdefault(name, set()).add(entry.name)
    selected = set()
    pending = list(seeds)
    while pending:
        path = pending.pop()
        if path in selected:
            continue
        if path not in records:
            raise ValueError(f"Production entrypoint absent in selected tree: {path}")
        selected.add(path)
        package, imports, clean = records[path]
        tokens = set(re.findall(r"\b\w+\b", clean))
        for name, paths in packages[package].items():
            if name in tokens:
                pending.extend(paths - selected)
        for imported in imports:
            if not imported.startswith("io.element.android.") or imported.startswith("io.element.android.wysiwyg."):
                continue
            lookup = imported
            while lookup and lookup not in symbols:
                lookup = lookup.rpartition(".")[0]
            if lookup:
                pending.extend(symbols[lookup] - selected)
    return sorted(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    config["sources"] = closure(args.source, args.ref, config["entrypoints"])
    args.config.write_text(json.dumps(config, indent=2) + "\n")
    print(json.dumps({"productionFiles": len(config["sources"]), "configuration": str(args.config)}))


if __name__ == "__main__":
    main()
