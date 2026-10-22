'use strict';
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v11/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Task14 V12 derivation changed: ' + old);
  return text.replace(old, next);
};

function coreSource() {
  let source = previous.coreSource();
  source = replace(source,
    `      let result = await driver.findComponents(ports.selector(selector, config.bundleName));
      if (strict && result == null) {
        // A null filtered query is not absence evidence. Independently enumerate
        // the actual candidate window and match its concrete component fields.
        if (!state.driverInventory) {
          const all = await driver.findComponents(ports.selector({}, config.bundleName));
          if (!Array.isArray(all) || all.length === 0) throw new Error('Driver inventory unavailable during bracketed acquisition');
          state.driverInventory = [];
          for (const component of all) state.driverInventory.push({ component,
            id: await component.getId(), type: await component.getType(), text: await component.getText() });
          record({ method: 'Task14.driverInventory', windowId: state.windowId, routeName: state.routeName,
            queryScope: config.bundleName, count: all.length,
            components: state.driverInventory.map(({ id, type, text }) => ({ id, type, text })) });
        }
        const matching = state.driverInventory.filter(item => (!selector.id || item.id === selector.id) &&`,
    `      let result = await driver.findComponents(ports.selector(selector, config.bundleName));
      if (strict && !state.driverInventory) {
        const all = await driver.findComponents(ports.selector({}, config.bundleName));
        if (!Array.isArray(all) || all.length === 0) throw new Error('Driver inventory unavailable during bracketed acquisition');
        state.driverInventory = [];
        for (const component of all) state.driverInventory.push({ component,
          id: await component.getId(), type: await component.getType(), text: await component.getText(),
          bounds: await component.getBounds() });
        record({ method: 'Task14.driverInventory', windowId: state.windowId, routeName: state.routeName,
          queryScope: config.bundleName, count: all.length,
          components: state.driverInventory.map(({ id, type, text, bounds }) => ({ id, type, text, bounds })) });
      }
      if (strict && result == null) {
        // A null filtered query is not absence evidence. Independently match the
        // concrete component inventory from the focused candidate window.
        const matching = state.driverInventory.filter(item => (!selector.id || item.id === selector.id) &&`);
  source = replace(source,
    `      const visibilityKnown = typeof attrs?.visibility === 'string' &&
        (typeof opacity === 'number' || typeof opacity === 'string' && opacity.trim() !== '') && Number.isFinite(Number(opacity));
      const control = { selector, present: true, id, text, type, bounds, enabled: await component.isEnabled(),
        focused: await component.isFocused(), clickable: await component.isClickable(),
        visible: visibilityKnown ? attrs.visibility === 'Visibility.Visible' && Number(opacity) > 0 && intersects(bounds, state.viewport) : undefined,
        visibility: attrs?.visibility, opacity, inspectorMatches: exact.length,
        observationScope: 'Actual Driver + scoped inspector attributes/geometry, not screenshot occlusion' };`,
    `      const visibilityKnown = typeof attrs?.visibility === 'string' &&
        (typeof opacity === 'number' || typeof opacity === 'string' && opacity.trim() !== '') && Number.isFinite(Number(opacity));
      const driverIdentityMatches = strict && Array.isArray(state.driverInventory) ?
        state.driverInventory.filter(item => item.id === id && item.type === type && sameBounds(item.bounds, bounds)) : [];
      const driverGeometryVisible = !visibilityKnown && exact.length === 0 && typeof selector.id === 'string' &&
        id === selector.id && driverIdentityMatches.length === 1 && validRect(bounds) && intersects(bounds, state.viewport);
      const visible = visibilityKnown ?
        attrs.visibility === 'Visibility.Visible' && Number(opacity) > 0 && intersects(bounds, state.viewport) :
        driverGeometryVisible ? true : undefined;
      const control = { selector, present: true, id, text, type, bounds, enabled: await component.isEnabled(),
        focused: await component.isFocused(), clickable: await component.isClickable(), visible,
        visibility: attrs?.visibility, opacity, inspectorMatches: exact.length,
        visibilityEvidence: visibilityKnown ? 'scoped_inspector_attributes_and_geometry' :
          driverGeometryVisible ? 'unique_focused_driver_identity_and_geometry' : 'unavailable',
        driverIdentityMatches: driverIdentityMatches.length,
        observationScope: 'Actual focused Driver inventory plus scoped inspector attributes/geometry; no screenshot inference' };`);
  source = replace(source,
    `      const fresh = control.anchorSelector ? (await inspect(control.anchorSelector, state)).actionAncestor : await inspect(control.selector, state);`,
    `      const fresh = control.anchorSelector ? (await inspect(control.anchorSelector, state, true)).actionAncestor :
        await inspect(control.selector, state, true);`);
  return source;
}

function adapterSource() {
  return previous.adapterSource()
    .replace('evaluateTask14FullNativeV11', 'evaluateTask14FullNativeV12')
    .replaceAll('task14.full-nine-configured-sdk.v11', 'task14.full-nine-configured-sdk.v12')
    .replaceAll('fullNativeEpisodeV11', 'fullNativeEpisodeV12');
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV11 } from './Task14FullNativeV11.adapter';",
      "import { evaluateTask14FullNativeV12 } from './Task14FullNativeV12.adapter';")
    .replace('return evaluateTask14FullNativeV11(args, config, ports, record);',
      'return evaluateTask14FullNativeV12(args, config, ports, record);');
}

function expectedFixtures() {
  return previous.expectedFixtures()
    .filter(item => !['Task14DeviceUi.core.js', 'Task14FullNativeV11.adapter.js',
      'Task14DeviceUi.js'].includes(item.name))
    .concat([
      { name: 'Task14DeviceUi.core.js', sha256: hash(coreSource()) },
      { name: 'Task14FullNativeV12.adapter.js', sha256: hash(adapterSource()) },
      { name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) }
    ]);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v12' };
  const core = coreSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.core.js'), core);
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV11.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV12.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replace(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => path.basename(item.path) !== 'Task14FullNativeV11.adapter.js')
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  fixtures.push({ path: 'entry/src/test/Task14FullNativeV12.adapter.js', source: __filename,
    sha256: hash(adapter), derivedBy: __filename });
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    e2e: { ...report.e2e,
      modalVisibility: 'unique focused Driver identity plus in-viewport geometry when scoped inspector remains on the covered page' },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, e2eSource: previous.e2eSource, coreSource, adapterSource, bridgeSource,
  expectedFixtures, pageObserverAlias: previous.pageObserverAlias };
