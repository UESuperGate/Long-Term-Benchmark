#!/usr/bin/env python3
"""Audit the actual host-versus-Android WYSIWYG ABI without building Rust."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "state_tests/runtime/android/11_room_upgrade_navigation/messages/.native"
JAVA = Path("/opt/homebrew/opt/openjdk@21/bin/javap")


def record(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing existing audit")
    jar = ROOT / "state_tests/runtime/android/08_threads/.dependencies/aar-classes/wysiwyg-2.38.3-466526be036d.jar"
    aar = ROOT / "state_tests/runtime/android/08_threads/.dependencies/maven-repository/io/element/android/wysiwyg/2.38.3/wysiwyg-2.38.3.aar"
    declarations = subprocess.check_output([str(JAVA), "-classpath", str(jar), "-p", "uniffi.wysiwyg_composer.UniffiLib"], text=True)
    symbols = [line.strip() for line in declarations.splitlines() if any(token in line for token in
        ("mentiondetector", "new_mention_detector", "uniffi_contract_version"))]
    android = []
    with zipfile.ZipFile(aar) as archive:
        for name in archive.namelist():
            if name.startswith("jni/") and name.endswith("libuniffi_wysiwyg_composer.so"):
                data = archive.read(name)
                android.append({"archiveEntry": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                "fileMagicHex": data[:4].hex(), "format": "ELF" if data[:4] == b"\x7fELF" else "unknown"})
    source = BASE / "matrix-rich-text-editor"
    sdk_file = source / "platforms/android/library/src/main/java/io/element/android/wysiwyg/EditorStyledTextView.kt"
    host = BASE / "target/debug/libuniffi_wysiwyg_composer.dylib"
    previous = json.loads((BASE / "provenance.json").read_text()) if (BASE / "provenance.json").exists() else None
    jna = BASE / "jna-5.17.0.jar"
    with zipfile.ZipFile(jna) as archive:
        dispatch = archive.read("com/sun/jna/darwin-aarch64/libjnidispatch.jnilib")
    result = {"sdk": "io.element.android:wysiwyg:2.38.3", "sourceCommit": subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip(),
        "hostArchitecture": subprocess.check_output(["uname", "-m"], text=True).strip(),
        "bindingMechanism": "JNA loads UniFFI C ABI; this is not a missing Java native navigation implementation",
        "expectedHostLibrary": str(host), "expectedHostLibraryExists": host.exists(),
        "previousNativeArtifact": previous.get("library") if previous else None,
        "compiledBindingJar": record(jar), "androidAar": record(aar), "androidLibraries": android,
        "actualBindingDeclarations": symbols,
        "desktopJna": record(jna), "desktopJnaDispatch": {"archiveEntry": "com/sun/jna/darwin-aarch64/libjnidispatch.jnilib",
            "bytes": len(dispatch), "sha256": hashlib.sha256(dispatch).hexdigest()},
        "upstreamSdkSwitch": {"source": record(sdk_file), "property": "EditorStyledTextView.isNativeCodeEnabled",
            "scope": "SDK optional Rust mention recognition; real styled renderer remains active"},
        "rootCause": "Host native build artifacts were hash-cleaned under SSD pressure. Android AAR contains Android ELF libraries, not the required macOS arm64 Mach-O library. The JNA Darwin dispatcher itself is present.",
        "rustBuildStarted": False, "applicationBuildStarted": False, "navigationReplaced": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"expectedHostLibraryExists": host.exists(), "actualAbiDeclarations": len(symbols), "androidArtifacts": len(android)}))


if __name__ == "__main__":
    main()
