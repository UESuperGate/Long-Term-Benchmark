#!/usr/bin/env python3
"""Offline Task11 evaluator wiring only; never builds, scores, or edits a candidate."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / 'state_tests/runtime/android/11_room_upgrade_navigation'
ORIGINAL = TASK / 'navigation/LoadedNavigationTest.kt'
LEAF = TASK / 'sdk_leaf_v1/Task11SdkLeafRooms.kt'
TEMPLATE = TASK / 'android11_navigation_followup/navigation_entry_compile_attempt2.config.json'
MATRIX = 'libraries/matrix/impl/src/main/kotlin/io/element/android/libraries/matrix/impl/'
EXTRA_ENTRYPOINTS = [MATRIX + p for p in (
    'room/RustBaseRoom.kt', 'room/JoinedRustRoom.kt', 'room/RoomInfoMapper.kt',
    'room/RoomSyncSubscriber.kt', 'room/RoomContentForwarder.kt',
    'room/tombstone/PredecessorRoom.kt', 'timeline/RustTimeline.kt',
    'notificationsettings/RustNotificationSettingsService.kt',
)]
EXTRA_ENTRYPOINTS += [
    'libraries/permissions/impl/src/main/kotlin/io/element/android/libraries/permissions/impl/DefaultPermissionsPresenter.kt',
    'features/roomcall/impl/src/main/kotlin/io/element/android/features/roomcall/impl/RoomCallStatePresenter.kt',
    'features/roommembermoderation/impl/src/main/kotlin/io/element/android/features/roommembermoderation/impl/RoomMemberModerationPresenter.kt',
    'features/call/impl/src/main/kotlin/io/element/android/features/call/impl/utils/DefaultCurrentCallService.kt',
    'features/enterprise/impl/src/main/kotlin/io/element/android/features/enterprise/impl/DefaultEnterpriseService.kt',
    'libraries/preferences/impl/src/main/kotlin/io/element/android/libraries/preferences/impl/store/DefaultSessionPreferencesStore.kt',
]
MESSAGES = 'features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/'
EXTRA_ENTRYPOINTS += [MESSAGES + p for p in (
    'crypto/identity/IdentityChangeStatePresenter.kt',
    'crypto/sendfailure/resolve/ResolveVerifiedUserSendFailurePresenter.kt', 'link/LinkPresenter.kt',
    'pinned/banner/PinnedMessagesBannerPresenter.kt', 'timeline/components/customreaction/CustomReactionPresenter.kt',
    'timeline/components/reactionsummary/ReactionSummaryPresenter.kt',
    'timeline/components/receipt/bottomsheet/ReadReceiptBottomSheetPresenter.kt',
    'timeline/protection/TimelineProtectionPresenter.kt', 'typing/TypingNotificationPresenter.kt',
    'voicemessages/composer/VoiceMessageComposerPresenter.kt',
)]


def record(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Reviewed evaluator input changed; never silently adapt assertions')
    return text.replace(old, new, 1)


def transform(text):
    """Only evaluator setup changes; no production file is transformed."""
    assertions = [line for line in text.splitlines() if any(
        token in line for token in ('assertEquals(', 'assertTrue(', 'Evidence.invariant('))]
    start = text.index('            val items = MutableStateFlow<List<MatrixTimelineItem>>')
    end = text.index('\n        }\n        val roomList =', start)
    block = text[start:end]
    if block.count('rooms[id.value] = port<JoinedRoom>') != 1 or block.count('port<Timeline>') != 1:
        raise ValueError('Reviewed room/timeline construction boundary changed')
    replacement = '''            val rawPredecessor = if (id != currentId) null else
                given.getAsJsonObject("predecessor")?.let {
                    org.matrix.rustcomponents.sdk.PredecessorRoom(it["roomId"].asString, it["lastEventId"].asString)
                } ?: given.get("predecessorRoomId")?.let {
                    // Unconstrained SDK input for banner-only case; never a post-state projection.
                    org.matrix.rustcomponents.sdk.PredecessorRoom(it.asString, "\\$fixture-last:example.org")
                }
            rooms[id.value] = Task11SdkLeafRooms.create(id, session, roomInfo, rawPredecessor,
                dispatchers, membership, scope, sdkCalls, construction)'''
    text = replace_once(text, block, replacement)
    text = replace_once(text, '        val timelines = mutableMapOf<String, MutableStateFlow<List<MatrixTimelineItem>>>()\n', '')
    # Original app DTO remains EXPECTED assertion data only, never input to a room.
    text = replace_once(text, '        val currentId = RoomId(given["currentRoomId"].asString)',
                        '        val currentId = RoomId((given.get("currentRoomId") ?: given.get("roomId")).asString)')
    text = replace_once(text, '            else given.getAsJsonObject("predecessor")["roomId"].asString)',
                        '            else (given.getAsJsonObject("predecessor")?.get("roomId") ?: given.get("predecessorRoomId")).asString)')
    old = '        val predecessor = given.getAsJsonObject("predecessor")?.let { PredecessorRoom(RoomId(it["roomId"].asString), EventId(it["lastEventId"].asString)) }'
    text = replace_once(text, old, old + '''
            ?: given.get("predecessorRoomId")?.let { PredecessorRoom(RoomId(it.asString), EventId("\\$fixture-last:example.org")) }''')
    text = replace_once(text, '    @Test fun open_predecessor() = probe("open_predecessor")',
                        '    @Test fun open_predecessor() = probe("open_predecessor")\n    @Test fun predecessor_banner() = probe("predecessor_banner")')
    text = replace_once(text, '            val timelineBefore = composition.state', '''            val timelineBefore = composition.state
            check(sdkCalls.any { it["method"] == "Room.predecessorRoom" && it["roomId"] == currentId.value }) {
                "Current room must acquire its predecessor through the source-bound production SDK bridge"
            }
            Evidence.record("production_sdk_acquisition", "roomClass" to rooms.getValue(currentId.value).javaClass.name,
                "timelineClass" to rooms.getValue(currentId.value).liveTimeline.javaClass.name,
                "sdkCalls" to sdkCalls.toList(), "runtime" to snapshot())''')
    button = '''                button.performClick()
                compose.waitForIdle()
            } else {'''
    banner = '''                if (key == "predecessor_banner") {
                    val name = timelineBefore.timelineRoomInfo.name
                    val ordinary = if (name == null) activity.get().getString(
                        io.element.android.features.messages.impl.R.string.screen_room_timeline_beginning_of_room_no_name)
                    else activity.get().getString(
                        io.element.android.features.messages.impl.R.string.screen_room_timeline_beginning_of_room, name)
                    compose.onNodeWithText(ordinary).assertIsDisplayed()
                    check(sdkCalls.any { it["method"] == "Room.predecessorRoom" })
                    Evidence.record("after_render", "runtime" to snapshot(),
                        "semanticsTree" to compose.onRoot(useUnmergedTree = true).printToString(),
                        "ordinaryRoomBeginning" to ordinary, "pixels" to pixels("${key}_after"))
                    Evidence.observe("predecessorBannerVisible" to button.isDisplayed(),
                        "historyVisible" to compose.onNodeWithText(ordinary).isDisplayed())
                    Evidence.invariant("the ordinary room-beginning content remains visible",
                        compose.onNodeWithText(ordinary).isDisplayed(), ordinary)
                    return
                }
''' + button
    text = replace_once(text, button, banner)
    if any(line not in text for line in assertions):
        raise ValueError('Original navigation assertions must remain unchanged')
    return text


def recipe():
    config = copy.deepcopy(json.loads(TEMPLATE.read_text()))
    config.pop('sources', None)  # Never reuse a historical candidate file manifest.
    config.update(scope='task11_sdk_leaf_original_loaded_page_preparation', sourceClosure=False,
                  testClass='runtime.LoadedNavigationTest',
                  keys=['open_successor', 'predecessor_banner', 'open_predecessor'])
    config['entrypoints'] = sorted(set(config['entrypoints'] + EXTRA_ENTRYPOINTS))
    config['evaluatorSources'] = [str(ORIGINAL), str(TASK / 'navigation/ActualConstructorGraph.kt'),
                                  str(TASK / 'messages/LocationBuildConfig.kt'), str(LEAF)]
    config['dependencyCatalog']['libraries'] = sorted(set(config['dependencyCatalog']['libraries'] + [
        'matrix_sdk', 'test_mockk', 'accompanist_permission', 'androidx_datastore_preferences',
        'androidx_core', 'androidx_corektx', 'serialization_json']))
    return config


def prepare(source, output):
    """Bind candidate files without copying production, resolving deps, or building."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError('Fresh evaluator-owned output outside the candidate required')
    if not (source / 'gradlew').is_file():
        raise ValueError('Explicit standalone Android candidate required')
    config = recipe()
    bindings = []
    for relative in config['entrypoints'] + ['gradle/libs.versions.toml']:
        path = source / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError('Candidate compile input unavailable; this is not a semantic failure: ' + relative)
        bindings.append({'relativePath': relative, **record(path)})
    output.mkdir(parents=True)
    derived = output / ORIGINAL.name
    derived.write_text(transform(ORIGINAL.read_text()))
    config['evaluatorSources'][0] = str(derived)
    # Keep the existing SDK-owned WYSIWYG switch and its original class name.
    if __package__:
        from .task11_plaintext_sdk import configure
    else:
        from task11_plaintext_sdk import configure
    config = configure(config, output / 'wysiwyg')
    plan = {'schema': 'task11-sdk-leaf-preparation/v1', 'source': str(source),
            'runtimeCompile': {'status': 'not_run'}, 'semanticScore': None,
            'compilerReadyClaimed': False, 'productionSourcesCopiedOrModified': False,
            'entrypointBindings': bindings, 'evaluatorInputs': [record(ORIGINAL), record(LEAF),
                record(TEMPLATE), record(Path(__file__))], 'derivedEvaluator': record(derived),
            'configuredEvaluatorInputs': [record(filename) for filename in config['evaluatorSources']],
            'configurationRecipe': config,
            'pending': ['Resolve whole unmodified source closure from this candidate, including appnav; never reuse a historical sources array.',
                        'Resolve exact candidate catalog dependencies/MockK/SDK and record actual compile/runtime classpath.',
                        'Compile and execute in the shared heavy queue; errors stay NS.',
                        'Validate base/final and same-agent copies, then replay the exact candidate before admission.'],
            'executionRequirements': {'overallSeconds': 3600, 'minimumFreeBytes': 8 * 1024**3,
                'locks': ['/tmp/long-term-benchmark-android-full-build.lock',
                          str(ROOT / 'state_tests/runtime/android/.build.lock')]}}
    (output / 'preparation.json').write_text(json.dumps(plan, indent=2) + '\n')
    return plan


def runtime_modules():
    # Keep the shared runner and patched_candidate on the SAME module instance.
    folder = str(ROOT / 'scripts/runtime_semantics')
    if folder not in sys.path:
        sys.path.insert(0, folder)
    return tuple(__import__(name) for name in (
        'android_robolectric', 'android_robolectric_ui_resources',
        'task10_11_android_strict_common', 'task14_15_formal_core'))


def execute_prepared(preparation, output, *, resource_clear_reviewed=False, timeout=3600):
    """Explicit queued diagnostic; never publishes canonical rows or readiness."""
    if not resource_clear_reviewed:
        raise ValueError('Heavy queue/resource review required; do not start a JVM')
    if not 0 < timeout <= 3600:
        raise ValueError('One overall deadline of at most 3600 seconds required')
    deadline = time.monotonic() + timeout
    preparation, output = Path(preparation).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError('Never overwrite a runtime attempt')
    plan = json.loads(preparation.read_text())
    source = Path(plan['source'])
    if output.is_relative_to(source):
        raise ValueError('Runtime output must be evaluator-owned, outside the candidate')
    preparation_binding = record(preparation)
    evidence = output.with_suffix('.sdk-leaf-evidence')
    evidence.mkdir(parents=True, exist_ok=False)
    result = {'scope': 'task11_sdk_leaf_diagnostic_not_formal_score', 'status': 'not_scored',
              'semanticPromotionEligible': False, 'runtimeCompile': {'status': 'not_run'},
              'preparation': preparation_binding, 'source': str(source), 'reason': None}
    android_robolectric = None
    old_prepare = old_resources = old_subprocess = None
    class BoundedProcesses:
        def __getattr__(self, name):
            return getattr(old_subprocess, name)
        def run(self, command, *args, **kwargs):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Task11 single runtime deadline exhausted')
            kwargs['timeout'] = min(kwargs.get('timeout', remaining), remaining)
            process = old_subprocess.run(command, *args, **kwargs)
            if process.returncode == 0 and '-d' in command and 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler' in command:
                classes = Path(command[command.index('-d') + 1])
                binaries = [record(path) for path in classes.rglob('*.class')]
                (evidence / 'compiled-class-hashes.json').write_text(json.dumps({
                    'classDirectory': str(classes), 'hashesBeforeTemporaryCleanup': binaries,
                    'binaryBytesRetained': False}, indent=2) + '\n')
            return process
    try:
        # Import failures are retained as diagnostics, not lost before the try/finally.
        android_robolectric, resources, mechanics, core = runtime_modules()
        compile_resources = resources.compile_resources
        old_prepare, old_resources = android_robolectric.prepare, android_robolectric.compile_resources
        old_subprocess = android_robolectric.subprocess
        for binding in (plan['evaluatorInputs'] + [plan['derivedEvaluator']] +
                        plan['entrypointBindings'] + plan['configuredEvaluatorInputs']):
            expected = {key: binding[key] for key in ('path', 'bytes', 'sha256')}
            if record(Path(binding['path'])) != expected:
                raise ValueError('Frozen candidate/evaluator preparation input changed')
        config = copy.deepcopy(plan['configurationRecipe'])
        # WYSIWYG configure generated a final annotation-only evaluator; bind that too.
        for filename in config['evaluatorSources']:
            if not Path(filename).is_file():
                raise ValueError('Configured evaluator input absent')
        with mechanics.wall_deadline(max(0.001, deadline - time.monotonic())), \
                core.bounded_file_lock(Path('/tmp/long-term-benchmark-android-full-build.lock'), deadline,
                                       'Task11 SDK leaf shared heavy queue'), \
                core.bounded_file_lock(ROOT / 'state_tests/runtime/android/.build.lock', deadline,
                                       'Task11 SDK leaf runtime lock'):
            core.require_build_space()
            if shutil.which('mvn') is None:
                raise ValueError('Existing Maven executable required; implicit distribution installation disabled')
            with mechanics.bound_git_snapshot(source, evidence / 'snapshot') as (control, snapshot), \
                    mechanics.patched_candidate(control, source):
                module_spec = importlib.util.spec_from_file_location('task11_leaf_whole_file_closure',
                                                                   TASK / 'navigation/source_closure.py')
                module = importlib.util.module_from_spec(module_spec)
                module_spec.loader.exec_module(module)
                config['sources'] = module.closure(control, snapshot['snapshotTree'], config['entrypoints'])
                config['offlineDependencies'] = True
                configuration = evidence / 'runtime.config.json'
                configuration.write_text(json.dumps(config, indent=2) + '\n')
                jna = TASK / 'messages/.native/jna-5.17.0.jar'
                if not jna.is_file():
                    raise ValueError('Desktop JNA cache unavailable; no download or Rust build is permitted here')
                def environment(configuration, work):
                    value = old_prepare(configuration, work)
                    value['jars'] = [jna] + [p for p in value['jars'] if not p.name.startswith('jna-')]
                    value['jvmArgs'] += [
                        f'-Druntime.contract.path={ROOT / "benchmark_tasks/11_room_upgrade_navigation/transitions.json"}',
                        f'-Druntime.rendered.output={evidence / "rendered"}',
                    ]
                    return value
                android_robolectric.prepare = environment
                android_robolectric.compile_resources = compile_resources
                android_robolectric.subprocess = BoundedProcesses()
                budget = deadline - time.monotonic()
                if budget <= 0:
                    raise TimeoutError('Task11 queue/closure exhausted the overall deadline')
                raw_path = evidence / 'runtime.raw.json'
                raw = android_robolectric.run_slice('11_room_upgrade_navigation', 'agent', control,
                    TASK / 'sdk_leaf_v1', configuration, raw_path, budget)
                result.update(runtimeCompile=raw.get('runtimeCompile', {'status': 'not_run'}),
                              raw=record(raw_path), sourceSnapshot=snapshot,
                              runtimeConfiguration=record(configuration), desktopJna=record(jna),
                              observations=raw.get('observations', []), reason=raw.get('error'))
                result['status'] = 'diagnostic_completed' if raw.get('status') == 'passed' else 'not_scored'
    except Exception as error:
        result.update(status='not_scored', reason=f'{type(error).__name__}: {error}')
    finally:
        if android_robolectric is not None and old_subprocess is not None:
            android_robolectric.prepare, android_robolectric.compile_resources = old_prepare, old_resources
            android_robolectric.subprocess = old_subprocess
        result['elapsedSeconds'] = timeout - max(0, deadline - time.monotonic())
        result['frozenPreparationUnchanged'] = record(preparation) == preparation_binding
        output.write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source', type=Path)
    mode.add_argument('--execute-prepared', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resource-clear-reviewed', action='store_true')
    parser.add_argument('--timeout', type=float, default=3600)
    args = parser.parse_args()
    if args.execute_prepared:
        result = execute_prepared(args.execute_prepared, args.output,
            resource_clear_reviewed=args.resource_clear_reviewed, timeout=args.timeout)
    else:
        result = prepare(args.source, args.output)
    print(json.dumps({'output': str(args.output), 'runtimeCompile': result['runtimeCompile'], 'semanticScore': None}))


if __name__ == '__main__':
    main()
