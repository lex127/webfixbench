"""Locating benchmark data, prompts and (optional) pricing metadata.

WebFixBench keeps its data (suites, prompts, pricing tables) outside the Python
package so that the dataset can be read, reviewed and diffed on its own. This
module resolves those locations.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_SUITE = "php-web-v0.1"
DEFAULT_PROMPT = "review_v1"

#: Environment variables read by the benchmark. API keys are read by the
#: providers only, never logged and never written to result files.
ENV_ROOT = "WEBFIXBENCH_HOME"
ENV_PRICING = "WEBFIXBENCH_PRICING"
ENV_OPENAI_KEY = "OPENAI_API_KEY"
ENV_ANTHROPIC_KEY = "ANTHROPIC_API_KEY"


class ConfigError(RuntimeError):
    """Raised when benchmark data cannot be located or read."""


def find_root(start: Optional[Path] = None) -> Path:
    """Return the benchmark data root (the directory containing ``suites/``).

    Resolution order: ``$WEBFIXBENCH_HOME``, then the first ancestor of
    ``start`` (default: the current directory) that contains a ``suites``
    directory, then the repository root inferred from this file's location.
    """
    env_root = os.environ.get(ENV_ROOT)
    if env_root:
        root = Path(env_root).expanduser().resolve()
        if not (root / "suites").is_dir():
            raise ConfigError(f"{ENV_ROOT}={root} does not contain a 'suites' directory")
        return root

    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "suites").is_dir():
            return candidate

    # Installed from a source checkout: src/webfixbench/config.py -> repo root.
    inferred = Path(__file__).resolve().parents[2]
    if (inferred / "suites").is_dir():
        return inferred

    raise ConfigError(
        "could not locate the WebFixBench data root; run the CLI from a checkout "
        f"or set {ENV_ROOT} to the directory containing 'suites/'"
    )


def suites_dir(root: Optional[Path] = None) -> Path:
    return (root or find_root()) / "suites"


def prompts_dir(root: Optional[Path] = None) -> Path:
    return (root or find_root()) / "prompts"


@dataclass(frozen=True)
class Prompt:
    """A frozen, content-addressed prompt template."""

    id: str
    text: str
    sha256: str

    def render(self, *, case_description: str, diff: str, context: Optional[str] = None) -> str:
        return (
            self.text.replace("{{CASE_DESCRIPTION}}", case_description)
            .replace("{{CONTEXT}}", context or "(no additional context supplied)")
            .replace("{{DIFF}}", diff)
        )


def load_prompt(prompt_id: str = DEFAULT_PROMPT, root: Optional[Path] = None) -> Prompt:
    """Load a frozen prompt by id from ``prompts/<id>.txt``.

    Prompts are versioned by filename and content-addressed by SHA-256; the
    digest is recorded in every result file so a run can be tied to the exact
    prompt text that produced it.
    """
    path = prompts_dir(root) / f"{prompt_id}.txt"
    if not path.is_file():
        raise ConfigError(f"unknown prompt {prompt_id!r} (expected {path})")
    text = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Prompt(id=prompt_id, text=text, sha256=digest)


# --------------------------------------------------------------------------
# Pricing metadata (optional, user-supplied, never baked into the engine)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PricingTable:
    """Per-model token prices supplied by the user.

    Vendor prices change and go stale; the benchmark therefore ships no real
    prices. Cost is reported as ``null`` unless a pricing table is supplied via
    ``--pricing`` or ``$WEBFIXBENCH_PRICING``.
    """

    as_of: Optional[str]
    source: Optional[str]
    models: Dict[str, Dict[str, float]]

    @classmethod
    def empty(cls) -> "PricingTable":
        return cls(as_of=None, source=None, models={})

    def cost_usd(self, model: str, usage: Optional[Dict[str, Any]]) -> Optional[float]:
        """Return the estimated cost of a call, or ``None`` if not computable."""
        if not usage or model not in self.models:
            return None
        prices = self.models[model]
        input_price = prices.get("input_usd_per_1m_tokens")
        output_price = prices.get("output_usd_per_1m_tokens")
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if None in (input_price, output_price, input_tokens, output_tokens):
            return None
        return (
            float(input_tokens) * float(input_price) + float(output_tokens) * float(output_price)
        ) / 1_000_000.0


def load_pricing(path: Optional[Path] = None) -> PricingTable:
    """Load a pricing table, falling back to an empty (cost-unknown) table."""
    target = path or (Path(os.environ[ENV_PRICING]) if os.environ.get(ENV_PRICING) else None)
    if target is None:
        return PricingTable.empty()
    target = Path(target).expanduser()
    if not target.is_file():
        raise ConfigError(f"pricing table not found: {target}")
    doc = json.loads(target.read_text(encoding="utf-8"))
    models = doc.get("models", {})
    if not isinstance(models, dict):
        raise ConfigError(f"pricing table {target}: 'models' must be an object")
    return PricingTable(as_of=doc.get("as_of"), source=doc.get("source"), models=models)
