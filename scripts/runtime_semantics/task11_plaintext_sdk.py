"""Evaluator configuration for the upstream WYSIWYG plain-text SDK switch."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDK_SOURCE = ROOT / "state_tests/runtime/android/11_room_upgrade_navigation/messages/Task11PlainTextSdkShadow.kt"
ANNOTATION = '@Config(sdk = [36], qualifiers = "en-rUS-w411dp-h891dp-mdpi")'
REPLACEMENT = '@Config(sdk = [36], qualifiers = "en-rUS-w411dp-h891dp-mdpi", shadows = [Task11PlainTextSdkShadow::class], instrumentedPackages = ["io.element.android.wysiwyg"])'
CLASSES = {"runtime.MessagesBasePrefixTest", "runtime.MessagesRenderedTest", "runtime.LoadedNavigationTest"}


def record(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def configure(config, output):
    config = copy.deepcopy(config)
    if config["testClass"] not in CLASSES:
        return config
    root = Path(output) / "sdk-plain-text-evaluator"
    root.mkdir(parents=True, exist_ok=True)
    sources, bindings = [], []
    found = False
    for filename in config["evaluatorSources"]:
        source = Path(filename)
        text = source.read_text()
        if f'class {config["testClass"].split(".")[-1]}' not in text:
            sources.append(filename)
            continue
        if text.count(ANNOTATION) != 1:
            raise ValueError("Task11 evaluator annotation changed; refuse to edit assertions")
        transformed = text.replace(ANNOTATION, REPLACEMENT)
        if transformed.replace(REPLACEMENT, ANNOTATION) != text:
            raise ValueError("SDK fixture must change only the evaluator annotation")
        target = root / source.name
        target.write_text(transformed)
        sources.append(str(target))
        bindings.append({"original": record(source), "configured": record(target), "assertionBodyUnchanged": True})
        found = True
    if not found:
        raise ValueError("Task11 actual evaluator class unavailable")
    config["evaluatorSources"] = sources + [str(SDK_SOURCE)]
    config["sdkBoundaryFixture"] = {"mode": "upstream_supported_plain_text_rendering_switch", "sdk": "io.element.android:wysiwyg:2.38.3",
        "source": record(SDK_SOURCE), "evaluatorBindings": bindings,
        "roomProductionReplaced": False, "navigationReplaced": False, "linksOrMentionsSupported": False}
    (root / "audit.json").write_text(json.dumps(config["sdkBoundaryFixture"], indent=2) + "\n")
    return config
