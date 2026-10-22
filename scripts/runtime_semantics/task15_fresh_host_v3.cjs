'use strict';

// One process, one source-parameterized production VM, one canonical host case.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const runtime = require('./arkts_runtime.cjs');
const apiBindings = require('../../state_tests/runtime/arkts/native/CandidateApiBindings.cjs');
const PROTOCOL = 'task15.arkts.own-host-episode.v3';
const keys = new Set(['default_form_blocks_submit', 'password_enables_submit', 'erase_data_option',
  'success_completes', 'close_dialog_resets_action']);
const clone = value => JSON.parse(JSON.stringify(value));
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const need = (condition, reason) => { if (!condition) throw Error(reason); };

async function run(plan) {
  const spec = plan.canonicalCase, nonce = crypto.randomBytes(16).toString('hex');
  const raw = { protocol: PROTOCOL, taskId: '15_account_deactivation', role: 'agent',
    caseId: spec.caseId, traceDigest: spec.traceDigest, canonicalCase: clone(spec),
    source: fs.realpathSync(plan.source), evaluatorSha256: plan.evaluator.sha256,
    executionNonce: nonce, episodeId: nonce + ':' + spec.caseId, startedAt: Date.now(),
    deadlineEpochMs: plan.deadlineEpochMs, outcome: 'not_scored', actions: [], frames: [],
    productionSources: [], calls: [], externalRequests: [], error: null, cleanup: null };
  let sequence = 0, receiver, exports, api, completedCallbacks = 0;
  const pending = [], returned = [];
  const budget = () => need(Number.isFinite(plan.deadlineEpochMs) && Date.now() < plan.deadlineEpochMs,
    'Whole scorer deadline exhausted');
  const receipt = async (phase, kind, method, args, fn) => {
    budget();
    const item = { sequence: ++sequence, phase, kind, method, args: clone(args), executed: false,
      episodeId: raw.episodeId, callStart: raw.calls.length, startedAt: Date.now() };
    raw.actions.push(item);
    try { const result = fn(); item.executed = true; return result; }
    finally { item.callEnd = raw.calls.length; item.finishedAt = Date.now(); }
  };
  const invoke = async (phase, method, ...args) => {
    need(receiver && typeof receiver[method] === 'function', 'Production API unavailable: ' + method);
    let value;
    await receipt(phase, 'production_method', method, args, () => {
      value = receiver[method](...args);
      if (value && typeof value.then === 'function') returned.push(value);
    });
    return { value };
  };
  const flush = async () => { for (let i = 0; i < 24; i++) { budget(); await Promise.resolve(); } };
  const external = {
    async restore() {}, async canDeactivateAccount() { return true; },
    deactivateAccount(password, eraseData) {
      budget();
      const request = { id: raw.externalRequests.length + 1, password, eraseData,
        episodeId: raw.episodeId, settlement: 'pending', sequence: ++sequence };
      raw.externalRequests.push(request);
      return new Promise((resolve, reject) => pending.push({ request, resolve, reject }));
    }
  };
  const settle = async (phase, status) => {
    const item = pending.find(item => item.request.settlement === 'pending');
    need(item, 'Actual production request not pending');
    await receipt(phase, 'external_response', 'deactivation_response', [item.request.id, status], () => {
      item.request.settlement = status;
      if (status === 'fulfilled') item.resolve(); else item.reject(Error('Evaluator external gateway failure'));
    });
    await flush();
  };
  const read = () => {
    const getter = typeof receiver.submitEnabled === 'function' ? 'submitEnabled' : 'canSubmit';
    need(typeof receiver[getter] === 'function', 'Production submit-state getter unavailable');
    return { password: receiver.password, eraseData: receiver.eraseData,
      action: exports.DEACTIVATION_SUCCEEDED !== undefined && receiver.action === exports.DEACTIVATION_SUCCEEDED ? 'success' : receiver.action,
      rawAction: receiver.action, requestCount: raw.externalRequests.length,
      submitEnabled: receiver[getter](), submitGetter: getter, completionCallbacks: completedCallbacks };
  };
  const capture = label => {
    budget();
    const state = read();
    const frame = { label, sequence: ++sequence, at: Date.now(), episodeId: raw.episodeId,
      receiverId: nonce + ':production-presenter-1', state: clone(state), callCount: raw.calls.length,
      requests: clone(raw.externalRequests) };
    raw.frames.push(frame); return frame;
  };
  try {
    budget();
    need(spec.taskId === raw.taskId && keys.has(spec.key), 'Not an audited own host case');
    need(plan.protocol === 'task15.arkts.full-ten-case.v3', 'No full-report producer plan');
    for (const item of plan.evaluator.files) {
      const bytes = fs.readFileSync(item.path);
      need(bytes.length === item.bytes && hash(bytes) === item.sha256, 'Frozen evaluator changed: ' + item.path);
    }
    need(plan.evaluator.files.some(item => path.resolve(item.path) === __filename), 'Host producer not source-bound');
    api = apiBindings.exportedClass(raw.source, 'AccountDeactivationPresenter');
    const load = runtime.productionLoader(raw.source, raw.productionSources, raw.calls);
    exports = load(api.path);
    need(typeof exports.AccountDeactivationPresenter === 'function', 'Original production export missing');
    const client = typeof exports.AccountDeactivationPresenter.prototype.refreshAvailability === 'function' &&
      typeof exports.AccountDeactivationPresenter.prototype.openForm === 'function';
    raw.apiBinding = { path: api.path, sha256: hash(fs.readFileSync(path.join(raw.source, api.path))),
      class: 'AccountDeactivationPresenter', shape: client ? 'clientCallback' : 'capabilityService' };
    // The default-form case observes constructor/openForm defaults, never setter-corrected defaults.
    await receipt(spec.key === 'default_form_blocks_submit' ? 'event' : 'setup',
      'production_constructor', 'AccountDeactivationPresenter', [], () => {
        receiver = new exports.AccountDeactivationPresenter(external,
          client ? () => { completedCallbacks++; } : external);
      });
    capture('constructor_defaults');
    if (client) {
      const available = await invoke('setup', 'refreshAvailability');
      await available.value;
      await invoke(spec.key === 'default_form_blocks_submit' ? 'event' : 'setup', 'openForm');
    }
    if (spec.key === 'default_form_blocks_submit') {
      raw.givenMode = 'constructor_defaults_no_setter_repair';
      capture('after_event');
    } else {
      raw.givenMode = 'observed_before_event';
      if (spec.given.password !== undefined) await invoke('setup', 'setPassword', spec.given.password);
      else if (spec.given.action === 'loading') await invoke('setup', 'setPassword', 'secret');
      if (spec.given.eraseData !== undefined) await invoke('setup', 'setEraseData', spec.given.eraseData);
      if (['loading', 'failure'].includes(spec.given.action)) {
        await invoke('setup', 'deactivateAccount', false);
        await invoke('setup', 'deactivateAccount', false);
        await flush();
        if (spec.given.action === 'failure') await settle('setup', 'rejected');
      }
      const before = capture('before_event');
      need(Object.entries(spec.given).every(([key, value]) => before.state[key] === value),
        'Own canonical given not established through production operations');
      if (spec.event.name === 'set_password') await invoke('event', 'setPassword', spec.event.value);
      else if (spec.event.name === 'set_erase_data') await invoke('event', 'setEraseData', spec.event.value);
      else if (spec.event.name === 'deactivation_succeeds') await settle('event', 'fulfilled');
      else if (spec.event.name === 'close_dialogs') await invoke('event', 'closeDialogs');
      else throw Error('Unsupported canonical host event');
      await flush(); capture('after_event');
    }
    raw.outcome = 'transition_observed';
  } catch (error) { raw.error = String(error.stack || error); }
  finally {
    // Settle only the evaluator's external promises; never mutate presenter state for cleanup.
    for (const item of pending) if (item.request.settlement === 'pending') item.resolve();
    await Promise.allSettled(returned);
    raw.cleanup = { externalPendingReleased: true, productionFieldsAssignedByEvaluator: false,
      vmEpisodeDiscardedAtProcessExit: true, noDeviceOrBuildStarted: true };
    raw.finishedAt = Date.now();
  }
  return raw;
}

module.exports = { run, PROTOCOL };
if (require.main === module) {
  const pairs = process.argv.slice(2);
  const args = Object.fromEntries(pairs.map((item, i) => i % 2 ? null : [item, pairs[i + 1]]).filter(Boolean));
  const plan = JSON.parse(fs.readFileSync(args['--plan'], 'utf8'));
  run(plan).then(raw => {
    fs.writeFileSync(plan.rawOutput, JSON.stringify(raw, null, 2) + '\n');
    console.log(JSON.stringify({ caseId: raw.caseId, outcome: raw.outcome, episodeId: raw.episodeId }));
  }).catch(error => { console.error(String(error)); process.exitCode = 1; });
}
