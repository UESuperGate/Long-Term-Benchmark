'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { deriveBuilder } = require('./runtime_semantics/task17_arkts_owner_build.cjs');

const oldInstaller = "const installer = taskId === '16_identity_reset' &&\n" +
  "            ['ir_state_005_oidc_handle_routes_and_resets', 'ir_state_010_cancel_cleans_up'].includes(caseId)\n" +
  "            ? 'Task16NativeUi.install.cjs' : taskId === '17_pinned_messages' && caseId === 'pm_state_001_open_loading'\n" +
  "              ? 'Task17LoadingUi.install.cjs' : 'Tasks16_18NativeUi.install.cjs';";

function sharedBuilder() {
  return "const root = path.resolve(__dirname, '../..');\n" +
    "const smoke = require('./arkts_native_smoke.cjs');\n" +
    "const bundle = require('./arkts_native_bundle.cjs');\n" + oldInstaller + "\n" +
    "          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native', installer)).install(work);\n";
}

test('Task17 owner derivation binds every Task17 case and explicit role', () => {
  const derived = deriveBuilder(sharedBuilder());
  assert.match(derived, /Task17OwnerNativeUi\.install\.cjs/);
  assert.match(derived, /\.install\(work, role\)/);
  assert.doesNotMatch(derived, /Task17LoadingUi\.install\.cjs/);
  assert.doesNotMatch(derived, /path\.resolve\(__dirname, '\.\.\/\.\.'\)/);
});

test('Task17 owner derivation fails closed when the shared builder shape changes', () => {
  assert.throws(() => deriveBuilder('const changed = true;'), /Shared builder shape changed/);
});
