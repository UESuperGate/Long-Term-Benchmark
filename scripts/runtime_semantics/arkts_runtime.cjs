#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

const DEFAULT_TYPESCRIPT = '/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript';
const ROOT = path.resolve(__dirname, '../..');

function snapshot(value) {
  const visited = new WeakSet();
  return JSON.parse(JSON.stringify(value, (_key, item) => {
    if (item === undefined) return { unavailable: 'undefined' };
    if (typeof item === 'bigint') return String(item);
    if (typeof item === 'function') return '[function]';
    if (item && typeof item === 'object') {
      if (visited.has(item)) return '[circular]';
      visited.add(item);
    }
    return item;
  }));
}

function productionLoader(project, evidence, calls, timerEnvironment) {
  const ts = require(process.env.LTB_TYPESCRIPT || DEFAULT_TYPESCRIPT);
  const root = fs.realpathSync(project);
  const cache = new Map();
  const nativeModules = new Map();
  const timers = { setTimeout, clearTimeout, setInterval, clearInterval, Date };
  if (timerEnvironment !== undefined) {
    for (const [name, value] of Object.entries(timerEnvironment)) {
      if (!Object.prototype.hasOwnProperty.call(timers, name) || typeof value !== 'function')
        throw new Error(`Unsupported production timer environment member: ${name}`);
      timers[name] = value;
    }
  }
  const context = vm.createContext({ console, ...timers, Promise, Map, Set });
  function load(request, parent = root) {
    if (request.startsWith('@ohos.') || request.startsWith('@kit.')) {
      if (!nativeModules.has(request)) {
        const unavailable = new Proxy({}, { get(_target, property) {
          calls.push({ module: request, method: String(property), unavailableNativeService: true });
          throw new Error(`Native service invocation has no runtime binding: ${request}.${String(property)}`);
        } });
        nativeModules.set(request, new Proxy({ default: unavailable }, { get(target, property) {
          if (property === 'default') return unavailable;
          return unavailable[property];
        } }));
      }
      return nativeModules.get(request);
    }
    if (request.startsWith('@') || (!request.startsWith('.') && parent !== root && !path.isAbsolute(request))) {
      throw new Error(`Native platform dependency has no runtime binding: ${request}`);
    }
    const stem = path.resolve(parent, request);
    const found = [stem, `${stem}.ets`, `${stem}.ts`, path.join(stem, 'index.ets')]
      .find(candidate => fs.existsSync(candidate) && fs.statSync(candidate).isFile());
    if (!found) throw new Error(`Production module not found: ${request}`);
    const file = fs.realpathSync(found);
    if (!file.startsWith(root + path.sep)) throw new Error(`Production import escapes candidate: ${request}`);
    if (!['.ets', '.ts'].includes(path.extname(file))) throw new Error(`Unsupported production module type: ${file}`);
    if (cache.has(file)) return cache.get(file).exports;
    const source = fs.readFileSync(file, 'utf8');
    const compiled = ts.transpileModule(source, {
      fileName: file.replace(/\.ets$/, '.ts'), reportDiagnostics: true,
      compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, experimentalDecorators: true },
    });
    const errors = (compiled.diagnostics || []).filter(d => d.category === ts.DiagnosticCategory.Error);
    if (errors.length) throw new Error(errors.map(d => ts.flattenDiagnosticMessageText(d.messageText, '\n')).join('\n'));
    evidence.push({ path: path.relative(root, file), sha256: crypto.createHash('sha256').update(source).digest('hex') });
    const module = { exports: {} };
    cache.set(file, module);
    const wrapper = new vm.Script(`(function(exports, require, module) {\n${compiled.outputText}\n})`, { filename: file });
    wrapper.runInContext(context, { timeout: 10000 })(module.exports, name => load(name, path.dirname(file)), module);
    // Wrap calls only to record execution; all method bodies remain production code.
    for (const [name, exported] of Object.entries(module.exports)) {
      if (typeof exported !== 'function' || !exported.prototype) continue;
      for (const method of Object.getOwnPropertyNames(exported.prototype)) {
        if (method === 'constructor') continue;
        const descriptor = Object.getOwnPropertyDescriptor(exported.prototype, method);
        if (typeof descriptor.value !== 'function') continue;
        const original = descriptor.value;
        Object.defineProperty(exported.prototype, method, { ...descriptor, value: function(...args) {
          const entry = { module: path.relative(root, file), class: name, method, args: snapshot(args) };
          calls.push(entry);
          try {
            const result = original.apply(this, args);
            entry.returned = result instanceof Promise ? '[promise]' : snapshot(result);
            return result;
          } catch (error) { entry.error = String(error); throw error; }
        } });
      }
      const exportDescriptor = Object.getOwnPropertyDescriptor(module.exports, name);
      if (exportDescriptor.writable || exportDescriptor.set) {
        module.exports[name] = new Proxy(exported, { construct(target, args, newTarget) {
          calls.push({ module: path.relative(root, file), class: name, method: 'constructor', args: snapshot(args) });
          return Reflect.construct(target, args, newTarget);
        } });
      }
    }
    return module.exports;
  }
  return request => load(request);
}

function compareExpected(expected, observed, location = '', failures = [], missing = []) {
  if (observed === undefined) { missing.push(location); return { failures, missing }; }
  if (Array.isArray(expected)) {
    if (!Array.isArray(observed) || expected.length !== observed.length) {
      failures.push({ path: location, expected, observed: snapshot(observed) });
    } else expected.forEach((item, index) => compareExpected(item, observed[index], `${location}[${index}]`, failures, missing));
  } else if (expected !== null && typeof expected === 'object') {
    if (observed === null || typeof observed !== 'object') failures.push({ path: location, expected, observed });
    else for (const [key, value] of Object.entries(expected)) compareExpected(value, observed[key], location ? `${location}.${key}` : key, failures, missing);
  } else if (expected !== observed) failures.push({ path: location, expected, observed: snapshot(observed) });
  return { failures, missing };
}

async function evaluateCase(taskId, caseSpec, project, adapter) {
  const productionSources = [], calls = [], checkpoints = [];
  const row = { caseId: caseSpec.caseId, traceDigest: caseSpec.traceDigest, status: 'not_scored', productionSources, calls, checkpoints };
  try {
    const load = productionLoader(project, productionSources, calls);
    const result = await adapter.runCase({ taskId, caseSpec, project, load,
      trace: (label, value) => checkpoints.push({ label, state: snapshot(value) }),
    });
    row.observed = snapshot(result.observed || {});
    row.invariantChecks = snapshot(result.invariantChecks || []);
    row.evidence = result.evidence || [];
    row.observationLevel = result.observationLevel || 'production_domain';
    row.unsupportedObservations = result.unsupportedObservations || [];
    const comparison = compareExpected(caseSpec.expected, result.observed || {});
    row.assertionFailures = comparison.failures;
    row.missingObservations = comparison.missing;
    const missingInvariants = (caseSpec.invariants || []).filter(description =>
      !row.invariantChecks.some(check => check.description === description && typeof check.passed === 'boolean'));
    row.missingInvariants = missingInvariants;
    if (calls.some(call => call.unavailableNativeService)) row.reason = 'Native service was invoked without a platform runtime; domain result is not scored';
    else if (result.unsupported) row.reason = result.unsupported;
    else if (!productionSources.length || !calls.length || checkpoints.length < 2) row.reason = 'Incomplete runtime evidence: require production execution and before/after checkpoints';
    else if (comparison.missing.length || missingInvariants.length) row.reason = 'Adapter did not observe every canonical expectation and invariant';
    else row.status = comparison.failures.length || row.invariantChecks.some(check => !check.passed) ? 'fail' : 'pass';
  } catch (error) {
    row.reason = String(error.stack || error);
  }
  return row;
}

async function main() {
  const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, i, all) => {
    if (i % 2 === 0) pairs.push([value.replace(/^--/, ''), all[i + 1]]);
    return pairs;
  }, []));
  if (!args.task || !args.source || !args.output || !args.role) throw new Error('--task --source --role --output are required');
  const contract = JSON.parse(fs.readFileSync(path.join(ROOT, 'benchmark_tasks', args.task, 'transitions.json'), 'utf8'));
  const number = Number(args.task.slice(0, 2));
  const group = number <= 11 ? 'tasks08_11' : number <= 15 ? 'tasks12_15' : 'tasks16_18';
  let adapter;
  try { adapter = require(path.join(ROOT, 'state_tests/runtime/arkts', `${group}.cjs`)); }
  catch (error) { adapter = { runCase: async () => ({ unsupported: String(error) }) }; }
  const rows = [];
  for (const caseSpec of contract.cases) rows.push(await evaluateCase(args.task, caseSpec, args.source, adapter));
  const counts = { passed: 0, failed: 0, notScored: 0, total: rows.length };
  for (const row of rows) counts[row.status === 'pass' ? 'passed' : row.status === 'fail' ? 'failed' : 'notScored']++;
  const report = {
    schemaVersion: 2, taskId: args.task, platform: 'arkts', role: args.role,
    observationMode: 'runtime_state_transition', runtime: 'node_transpiled_arkts_domain',
    observationScope: 'production domain methods; native ArkUI rendering and OS services are not executed',
    generatedAt: new Date().toISOString(), target: path.resolve(args.source),
    compile: { passed: null, scope: 'not_built_by_domain_runner' },
    semantic: { ...counts, cases: rows },
    diagnostics: { adapter: counts.notScored ? 'incomplete' : 'ready', nativeRuntimeExecuted: false },
  };
  fs.mkdirSync(path.dirname(path.resolve(args.output)), { recursive: true });
  fs.writeFileSync(args.output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ taskId: args.task, role: args.role, ...counts }));
}

module.exports = { productionLoader, compareExpected, evaluateCase, snapshot };
if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
