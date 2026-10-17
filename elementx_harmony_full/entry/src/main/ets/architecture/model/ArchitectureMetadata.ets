export enum ClientModuleLayer {
  Feature = 'feature',
  Library = 'library',
  Service = 'service'
}

export enum RuntimeCapabilityStatus {
  Implemented = 'implemented',
  Partial = 'partial',
  Missing = 'missing'
}

export interface ClientModuleMetadata {
  id: string;
  layer: ClientModuleLayer;
  androidSourceDirectory: string;
  androidModules: string[];
  dependencies: string[];
  runtimeStatus: RuntimeCapabilityStatus;
  capabilityIds: string[];
  evidence: string[];
  gap: string;
}

export interface ClientArchitectureLayer {
  id: string;
  layer: ClientModuleLayer;
  modules: ClientModuleMetadata[];
}

export interface ClientArchitectureSummary {
  androidVersion: string;
  moduleDomainCount: number;
  androidGradleModuleCount: number;
  implementedCount: number;
  partialCount: number;
  missingCount: number;
}

export function createModuleMetadata(
  id: string,
  layer: ClientModuleLayer,
  androidSourceDirectory: string,
  androidVariants: string[],
  dependencies: string[],
  runtimeStatus: RuntimeCapabilityStatus,
  capabilityIds: string[],
  evidence: string[],
  gap: string
): ClientModuleMetadata {
  const androidModules: string[] = [];
  androidVariants.forEach((variant: string) => {
    if (variant.length === 0) {
      androidModules.push(androidSourceDirectory);
    } else {
      androidModules.push(`${androidSourceDirectory}/${variant}`);
    }
  });
  return {
    id: id,
    layer: layer,
    androidSourceDirectory: androidSourceDirectory,
    androidModules: androidModules,
    dependencies: dependencies,
    runtimeStatus: runtimeStatus,
    capabilityIds: capabilityIds,
    evidence: evidence,
    gap: gap
  };
}
