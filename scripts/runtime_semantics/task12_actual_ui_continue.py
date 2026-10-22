"""Resume only the storage-blocked exact candidate; never rerun valid controls."""

import argparse
import copy
from pathlib import Path
import shutil
import tempfile
import time

from . import task12_actual_ui_protocol as actual
from . import task12_13_formal_core as core
from scripts.run_runtime_transition_matrix import validate_report


def run(batch, run_root):
    batch, run_root = batch.resolve(), run_root.resolve()
    prior = core.load(batch / 'protocol.json')
    deadline_epoch = prior['sharedEpisodeDeadlineEpoch']
    remaining = deadline_epoch - time.time()
    actual.require(0 < remaining <= 3600, 'original shared repair deadline exhausted')
    deadline, started = time.monotonic() + remaining, time.monotonic()
    root = batch / 'admitted'
    actual.require(not root.exists(), 'refusing existing continuation audit')
    root.mkdir()
    record = {'nativeProtocol': actual.PROTOCOL, 'readyCandidate': False, 'reports': [],
        'newModelCall': False, 'reusedActualSourceBoundControls': True,
        'newControlDeviceExecution': False, 'originalDeadlineEpoch': deadline_epoch,
        'remainingBudgetAtStart': remaining, 'previousProtocol': core.file_record(batch / 'protocol.json')}
    temporary = Path(tempfile.mkdtemp(prefix='ltb-task12-actual-candidate-resume-'))
    source = temporary / 'candidate'
    try:
        changed = []
        protected = core.load(batch / 'protected-inputs.json')
        allowed = {str(run_root / name) for name in ('eval_manifest.json', 'eval_manifest.partial.json')}
        for item in protected:
            now = core.file_record(Path(item['path']))
            if now != item:
                changed.append({'before': item, 'after': now})
                actual.require(item['path'] in allowed, 'frozen task input or evaluator changed')
        record['protectedAggregateChanges'] = changed
        record['originalBroadProtectionResult'] = prior['protectedOriginalsUnchanged']
        record['taskSpecificFrozenInputsAndHelpersUnchanged'] = True
        contract = core.load(actual.CONTRACT)
        for label, counts in (('base', (0, 10, 0)), ('final', (10, 0, 0)),
                              ('negative', (0, 10, 0)), ('positive', (10, 0, 0))):
            original = batch / label / 'runtime.json'
            report = core.load(original)
            proof = actual.validate_report_evidence(report, contract, deadline=deadline)
            actual.require(tuple(proof['counts'][k] for k in ('passed', 'failed', 'notScored')) == counts,
                           'retained actual control no longer valid')
            target = root / label / 'runtime.json'
            core.write(target, report)
            record['reports'].append({'label': label, 'reportPath': str(target),
                'retainedActualOriginal': core.file_record(original), 'counts': proof['counts'],
                'newDeviceExecution': False, 'publicPassed': False})
        budget = core.load(run_root / 'reports/arkts_12_report_room_execution-budget.json')
        old_path = run_root / 'reports/arkts_12_report_room_agent.json'
        old = core.load(old_path)
        actual.replay.reconstruct(budget, source, root)
        path = root / 'model/runtime.json'
        try:
            model = actual.evaluate(task=actual.specification(), platform='arkts', source=source,
                role='agent', output=path, deadline=deadline, serial='127.0.0.1:5555')
        finally:
            core.write(path.parent / 'cleanup.json', core.cleanup_artifacts(path.parent))
        model['provenance']['runtimeEvidence']['currentCleanup'] = core.file_record(path.parent / 'cleanup.json')
        core.write(path, model)
        proof = actual.validate_report_evidence(model, contract, deadline=deadline)
        record['reports'].append({'label': 'model', 'reportPath': str(path), 'counts': proof['counts'],
                                  'newDeviceExecution': True, 'publicPassed': False})
        bundle = {'nativeProtocol': actual.PROTOCOL, 'contract': core.file_record(actual.CONTRACT),
            'producerHashes': [core.file_record(p) for p in (actual.FACTS, actual.RUNNER, Path(actual.__file__))],
            'sourceParameterizedControls': {}, 'episodeDeadlineEpoch': deadline_epoch,
            'retainedActualControlReuse': 'Same source inventories, producer hashes, canonical and device evidence; no retained report relabeled as a new execution.'}
        for item in record['reports']:
            report = core.load(Path(item['reportPath']))
            evidence = report['provenance']['runtimeEvidence']
            bundle['sourceParameterizedControls'][item['label']] = {'reportPath': item['reportPath'],
                **{key: evidence[key] for key in ('raw', 'sourceInventory', 'build', 'currentCleanup')}}
        bundle_path = root / 'admission-bundle.json'
        core.write(bundle_path, bundle)
        for item in record['reports']:
            report = core.load(Path(item['reportPath']))
            report['provenance']['runtimeEvidence']['admissionBundle'] = core.file_record(bundle_path)
            core.write(Path(item['reportPath']), report)
        for item in record['reports']:
            try:
                validate_report(core.load(Path(item['reportPath'])), contract)
                item['publicPassed'] = True
            except Exception as error:
                item['publicError'] = f'{type(error).__name__}: {error}'
        formal = copy.deepcopy(core.load(path))
        formal['compile'], formal['codeGeneration'] = old['compile'], old['codeGeneration']
        formal['calibration'] = {'passed': True, 'base': record['reports'][0]['counts'],
                                 'final': record['reports'][1]['counts']}
        formal['semanticReplay'] = {'originalReport': core.file_record(old_path), 'newModelCall': False,
            'reconstruction': core.file_record(root / 'reconstruction.json'), 'originalTimingReplaced': False,
            'storageProtectedContinuation': True, 'controlsReusedNotNewRuntime': True}
        formal['publication'] = {'eligible': False, 'reason': 'Pending independent public admission and aggregate-change review'}
        core.write(root / 'agent.replay.json', formal)
        record['formalReport'] = core.file_record(root / 'agent.replay.json')
        record['allPublicPassed'] = all(item['publicPassed'] for item in record['reports'])
        record['requiresAggregateChangeReview'] = bool(changed)
        record['readyCandidate'] = record['allPublicPassed'] and not changed
    except Exception as error:
        record['error'] = f'{type(error).__name__}: {error}'
    finally:
        files = [core.file_record(p) for p in sorted(temporary.rglob('*')) if p.is_file()]
        core.write(root / 'source-cleanup.json', {'allOwnedWorkflowFinished': True, 'source': str(temporary),
            'files': files, 'fileCount': len(files), 'bytes': sum(item['bytes'] for item in files)})
        shutil.rmtree(temporary)
        record['elapsedSeconds'] = time.monotonic() - started
        record['finishedBeforeOriginalDeadline'] = time.monotonic() < deadline and time.time() < deadline_epoch
        record['readyCandidate'] = record['readyCandidate'] and record['finishedBeforeOriginalDeadline']
        core.write(root / 'continuation.json', record)
    print({k: record.get(k) for k in ('readyCandidate', 'allPublicPassed', 'error', 'elapsedSeconds')}, flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--run-root', type=Path, required=True)
    raise SystemExit(0 if run(**vars(parser.parse_args()))['readyCandidate'] else 2)
