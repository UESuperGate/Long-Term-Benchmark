#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import re
import shutil
import subprocess
from pathlib import Path

HVIGOR = "/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    migration = Path(__file__).resolve().parents[1]
    if shutil.disk_usage(project).free < 8 * 1024 ** 3:
        raise SystemExit("refusing disk-heavy ArkTS build below 8 GiB free")
    temporary = project / ".benchmark-calibration-build"
    shutil.rmtree(temporary, ignore_errors=True)
    shutil.copytree(project, temporary, ignore=shutil.ignore_patterns(
        "build", ".hvigor", ".benchmark-calibration-build", ".git", "_benchmark_inputs",
        "build-agent.sh", "opencode.json", "__pycache__",
    ))
    evaluator = temporary / "entry/src/main/ets/evaluator"
    evaluator.mkdir(parents=True)
    for source in (migration / "evaluator/arkts").glob("*.ets"):
        shutil.copy2(source, evaluator / source.name)
    ability = temporary / "entry/src/main/ets/entryability/EntryAbility.ets"
    text = ability.read_text()
    if "EvergreenRuntimeLaunch" in text:
        raise RuntimeError("candidate collides with hidden EvergreenRuntimeLaunch evaluator symbol")
    import_anchor = "import { window } from '@kit.ArkUI';"
    if text.count(import_anchor) != 1:
        raise RuntimeError("EntryAbility ArkUI import ABI is missing or ambiguous")
    text = text.replace(import_anchor, import_anchor + "\nimport { EvergreenRuntimeLaunch } from '../evaluator/EvergreenRuntimeLaunch';")
    create = re.compile(r"(\s+onCreate\(want: Want, launchParam: AbilityConstant\.LaunchParam\): void \{\s*\n)")
    text, count = create.subn(r"\1    EvergreenRuntimeLaunch.caseKey = String(want.parameters?.['caseKey'] ?? '');\n", text, count=1)
    if count != 1:
        raise RuntimeError("EntryAbility onCreate ABI is missing or ambiguous")
    ability.write_text(text)
    page = temporary / "entry/src/main/ets/pages/Index.ets"
    text = page.read_text()
    for symbol in ("EvergreenRuntimeLaunch", "prepareEvergreenEpisode", "LTB_EVERGREEN_CHUNK"):
        if symbol in text:
            raise RuntimeError(f"candidate collides with hidden evaluator symbol: {symbol}")
    page_import = "import { common } from '@kit.AbilityKit';"
    if text.count(page_import) != 1:
        raise RuntimeError("Index AbilityKit import ABI is missing or ambiguous")
    text = text.replace(page_import, page_import + "\nimport { hilog } from '@kit.PerformanceAnalysisKit';\nimport { EvergreenRuntimeLaunch } from '../evaluator/EvergreenRuntimeLaunch';\nimport { prepareEvergreenEpisode } from '../evaluator/EvergreenRuntimeEpisode';")
    body = """    const key = EvergreenRuntimeLaunch.caseKey;
    if (key.length === 0) return;
    const ltbRuntimeContext = getContext(this) as common.UIAbilityContext;
    const prepared = await prepareEvergreenEpisode(ltbRuntimeContext, key);
    const ltbRuntimeOwner = this.createRuntimeOwner();
    await ltbRuntimeOwner.mount(ltbRuntimeContext, { state: prepared.state, persistence: prepared.persistence, leaf: prepared.leaf });
    const episode = await prepared.run(ltbRuntimeOwner);
    const payload = encodeURIComponent(JSON.stringify(episode));
    const size = 2800;
    const total = Math.ceil(payload.length / size);
    for (let index = 0; index < total; index++) {
      const chunk = payload.substring(index * size, (index + 1) * size);
      hilog.info(0x0000, 'LTB_RUNTIME', '%{public}s', 'LTB_EVERGREEN_CHUNK:' + key + ':' + String(index) + ':' + String(total) + ':' + chunk);
    }
"""
    lifecycle = re.compile(r"(\s+async aboutToAppear\(\): Promise<void> \{\s*\n)")
    text, count = lifecycle.subn(lambda match: match.group(1) + body, text, count=1)
    if count != 1:
        raise RuntimeError("Index async aboutToAppear ABI is missing or ambiguous")
    page.write_text(text)
    output_dir = project / "entry/build/default/outputs/default"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open("/tmp/long-term-benchmark-arkts-full-build.lock", "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            run = subprocess.run([HVIGOR, "--mode", "module", "-p", "product=default", "-p", "module=entry@default", "assembleHap", "--no-daemon"], cwd=temporary)
            if run.returncode:
                return run.returncode
            haps = sorted((temporary / "entry/build").rglob("*.hap"))
            if not haps:
                raise RuntimeError("no HAP produced")
            shutil.copy2(haps[-1], output_dir / haps[-1].name)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
