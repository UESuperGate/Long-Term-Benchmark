"""Versioned Task15 base probe: same assertions, bounded work plus real cleanup."""
import json
import time
from pathlib import Path
from typing import Optional
from . import task14_15_formal_core as core
from . import task14_15_arkts_entry_evidence as arkts_entry_evidence
from . import task15_device_scheduling
from .task15_formal_agent import _bundle_name, _derive_base_command_logs, _derive_base_install_ownership, _discover_device
ROOT = core.ROOT
CONTRACT = ROOT / 'benchmark_tasks/15_account_deactivation/transitions.json'


def evaluate(*, source: Path, evidence: Path, deadline: float,
                        device_serial: Optional[str]) -> tuple[list[dict], list[dict]]:
    work_deadline = deadline - 120
    core.remaining_deadline(work_deadline, 'base probe reserves cleanup in original budget')
    build_dir = evidence / "base-application"
    build = core.build_arkts_application(source=source, output=build_dir, deadline=work_deadline,
                                         label="task15-base-runtime")
    build_report = build_dir / "application-build.json"
    hap = Path(build["hap"]["path"])
    original = ROOT / "scripts/runtime_semantics/Task15BaseAllDevice.cjs"
    script = original.read_text(encoding="utf-8")
    replacements = {
        "const root = path.resolve(__dirname, '../..');": f"const root = {json.dumps(str(ROOT))};",
        "const bundleName = 'com.qingyu.elementx.deactivation.base';":
            f"const bundleName = {json.dumps(_bundle_name(source))};",
        "const buildReport = path.join(root,\n  'experiment_results/runtime_transition_20261020/task15_repair/v3/build-base-eexist-repair/report.json');":
            f"const buildReport = {json.dumps(str(build_report))};",
        "const hapRecord = build.haps?.[0];": "const hapRecord = build.hap;",
        "build.role !== 'base'": "build.role !== 'agent'",
        "build.compile?.passed !== true": "build.passed !== true",
        "build.productionCopyUnchanged !== true": "build.copiedProductionUnchanged !== true",
        "build.temporaryWorkspaceRemoved !== true": "build.temporaryProjectRemoved !== true",
        "for (const source of build.production) {": "for (const source of build.sources) {",
        "production: build.production, source:": "production: build.sources, source:",
        "platform: 'arkts', role: 'base',": "platform: 'arkts', role: 'agent',",
        ("invariantChecks: spec.invariants.map(text => ({ text, passed: false,\n"
         "          reason: 'The final-version deactivation transition cannot execute from this base settings UI.' })),"):
            "invariantChecks: [], unevaluatedInvariants: spec.invariants,",
    }
    for old, new in replacements.items():
        count = script.count(old)
        if count != 1:
            raise RuntimeError(f"Task15 base runner derivation point changed: {old[:50]} ({count})")
        script = script.replace(old, new)
    script = _derive_base_command_logs(script)
    script = task15_device_scheduling.base_case_leases(script,
        serial=_discover_device(device_serial, work_deadline), deadline=work_deadline)
    script = _derive_base_install_ownership(script)
    epoch_ms = int((time.time() + core.remaining_deadline(deadline, 'base cleanup deadline')) * 1000)
    script = task15_device_scheduling.replace_once(script,
        '  const run = (args, allowed = [0], timeout = 30000) => {',
        '  const run = (args, allowed = [0], timeout = 30000) => {\n'
        "    const cleanup = args[0] === 'uninstall' || (args[0] === 'shell' && args[1] === 'rm');\n"
        '    const cap = cleanup ? ' + str(epoch_ms) + ' : ' + str(epoch_ms - 120000) + ';\n'
        '    if (Date.now() >= cap) throw Error("Whole base probe deadline exhausted");\n'
        '    timeout = Math.max(1, Math.min(timeout, cap - Date.now()));')
    derived = evidence / "task15-base-source-parameterized.cjs"
    derived.write_text(script, encoding="utf-8")
    output = evidence / "base-device"
    node = "/Applications/DevEco-Studio.app/Contents/tools/node/bin/node"
    from .task15_full_report_v4 import command
    result = command([node, str(derived), '--output', str(output)], deadline=deadline,
        log=evidence / 'base-device.log', lease_serial=device_serial)
    if result['exit'] != 0 or result['timedOut']:
        raise RuntimeError('Base runtime did not complete; preserve raw/logs, never semantic fail')
    report = core.load(output / "report.json")
    report['freshProtocol'] = 'task15.arkts.full-ten-case.v4'
    report['runtimeImplementation'] = {'path': str(Path(__file__)), 'sha256': core.sha256(Path(__file__))}
    from .task14_15_arkts_artifacts import artifact
    report['outerCommand'] = artifact((evidence / 'base-device.log').with_suffix('.command.json'))
    core.write(output / 'report.json', report)
    semantic = report.get("semantic", {})
    if report.get("status") != "passed" or (
            semantic.get("passed"), semantic.get("failed"), semantic.get("notScored")) != (0, 10, 0):
        raise RuntimeError("Task15 base device runtime did not prove 0P/10F/0NS")
    contract = core.load(CONTRACT)
    specs = {item["caseId"]: item for item in contract["cases"]}
    rows = []
    for raw in semantic.get("cases", []):
        spec = specs.get(raw.get("caseId"))
        if spec is None:
            raise RuntimeError("Task15 base device runtime returned an unknown canonical case")
        rows.append(arkts_entry_evidence.entry_row(
            raw, spec, output / "report.json", build["sources"]))
    return rows, core.remove_binary_artifacts(evidence)
