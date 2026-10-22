"""Task08-private successor: replace inherited Task13 guard, never bypass entry proof."""
import hashlib
import json
from pathlib import Path
from scripts.runtime_semantics import task08_arkts_focus_build_v2 as previous

ROOT = previous.ROOT
GATE = ROOT / 'scripts/runtime_semantics/task08_arkts_entry_binding_v3.cjs'
TEMPLATE = ROOT / 'scripts/runtime_semantics/task13_arkts_revision5_execute.cjs'
OLD = '''  if (build.task13Revision5?.compileOnly === true || !build.task13Revision5?.entryDiscovery) {
    throw new Error('Compile-only scaffolding is not actual entry discovery; device execution refused');
  }'''


def derive(output):
    output = Path(output)
    result = previous.derive(output)
    gate = output / 'task08-entry-binding.v3.cjs'
    gate_source = previous.replace_once(GATE.read_text(), "const root = path.resolve(__dirname, '../..');", 'const root = ' + json.dumps(str(ROOT)) + ';')
    gate.write_text(gate_source)
    template = output / 'task08-entry-template.v3.cjs'
    original = TEMPLATE.read_text()
    new = ('  const task08EntryBinding = require(' + json.dumps(str(gate)) + ').validateTask08EntryBinding(build);\n'
           "  fs.writeFileSync(path.join(path.dirname(path.resolve(buildFile)), 'task08-entry-binding-proof.json'), "
           "JSON.stringify(task08EntryBinding, null, 2) + '\\n');")
    corrected = previous.replace_once(original, OLD, new)
    template.write_text(corrected)
    wrapper = Path(result['executeEntrypoint'])
    wrapper.write_text(previous.replace_once(wrapper.read_text(),
        'const template = ' + json.dumps(str(TEMPLATE)) + ';',
        'const template = ' + json.dumps(str(template)) + ';'))
    result['schema'] = 'task08.focus-null.build.v3.original-entry-bound'
    result['entryGateReplacement'] = {'before': OLD, 'after': new,
        'originalTemplateSha256': hashlib.sha256(original.encode()).hexdigest(),
        'derivedTemplateSha256': hashlib.sha256(corrected.encode()).hexdigest(),
        'discoveryFlagFabricated': False, 'actualNativeProofStillRequired': True}
    result['generated'] = [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                           for p in sorted(output.glob('*.cjs'))]
    result['originalInputs'].extend({'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                                    for p in (Path(__file__), Path(previous.__file__), GATE, TEMPLATE))
    (output / 'derivation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
