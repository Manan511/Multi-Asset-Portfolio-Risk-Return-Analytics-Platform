"""
AI Narrative Layer — Prompt Design
Multi-Asset Portfolio Risk & Return Analytics Platform

The prompt lives in its own module so it can be iterated on independently of the
generation/validation code, and so "before/after" prompt versions can be diffed.

Nothing in this file computes a metric. The prompt only ever narrates the
already-computed numbers handed to it in `metrics_summary`.
"""

import json


# ── System prompt ────────────────────────────────────────────────────────────
# Kept byte-stable so it can be cached across calls (prompt caching is a prefix
# match — see generate_narrative()).

SYSTEM_PROMPT = """You are a financial analyst writing a short commentary for a portfolio \
risk & return report. You will be given a JSON object containing already-computed \
portfolio metrics for this period.

Write a 3-5 sentence narrative summary explaining what these numbers mean, in the \
style of a professional but accessible analyst note.

Rules:
- Only reference numbers that appear in the provided data. Never invent, estimate, \
or round in a way that changes the meaning of a figure.
- If the data shows a metric worsened, say so plainly — do not sugarcoat a decline \
in performance.
- Do not speculate about *why* something changed unless the data itself indicates a \
specific driver (e.g. a correlation change is a valid thing to point to as a driver \
of volatility; do not speculate about external market events not present in the data).
- Keep it under 120 words so it fits as a text box alongside a dashboard.
- Output the narrative prose only. No headings, no bullet points, no preamble."""


# ── User-turn template ───────────────────────────────────────────────────────

USER_TEMPLATE = """Metrics data:
{metrics_summary}"""


def build_user_message(metrics_summary: dict) -> str:
    """Render the metrics dict into the user turn of the prompt.

    `sort_keys=True` keeps serialization deterministic — an unstable key order
    would silently defeat prompt caching on repeated runs.
    """
    return USER_TEMPLATE.format(
        metrics_summary=json.dumps(metrics_summary, indent=2, sort_keys=True)
    )


# ── Prompt version log ───────────────────────────────────────────────────────
#
# v1 — the spec prompt verbatim (see build spec section 4).
# v2 — adds the final rule: "Output the narrative prose only. No headings, no
#      bullet points, no preamble." A heading or preamble is wasted space in a
#      Power BI text box, and a heading that restates the period ("Q3 2026")
#      injects digits into the text that the traceability validator then has to
#      account for. Set PROMPT_VERSION back to "v1" and drop that rule from
#      SYSTEM_PROMPT to reproduce the baseline for a before/after comparison.
#
PROMPT_VERSION = "v2"
