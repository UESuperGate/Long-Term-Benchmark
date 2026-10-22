'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');
const runner = path.resolve(__dirname, '../../../../scripts/runtime_semantics/arkts_native_smoke.cjs');
const { withTemporaryWorkspace } = require(runner);

test('successful work is removed before its report is returned', async () => {
  let work;
  const result = await withTemporaryWorkspace(async directory => {
    work = directory;
    fs.writeFileSync(path.join(work, 'generated.txt'), 'test');
    return { report: {} };
  });
  assert.equal(fs.existsSync(work), false);
  assert.equal(result.report.temporaryProjectRemoved, true);
});

for (const stage of ['generation', 'build']) {
  test(`${stage} rejection removes work and preserves the original error`, async () => {
    let work;
    const error = new Error(`${stage} failed`);
    await assert.rejects(withTemporaryWorkspace(async directory => {
      work = directory;
      fs.writeFileSync(path.join(work, 'partial.txt'), 'test');
      if (stage === 'build') await Promise.resolve();
      throw error;
    }, { prepareOnly: stage === 'generation' }), failure => failure === error);
    assert.equal(fs.existsSync(work), false);
  });
}

for (const options of [{ keepTemp: true }, { prepareOnly: true }]) {
  test(`explicit retention is honored: ${JSON.stringify(options)}`, async () => {
    let work;
    try {
      await withTemporaryWorkspace(async directory => {
        work = directory;
        return { prepared: true, report: {} };
      }, options);
      assert.equal(fs.existsSync(work), true);
    } finally {
      if (work) fs.rmSync(work, { recursive: true, force: true });
    }
  });
}

test('CLI generation failure cleans its workspace without starting a build', () => {
  const evidence = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-native-cleanup-test-'));
  try {
    const result = spawnSync(process.execPath, [runner, '--bundle', 'invalid-cleanup-test',
      '--role', 'final', '--output-dir', evidence], { encoding: 'utf8', timeout: 30000 });
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /No selected tasks: invalid-cleanup-test/);
    assert.doesNotMatch(result.stdout, /hvigor/);
    const runs = fs.readdirSync(path.join(evidence, 'native'));
    assert.equal(runs.length, 1);
    const workName = runs[0].slice(runs[0].indexOf('ltb-arkts-native-'));
    assert.equal(fs.existsSync(path.join(os.tmpdir(), workName)), false);
  } finally {
    fs.rmSync(evidence, { recursive: true, force: true });
  }
});
