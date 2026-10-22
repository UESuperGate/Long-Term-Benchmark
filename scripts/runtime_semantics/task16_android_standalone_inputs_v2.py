"""Offline, role-free capture of an actual standalone Android candidate.

No Git/ref fallback and no dependency resolution. A capture is input evidence,
never compilation, semantic evidence, or permission to start a worker.
"""
from collections import defaultdict
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile


EXCLUDED_DIRS = {".git", ".gradle", ".idea", "build", "node_modules", ".kotlin", ".cxx", ".externalNativeBuild"}
PRIVATE_FILES = {"local.properties", "key.properties", "keystore.properties", ".env"}
MAX_BYTES = 512 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(source):
    source = Path(source).resolve(strict=True)
    files, excluded = {}, []
    total = 0
    for directory, directories, names in os.walk(source, followlinks=False):
        parent = Path(directory)
        for name in list(directories):
            path = parent / name
            if path.is_symlink():
                raise ValueError("Symlink candidate directory: " + str(path))
            if name in EXCLUDED_DIRS:
                excluded.append(path.relative_to(source).as_posix() + "/")
                directories.remove(name)
        for name in sorted(names):
            path = parent / name
            relative = path.relative_to(source).as_posix()
            if name == ".git" or name in PRIVATE_FILES or name.startswith(".env.") or path.suffix.lower() in {".jks", ".keystore", ".p12", ".pem", ".key"}:
                excluded.append(relative)
                continue
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode) or path.is_symlink():
                raise ValueError("Non-regular candidate input: " + relative)
            total += before.st_size
            if total > MAX_BYTES:
                raise ValueError("Standalone input exceeds bounded capture size")
            data = path.read_bytes()
            after = path.lstat()
            if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode):
                raise ValueError("Candidate changed during read: " + relative)
            # Do not publish accidental credentials embedded in tracked project files.
            if re.search(rb'(?:sk-(?:cp-)?[A-Za-z0-9_-]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)', data):
                raise ValueError("Credential-shaped input; capture refused: " + relative)
            files[relative] = (data, stat.S_IMODE(before.st_mode))
    for required in ("gradlew", "settings.gradle.kts", "gradle/libs.versions.toml"):
        if required not in files or not files[required][0].strip():
            raise ValueError("Missing actual standalone build input: " + required)
    return files, sorted(excluded)


def records(files):
    return [{"path": name, "bytes": len(data), "sha256": digest(data), "mode": mode}
            for name, (data, mode) in sorted(files.items())]


def tree_hash(rows):
    return digest(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode())


def capture(source, output):
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError("Retained input root must be outside candidate")
    files, excluded = inventory(source)
    rows = records(files)
    # Re-read the complete namespace, not only the originally selected Kotlin files.
    second, exclusions = inventory(source)
    if records(second) != rows or exclusions != excluded:
        raise ValueError("Candidate changed during complete capture")
    output.mkdir(parents=True, exist_ok=False)
    archive = output / "standalone-inputs.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        for name, (data, mode) in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode, entry.mtime = len(data), mode, 0
            stream.addfile(entry, io.BytesIO(data))
    receipt = {"schemaVersion": "task16-standalone-capture.v2", "source": str(source),
               "treeSha256": tree_hash(rows), "files": rows, "excluded": excluded,
               "archive": {"path": str(archive), "bytes": archive.stat().st_size, "sha256": digest(archive.read_bytes())},
               "semanticStatus": "not_scored", "compileStatus": "not_run", "runtimeStatus": "not_run",
               "bindingTier": "complete supplied standalone input, not immutable-ref role selection"}
    (output / "input.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def retained_files(receipt):
    archive = Path(receipt["archive"]["path"])
    if digest(archive.read_bytes()) != receipt["archive"]["sha256"]:
        raise ValueError("Retained archive hash mismatch")
    result = {}
    total = 0
    with tarfile.open(archive) as stream:
        for entry in stream:
            name = entry.name
            if not entry.isfile() or name in result or name.startswith("/") or ".." in Path(name).parts:
                raise ValueError("Invalid retained archive entry")
            total += entry.size
            if total > MAX_BYTES:
                raise ValueError("Retained input exceeds bounded capture size")
            result[name] = (stream.extractfile(entry).read(), entry.mode)
    if records(result) != receipt["files"] or tree_hash(records(result)) != receipt["treeSha256"]:
        raise ValueError("Retained complete input ledger mismatch")
    return result


def materialize(receipt, destination):
    """Restore exact captured regular inputs into a NEW root, without executing them."""
    files = retained_files(receipt)
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    for name, (data, mode) in sorted(files.items()):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)
    assert_unchanged(destination, dict(receipt, excluded=[]))
    return destination


def binary_ledger(paths):
    """Call BEFORE temporary build cleanup; this is not main bytewise verification."""
    rows = []
    for path in sorted(map(Path, paths)):
        if not path.is_file() or path.is_symlink():
            raise ValueError("Actual compiled binary unavailable before ledger: " + str(path))
        data = path.read_bytes()
        rows.append({"path": str(path.resolve()), "bytes": len(data), "sha256": digest(data)})
    if not rows:
        raise ValueError("Empty actual compiler binary ledger")
    return {"files": rows, "ledgerSha256": tree_hash(rows),
            "verificationTier": "worker capture before cleanup; independent main class bytes not asserted"}


def assert_unchanged(source, before):
    files, excluded = inventory(source)
    if records(files) != before["files"] or excluded != before["excluded"]:
        raise ValueError("Prospective candidate inputs changed; runtime is unscored")
    return tree_hash(records(files))


def closure(files, seeds):
    """Discover imports in the supplied retained bytes; compilation uses whole files."""
    index, symbols, packages = {}, defaultdict(set), defaultdict(dict)
    for path, (data, _) in files.items():
        if not path.endswith(".kt") or "/src/main/" not in path:
            continue
        code = data.decode()
        package = re.search(r"^package ([\w.]+)", code, re.M)
        if not package:
            continue
        package = package[1]
        clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.S)
        imports = re.findall(r"^import ([\w.*]+)", code, re.M)
        names = set(re.findall(r"^(?:(?:public|internal|private|open|sealed|data|enum|annotation|value|fun|abstract|inline) )*(?:class|interface|object|typealias) (\w+)", clean, re.M))
        names.update(re.findall(r"^(?:(?:public|internal|private|suspend|inline|tailrec|operator|infix)\s+)*fun (?:<[^\n]+?>\s+)?(?:[^\n(]+\.)?(\w+)\(", clean, re.M))
        names.update(re.findall(r"^(?:internal |private |public )?(?:const )?(?:val|var) (?:[^\n ]+\.)?(\w+)\b", clean, re.M))
        index[path] = package, imports, clean
        for name in names:
            symbols[package + "." + name].add(path)
            packages[package].setdefault(name, set()).add(path)
    pending, selected = list(seeds), set()
    while pending:
        path = pending.pop()
        if path in selected:
            continue
        if path not in index:
            raise ValueError("Unbound candidate production entrypoint (not semantic failure): " + path)
        selected.add(path)
        package, imports, clean = index[path]
        tokens = set(re.findall(r"\b\w+\b", clean))
        for name, paths in packages[package].items():
            if name in tokens:
                pending.extend(paths - selected)
        for imported in imports:
            if imported.endswith(".*"):
                for name, paths in packages[imported[:-2]].items():
                    if name in tokens:
                        pending.extend(paths - selected)
                continue
            lookup = imported
            while lookup and lookup not in symbols:
                lookup = lookup.rpartition(".")[0]
            if lookup:
                pending.extend(symbols[lookup] - selected)
    return sorted(selected)
