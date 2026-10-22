"""New reviewed-input proposal, never an expansion of the frozen v2 policy.

Only diagnostic admission here; public integration remains main-owned. Hashes
fence unknown UI code, but cannot supply the physical transition themselves.
"""
import hashlib
import json
from pathlib import Path

from scripts.runtime_semantics import tasks16_17_arkts_entry_binding_v2 as acquisition

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT/'experiment_results/runtime_transition_20261020/tasks16_17_arkts_production_ports_v1/entry-v3-proposal/reference.json'
REFERENCE_SHA256 = '7bcd05d253eefb92971384dd44736567a5930113bf40b263ece9c7d30dfe3d74'
POLICY_ID = 'tasks16_17.arkts.closed-input-entry.v3'


def require(value, message):
    if not value:
        raise ValueError('Physical prefix unavailable: '+message)


def reference():
    require(acquisition.record(REFERENCE)['sha256'] == REFERENCE_SHA256, 'review proposal changed')
    value = json.loads(REFERENCE.read_text())
    require(value['policyId'] == POLICY_ID and value['publicAdmissionChanged'] is False, 'wrong policy')
    require(acquisition.record(acquisition.__file__) == value['oldPolicy'] and
            acquisition.record(acquisition.REFERENCE) == value['oldReference'], 'frozen v2 changed')
    return value


def assess(build, task_id, input_binding):
    """Prospective before/after required. No legacy/path/role fallback."""
    reviewed = reference()['tasks'][task_id]
    binding = acquisition.bound(input_binding)
    require(acquisition.bound(binding['build']) == build and binding['buildRecordHash'] ==
            hashlib.sha256(json.dumps(build, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'actual build seal differs')
    before, after = [acquisition.bound(binding[key]) for key in ('before', 'after')]
    for captured, phase in ((before, 'before_runtime'), (after, 'after_runtime')):
        require(captured.get('phase') == phase and captured.get('complete') is True and
                captured.get('producer') == acquisition.record(acquisition.__file__) and
                captured.get('candidateSource') and build.get('source') and
                Path(captured['candidateSource']).resolve() == Path(build['source']).resolve(),
                'capture phase/source/producer differs')
    require(before['files'] == after['files'] == reviewed['completeInputs'], 'unknown/changed/extra full inputs')
    order = acquisition.ordered
    require(order(build.get('production', [])) == order(reviewed['compiledProduction']) ==
            order(build.get('nativeUIObserver', {}).get('production', [])), 'compiled closure differs')
    require(build.get('productionUnchanged') and build.get('copiedProductionUnchanged') and
            build.get('temporaryProjectRemoved') and build.get('runtimeCompile', {}).get('passed'), 'packaging incomplete')
    return dict(policyId=POLICY_ID, eligible=True, reference=acquisition.record(REFERENCE),
                validator=acquisition.record(__file__), inputBinding=input_binding,
                completeInputFileCount=len(before['files']), publicAdmissionChanged=False,
                reviewStatus='pending_main_review', usage='eligibility only, not a semantic verdict')


def physical_facts(case, raw):
    """No projected final state or manufactured false invariants."""
    task_id = raw.get('taskId')
    require(task_id in ('16_identity_reset', '17_pinned_messages'), 'wrong task')
    require(all(raw.get(key) == case[key] for key in ('caseId', 'key', 'traceDigest')), 'case binding differs')
    require(raw.get('integrationTier') == 'actual_page_physical_prefix' and not raw.get('failure') and
            raw.get('eventExecuted') and raw.get('classification') == 'physical_prefix_completed', 'real prefix incomplete')
    require(raw.get('observed') is None and raw.get('invariantChecks') == [] and
            raw.get('unevaluatedInvariants') == case['invariants'], 'final state/invariants fabricated')
    frames = raw.get('frames', [])
    require([value['label'] for value in frames] == ['before_event', 'after_event'], 'physical frames incomplete')
    identity = task_id == '16_identity_reset'
    for value in frames:
        window = value['windowIdentity']
        require(window.get('hostVerified') and window.get('focused') and window.get('bundleName') == raw['bundleName']
                and window.get('routeName') in ('pages/Index', 'pages/Index.ets'), 'wrong original window')
        inventory = value.get('inventory')
        require(inventory, 'full native inventory absent')
        for item in inventory:
            bounds = item['bounds']
            require(all(isinstance(bounds.get(key), (int, float)) for key in ('left','right','top','bottom')),
                    'native inventory bounds absent')
            if item['clickable'] or item['type'] in ('Button', 'TextInput'):
                if identity:
                    allowed = ((item['type'] == 'Button' and item['text'] in ('Enable backup', 'Recover')) or
                               item['type'] == 'TextInput')
                else:
                    allowed = item['type'] == 'Button' and item['id'] == 'pinned_banner_next' and item['text'] == 'Next'
                require(allowed, 'extra/renamed/unbound native control')
        buttons = [item for item in inventory if item['type'] == 'Button']
        require(sorted(item['text'] for item in buttons) == (['Enable backup','Recover'] if identity else ['Next']),
                'missing/duplicate native controls')
        require(sum(item['type'] == 'TextInput' for item in inventory) == (1 if identity else 0),
                'extra/missing native input controls')
    actions = raw.get('actions', [])
    require(len(actions) == 1 and actions[0].get('kind') == 'click' and actions[0].get('completed') and
            frames[0]['sequence'] < actions[0]['sequence'] < frames[1]['sequence'], 'physical click missing/reordered')
    target = dict(type='Button', text='Enable backup') if identity else dict(type='Button', text='Next', id='pinned_banner_next')
    require(all(actions[0].get(key) == value for key,value in target.items()), 'wrong physical target')
    clicked = [item for item in frames[0]['inventory'] if all(item.get(key) == value for key,value in target.items())]
    require(len(clicked) == 1 and clicked[0]['enabled'] and clicked[0]['clickable'], 'target disabled/ambiguous')
    bounds, window = clicked[0]['bounds'], frames[0]['windowIdentity']['bounds']
    require(min(bounds['right'],window['right']) > max(bounds['left'],window['left']) and
            min(bounds['bottom'],window['bottom']) > max(bounds['top'],window['top']), 'target outside actual window')
    texts = [{item['text'] for item in frame['inventory']} for frame in frames]
    initial, final = ('Backup state: disabled','Backup state: enabled') if identity else ('Please read the room rules','Welcome to the room')
    require(initial in texts[0] and final not in texts[0] and final in texts[1] and initial not in texts[1],
            'production positive-control transition not observed')
    require(('Chat backup' if identity else 'Design team') in texts[0], 'common original entry absent')
    return dict(physicalPrefixVerified=True, featureMissingRequiresEligibility=True,
                observed=None, invariantChecks=[], unevaluatedInvariants=case['invariants'])
