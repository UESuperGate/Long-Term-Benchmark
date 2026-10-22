"""Task12 immutable four-control reuse, never a freshness or approval shortcut."""

from pathlib import Path
from contextlib import contextmanager
import hashlib
import math
import os
import re
import shutil
import time
import uuid

from . import task12_13_formal_core as core
from . import task12_13_runtime_support as support
from . import task12_actual_ui_protocol as actual

PROTOCOL = 'task12.reviewed-control-reuse.v1'
VERSION_PROTOCOL = 'task12.execution-bound-toolchain-adoption.v1'
CALIBRATION_PROTOCOL = 'task12.pre-agent-four-control-calibration.v2'
PARENT_CLOCK = 'parent_process.time.monotonic.v1'
CHILD_CLOCK = 'worker_process.time.monotonic.v1'
CLOCK_TRANSLATION = 'parent_remaining_seconds.v1'
# Review pins identify evidence, not an override: every version proof is still
# parsed and checked. The retained v3 audit currently has unknown versions.
REVIEWED_VERSION_AUDITS = frozenset()
LABELS = ('base', 'final', 'negative', 'positive')
COMPONENTS = ('sdkRelease', 'sdkApi', 'hvigor', 'buildNode', 'runtimeNode',
              'java', 'hdc', 'deviceApi', 'deviceVersion')
STUDIO = Path('/Applications/DevEco-Studio.app/Contents')
SDK = Path.home() / 'Library/OpenHarmony/Sdk/23'
NODE = STUDIO / 'tools/node/bin/node'
HVIGOR = STUDIO / 'tools/hvigor/hvigor/package.json'
SDK_META = SDK / 'ets/oh-uni-package.json'
HDC = SDK / 'toolchains/hdc'
COMPILER = SDK / 'ets/build-tools/ets-loader/bin/ark/build-mac/bin/es2abc'
PLUGIN = STUDIO / 'tools/hvigor/hvigor-ohos-plugin/package.json'
JAVA = STUDIO / 'jbr/Contents/Home/bin/java'
SHARED_MODULES = core.ROOT / 'elementx_harmony_full/oh_modules'


def require(value, reason):
    if not value:
        raise ValueError('Task12 reviewed controls: ' + reason)


def check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('Task12 reviewed controls shared deadline exhausted')


def validate_versions(values):
    require(set(values) == set(COMPONENTS) and all(isinstance(value, str) and value.strip() == value and value
            for value in values.values()), 'toolchain version values missing')
    for name, value in values.items():
        require(not any(word in value.lower() for word in ('unknown', 'not found', 'error:', 'undefined', 'unavailable')),
                'unavailable actual version: ' + name)
    for name in ('sdkRelease', 'hvigor'):
        require(re.fullmatch(r'\d+(?:\.\d+){2,}(?:[-A-Za-z0-9_.]*)', values[name]), 'invalid actual version: ' + name)
    for name in ('buildNode', 'runtimeNode'):
        require(re.fullmatch(r'v\d+\.\d+\.\d+(?:[-A-Za-z0-9_.]*)', values[name]), 'invalid actual Node version')
    require(re.search(r'\b(?:openjdk|java)(?:\s+version)?\s+"?\d+(?:\.\d+)*', values['java'], re.I),
            'actual build JBR version output missing')
    require(re.search(r'\d+\.\d+\.\d+', values['hdc']) and
            re.search(r'\d+(?:\.\d+){2,}', values['deviceVersion']), 'actual HDC/device version output missing')
    require(values['sdkApi'] == values['deviceApi'] == '23', 'SDK/device API mismatch')


def file_record(path, deadline):
    check(deadline)
    path = Path(path)
    if not path.is_absolute():
        path = core.ROOT / path
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            check(deadline)
            digest.update(block)
            size += len(block)
    return {'path': str(path.resolve()), 'bytes': size, 'sha256': digest.hexdigest()}


def checked(record, deadline):
    actual_record = file_record(record['path'], deadline)
    require((actual_record['bytes'], actual_record['sha256']) == (record['bytes'], record['sha256']),
            'artifact hash/size changed: ' + record['path'])
    return Path(actual_record['path'])


def policy_records(deadline=None):
    deadline = deadline if deadline is not None else time.monotonic() + 120
    from . import task14_15_formal_core as builder
    paths = [Path(__file__), Path(__file__).with_name('task12_arkts_runtime_admission.py'),
        Path(__file__).with_name('task12_arkts_actual_formal.py'), Path(core.__file__), Path(support.__file__),
        Path(actual.replay.__file__), Path(actual.replay.frozen.__file__), Path(actual.replay.entry.__file__),
        Path(actual.replay.formal.__file__), Path(builder.__file__),
        Path(__file__).resolve().parents[1] / 'run_runtime_transition_matrix.py']
    return [file_record(path, deadline) for path in paths]


def source_inventory(source, deadline):
    from .task12_arkts_actual_formal import inventory
    return inventory(Path(source).resolve(), deadline)


def execution_policy_records(deadline):
    # The capturing/admitting helper is part of the frozen execution boundary.
    # Editing a review registry also changes this boundary; it cannot silently
    # adopt controls generated under a different helper revision.
    return policy_records(deadline)


@contextmanager
def nested_deadline(deadline):
    original = support.run
    def bounded(*args, **kwargs):
        kwargs['deadline'] = min(kwargs['deadline'], deadline)
        return original(*args, **kwargs)
    support.run = bounded
    try:
        yield
    finally:
        support.run = original


def version_audit(record, bundle_record, deadline):
    audit = core.load(checked(record, deadline))
    require(audit.get('protocol') == VERSION_PROTOCOL and
            audit.get('controlBundle') == bundle_record,
            'missing execution-bound historical version audit for this bundle')
    expected_policy = execution_policy_records(deadline)
    require(audit.get('executionPolicyBefore') == expected_policy == audit.get('executionPolicyAfter'),
            'original calibration execution policy/source bindings missing or changed')
    for name in COMPONENTS:
        check(deadline)
        component = audit.get('components', {}).get(name, {})
        value = component.get('value')
        require(isinstance(value, str) and value.strip() == value and value and
                component.get('status') == 'execution_bound',
                'unknown/unbound historical toolchain component: ' + name)
        evidence = component['evidence']
        path = checked(evidence['artifact'], deadline)
        if evidence['format'] == 'json':
            observed = core.load(path)
            for part in evidence['pointer']:
                require(type(part) in (str, int), 'invalid version evidence pointer')
                observed = observed[part]
        else:
            require(evidence['format'] == 'stdout', 'unsupported historical evidence format')
            observed = path.read_text().strip()
        require(str(observed) == value and component.get('boundControlBundleSha256') == bundle_record['sha256'],
                'historical version value/batch binding differs: ' + name)
    prospective = record['sha256'] not in REVIEWED_VERSION_AUDITS
    if prospective:
        require('prospectiveExecution' in audit,
                'historical version audit has not been registered after evidence review')
    versions = {name: audit['components'][name]['value'] for name in COMPONENTS}
    validate_versions(versions)
    execution = audit.get('executionToolchain', {})
    require(all(name in execution for name in ('before', 'after')),
            'original calibration toolchain snapshots missing')
    before = verify_snapshot(execution['before'], versions, deadline)
    after = verify_snapshot(execution['after'], versions, deadline)
    require(before['files'] == after['files'] and before['captureNonce'] != after['captureNonce'],
            'toolchain fingerprints changed across original calibration')
    if prospective:
        validate_prospective(audit, bundle_record, before, after, deadline)
    # These must be prospective execution snapshots, never current captures
    # retroactively attributed to v3 or 4517.
    return audit


def identities(report, deadline):
    raw = core.load(checked(report['provenance']['runtimeEvidence']['raw'], deadline))
    rows = raw['semantic']['cases']
    values = [row.get('caseRunId') or row.get('entryFailureEvidence', {}).get('caseRunId') for row in rows]
    require(len(values) == 10 and all(isinstance(value, str) and value for value in values) and
            len(set(values)) == 10, 'ten independent case identities missing/repeated')
    return set(values)


def verify_controls(receipt, contract, base_source, final_source, deadline):
    from . import task12_arkts_runtime_admission as admission
    require(receipt.get('protocol') == PROTOCOL and receipt.get('controlsReused') is True and
            receipt.get('freshControlExecutions') is False, 'not an explicit reused-control receipt')
    bundle_record = receipt['controlBundle']
    bundle_path = checked(bundle_record, deadline)
    require(bundle_path.is_relative_to(core.ROOT / 'experiment_results'), 'control bundle outside audit root')
    audit = version_audit(receipt['versionAudit'], bundle_record, deadline)
    require(receipt.get('policyFiles') == policy_records(deadline), 'reviewed reuse policy changed')
    require(receipt.get('contract') == file_record(actual.CONTRACT, deadline) and
            core.load(actual.CONTRACT) == contract, 'canonical contract differs')
    producers = [file_record(p, deadline) for p in (actual.FACTS, actual.RUNNER, Path(actual.__file__))]
    require(receipt.get('producerFiles') == producers and
            tuple(p['sha256'] for p in producers) == admission.PRODUCER_SHAS,
            'actual-UI producer boundary changed')
    for name, source, expected in (('base', base_source, admission.BASE_SHA),
                                   ('final', final_source, admission.FINAL_SHA)):
        check(deadline)
        inventory = source_inventory(source, deadline)
        declared = receipt['immutableSources'][name]
        require(inventory['sha256'] == expected == declared['sha256'] and
                str(Path(source).resolve()) == declared['source'], 'current immutable source differs: ' + name)
    bundle = core.load(bundle_path)
    paths, run_ids, raw_shas, counts = set(), set(), set(), {}
    from scripts.run_runtime_transition_matrix import validate_report
    for label, role, sha, expected in (
        ('base', 'base', admission.BASE_SHA, (0, 10, 0)),
        ('final', 'final', admission.FINAL_SHA, (10, 0, 0)),
        ('negative', 'agent', admission.BASE_SHA, (0, 10, 0)),
        ('positive', 'agent', admission.FINAL_SHA, (10, 0, 0))):
        check(deadline)
        path = checked(receipt['reports'][label], deadline)
        require(path == Path(bundle['sourceParameterizedControls'][label]['reportPath']).resolve(),
                'control reference differs from its original bundle')
        control = core.load(path)
        evidence = control['provenance']['runtimeEvidence']
        require(evidence.get('admissionBundle') == bundle_record and
                control['role'] == role and control['provenance']['sourceInventorySha256'] == sha,
                'old control batch/source/role changed')
        with nested_deadline(deadline):
            proof = actual.validate_report_evidence(control, contract, deadline=deadline)
        require(tuple(proof['counts'][key] for key in ('passed', 'failed', 'notScored')) == expected,
                'actual control polarity incomplete: ' + label)
        # Full public validation includes the original (unchanged) fresh-bundle
        # admission, not an upgraded or reparented copy of a historical report.
        with nested_deadline(deadline):
            validate_report(control, contract)
        source = control['provenance']['candidateSource']
        ids = identities(control, deadline)
        require(source not in paths and not ids.intersection(run_ids) and
                evidence['raw']['sha256'] not in raw_shas, 'control source/raw/case identity reused')
        paths.add(source)
        run_ids.update(ids)
        raw_shas.add(evidence['raw']['sha256'])
        counts[label] = list(expected)
    return {'validated': True, 'counts': counts, 'controlSources': sorted(paths),
            'controlCaseIdentities': sorted(run_ids), 'controlRawSha256': sorted(raw_shas),
            'versions': {name: audit['components'][name]['value'] for name in COMPONENTS}}


def toolchain_paths(deadline):
    runtime_node = Path(shutil.which('node') or '')
    java_home = JAVA.parent.parent
    paths = {SDK_META, SDK / 'toolchains/oh-uni-package.json', HVIGOR, NODE, runtime_node,
        JAVA, java_home / 'release', java_home / 'lib/modules', java_home / 'lib/server/libjvm.dylib',
        HDC, COMPILER, PLUGIN, HVIGOR.parent / 'index.js', PLUGIN.parent / 'index.js',
        STUDIO / 'tools/hvigor/hvigor/bin/hvigor.js'}
    for path in COMPILER.parent.iterdir():
        check(deadline)
        if path.is_file():
            paths.add(path)
    require(SHARED_MODULES.is_dir(), 'actual build shared modules missing')
    for root in (HVIGOR.parent / 'src', PLUGIN.parent / 'src', PLUGIN.parent / 'res',
                 SDK / 'ets/build-tools/ets-loader/lib', SHARED_MODULES):
        for path in root.rglob('*'):
            check(deadline)
            if path.is_file():
                paths.add(path)
    return sorted({path.resolve() for path in paths})


def capture_toolchain(output, serial, deadline):
    started = time.monotonic()
    check(deadline)
    output.mkdir(parents=True, exist_ok=False)
    runtime_node = Path(shutil.which('node') or '')
    require(runtime_node.is_file(), 'runtime node not found')
    files = [file_record(path, deadline) for path in toolchain_paths(deadline)]
    probes = {}
    for name, command in (
        ('buildNode', [str(NODE), '--version']), ('runtimeNode', [str(runtime_node), '--version']),
        ('java', [str(JAVA), '-version']), ('hdc', [str(HDC), '-v'])):
        log = output / (name + '.log')
        support.run(command, deadline=deadline, phase='Task12 current toolchain ' + name, log=log)
        probes[name] = {'command': command, 'log': file_record(log, deadline)}
    with support.arkts_device_lock(serial=serial, deadline=deadline):
        for name, key in (('deviceApi', 'const.ohos.apiversion'), ('deviceVersion', 'const.ohos.fullname')):
            command = [str(HDC), '-t', serial, 'shell', 'param', 'get', key]
            log = output / (name + '.log')
            support.run(command, deadline=deadline, phase='Task12 current device version ' + name, log=log)
            probes[name] = {'command': command, 'log': file_record(log, deadline)}
    result = {'files': files, 'probes': probes, 'serial': serial,
              'capturedNowNotHistorical': True, 'runtimeNode': str(runtime_node.resolve()),
              'captureNonce': uuid.uuid4().hex, 'buildJavaHome': str(STUDIO / 'jbr/Contents/Home'),
              'startedMonotonic': started, 'finishedMonotonic': time.monotonic(),
              'clockDomain': CHILD_CLOCK, 'clockPid': os.getpid(), 'timesAreLocalDiagnosticsOnly': True}
    core.write(output / 'snapshot.json', result)
    return file_record(output / 'snapshot.json', deadline)


def snapshot_values(record, deadline):
    snapshot = core.load(checked(record, deadline))
    require(snapshot.get('clockDomain') == CHILD_CLOCK and snapshot.get('timesAreLocalDiagnosticsOnly') is True and
            type(snapshot.get('clockPid')) is int and snapshot['clockPid'] > 0 and
            all(type(snapshot.get(key)) in (int, float) and math.isfinite(snapshot[key]) and snapshot[key] >= 0
                for key in ('startedMonotonic', 'finishedMonotonic')) and
            snapshot['startedMonotonic'] <= snapshot['finishedMonotonic'],
            'snapshot local diagnostic clock attribution missing')
    require(snapshot.get('capturedNowNotHistorical') is True and
            isinstance(snapshot.get('captureNonce'), str) and
            re.fullmatch('[0-9a-f]{32}', snapshot['captureNonce']), 'snapshot capture attribution/nonce missing')
    require(snapshot.get('buildJavaHome') == str(STUDIO / 'jbr/Contents/Home'),
            'actual build JAVA_HOME identity differs')
    expected_files = set(toolchain_paths(deadline))
    require({checked(item, deadline) for item in snapshot['files']} == expected_files,
            'current toolchain binary/metadata set differs')
    values = {'sdkRelease': str(core.load(SDK_META)['version']), 'sdkApi': str(core.load(SDK_META)['apiVersion']),
              'hvigor': str(core.load(HVIGOR)['version'])}
    tool_meta = core.load(SDK / 'toolchains/oh-uni-package.json')
    require(str(tool_meta['version']) == values['sdkRelease'] and str(tool_meta['apiVersion']) == values['sdkApi'],
            'SDK components disagree')
    commands = {'buildNode': [str(NODE), '--version'],
        'runtimeNode': [str(Path(shutil.which('node'))), '--version'], 'hdc': [str(HDC), '-v'],
        'java': [str(JAVA), '-version'],
        'deviceApi': [str(HDC), '-t', snapshot['serial'], 'shell', 'param', 'get', 'const.ohos.apiversion'],
        'deviceVersion': [str(HDC), '-t', snapshot['serial'], 'shell', 'param', 'get', 'const.ohos.fullname']}
    for name, command in commands.items():
        probe = snapshot['probes'][name]
        require(probe['command'] == command, 'version probe command differs: ' + name)
        values[name] = checked(probe['log'], deadline).read_text().strip()
    validate_versions(values)
    return snapshot, values


def verify_snapshot(record, versions, deadline):
    snapshot, values = snapshot_values(record, deadline)
    require(values == versions,
            'current versions do not match historically execution-bound versions')
    return snapshot


def parent_worker_span(item, envelope, deadline):
    config_path = checked(item['workerConfig'], deadline)
    process = core.load(checked(item['workerProcess'], deadline))
    config = core.load(config_path)
    require(process.get('clockDomain') == config.get('parentClockDomain') == PARENT_CLOCK and
            process.get('parentPid') == config.get('parentPid') == envelope['parentPid'] and
            process.get('workerConfig') == item['workerConfig'] and
            config.get('workerConfigPath') == str(config_path), 'worker parent clock/config binding differs')
    numeric = [process.get(key) for key in ('startedMonotonic', 'finishedMonotonic')]
    numeric += [config.get(key) for key in ('launchParentMonotonic', 'remainingBudgetSeconds')]
    require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in numeric),
            'invalid parent worker timestamp/budget')
    require(config['clockTranslation'] == CLOCK_TRANSLATION and
            config['workDeadlineMonotonic'] == envelope['workDeadlineMonotonic'] and
            config['cleanupDeadlineMonotonic'] == envelope['deadlineMonotonic'] and
            config['launchParentMonotonic'] == process['startedMonotonic'] and
            config['remainingBudgetSeconds'] == envelope['workDeadlineMonotonic'] - config['launchParentMonotonic'] and
            0 < config['remainingBudgetSeconds'] <= 3600 and
            envelope['startedMonotonic'] <= process['startedMonotonic'] < process['finishedMonotonic'] <=
            envelope['workDeadlineMonotonic'], 'parent remaining budget/deadline differs')
    require(process.get('childReaped') is True and process.get('cleanupSafe') is True and
            type(process.get('exitCode')) is int and process['exitCode'] == 0 and
            type(process.get('pid')) is int and process['pid'] > 0 and
            process.get('remainingGroupMembers') == [] and process.get('signalFailures') == [] and
            process['isolation']['ownedNewSession'] is True, 'prospective worker execution/cleanup incomplete')
    clock = core.load(checked(process['workerClockReceipt'], deadline))
    require(Path(config['workerClockReceipt']).resolve() == Path(process['workerClockReceipt']['path']).resolve() and
            clock.get('protocol') == CLOCK_TRANSLATION and clock.get('clockDomain') == CHILD_CLOCK and
            clock.get('parentPid') == envelope['parentPid'] and clock.get('workerPid') == process['pid'] and
            clock.get('workerConfig') == item['workerConfig'] and clock.get('parentHardTimeoutAuthority') is True and
            clock.get('epochIsDiagnosticOnly') is True and
            clock.get('launchParentMonotonic') == config['launchParentMonotonic'] and
            clock.get('parentWorkDeadlineMonotonic') == config['workDeadlineMonotonic'] and
            clock.get('remainingBudgetSeconds') == config['remainingBudgetSeconds'] and
            all(type(clock.get(key)) in (int, float) and math.isfinite(clock[key]) and clock[key] >= 0
                for key in ('startedLocalMonotonic', 'deadlineLocalMonotonic')) and
            clock['deadlineLocalMonotonic'] == clock['startedLocalMonotonic'] + config['remainingBudgetSeconds'],
            'worker local clock translation receipt differs')
    return config, process, clock


def validate_prospective(audit, bundle_record, before, after, deadline):
    path = checked(audit['prospectiveExecution'], deadline)
    envelope = core.load(path)
    root = path.parent
    require(root.is_relative_to(core.ROOT / 'experiment_results') and
            envelope.get('protocol') == CALIBRATION_PROTOCOL and
            envelope.get('clockDomain') == PARENT_CLOCK and
            type(envelope.get('parentPid')) is int and envelope['parentPid'] > 0 and
            envelope.get('controlBundle') == bundle_record and
            envelope.get('executionToolchain') == audit['executionToolchain'],
            'prospective calibration envelope/bundle differs')
    budget = envelope['timeoutSeconds']
    times = [envelope[key] for key in ('startedMonotonic', 'deadlineMonotonic', 'workDeadlineMonotonic')]
    require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in times),
            'invalid calibration timestamp')
    require(type(budget) in (float, int) and math.isfinite(budget) and 0 < budget <= 3600 and
            envelope['deadlineMonotonic'] == envelope['startedMonotonic'] + budget and
            envelope['startedMonotonic'] < envelope['workDeadlineMonotonic'] < envelope['deadlineMonotonic'],
            'calibration does not have one independent <=3600 budget with reserve')
    bundle = core.load(checked(bundle_record, deadline))
    require(set(envelope['snapshotWorkers']) == {'before', 'after'}, 'snapshot parent execution receipts missing')
    snapshot_spans = {}
    for label, snapshot in (('before', before), ('after', after)):
        item = envelope['snapshotWorkers'][label]
        require(item['snapshot'] == audit['executionToolchain'][label] and
                core.load(checked(item['snapshot'], deadline)) == snapshot and
                core.load(checked(item['result'], deadline)) == item['snapshot'],
                'snapshot worker result is not bound to original toolchain capture')
        config, process, clock = parent_worker_span(item, envelope, deadline)
        require(Path(item['workerConfig']['path']) == root / ('toolchain-' + label + '-worker.json') and
                Path(item['workerProcess']['path']) == root / ('toolchain-' + label + '-worker.process.json') and
                config['phase'] == 'calibration_snapshot' and
                config['result'] == str(checked(item['result'], deadline)) and
                config['snapshotOutput'] == str(root / ('toolchain-' + label)) and
                checked(item['snapshot'], deadline) == Path(config['snapshotOutput']) / 'snapshot.json' and
                config['serial'] == before['serial'] == after['serial'] and
                snapshot.get('clockDomain') == CHILD_CLOCK and snapshot.get('clockPid') == process['pid'] and
                snapshot.get('timesAreLocalDiagnosticsOnly') is True and
                all(type(snapshot.get(key)) in (float, int) and math.isfinite(snapshot[key])
                    for key in ('startedMonotonic', 'finishedMonotonic')) and
                clock['startedLocalMonotonic'] <= snapshot['startedMonotonic'] < snapshot['finishedMonotonic'] <=
                clock['deadlineLocalMonotonic'], 'snapshot worker local diagnostic/source binding differs')
        snapshot_spans[label] = process
    require(set(envelope['phases']) == set(LABELS), 'four prospective phases missing')
    previous_finish = snapshot_spans['before']['finishedMonotonic']
    for label in LABELS:
        item = envelope['phases'][label]
        report_path = checked(item['report'], deadline)
        require(report_path.parent == root / label and
                report_path == Path(bundle['sourceParameterizedControls'][label]['reportPath']).resolve(),
                'prospective control is outside its fresh phase')
        report = core.load(report_path)
        require(Path(report['provenance']['candidateSource']).is_relative_to(root / 'owned-sources') and
                checked(report['provenance']['runtimeEvidence']['raw'], deadline).is_relative_to(root / label),
                'retained control cannot be relabeled into a prospective calibration')
        config_path = checked(item['workerConfig'], deadline)
        process_path = checked(item['workerProcess'], deadline)
        require(config_path.parent == process_path.parent == root / label, 'worker receipts outside their fresh phase')
        config, process, _ = parent_worker_span(item, envelope, deadline)
        expected_role = label if label in ('base', 'final') else 'agent'
        require(config['phase'] == 'runtime' and config['source'] == report['provenance']['candidateSource'] and
                config['role'] == report['role'] == expected_role and config['result'] == str(report_path) and
                config['serial'] == before['serial'] == after['serial'], 'worker source/role/deadline differs')
        require(previous_finish <= process['startedMonotonic'] and
                process['finishedMonotonic'] <= snapshot_spans['after']['startedMonotonic'],
                'prospective runtime does not lie between parent-recorded toolchain workers')
        previous_finish = process['finishedMonotonic']


def assemble_version_audit(*, bundle, before, after, envelope, output, deadline):
    require(not output.exists(), 'refusing existing version audit')
    first, versions = snapshot_values(before, deadline)
    last = verify_snapshot(after, versions, deadline)
    require(first['files'] == last['files'], 'toolchain changed during calibration')
    components = {}
    for name, value in versions.items():
        if name in ('sdkRelease', 'sdkApi', 'hvigor'):
            source = HVIGOR if name == 'hvigor' else SDK_META
            evidence = {'format': 'json', 'artifact': file_record(source, deadline),
                        'pointer': ['apiVersion' if name == 'sdkApi' else 'version']}
        else:
            evidence = {'format': 'stdout', 'artifact': first['probes'][name]['log']}
        components[name] = {'status': 'execution_bound', 'value': value, 'evidence': evidence,
                            'boundControlBundleSha256': bundle['sha256']}
    policy = core.load(checked(envelope, deadline))
    audit = {'protocol': VERSION_PROTOCOL, 'controlBundle': bundle, 'components': components,
        'executionToolchain': {'before': before, 'after': after},
        'executionPolicyBefore': policy['executionPolicyBefore'], 'executionPolicyAfter': policy['executionPolicyAfter'],
        'prospectiveExecution': envelope, 'historicalUnknownVersionsNotRetrofitted': True}
    core.write(output, audit)
    version_audit(file_record(output, deadline), bundle, deadline)
    return file_record(output, deadline)


def verify_receipt(record, contract, base_source, final_source, deadline):
    path = checked(record, deadline)
    require(path.is_relative_to(core.ROOT / 'experiment_results'), 'reuse receipt outside evaluator audit root')
    receipt = core.load(path)
    proof = verify_controls(receipt, contract, base_source, final_source, deadline)
    verify_snapshot(receipt['sealedToolchain'], proof['versions'], deadline)
    audit = core.load(checked(receipt['versionAudit'], deadline))
    if 'prospectiveExecution' in audit:
        root = checked(audit['prospectiveExecution'], deadline).parent
        completion = core.load(root / 'calibration-completion.json')
        require(completion.get('receipt') == record and completion.get('readyForCandidateScoring') is True,
                'prospective calibration never completed and released its resources')
        for name in ('owned-sources', 'temporary'):
            clean = core.load(root / (name + '-cleanup.json'))
            require(clean.get('performed') is True and clean.get('root') == str(root / name) and
                    not (root / name).exists(), 'prospective calibration cleanup incomplete: ' + name)
    return receipt, proof


def create_receipt(*, bundle, version_evidence, base_source, final_source, output, serial, deadline):
    """Called only inside the bounded scorer worker, after version-evidence review."""
    require(not output.exists(), 'refusing to overwrite a reuse receipt')
    bundle_record = file_record(bundle, deadline)
    version_audit(file_record(version_evidence, deadline), bundle_record, deadline)
    original = core.load(bundle)
    receipt = {'protocol': PROTOCOL, 'controlsReused': True, 'freshControlExecutions': False,
        'controlBundle': bundle_record, 'versionAudit': file_record(version_evidence, deadline),
        'contract': file_record(actual.CONTRACT, deadline), 'policyFiles': policy_records(deadline),
        'producerFiles': [file_record(p, deadline) for p in (actual.FACTS, actual.RUNNER, Path(actual.__file__))],
        'reports': {label: file_record(Path(original['sourceParameterizedControls'][label]['reportPath']), deadline) for label in LABELS},
        'immutableSources': {name: {'source': str(Path(source).resolve()), 'sha256': source_inventory(source, deadline)['sha256']}
                            for name, source in (('base', base_source), ('final', final_source))}}
    proof = verify_controls(receipt, core.load(actual.CONTRACT), base_source, final_source, deadline)
    audit = version_audit(file_record(version_evidence, deadline), bundle_record, deadline)
    snapshot = audit['executionToolchain']['after']
    verify_snapshot(snapshot, proof['versions'], deadline)
    receipt['sealedToolchain'] = snapshot
    receipt['sealedSnapshotReusedFromCalibrationAfter'] = True
    check(deadline)
    core.write(output, receipt)
    return file_record(output, deadline)


def validate_candidate(report, contract, *, deadline=None):
    deadline = deadline or time.monotonic() + 120
    evidence = report['provenance']['runtimeEvidence']
    require('admissionBundle' not in evidence, 'new candidate must not join the old control batch')
    receipt_record = evidence['reviewedControlReceipt']
    receipt = core.load(checked(receipt_record, deadline))
    base, final = (Path(receipt['immutableSources'][name]['source']) for name in ('base', 'final'))
    receipt, proof = verify_receipt(receipt_record, contract, base, final, deadline)
    calibration = report.get('calibration', {})
    require(calibration.get('controlsReused') is True and calibration.get('freshControlExecutions') is False and
            calibration.get('passed') is True and calibration.get('reviewedControls') == proof['counts'] and
            report['role'] == 'agent', 'candidate/control freshness, counts or role is misattributed')
    require(report['provenance']['candidateSource'] not in proof['controlSources'], 'candidate reuses a control source directory')
    require(evidence['raw']['sha256'] not in proof['controlRawSha256'] and
            not identities(report, deadline).intersection(proof['controlCaseIdentities']), 'candidate reuses a control execution')
    snapshots = [verify_snapshot(evidence[name], proof['versions'], deadline)
                 for name in ('preCandidateToolchain', 'postCandidateToolchain')]
    require(evidence['preCandidateToolchain']['sha256'] != evidence['postCandidateToolchain']['sha256'] and
            snapshots[0]['captureNonce'] != snapshots[1]['captureNonce'], 'pre/post version snapshots reused')
    with nested_deadline(deadline):
        actual.validate_report_evidence(report, contract, deadline=deadline)
    check(deadline)
    return True
