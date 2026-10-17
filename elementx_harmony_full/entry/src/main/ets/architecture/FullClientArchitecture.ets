import {
  ClientArchitectureLayer,
  ClientArchitectureSummary,
  ClientModuleLayer,
  ClientModuleMetadata,
  RuntimeCapabilityStatus
} from './model/ArchitectureMetadata';
import { FEATURE_MODULES } from './features/FeatureModuleCatalog';
import { LIBRARY_MODULES } from './libraries/LibraryModuleCatalog';
import { SERVICE_MODULES } from './services/ServiceModuleCatalog';

export const ANDROID_REFERENCE_VERSION: string = 'v26.04.0';

export const FULL_CLIENT_ARCHITECTURE: ClientArchitectureLayer[] = [
  { id: 'features', layer: ClientModuleLayer.Feature, modules: FEATURE_MODULES },
  { id: 'libraries', layer: ClientModuleLayer.Library, modules: LIBRARY_MODULES },
  { id: 'services', layer: ClientModuleLayer.Service, modules: SERVICE_MODULES }
];

export function getFullClientModules(): ClientModuleMetadata[] {
  const modules: ClientModuleMetadata[] = [];
  FULL_CLIENT_ARCHITECTURE.forEach((architectureLayer: ClientArchitectureLayer) => {
    architectureLayer.modules.forEach((moduleMetadata: ClientModuleMetadata) => {
      modules.push(moduleMetadata);
    });
  });
  return modules;
}

export function findFullClientModule(moduleId: string): ClientModuleMetadata | null {
  const modules = getFullClientModules();
  for (let index = 0; index < modules.length; index += 1) {
    if (modules[index].id === moduleId) {
      return modules[index];
    }
  }
  return null;
}

export function summarizeFullClientArchitecture(): ClientArchitectureSummary {
  const modules = getFullClientModules();
  let gradleModuleCount = 0;
  let implementedCount = 0;
  let partialCount = 0;
  let missingCount = 0;
  modules.forEach((moduleMetadata: ClientModuleMetadata) => {
    gradleModuleCount += moduleMetadata.androidModules.length;
    if (moduleMetadata.runtimeStatus === RuntimeCapabilityStatus.Implemented) {
      implementedCount += 1;
    } else if (moduleMetadata.runtimeStatus === RuntimeCapabilityStatus.Partial) {
      partialCount += 1;
    } else {
      missingCount += 1;
    }
  });
  return {
    androidVersion: ANDROID_REFERENCE_VERSION,
    moduleDomainCount: modules.length,
    androidGradleModuleCount: gradleModuleCount,
    implementedCount: implementedCount,
    partialCount: partialCount,
    missingCount: missingCount
  };
}
