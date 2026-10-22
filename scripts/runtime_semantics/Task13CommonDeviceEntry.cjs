'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const record = file => { const data = fs.readFileSync(file); return {path: file, bytes: data.length, sha256: sha(data)}; };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const closure = require('../../state_tests/runtime/arkts/native/Task13UiClosure.cjs');
const { bind } = require('../../state_tests/runtime/arkts/native/Task13PageBinding.cjs');

function value(flag) {
  const index = process.argv.indexOf(flag);
  if (index < 0 || !process.argv[index + 1]) throw Error(flag + ' required');
  return process.argv[index + 1];
}

function flatten(node, result = []) {
  if (node.attributes) result.push(node.attributes);
  for (const child of node.children || []) flatten(child, result);
  return result;
}

function classify(nodes) {
  const visible = id => nodes.filter(node => node.id === id && node.visible === 'true');
  const dm = visible('start_direct_message');
  const verification = [...visible('verify_user_action'), ...visible('withdraw_verification_action'), ...visible('verification_unavailable')];
  if (dm.length === 1 && verification.length === 0) {
    const actual = nodes.filter(node => node.type);
    const root = actual.filter(node => node.type === 'root');
    if (root.length !== 1) throw Error('Original UI inventory has no unique root');
    const match = /^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$/.exec(root[0].bounds || '');
    if (!match) throw Error('Original root bounds missing');
    closure.validate(closure.fromLayout(actual, { left: +match[1], top: +match[2], right: +match[3], bottom: +match[4] }));
    return 'base';
  }
  if (dm.length <= 1 && verification.length === 1) return 'final';
  throw Error('Common production profile binding unavailable or ambiguous');
}

async function main() {
  const source = fs.realpathSync(value('--source'));
  const output = path.resolve(value('--output'));
  const buildPath = path.resolve(value('--build-report'));
  const serial = value('--serial');
  const hdc = value('--hdc');
  if (fs.existsSync(output)) throw Error('Refusing existing discovery evidence');
  fs.mkdirSync(output, {recursive: true});
  const build = JSON.parse(fs.readFileSync(buildPath));
  const bundle = json5.parse(fs.readFileSync(path.join(source, 'AppScope/app.json5'), 'utf8')).app.bundleName;
  if (build.source !== source || build.passed !== true || build.productionUnchanged !== true ||
      build.hap.sha256 !== record(build.hap.path).sha256) throw Error('Discovery HAP/source binding differs');
  const commands = [], layouts = [], remoteFiles = [];
  let sequence = 0;
  const nonce = crypto.randomBytes(12).toString('hex');
  const run = (args, allowed = [0]) => {
    const result = spawnSync(hdc, ['-t', serial, ...args], {encoding: 'utf8', timeout: 30000, maxBuffer: 8 * 1024 * 1024});
    const text = (result.stdout || '') + (result.stderr || '');
    const log = path.join(output, String(++sequence).padStart(5, '0') + '.log');
    fs.writeFileSync(log, text);
    commands.push({args, exitCode: result.status, log: record(log)});
    if (result.error || !allowed.includes(result.status)) throw Error('Device discovery command failed: ' + text);
    return text;
  };
  const dump = label => {
    const remote = '/data/local/tmp/ltb-task13-discovery-' + nonce + '-' + sequence + '.json';
    remoteFiles.push(remote);
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', bundle]);
    let parsed;
    for (let attempt = 0; attempt < 5; attempt++) {
      try { parsed = JSON.parse(run(['shell', 'cat', remote])); break; }
      catch (error) {
        if (!(error instanceof SyntaxError) || !error.message.includes('Unexpected end of JSON') || attempt === 4) throw error;
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50);
      }
    }
    const nodes = flatten(parsed);
    const roots = nodes.filter(node => node.type === 'root');
    if (roots.length !== 1 || roots[0].bundleName !== bundle || roots[0].pagePath !== 'pages/Index' || roots[0].focused !== 'true') {
      throw Error('Discovery did not observe the focused production page');
    }
    const file = path.join(output, label + '-' + sequence + '.layout.json');
    fs.writeFileSync(file, JSON.stringify(parsed, null, 2));
    layouts.push({label, layout: record(file)});
    return nodes;
  };
  const waitFor = async (label, predicate) => {
    for (let attempt = 0; attempt < 40; attempt++) {
      try { const nodes = dump(label); if (predicate(nodes)) return nodes; }
      catch (error) { if (!error.message.startsWith('Discovery did not observe')) throw error; }
      await sleep(150);
    }
    throw Error('Production profile UI timed out: ' + label);
  };
  const visible = (nodes, id) => nodes.filter(node => node.id === id && node.visible === 'true');
  const click = (nodes, id) => {
    const matches = visible(nodes, id);
    if (matches.length !== 1 || matches[0].enabled !== 'true') throw Error('Production control is unavailable: ' + id);
    const bounds = /^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$/.exec(matches[0].bounds || '');
    if (!bounds) throw Error('Missing production control bounds');
    run(['shell', 'uitest', 'uiInput', 'click', String(Math.round((+bounds[1] + +bounds[3]) / 2)), String(Math.round((+bounds[2] + +bounds[4]) / 2))]);
  };
  let observedBinding, positiveControl, freshInstall = false, ownedAppUninstalled = false;
  try {
    run(['uninstall', bundle], [0, 255]);
    const absent = run(['shell', 'bm', 'dump', '-n', bundle], [0, 255]);
    if (!/failed|not exist|error/i.test(absent)) throw Error('Production app was not absent before discovery');
    run(['install', '-r', build.hap.path]);
    freshInstall = true;
    run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundle, '-m', 'entry']);
    const before = await waitFor('profile', nodes => nodes.some(node => node.text === '@alice:example.org' && node.visible === 'true'));
    observedBinding = classify(before);
    await sleep(150);
    if (classify(dump('profile-stable')) !== observedBinding) throw Error('Production entry changed between samples');
    if (observedBinding === 'base') {
      click(before, 'start_direct_message');
      await waitFor('direct-message-opened', nodes => nodes.some(node => node.text === 'Opening direct message' && node.visible === 'true'));
      positiveControl = 'production_direct_message_opened';
    } else {
      if (visible(before, 'verification_unavailable').length === 1) {
        click(before, 'start_direct_message');
        await waitFor('sdk-unavailable-dm-opened', nodes => nodes.some(node => node.text === 'Opening direct message' && node.visible === 'true'));
        positiveControl = 'production_sdk_unavailable_profile_dm_opened';
      } else {
      let unverified = before;
      if (visible(before, 'withdraw_verification_action').length) {
        click(before, 'withdraw_verification_action');
        unverified = await waitFor('withdrawn', nodes => visible(nodes, 'verify_user_action').length === 1 &&
          ['profile_verification_violation', 'timeline_identity_warning', 'room_member_identity_warning', 'withdraw_verification_action']
            .every(id => visible(nodes, id).length === 0));
      }
      click(unverified, 'verify_user_action');
      await waitFor('verification-flow', nodes => visible(nodes, 'request_user_verification').length === 1 ||
        visible(nodes, 'verification_remote_accepted').length === 1);
      positiveControl = 'production_verify_user_flow_opened';
      }
    }
  } finally {
    run(['uninstall', bundle], [0, 255]);
    ownedAppUninstalled = true;
    for (const remote of remoteFiles) run(['shell', 'rm', '-f', remote], [0, 255]);
  }
  const result = {schemaVersion: 1, taskId: '13_user_verification', source, bundleName: bundle,
    status: 'production_common_entry_completed', observedBinding, positiveControl,
    pageBinding: bind(source, observedBinding),
    freshInstall, ownedAppUninstalled, build: record(buildPath), commands, layouts};
  fs.writeFileSync(path.join(output, 'discovery.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify({observedBinding, positiveControl}));
}

module.exports = {classify};
if (require.main === module) main().catch(error => { console.error(error.stack); process.exitCode = 1; });
