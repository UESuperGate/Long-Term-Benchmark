"""Shape-checked fresh evaluator derivation for the approved null-focus contract."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / 'state_tests/runtime/arkts/tasks08_11.cjs'
BUILDER = ROOT / 'scripts/runtime_semantics/task08_arkts_strict_build.cjs'
BUNDLER = ROOT / 'scripts/runtime_semantics/arkts_native_bundle.cjs'
EXECUTOR = ROOT / 'scripts/runtime_semantics/arkts_device_execute.cjs'
EXECUTE_WRAPPER = ROOT / 'scripts/runtime_semantics/task08_arkts_strict_execute.cjs'
WORKSPACE = ROOT / 'scripts/runtime_semantics/task08_arkts_workspace_v2.cjs'
OLD = 'equal(before.visibleEvents, after.visibleEvents) && before.focusedEventId === after.focusedEventId'
NEW = ("equal(before.visibleEvents, after.visibleEvents) && before.threadRootId === after.threadRootId && "
       "mainUnchanged && after.focusState === 'failure' && after.focusedEventId === null")


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Unreviewed Task08 template shape: ' + old)
    return source.replace(old, new)


def derive(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    adapter_path = output / 'tasks08_11.focus-null-v2.cjs'
    bundler_path = output / 'task08-bundle.focus-null-v2.cjs'
    builder_path = output / 'task08-builder.focus-null-v2.cjs'
    workspace_path = output / 'task08-workspace.v2.cjs'
    executor_path = output / 'task08-device-execute.v2.cjs'
    execute_path = output / 'task08-execute-wrapper.v2.cjs'
    adapter = replace_once(ADAPTER.read_text(), OLD, NEW)
    bundler = replace_once(BUNDLER.read_text(), "const root = path.resolve(__dirname, '../..');", 'const root = ' + json.dumps(str(ROOT)) + ';')
    bundler = replace_once(bundler, "const file = path.join(root, 'state_tests/runtime/arkts', group + '.cjs');",
                          "const file = group === 'tasks08_11' ? " + json.dumps(str(adapter_path)) + " : path.join(root, 'state_tests/runtime/arkts', group + '.cjs');")
    builder = replace_once(BUILDER.read_text(), "\nconst root = path.resolve(__dirname, '../..');", '\nconst root = ' + json.dumps(str(ROOT)) + ';')
    builder = replace_once(builder, "const sharedBuilder = path.join(__dirname, 'arkts_native_device.cjs');",
                          'const sharedBuilder = ' + json.dumps(str(ROOT / 'scripts/runtime_semantics/arkts_native_device.cjs')) + ';')
    builder = replace_once(builder, "const sharedSmoke = path.join(__dirname, 'arkts_native_smoke.cjs');",
                          'const sharedSmoke = ' + json.dumps(str(workspace_path)) + ';')
    builder = replace_once(builder, "const sharedBundle = path.join(__dirname, 'arkts_native_bundle.cjs');",
                          'const sharedBundle = ' + json.dumps(str(bundler_path)) + ';')
    executor = replace_once(EXECUTOR.read_text(), 'fs.mkdirSync(lock);\n      locked = true;',
        'fs.mkdirSync(lock);\n      locked = true;\n      const leaseStat = fs.lstatSync(lock);\n'
        '      report.task08CanonicalLease = { path: lock, inode: leaseStat.ino, device: leaseStat.dev, acquired: true };')
    executor = replace_once(executor, 'if (locked && fs.existsSync(lock)) fs.rmdirSync(lock);',
        "if (locked && fs.existsSync(lock)) {\n      const leaseStat = fs.lstatSync(lock);\n"
        "      if (leaseStat.isSymbolicLink() || leaseStat.ino !== report.task08CanonicalLease.inode || "
        "leaseStat.dev !== report.task08CanonicalLease.device) throw new Error('Task08 owned lease changed; retain');\n"
        "      fs.rmdirSync(lock);\n      report.cleanup.canonicalLeaseReleased = true;\n"
        "      report.cleanup.canonicalLeasePath = lock;\n    }")
    execute = replace_once(EXECUTE_WRAPPER.read_text(), "const template = path.join(__dirname, 'task13_arkts_revision5_execute.cjs');",
        'const template = ' + json.dumps(str(ROOT / 'scripts/runtime_semantics/task13_arkts_revision5_execute.cjs')) + ';')
    execute = replace_once(execute, "const sharedExecutor = path.join(__dirname, 'arkts_device_execute.cjs');",
        'const sharedExecutor = ' + json.dumps(str(executor_path)) + ';')
    execute = replace_once(execute, "const providerHost = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');",
        'const providerHost = ' + json.dumps(str(ROOT / 'state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs')) + ';')
    execute = replace_once(execute, "cwd: path.resolve(__dirname, '../..'),", 'cwd: ' + json.dumps(str(ROOT)) + ',')
    execute = replace_once(execute, "const policy = path.join(__dirname, 'task08_arkts_entry_evidence.py');",
        'const policy = ' + json.dumps(str(ROOT / 'scripts/runtime_semantics/task08_arkts_entry_evidence.py')) + ';')
    execute = replace_once(execute, "    .replaceAll('Task13', 'Task08')",
        '    .replace("let derived = deriveRunner(fs.readFileSync(shared, \'utf8\'));",\n'
        '      patchSharedRead + \'\\n  let derived = deriveRunner(original);\')\n'
        "    .replaceAll('Task13', 'Task08')")
    records = []
    for path, source in ((adapter_path, adapter), (bundler_path, bundler), (builder_path, builder),
                         (workspace_path, WORKSPACE.read_text()), (executor_path, executor), (execute_path, execute)):
        data = source.encode()
        path.write_bytes(data)
        records.append({'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    proof = {'schema': 'task08.focus-null.build.v2', 'generated': records,
             'originalInputs': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (ADAPTER, BUILDER, BUNDLER, EXECUTOR, EXECUTE_WRAPPER, WORKSPACE)],
             'approvedFieldCheck': {'before': OLD, 'after': NEW}, 'productionModified': False,
             'canonicalInvariantTextChanged': False, 'publicPromotion': False}
    (output / 'derivation.json').write_text(json.dumps(proof, indent=2) + '\n')
    return dict(proof, buildEntrypoint=str(builder_path), executeEntrypoint=str(execute_path))
