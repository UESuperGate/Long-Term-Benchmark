'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { fixture } = require('./Task15AccountClient.fixture.cjs');
for (const role of ['base', 'final']) {
  function setup(t) { const f = fixture(role); t.after(() => f.dispose()); return f; }
  test(role + ': fresh signed-out capability, real login HTTP pending, secure persistence and reopen', async t => {
    const f = setup(t); await f.client.restore();
    assert.equal(await f.client.canDeactivateAccount(), false); assert.equal(f.client.userId(), '');
    const login = f.client.login('https://matrix.example.org/', 'alice', 'not-secret');
    assert.equal(f.client.isBusy(), true); assert.equal(f.assets.size, 0);
    assert.equal(f.requests.length, 1); assert.equal(f.requests[0].body.password, 'not-secret');
    assert.equal(f.requests[0].options.header.Authorization, undefined);
    f.requests[0].respond(200, { user_id: f.session.userId, device_id: f.session.deviceId, access_token: f.session.accessToken });
    await login;
    assert.equal(f.client.isBusy(), false); assert.equal(await f.client.canDeactivateAccount(), true);
    assert.equal(f.assets.size, 1); assert.equal((await f.store.read()).accessToken, f.session.accessToken);
    const metadata = path.join(f.filesDir, 'account-sessions', encodeURIComponent(f.session.userId), f.session.deviceId, 'session.json');
    assert.equal(fs.readFileSync(metadata, 'utf8').includes('test-token'), false);
    const reopened = f.newClient(); await reopened.restore();
    assert.equal(reopened.userId(), f.session.userId); assert.equal(await reopened.canDeactivateAccount(), true);
    assert.equal(f.requests.length, 1);
  });
  test(role + ': repeated save tolerates only existing session directories and truncates metadata', async t => {
    const f = setup(t); await f.signedIn();
    const account = path.join(f.filesDir, 'account-sessions', encodeURIComponent(f.session.userId), f.session.deviceId);
    const metadata = path.join(account, 'session.json');
    fs.writeFileSync(metadata, JSON.stringify({ ...f.session, phase: 'active', padding: 'must-be-truncated' }));
    await f.store.save({ ...f.session, phase: 'cleanup_pending' });
    const saved = fs.readFileSync(metadata, 'utf8');
    assert.equal(saved.includes('must-be-truncated'), false);
    assert.equal(JSON.parse(saved).phase, 'cleanup_pending');
    assert.equal((await f.store.read()).phase, 'cleanup_pending');
    assert.equal(f.events.filter(event => event.startsWith('fs.mkdir:')).length, 4);
  });
  test(role + ': session directory creation propagates non-EEXIST errors', async t => {
    const f = setup(t);
    const denied = Object.assign(new Error('mkdir denied'), { code: 13900012 });
    f.errors.mkdir = denied;
    await assert.rejects(f.store.save(f.session), error => error === denied);
    assert.equal(f.assets.size, 0);
  });
  test(role + ': EEXIST is rejected when the session path is not a directory', async t => {
    const f = setup(t);
    const account = path.join(f.filesDir, 'account-sessions', encodeURIComponent(f.session.userId), f.session.deviceId);
    fs.mkdirSync(path.dirname(account), { recursive: true });
    fs.writeFileSync(account, 'path collision');
    await assert.rejects(f.store.save(f.session), error => error.code === 13900015 && error.message === 'File exists');
    assert.equal(f.assets.size, 0);
  });
  test(role + ': unsupported auth capability is restored, not supplied by testcase or password', async t => {
    const f = setup(t); await f.signedIn('oidc');
    assert.equal(f.client.userId(), f.session.userId); assert.equal(await f.client.canDeactivateAccount(), false);
    await assert.rejects(f.client.deactivateAccount('anything', true), /does not support/);
    assert.equal(f.requests.length, 0); assert.equal(f.assets.size, 1);
  });
  test(role + ': unauthed deactivation success clears actual store and account directory', async t => {
    const f = setup(t); await f.login();
    const account = path.join(f.filesDir, 'account-sessions', encodeURIComponent(f.session.userId), f.session.deviceId);
    const other = path.join(f.filesDir, 'account-sessions', 'other'); fs.mkdirSync(other);
    fs.writeFileSync(path.join(account, 'crypto-fixture.db'), 'opaque external data');
    const pending = f.client.deactivateAccount('any-password', true);
    assert.equal(f.client.isBusy(), true); assert.equal(f.assets.size, 1);
    const request = f.requests[1]; assert.deepEqual(request.body, { erase: true });
    assert.equal(request.options.header.Authorization, 'Bearer test-token');
    await assert.rejects(f.client.deactivateAccount('duplicate', false), /already pending/);
    assert.equal(f.requests.length, 2);
    request.respond(200, { id_server_unbind_result: 'no-support' }); await pending;
    assert.equal(f.assets.size, 0); assert.equal(fs.existsSync(account), false); assert.equal(fs.existsSync(other), true);
    assert.equal(request.destroyed, true); assert.equal(f.client.userId(), '');
    const reopened = f.newClient(); await reopened.restore(); assert.equal(await reopened.canDeactivateAccount(), false);
  });
  test(role + ': UIA challenge carries session, wrong password preserves session, subsequent retry succeeds', async t => {
    const f = setup(t); await f.signedIn();
    const pending = f.client.deactivateAccount('wrong', false);
    f.requests[0].respond(401, { session: 'challenge', flows: [{ stages: ['m.login.password'] }] });
    await f.waitRequests(2);
    assert.deepEqual(f.requests[1].body, { erase: false, auth: { type: 'm.login.password',
      identifier: { type: 'm.id.user', user: f.session.userId }, password: 'wrong', session: 'challenge' } });
    assert.equal(f.client.isBusy(), true); assert.equal(f.assets.size, 1);
    f.requests[1].respond(403, { errcode: 'M_FORBIDDEN', error: 'Wrong password' });
    await assert.rejects(pending, e => e.status === 403 && e.code === 'M_FORBIDDEN');
    assert.equal(f.client.isBusy(), false); assert.equal(f.client.userId(), f.session.userId);
    assert.equal(await f.client.canDeactivateAccount(), true); assert.equal(f.assets.size, 1);
    const retry = f.client.deactivateAccount('correct', false);
    f.requests[2].respond(401, { session: 'next-challenge' }); await f.waitRequests(4);
    assert.equal(f.requests[3].body.auth.password, 'correct');
    f.requests[3].respond(200, {}); await retry; assert.equal(f.assets.size, 0);
  });
  test(role + ': arbitrary server and transport failure are not password-dependent', async t => {
    const f = setup(t); await f.signedIn();
    const pending = f.client.deactivateAccount('secret', true);
    f.requests[0].reject(new Error('network offline')); await f.waitRequests(2);
    assert.equal(f.requests[1].body.auth.password, 'secret'); assert.equal(f.requests[1].body.auth.session, undefined);
    f.requests[1].respond(503, 'upstream unavailable');
    await assert.rejects(pending, e => e.status === 503 && e.code === 'M_UNKNOWN');
    assert.equal(f.assets.size, 1); assert.equal(f.client.userId(), f.session.userId);
    assert.equal(f.events.some(e => e.startsWith('fs.rmdir')), false);
  });
  test(role + ': local cleanup failure does not restore a remotely deactivated account', async t => {
    const f = setup(t); await f.signedIn(); f.errors.rmdir = new Error('disk denied');
    const pending = f.client.deactivateAccount('secret', true); f.requests[0].respond(200, {});
    await assert.rejects(pending, /disk denied/);
    assert.equal(f.client.needsCleanup(), true); assert.equal(await f.client.canDeactivateAccount(), false);
    assert.equal((await f.store.read()).phase, 'cleanup_pending');
    const reopened = f.newClient(); await assert.rejects(reopened.restore(), /disk denied/);
    assert.equal(reopened.userId(), ''); assert.equal(await reopened.canDeactivateAccount(), false);
    f.errors.rmdir = null; await reopened.retryCleanup();
    assert.equal(f.assets.size, 0); assert.equal(reopened.needsCleanup(), false); assert.equal(f.requests.length, 1);
  });
  test(role + ': sign out pending/failure preserves session and success removes it', async t => {
    const f = setup(t); await f.signedIn();
    const failed = f.client.logout(); assert.equal(f.client.isBusy(), true);
    f.requests[0].respond(500, { errcode: 'M_UNKNOWN' }); await assert.rejects(failed);
    assert.equal(f.client.userId(), f.session.userId);
    const success = f.client.logout(); assert.equal(f.requests[1].url.endsWith('/logout'), true);
    f.requests[1].respond(200, {}); await success; assert.equal(f.assets.size, 0);
  });
  test(role + ': file tombstone prevents restore when Asset update and local deletion both fail', async t => {
    const f = setup(t); await f.signedIn();
    f.errors.assetWrite = new Error('asset unavailable'); f.errors.rmdir = new Error('disk denied');
    const pending = f.client.deactivateAccount('secret', true); f.requests[0].respond(200, {});
    await assert.rejects(pending);
    assert.equal((await f.store.read()).phase, 'cleanup_pending');
    const reopened = f.newClient(); await assert.rejects(reopened.restore());
    assert.equal(await reopened.canDeactivateAccount(), false); assert.equal(reopened.userId(), '');
    f.errors.assetWrite = null; f.errors.rmdir = null; await reopened.retryCleanup();
    assert.equal(f.assets.size, 0); assert.equal(f.requests.length, 1);
  });
  test(role + ': Asset denial, malformed sessions/login, and insecure origins fail closed', async t => {
    const f = setup(t); f.errors.assetRead = Object.assign(new Error('denied'), { code: 24000001 });
    await assert.rejects(f.client.restore(), /denied/); assert.equal(await f.client.canDeactivateAccount(), false);
    f.errors.assetRead = null; await f.client.restore();
    for (const url of ['http://example.org', 'https://user@example.org', 'https://example.org/path']) {
      await assert.rejects(f.client.login(url, 'alice', 'p'), /HTTPS/);
    }
    assert.equal(f.requests.length, 0);
    const bad = f.client.login(f.session.homeserver, 'alice', 'p'); f.requests[0].respond(200, {});
    await assert.rejects(bad); assert.equal(f.assets.size, 0); assert.equal(f.client.userId(), '');
    await assert.rejects(f.store.save({ ...f.session, accessToken: '' }), /invalid/);
    for (const deviceId of ['.', '..']) await assert.rejects(f.store.save({ ...f.session, deviceId }), /invalid/);
  });
}
test('final actual presenter: confirm is zero I/O, pending is held at HTTP, failure then retry', async t => {
  const f = fixture(); t.after(() => f.dispose()); await f.signedIn();
  const { AccountDeactivationPresenter } = f.load(path.join(f.project, 'entry/src/main/ets/features/AccountDeactivationFeature.ets'));
  const p = new AccountDeactivationPresenter(f.client, f.client); await p.loadCapability();
  p.setPassword('secret'); p.setEraseData(true); await p.deactivateAccount(false);
  assert.equal(p.action, 'confirming'); assert.equal(f.requests.length, 0);
  const pending = p.deactivateAccount(false); assert.equal(p.action, 'loading');
  await Promise.resolve(); assert.equal(p.action, 'loading');
  f.requests[0].respond(500, {}); await f.waitRequests(2);
  assert.equal(p.action, 'loading'); assert.equal(f.requests[1].body.auth.password, 'secret');
  f.requests[1].respond(500, {}); await pending;
  assert.equal(p.action, 'failure'); assert.equal(p.password, 'secret'); assert.equal(p.eraseData, true);
  const retry = p.deactivateAccount(true); assert.equal(p.action, 'loading');
  f.requests[2].respond(200, {}); await retry;
  assert.equal(p.action, 'success'); assert.equal(f.assets.size, 0);
});
test('base settings presenter uses real AccountClient logout without final deactivation presenter API', async t => {
  const f = fixture('base'); t.after(() => f.dispose()); await f.signedIn();
  const { PreferencesBasePresenter } = f.load(path.join(f.project, 'entry/src/main/ets/features/PreferencesBase.ets'));
  const p = new PreferencesBasePresenter(f.client); p.openNotificationSettings();
  assert.equal(p.notificationSettingsOpen, true); assert.equal(p.deactivateAccount, undefined);
  const pending = p.signOut(); assert.equal(p.signedOut, false);
  f.requests[0].respond(200, {}); await pending; assert.equal(p.signedOut, true); assert.equal(f.assets.size, 0);
});
