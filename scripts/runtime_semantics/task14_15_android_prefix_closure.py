"""Eligibility for the exact original Android UI prefix, never a source-only verdict."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
POLICY_ID = 'task14_15.android.immutable-production-ui-prefix.v2'
DIRECTORY = ROOT / ('experiment_results/runtime_transition_20261020/formal_agent_scorer_audit/'
                    'task14_15_android_prefix_closure_v2')
PROFILES = DIRECTORY / 'profiles.json'
PROFILES_SHA256 = '15386a0bf7b1139b750309ced6b6cab99cb1212b48d532375046612b6f6c26b7'
INPUT_KEYS = ('evaluatorSources', 'catalogDependencies', 'buildVariantFields', 'resourceApkSha256')


def require(value, message):
    if not value:
        raise ValueError(message)


def profiles():
    data = PROFILES.read_bytes()
    require(hashlib.sha256(data).hexdigest() == PROFILES_SHA256, 'Android reviewed UI closure profile changed')
    document = json.loads(data)
    require(document.get('policyId') == POLICY_ID, 'Wrong Android prefix closure identity')
    return document['tasks']


def reviewed_source(task_id, root_sha256):
    """Select a probe binding only. Real render, click and isolation are still required."""
    return profiles()[task_id]['sourceRootSha256'] == root_sha256


def prefix_inventory(raw):
    points = copy.deepcopy(raw['checkpoints'])
    require(len(points) == len({p['name'] for p in points}), 'Duplicate UI prefix checkpoint')
    for point in points:
        state = point['state']
        if 'caseKey' in state:
            require(state['caseKey'] == raw['key'], 'UI prefix case identity changed')
            state['caseKey'] = '$canonical.key'
        if 'semantics' in state:
            # Only volatile Compose node IDs and CollectionInfo object addresses vary.
            # Labels/actions/tree indentation/bounds/unknown properties are all retained.
            state['semantics'] = re.sub(r'Node #\d+', 'Node #<runtime>', state['semantics'])
            state['semantics'] = re.sub(r'androidx\.compose\.ui\.semantics\.CollectionInfo@[0-9a-f]+',
                'androidx.compose.ui.semantics.CollectionInfo@<runtime>', state['semantics'])
    return points


def check_inventory(raw, task_id):
    profile = profiles()[task_id]
    require(prefix_inventory(raw) == profile['prefixInventory'],
            'Unbound/extra/renamed Android control or incomplete original UI prefix; absence unavailable')


def check_sources(provenance, task_id, sources):
    profile = profiles()[task_id]
    require(reviewed_source(task_id, provenance.get('candidateRootSha256')),
            'Unreviewed Android candidate capability/source identity; missing-entry verdict unavailable')
    require(len(sources) == len({item['path'] for item in sources}) and
            sources == provenance.get('productionSources') and
            sorted(sources, key=lambda item: item['path']) ==
            sorted(profile['productionSources'], key=lambda item: item['path']),
            'Changed/extra/renamed Android production UI closure; missing-entry binding unavailable')
    require({key: provenance.get(key) for key in INPUT_KEYS} == profile['runtimeInputs'],
            'Android prefix evaluator/resource inputs differ from the reviewed original UI binding')
    try:
        from . import task14_15_android_entry_evidence as artifacts
    except ImportError:
        import task14_15_android_entry_evidence as artifacts
    reviewed = json.loads(artifacts.bound(profile['reviewedReport']))
    original = json.loads(artifacts.bound(reviewed['semantic']['cases'][0]['entryFailureEvidence']['report']))
    require(provenance.get('resourceDependencies') == original['provenance'].get('resourceDependencies') and
            bool(provenance.get('resourceDependencies')),
            'Android original UI dependency inventory changed; prefix capability is unbound')
    return {'policyId': POLICY_ID, 'profileSha256': PROFILES_SHA256,
            'eligibilityOnly': True, 'immutableCommit': profile['commit'], 'immutableTree': profile['tree'],
            'productionInputs': len(sources), 'runtimePositiveControlStillRequired': True}


def check_prefix(raw, raw_report, task_id, sources):
    proof = check_sources(raw_report.get('provenance', {}), task_id, sources)
    check_inventory(raw, task_id)
    return proof
