"""Link unchanged candidate and real AAR resources for Robolectric UI slices.

Call after android_robolectric_dependencies.prepare(config, work), under the
shared Android build lock. The returned jar contains aapt2-generated R classes
and Robolectric test_config.properties pointing at the linked resource APK.
config.resources and config.buildConfig have the same shape as the domain
resource compiler. AARs come from work/robolectric-classpath.txt; all consumed
candidate resources and AARs are hashed in candidate.provenance.

This is test-Activity resource packaging, not an application build: library
manifests are not merged, assets are not loaded, and no UI classes are supplied.
Production composables and all framework/Compose classes must be real sources
or dependencies supplied by the caller. No semantic observations are made here.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile


def compile_resources(candidate, config, work, java_home):
    directory = work / "rendered-resources"
    directory.mkdir()
    sdk = Path.home() / "Library/Android/sdk"
    aapt = sdk / "build-tools/36.0.0/aapt2"
    android = sdk / "platforms/android-36/android.jar"
    packages = set()
    compiled = []
    artifacts = []
    seen = set()

    def run(command):
        result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def compile_directory(source):
        if not any(path.is_file() for path in source.rglob("*")):
            return
        target = directory / f"compiled-{len(compiled)}.zip"
        run([aapt, "compile", "--dir", source, "-o", target])
        compiled.append(target)

    classpath = work / "robolectric-classpath.txt"
    for value in classpath.read_text().strip().split(os.pathsep):
        artifact = Path(value)
        if artifact.suffix == ".jar":
            artifact = artifact.with_suffix(".aar")
        if artifact.suffix != ".aar" or not artifact.is_file():
            continue
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        artifacts.append({"path": str(artifact), "sha256": digest})
        source = directory / f"dependency-{len(artifacts)}" / "res"
        source.mkdir(parents=True)
        with zipfile.ZipFile(artifact) as archive:
            manifest = ET.fromstring(archive.read("AndroidManifest.xml"))
            package = manifest.get("package")
            if package:
                packages.add(package)
            for name in archive.namelist():
                if not name.startswith("res/") or name.endswith("/"):
                    continue
                destination = source / name.removeprefix("res/")
                if not destination.resolve().is_relative_to(source.resolve()):
                    raise ValueError(f"Unsafe AAR resource: {name}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))
        compile_directory(source)

    for index, module in enumerate(config.get("resources", [])):
        packages.add(module["package"])
        source = directory / f"candidate-{index}" / "res"
        source.mkdir(parents=True)
        for path in module["files"]:
            destination = source / path.split("/res/", 1)[1]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(candidate.read(path))
        compile_directory(source)

    manifest = directory / "AndroidManifest.xml"
    tree = ET.Element("manifest", {"package": "runtime.evaluator.resources",
                                  "xmlns:android": "http://schemas.android.com/apk/res/android"})
    ET.SubElement(tree, "uses-sdk", {"android:minSdkVersion": "24", "android:targetSdkVersion": "36"})
    ET.SubElement(tree, "application", {"android:theme": "@android:style/Theme.Material.Light.NoActionBar"})
    ET.ElementTree(tree).write(manifest, encoding="utf-8", xml_declaration=True)
    java = directory / "java"
    java.mkdir()
    resource_apk = directory / "resources.apk"
    command = [aapt, "link", "-I", android, "--manifest", manifest, "--java", java,
               "--auto-add-overlay", "--extra-packages", ":".join(sorted(packages)), "-o", resource_apk]
    for artifact in compiled:
        command.extend(["-R", artifact])
    run(command)
    for package, fields in config.get("buildConfig", {}).items():
        destination = java / package.replace(".", "/") / "BuildConfig.java"
        destination.parent.mkdir(parents=True, exist_ok=True)
        declarations = []
        for name, value in fields.items():
            if not isinstance(value, bool):
                raise ValueError("Only explicit boolean build-variant fields are supported")
            declarations.append(f"public static final boolean {name} = {str(value).lower()};")
        destination.write_text(f"package {package};\npublic final class BuildConfig {{\n" + "\n".join(declarations) + "\n}\n")
    classes = directory / "classes"
    classes.mkdir()
    run([java_home / "bin/javac", "-d", classes, *sorted(java.rglob("*.java"))])
    assets = directory / "assets"
    assets.mkdir()
    merged = directory / "res"
    merged.mkdir()
    jar = directory / "resources.jar"
    with zipfile.ZipFile(jar, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(classes.rglob("*.class")):
            archive.write(path, str(path.relative_to(classes)))
        archive.writestr("com/android/tools/test_config.properties", "\n".join([
            f"android_merged_manifest={manifest}", f"android_merged_resources={merged}",
            f"android_merged_assets={assets}", f"android_resource_apk={resource_apk}",
            "android_custom_package=runtime.evaluator.resources", "",
        ]))
    candidate.provenance["resourceDependencies"] = artifacts
    candidate.provenance["resourceApkSha256"] = hashlib.sha256(resource_apk.read_bytes()).hexdigest()
    return jar
