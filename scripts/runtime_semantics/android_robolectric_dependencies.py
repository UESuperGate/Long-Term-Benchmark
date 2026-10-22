"""Resolve real JVM/Android test dependencies, reusing Gradle and Maven caches.

Maven resolves dependencies only; it does not build the Android app. Downloads
and extracted AAR classes stay in the adapter's ignored .dependencies directory.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

GRADLE_CACHE = Path.home() / ".gradle/caches/modules-2/files-2.1"
MAVEN_CACHE = Path.home() / ".m2/repository"
MAVEN_VERSION = "3.9.9"


def download(url: str, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def maven(cache: Path) -> Path:
    existing = shutil.which("mvn")
    if existing:
        return Path(existing)
    executable = cache / f"apache-maven-{MAVEN_VERSION}/bin/mvn"
    if not executable.exists():
        archive = cache / f"apache-maven-{MAVEN_VERSION}-bin.tar.gz"
        url = f"https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/{MAVEN_VERSION}/{archive.name}"
        if not archive.exists():
            download(url, archive)
        with urllib.request.urlopen(url + ".sha512", timeout=30) as response:
            expected = response.read().decode().strip().split()[0]
        if hashlib.sha512(archive.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Maven distribution SHA-512 mismatch")
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                if not (cache / member.name).resolve().is_relative_to(cache.resolve()):
                    raise RuntimeError("Unsafe Maven archive path")
            bundle.extractall(cache)
    return executable


def seed_repository(repository: Path):
    """Link cached artifacts instead of duplicating their bytes."""
    for artifact in GRADLE_CACHE.glob("*/*/*/*/*"):
        if artifact.suffix not in (".jar", ".aar", ".pom"):
            continue
        group, name, version, _, filename = artifact.relative_to(GRADLE_CACHE).parts
        if artifact.suffix == ".aar":
            filename = f"{name}-{version}.aar"
        target = repository / group.replace(".", "/") / name / version / filename
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(artifact)
    for artifact in MAVEN_CACHE.glob("**/*"):
        if artifact.is_file() and artifact.suffix in (".jar", ".aar", ".pom"):
            target = repository / artifact.relative_to(MAVEN_CACHE)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(artifact)


def expose_aar_classes(repository: Path, coordinates, offline=False):
    """Supply JVM classes for POMs that omit their Android dependency type."""
    changed = False
    for group, name, version in coordinates:
        directory = repository / group.replace(".", "/") / name / version
        aar = directory / f"{name}-{version}.aar"
        jar = aar.with_suffix(".jar")
        if jar.exists():
            continue
        if not aar.exists():
            if offline:
                continue
            pom = aar.with_suffix(".pom")
            if not pom.exists() or ET.parse(pom).getroot().findtext("{http://maven.apache.org/POM/4.0.0}packaging") != "aar":
                continue
            for base in ("https://dl.google.com/dl/android/maven2/", "https://repo.maven.apache.org/maven2/"):
                try:
                    download(base + str(aar.relative_to(repository)), aar)
                    break
                except urllib.error.HTTPError as error:
                    if error.code != 404:
                        raise
            if not aar.exists():
                continue
        with zipfile.ZipFile(aar) as archive:
            if "classes.jar" in archive.namelist():
                jar.write_bytes(archive.read("classes.jar"))
                changed = True
    return changed


def resolve(adapter: Path, java_home: Path, timeout: float = 180, dependencies=(), work: Path | None = None, boms=(), aligned_groups=(), offline=False) -> list[Path]:
    cache = adapter / ".dependencies"
    cache.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(cache).free < 1024 ** 3:
        raise RuntimeError("Less than 1 GiB available; dependency resolution stopped")
    repository = cache / "maven-repository"
    seed_repository(repository)
    if offline and not shutil.which("mvn") and not (cache / f"apache-maven-{MAVEN_VERSION}/bin/mvn").exists():
        raise RuntimeError("Offline dependency resolution requires cached Maven")
    executable = maven(cache)
    pom = adapter / "robolectric/dependencies.pom"
    output = cache / "classpath.txt"
    if dependencies or boms or aligned_groups:
        if work is None:
            raise ValueError("Additional dependencies require an isolated work directory")
        namespace = "http://maven.apache.org/POM/4.0.0"
        ET.register_namespace("", namespace)
        tag = lambda name: "{" + namespace + "}" + name
        tree = ET.parse(pom)
        if dependencies or boms or aligned_groups:
            management = tree.getroot().find(tag("dependencyManagement"))
            if management is None:
                management = ET.SubElement(tree.getroot(), tag("dependencyManagement"))
            managed = management.find(tag("dependencies"))
            if managed is None:
                managed = ET.SubElement(management, tag("dependencies"))
            for group, artifact, version in boms:
                entry = ET.SubElement(managed, tag("dependency"))
                for name, value in (("groupId", group), ("artifactId", artifact), ("version", version),
                                    ("type", "pom"), ("scope", "import")):
                    ET.SubElement(entry, tag(name)).text = value
                bom = repository / group.replace(".", "/") / artifact / version / f"{artifact}-{version}.pom"
                if not bom.exists():
                    raise RuntimeError(f"BOM must be available in the dependency cache: {bom}")
                # Android POMs mix jar and aar edges for the same library.
                for original in ET.parse(bom).findall("./" + tag("dependencyManagement") + "/" + tag("dependencies") + "/" + tag("dependency")):
                    entry = ET.SubElement(managed, tag("dependency"))
                    for name in ("groupId", "artifactId", "version"):
                        ET.SubElement(entry, tag(name)).text = original.findtext(tag(name))
                    ET.SubElement(entry, tag("type")).text = "aar"
            for group, version in aligned_groups:
                for artifact in sorted((GRADLE_CACHE / group).iterdir()):
                    if not (artifact / version).exists():
                        continue
                    for kind in ("jar", "aar"):
                        entry = ET.SubElement(managed, tag("dependency"))
                        for name, value in (("groupId", group), ("artifactId", artifact.name),
                                            ("version", version), ("type", kind)):
                            ET.SubElement(entry, tag(name)).text = value
        entries = tree.getroot().find(tag("dependencies"))
        for dependency in dependencies:
            if len(dependency) not in (3, 4):
                raise ValueError("dependencies entries need group, artifact, version, and optional jar/aar type")
            group, artifact, version = dependency[:3]
            for kind in ("jar", "aar"):
                entry = ET.SubElement(managed, tag("dependency"))
                for name, value in (("groupId", group), ("artifactId", artifact), ("version", version), ("type", kind)):
                    ET.SubElement(entry, tag(name)).text = value
            kind = dependency[3] if len(dependency) == 4 else (
                "aar" if list((GRADLE_CACHE / group / artifact / version).glob("*/*.aar")) else "jar"
            )
            for existing in list(entries):
                if existing.findtext(tag("groupId")) == group and existing.findtext(tag("artifactId")) == artifact:
                    entries.remove(existing)
            entry = ET.SubElement(entries, tag("dependency"))
            for name, value in (("groupId", group), ("artifactId", artifact), ("version", version), ("type", kind)):
                ET.SubElement(entry, tag(name)).text = value
        # AndroidX MPP POMs may publish kotlin-stdlib-common:unspecified.
        # JVM stdlib is already pinned; common metadata contains no JVM classes.
        for entry in entries:
            exclusions = entry.find(tag("exclusions"))
            if exclusions is None:
                exclusions = ET.SubElement(entry, tag("exclusions"))
            if any(item.findtext(tag("groupId")) == "org.jetbrains.kotlin" and
                   item.findtext(tag("artifactId")) == "kotlin-stdlib-common" for item in exclusions):
                continue
            exclusion = ET.SubElement(exclusions, tag("exclusion"))
            ET.SubElement(exclusion, tag("groupId")).text = "org.jetbrains.kotlin"
            ET.SubElement(exclusion, tag("artifactId")).text = "kotlin-stdlib-common"
        pom = work / "robolectric-dependencies.pom"
        tree.write(pom, encoding="utf-8", xml_declaration=True)
        output = work / "robolectric-classpath.txt"
    command = [str(executable), "-B", "-q", "-f", str(pom),
               f"-Dmaven.repo.local={repository}",
               "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath",
               f"-Dmdep.outputFile={output}", "-DincludeScope=test"]
    if offline:
        command.append("--offline")
    environment = dict(os.environ, JAVA_HOME=str(java_home), MAVEN_OPTS="-Xmx512m")
    deadline = time.monotonic() + timeout
    for attempt in range(4):
        result = subprocess.run(command, env=environment, capture_output=True, text=True,
                                timeout=max(1, deadline - time.monotonic()))
        if not result.returncode or not dependencies or attempt == 3:
            break
        missing = re.findall(r"dependency: ([\w.-]+):([\w.-]+):jar:([^\s]+)", result.stdout + result.stderr)
        if not expose_aar_classes(repository, missing, offline=offline):
            break
    log = (work or cache) / "dependency-resolution.log"
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"Maven dependency resolution failed: {(result.stdout + result.stderr)[:6000]}")
    jars = []
    for value in output.read_text().strip().split(os.pathsep):
        artifact = Path(value)
        if artifact.suffix == ".aar":
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            target = cache / "aar-classes" / f"{artifact.stem}-{digest[:12]}.jar"
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(artifact) as archive:
                    if "classes.jar" not in archive.namelist():
                        continue
                    target.write_bytes(archive.read("classes.jar"))
            jars.append(target)
        elif artifact.suffix == ".jar":
            jars.append(artifact)
        else:
            raise RuntimeError(f"Unsupported runtime dependency {artifact}")
    return jars


def runtime_options(adapter: Path) -> list[str]:
    sdk = adapter / ".dependencies/android-sdk"
    sdk.mkdir(parents=True, exist_ok=True)
    jars = list((MAVEN_CACHE / "org/robolectric/android-all-instrumented").glob("*/*.jar"))
    jars += list((adapter / ".dependencies/maven-repository/org/robolectric/android-all-instrumented").glob("*/*.jar"))
    for jar in jars:
        target = sdk / jar.name
        if not target.exists():
            target.symlink_to(jar.resolve())
    return ["-Drobolectric.offline=true", f"-Drobolectric.dependency.dir={sdk}"]


def prepare(config: dict, work: Path) -> dict:
    """Shared-runner bridge. Caller holds the shared Android build lock."""
    root = Path(__file__).resolve().parents[2]
    foundation = root / "state_tests/runtime/android" / config.get("robolectricFoundation", "08_threads")
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    java_home = Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home")
    timeout = float(config.get("runtimeTimeout", 180))
    jars = resolve(foundation, java_home, timeout, config.get("dependencies", []), work,
                   config.get("boms", []), config.get("alignedGroups", []), config.get("offlineDependencies", False))
    classes = work / "robolectric-bridge"
    classes.mkdir(exist_ok=True)
    sources = [foundation / "robolectric" / name for name in ("EvidenceRobolectricRunner.java", "RobolectricMain.java")]
    proc = subprocess.run([str(java_home / "bin/javac"), "-cp", os.pathsep.join(map(str, jars)),
                           "-d", str(classes), *map(str, sources)], capture_output=True, text=True, timeout=timeout)
    (work / "robolectric-bridge.log").write_text(proc.stdout + proc.stderr)
    if proc.returncode:
        raise RuntimeError(f"Robolectric bridge compilation failed: {proc.stderr}")
    bridge = work / "robolectric-bridge.jar"
    with zipfile.ZipFile(bridge, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(classes.rglob("*.class")):
            archive.write(path, str(path.relative_to(classes)))
    jars.append(bridge)

    def kotlin(artifact):
        paths = list((GRADLE_CACHE / "org.jetbrains.kotlin" / artifact / "2.2.10").glob("*/*.jar"))
        if len(paths) != 1:
            raise RuntimeError(f"Expected one cached Kotlin 2.2.10 {artifact}")
        return paths[0]

    return {
        "jars": jars,
        "compiler": kotlin("kotlin-compiler-embeddable"),
        "plugin": kotlin("kotlin-compose-compiler-plugin-embeddable"),
        "compilerArgs": [f"-Xplugin={kotlin('kotlin-parcelize-compiler')}"],
        "compileOnlyJars": [Path.home() / "Library/Android/sdk/platforms/android-36/android.jar"],
        "jvmArgs": runtime_options(foundation),
        "mainClass": "runtime.foundation.RobolectricMain",
        "excludedCommonSources": ["Parcelable.kt", "Parcelize.kt", "Inject.kt", "Timber.kt", *config.get("excludeCommonSources", [])],
        "replaceClasspath": True,
        "executionEnvironment": "host_jvm_robolectric",
        "framework": "JUnit4 / Robolectric 4.16.1 / real AndroidX Compose and DataStore",
        "scope": config.get("runtimeScope", "android_production_components"),
        "evaluatorSources": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sources],
        "dependencyPom": {"path": str(foundation / "robolectric/dependencies.pom"),
                          "sha256": hashlib.sha256((foundation / "robolectric/dependencies.pom").read_bytes()).hexdigest()},
    }
