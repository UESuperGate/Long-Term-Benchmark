let execute, bundle;
export function configurePagePortsProbe(probe, bundleName) { execute = probe; bundle = bundleName; }
export function attachPagePortsProbe(bridge) {
  if (typeof execute !== 'function' || !bundle) throw new Error('Page port runtime not configured');
  bridge.runPagePortsUI = async spec => JSON.parse(await execute(JSON.stringify(spec), bundle));
}
