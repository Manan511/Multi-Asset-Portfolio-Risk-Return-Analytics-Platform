"""
Phase 4A: AI Narrative Report — single quarter
Multi-Asset Portfolio Risk & Return Analytics Platform

Runs after the existing metric calculations. Reads the metrics the pipeline has
already computed, asks the model to narrate them, validates every number in the
result against the input, and writes the report/metrics pair to reports/.

Usage:
    python 6_generate_narrative_report.py              # latest quarter
    python 6_generate_narrative_report.py "Q2 2026"    # a specific quarter
    python 6_generate_narrative_report.py --sample     # spec sample, no price file needed
"""

import sys

import metrics_collector as mc
from llm_client import NarrativeClient
from narrative_generator import generate_report, powerbi_text_box


# The worked example from the build spec — useful for exercising the module
# without a price file or a database.
SAMPLE_METRICS = {
    'period': 'Q3 2026',
    'volatility': {'current': 18.2, 'previous': 14.6, 'unit': '%'},
    'sharpe_ratio': {'current': 0.94, 'previous': 1.02},
    'max_drawdown': {'value': -12.4, 'unit': '%', 'date_range': 'Mar 2026'},
    'correlation_changes': [
        {'asset_pair': 'Tech-Energy', 'previous': 0.31, 'current': 0.58}
    ],
    'rolling_returns': {'3mo': 6.1, '6mo': 11.4, '12mo': 15.8, 'unit': '%'},
}


def pick_metrics(args) -> dict:
    if '--sample' in args:
        return SAMPLE_METRICS

    all_metrics = mc.collect_all()
    if not all_metrics:
        sys.exit('No quarters available. Run 1_data_extraction.py first.')

    wanted = next((a for a in args if not a.startswith('-')), None)
    if wanted is None:
        return all_metrics[-1]

    for m in all_metrics:
        if m['period'].lower() == wanted.lower():
            return m

    sys.exit(f'Quarter {wanted!r} not found. Available: '
             + ', '.join(m['period'] for m in all_metrics))


def main() -> int:
    metrics = pick_metrics(sys.argv[1:])
    period = metrics['period']

    client = NarrativeClient()
    print(f'Generating narrative for {period} using {client.model} '
          f'({client.provider}) ...\n')
    narrative, result = generate_report(metrics, client=client)

    print(narrative)
    print()
    print('─' * 72)
    print(f'Validation   : {result.status}  '
          f'({len(result.numbers_found)} figures checked)')
    print(f'Word count   : {result.word_count}  (Power BI text box target: < 120)')

    if result.untraceable:
        print(f'Untraceable  : {result.untraceable}')
        print('               → flagged as NEEDS REVIEW, not shipped clean.')

    print()
    print('── Power BI text box ' + '─' * 51)
    print(powerbi_text_box(narrative))
    print('─' * 72)
    print(f'\nSaved: reports/report_{period.replace(" ", "_")}.md'
          f' + reports/metrics_{period.replace(" ", "_")}.json')

    return 1 if result.untraceable else 0


if __name__ == '__main__':
    sys.exit(main())
