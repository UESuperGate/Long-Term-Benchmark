import fs from 'node:fs';
import path from 'node:path';

const migration = path.resolve(process.argv[2]);
const contract = JSON.parse(fs.readFileSync(path.join(migration, 'canonical', 'transitions.json'), 'utf8'));
fs.mkdirSync(path.join(migration, 'results'), { recursive: true });

for (const platform of ['android', 'arkts']) {
  for (const role of ['base', 'final', 'agent']) {
    const report = {
      schemaVersion: 1,
      taskId: contract.taskId,
      platform,
      role,
      observationMode: 'runtime_state_transition',
      runtime: platform === 'android' ? 'jvm_focused_production_runtime' : 'arkts_production_store_host_binding',
      codeGeneration: { passed: role === 'agent' ? null : false, changedProductionFiles: [] },
      compile: { passed: null, command: null, reason: 'not_run_by_user_instruction' },
      semantic: {
        passed: 0,
        failed: 0,
        notScored: contract.cases.length,
        total: contract.cases.length,
        cases: contract.cases.map(item => ({
          caseId: item.caseId,
          traceDigest: item.traceDigest,
          status: 'not_scored',
          checkpoints: [],
          observed: null,
          invariantChecks: [],
          reason: 'runtime_not_executed'
        }))
      },
      diagnostics: { adapter: 'present_unexecuted', transport: 'not_attempted', runtimeCompile: 'not_attempted', publicationEligible: false }
    };
    fs.writeFileSync(path.join(migration, 'results', `${platform}-${role}.json`), `${JSON.stringify(report, null, 2)}\n`);
  }
}

const manifest = {
  schemaVersion: 1,
  taskId: contract.taskId,
  status: 'not_scored',
  generatedAt: '2026-10-22T00:00:00+08:00',
  reason: 'runtime_not_executed_by_user_instruction',
  publicationEligible: false,
  reports: Object.fromEntries(['android', 'arkts'].flatMap(platform => ['base', 'final', 'agent'].map(role => [`${platform}-${role}`, `${platform}-${role}.json`]))),
  requiredNextStep: 'Replace placeholders only with reports emitted by execution.json commands.'
};
fs.writeFileSync(path.join(migration, 'results', 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
