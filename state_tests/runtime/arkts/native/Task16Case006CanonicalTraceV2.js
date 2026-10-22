// Test-only scope selection. Input logs are never changed or removed.
export function canonicalManagerTraceV2(snapshot, bootstrap) {
  const need = (ok, reason) => { if (!ok) throw new Error('Case006 unavailable: ' + reason); };
  const current = snapshot.current;
  need(current && current.managerId && current.sdkPortMatches, 'actual canonical manager/port missing');
  const owners = snapshot.owners || [];
  need(owners.length === 2 && snapshot.ownerCount === owners.length, 'unknown/incomplete owner inventory');
  const retired = owners.find(owner => owner.ownerId === bootstrap.warmupOwnerId);
  need(retired && retired.disposed && retired.serviceAvailable === false && retired.sdkPortId === null &&
    retired.managerId && retired.managerId !== current.managerId, 'retired warm-up identity is not proved');
  const allTransitions = snapshot.managerTransitions || [];
  need(allTransitions.length && allTransitions.every(row =>
    row.managerId === current.managerId || row.managerId === retired.managerId), 'unknown manager transition');
  const canonicalTransitions = allTransitions.filter(row => row.managerId === current.managerId);
  need(canonicalTransitions.length, 'canonical manager transitions absent');
  for (let index = 1; index < canonicalTransitions.length; index++) {
    need(canonicalTransitions[index - 1].to === canonicalTransitions[index].from, 'canonical trace is discontinuous');
  }
  return {
    version: 'case006.actual-canonical-manager.v2', canonicalManagerId: current.managerId,
    retiredWarmupManagerId: retired.managerId,
    allTransitions: allTransitions.map(row => ({ ...row })),
    canonicalTransitions: canonicalTransitions.map(row => ({ ...row })),
    retiredWarmupTransitions: allTransitions.filter(row => row.managerId === retired.managerId).map(row => ({ ...row }))
  };
}
