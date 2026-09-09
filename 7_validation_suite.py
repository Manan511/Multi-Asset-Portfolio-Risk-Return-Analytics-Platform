"""
Phase 4B: Number-Traceability Validation Suite
Multi-Asset Portfolio Risk & Return Analytics Platform

Generates a narrative for every quarter the pipeline has metrics for, then checks
each one for fabricated figures: every number in the narrative must trace back to
the metrics dict it was generated from.

This is the check that decides whether a narrative can be published as-is or has
to be marked "needs review". The pass rate it prints is the real, measured number
quoted in the README — rerun it to reproduce or update that figure.

Usage:
    python 7_validation_suite.py             # every available quarter
    python 7_validation_suite.py --limit 10  # first N quarters only
    python 7_validation_suite.py --no-write  # don't write report files
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import metrics_collector as mc
from llm_client import NarrativeClient
from narrative_generator import REPORTS_DIR, generate_report
from narrative_prompt import PROMPT_VERSION


RESULTS_FILE = REPORTS_DIR / 'validation_results.json'


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--limit', type=int, default=None,
                   help='only run the first N quarters')
    p.add_argument('--no-write', action='store_true',
                   help='skip writing per-quarter report files')
    return p.parse_args()


def main() -> int:
    args = parse_args()

    metric_sets = mc.collect_all()
    if not metric_sets:
        sys.exit('No metric sets available. Run 1_data_extraction.py first.')
    if args.limit:
        metric_sets = metric_sets[:args.limit]

    client = NarrativeClient()

    print(f'Number-traceability validation — {len(metric_sets)} metric sets')
    print(f'Model: {client.model} ({client.provider}) · prompt {PROMPT_VERSION}\n')

    rows = []

    for i, metrics in enumerate(metric_sets, 1):
        period = metrics['period']
        try:
            narrative, result = generate_report(
                metrics, client=client, write_files=not args.no_write
            )
        except Exception as exc:                      # noqa: BLE001 — report, don't abort the sweep
            print(f'{i:>3}. {period:<9} ERROR  {exc}')
            rows.append({'period': period, 'error': str(exc)})
            continue

        flag = '✓ clean' if result.passed else '✗ NEEDS REVIEW'
        print(f'{i:>3}. {period:<9} {flag:<16} '
              f'{len(result.numbers_found):>2} figures · {result.word_count:>3} words')

        if result.untraceable:
            print(f'      untraceable: {result.untraceable}')
            print(f'      narrative:   {narrative}')

        rows.append({
            'period': period,
            'passed': result.passed,
            'numbers_found': result.numbers_found,
            'untraceable': result.untraceable,
            'word_count': result.word_count,
            'narrative': narrative,
        })

    report_summary(rows)

    REPORTS_DIR.mkdir(exist_ok=True)
    RESULTS_FILE.write_text(json.dumps({
        'run_at': datetime.now().isoformat(timespec='seconds'),
        'model': client.model,
        'provider': client.provider,
        'prompt_version': PROMPT_VERSION,
        'results': rows,
    }, indent=2) + '\n')
    print(f'\nFull results: {RESULTS_FILE}')

    return 0


def report_summary(rows: list) -> None:
    scored = [r for r in rows if 'passed' in r]
    if not scored:
        print('\nNo narratives were generated.')
        return

    clean = [r for r in scored if r['passed']]
    flagged = [r for r in scored if not r['passed']]
    over_limit = [r for r in scored if r['word_count'] >= 120]

    print('\n' + '─' * 72)
    print(f'Metric sets generated : {len(scored)}')
    print(f'Passed cleanly        : {len(clean)}')
    print(f'Flagged for review    : {len(flagged)}')
    print(f'Traceability pass rate: {len(clean) / len(scored):.1%}')
    print(f'Under 120 words       : {len(scored) - len(over_limit)}/{len(scored)}')

    if flagged:
        print('\nFlagged quarters:')
        for r in flagged:
            print(f'  {r["period"]}: {r["untraceable"]}')

    errors = [r for r in rows if 'error' in r]
    if errors:
        print(f'\nErrored: {len(errors)} ({", ".join(r["period"] for r in errors)})')
    print('─' * 72)


if __name__ == '__main__':
    sys.exit(main())
