import { installTask14Observer } from './Task14PageObserver';
import { installTask14RealFlowV2Observer } from './Task14RealFlowV2Observer';
import { acquireTask14RealFlowFrame } from './Task14RealFlowV2Frame';

const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const requireObserved = (condition, reason) => { if (!condition) throw new Error(reason); };
const action = control => control?.actionAncestor || control;

const SELECTORS = {
  root: {
    title: [{ text: 'Start a chat', type: 'Text' }], search: [{ id: 'people_search_input' }],
    join: [{ id: 'join_room_by_address' }], create: [{ id: 'create_room_action' }],
    dm: [{ id: 'person_@alice:demo.local' }]
  },
  address: {
    title: [{ text: 'Join a room by address', type: 'Text' }], input: [{ id: 'room_address_input' }, { id: 'join_address_input' }],
    cancel: [{ id: 'join_room_cancel' }, { id: 'join_address_cancel' }],
    continue: [{ id: 'join_room_continue' }, { id: 'join_address_continue' }]
  },
  create: {
    title: [{ id: 'create_room_title' }], name: [{ id: 'create_room_name' }],
    submit: [{ id: 'create_room_submit' }], cancel: [{ id: 'create_room_cancel' }]
  },
  room: {
    back: [{ id: 'room_back' }], roomId: [{ id: 'room_id' }], members: [{ id: 'room_members' }],
    timeline: [{ id: 'room_timeline' }], input: [{ id: 'room_message_input' }], send: [{ id: 'room_send' }]
  }
};
const forbidden = {
  root: ['room_address_input', 'create_room_name', 'room_id'],
  address: ['people_search_input', 'create_room_name', 'room_id'],
  create: ['people_search_input', 'room_address_input', 'room_id'],
  room: ['people_search_input', 'room_address_input', 'create_room_name']
};
const surface = async (session, label, name, routeName, anchor, record) =>
  acquireTask14RealFlowFrame(session, label, SELECTORS[name], { routeName, anchor,
    required: Object.keys(SELECTORS[name]), forbiddenIds: forbidden[name] }, record);
const callOf = (calls, owner, method, phase, after) => calls.find(call =>
  call.sequence > after && call.owner === owner && call.method === method && call.phase === phase);
const callStarted = (calls, owner, method, after) => callOf(calls, owner, method, 'call', after);

export async function runTask14RealFlowV2(spec, config, session, importModule, emit, trace = () => {}) {
  requireObserved(spec.caseId === 'jr_state_001_entry_opens_address_flow' && spec.key === 'entry_opens_address_flow',
    'real_flow_v2 executes only canonical case001');
  const result = { taskId: spec.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest,
    observed: {}, invariantChecks: [], unsupportedInvariants: [], evidence: [], notes: [],
    observationLevel: 'native_original_ui_complete_production_action_chain',
    limitations: ['Session-local production backend; no Matrix network, federation, encryption, or process-death persistence claim.'] };
  const record = event => { result.evidence.push({ label: event.method, data: copy(event) }); emit(event); };
  let observer;
  const checkpoint = (label, frame) => {
    const value = { label, routeName: frame.routeName, routeParams: copy(frame.routeParams), windowId: frame.windowId,
      controls: copy(frame.controls) };
    result.evidence.push({ label, data: value });
    trace(label, value);
    return value;
  };
  try {
    const root = await surface(session, 'setup:root', 'root', config.entryRoute, 'search', record);
    checkpoint('setup:root', root);
    requireObserved(root.controls.search.text === '' && root.controls.search.focused === false,
      'Canonical empty inactive search given is not established');
    for (const key of ['join', 'create', 'dm']) requireObserved(action(root.controls[key]).visible === true &&
      action(root.controls[key]).enabled === true && action(root.controls[key]).clickable === true,
      'Original root action is not visible/enabled/clickable: ' + key);

    const join = await importModule(config.joinModuleUrl);
    const chat = await importModule(config.chatFeatureModuleUrl);
    const routes = await importModule(config.chatRoutesModuleUrl);
    const runtime = await importModule(config.chatRuntimeModuleUrl);
    const joinObserver = installTask14Observer(join, record);
    observer = installTask14RealFlowV2Observer({ chat, routes, runtime, joinObserver }, record);
    record({ method: 'Task14.realFlowModulesBound', moduleUrls: config.realFlowModuleUrls,
      exportedSingletons: ['roomGateway', 'chatNavigator', 'startDMService', 'startChatPresenter'] });

    trace('before:event', checkpoint('before:event', root));
    await session.action('click', action(root.controls.join));
    await session.delay(50);
    const address = await surface(session, 'after:event', 'address', config.addressRoute || config.entryRoute, 'input', record);
    const joinState = joinObserver.read();
    requireObserved(joinState.available && joinState.instanceCount === 1,
      'Actual page-owned JoinRoomByAddressPresenter receiver was not captured');
    requireObserved(address.controls.input.text === joinState.address,
      'Rendered address differs from actual page-owned presenter');
    result.observed = { addressFlowVisible: address.controls.input.visible === true,
      address: address.controls.input.text,
      addressState: joinState.visibleAddressState ?? joinState.addressState };
    trace('after:event', checkpoint('after:event', address));

    await session.action('click', action(address.controls.cancel));
    await session.delay(50);
    const returned = await surface(session, 'returned:root', 'root', config.entryRoute, 'search', record);
    checkpoint('returned:root', returned);

    const createStart = observer.checkpoint();
    await session.action('click', action(returned.controls.create));
    await observer.waitFor('HarmonyRoutePort', 'push', createStart);
    await observer.waitFor('StartChatPresenter', 'createRoom', createStart);
    await session.delay(50);
    const create = await surface(session, 'create:configuration', 'create', 'pages/CreateRoom', 'name', record);
    checkpoint('create:configuration', create);
    await session.action('input', create.controls.name, 'Task14 Native Room');
    await session.dismissKeyboard();
    const named = await surface(session, 'create:named', 'create', 'pages/CreateRoom', 'name', record);
    requireObserved(named.controls.name.text === 'Task14 Native Room', 'Create-room name did not reach original UI');
    const submitStart = observer.checkpoint();
    await session.action('click', action(named.controls.submit));
    const createRoomResult = await observer.waitFor('DemoRoomGateway', 'createRoom', submitStart);
    await observer.waitFor('HarmonyRoutePort', 'replace', submitStart);
    await observer.waitFor('RoomPresenter', 'load', submitStart);
    await session.delay(50);
    const createdRoom = await surface(session, 'create:room', 'room', 'pages/Room', 'roomId', record);
    checkpoint('create:room', createdRoom);
    const createdCalls = observer.calls();
    const createdId = createRoomResult.value;
    const createOpen = callStarted(createdCalls, 'RouterChatNavigator', 'openRoom', submitStart);
    const createReplace = callStarted(createdCalls, 'HarmonyRoutePort', 'replace', submitStart);
    const createLoad = callStarted(createdCalls, 'RoomPresenter', 'load', submitStart);
    const createGet = callOf(createdCalls, 'DemoRoomGateway', 'getRoom', 'fulfilled', submitStart);
    requireObserved(typeof createdId === 'string' && createdId.length > 0 &&
      createOpen?.args?.[0] === createdId && createReplace?.args?.[1]?.roomId === createdId &&
      createLoad?.args?.[0] === createdId && createGet?.value?.roomId === createdId &&
      createGet?.value?.direct === false && createdRoom.controls.roomId.text === createdId &&
      createdRoom.routeParams?.roomId === createdId,
      'Create chain room identity/route/render/store evidence disagrees');

    const backStart = observer.checkpoint();
    await session.action('click', action(createdRoom.controls.back));
    await observer.waitFor('HarmonyRoutePort', 'returnToStart', backStart);
    await session.delay(50);
    const rootAgain = await surface(session, 'dm:root', 'root', config.entryRoute, 'search', record);
    checkpoint('dm:root', rootAgain);
    const dmUserId = '@alice:demo.local';
    const dmStart = observer.checkpoint();
    await session.action('click', action(rootAgain.controls.dm));
    const dmResult = await observer.waitFor('StartDMService', 'execute', dmStart);
    await observer.waitFor('HarmonyRoutePort', 'replace', dmStart);
    await observer.waitFor('RoomPresenter', 'load', dmStart);
    await session.delay(50);
    const dmRoom = await surface(session, 'dm:room', 'room', 'pages/Room', 'roomId', record);
    checkpoint('dm:room', dmRoom);
    const dmCalls = observer.calls();
    const dmId = dmResult.value;
    const select = callStarted(dmCalls, 'StartChatPresenter', 'selectPerson', dmStart);
    const dmCreate = callOf(dmCalls, 'DemoRoomGateway', 'createDirectRoom', 'fulfilled', dmStart);
    const dmOpen = callStarted(dmCalls, 'RouterChatNavigator', 'openRoom', dmStart);
    const dmReplace = callStarted(dmCalls, 'HarmonyRoutePort', 'replace', dmStart);
    const dmLoad = callStarted(dmCalls, 'RoomPresenter', 'load', dmStart);
    const dmGet = callOf(dmCalls, 'DemoRoomGateway', 'getRoom', 'fulfilled', dmStart);
    requireObserved(select?.args?.[0] === dmUserId && typeof dmId === 'string' && dmId.length > 0 &&
      dmCreate?.value === dmId && dmOpen?.args?.[0] === dmId && dmReplace?.args?.[1]?.roomId === dmId &&
      dmLoad?.args?.[0] === dmId && dmGet?.value?.roomId === dmId && dmGet?.value?.direct === true &&
      dmGet?.value?.memberIds?.includes(dmUserId) && dmGet?.value?.memberIds?.includes('@me:demo.local') &&
      dmRoom.controls.roomId.text === dmId && dmRoom.routeParams?.roomId === dmId,
      'DM chain user/room/route/render/store evidence disagrees');
    result.invariantChecks.push({ description: 'existing create-room and direct-message actions remain available',
      passed: true, observed: { returnedRootActions: ['create_room_action', 'person_@alice:demo.local'],
        create: { roomId: createdId, route: createdRoom.routeName, direct: createGet.value.direct },
        directMessage: { userId: dmUserId, roomId: dmId, route: dmRoom.routeName,
          direct: dmGet.value.direct, members: dmGet.value.memberIds } } });
    result.notes.push({ kind: 'production_backend_scope',
      reason: 'Real app route/presenter/service/store/render chain over the production session-local backend; not a Matrix network claim.' });
    result.productionCalls = observer.calls();
    return result;
  } finally { if (observer) observer.dispose(); }
}
