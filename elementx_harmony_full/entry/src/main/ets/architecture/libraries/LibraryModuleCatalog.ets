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
    `libraries.${name}`,
    ClientModuleLayer.Library,
    `libraries/${name}`,
    variants,
    dependencies,
    RuntimeCapabilityStatus.Missing,
    [],
    [],
    'No production-equivalent ArkTS runtime for this Android library domain is present.'
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
    `libraries.${name}`,
    ClientModuleLayer.Library,
    `libraries/${name}`,
    variants,
    dependencies,
    RuntimeCapabilityStatus.Partial,
    capabilityIds,
    evidence,
    gap
  );
}

export const LIBRARY_MODULES: ClientModuleMetadata[] = [
  missing('accountselect', ['api', 'impl'], ['libraries.matrix', 'libraries.session-storage']),
  missing('androidutils', [''], ['libraries.core', 'services.toolbox']),
  partial('architecture', [''], ['libraries.core', 'libraries.di'], ['architecture.state-snapshots'], [V], 'The client uses one mutable view model and snapshots; Appyx/Molecule-equivalent lifecycle and reactive contracts are absent.'),
  missing('audio', ['api', 'impl', 'test'], ['libraries.di']),
  missing('compound', [''], []),
  partial('core', [''], [], ['core.models'], ['entry/src/main/ets/model/ClientModels.ets', 'entry/src/main/ets/model/ClientRuntimeModels.ets', 'entry/src/main/ets/model/ElementModels.ets'], 'Only client-specific models and helpers exist; the Android core library surface is not fully represented.'),
  missing('cryptography', ['api', 'impl', 'test'], ['libraries.di']),
  missing('dateformatter', ['api', 'impl', 'test'], ['libraries.core', 'services.toolbox']),
  partial('deeplink', ['api', 'impl'], ['libraries.matrix', 'services.toolbox'], ['intent.deeplink'], [`${S}LaunchIntentStore.ets`], 'Selected Matrix and share intents are parsed; full permalink and navigation coverage is absent.'),
  partial('designsystem', [''], ['libraries.compound', 'libraries.ui-strings'], ['ui.shell'], [P], 'ArkUI styling exists inside one page, without a reusable Compound-equivalent design system.'),
  missing('di', [''], []),
  missing('encrypted-db', [''], ['libraries.androidutils']),
  missing('eventformatter', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.matrixui']),
  missing('featureflag', ['api', 'impl', 'test', 'ui'], ['libraries.preferences', 'libraries.matrix']),
  missing('fullscreenintent', ['api', 'impl'], ['libraries.permissions', 'libraries.matrix']),
  missing('indicator', ['api', 'impl', 'test'], ['libraries.featureflag', 'libraries.matrix']),
  partial('matrix', ['api', 'impl', 'test'], ['libraries.network', 'libraries.rustsdk', 'libraries.session-storage'], ['matrix.rest-subset', 'sync.foreground'], [`${S}MatrixClientContract.ets`, `${S}MatrixClientServerApi.ets`, `${S}MatrixClientService.ets`], 'A REST subset and fixture adapter exist; there is no Matrix Rust SDK bridge, encryption, live services, or full event model.'),
  partial('matrixmedia', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.session-storage'], ['media.upload'], [`${S}MatrixClientServerApi.ets`, `${S}SharedMediaFileReader.ets`], 'Plain upload and file reading exist; authenticated download, cache, decryption, and encrypted media are absent.'),
  partial('matrixui', [''], ['libraries.matrix', 'libraries.matrixmedia', 'libraries.designsystem'], ['timeline.render'], [P], 'Selected timeline events render in a monolithic page; reusable Matrix UI components and full event coverage are absent.'),
  partial('mediapickers', ['api', 'impl', 'test'], ['libraries.permissions', 'libraries.ui-strings'], ['intent.share'], [`${S}LaunchIntentStore.ets`, `${S}SharedMediaFileReader.ets`], 'Incoming shared files are read, but a platform picker abstraction is not implemented.'),
  missing('mediaplayer', ['api', 'impl', 'test'], ['libraries.audio', 'libraries.matrix']),
  partial('mediaupload', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.preferences'], ['media.upload'], [V, `${S}MatrixClientServerApi.ets`], 'Basic unencrypted upload exists without queueing, retries, progress, cancellation, or encrypted media.'),
  partial('mediaviewer', ['api', 'impl', 'test'], ['libraries.matrixmedia', 'libraries.matrixui'], ['media.gallery-surface'], [P, 'entry/src/main/ets/androidparity/FunctionLevelParity.ets'], 'Gallery surfaces exist, but production media loading, paging, playback, and sharing are incomplete.'),
  partial('network', [''], ['libraries.core', 'libraries.preferences'], ['network.http'], [`${S}MatrixClientServerApi.ets`], 'HTTP calls exist without the Android network stack, monitoring, retry policy, or certificate handling parity.'),
  missing('oidc', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.permissions']),
  partial('permissions', ['api', 'impl', 'noop', 'test'], ['libraries.troubleshoot', 'services.toolbox'], ['intent.share'], [`${S}LaunchIntentStore.ets`], 'Intent grants are consumed, but a reusable runtime-permission abstraction is absent.'),
  partial('preferences', ['api', 'impl', 'test'], ['libraries.matrix'], ['preferences.basic'], [`${S}PersistentSessionStore.ets`, V], 'Preferences persistence is used for sessions and selected options; Android preference coverage and security are incomplete.'),
  missing('previewutils', [''], ['libraries.designsystem', 'libraries.matrix']),
  missing('push', ['api', 'impl', 'test'], ['libraries.pushproviders', 'libraries.pushstore', 'libraries.matrix']),
  missing('pushproviders', ['api', 'firebase', 'test', 'unifiedpush'], ['libraries.push', 'libraries.pushstore']),
  missing('pushstore', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.preferences']),
  partial('qrcode', [''], ['libraries.designsystem'], ['device-link.surface'], ['entry/src/main/ets/androidparity/FunctionLevelParity.ets', P], 'QR state is represented for parity UI, but no QR encoder/scanner or SDK-backed login flow exists.'),
  missing('recentemojis', ['api', 'impl', 'test'], ['libraries.matrix']),
  partial('roomselect', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.matrixui'], ['room.select'], [`${S}MatrixClientService.ets`, P], 'A selected-room snapshot exists without the reusable Android room-selection flow.'),
  missing('rustsdk', [''], []),
  partial('session-storage', ['api', 'impl', 'test'], ['libraries.encrypted-db', 'libraries.matrix'], ['session.persistence'], [`${S}PersistentSessionStore.ets`], 'Preferences-backed session persistence exists; tokens and crypto material are not stored in an encrypted production store.'),
  missing('testtags', [''], []),
  partial('textcomposer', ['impl', 'lib'], ['libraries.matrix', 'libraries.matrixui'], ['message.send'], [P, V], 'A basic text composer sends messages; rich editing, mentions, attachments, and draft semantics are incomplete.'),
  missing('troubleshoot', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.push']),
  partial('ui-common', [''], ['libraries.designsystem'], ['ui.shell'], [P], 'Common visual patterns exist only inside the monolithic client page.'),
  partial('ui-strings', [''], [], ['ui.shell'], ['entry/src/main/resources/base/element/string.json'], 'A small Harmony string set exists; Android v26.04.0 localization coverage is not migrated.'),
  partial('ui-utils', [''], ['libraries.androidutils', 'services.toolbox'], ['ui.shell'], [P], 'Local page helpers exist without an independently reusable UI utilities library.'),
  missing('usersearch', ['api', 'impl', 'test'], ['libraries.matrix', 'libraries.matrixui']),
  missing('voiceplayer', ['api', 'impl'], ['libraries.audio', 'libraries.mediaplayer', 'libraries.matrix']),
  missing('voicerecorder', ['api', 'impl', 'test'], ['libraries.audio', 'libraries.matrix']),
  partial('wellknown', ['api', 'impl', 'test'], ['libraries.network', 'libraries.matrix'], ['homeserver.discovery'], [`${S}MatrixClientServerApi.ets`], 'Client discovery is implemented for login, but caching, delegated authentication, and complete error semantics are absent.'),
  missing('workmanager', ['api', 'impl', 'test'], ['libraries.session-storage', 'libraries.matrix'])
];
