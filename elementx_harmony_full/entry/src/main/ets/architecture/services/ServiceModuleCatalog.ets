import {
  ClientModuleLayer,
  ClientModuleMetadata,
  RuntimeCapabilityStatus,
  createModuleMetadata
} from '../model/ArchitectureMetadata';

function missing(name: string, variants: string[], dependencies: string[]): ClientModuleMetadata {
  return createModuleMetadata(
    `services.${name}`,
    ClientModuleLayer.Service,
    `services/${name}`,
    variants,
    dependencies,
    RuntimeCapabilityStatus.Missing,
    [],
    [],
    'No production-equivalent ArkTS runtime for this Android service domain is present.'
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
    `services.${name}`,
    ClientModuleLayer.Service,
    `services/${name}`,
    variants,
    dependencies,
    RuntimeCapabilityStatus.Partial,
    capabilityIds,
    evidence,
    gap
  );
}

export const SERVICE_MODULES: ClientModuleMetadata[] = [
  missing('analytics', ['api', 'compose', 'impl', 'noop', 'test'], ['services.analyticsproviders', 'services.appnavstate', 'services.toolbox']),
  missing('analyticsproviders', ['api', 'posthog', 'sentry', 'test'], ['services.appnavstate', 'libraries.matrix']),
  partial('apperror', ['api', 'impl', 'test'], ['services.toolbox', 'libraries.ui-strings'], ['error.inline'], ['entry/src/main/ets/pages/Index.ets', 'entry/src/main/ets/viewmodel/ElementClientViewModel.ets'], 'Errors are surfaced as local result strings; there is no centralized application-error service.'),
  partial('appnavstate', ['api', 'impl', 'test'], ['libraries.matrix'], ['navigation.snapshot'], ['entry/src/main/ets/model/ClientRuntimeModels.ets', 'entry/src/main/ets/services/LaunchIntentStore.ets'], 'Root navigation and intent snapshots exist without the Android observable app-navigation service.'),
  missing('toolbox', ['api', 'impl', 'test'], ['libraries.androidutils', 'libraries.di'])
];
