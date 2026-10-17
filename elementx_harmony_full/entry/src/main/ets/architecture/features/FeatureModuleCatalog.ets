import {
  ClientModuleLayer,
  ClientModuleMetadata,
  RuntimeCapabilityStatus,
  createModuleMetadata
} from '../model/ArchitectureMetadata';

const S = 'entry/src/main/ets/services/';
const V = 'entry/src/main/ets/viewmodel/ElementClientViewModel.ets';
const P = 'entry/src/main/ets/pages/Index.ets';

function missing(name: string, variants: string[], dependencies: string[]): ClientModuleMetadata {
  return createModuleMetadata(
    `features.${name}`,
    ClientModuleLayer.Feature,
    `features/${name}`,
    variants,
    dependencies,
    RuntimeCapabilityStatus.Missing,
    [],
    [],
    'No production-equivalent ArkTS runtime for this Android feature domain is present.'
  );
}

function partial(
  name: string,
  variants: string[],
  dependencies: string[],
  capabilityIds: string[],
  evidence: string[],
  gap: string
): ClientModuleMetadata {
  return createModuleMetadata(
    `features.${name}`,
    ClientModuleLayer.Feature,
    `features/${name}`,
    variants,
    dependencies,
    RuntimeCapabilityStatus.Partial,
    capabilityIds,
    evidence,
    gap
  );
}

export const FEATURE_MODULES: ClientModuleMetadata[] = [
  missing('analytics', ['api', 'impl'], ['services.analytics', 'libraries.matrix']),
  missing('announcement', ['api', 'impl', 'test'], ['libraries.architecture', 'libraries.matrix', 'libraries.preferences']),
  missing('cachecleaner', ['api', 'impl'], ['libraries.architecture', 'libraries.core']),
  partial('call', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.audio', 'libraries.push'], ['call.timeline-card'], [P], 'An active-call timeline surface exists, but no real call stack, media session, or signalling runtime exists.'),
  partial('createroom', ['api', 'impl', 'test'], ['features.invitepeople', 'libraries.matrix', 'libraries.mediaupload'], ['room.create-direct'], [V, `${S}MatrixClientServerApi.ets`], 'Only direct-room creation is wired; general room creation and configuration are absent.'),
  missing('deactivation', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.ui-strings']),
  missing('enterprise', ['api', 'impl-foss', 'test'], ['libraries.matrix', 'libraries.compound']),
  missing('forward', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.roomselect']),
  missing('ftue', ['api', 'impl', 'test'], ['features.login', 'features.securebackup', 'features.verifysession']),
  partial('home', ['api', 'impl'], ['features.invite', 'features.leaveroom', 'libraries.matrix', 'services.appnavstate'], ['shell.signed-in', 'room.list'], [P, `${S}MatrixClientService.ets`], 'Home and room rows exist, but room-list subscriptions and the Android navigation graph are not equivalent.'),
  partial('invite', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.push'], ['room.membership'], [`${S}MatrixClientServerApi.ets`, P], 'Basic invite REST support exists without the complete invite lifecycle or push integration.'),
  partial('invitepeople', ['api', 'impl'], ['libraries.matrix', 'libraries.usersearch'], ['room.membership'], [`${S}MatrixClientServerApi.ets`, P], 'Direct user-id invitation exists; user search and the full selection flow are missing.'),
  partial('joinroom', ['api', 'impl'], ['features.roomdirectory', 'libraries.matrix'], ['room.join'], [V, `${S}MatrixClientServerApi.ets`], 'Join by room id or alias exists without the complete preview, knock, and restricted-room flow.'),
  missing('knockrequests', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.featureflag']),
  partial('leaveroom', ['api', 'impl'], ['libraries.matrix', 'libraries.push'], ['room.leave'], [V, `${S}MatrixClientServerApi.ets`], 'Basic leave is wired; space handling, cleanup, and push reconciliation are absent.'),
  missing('licenses', ['api', 'impl', 'test'], ['libraries.core', 'libraries.ui-strings']),
  partial('linknewdevice', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.oidc', 'libraries.qrcode', 'libraries.session-storage'], ['device-link.surface'], ['entry/src/main/ets/androidparity/FunctionLevelParity.ets', P], 'QR rotation and verification are parity fixtures only; no SDK-backed device-link protocol is present.'),
  partial('location', ['api', 'impl', 'test'], ['features.messages', 'libraries.matrix', 'services.toolbox'], ['location.timeline-surface'], ['entry/src/main/ets/androidparity/FunctionLevelParity.ets', P], 'Location rows and local transitions exist without platform location, live-share service, or Matrix state events.'),
  missing('lockscreen', ['api', 'impl', 'test'], ['libraries.cryptography', 'libraries.session-storage', 'services.appnavstate']),
  partial('login', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.oidc', 'libraries.wellknown', 'libraries.session-storage'], ['auth.password', 'auth.login-token', 'shell.signed-out'], [V, `${S}MatrixClientServerApi.ets`, P], 'Password and login-token REST paths exist; OIDC, QR login, secure storage, and Matrix SDK session semantics are incomplete.'),
  partial('logout', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.session-storage', 'libraries.workmanager'], ['auth.logout-local'], [V, `${S}PersistentSessionStore.ets`], 'Local session clearing exists without complete server logout and background-work cleanup.'),
  partial('messages', ['api', 'impl', 'test'], ['features.call', 'features.location', 'features.poll', 'libraries.matrix', 'libraries.matrixmedia', 'libraries.mediaupload', 'libraries.textcomposer'], ['timeline.render', 'message.send', 'media.send'], [P, V, `${S}MatrixClientServerApi.ets`], 'Basic timeline and sending exist; pagination, edits, reactions, threads, encrypted events, and full rich-event handling do not.'),
  missing('migration', ['api', 'impl'], ['libraries.matrix', 'libraries.session-storage', 'libraries.workmanager']),
  missing('networkmonitor', ['api', 'impl', 'test'], ['libraries.network', 'libraries.matrix']),
  missing('poll', ['api', 'impl', 'test'], ['features.messages', 'libraries.matrix']),
  partial('preferences', ['api', 'impl'], ['features.home', 'libraries.preferences', 'libraries.push', 'libraries.session-storage'], ['preferences.basic'], [P, V], 'A small set of read-receipt and media-preview preferences exists; the Android preferences tree is not covered.'),
  missing('rageshake', ['api', 'impl', 'test'], ['libraries.network', 'libraries.session-storage', 'services.toolbox']),
  partial('reportroom', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.matrixui'], ['room.report'], [V, `${S}MatrixClientServerApi.ets`], 'A basic room-report REST call exists without the complete confirmation and error flow.'),
  partial('rolesandpermissions', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.usersearch'], ['room.moderation'], [V, `${S}MatrixClientServerApi.ets`], 'Selected membership actions exist without power-level modelling and complete permission gates.'),
  partial('roomaliasresolver', ['api', 'impl'], ['libraries.matrix', 'libraries.matrixui'], ['room.preview', 'room.join'], [V, `${S}MatrixClientService.ets`], 'Alias preview and join are basic snapshot operations rather than SDK-backed resolution flows.'),
  partial('roomcall', ['api', 'impl'], ['features.call', 'libraries.matrix'], ['call.timeline-card'], [P], 'Call content can be rendered, but no real room-call runtime is connected.'),
  partial('roomdetails', ['api', 'impl'], ['features.leaveroom', 'features.roomdetailsedit', 'libraries.matrix'], ['room.details'], [P, V], 'Core room fields are displayed and selected actions are wired; the complete room-details graph is absent.'),
  partial('roomdetailsedit', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.mediaupload'], ['room.metadata'], [V, `${S}MatrixClientServerApi.ets`], 'Room name, topic, and own display-name updates exist; avatar and full editing semantics are absent.'),
  missing('roomdirectory', ['api', 'impl'], ['libraries.matrix', 'libraries.matrixui']),
  partial('roommembermoderation', ['api', 'impl'], ['libraries.matrix', 'services.analytics'], ['room.moderation'], [V, `${S}MatrixClientServerApi.ets`], 'Invite, kick, ban, and unban calls exist without complete member state and authorization handling.'),
  missing('securebackup', ['api', 'impl'], ['libraries.matrix', 'libraries.oidc']),
  missing('securityandprivacy', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.featureflag']),
  partial('share', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.mediaupload', 'services.appnavstate'], ['intent.share', 'media.send'], [`${S}LaunchIntentStore.ets`, `${S}SharedMediaFileReader.ets`, P], 'Share intents and local file reads exist; broad MIME handling, grants, and encrypted upload are incomplete.'),
  partial('signedout', ['api', 'impl'], ['libraries.matrix', 'libraries.session-storage'], ['shell.signed-out'], [P], 'Signed-out routes are rendered, but the complete Android onboarding and account selection flow is absent.'),
  missing('space', ['api', 'impl'], ['features.createroom', 'libraries.matrix', 'libraries.deeplink']),
  partial('startchat', ['api', 'impl', 'test'], ['features.createroom', 'libraries.matrix', 'libraries.usersearch'], ['room.create-direct'], [V, `${S}MatrixClientServerApi.ets`], 'Direct room creation by user id exists without user search and complete start-chat behaviour.'),
  partial('userprofile', ['api', 'impl', 'shared'], ['features.startchat', 'libraries.matrix', 'libraries.mediaviewer'], ['profile.read', 'profile.update'], [P, V, `${S}MatrixClientServerApi.ets`], 'Basic profile read/update exists; verification, mutual rooms, media, and full profile actions are absent.'),
  missing('verifysession', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.dateformatter']),
  missing('viewfolder', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.ui-strings'])
];
