"""Package genuine dependency AAR resources for host Android UI tests."""
from pathlib import Path
import hashlib
import os
import subprocess
import xml.etree.ElementTree as ET
import zipfile


def compile_ui_resources(classpath_file, work, java_home, candidate=None, config=None):
    config = config or {}
    directory = Path(work) / "android-ui-resources"
    directory.mkdir()
    sdk = Path.home() / "Library/Android/sdk"
    aapt = sdk / "build-tools/36.0.0/aapt2"
    android = sdk / "platforms/android-36/android.jar"
    packages, compiled, provenance = [], [], []
    seen = set()
    for entry in Path(classpath_file).read_text().strip().split(os.pathsep):
        aar = Path(entry).with_suffix(".aar")
        if not aar.is_file() or aar.resolve() in seen:
            continue
        seen.add(aar.resolve())
        with zipfile.ZipFile(aar) as archive:
            manifest = ET.fromstring(archive.read("AndroidManifest.xml"))
            package = manifest.attrib["package"]
            if package not in packages:
                packages.append(package)
            resources = [name for name in archive.namelist() if name.startswith("res/") and not name.endswith("/")]
            if not resources:
                continue
            module = directory / f"library-{len(compiled)}"
            for name in resources:
                if ".." in Path(name).parts:
                    raise ValueError(f"Invalid AAR resource path: {name}")
                destination = module / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))
            output = directory / f"library-{len(compiled)}.zip"
            subprocess.run([str(aapt), "compile", "--dir", str(module / "res"), "-o", str(output)],
                           check=True, capture_output=True, text=True)
            compiled.append(output)
            provenance.append({"path": str(aar), "sha256": hashlib.sha256(aar.read_bytes()).hexdigest()})
    for index, specification in enumerate(config.get("resources", [])):
        if candidate is None:
            raise ValueError("Candidate resource packaging requires a candidate reader")
        packages.append(specification["package"])
        module = directory / f"candidate-{index}"
        for path in specification["files"]:
            relative = path.split("/res/", 1)[1]
            if ".." in Path(relative).parts:
                raise ValueError(f"Invalid candidate resource path: {path}")
            destination = module / "res" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(candidate.read(path))
        output = directory / f"candidate-{index}.zip"
        subprocess.run([str(aapt), "compile", "--dir", str(module / "res"), "-o", str(output)],
                       check=True, capture_output=True, text=True)
        compiled.append(output)
    manifest = directory / "AndroidManifest.xml"
    android_ns = "http://schemas.android.com/apk/res/android"
    ET.register_namespace("android", android_ns)
    root = ET.Element("manifest", {"package": "runtime.evaluator.ui"})
    ET.SubElement(root, "uses-sdk", {f"{{{android_ns}}}minSdkVersion": "24", f"{{{android_ns}}}targetSdkVersion": "36"})
    app = ET.SubElement(root, "application", {f"{{{android_ns}}}theme": "@android:style/Theme.Material.Light.NoActionBar"})
    ET.SubElement(app, "activity", {f"{{{android_ns}}}name": "androidx.activity.ComponentActivity", f"{{{android_ns}}}exported": "true"})
    ET.ElementTree(root).write(manifest, encoding="utf-8", xml_declaration=True)
    java = directory / "java"
    classes = directory / "classes"
    java.mkdir()
    classes.mkdir()
    apk = directory / "resources.apk"
    overlays = [argument for path in compiled for argument in ("-R", str(path))]
    subprocess.run([str(aapt), "link", "-I", str(android), "--manifest", str(manifest), "--java", str(java),
                    "--extra-packages", ":".join(dict.fromkeys(packages)), "--auto-add-overlay", "-o", str(apk), *overlays],
                   check=True, capture_output=True, text=True)
    for package, fields in config.get("buildConfig", {}).items():
        destination = java / package.replace(".", "/") / "BuildConfig.java"
        destination.parent.mkdir(parents=True, exist_ok=True)
        declarations = []
        for name, value in fields.items():
            if not isinstance(value, bool):
                raise ValueError("Only explicit boolean BuildConfig fields are supported")
            declarations.append(f"public static final boolean {name} = {str(value).lower()};")
        destination.write_text(f"package {package};\npublic final class BuildConfig {{\n" + "\n".join(declarations) + "\n}\n")
    subprocess.run([str(Path(java_home) / "bin/javac"), "-d", str(classes), *map(str, java.rglob("*.java"))],
                   check=True, capture_output=True, text=True)
    jar = directory / "ui-resource-bindings.jar"
    assets = directory / "assets"
    assets.mkdir()
    with zipfile.ZipFile(jar, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in classes.rglob("*.class"):
            archive.write(path, str(path.relative_to(classes)))
        archive.writestr("com/android/tools/test_config.properties", "\n".join([
            f"android_merged_manifest={manifest}", f"android_merged_resources={directory}",
            f"android_merged_assets={assets}", f"android_resource_apk={apk}",
            "android_custom_package=runtime.evaluator.ui", "",
        ]))
    return jar, provenance
