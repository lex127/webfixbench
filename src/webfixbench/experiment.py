"""Strict experiment configuration and incremental multi-run execution."""

from __future__ import annotations

import hashlib
import json
import os
import re
import random
import subprocess
import uuid
from dataclasses import asdict, dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .cases import Case, Suite, load_suite
from .conditions import validate_conditions, materialize_conditions
from .comparison import compare_episodes, render_comparison
from .config import DEFAULT_PROMPT, DEFAULT_SUITE, ConfigError, PricingTable, load_prompt
from .evaluator import evaluate_document, write_evaluation
from .providers import get_provider
from .report import render_markdown
from .runner import build_prompt_text, run_suite, write_results

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY", "xai": "XAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}
ROOT_FIELDS = {"experiment_id", "suite_id", "prompt_id", "case_ids", "case_limit",
               "providers", "repeat_count", "timeout", "max_output_tokens", "mode", "conditions", "schedule_seed", "incident_ids", "cluster_ids"}
PROVIDER_FIELDS = {"provider", "model", "api_type", "output_constraint", "temperature",
                   "reasoning_effort", "thinking_mode", "model_id_stability",
                   "api_key_env", "mock_mode"}
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
    conditions: Optional[List[Dict[str, Any]]] = None
    schedule_seed: Optional[int] = None
    incident_ids: Optional[Dict[str, str]] = None
    cluster_ids: Optional[Dict[str, str]] = None

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
                      repeat_count, timeout, max_tokens, mode,
                      validate_conditions(doc["conditions"]) if "conditions" in doc else None,
                      _optional_int(doc.get("schedule_seed"), "schedule_seed", minimum=0),
                      _id_mapping(doc.get("incident_ids"), "incident_ids"),
                      _id_mapping(doc.get("cluster_ids"), "cluster_ids"))


def _validate_provider(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise ConfigError("each provider entry must be an object")
    unknown = sorted(set(entry) - PROVIDER_FIELDS)
    if unknown:
        raise ConfigError(f"unknown provider fields: {', '.join(unknown)}")
    name = entry.get("provider")
    if name not in ("mock", "openai", "anthropic", "gemini", "xai", "deepseek"):
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
        "gemini": ("json_schema", "json_object", "prompt_only"),
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
    efforts = {"openai": ("none", "low", "medium", "high", "xhigh", "max"),
               "anthropic": ("low", "medium", "high", "xhigh", "max"),
               "gemini": ("low", "medium", "high"),
               "xai": ("low", "medium", "high", "xhigh"),
               "deepseek": ("none", "low", "high", "max")}
    if effort is not None and (name not in efforts or effort not in efforts[name]):
        raise ConfigError(f"provider {name} does not support reasoning_effort {effort!r}")
    if name == "deepseek" and effort is None:
        raise ConfigError("provider deepseek requires explicit reasoning_effort (use 'none' to disable thinking)")
    if name == "deepseek" and effort not in (None, "none") and "temperature" in entry:
        raise ConfigError("DeepSeek temperature is unsupported in thinking mode")
    if name == "openai" and effort is not None and "temperature" in entry:
        raise ConfigError("OpenAI temperature is not supported with explicit reasoning_effort")
    thinking_mode = entry.get("thinking_mode")
    if name == "anthropic":
        if thinking_mode not in (None, "disabled", "between_tools", "adaptive"):
            raise ConfigError("Anthropic thinking_mode must be disabled, between_tools, or adaptive")
        if effort is not None and thinking_mode not in ("adaptive", "between_tools"):
            raise ConfigError("Anthropic reasoning_effort requires adaptive or between_tools thinking")
        if thinking_mode == "between_tools" and effort in ("xhigh", "max"):
            raise ConfigError("Anthropic between_tools supports low, medium, or high effort")
        if result["model"] == "claude-sonnet-5-5" and thinking_mode == "disabled":
            raise ConfigError("claude-sonnet-5-5 requires between_tools or adaptive thinking")
        if result["model"] in ("claude-sonnet-5", "claude-sonnet-5-5") and "temperature" in entry:
            raise ConfigError(f"{result['model']} baseline must omit temperature")
    elif thinking_mode is not None:
        raise ConfigError(f"thinking_mode is not supported for provider {name}")
    stability = entry.get("model_id_stability", "unknown")
    if stability not in ("pinned", "stable_alias", "mutable_alias", "unknown"):
        raise ConfigError("model_id_stability must be pinned, stable_alias, mutable_alias, or unknown")
    result["model_id_stability"] = stability
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
    materialize_conditions(experiment.conditions, load_prompt(experiment.prompt_id, root=root), root)
    if experiment.case_ids:
        try:
            cases = [suite.get(case_id) for case_id in experiment.case_ids]
        except KeyError as exc:
            raise ConfigError(str(exc))
    else:
        cases = list(suite.cases[:experiment.case_limit])
    count = _request_count(experiment, cases)
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
    for mapping in (experiment.incident_ids, experiment.cluster_ids):
        if mapping is not None and set(mapping) != {c.id for c in cases}:
            raise ConfigError("incident/cluster mapping must cover exactly selected cases")
    if experiment.incident_ids and experiment.cluster_ids:
        groups = {}
        for cid, incident in experiment.incident_ids.items():
            if incident in groups and groups[incident] != experiment.cluster_ids[cid]:
                raise ConfigError("one incident cannot belong to multiple clusters")
            groups[incident] = experiment.cluster_ids[cid]
    if require_keys:
        for entry in experiment.providers:
            _make_provider(entry, experiment)
    return suite, cases, sorted(set(missing_keys))


def _id_mapping(value: Any, name: str) -> Optional[Dict[str, str]]:
    if value is None:
        return None
    if not isinstance(value, dict) or not value:
        raise ConfigError(f"{name} must be a non-empty case-id mapping")
    for key, entry in value.items():
        _safe_id(key, name)
        _safe_id(entry, name)
    return dict(value)


@contextmanager
def _invocation_lock(directory: Path):
    lock = directory / ".active"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise ConfigError("invocation already active; inspect process before removing a stale .active lock") from exc
    with handle:
        handle.write(f"pid={os.getpid()}\n")
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def _configuration(experiment: Experiment) -> Dict[str, Any]:
    config = asdict(experiment)
    return {k: v for k, v in config.items() if v is not None}


def _slug(experiment: Experiment, block: Dict[str, Any]) -> str:
    entry = experiment.providers[block["provider_index"] - 1]
    slug = f"{block['provider_index']:02d}-{_safe_component(entry['provider'])}-{_safe_component(entry['model'])}-r{block['repetition']:02d}"
    return slug + "-" + block["condition_id"] if experiment.conditions is not None else slug


def _validate_resume(directory: Path, source: Dict[str, Any], expected: Dict[str, Any],
                     experiment: Experiment, cases: Sequence[Case]) -> Dict[str, Dict[str, Any]]:
    if source.get("checkpoint_version") != 1:
        raise ConfigError("manifest predates recoverable checkpoints; cannot resume")
    for key in ("configuration", "suite", "prompt", "case_fingerprints", "input_fingerprints",
                "condition_input_fingerprints", "conditions", "schedule", "pricing_snapshot", "engine_fingerprint", "case_inventory"):
        if source.get(key) != expected.get(key):
            raise ConfigError(f"resume {key} changed")
    if source.get("repository", {}).get("git_sha") != expected["repository"].get("git_sha"):
        raise ConfigError("resume HEAD changed")
    runs = source.get("runs")
    if not isinstance(runs, list) or len(runs) > len(expected["schedule"]):
        raise ConfigError("invalid resume run inventory")
    saved = {}
    selected = [c.id for c in cases]
    for index, block in zip(runs, expected["schedule"]):
        slug = _slug(experiment, block)
        entry = experiment.providers[block["provider_index"] - 1]
        identity = {"provider_index": block["provider_index"], "provider": entry["provider"],
                    "requested_model": entry["model"], "repetition": block["repetition"], "path": slug}
        if experiment.conditions is not None:
            identity["condition_id"] = block["condition_id"]
        if any(index.get(k) != v for k, v in identity.items()) or slug in saved:
            raise ConfigError("resume run identity/order changed")
        if index.get("results") != f"{slug}/results.json":
            raise ConfigError("resume result path changed")
        path = directory / slug / "results.json"
        if not path.is_file():
            raise ConfigError("resume checkpoint missing; cannot establish charged-request prefix")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            responses = doc["responses"]
            prefix = [r["case_id"] for r in responses]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ConfigError("corrupt resume checkpoint") from exc
        if doc.get("results_format_version") != 2 or prefix != selected[:len(prefix)] or len(prefix) > len(selected):
            raise ConfigError("resume responses must be an ordered prefix")
        run = doc.get("run", {})
        if run.get("checkpoint_identity") != identity or run.get("case_fingerprints") != expected["case_fingerprints"]:
            raise ConfigError("resume checkpoint identity changed")
        hashes = expected.get("condition_input_fingerprints", {}).get(block["condition_id"], expected["input_fingerprints"])
        if run.get("input_fingerprints") != hashes or run.get("cases_run") != selected:
            raise ConfigError("resume checkpoint input identity changed")
        if index.get("status") in ("completed", "completed_with_invalid_responses") and len(prefix) != len(selected):
            raise ConfigError("completed resume artifact is incomplete")
        saved[slug] = doc
    return saved


def run_experiment(experiment: Experiment, *, root: Optional[Path], output_root: Path,
                   max_requests: int, pricing: Optional[PricingTable] = None,
                   retry_of: Optional[str] = None, resume_dir: Optional[Path] = None) -> Path:
    # Validate identity before constructing any provider, including completed resumes.
    suite, cases, _ = preflight(experiment, root=root, max_requests=max_requests, require_keys=False)
    prompt = load_prompt(experiment.prompt_id, root=root)
    conditions = materialize_conditions(experiment.conditions, prompt, root)
    for mapping in (experiment.incident_ids, experiment.cluster_ids):
        if mapping is not None and set(mapping) != {c.id for c in cases}:
            raise ConfigError("incident/cluster mapping must cover exactly selected cases")
    if experiment.incident_ids and experiment.cluster_ids:
        clusters = {}
        for cid, incident in experiment.incident_ids.items():
            if incident in clusters and clusters[incident] != experiment.cluster_ids[cid]:
                raise ConfigError("one incident cannot belong to multiple clusters")
            clusters[incident] = experiment.cluster_ids[cid]
    git = _git_state(root)
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    manifest: Dict[str, Any] = {
        "experiment_format_version": 2 if experiment.conditions is not None else 1,
        "checkpoint_version": 1, "experiment_id": experiment.experiment_id,
        "experiment_run_id": run_stamp, "created_at": _now(), "completed_at": None,
        "retry_of": retry_of, "mode": experiment.mode,
        "provisional": any(not c.labels_frozen for c in cases),
        "comparative_ranking_permitted": (retry_of is None and experiment.mode == "reviewed" and
                                         all(c.labels_frozen for c in cases) and
                                         all(p["provider"] != "mock" for p in experiment.providers)),
        "suite": {"id": suite.id, "version": suite.version},
        "prompt": {"id": prompt.id, "sha256": prompt.sha256},
        "repository": git, "engine_fingerprint": _engine_fingerprint(),
        "case_fingerprints": {c.id: _case_hash(c) for c in cases},
        "case_inventory": {c.id: {"is_clean": c.is_clean, "category": c.category,
                                  "label_status": c.label_status} for c in cases},
        "input_fingerprints": {c.id: _input_hash(prompt, c) for c in cases},
        "configuration": _configuration(experiment),
        "pricing": {"as_of": pricing.as_of, "source": pricing.source} if pricing and pricing.models else None,
        "pricing_snapshot": asdict(pricing) if pricing else asdict(PricingTable.empty()),
        "repeat_count": experiment.repeat_count, "planned_requests": _request_count(experiment, cases),
        "schedule": build_schedule(experiment, conditions), "runs": [],
    }
    if experiment.conditions is not None:
        manifest["conditions"] = [{k: v for k, v in c.items() if k != "prompt"} for c in conditions]
        manifest["condition_input_fingerprints"] = {
            c["condition_id"]: {case.id: _input_hash(c["prompt"], case) for case in cases} for c in conditions}
    directory = Path(resume_dir) if resume_dir is not None else Path(output_root) / experiment.experiment_id / run_stamp
    if resume_dir is None:
        directory.mkdir(parents=True, exist_ok=False)
    with _invocation_lock(directory):
        if resume_dir is None:
            _write_json(directory / "configuration.json", _configuration(experiment))
        saved = {}
        if resume_dir is not None:
            try:
                source = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ConfigError("cannot read resume manifest") from exc
            saved = _validate_resume(directory, source, manifest, experiment, cases)
            manifest = source
            run_stamp = manifest["experiment_run_id"]
        missing = sum(len(cases) - len(saved.get(_slug(experiment, b), {}).get("responses", [])) for b in manifest["schedule"])
        if missing:
            preflight(experiment, root=root, max_requests=max_requests, require_keys=True)
        _write_json(directory / "manifest.json", manifest)
        for block_number, block in enumerate(manifest["schedule"]):
            provider_index = block["provider_index"]
            entry = experiment.providers[provider_index - 1]
            repetition = block["repetition"]
            condition = next(c for c in conditions if c["condition_id"] == block["condition_id"])
            slug = _slug(experiment, block)
            run_dir = directory / slug
            run_dir.mkdir(exist_ok=True)
            identity = {"provider_index": provider_index, "provider": entry["provider"],
                        "requested_model": entry["model"], "repetition": repetition, "path": slug}
            if experiment.conditions is not None:
                identity["condition_id"] = condition["condition_id"]
            if block_number < len(manifest["runs"]):
                index = manifest["runs"][block_number]
            else:
                index = {**identity, "status": "running", "results": f"{slug}/results.json",
                         "evaluation": None, "report": None, "error": None}
                manifest["runs"].append(index)
            inputs = {c.id: build_prompt_text(condition["prompt"], c) for c in cases}
            _write_json(run_dir / "inputs.json", inputs)
            hashes = manifest.get("condition_input_fingerprints", {}).get(condition["condition_id"], manifest["input_fingerprints"])
            def checkpoint(doc: Dict[str, Any]) -> None:
                doc["run"].update({
                    "experiment": {"id": experiment.experiment_id, "experiment_run_id": run_stamp,
                                   "repetition": repetition, "mode": experiment.mode},
                    "repository": git, "case_fingerprints": manifest["case_fingerprints"],
                    "input_fingerprints": hashes, "checkpoint_identity": identity})
                if experiment.conditions is not None:
                    doc["run"]["condition"] = {k: v for k, v in condition.items() if k not in ("prompt", "text", "files")}
                _write_json(run_dir / "results.json", doc)
            try:
                document = saved.get(slug)
                if document is None or len(document["responses"]) < len(cases):
                    index.update({"status": "running", "error": None})
                    _write_json(directory / "manifest.json", manifest)
                    provider = _make_provider(entry, experiment)
                    document = run_suite(suite, provider, condition["prompt"], case_ids=[c.id for c in cases],
                                         pricing=pricing, checkpoint=checkpoint, resume_document=document)
                checkpoint(document)
                evaluation = evaluate_document(document, suite, root=root)
                evaluation["experiment"] = {"mode": experiment.mode, "provisional": manifest["provisional"],
                                           "comparative_ranking_permitted": manifest["comparative_ranking_permitted"]}
                write_evaluation(evaluation, run_dir / "evaluation.json")
                (run_dir / "report.md").write_text(render_markdown(evaluation), encoding="utf-8")
                if any(r.get("error") for r in document["responses"]):
                    status = "failed"
                    index["error"] = "provider requests failed; see retained results.json"
                elif any(not r.get("valid") for r in document["responses"]):
                    status = "completed_with_invalid_responses"
                else:
                    status = "completed"
                    index["error"] = None
                index.update({"status": status, "evaluation": f"{slug}/evaluation.json", "report": f"{slug}/report.md"})
            except Exception as exc:
                index.update({"status": "failed", "error": _safe_error(exc)})
            _write_json(directory / "manifest.json", manifest)
        manifest["completed_at"] = _now()
        manifest["status"] = ("failed" if any(r["status"] == "failed" for r in manifest["runs"]) else
                              "completed_with_invalid_responses" if any(r["status"] != "completed" for r in manifest["runs"]) else "completed")
        _write_json(directory / "manifest.json", manifest)
        comparison = _compare_directory(directory, manifest, suite, root)
        _write_json(directory / "comparison.json", comparison)
        summary = _render_experiment_summary(directory, manifest) + "\n" + render_comparison(comparison)
        (directory / "summary.md").write_text(summary, encoding="utf-8")
        return directory


def _compare_directory(directory: Path, manifest: Dict[str, Any], suite: Suite,
                       root: Optional[Path]) -> Dict[str, Any]:
    episodes = []
    for index in manifest["runs"]:
        path = directory / index["results"]
        if not path.is_file():
            continue
        doc = json.loads(path.read_text())
        if not doc.get("responses"):
            continue
        evaluation = evaluate_document(doc, suite, root=root)
        raw = {r["case_id"]: r for r in doc["responses"]}
        for case in evaluation["cases"]:
            episodes.append({**case, "provider_index": index["provider_index"],
                             "condition_id": index.get("condition_id", "baseline"),
                             "repetition": index["repetition"], "valid": case["valid_response"],
                             "usage": raw[case["case_id"]].get("usage")})
    return compare_episodes(manifest, episodes)


def retry_failed_experiment(manifest_path: Path, *, root: Optional[Path], output_root: Path,
                            max_requests: int, pricing: Optional[PricingTable] = None) -> Path:
    """Create a new invocation containing only provider/model runs that failed.

    Invalid model responses are intentionally not retried: malformed structured
    output is benchmark evidence, while this command is only for provider errors
    or invocation failures recorded with status=failed.
    """
    manifest_path = Path(manifest_path)
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source.get("checkpoint_version") == 1 or "conditions" in source:
        return _retry_exact(manifest_path, source, root=root, output_root=output_root,
                            max_requests=max_requests, pricing=pricing)
    failed = [run for run in source.get("runs", []) if run.get("status") == "failed"]
    if not failed:
        raise ConfigError(f"{manifest_path}: no failed runs to retry")
    config = source.get("configuration")
    if not isinstance(config, dict):
        raise ConfigError(f"{manifest_path}: missing experiment configuration")

    selected: List[Dict[str, Any]] = []
    seen = set()
    for run in failed:
        key = (run.get("provider"), run.get("requested_model"))
        if key in seen:
            continue
        match = next(
            (p for p in config.get("providers", [])
             if p.get("provider") == key[0] and p.get("model") == key[1]),
            None,
        )
        if match is None:
            raise ConfigError(f"{manifest_path}: cannot map failed run {key!r} to configuration")
        selected.append(dict(match))
        seen.add(key)

    case_ids = list((source.get("input_fingerprints") or {}).keys())
    if not case_ids:
        raise ConfigError(f"{manifest_path}: missing input fingerprints/case ids")

    retry = Experiment(
        experiment_id=_safe_id(str(source.get("experiment_id", "experiment")) + "-retry", "experiment_id"),
        suite_id=config["suite_id"],
        prompt_id=config["prompt_id"],
        case_ids=case_ids,
        case_limit=None,
        providers=selected,
        repeat_count=1,
        timeout=config["timeout"],
        max_output_tokens=config["max_output_tokens"],
        mode=config["mode"],
    )
    source_id = str(source.get("experiment_run_id") or manifest_path.parent.name)
    return run_experiment(
        retry, root=root, output_root=output_root, max_requests=max_requests,
        pricing=pricing, retry_of=source_id,
    )


def _retry_exact(manifest_path: Path, source: Dict[str, Any], *, root: Optional[Path],
                 output_root: Path, max_requests: int, pricing: Optional[PricingTable]) -> Path:
    """Retry only explicitly failed requests; never collapse settings or repetitions."""
    try:
        original = Experiment(**{"case_ids": None, "case_limit": None, **source["configuration"]})
    except (KeyError, TypeError) as exc:
        raise ConfigError("missing/corrupt original configuration") from exc
    suite, cases, _ = preflight(original, root=root,
        max_requests=max(source.get("planned_requests", 0), 1), require_keys=False)
    prompt = load_prompt(original.prompt_id, root=root)
    conditions = materialize_conditions(original.conditions, prompt, root)
    if {c.id: _case_hash(c) for c in cases} != source.get("case_fingerprints"):
        raise ConfigError("retry case fingerprint changed")
    if source.get("prompt") != {"id": prompt.id, "sha256": prompt.sha256}:
        raise ConfigError("retry prompt changed")
    if source.get("repository", {}).get("git_sha") != _git_state(root).get("git_sha"):
        raise ConfigError("retry HEAD changed")
    if original.conditions is not None:
        snapshot = [{k: v for k, v in c.items() if k != "prompt"} for c in conditions]
        if snapshot != source.get("conditions"):
            raise ConfigError("retry condition snapshot changed")
    if source.get("engine_fingerprint") is not None and source["engine_fingerprint"] != _engine_fingerprint():
        raise ConfigError("retry engine fingerprint changed")
    if source.get("pricing_snapshot") is not None and source["pricing_snapshot"] != asdict(pricing or PricingTable.empty()):
        raise ConfigError("retry pricing changed")
    plans = []
    for index in source.get("runs", []):
        if index.get("status") != "failed":
            continue
        provider_index = index.get("provider_index")
        if not isinstance(provider_index, int) or not 1 <= provider_index <= len(original.providers):
            raise ConfigError("cannot resolve exact original provider configuration")
        entry = original.providers[provider_index - 1]
        if index.get("provider") != entry["provider"] or index.get("requested_model") != entry["model"]:
            raise ConfigError("retry provider identity changed")
        cid = index.get("condition_id", "baseline")
        condition = next((c for c in conditions if c["condition_id"] == cid), None)
        if condition is None:
            raise ConfigError("retry condition identity changed")
        result_path = manifest_path.parent / index["results"]
        if not result_path.resolve().is_relative_to(manifest_path.parent.resolve()):
            raise ConfigError("retry result escapes invocation")
        if not result_path.is_file():
            raise ConfigError("retry has no saved request evidence; recover by resume instead")
        doc = json.loads(result_path.read_text(encoding="utf-8"))
        expected = source.get("condition_input_fingerprints", {}).get(cid, source.get("input_fingerprints"))
        if doc.get("run", {}).get("input_fingerprints") != expected:
            raise ConfigError("retry input identity changed")
        responses = doc.get("responses", [])
        if [r.get("case_id") for r in responses] != [c.id for c in cases]:
            raise ConfigError("retry requires a complete saved run; resume the unfinished prefix first")
        ids = [r["case_id"] for r in responses if r.get("error")]
        if ids:
            plans.append((index, entry, cid, ids))
    count = sum(len(plan[3]) for plan in plans)
    if not count:
        raise ConfigError("no failed provider responses eligible for condition-aware retry")
    if count > max_requests or max_requests < 1:
        raise ConfigError(f"retry plans {count} requests, exceeding --max-requests {max_requests}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    retry_id = _safe_id(original.experiment_id + "-retry", "experiment_id")
    directory = Path(output_root) / retry_id / stamp
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"experiment_format_version": 2, "experiment_id": retry_id,
                "experiment_run_id": stamp, "retry_of": source["experiment_run_id"],
                "configuration": source["configuration"], "mode": original.mode,
                "planned_requests": count, "runs": [], "comparative_ranking_permitted": False,
                "provisional": source["provisional"], "created_at": _now()}
    if original.conditions is not None:
        manifest["conditions"] = source["conditions"]
    _write_json(directory / "manifest.json", manifest)
    for number, (index, entry, cid, ids) in enumerate(plans, 1):
        selected_condition = next(c for c in original.conditions or [] if c["condition_id"] == cid) if original.conditions is not None else None
        child = Experiment(retry_id, original.suite_id, original.prompt_id, ids, None, [entry], 1,
                           original.timeout, original.max_output_tokens, original.mode,
                           [selected_condition] if selected_condition else None, original.schedule_seed)
        child_dir = run_experiment(child, root=root, output_root=directory / f"attempt-{number:03d}",
                                   max_requests=len(ids), pricing=pricing, retry_of=source["experiment_run_id"])
        child_manifest = json.loads((child_dir / "manifest.json").read_text())
        context = {"source_invocation": source["experiment_run_id"], "source_run": index["path"],
                   "original_provider_index": index["provider_index"],
                   "original_repetition": index["repetition"], "condition_id": cid,
                   "case_ids": ids}
        child_manifest["retry_context"] = context
        _write_json(child_dir / "manifest.json", child_manifest)
        for child_run in child_manifest["runs"]:
            prefix = child_dir.relative_to(directory)
            doc_path = child_dir / child_run["results"]
            if doc_path.is_file():
                child_document = json.loads(doc_path.read_text())
                child_document["run"]["retry_context"] = context
                _write_json(doc_path, child_document)
            item = {**child_run, "original_provider_index": index["provider_index"],
                    "original_repetition": index["repetition"], "original_run_path": index["path"],
                    "attempt_manifest": str(prefix / "manifest.json"),
                    "attempt_configuration": str(prefix / "configuration.json")}
            for key in ("path", "results", "evaluation", "report"):
                if item.get(key):
                    item[key] = str(prefix / item[key])
            manifest["runs"].append(item)
        _write_json(directory / "manifest.json", manifest)
    manifest["completed_at"] = _now()
    manifest["status"] = ("failed" if any(r["status"] == "failed" for r in manifest["runs"]) else
                          "completed_with_invalid_responses" if any(r["status"] != "completed" for r in manifest["runs"]) else "completed")
    _write_json(directory / "manifest.json", manifest)
    (directory / "summary.md").write_text(_render_experiment_summary(directory, manifest), encoding="utf-8")
    return directory


def _render_experiment_summary(directory: Path, manifest: Dict[str, Any]) -> str:
    """Render one auditable cross-provider table for an experiment invocation."""
    lines = [
        f"# Experiment summary — {manifest['experiment_id']}",
        "",
        f"Status: **{manifest.get('status', 'incomplete')}**",
        "",
        "| Provider | Model | Rep | Status | TP | FP | FN | Precision | Recall | Clean false alarms | Malformed | Errors |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    conditioned = "conditions" in manifest
    if conditioned:
        lines[4] = lines[4].replace("| Provider |", "| Condition | Provider |", 1)
        lines[5] = "| --- " + lines[5]
    for run in manifest.get("runs", []):
        row_prefix = f"| {run['condition_id']} " if conditioned else ""
        evaluation_path = run.get("evaluation")
        if not evaluation_path or not (directory / evaluation_path).is_file():
            lines.append(
                row_prefix + f"| {run['provider']} | {run['requested_model']} | {run['repetition']} | "
                f"{run['status']} | — | — | — | — | — | — | — | — |"
            )
            continue
        evaluation = json.loads((directory / evaluation_path).read_text(encoding="utf-8"))
        metrics = evaluation["metrics"]
        counts = metrics["counts"]
        findings = metrics["findings"]
        quality = metrics["quality"]
        false_alarms = metrics["false_alarms"]

        def show(value: Any) -> str:
            return "—" if value is None else (f"{value:.3f}" if isinstance(value, float) else str(value))

        lines.append(
            row_prefix + f"| {run['provider']} | {run['requested_model']} | {run['repetition']} | {run['status']} | "
            f"{findings['true_positives']} | {findings['false_positives']} | {findings['false_negatives']} | "
            f"{show(quality['precision'])} | {show(quality['recall'])} | "
            f"{show(false_alarms['clean_case_false_alarm_rate'])} | "
            f"{counts['invalid_responses'] - counts['provider_errors']} | {counts['provider_errors']} |"
        )
    lines.extend([
        "",
        "This table is descriptive. Pairwise claims remain subject to the frozen methodology and run-count requirements.",
        "",
    ])
    return "\n".join(lines)


def dry_run_summary(experiment: Experiment, suite: Suite, cases: Sequence[Case],
                    missing_keys: Sequence[str], output_root: Path, max_requests: int) -> str:
    lines = [f"experiment: {experiment.experiment_id}", f"mode: {experiment.mode}",
             f"suite: {suite.id} {suite.version}", f"cases ({len(cases)}): " + ", ".join(c.id for c in cases),
             f"repeat count: {experiment.repeat_count}",
             f"planned requests: {_request_count(experiment, cases)} (maximum {max_requests})",
             f"output: {Path(output_root) / experiment.experiment_id / '<unique-run-id>'}", "providers:"]
    for entry in experiment.providers:
        lines.append(f"  - {entry['provider']} / {entry['model']} / {entry.get('output_constraint', 'native_json')}")
    if experiment.conditions is not None:
        lines.append("conditions: " + ", ".join(c["condition_id"] for c in experiment.conditions))
    lines.append("missing credentials: " + (", ".join(missing_keys) if missing_keys else "none"))
    return "\n".join(lines)


def build_schedule(experiment: Experiment, conditions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Randomized run blocks with reverse-paired condition order; legacy is fixed."""
    rng = random.Random(experiment.schedule_seed)
    schedule = []
    for provider_index in range(1, len(experiment.providers) + 1):
        order = [c["condition_id"] for c in conditions]
        for repetition in range(1, experiment.repeat_count + 1):
            if experiment.schedule_seed is not None:
                if repetition % 2:
                    rng.shuffle(order)
                else:
                    order.reverse()
            for condition_id in order:
                schedule.append({"provider_index": provider_index,
                                 "repetition": repetition, "condition_id": condition_id})
    return schedule


def _request_count(experiment: Experiment, cases: Sequence[Case]) -> int:
    return (len(cases) * len(experiment.providers) * experiment.repeat_count *
            (len(experiment.conditions) if experiment.conditions is not None else 1))


def _make_provider(entry: Dict[str, Any], experiment: Experiment):
    kwargs: Dict[str, Any] = {"name": entry["provider"], "model": entry["model"],
        "timeout": experiment.timeout, "max_output_tokens": experiment.max_output_tokens,
        "mode": entry.get("mock_mode", "heuristic"),
        "model_id_stability": entry.get("model_id_stability", "unknown")}
    if "temperature" in entry:
        kwargs["temperature"] = entry["temperature"]
    for name in ("api_type", "output_constraint", "reasoning_effort", "thinking_mode"):
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


def _engine_fingerprint() -> str:
    source = Path(__file__).parent
    inventory = [(p.relative_to(source).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in sorted(source.rglob("*.py"))]
    return hashlib.sha256(json.dumps(inventory, separators=(",", ":")).encode()).hexdigest()


def _case_hash(case: Case) -> str:
    canonical = json.dumps(case.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _input_hash(prompt: Any, case: Case) -> str:
    return hashlib.sha256(build_prompt_text(prompt, case).encode()).hexdigest()


def _git_state(root: Optional[Path]) -> Dict[str, Any]:
    cwd = str(root or Path.cwd())
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, text=True,
                             capture_output=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"],
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
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
