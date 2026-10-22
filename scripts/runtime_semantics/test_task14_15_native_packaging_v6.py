"""Offline integration: actual candidate sources, real bundle and fixture installers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from . import task14_actual_routes_packaging_v4 as task14
from . import task14_actual_routes_scorer_v4 as scorer
from . import task15_page_owner_packaging_v6 as task15
from . import task15_page_owner_admission_v6 as admission
from . import task15_fresh_protocol_v2 as old15

ROOT = task14.ROOT
EVIDENCE = ROOT / 'experiment_results/runtime_transition_20261020'
SOURCES = EVIDENCE / 'postrun_task14_15_evaluator_repair_v1/sources'
NODE = task15.NODE


class PackagingTests(unittest.TestCase):
    def temporary(self):
        directory = tempfile.TemporaryDirectory(prefix='offline-task14-15-packaging-', dir=EVIDENCE)
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def test_task14_offline_source_parameterized_builder_has_real_installer(self):
        directory = self.temporary()
        source = SOURCES / '14_join_room_by_address/candidate'
        plan = task14.prepare(source=source, output=directory / 'plan', deadline=time.monotonic() + 3600)
        self.assertFalse(plan['ready'])
        self.assertEqual(set(plan['selectedCases']), task14.CASES)
        code = Path(plan['builder']['path']).read_text()
        self.assertIn(str(task14.DIRECTORY / 'install.cjs'), code)
        self.assertIn(str(source), (directory / 'plan/input-inventory.json').read_text())
        subprocess.run([NODE, '--check', plan['builder']['path']], check=True, capture_output=True, timeout=30)
        with self.assertRaises(ValueError):
            task14.prepare(source=source, output=directory / 'plan', deadline=time.monotonic() + 3600)

    def test_task14_unregistered_default_does_not_revive_old_host_route_score(self):
        directory = self.temporary()
        report = scorer.score(platform='arkts', source=SOURCES / '14_join_room_by_address/candidate',
            base_source=ROOT / '14_join_room_by_address_base_25_02_0',
            final_source=ROOT / 'final_dev_nodes/14_join_room_by_address_final_25_03_0',
            output=directory / 'default.json', compile_passed=True, compile_command='retained original standalone proof', timeout=2)
        self.assertEqual(report['semantic']['notScored'], 9)
        self.assertEqual(report['semantic']['failed'], 0)
        self.assertIs(report['compile']['passed'], True)
        self.assertFalse(report['publication']['eligible'])
        self.assertFalse(report['diagnostics']['hardwareStarted'])

    def test_task14_capture_requires_explicit_release(self):
        with self.assertRaisesRegex(ValueError, 'No hardware'):
            scorer.evaluate(source=ROOT, output=self.temporary() / 'denied', execute=False)

    def test_task15_all_five_own_cases_generate_native_wrappers_no_globals_changed(self):
        directory = self.temporary()
        before_cases = set(old15.NATIVE_CASES)
        source = ROOT / 'final_dev_nodes/15_account_deactivation_final_0_6_3'
        for case_id in sorted(task15.CASES):
            with self.subTest(case_id=case_id):
                plan = task15.prepare(source=source, case_id=case_id, output=directory / case_id,
                    deadline=time.monotonic() + 3600)
                self.assertEqual(plan['caseId'], case_id)
                self.assertEqual(plan['canonicalCase']['caseId'], case_id)
                self.assertFalse(plan['nativeProfileApproved'])
                engine = directory / case_id / 'native-environment-fixtures/Task15FreshActionsV2.js'
                code = engine.read_text()
                self.assertNotIn('launch.reload()', code)
                self.assertLess(code.index('observer = ports.observePage'), code.index('await integration.prepare'))
                self.assertIn("entry: selector('entry')", code)
                wrapper = engine.with_name('Task15NativeUi.js').read_text()
                self.assertIn('observePage: observeTask15OriginalPageOwnerV5', wrapper)
                self.assertIn('runTask15PageOwnerCaseV5', wrapper)
                subprocess.run([NODE, '--check', str(directory / case_id / 'fresh-host.cjs')],
                               capture_output=True, check=True, timeout=30)
        self.assertEqual(set(old15.NATIVE_CASES), before_cases)

    def test_task15_actual_final_and_candidate_install_new_observer_and_binding(self):
        directory = self.temporary()
        script = """
const fs = require('node:fs'), path = require('node:path');
const root = process.argv[1], planFile = process.argv[2], work = process.argv[3];
const plan = JSON.parse(fs.readFileSync(planFile)), source = plan.source;
fs.cpSync(source, work, { recursive: true, filter: file => !['.git','build','.hvigor','oh_modules','node_modules'].includes(path.basename(file)) });
fs.mkdirSync(path.join(work,'entry/src/test'), { recursive: true });
const evidence = path.join(work,'bundle-evidence'); fs.mkdirSync(evidence);
require(path.join(root,'scripts/runtime_semantics/arkts_native_bundle.cjs')).generate(
  work,evidence,'15_account_deactivation','agent',source,true,{device:true,caseId:plan.caseId});
const installer = path.join(path.dirname(planFile),'native-environment-fixtures/Task15NativeUi.install.cjs');
const report = require(installer).install(work);
const compiled = require(path.join(root,'scripts/runtime_semantics/offline_task14_15_fixture_compile_v1.cjs')).compileFixtures(work,report);
const crypto = require('node:crypto');
for(const fixture of report.fixtures) {
  const sha = crypto.createHash('sha256').update(fs.readFileSync(path.join(work,fixture.installedPath))).digest('hex');
  if(sha !== fixture.sha256) throw Error('Installed fixture hash differs');
}
process.stdout.write(JSON.stringify({binding:report.binding,productionUnchanged:report.productionUnchanged,
  fixtures:report.fixtures.map(item=>path.basename(item.installedPath)), compiled, scope:report.scope}));
"""
        for label, source in [('final', ROOT / 'final_dev_nodes/15_account_deactivation_final_0_6_3'),
                              ('candidate', SOURCES / '15_account_deactivation/candidate')]:
            with self.subTest(label=label):
                plan_root = directory / label
                task15.prepare(source=source, case_id='ad_state_003_password_enables_submit',
                    output=plan_root, deadline=time.monotonic() + 3600)
                result = subprocess.run([NODE, '-e', script, str(ROOT), str(plan_root / 'plan.json'), str(directory / (label + '-work'))],
                    capture_output=True, text=True, check=True, timeout=30)
                report = json.loads(result.stdout)
                self.assertTrue(report['productionUnchanged'])
                self.assertTrue(report['compiled']['passed'])
                self.assertFalse(report['compiled']['binariesRetained'])
                self.assertTrue(all(item['binary']['removed'] for item in report['compiled']['files']))
                if os.environ.get('LTB_OFFLINE_RECEIPT_DIR'):
                    receipt = Path(os.environ['LTB_OFFLINE_RECEIPT_DIR']) / ('task15-' + label + '.json')
                    with receipt.open('x') as stream:
                        json.dump({'label': label, **report['compiled']}, stream, indent=2); stream.write('\n')
                self.assertIn('Task15PageOwnerObserverV5.js', report['fixtures'])
                self.assertIn('Task15FreshActionsV2.js', report['fixtures'])
                self.assertEqual(report['binding']['ownerBinding']['pageSourcePath'],
                    'entry/src/main/ets/pages/Index.ets' if label == 'final' else 'entry/src/main/ets/components/AccountDeactivationControls.ets')
                self.assertEqual(report['binding']['controlSelectors']['close'],
                    {'type': 'Button', 'text': 'Close'} if label == 'final' else {'id': 'deactivation_failure_dismiss'})

    def test_task15_no_offline_profile_can_upgrade_old_host_rows(self):
        with self.assertRaisesRegex(ValueError, 'No source-bound actual native'):
            admission.admit({}, {}, profile_key='offline-discovery')


if __name__ == '__main__':
    unittest.main()
