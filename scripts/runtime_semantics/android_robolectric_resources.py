"""Build real Android resource bindings from the selected candidate with aapt2."""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile


def compile_resources(candidate, config, work: Path, java_home: Path):
    modules = config.get("resources", [])
    build_config = config.get("buildConfig", {})
    if not modules and not build_config:
        return None
    directory = work / "android-resources"
    source = directory / "res"
    flat = directory / "flat"
    java = directory / "java"
    classes = directory / "classes"
    for path in (source, flat, java, classes):
        path.mkdir(parents=True, exist_ok=True)
    sdk = Path.home() / "Library/Android/sdk"
    aapt = sdk / "build-tools/36.0.0/aapt2"
    android = sdk / "platforms/android-36/android.jar"
    manifest = directory / "AndroidManifest.xml"
    tree = ET.Element("manifest", {"package": "runtime.evaluator.resources",
                                  "xmlns:android": "http://schemas.android.com/apk/res/android"})
    ET.SubElement(tree, "uses-sdk", {"android:minSdkVersion": "24", "android:targetSdkVersion": "36"})
    ET.SubElement(tree, "application")
    ET.ElementTree(tree).write(manifest, encoding="utf-8", xml_declaration=True)
    for index, module in enumerate(modules):
        for path in module["files"]:
            relative = path.split("/res/", 1)[1]
            folder, filename = relative.split("/", 1)
            if folder.startswith("values"):
                filename = f"module_{index}_{filename}"
            destination = source / folder / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(candidate.read(path))
            subprocess.run([str(aapt), "compile", "-o", str(flat), str(destination)], check=True, capture_output=True, text=True)
    resource_apk = directory / "resources.apk"
    if modules:
        subprocess.run([str(aapt), "link", "-I", str(android), "--manifest", str(manifest), "--java", str(java),
                        "--extra-packages", ":".join(module["package"] for module in modules),
                        "-o", str(resource_apk), *map(str, sorted(flat.glob("*.flat")))],
                       check=True, capture_output=True, text=True)
    for package, fields in build_config.items():
        destination = java / package.replace(".", "/") / "BuildConfig.java"
        destination.parent.mkdir(parents=True, exist_ok=True)
        body = f"package {package};\npublic final class BuildConfig {{\n"
        for name, value in fields.items():
            if not isinstance(value, bool):
                raise ValueError("Only explicitly selected boolean build-variant fields are supported")
            body += f"public static final boolean {name} = {str(value).lower()};\n"
        destination.write_text(body + "}\n")
    subprocess.run([str(java_home / "bin/javac"), "-d", str(classes), *map(str, sorted(java.rglob("*.java")))],
                   check=True, capture_output=True, text=True)
    jar = directory / "android-resource-bindings.jar"
    with zipfile.ZipFile(jar, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(classes.rglob("*.class")):
            archive.write(path, str(path.relative_to(classes)))
        if modules:
            assets = directory / "assets"
            assets.mkdir()
            properties = "\n".join([
                f"android_merged_manifest={manifest}", f"android_merged_resources={source}",
                f"android_merged_assets={assets}", f"android_resource_apk={resource_apk}",
                "android_custom_package=runtime.evaluator.resources", "",
            ])
            archive.writestr("com/android/tools/test_config.properties", properties)
    return jar
