'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { evaluateClockCase, CASE } = require('./Task14Clock.cjs');
const ROOT = path.resolve(__dirname, '../../..');
const FEATURE = 'entry/src/main/ets/features/JoinRoomByAddressFeature.ets';
const hash = data => crypto.createHash('sha256').update(data).digest('hex');

const mutations = [
  { id: 'wrong100', from: 'ADDRESS_DEBOUNCE_MS: number = 300;', to: 'ADDRESS_DEBOUNCE_MS: number = 100;' },
  { id: 'wrong600', from: 'ADDRESS_DEBOUNCE_MS: number = 300;', to: 'ADDRESS_DEBOUNCE_MS: number = 600;' },
  { id: 'two300serial', from: '    await delay(ADDRESS_DEBOUNCE_MS);',
    to: '    await delay(ADDRESS_DEBOUNCE_MS);\n    await delay(ADDRESS_DEBOUNCE_MS);' },
  { id: 'stateResolvingearly',
    from: '    this.address = value.trim();\n    this.addressState = RoomAddressState.Unknown;',
    to: '    this.address = value.trim();\n    this.addressState = RoomAddressState.Resolving;' },
  { id: 'staleresponse',
    from: '    const resolved: ResolvedRoomAlias | undefined = await this.resolveWithTimeout(this.address);\n    if (token !== this.updateToken) {\n      return;\n    }',
    to: '    const resolved: ResolvedRoomAlias | undefined = await this.resolveWithTimeout(this.address);' }
];

async function runMutations(project, caseSpec) {
  const file = path.join(project, FEATURE);
  const original = fs.readFileSync(file, 'utf8');
  const rows = [];
  for (const mutation of mutations) {
    if (original.split(mutation.from).length !== 2) throw new Error(`Mutation anchor not unique: ${mutation.id}`);
    const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'Task14Clock-mutant-'));
    try {
      const destination = path.join(temporary, FEATURE);
      fs.mkdirSync(path.dirname(destination), { recursive: true });
      // Generated negative-control candidates only; the original project is read-only.
      const mutant = original.replace(mutation.from, mutation.to);
      fs.writeFileSync(destination, mutant);
      rows.push({ mutation: mutation.id, originalSha256: hash(original), mutantSha256: hash(mutant),
        change: { from: mutation.from, to: mutation.to }, result: await evaluateClockCase(temporary, caseSpec) });
    } finally { fs.rmSync(temporary, { recursive: true, force: true }); }
  }
  const unchanged = hash(fs.readFileSync(file)) === hash(original);
  if (!unchanged) throw new Error('Original candidate changed while running mutations');
  return { schemaVersion: 1, scope: 'host_transpiled_production; generated disposable negative controls, not candidate scores',
    original: { path: file, sha256: hash(original), unchanged }, caseId: caseSpec.caseId, traceDigest: caseSpec.traceDigest,
    generatedAt: new Date().toISOString(), temporaryCandidatesRemoved: true,
    mutationRunner: { path: __filename, sha256: hash(fs.readFileSync(__filename)) },
    mutations: rows, detected: rows.filter(row => row.result.status === 'fail').length, total: rows.length };
}

module.exports = { runMutations, mutations, FEATURE };
if (require.main === module) {
  const args = process.argv.slice(2);
  if (!args.includes('--output')) throw new Error('--output required');
  const spec = JSON.parse(fs.readFileSync(path.join(ROOT, 'benchmark_tasks/14_join_room_by_address/transitions.json')))
    .cases.find(item => item.caseId === CASE);
  const task = JSON.parse(fs.readFileSync(path.join(ROOT, 'benchmark_tasks/14_join_room_by_address/task.json')));
  runMutations(path.join(ROOT, task.arkts.finalPath), spec).then(report => {
    const output = path.resolve(args[args.indexOf('--output') + 1]);
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ output, detected: report.detected, total: report.total }));
    if (report.detected !== report.total) process.exitCode = 1;
  }).catch(error => { console.error(error); process.exitCode = 1; });
}
