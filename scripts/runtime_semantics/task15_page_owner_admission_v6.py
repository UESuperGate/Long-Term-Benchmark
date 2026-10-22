"""Independent raw admission for actually packaged Task15 owner-v6 episodes."""
import json
from pathlib import Path

from . import task15_page_owner_v5 as owner
from . import task15_fresh_admission_v2 as transport

PROTOCOL = 'task15.arkts.original-owner-packaging.v6'
APPROVED_NATIVE_PROFILES = {}


def admit(bundle, contract, *, profile_key):
    transport.require(profile_key in APPROVED_NATIVE_PROFILES,
        'No source-bound actual native owner/layout profile reviewed; discovery is not runtime proof')
    data = transport.envelope(bundle, contract)
    plan, build = data['plan'], data['build']
    transport.require(plan.get('packagingProtocol') == PROTOCOL and plan.get('pageOwnerProtocol') == owner.PROTOCOL,
        'Old detached host or diagnostic row cannot acquire native original-owner provenance')
    bindings = transport.read(plan['actualSourceBindings'])
    production = {item['path']: item['sha256'] for item in build['production']}
    for item in bindings['sourceFiles']:
        transport.require(production.get(item['path']) == item['sha256'], 'Control discovery differs from compiled production')
    bound = build['nativeUIObserver']['binding']
    transport.require(bound['ownerBinding'] == bindings['ownerBinding'] and
        bound['controlSelectors'] == bindings['controlSelectors'], 'Original owner/physical selectors were not packaged')
    indexed = {Path(item['path']).name: item for item in plan['derivedFiles']}
    fixtures = {Path(item['installedPath']).name: item for item in build['nativeUIObserver']['fixtures']}
    for name in ('Task15PageOwnerObserverV5.js', 'Task15FreshActionsV2.js', 'Task15NativeUi.js'):
        transport.require(indexed[name]['sha256'] == fixtures[name]['sha256'], 'New native original-owner fixture not compiled')
    profile = transport.read(APPROVED_NATIVE_PROFILES[profile_key])
    transport.require(profile['ownerBinding'] == bindings['ownerBinding'] and
        profile['sourceRootSha256'] == data['inputs']['rootSha256'] and profile['compiledProduction'] == build['production'],
        'Unknown original owner/source/layout closure')
    result = owner.inspect_same_page_owner(data, profile)
    return {**result, 'rawEpisode': bundle, 'productionSources': build['production'], 'packagingProtocol': PROTOCOL}
