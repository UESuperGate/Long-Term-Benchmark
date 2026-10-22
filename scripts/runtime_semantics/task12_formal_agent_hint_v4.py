"""Private Task12 hint-profile successor; not the central/public default."""

import argparse
from pathlib import Path

from .task12_merged_pipeline_hint_v4 import score


dispatch = score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--base-source', type=Path, required=True)
    parser.add_argument('--final-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    # Parent-only private receipt: never supply this command to the model.
    parser.add_argument('--control-receipt', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--device-serial', default='127.0.0.1:5555')
    parser.add_argument('--execute-after-coordinator-release', action='store_true', required=True)
    args = parser.parse_args()
    result = score(platform='arkts', source=args.source, base_source=args.base_source,
        final_source=args.final_source, output=args.output, timeout=args.timeout,
        compile_passed=None, control_receipt=args.control_receipt,
        device_serial=args.device_serial, coordinator_release=args.execute_after_coordinator_release)
    return 0 if result and result.get('publication', {}).get('eligible') is True else 2


if __name__ == '__main__':
    raise SystemExit(main())
