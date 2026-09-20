"""Strict experiment configuration and incremental multi-run execution."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .cases import Case, Suite, load_suite
from .config import DEFAULT_PROMPT, DEFAULT_SUITE, ConfigError, load_prompt
from .evaluator import evaluate_document, write_evaluation
from .providers import get_provider
from .report import render_markdown
from .runner import run_suite, write_results

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
        "xai": "XAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}
ROOT_FIELDS = {"experiment_id", "suite_id", "prompt_id", "case_ids", "case_limit",
               "providers", "repeat_count", "timeout", "max_output_tokens", "mode"}
PROVIDER_FIELDS = {"provider", "model", "api_type", "output_constraint", "temperature",
                   "reasoning_effort", "api_key_env", "mock_mode"}
SMOKE_CASE_LIMIT = 3


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    suite_id: str
    prompt_id: str
    case_ids: Optional[List[str]]
    case_limit: Optional[int]
    providers: List[Dict[str, Any]]
    repeat_count: int
    timeout: float
    max_output_tokens: int
    mode: str

def load_experiment(path: Path) -> Experiment:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read experiment config {path}: {exc}")
    if not isinstance(doc, dict):
        raise ConfigError("experiment config must be a JSON object")
    unknown = sorted(set(doc) - ROOT_FIELDS)
    if unknown:
        raise ConfigError(f"unknown experiment fields: {', '.join(unknown)}")
    required = {"experiment_id", "providers"}
    missing = sorted(required - set(doc))
    if missing:
        raise ConfigError(f"missing experiment fields: {', '.join(missing)}")
    experiment_id = _safe_id(doc["experiment_id"], "experiment_id")
    suite_id = _safe_id(doc.get("suite_id", DEFAULT_SUITE), "suite_id")
    prompt_id = _safe_id(doc.get("prompt_id", DEFAULT_PROMPT), "prompt_id")
    case_ids = doc.get("case_ids")
    if case_ids is not None:
        if not isinstance(case_ids, list) or not case_ids or not all(isinstance(x, str) for x in case_ids):
            raise ConfigError("case_ids must be a non-empty array of strings")
        case_ids = [_safe_id(x, "case id") for x in case_ids]
        if len(set(case_ids)) != len(case_ids):
            raise ConfigError("case_ids must not contain duplicates")
    case_limit = _optional_int(doc.get("case_limit"), "case_limit", minimum=1)
    if case_ids is not None and case_limit is not None:
        raise ConfigError("use case_ids or case_limit, not both")
    repeat_count = _int(doc.get("repeat_count", 1), "repeat_count", 1, 100)
    timeout = _number(doc.get("timeout", 120), "timeout", 0.1, 3600)
    max_tokens = _int(doc.get("max_output_tokens", 2048), "max_output_tokens", 1, 1_000_000)
    mode = doc.get("mode", "reviewed")
    if mode not in ("reviewed", "smoke"):
        raise ConfigError("mode must be 'reviewed' or 'smoke'")
    providers = doc["providers"]
    if not isinstance(providers, list) or not providers:
        raise ConfigError("providers must be a non-empty array")
    checked = [_validate_provider(p) for p in providers]
    return Experiment(experiment_id, suite_id, prompt_id, case_ids, case_limit, checked,
                      repeat_count, timeout, max_tokens, mode)


def _validate_provider(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise ConfigError("each provider entry must be an object")
    unknown = sorted(set(entry) - PROVIDER_FIELDS)
    if unknown:
        raise ConfigError(f"unknown provider fields: {', '.join(unknown)}")
    name = entry.get("provider")
    if name not in ("mock", "openai", "anthropic", "xai", "deepseek"):
        raise ConfigError(f"unknown provider {name!r}")
    model = entry.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ConfigError(f"provider {name} requires an explicit model")
    result = dict(entry)
    result["model"] = model.strip()
    if result["model"].startswith("REPLACE_"):
        raise ConfigError(f"provider {name} model placeholder must be replaced with a documented model id")
    if "temperature" in entry:
        result["temperature"] = _number(entry["temperature"], "temperature", 0, 2)
    constraint = entry.get("output_constraint")
    allowed = {
        "mock": (None, "native_json"),
        "openai": ("json_schema", "json_object", "prompt_only"),
        "anthropic": ("json_schema", "prompt_only"),
        "xai": ("json_schema", "json_object", "prompt_only"),
        "deepseek": ("json_object", "prompt_only"),
    }[name]
    if constraint not in allowed:
        raise ConfigError(f"provider {name} does not support output_constraint {constraint!r}")
    if name != "openai" and "api_type" in entry:
        raise ConfigError(f"api_type is not supported for provider {name}")
    if name == "openai" and entry.get("api_type", "responses") not in ("responses", "chat.completions"):
        raise ConfigError("OpenAI api_type must be responses or chat.completions")
    effort = entry.get("reasoning_effort")
    efforts = {"openai": ("low", "medium", "high", "xhigh", "max"),
               "xai": ("low", "medium", "high", "xhigh"),
               "deepseek": ("none", "low", "high", "max")}
    if effort is not None and (name not in efforts or effort not in efforts[name]):
        raise ConfigError(f"provider {name} does not support reasoning_effort {effort!r}")
    if name == "deepseek" and effort is None:
        raise ConfigError("provider deepseek requires explicit reasoning_effort (use 'none' to disable thinking)")
    if name == "deepseek" and effort not in (None, "none") and entry.get("temperature", 0) != 0:
        raise ConfigError("DeepSeek temperature is unsupported in thinking mode")
    if name == "openai" and effort is not None and entry.get("temperature", 0) != 0:
        raise ConfigError("OpenAI temperature is not supported with explicit reasoning_effort")
    expected_key = KEYS.get(name)
    if expected_key:
        if entry.get("api_key_env") != expected_key:
            raise ConfigError(f"provider {name} must set api_key_env to {expected_key}")
    elif "api_key_env" in entry:
        raise ConfigError("mock must not declare api_key_env")
    if name != "mock" and "mock_mode" in entry:
        raise ConfigError(f"mock_mode is not supported for provider {name}")
    return result


def preflight(experiment: Experiment, *, root: Optional[Path], max_requests: int,
              require_keys: bool) -> Tuple[Suite, Sequence[Case], List[str]]:
    if max_requests < 1:
        raise ConfigError("--max-requests must be at least 1")
    suite = load_suite(experiment.suite_id, root=root)
    load_prompt(experiment.prompt_id, root=root)
    if experiment.case_ids:
        try:
            cases = [suite.get(case_id) for case_id in experiment.case_ids]
        except KeyError as exc:
            raise ConfigError(str(exc))
    else:
        cases = list(suite.cases[:experiment.case_limit])
    count = len(cases) * len(experiment.providers) * experiment.repeat_count
    if count > max_requests:
        raise ConfigError(f"experiment plans {count} requests, exceeding --max-requests {max_requests}")
    paid = any(p["provider"] != "mock" for p in experiment.providers)
    pending = [case.id for case in cases if not case.labels_frozen]
    if paid and pending and experiment.mode != "smoke":
        raise ConfigError("paid experiments require frozen labels; use mode 'smoke' for a limited provisional run")
    if paid and experiment.mode == "smoke" and len(cases) > SMOKE_CASE_LIMIT:
        raise ConfigError(f"paid smoke experiments are limited to {SMOKE_CASE_LIMIT} cases")
    missing_keys = [p["api_key_env"] for p in experiment.providers
                    if p["provider"] != "mock" and not os.environ.get(p["api_key_env"])]
    if require_keys and missing_keys:
        raise ConfigError("missing required environment variables: " + ", ".join(sorted(set(missing_keys))))
    # Construct all providers before the first request so settings fail together.
    if require_keys:
        for entry in experiment.providers:
            _make_provider(entry, experiment)
    return suite, cases, sorted(set(missing_keys))


def run_experiment(experiment: Experiment, *, root: Optional[Path], output_root: Path,
                   max_requests: int) -> Path:
    suite, cases, _ = preflight(experiment, root=root, max_requests=max_requests, require_keys=True)
    prompt = load_prompt(experiment.prompt_id, root=root)
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = Path(output_root) / experiment.experiment_id / run_stamp
    directory.mkdir(parents=True, exist_ok=False)
    git = _git_state(root)
    manifest: Dict[str, Any] = {
        "experiment_format_version": 1, "experiment_id": experiment.experiment_id,
        "experiment_run_id": run_stamp, "created_at": _now(), "completed_at": None,
        "mode": experiment.mode, "provisional": bool([c for c in cases if not c.labels_frozen]),
        "comparative_ranking_permitted": experiment.mode == "reviewed" and all(c.labels_frozen for c in cases),
        "suite": {"id": suite.id, "version": suite.version},
        "prompt": {"id": prompt.id, "sha256": prompt.sha256},
        "repository": git, "case_fingerprints": {c.id: _case_hash(c) for c in cases},
        "repeat_count": experiment.repeat_count,
        "planned_requests": len(cases) * len(experiment.providers) * experiment.repeat_count,
        "runs": [],
    }
    _write_json(directory / "manifest.json", manifest)
    for provider_index, entry in enumerate(experiment.providers, 1):
        for repetition in range(1, experiment.repeat_count + 1):
            slug = f"{provider_index:02d}-{_safe_component(entry['provider'])}-{_safe_component(entry['model'])}-r{repetition:02d}"
            run_dir = directory / slug
            run_dir.mkdir()
            index = {"provider": entry["provider"], "requested_model": entry["model"],
                     "repetition": repetition, "status": "running", "path": slug,
                     "results": f"{slug}/results.json", "evaluation": None, "report": None,
                     "error": None}
            manifest["runs"].append(index)
            _write_json(directory / "manifest.json", manifest)
            try:
                provider = _make_provider(entry, experiment)
                document = run_suite(suite, provider, prompt, case_ids=[c.id for c in cases])
                document["run"]["experiment"] = {"id": experiment.experiment_id,
                    "experiment_run_id": run_stamp, "repetition": repetition, "mode": experiment.mode}
                document["run"]["repository"] = git
                document["run"]["case_fingerprints"] = manifest["case_fingerprints"]
                write_results(document, run_dir / "results.json")
                evaluation = evaluate_document(document, suite, root=root)
                evaluation["experiment"] = {"mode": experiment.mode,
                    "provisional": manifest["provisional"],
                    "comparative_ranking_permitted": manifest["comparative_ranking_permitted"]}
                write_evaluation(evaluation, run_dir / "evaluation.json")
                (run_dir / "report.md").write_text(render_markdown(evaluation), encoding="utf-8")
                if any(r.get("error") for r in document["responses"]):
                    run_status = "failed"
                    failures = sum(1 for r in document["responses"] if r.get("error"))
                    index["error"] = f"{failures} provider request(s) failed; see results.json"
                elif any(not r.get("valid") for r in document["responses"]):
                    run_status = "completed_with_invalid_responses"
                else:
                    run_status = "completed"
                index.update({"status": run_status,
                              "evaluation": f"{slug}/evaluation.json", "report": f"{slug}/report.md"})
            except Exception as exc:
                index.update({"status": "failed", "error": _safe_error(exc)})
            _write_json(directory / "manifest.json", manifest)
    manifest["completed_at"] = _now()
    if any(r["status"] == "failed" for r in manifest["runs"]):
        manifest["status"] = "failed"
    elif any(r["status"] != "completed" for r in manifest["runs"]):
        manifest["status"] = "completed_with_invalid_responses"
    else:
        manifest["status"] = "completed"
    _write_json(directory / "manifest.json", manifest)
    return directory


def dry_run_summary(experiment: Experiment, suite: Suite, cases: Sequence[Case],
                    missing_keys: Sequence[str], output_root: Path, max_requests: int) -> str:
    lines = [f"experiment: {experiment.experiment_id}", f"mode: {experiment.mode}",
             f"suite: {suite.id} {suite.version}", f"cases ({len(cases)}): " + ", ".join(c.id for c in cases),
             f"repeat count: {experiment.repeat_count}",
             f"planned requests: {len(cases) * len(experiment.providers) * experiment.repeat_count} (maximum {max_requests})",
             f"output: {Path(output_root) / experiment.experiment_id / '<unique-run-id>'}", "providers:"]
    for entry in experiment.providers:
        lines.append(f"  - {entry['provider']} / {entry['model']} / {entry.get('output_constraint', 'native_json')}")
    lines.append("missing credentials: " + (", ".join(missing_keys) if missing_keys else "none"))
    return "\n".join(lines)


def _make_provider(entry: Dict[str, Any], experiment: Experiment):
    kwargs: Dict[str, Any] = {"name": entry["provider"], "model": entry["model"],
        "timeout": experiment.timeout, "max_output_tokens": experiment.max_output_tokens,
        "temperature": entry.get("temperature", 0.0), "mode": entry.get("mock_mode", "heuristic")}
    for name in ("api_type", "output_constraint", "reasoning_effort"):
        if entry["provider"] == "mock":
            continue
        if name in entry:
            kwargs[name] = entry[name]
    return get_provider(**kwargs)


def _safe_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value) or value in (".", ".."):
        raise ConfigError(f"{name} must contain only letters, digits, '.', '_' or '-' and be at most 80 characters")
    return value


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)[:80]


def _int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


def _optional_int(value: Any, name: str, minimum: int) -> Optional[int]:
    return None if value is None else _int(value, name, minimum, 1_000_000)


def _number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be a number from {minimum} to {maximum}")
    return float(value)


def _case_hash(case: Case) -> str:
    canonical = json.dumps(case.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _git_state(root: Optional[Path]) -> Dict[str, Any]:
    cwd = str(root or Path.cwd())
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, text=True,
                             capture_output=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                    cwd=cwd, text=True, capture_output=True, check=True).stdout.strip())
        return {"git_sha": sha, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"git_sha": None, "dirty": None}


def _safe_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    for key in KEYS.values():
        secret = os.environ.get(key)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text[:1000]


def _write_json(path: Path, document: Dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
