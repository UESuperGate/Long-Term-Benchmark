'use strict';
// Fixture units validate protocol wiring only. Host Node cannot execute OpenHarmony system UI.
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');

const source = fs.readFileSync(path.join(__dirname, 'Task14NativeE2E.js'), 'utf8');
const modulePromise = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const nonce = 'a1'.repeat(16);
const caSha256 = 'bc'.repeat(32);

test('ability arguments are strictly parsed and homeserver input omits the scheme', async () => {
  const api = await modulePromise;
  assert.equal(api.task14NativeE2EConfig({}), undefined);
  assert.deepEqual(api.task14NativeE2EConfig({ task14E2E: '1', task14Nonce: nonce,
    task14Homeserver: 'https://127.0.0.1:8448', task14CaSha256: caSha256 }), {
    enabled: true, nonce, homeserver: '127.0.0.1:8448',
    controlHomeserver: 'https://127.0.0.1:8448', caSha256
  });
  assert.deepEqual(api.task14NativeE2EConfig({ '-s task14E2E': '1', '-s task14Nonce': nonce,
    '-s task14Homeserver': '127.0.0.1:18448', '-s task14CaSha256': caSha256 }), {
    enabled: true, nonce, homeserver: '127.0.0.1:18448',
    controlHomeserver: 'https://127.0.0.1:18448', caSha256
  });
  for (const bad of [
    { task14E2E: '1', task14Nonce: 'a'.repeat(31), task14Homeserver: '127.0.0.1:8448', task14CaSha256: caSha256 },
    { task14E2E: '1', task14Nonce: nonce, task14Homeserver: 'http://127.0.0.1:8448', task14CaSha256: caSha256 },
    { task14E2E: '1', task14Nonce: nonce, task14Homeserver: 'localhost:8448', task14CaSha256: caSha256 },
    { task14E2E: '1', task14Nonce: nonce, task14Homeserver: '127.0.0.1:65536', task14CaSha256: caSha256 },
    { task14E2E: '1', task14Nonce: nonce, task14Homeserver: '127.0.0.1:8448/path', task14CaSha256: caSha256 },
    { task14E2E: '1', task14Nonce: nonce, task14Homeserver: '127.0.0.1:8448', task14CaSha256: caSha256.toUpperCase() }
  ]) assert.throws(() => api.task14NativeE2EConfig(bad), /Invalid Task14/);
});

function fixture() {
  const events = [];
  const inputs = {};
  const bytes = new Uint8Array([1, 2, 3, 4]);
  const certificateName = 'LTB Task14 ' + nonce;
  let screen = 'candidate';
  let loggedIn = false;
  let startChat = false;
  let certificatePresent = false;
  let certificateEnabled = false;
  let destroyedRequests = 0;
  const held = [{ caseId: 'case-held', alias: '#room:unit.test', requestSequence: 17 }];
  const setScreen = value => { screen = value; events.push(['screen', value]); };
  const node = ({ id = '', text = '', type = 'Any', click, input }) => ({
    __type: type,
    getId: async () => id,
    getText: async () => text,
    isEnabled: async () => true,
    click: async () => { events.push(['click', id || text]); if (click) click(); },
    inputText: async value => { events.push(['input', id]); inputs[id] = value; if (input) input(value); }
  });
  const candidateNodes = () => {
    if (startChat) return [node({ id: 'people_search_input' })];
    if (loggedIn) return [
      node({ id: 'session_user', text: '@task14_' + nonce.slice(0, 12) + ':task14.test' }),
      node({ id: 'start_chat_action', click: () => { startChat = true; } })
    ];
    return ['login_homeserver', 'login_username', 'login_password'].map(id => node({ id })).concat([
      node({ id: 'login_submit', click: () => { loggedIn = true; } })
    ]);
  };
  const systemNodes = () => {
    if (screen === 'cert-install') return [node({ type: 'Button', text: 'Install', click: () => setScreen('install-confirm') })];
    if (screen === 'install-confirm') return [
      node({ type: 'Text', text: 'Install certificate' }),
      node({ type: 'Button', id: 'advanced_dialog_button_1', click: () => { certificatePresent = true; setScreen('installed'); } })
    ];
    if (screen === 'cert-root') return [node({ type: 'Text', text: 'CA certificates', click: () => setScreen('cert-ca') })];
    if (screen === 'cert-ca') return [node({ type: 'Text', text: 'User', click: () => setScreen('cert-list') })];
    if (screen === 'cert-list') return [
      node({ type: 'Text', text: certificateName, click: () => setScreen('cert-detail') }),
      node({ type: 'Text', text: certificateName })
    ];
    if (screen === 'cert-detail') return [
      node({ type: 'Toggle', click: () => {} }),
      node({ type: 'Button', text: certificateEnabled ? 'Delete certificate' : 'Continue', click: () => {
        if (certificateEnabled) setScreen('delete-confirm');
        else { certificateEnabled = true; setScreen('enabled'); }
      } })
    ];
    if (screen === 'delete-confirm') return [
      node({ type: 'Text', text: 'Delete certificate' }),
      node({ type: 'Button', id: 'advanced_dialog_button_1', click: () => {
        certificatePresent = false; certificateEnabled = false; setScreen('deleted');
      } })
    ];
    return [];
  };
  const driver = {
    delayMs: async () => {},
    findComponents: async selector => {
      const nodes = screen === 'candidate' ? candidateNodes() : systemNodes();
      if (selector.id !== undefined) {
        const matches = [];
        for (const item of nodes) if (await item.getId() === selector.id) matches.push(item);
        return matches;
      }
      if (selector.type === 'Any') return nodes;
      return nodes.filter(item => item.__type === selector.type);
    }
  };
  return { events, inputs, bytes, driver,
    ON: { id: id => ({ id }), type: type => ({ type }) },
    context: { cacheDir: '/fixture-cache' },
    resourceContext: { resourceManager: { getRawFileContent: async name => {
      assert.equal(name, 'task14-ca.der'); return bytes;
    } } },
    platform: {
      fs: { OpenMode: { CREATE: 1, WRITE_ONLY: 2, TRUNC: 4 }, openSync: () => ({ fd: 7 }),
        writeSync: (_fd, buffer) => buffer.byteLength, closeSync: () => {}, unlinkSync: file => events.push(['unlink', file]) },
      fileUri: { getUriFromPath: file => 'file://' + file },
      wantConstant: { Action: { ACTION_VIEW_DATA: 'view' }, Flags: { FLAG_AUTH_READ_URI_PERMISSION: 1 } },
      abilityDelegator: {
        getCurrentTopAbility: async () => ({ context: { abilityInfo: { bundleName: 'candidate.test' },
          startAbility: async want => setScreen(want.action === 'view' ? 'cert-install' : 'cert-root') } }),
        startAbility: async () => setScreen('candidate')
      },
      certificateManager: {
        CertScope: { CURRENT_USER: 1 },
        getAllUserTrustedCertificates: async () => ({ certList: certificatePresent ? [{ uri: 'cert://task14',
          state: certificateEnabled, certAlias: certificateName, subjectName: 'CN=' + certificateName }] : [] }),
        getUserTrustedCertificate: async () => ({ certInfo: { cert: bytes } })
      },
      http: {
        RequestMethod: { GET: 'GET', POST: 'POST' }, HttpDataType: { STRING: 'STRING' },
        createHttp: () => ({
          request: async (url, options) => {
            events.push(['http', options.method, url]);
            assert.equal(options.header['X-Task14-Nonce'], nonce);
            if (url.includes('/__task14/status')) {
              return { responseCode: 200, result: JSON.stringify({ nonce, held }) };
            }
            assert.ok(url.endsWith('/__task14/release'));
            const body = JSON.parse(options.extraData);
            assert.deepEqual(body, { nonce, caseId: 'case-held', requestSequence: 17 });
            held.length = 0;
            return { responseCode: 200, result: JSON.stringify({ released: 'case-held',
              requestSequence: 17, outcome: 'success' }) };
          },
          destroy: () => { destroyedRequests++; }
        })
      }
    },
    state: () => ({ certificatePresent, certificateEnabled, screen, destroyedRequests })
  };
}

test('fixture unit follows system certificate UI and physical login/StartChat controls without serializing password', async () => {
  const api = await modulePromise;
  const f = fixture();
  const integration = api.createTask14NativeE2E({ enabled: true, nonce, homeserver: '127.0.0.1:8448',
    controlHomeserver: 'https://127.0.0.1:8448', caSha256 }, f.context, f.resourceContext,
  f.driver, f.ON, f.platform);
  const prepared = await integration.prepare('candidate.test');
  const derivedPassword = 'task14-login-' + nonce;
  assert.equal(f.inputs.login_homeserver, '127.0.0.1:8448');
  assert.equal(f.inputs.login_username, 'task14_' + nonce.slice(0, 12));
  assert.equal(f.inputs.login_password, derivedPassword);
  assert.deepEqual(prepared.checkpoints.map(item => item.label), [
    'candidate_login_form_ready', 'certificate_installed_and_enabled',
    'candidate_returned_after_certificate_ui', 'login_fields_entered', 'login_complete', 'start_chat_ready'
  ]);
  assert.equal(JSON.stringify(prepared).includes(derivedPassword), false);
  assert.equal(JSON.stringify(integration).includes(derivedPassword), false);
  const status = await integration.control('status');
  assert.equal(status.held[0].alias, '#room:unit.test');
  const released = await integration.control('release', { alias: '#room:unit.test' });
  assert.equal(released.outcome, 'success');
  assert.equal(f.state().destroyedRequests, 3);
  const cleaned = await integration.cleanup();
  assert.equal(cleaned.certificate.cleanupConfirmed, true);
  assert.equal(cleaned.certificate.absenceQuerySucceeded, true);
  assert.equal(f.state().certificatePresent, false);
  assert.equal(JSON.stringify(cleaned).includes(derivedPassword), false);
});
