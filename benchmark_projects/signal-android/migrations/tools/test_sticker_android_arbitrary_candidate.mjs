import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const tools = path.dirname(new URL(import.meta.url).pathname);
const migrations = path.resolve(tools, '..');
const migration = path.join(migrations, '02_sticker_management');
const project = path.join(migration, 'android', 'base');
const scorer = path.join(migration, 'android', 'evaluator', 'run-semantic.mjs');
const contract = JSON.parse(fs.readFileSync(path.join(migration, 'canonical', 'transitions.json'), 'utf8'));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'signal-sticker-arbitrary-candidate-test-'));

const score = (name, terminalFailure) => {
  const observations = path.join(temporary, `${name}.jsonl`);
  const output = path.join(temporary, `${name}.json`);
  fs.writeFileSync(observations, `${contract.cases.map(item => JSON.stringify({
    caseId: item.caseId,
    productionEntrypoint: 'Android application ClassLoader public integration gate',
    before: null,
    after: null,
    effects: [],
    givenEstablished: false,
    terminalFailure,
    availability: 'executed_android_application_runtime_capability_gate'
  })).join('\n')}\n`);
  const result = spawnSync(process.execPath, [
    scorer,
    '--project', project,
    '--role', 'agent',
    '--output', output,
    '--observations', observations,
    '--native-device', 'unit-runtime-receipt'
  ], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return JSON.parse(fs.readFileSync(output, 'utf8'));
};

try {
  const valid = score('valid', {
    kind: 'mandatory_public_integration_contract_unavailable_after_app_launch',
    appRuntimeReached: true,
    missingDeclarations: ['org.thoughtcrime.securesms.stickers.StickerManagementViewModel#installStickerPack/1']
  });
  assert.deepEqual(
    [valid.semantic.passed, valid.semantic.failed, valid.semantic.notScored, valid.semantic.total],
    [0, 10, 0, 10]
  );
  assert.ok(valid.semantic.cases.every(item => item.reason === 'mandatory_public_integration_contract_unavailable_in_android_app_runtime'));

  const malformed = score('malformed', {
    kind: 'mandatory_public_integration_contract_unavailable_after_app_launch',
    appRuntimeReached: true,
    missingDeclarations: []
  });
  assert.deepEqual(
    [malformed.semantic.passed, malformed.semantic.failed, malformed.semantic.notScored, malformed.semantic.total],
    [0, 0, 10, 10]
  );

  const prepare = fs.readFileSync(path.join(tools, 'prepare_agent_harness.mjs'), 'utf8');
  const build = fs.readFileSync(path.join(tools, 'build_android_agent_harness.sh'), 'utf8');
  const gate = fs.readFileSync(path.join(migration, 'android', 'evaluator', 'runtime-gate', 'MandatoryStickerContractProbe.kt'), 'utf8');
  assert.ok(prepare.indexOf('public-integration-contract') < prepare.indexOf('reachable-legacy-production-prefix'));
  assert.ok(prepare.indexOf('reachable-legacy-production-prefix') < prepare.indexOf('mandatory-public-abi-runtime-gate'));
  assert.match(build, /first_compile_compatible_public_action_bridge/);
  assert.doesNotMatch(build, /rg |grep /);
  assert.match(gate, /application\.javaClass\.classLoader/);
  assert.doesNotMatch(gate, /readText|exists|java\.io\.File/);

  process.stdout.write('PASS sticker arbitrary-candidate runtime gate: 8/8 checks passed\n');
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
