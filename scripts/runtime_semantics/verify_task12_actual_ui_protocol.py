"""Independent public admission check for one current actual-native batch."""

import argparse
from pathlib import Path

from . import task12_13_formal_core as core
from . import task12_actual_ui_protocol as actual
from scripts.run_runtime_transition_matrix import validate_report


def verify(batch):
    batch = batch.resolve()
    contract = core.load(actual.CONTRACT)
    results = []
    for label in ('base', 'final', 'negative', 'positive', 'model', 'formal'):
        path = batch / label / 'runtime.json' if label != 'formal' else batch / 'agent.replay.json'
        row = {'label': label, 'reportPath': str(path), 'publicPassed': False}
        try:
            report = core.load(path)
            row['report'] = core.file_record(path)
            row['proof'] = actual.validate_report_evidence(report, contract)
            validate_report(report, contract)
            row['publicPassed'] = True
        except Exception as error:
            row['error'] = f'{type(error).__name__}: {error}'
        results.append(row)
    return {'nativeProtocol': actual.PROTOCOL, 'contract': core.file_record(actual.CONTRACT),
            'batch': str(batch), 'allPublicPassed': all(row['publicPassed'] for row in results),
            'reports': results, 'oldProjectionReportsAccepted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing existing independent audit output')
    result = verify(args.batch)
    core.write(args.output, result)
    print({key: result[key] for key in ('batch', 'allPublicPassed')})
    raise SystemExit(0 if result['allPublicPassed'] else 2)
