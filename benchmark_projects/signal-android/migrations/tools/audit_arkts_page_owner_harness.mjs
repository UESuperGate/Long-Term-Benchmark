import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const migrations = path.resolve(process.argv[2] ?? path.join(process.cwd(), 'benchmark_projects/signal-android/migrations'));
const outputFlag = process.argv.indexOf('--output');
const output = outputFlag >= 0 ? path.resolve(process.argv[outputFlag + 1]) : null;
const taskIds = ['01_media_keyboard', '02_sticker_management'];
const roles = ['base', 'final'];
const checks = [];

const check = (id, passed, detail) => checks.push({ id, passed, detail });
const read = file => fs.readFileSync(file, 'utf8');

for (const taskId of taskIds) {
  const task = path.join(migrations, taskId);
  const observerTexts = [];
  for (const role of roles) {
    const project = path.join(task, 'arkts', role);
    const page = read(path.join(project, 'entry/src/main/ets/pages/Index.ets'));
    const featureName = taskId === '01_media_keyboard' ? 'MediaKeyboardStore.ts' : 'StickerManagementStore.ts';
    const feature = read(path.join(project, 'entry/src/main/ets/feature', featureName));
    const observer = read(path.join(task, 'arkts/evaluator', role, 'RuntimeObserver.ets'));
    observerTexts.push(observer);

    const stateFields = [...page.matchAll(/@State\s+(?:private\s+)?([A-Za-z0-9_]+)/g)].map(match => match[1]);
    check(`${taskId}.${role}.page-single-owner`, /private readonly owner: .*PageOwner = new .*PageOwner\(\)/.test(page), 'ArkUI page creates exactly one production page owner');
    check(`${taskId}.${role}.page-no-business-state`, JSON.stringify(stateFields) === JSON.stringify(['revision']), `ArkUI @State fields: ${stateFields.join(',')}`);
    check(`${taskId}.${role}.page-no-filtering`, !/\.filter\s*\(/.test(page), 'ArkUI page does not reproduce store filtering');
    check(`${taskId}.${role}.owner-action-surface`, /this\.owner\.(selectTab|installPack|toggleSelection)\(/.test(page), 'Rendered controls call the same page owner actions used by the observer');
    check(`${taskId}.${role}.no-seed-api`, !/\bseed[A-Z_a-z0-9]*\s*\(/.test(feature) && !/\bseed[A-Z_a-z0-9]*\s*\(/.test(observer), 'No seed API exists in production or evaluator paths');
    check(`${taskId}.${role}.observer-reuses-owner`, /SemanticObserver\(owner: .*PageOwner\)/.test(observer), 'Observer requires the page-owned controller');
    check(`${taskId}.${role}.observer-no-detached-store`, !/new\s+(MediaKeyboardStore|GifStore|ConversationMediaStore|StickerManagementStore|StickerManagementRepository)\s*\(/.test(observer), 'Observer creates no detached production store or repository');
    check(`${taskId}.${role}.given-prefix-or-leaf`, /owner\.reopen\(\)/.test(observer) && /owner\.(initializeKeyboard|toggleSelection|installPack)\(/.test(observer) && /leaf\.(configure|replacePacks)/.test(observer), 'Given state is established by owner transitions and external leaves');
    if (taskId === '02_sticker_management') {
      check(`${taskId}.${role}.persistence-reopen`, /owner\.completeDrag\(0, 2\)[\s\S]*owner\.reopen\(\)[\s\S]*sm_state_005_drop_persists_order[\s\S]*persistEffects, true\)/.test(observer), 'Persistence case reloads a new store graph through the same page owner');
    }
  }
  check(`${taskId}.observer-role-parity`, observerTexts[0] === observerTexts[1], 'Base and final use the identical runtime observer');

  const canonical = JSON.parse(read(path.join(task, 'canonical/transitions.json')));
  const bindings = JSON.parse(read(path.join(task, 'arkts/bindings.json')));
  const canonicalDigests = new Map(canonical.cases.map(item => [item.caseId, item.traceDigest]));
  const bindingParity = bindings.cases.length === canonical.cases.length
    && bindings.cases.every(item => canonicalDigests.get(item.caseId) === item.traceDigest);
  check(`${taskId}.canonical-binding-parity`, bindingParity, 'Canonical case IDs and digests remain unchanged');
}

const inject = read(path.join(migrations, 'tools/inject_arkts_observer.mjs'));
const prepare = read(path.join(migrations, 'tools/prepare_agent_harness.mjs'));
const runner = read(path.join(migrations, 'tools/run_arkts_native_semantic.mjs'));
check('tools.inject-owner-argument', /SemanticObserver\}\(this\.owner\)/.test(inject) || /\$\{functionName\}\(this\.owner\)/.test(inject), 'Calibration injection passes the live page owner');
check('tools.agent-owner-argument', /\$\{functionName\}\(this\.owner\)/.test(prepare), 'Agent injection requires an executable page owner binding');
check('tools.runner-canonical-given', /subset\(observed\.given, item\.given\)/.test(runner), 'Runner verifies every canonical given from runtime evidence');
check('tools.runner-owner-identity', /native_page_owner_identity_mismatch/.test(runner), 'Runner rejects mixed or missing page owners');
check('tools.runner-no-presence-verdict', !/existsSync\([^\n]+(?:Store|Index|feature)/.test(runner), 'Semantic verdict does not depend on production filename presence');
check('tools.runner-reopen-gate', /persistenceReopened === true/.test(runner), 'Persistence invariant requires owner reopen evidence');

const failed = checks.filter(item => !item.passed);
const report = {
  schemaVersion: 1,
  classification: 'diagnostic_harness_structure_audit_not_semantic_scoring',
  scope: taskIds,
  passed: failed.length === 0,
  checks
};
const json = `${JSON.stringify(report, null, 2)}\n`;
if (output !== null) {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, json);
}
process.stdout.write(json);
process.exit(failed.length === 0 ? 0 : 1);
