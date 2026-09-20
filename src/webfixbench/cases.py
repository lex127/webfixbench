"""Loading benchmark suites and cases from disk."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DEFAULT_SUITE, ConfigError, suites_dir
from .schemas import Case, ValidationError, case_from_dict

SUITE_MANIFEST = "suite.json"


@dataclass(frozen=True)
class Suite:
    """A benchmark suite: a manifest plus an ordered list of cases."""

    id: str
    title: str
    version: str
    description: str
    cases: List[Case]
    path: Path
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.cases)

    def get(self, case_id: str) -> Case:
        for case in self.cases:
            if case.id == case_id:
                return case
        raise KeyError(case_id)

    @property
    def clean_cases(self) -> List[Case]:
        return [c for c in self.cases if c.is_clean]

    @property
    def defect_cases(self) -> List[Case]:
        return [c for c in self.cases if not c.is_clean]


def load_case_file(path: Path) -> Case:
    """Load and validate a single case JSON file."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError([f"file is not valid JSON: {exc}"], subject=f"case {path}")
    return case_from_dict(doc, path=path)


def load_suite(suite_id: str = DEFAULT_SUITE, root: Optional[Path] = None) -> Suite:
    """Load a suite by id, validating every case it contains.

    A suite directory holds ``suite.json`` (manifest) and ``cases/*.json``.
    Cases are ordered by id so that runs and reports are stable.
    """
    base = suites_dir(root) / suite_id
    manifest_path = base / SUITE_MANIFEST
    if not manifest_path.is_file():
        available = list_suites(root)
        raise ConfigError(
            f"unknown suite {suite_id!r} (expected {manifest_path}). "
            f"Available: {', '.join(available) if available else 'none'}"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    case_paths = sorted((base / "cases").glob("*.json"))
    if not case_paths:
        raise ConfigError(f"suite {suite_id!r} contains no cases in {base / 'cases'}")

    cases = [load_case_file(p) for p in case_paths]
    cases.sort(key=lambda c: c.id)

    seen: Dict[str, Path] = {}
    for case in cases:
        if case.id in seen:
            raise ValidationError(
                [f"duplicate case id {case.id!r} in {case.path} and {seen[case.id]}"],
                subject=f"suite {suite_id}",
            )
        seen[case.id] = case.path  # type: ignore[assignment]

    declared = manifest.get("case_count")
    if isinstance(declared, int) and declared != len(cases):
        raise ValidationError(
            [f"manifest declares case_count={declared} but {len(cases)} case files were found"],
            subject=f"suite {suite_id}",
        )

    return Suite(
        id=manifest.get("id", suite_id),
        title=manifest.get("title", suite_id),
        version=manifest.get("version", "unknown"),
        description=manifest.get("description", ""),
        cases=cases,
        path=base,
        metadata=manifest,
    )


def list_suites(root: Optional[Path] = None) -> List[str]:
    """Return the ids of suites available on disk."""
    try:
        base = suites_dir(root)
    except ConfigError:
        return []
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / SUITE_MANIFEST).is_file())
