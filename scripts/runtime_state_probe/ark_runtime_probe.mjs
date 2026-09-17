import { appendFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
// Ark's handshake rejects Node's built-in client's upgrade header formatting.
const WebSocket = require(process.env.PROBE_WS_MODULE || 'C:/Program Files/Huawei/DevEco Studio/tools/hvigor/hvigor/node_modules/ws');

// Desktop protocol client; does not write business state or evaluate app methods.
const [url, mode, output, seconds = '30'] = process.argv.slice(2);
if (!url || !mode || !output) throw new Error('url mode output [seconds] required');
function record(direction, data) {
  appendFileSync(output, JSON.stringify({ time: new Date().toISOString(), direction, data }) + '\n');
  console.log(direction, JSON.stringify(data).slice(0, 1200));
}
const socket = new WebSocket(url);
let opened = false;
let serial = 0;
const pendingProperties = new Map();
const seenObjects = new Set();
const send = data => { record('send', data); socket.send(JSON.stringify(data)); };
const command = (method, params = {}) => send({ id: ++serial, method, params });
function properties(objectId, path, depth = 0) {
  if (!objectId || seenObjects.has(objectId)) return;
  seenObjects.add(objectId);
  pendingProperties.set(serial + 1, { path, depth });
  command('Runtime.getProperties', { objectId, ownProperties: true });
}
const timer = setTimeout(() => {
  record('timeout', { opened });
  if (socket.readyState === WebSocket.OPEN) {
    if (mode === 'state') send({ type: 'ArkUIStateProfilerClose' });
    if (mode === 'debug' || mode === 'inspect') command('Debugger.resume');
    socket.close();
  }
  setTimeout(() => process.exit(opened ? 0 : 2), 1000);
}, Number(seconds) * 1000);
socket.addEventListener('open', () => {
  opened = true;
  record('open', { url, mode });
  if (mode === 'state') {
    send({ type: 'connected' });
    send({ type: 'ArkUIStateProfilerOpen' });
  } else if (mode === 'debug' || mode === 'inspect') {
    command('Runtime.enable');
    command('Debugger.enable');
    command('Runtime.runIfWaitingForDebugger');
    if (mode === 'inspect') command('Debugger.pause');
  }
});
socket.addEventListener('message', async ev => {
  let data = typeof ev.data === 'string' ? ev.data : await ev.data.text();
  try { data = JSON.parse(data); } catch { /* Preserve non-JSON control messages. */ }
  record('recv', data);
  if (mode === 'inspect' && data?.method === 'Debugger.paused') {
    seenObjects.clear();
    const frame = data.params.callFrames?.[0];
    for (const scope of frame?.scopeChain || []) {
      if (scope.type === 'local' || scope.type === 'closure') properties(scope.object.objectId, scope.type);
    }
    properties(frame?.this?.objectId, 'this');
    if (!pendingProperties.size) command('Debugger.resume');
  }
  if (mode === 'inspect' && pendingProperties.has(data?.id)) {
    const context = pendingProperties.get(data.id);
    pendingProperties.delete(data.id);
    record('properties', { ...context, result: data.result });
    for (const p of data.result?.result || []) {
      if (context.depth < 8 && /^(this|__?clientSnapshot|clientSnapshot|currentUser|status|text|emoji|wrappedValue_|value_|__?pickerState|pickerState|\[\[Target\]\])$/.test(p.name)) {
        properties(p.value?.objectId, context.path + '.' + p.name, context.depth + 1);
      }
    }
    if (!pendingProperties.size) command('Debugger.resume');
  }
  if (mode === 'debug' && data?.method === 'Debugger.paused') {
    for (const scope of data.params.callFrames?.[0]?.scopeChain || []) {
      if (scope.type === 'local') command('Runtime.getProperties', { objectId: scope.object.objectId, ownProperties: true });
    }
    command('Debugger.resume');
  }
});
socket.addEventListener('error', ev => { record('error', { url, message: ev.message }); clearTimeout(timer); process.exitCode = 2; });
socket.addEventListener('close', ev => { record('close', { code: ev.code, reason: ev.reason }); clearTimeout(timer); });
