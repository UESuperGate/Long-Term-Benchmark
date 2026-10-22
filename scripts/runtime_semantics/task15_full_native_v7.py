"""Complete ten-case ORIGINAL native page-owner producer, never a host pole."""
from __future__ import annotations

import json
from pathlib import Path
import time
import types

from . import task15_page_owner_packaging_v6 as previous
from . import task15_page_owner_v5 as owner
from . import task15_fresh_protocol_v2 as transport
from . import task14_15_formal_core as core

TASK = '15_account_deactivation'
PROTOCOL = 'task15.full-ten-original-owner.v7'
CONTRACT = core.ROOT / 'benchmark_tasks' / TASK / 'transitions.json'
CASES = {case['caseId'] for case in core.load(CONTRACT)['cases']}


def observer_source():
    code = (owner.DIRECTORY / 'Task15PageOwnerObserverV5.js').read_text()
    code = transport.replace(code, "'task15.arkts.same-original-page-owner.v5'", json.dumps(PROTOCOL))
    # Read only own data fields of the actual service, never call userId(),
    # canSubmit(), a presenter event, or a session getter to manufacture proof.
    code = transport.replace(code, '      action: namespace.DEACTIVATION_SUCCEEDED', '''      serverCanDeactivateAccount: typeof receiver.canDeactivateAccount === 'boolean' ? receiver.canDeactivateAccount :
        (typeof receiver.available === 'boolean' ? receiver.available : undefined),
      accountSessionActive: service && Object.prototype.hasOwnProperty.call(service, 'session') &&
        typeof service.closed === 'boolean' ? service.session?.phase === 'active' && !service.closed : undefined,
      action: namespace.DEACTIVATION_SUCCEEDED''')
    return code


def engine_source():
    code = previous._engine()
    begin = code.index('const keys = new Set(')
    end = code.index(');', begin) + 2
    keys = [case['key'] for case in core.load(CONTRACT)['cases']]
    code = code[:begin] + 'const keys = new Set(' + json.dumps(keys) + ');' + code[end:]
    code = code.replace("'task15.arkts.same-original-page-owner.v5'", json.dumps(PROTOCOL))
    code = transport.replace(code, '    result.frames.push(frame); return frame;', '''    frame.bracketEnd = { windowIdentity: await launch.check(driver), windowAndIme: await inspector.ime(),
      nativeTree: inspector.tree(), pageOwner: observer?.read() };
    result.frames.push(frame); return frame;''')
    code = transport.replace(code, "confirm: ON.type('Button').text(binding.confirmText), close: selector('close') };", """confirm: ON.type('Button').text(binding.confirmText), close: selector('close'),
    confirmation: ON.text(binding.confirmationText), loading: ON.id(binding.loadingId), retry: selector('retry') };""")
    begin = code.index("    if (spec.key === 'default_form_blocks_submit') {")
    end = code.index('    // Fixed observation delay, never wait for expected/success state to appear.', begin)
    code = code[:begin] + """    if (spec.key === 'capability_gates_entry') {
      await capture('before_event');
      await receipt('ability_start','original_settings',()=>launch.reload(),{},'event');
    } else if (spec.key === 'default_form_blocks_submit') {
      await capture('before_event'); await click('entry','event');
    } else {
      await click('entry');
      if (spec.key === 'password_enables_submit') {
        await capture('before_event'); await input(spec.event.value,'event'); await hideObservedIme();
      } else if (spec.key === 'erase_data_option') {
        await capture('before_event'); await click('erase','event');
      } else {
        if ((await inspect('erase')).checked === false) await click('erase');
        await input('secret'); await hideObservedIme();
        if (spec.key === 'first_submit_confirms') {
          await capture('before_event'); await click('submit','event');
        } else {
          await click('submit');
          await driver.delayMs(300);
          if (spec.key === 'confirm_sends_payload') {
            await capture('before_event'); await click('confirm','event');
            await integration.control.waitHeld(1); await release(1,401); await integration.control.waitHeld(2);
            await driver.delayMs(100);
            const loading = await capture('after_event');
            const password = loading.controls.find(value=>value.name==='password');
            const modal = loading.controls.find(value=>value.name==='loading');
            if (modal.present && modal.visible) {
              need(password.present && typeof ports.modalInput === 'function','Own modal hit routing boundary unavailable');
              let error;
              await receipt('modal_physical_input','password_coordinates',async()=>{
                try { await ports.modalInput([[password.bounds.left,password.bounds.top],[password.bounds.right,password.bounds.bottom]],'tampered'); }
                catch(value){error=String(value);}
              },{attemptedText:'tampered',geometry:[[password.bounds.left,password.bounds.top],[password.bounds.right,password.bounds.bottom]]},'invariant');
              const after = await capture('after_modal_input');
              result.modalProbe={beforeSequence:loading.sequence,afterSequence:after.sequence,inputError:error||null};
            }
          } else {
            await click('confirm'); await integration.control.waitHeld(1);
            await release(1,401); await integration.control.waitHeld(2);
            if (spec.key === 'success_completes' || spec.key === 'failure_preserves_form') {
              await capture('before_event'); await release(2,spec.key==='success_completes'?200:503,'event');
            } else {
              await release(2,503); await driver.delayMs(300);
              await capture('before_event');
              await click(spec.key==='retry_bypasses_confirmation'?'retry':'close','event');
            }
          }
        }
      }
    }
""" + code[end:]
    code = transport.replace(code, "await driver.delayMs(300); await capture('after_event');",
        "await driver.delayMs(300); if (!result.frames.some(frame=>frame.label==='after_event')) await capture('after_event');")
    return code


def prepare(*, source, case_id, output, deadline, serial='127.0.0.1:5555'):
    if case_id not in CASES:
        raise ValueError('Unknown ten-case canonical episode')
    all_keys = {case['key'] for case in core.load(CONTRACT)['cases']}
    # Local, source-recorded preparation specialization. No imported globals,
    # frozen methods, runtime semantics or production bytes are patched.
    scoped_owner = types.SimpleNamespace(**{name: getattr(owner, name) for name in
        ('DIRECTORY', 'PROTOCOL', '__file__')}, CASES=all_keys)
    function = types.FunctionType(previous.prepare.__code__,
        {**previous.prepare.__globals__, 'CASES': CASES, '_engine': engine_source, 'owner': scoped_owner},
        name='prepare_ten_original_owner_cases_v7', argdefs=previous.prepare.__defaults__, closure=previous.prepare.__closure__)
    function.__kwdefaults__ = previous.prepare.__kwdefaults__
    plan = function(source=source, case_id=case_id, output=output, deadline=deadline, serial=serial)
    output = Path(output)
    (output / 'v6-preparation-plan.json').write_bytes((output / 'plan.json').read_bytes())
    directory = output / 'native-environment-fixtures'
    observer = directory / 'Task15PageOwnerObserverV5.js'
    observer.write_text(observer_source())
    bindings = core.load(output / 'actual-source-bindings.json')
    # Discover the actual retry button through the same token scanner. UI and
    # closed-layout eligibility are still independently checked at runtime.
    script = """const fs=require('node:fs'),path=require('node:path'),b=require(process.argv[1]);
const base=JSON.parse(fs.readFileSync(process.argv[2])),found=[];
for(const file of base.sourceFiles)for(const node of b.controls(fs.readFileSync(path.join(base.source,file.path),'utf8'),file.path))
if(node.type==='Button'&&node.label==='Retry'&&node.handlers.some(body=>body.includes('true')&&(body.includes('deactivateAccount')||body.includes('submitDeactivation'))))found.push(node);
if(found.length!==1)throw Error('Unbound/ambiguous actual retry control');process.stdout.write(JSON.stringify(found[0]));"""
    import subprocess
    process = subprocess.run([previous.NODE, '-e', script, str(previous.BINDER), str(output / 'actual-source-bindings.json')],
        cwd=core.ROOT, capture_output=True, text=True, check=True,
        timeout=min(30, core.remaining_deadline(deadline, 'Actual retry source binding')))
    retry = json.loads(process.stdout)
    bindings['controlBindings']['retry'] = retry
    bindings['controlSelectors']['retry'] = {'id': retry['id']} if retry['id'] else {'type': 'Button', 'text': retry['label']}
    core.write(output / 'actual-source-bindings.json', bindings)
    installer = directory / 'Task15NativeUi.install.cjs'
    code = installer.read_text()
    code = transport.replace(code, '  const observedSources = new Set(',
        '  binding.controlSelectors.retry = ' + json.dumps(bindings['controlSelectors']['retry']) + ';\n  const observedSources = new Set(')
    installer.write_text(code)
    files = {item['path']: item for item in plan['evaluator']['files']}
    for path in (Path(__file__), observer, directory / 'Task15FreshActionsV2.js',
                 Path(__file__).with_name('full_native_14_15_guard_v1.py'),
                 Path(__file__).with_name('full_native_14_15_runner_v1.py')):
        files[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}
    records = [files[key] for key in sorted(files)]
    plan.update(role='agent', fullNativeProtocol=PROTOCOL, pageOwnerProtocol=PROTOCOL,
        actualSourceBindings=transport.artifacts.artifact(output / 'actual-source-bindings.json'),
        evaluator={'protocol': transport.PROTOCOL, 'files': records, 'sha256': transport.artifacts.row_digest(records)})
    manifest = directory / 'manifest.json'
    core.write(manifest, {'protocol': PROTOCOL, 'files': [transport.artifacts.artifact(path)
        for path in sorted(directory.iterdir()) if path.is_file() and path != manifest]})
    plan['derivedFiles'] = [transport.artifacts.artifact(path) for path in sorted(directory.iterdir()) if path.is_file()] + [
        transport.artifacts.artifact(output / 'fresh-host.cjs')]
    core.write(output / 'plan.json', plan)
    return plan
