"""
LLM Backend — provider abstraction for the narrative layer
Multi-Asset Portfolio Risk & Return Analytics Platform

The narrative layer needs exactly one thing from a model provider: given a fixed
system prompt and a metrics JSON payload, return prose. That is a small enough
surface to keep provider-neutral, so the grounding and validation logic in
narrative_generator.py stays identical no matter which model produced the text.

Two backends are supported:

    gemini     — Google Gemini via the google-genai SDK   (GEMINI_API_KEY)
    anthropic  — Anthropic Claude via the anthropic SDK   (ANTHROPIC_API_KEY)

Selection order:
    1. NARRATIVE_PROVIDER, if set ("gemini" or "anthropic")
    2. whichever provider's API key is present in the environment
    3. gemini

Override the model with NARRATIVE_MODEL.

Keys are read from the environment, or from a local `.env` file (git-ignored) so
a key never has to live in a shell profile:

    GEMINI_API_KEY=...
"""

import os
from pathlib import Path


def load_dotenv(path: str = '.env') -> None:
    """Load KEY=VALUE lines from a local .env into os.environ.

    Deliberately minimal (no dependency) and non-overriding: a variable already
    set in the real environment always wins.
    """
    env_file = Path(path)
    if not env_file.is_file():
        return

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        os.environ.setdefault(key.strip(), value.strip().strip('\'"'))


load_dotenv()


DEFAULT_MODELS = {
    'gemini':    'gemini-2.5-flash',
    'anthropic': 'claude-sonnet-4-6',
}

MAX_OUTPUT_TOKENS = 1024


def resolve_provider() -> str:
    """Which backend to use for this run."""
    explicit = os.environ.get('NARRATIVE_PROVIDER', '').strip().lower()
    if explicit:
        if explicit not in DEFAULT_MODELS:
            raise ValueError(
                f'Unknown NARRATIVE_PROVIDER {explicit!r}. '
                f'Expected one of: {", ".join(DEFAULT_MODELS)}'
            )
        return explicit

    if os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY'):
        return 'gemini'
    if os.environ.get('ANTHROPIC_API_KEY'):
        return 'anthropic'
    return 'gemini'


def resolve_model(provider: str = None) -> str:
    provider = provider or resolve_provider()
    return os.environ.get('NARRATIVE_MODEL') or DEFAULT_MODELS[provider]


class NarrativeClient:
    """Thin wrapper exposing a single `complete(system, user) -> str` call.

    Constructed once per run so the underlying HTTP client (and, on Anthropic,
    the cached system-prompt prefix) is reused across every quarter.
    """

    def __init__(self, provider: str = None, model: str = None):
        self.provider = provider or resolve_provider()
        self.model = model or resolve_model(self.provider)
        self._client = None

    # ── Backends ─────────────────────────────────────────────────────────────

    def _gemini(self, system: str, user: str) -> str:
        from google import genai
        from google.genai import types

        if self._client is None:
            api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
            if not api_key:
                raise RuntimeError(
                    'No Gemini API key found. Set GEMINI_API_KEY (or GOOGLE_API_KEY).'
                )
            self._client = genai.Client(api_key=api_key)

        response = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                # Commentary on a fixed set of numbers should be reproducible;
                # there is no upside to sampling variety in a financial report.
                temperature=0.2,
            ),
        )

        text = (response.text or '').strip()
        if not text:
            raise RuntimeError(
                f'Model returned no text (finish reason: '
                f'{getattr(response.candidates[0], "finish_reason", "unknown")})'
            )
        return text

    def _anthropic(self, system: str, user: str) -> str:
        import anthropic

        if self._client is None:
            self._client = anthropic.Anthropic()

        response = self._client.messages.create(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            # The system prompt is byte-stable across every quarter in a run, so
            # it is worth caching; only the metrics JSON varies.
            system=[{
                'type': 'text',
                'text': system,
                'cache_control': {'type': 'ephemeral'},
            }],
            messages=[{'role': 'user', 'content': user}],
        )

        if response.stop_reason == 'refusal':
            raise RuntimeError(f'Model declined the request: {response.stop_details}')

        return ''.join(b.text for b in response.content if b.type == 'text').strip()

    # ── Public API ───────────────────────────────────────────────────────────

    def complete(self, system: str, user: str) -> str:
        if self.provider == 'gemini':
            return self._gemini(system, user)
        if self.provider == 'anthropic':
            return self._anthropic(system, user)
        raise ValueError(f'Unsupported provider: {self.provider}')

    def __repr__(self) -> str:
        return f'NarrativeClient(provider={self.provider!r}, model={self.model!r})'
