'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const fixtureFile = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/task10_base_closure/reviewed_closure.json');
const FIXTURE_SHA256 = '9aa41b120668bc9b6cfee08c185af24fe99645d6ff7739b52e8ba52d78c46190';
const volatile = new Set(['bounds', 'origBounds', 'hierarchy', 'hostWindowId', 'focused',
  'windowId', 'key', 'zIndex', 'debugLine', 'hashcode', 'index']);

function projectTree(node) {
  if (!node || typeof node !== 'object' || Array.isArray(node) ||
      Object.keys(node).some(key => !['attributes', 'children'].includes(key)) ||
      !node.attributes || typeof node.attributes !== 'object' || Array.isArray(node.attributes) ||
      !Array.isArray(node.children || [])) throw new Error('Incomplete/unknown native UI tree');
  const attributes = {};
  for (const key of Object.keys(node.attributes).sort()) if (!volatile.has(key)) attributes[key] = node.attributes[key];
  return { attributes, children: (node.children || []).map(projectTree) };
}

function loadFixture() {
  const bytes = fs.readFileSync(fixtureFile);
  if (crypto.createHash('sha256').update(bytes).digest('hex') !== FIXTURE_SHA256)
    throw new Error('Reviewed Task10 closure fixture hash mismatch');
  const fixture = JSON.parse(bytes);
  if (fixture.taskId !== '10_media_upload_quality' || fixture.schemaVersion !== 1)
    throw new Error('Reviewed Task10 closure fixture identity mismatch');
  return fixture;
}

function assessBaseEntry(inventory, layout) {
  const fixture = loadFixture();
  const result = { guardId: fixture.guardId, eligible: false, status: 'not_scored',
    fixture: { path: fixtureFile, bytes: fs.statSync(fixtureFile).size, sha256: FIXTURE_SHA256 },
    sourceInventory: inventory, reason: 'Unreviewed production closure or unknown/extra/renamed UI; never semantic missing-entry.' };
  if (inventory.files !== fixture.fullInputInventory.files || inventory.sha256 !== fixture.fullInputInventory.sha256)
    return result;
  try {
    if (JSON.stringify(projectTree(layout)) !== JSON.stringify(fixture.initialUiProjection)) return result;
  } catch (_) { return result; }
  return { ...result, eligible: true, status: 'eligible_for_real_common_prefix_only',
    reason: 'Reviewed complete production closure and full initial UI match; actual per-case prefix still required.' };
}
module.exports = { projectTree, assessBaseEntry, loadFixture, fixtureFile, FIXTURE_SHA256 };
