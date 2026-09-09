"""
AI Narrative Report Generator
Multi-Asset Portfolio Risk & Return Analytics Platform

Turns an already-computed `metrics_summary` dict into a short analyst commentary,
then checks every number in that commentary back against the input before the
output is allowed to ship clean.

Grounding contract:
    * This module never touches a price series and never computes a metric.
      It receives numbers that the SQL view / DAX measures already defined
      (see metrics_collector.py) and asks the model to narrate them.
    * Every digit the model writes must be traceable to the input dict. An
      untraceable digit does not silently ship — the narrative is returned with
      needs_review=True and the offending figures listed.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from llm_client import NarrativeClient
from narrative_prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_message,
)


REPORTS_DIR = Path('reports')


# ── Generation ───────────────────────────────────────────────────────────────

def generate_narrative(metrics_summary: dict, client: NarrativeClient = None) -> str:
    """Ask the model to narrate one metrics dict, and return the prose.

    The model is handed the metrics and nothing else — no prices, no history —
    so there is nothing here for it to recompute.
    """
    client = client or NarrativeClient()
    return client.complete(SYSTEM_PROMPT, build_user_message(metrics_summary))


# ── Number-traceability validation ───────────────────────────────────────────

# Matches integers and decimals, with an optional leading sign, and ignores
# thousands separators. The sign is captured because a drawdown legitimately
# reads as either "-12.4%" or "a drawdown of 12.4%".
NUMBER_RE = re.compile(r'-?\d+(?:,\d{3})*(?:\.\d+)?')

# Figures a professional note uses as English rather than as data. These are not
# treated as claims about the portfolio, so they are not required to be traceable.
STOPWORD_NUMBERS = {0.0, 1.0, 2.0, 3.0, 4.0}

TOLERANCE = 1e-9


@dataclass
class ValidationResult:
    """Outcome of checking one narrative against the metrics it came from."""
    passed: bool
    numbers_found: list = field(default_factory=list)
    untraceable: list = field(default_factory=list)
    word_count: int = 0

    @property
    def status(self) -> str:
        return 'clean' if self.passed else 'needs review'


def _extract_numbers(text: str) -> list:
    """Every numeric literal in the narrative, as floats."""
    return [float(m.group().replace(',', '')) for m in NUMBER_RE.finditer(text)]


def traceable_values(metrics_summary: dict) -> set:
    """The set of numbers the narrative is permitted to state.

    Walks the whole input dict. Numeric fields contribute their own value;
    strings contribute any digits embedded in them, so a period label like
    "Q3 2026" or a drawdown date like "Mar 2026" is traceable too.

    A negative source value also licenses its unsigned form: an analyst writing
    "a maximum drawdown of 12.4%" is quoting -12.4, not inventing a figure. The
    reverse is not allowed — a positive source value never licenses a negative.
    """
    allowed = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, bool):
            pass
        elif isinstance(node, (int, float)):
            value = float(node)
            allowed.add(value)
            if value < 0:
                allowed.add(abs(value))
        elif isinstance(node, str):
            for m in NUMBER_RE.finditer(node):
                allowed.add(float(m.group().replace(',', '')))

    walk(metrics_summary)
    return allowed


def validate_narrative(narrative: str, metrics_summary: dict) -> ValidationResult:
    """Confirm every number in `narrative` traces back to `metrics_summary`."""
    allowed = traceable_values(metrics_summary)
    found = _extract_numbers(narrative)

    untraceable = [
        n for n in found
        if n not in STOPWORD_NUMBERS
        and not any(abs(n - a) <= TOLERANCE for a in allowed)
    ]

    return ValidationResult(
        passed=not untraceable,
        numbers_found=found,
        untraceable=untraceable,
        word_count=len(narrative.split()),
    )


# ── End-to-end: generate, validate, persist ──────────────────────────────────

def _slug(period: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', period).strip('_')


def generate_report(metrics_summary: dict,
                    client: NarrativeClient = None,
                    write_files: bool = True,
                    reports_dir: Path = REPORTS_DIR) -> tuple:
    """Generate one narrative, validate it, and write the traceable pair to disk.

    Returns (narrative, ValidationResult). The metrics JSON is saved alongside
    the markdown so any published figure can be traced back to the exact input
    it was generated from.
    """
    client = client or NarrativeClient()
    narrative = generate_narrative(metrics_summary, client=client)
    result = validate_narrative(narrative, metrics_summary)

    if not write_files:
        return narrative, result

    reports_dir.mkdir(exist_ok=True)
    slug = _slug(metrics_summary.get('period', 'report'))

    (reports_dir / f'metrics_{slug}.json').write_text(
        json.dumps(metrics_summary, indent=2, sort_keys=True) + '\n'
    )
    (reports_dir / f'report_{slug}.md').write_text(
        _render_markdown(metrics_summary, narrative, result, client)
    )

    return narrative, result


def _render_markdown(metrics_summary: dict, narrative: str, result: ValidationResult,
                     client: NarrativeClient = None) -> str:
    period = metrics_summary.get('period', 'Portfolio')
    model_label = f'{client.model} ({client.provider})' if client else 'unknown model'
    lines = [
        f'# Portfolio Commentary — {period}',
        '',
        narrative,
        '',
        '---',
        '',
        '## Provenance',
        '',
        f'- **Generated:** {date.today().isoformat()}',
        f'- **Model:** {model_label} · prompt {PROMPT_VERSION}',
        f'- **Source metrics:** `metrics_{_slug(period)}.json`',
        f'- **Word count:** {result.word_count} (Power BI text box target: < 120)',
        f'- **Number traceability:** {result.status} '
        f'({len(result.numbers_found)} figures checked)',
    ]

    if result.untraceable:
        lines += [
            '',
            '> **⚠️ Needs review.** These figures could not be traced back to the '
            'source metrics and must be checked before publication: '
            + ', '.join(str(n) for n in result.untraceable),
        ]

    lines += [
        '',
        '## Metrics narrated',
        '',
        '```json',
        json.dumps(metrics_summary, indent=2, sort_keys=True),
        '```',
        '',
    ]
    return '\n'.join(lines)


# ── Convenience: the Power BI text-box form ──────────────────────────────────

def powerbi_text_box(narrative: str) -> str:
    """The narrative with nothing around it, ready to paste into a text box."""
    return ' '.join(narrative.split())


if __name__ == '__main__':
    # Sample metrics from the build spec — lets the module be exercised end to
    # end without a database or a price file.
    SAMPLE = {
        'period': 'Q3 2026',
        'volatility': {'current': 18.2, 'previous': 14.6, 'unit': '%'},
        'sharpe_ratio': {'current': 0.94, 'previous': 1.02},
        'max_drawdown': {'value': -12.4, 'unit': '%', 'date_range': 'Mar 2026'},
        'correlation_changes': [
            {'asset_pair': 'Tech-Energy', 'previous': 0.31, 'current': 0.58}
        ],
        'rolling_returns': {'3mo': 6.1, '6mo': 11.4, '12mo': 15.8, 'unit': '%'},
    }

    client = NarrativeClient()
    print(f'Using {client!r}\n')
    text, validation = generate_report(SAMPLE, client=client)
    print(text)
    print()
    print(f'[{validation.status}] {validation.word_count} words, '
          f'{len(validation.numbers_found)} figures checked')
    if validation.untraceable:
        print(f'  untraceable: {validation.untraceable}')
