"""Fail-closed native layout closure for the reviewed Task14/15 common prefix.

A filename or a missing selector is never an absence verdict. Only the complete
reviewed source identity AND the actual full native trees can close this prefix.
Any changed/extra/renamed/unbound control requires another executable binding.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

try:
    from . import task14_15_arkts_artifacts as artifacts
except ImportError:
    import task14_15_arkts_artifacts as artifacts

POLICY_ID = 'task14_15.arkts.complete-native-layout-source-closure.v2'
PROFILES = artifacts.ROOT / ('experiment_results/runtime_transition_20261020/formal_agent_scorer_audit/'
                             'task14_15_arkts_layout_closure_v2/profiles.json')
PROFILES_SHA256 = 'adb5dc0a1656c2f5161282c7fff330565213a4693f5999d8a5c935085eadb8a7'
FIELDS = ('type', 'id', 'key', 'text', 'originalText', 'hint', 'description', 'visible',
          'enabled', 'clickable', 'longClickable', 'scrollable', 'checkable', 'checked',
          'selected', 'hitTestBehavior', 'clip', 'opacity', 'zIndex')


def profiles():
    data = PROFILES.read_bytes()
    artifacts.require(hashlib.sha256(data).hexdigest() == PROFILES_SHA256,
                      'Reviewed native layout/source closure profile changed')
    value = json.loads(data)
    artifacts.require(value.get('policyId') == POLICY_ID and set(value.get('tasks', {})) == artifacts.TASKS,
                      'Wrong reviewed native closure identity')
    return value['tasks']


def reviewed_source(task_id, root_sha256):
    """Probe-selection hint only; fresh native layout/positive controls remain mandatory."""
    return root_sha256 == profiles()[task_id]['candidateRootSha256']


def bounds(value):
    match = re.fullmatch(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', value or '')
    artifacts.require(match is not None, 'Native layout has invalid/missing bounds; closure unavailable')
    return tuple(map(int, match.groups()))


def inventory(layout, *, checkpoint, observed):
    """Include EVERY node, even disabled/hidden and non-Button gesture targets."""
    viewport = bounds(layout.get('attributes', {}).get('bounds'))
    artifacts.require(viewport[2] > viewport[0] and viewport[3] > viewport[1], 'Empty native viewport')
    rows = []

    def visit(node, path):
        artifacts.require(isinstance(node, dict) and isinstance(node.get('attributes'), dict) and
                          isinstance(node.get('children'), list), 'Incomplete native layout subtree')
        attrs = node['attributes']
        geometry = bounds(attrs.get('bounds'))
        if attrs.get('visible') == 'true':
            artifacts.require(geometry[2] > geometry[0] and geometry[3] > geometry[1] and
                              viewport[0] <= geometry[0] < geometry[2] <= viewport[2] and
                              viewport[1] <= geometry[1] < geometry[3] <= viewport[3],
                              'Native control is clipped/offscreen; complete prefix not established')
        value = {key: attrs.get(key) for key in FIELDS}
        # The room identifier is an actual positive-control output, never a wildcard.
        if checkpoint == 'stored_direct_room_route' and attrs.get('id') == 'room_id':
            room = observed.get('storedDirectRoomId')
            artifacts.require(isinstance(room, str) and room.startswith('!local-') and
                              attrs.get('text') == attrs.get('originalText') == room,
                              'Direct-room layout differs from observed stored production room')
            value['text'] = value['originalText'] = '$observed.storedDirectRoomId'
        rows.append({'path': path, 'attributes': value, 'children': len(node['children'])})
        for index, child in enumerate(node['children']):
            visit(child, f'{path}/{index}')

    visit(layout, 'root')
    return rows


def check_layouts(raw, task_id):
    profile = profiles()[task_id]
    points = raw.get('checkpoints', [])
    names = [item.get('name') for item in points]
    artifacts.require(len(names) == len(set(names)) and set(names) == set(profile['checkpoints']),
                      'Native prefix checkpoint inventory is incomplete or duplicated')
    receipts = []
    for point in points:
        layout = json.loads(artifacts.bound(point['layout']))
        rows = inventory(layout, checkpoint=point['name'], observed=raw.get('observed', {}))
        artifacts.require(rows == profile['checkpoints'][point['name']],
                          'Unbound/extra/renamed native control or ambiguous capability; semantic absence unavailable')
        receipts.append({'checkpoint': point['name'], 'layout': point['layout'], 'nodes': len(rows),
                         'inventorySha256': artifacts.row_digest(rows)})
    return receipts


def check_sources(sources, task_id, *, candidate_root_sha256):
    profile = profiles()[task_id]
    artifacts.require(reviewed_source(task_id, candidate_root_sha256),
                      'Unreviewed candidate capability/source closure; missing-entry verdict unavailable')
    artifacts.require(sources == profile['productionSources'],
                      'Changed/extra/renamed production input; native common-prefix binding unavailable')


def check_prefix(raw, raw_report, task_id, sources, *, candidate_root_sha256):
    artifacts.require(raw_report.get('provenance', {}).get('production') == sources,
                      'Native execution/build production closure differs')
    check_sources(sources, task_id, candidate_root_sha256=candidate_root_sha256)
    return {'policyId': POLICY_ID, 'profileSha256': PROFILES_SHA256,
            'sourceClosureVerified': True, 'checkpoints': check_layouts(raw, task_id)}
