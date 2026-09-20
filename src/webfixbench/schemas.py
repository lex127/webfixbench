"""Schemas and validation for benchmark cases and model responses.

Validation is implemented in plain Python rather than through a JSON Schema
library so that the benchmark can be run and reproduced without installing
anything. Machine-readable JSON Schema documents describing the same shapes
live in ``schema/`` for external tooling; ``tests/test_schema_documents.py``
keeps the two in sync for the fields that matter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# --------------------------------------------------------------------------
# Taxonomy
# --------------------------------------------------------------------------

#: Defect categories allowed in v0.1. Deliberately limited to categories with
#: objective ground truth. Subjective categories (style, maintainability,
#: performance, architecture) are out of scope for this release.
CATEGORIES = (
    "authorization",
    "injection",
    "xss",
    "secrets",
    "unsafe_deserialization",
    "clean_control",
)

#: Categories that describe an actual defect (``clean_control`` is a label for
#: cases that must produce no findings, not a defect category).
DEFECT_CATEGORIES = tuple(c for c in CATEGORIES if c != "clean_control")

#: Machine-readable mechanisms used for finding-level matching. Broad
#: categories remain on findings for aggregation, but are not precise enough
#: to decide whether a prediction identified the labelled defect.
DEFECT_TYPES = (
    "authorization_policy_removed",
    "authorization_middleware_removed",
    "authorization_capability_missing",
    "sql_injection",
    "xss_unescaped_output",
    "hardcoded_secret",
    "unsafe_deserialization",
    "environment_override_from_web_argv",
)

UNKNOWN_DEFECT_TYPE = "other"

#: Category returned by :func:`normalize_category` when a predicted category
#: cannot be mapped onto the v0.1 taxonomy.
UNKNOWN_CATEGORY = "other"

SEVERITIES = ("low", "medium", "high", "critical")
DIFFICULTIES = ("easy", "medium", "hard")
ECOSYSTEMS = ("php", "laravel", "wordpress")
LANGUAGES = ("php",)
SOURCE_TYPES = ("synthetic", "public_advisory", "public_repository")

#: How a case's ground truth was produced. An agent may draft a fixture, but a
#: draft is not ground truth: only a human maintainer can review and freeze it.
LABEL_SOURCES = (
    "agent_drafted",
    "human_authored",
    "human_reviewed",
    "public_advisory_plus_human_review",
)

#: Lifecycle of a case's labels. Only ``frozen`` labels are ready to score a
#: model against; see :func:`validate_case_dict` for the invariant that stops a
#: case being marked frozen without a named human reviewer.
LABEL_STATUSES = ("draft", "pending_review", "frozen")

#: Label sources that represent human authorship or human review.
HUMAN_LABEL_SOURCES = (
    "human_authored",
    "human_reviewed",
    "public_advisory_plus_human_review",
)

#: Aliases accepted from model output. Models phrase categories in many ways;
#: matching would be unfairly strict without a fixed, documented alias table.
#: The table is frozen for the v0.1 suite and versioned with it.
CATEGORY_ALIASES: Dict[str, str] = {
    # authorization
    "authz": "authorization",
    "access_control": "authorization",
    "broken_access_control": "authorization",
    "missing_authorization": "authorization",
    "missing_authorization_check": "authorization",
    "missing_capability_check": "authorization",
    "privilege_escalation": "authorization",
    "idor": "authorization",
    "insecure_direct_object_reference": "authorization",
    # injection
    "sql_injection": "injection",
    "sqli": "injection",
    "command_injection": "injection",
    "code_injection": "injection",
    "injection_flaw": "injection",
    # xss
    "cross_site_scripting": "xss",
    "reflected_xss": "xss",
    "stored_xss": "xss",
    "output_escaping": "xss",
    "missing_output_escaping": "xss",
    # secrets
    "secret": "secrets",
    "hardcoded_secret": "secrets",
    "hardcoded_credentials": "secrets",
    "hardcoded_credential": "secrets",
    "credential_leak": "secrets",
    "exposed_credentials": "secrets",
    # unsafe deserialization
    "deserialization": "unsafe_deserialization",
    "insecure_deserialization": "unsafe_deserialization",
    "unsafe_unserialize": "unsafe_deserialization",
    "object_injection": "unsafe_deserialization",
    "php_object_injection": "unsafe_deserialization",
}


def normalize_category(value: Any) -> str:
    """Normalize a model-supplied category onto the v0.1 taxonomy.

    Unrecognised categories are mapped to :data:`UNKNOWN_CATEGORY` rather than
    being dropped, so that they are still counted as false positives.
    """
    if not isinstance(value, str):
        return UNKNOWN_CATEGORY
    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    while "__" in key:
        key = key.replace("__", "_")
    if key in CATEGORIES:
        return key
    return CATEGORY_ALIASES.get(key, UNKNOWN_CATEGORY)


def normalize_defect_type(value: Any) -> str:
    """Return a canonical v0.1 defect type, or ``other`` when unknown."""
    if not isinstance(value, str):
        return UNKNOWN_DEFECT_TYPE
    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    while "__" in key:
        key = key.replace("__", "_")
    return key if key in DEFECT_TYPES else UNKNOWN_DEFECT_TYPE


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class ValidationError(ValueError):
    """Raised when a case or a model response does not satisfy the schema."""

    def __init__(self, errors: Iterable[str], subject: str = "document") -> None:
        self.errors = list(errors)
        joined = "; ".join(self.errors)
        super().__init__(f"invalid {subject}: {joined}")


# --------------------------------------------------------------------------
# Small validation helpers
# --------------------------------------------------------------------------


def _require(errors: List[str], cond: bool, message: str) -> bool:
    if not cond:
        errors.append(message)
    return cond


def _check_str(errors: List[str], doc: Dict[str, Any], key: str, *, where: str,
               allowed: Optional[Iterable[str]] = None, allow_empty: bool = False) -> None:
    value = doc.get(key)
    if not isinstance(value, str):
        errors.append(f"{where}.{key} must be a string")
        return
    if not allow_empty and not value.strip():
        errors.append(f"{where}.{key} must not be empty")
        return
    if allowed is not None and value not in allowed:
        errors.append(f"{where}.{key} must be one of {sorted(allowed)}, got {value!r}")


def _check_optional_str(errors: List[str], doc: Dict[str, Any], key: str, *, where: str) -> None:
    value = doc.get(key, None)
    if value is not None and not isinstance(value, str):
        errors.append(f"{where}.{key} must be a string or null")


def _check_confidence(errors: List[str], value: Any, where: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{where} must be a number between 0.0 and 1.0")
        return
    if not (0.0 <= float(value) <= 1.0):
        errors.append(f"{where} must be between 0.0 and 1.0, got {value}")


# --------------------------------------------------------------------------
# Case schema
# --------------------------------------------------------------------------

CASE_REQUIRED_FIELDS = (
    "id",
    "title",
    "language",
    "ecosystem",
    "category",
    "difficulty",
    "source_type",
    "source_url",
    "description",
    "diff",
    "expected_findings",
    "is_clean",
    "label_source",
    "label_status",
    "reviewed_by",
)

ADVISORY_PROVENANCE_FIELDS = (
    "advisory_id", "original_project", "reconstruction_type", "license_note",
)
RECONSTRUCTION_TYPES = ("synthetic_reconstruction",)
CASE_OPTIONAL_FIELDS = (
    "tags", "context", "notes", "references", "academic_review",
) + ADVISORY_PROVENANCE_FIELDS

_CASE_KNOWN_FIELDS = set(CASE_REQUIRED_FIELDS) | set(CASE_OPTIONAL_FIELDS)


@dataclass(frozen=True)
class ExpectedFinding:
    """A labelled defect that a reviewer is expected to report."""

    category: str
    defect_type: str
    severity: str
    description: str
    file: Optional[str] = None
    id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "defect_type": self.defect_type,
            "severity": self.severity,
            "file": self.file,
            "description": self.description,
        }


@dataclass(frozen=True)
class Case:
    """A single benchmark case."""

    id: str
    title: str
    language: str
    ecosystem: str
    category: str
    difficulty: str
    source_type: str
    source_url: Optional[str]
    description: str
    diff: str
    expected_findings: List[ExpectedFinding]
    is_clean: bool
    label_source: str = "agent_drafted"
    label_status: str = "draft"
    reviewed_by: List[str] = field(default_factory=list)
    academic_review: bool = False
    tags: List[str] = field(default_factory=list)
    context: Optional[str] = None
    notes: Optional[str] = None
    references: List[str] = field(default_factory=list)
    advisory_id: Optional[str] = None
    original_project: Optional[str] = None
    reconstruction_type: Optional[str] = None
    license_note: Optional[str] = None
    path: Optional[Path] = None

    @property
    def expected_categories(self) -> List[str]:
        return [f.category for f in self.expected_findings]

    @property
    def labels_frozen(self) -> bool:
        """True when the ground truth is final and ready to score against."""
        return self.label_status == "frozen"

    def to_dict(self) -> Dict[str, Any]:
        document = {
            "id": self.id,
            "title": self.title,
            "language": self.language,
            "ecosystem": self.ecosystem,
            "category": self.category,
            "difficulty": self.difficulty,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "description": self.description,
            "diff": self.diff,
            "expected_findings": [f.to_dict() for f in self.expected_findings],
            "is_clean": self.is_clean,
            "label_source": self.label_source,
            "label_status": self.label_status,
            "reviewed_by": list(self.reviewed_by),
            "academic_review": self.academic_review,
            "tags": list(self.tags),
            "context": self.context,
            "notes": self.notes,
            "references": list(self.references),
        }
        for key in ADVISORY_PROVENANCE_FIELDS:
            value = getattr(self, key)
            if value is not None:
                document[key] = value
        return document


def validate_case_dict(doc: Any) -> List[str]:
    """Return a list of validation errors for a raw case document."""
    errors: List[str] = []
    if not isinstance(doc, dict):
        return ["case must be a JSON object"]

    missing = [k for k in CASE_REQUIRED_FIELDS if k not in doc]
    if missing:
        errors.append(f"missing required field(s): {', '.join(sorted(missing))}")

    unknown = sorted(set(doc) - _CASE_KNOWN_FIELDS)
    if unknown:
        errors.append(f"unknown field(s): {', '.join(unknown)}")

    _check_str(errors, doc, "id", where="case")
    _check_str(errors, doc, "title", where="case")
    _check_str(errors, doc, "language", where="case", allowed=LANGUAGES)
    _check_str(errors, doc, "ecosystem", where="case", allowed=ECOSYSTEMS)
    _check_str(errors, doc, "category", where="case", allowed=CATEGORIES)
    _check_str(errors, doc, "difficulty", where="case", allowed=DIFFICULTIES)
    _check_str(errors, doc, "source_type", where="case", allowed=SOURCE_TYPES)
    _check_str(errors, doc, "description", where="case")
    _check_str(errors, doc, "diff", where="case")
    _check_optional_str(errors, doc, "source_url", where="case")
    _check_optional_str(errors, doc, "context", where="case")
    _check_optional_str(errors, doc, "notes", where="case")

    # Advisory provenance is mandatory for sourced drafts, never a substitute
    # for human approval. Original synthetic cases keep their existing shape.
    for key in ADVISORY_PROVENANCE_FIELDS:
        if key in doc or doc.get("source_type") == "public_advisory":
            allowed = RECONSTRUCTION_TYPES if key == "reconstruction_type" else None
            _check_str(errors, doc, key, where="case", allowed=allowed)
    if doc.get("source_type") == "public_advisory":
        _check_str(errors, doc, "source_url", where="case")

    case_id = doc.get("id")
    if isinstance(case_id, str) and case_id.strip():
        allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if set(case_id) - allowed_chars:
            errors.append("case.id must contain only lowercase letters, digits and '-'")

    for key in ("tags", "references", "reviewed_by"):
        value = doc.get(key, [])
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            errors.append(f"case.{key} must be a list of strings")

    _check_str(errors, doc, "label_source", where="case", allowed=LABEL_SOURCES)
    _check_str(errors, doc, "label_status", where="case", allowed=LABEL_STATUSES)

    academic_review = doc.get("academic_review", False)
    if not isinstance(academic_review, bool):
        errors.append("case.academic_review must be a boolean")

    # Ground truth may not be frozen by an agent, and may not be frozen
    # anonymously: a frozen label names the human who accepted it.
    label_status = doc.get("label_status")
    label_source = doc.get("label_source")
    reviewed_by = doc.get("reviewed_by")
    if label_status == "frozen":
        if not isinstance(reviewed_by, list) or not reviewed_by:
            errors.append(
                "case.label_status 'frozen' requires a non-empty reviewed_by list "
                "naming the human reviewer who accepted the labels"
            )
        if label_source not in HUMAN_LABEL_SOURCES:
            errors.append(
                "case.label_status 'frozen' requires label_source to be one of "
                f"{sorted(HUMAN_LABEL_SOURCES)}; model output is never ground truth"
            )
    if label_source == "agent_drafted" and label_status == "frozen":
        errors.append("an agent-drafted case cannot be frozen without human review")

    is_clean = doc.get("is_clean")
    if not isinstance(is_clean, bool):
        errors.append("case.is_clean must be a boolean")

    findings = doc.get("expected_findings")
    if not isinstance(findings, list):
        errors.append("case.expected_findings must be a list")
        findings = []
    for index, finding in enumerate(findings):
        where = f"case.expected_findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{where} must be an object")
            continue
        unknown_f = sorted(
            set(finding) - {"id", "category", "defect_type", "severity", "file", "description"}
        )
        if unknown_f:
            errors.append(f"{where} has unknown field(s): {', '.join(unknown_f)}")
        _check_str(errors, finding, "category", where=where, allowed=DEFECT_CATEGORIES)
        _check_str(errors, finding, "defect_type", where=where, allowed=DEFECT_TYPES)
        _check_str(errors, finding, "severity", where=where, allowed=SEVERITIES)
        _check_str(errors, finding, "description", where=where)
        _check_optional_str(errors, finding, "file", where=where)
        _check_optional_str(errors, finding, "id", where=where)

    # Cross-field consistency: the whole point of clean controls is that they
    # carry no expected findings, and defect cases must carry at least one.
    if isinstance(is_clean, bool) and isinstance(findings, list):
        if is_clean and findings:
            errors.append("clean cases must have an empty expected_findings list")
        if not is_clean and not findings:
            errors.append("non-clean cases must declare at least one expected finding")

    category = doc.get("category")
    if isinstance(is_clean, bool) and isinstance(category, str):
        if is_clean and category != "clean_control":
            errors.append("clean cases must use category 'clean_control'")
        if not is_clean and category == "clean_control":
            errors.append("category 'clean_control' requires is_clean = true")

    if isinstance(category, str) and isinstance(findings, list) and findings:
        declared = {f.get("category") for f in findings if isinstance(f, dict)}
        if category not in declared:
            errors.append(
                "case.category must match at least one expected finding category "
                f"(category={category!r}, findings={sorted(str(d) for d in declared)})"
            )

    return errors


def case_from_dict(doc: Any, *, path: Optional[Path] = None) -> Case:
    """Validate ``doc`` and build a :class:`Case`."""
    errors = validate_case_dict(doc)
    if errors:
        subject = f"case {path}" if path else "case"
        raise ValidationError(errors, subject=subject)

    findings = [
        ExpectedFinding(
            category=f["category"],
            defect_type=f["defect_type"],
            severity=f["severity"],
            description=f["description"],
            file=f.get("file"),
            id=f.get("id"),
        )
        for f in doc["expected_findings"]
    ]
    return Case(
        id=doc["id"],
        title=doc["title"],
        language=doc["language"],
        ecosystem=doc["ecosystem"],
        category=doc["category"],
        difficulty=doc["difficulty"],
        source_type=doc["source_type"],
        source_url=doc.get("source_url"),
        description=doc["description"],
        diff=doc["diff"],
        expected_findings=findings,
        is_clean=doc["is_clean"],
        label_source=doc["label_source"],
        label_status=doc["label_status"],
        reviewed_by=list(doc.get("reviewed_by", [])),
        academic_review=bool(doc.get("academic_review", False)),
        tags=list(doc.get("tags", [])),
        context=doc.get("context"),
        notes=doc.get("notes"),
        references=list(doc.get("references", [])),
        advisory_id=doc.get("advisory_id"),
        original_project=doc.get("original_project"),
        reconstruction_type=doc.get("reconstruction_type"),
        license_note=doc.get("license_note"),
        path=path,
    )


# --------------------------------------------------------------------------
# Model response schema
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PredictedFinding:
    """A finding reported by a reviewer."""

    category: str
    defect_type: str
    severity: str
    description: str
    file: Optional[str] = None
    line: Optional[int] = None
    confidence: Optional[float] = None

    @property
    def normalized_category(self) -> str:
        return normalize_category(self.category)

    @property
    def normalized_defect_type(self) -> str:
        return normalize_defect_type(self.defect_type)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "defect_type": self.defect_type,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "description": self.description,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ModelResponse:
    """A validated structured review returned by a provider."""

    findings: List[PredictedFinding]
    overall_confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "overall_confidence": self.overall_confidence,
        }


def validate_model_response_dict(doc: Any) -> List[str]:
    """Return a list of validation errors for a raw model response."""
    errors: List[str] = []
    if not isinstance(doc, dict):
        return ["model response must be a JSON object"]

    unknown = sorted(set(doc) - {"findings", "overall_confidence"})
    if unknown:
        errors.append(f"unknown field(s): {', '.join(unknown)}")

    if "findings" not in doc:
        errors.append("missing required field: findings")
    findings = doc.get("findings")
    if not isinstance(findings, list):
        if "findings" in doc:
            errors.append("findings must be a list")
        findings = []

    for index, finding in enumerate(findings):
        where = f"findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{where} must be an object")
            continue
        unknown_f = sorted(
            set(finding)
            - {"category", "defect_type", "severity", "file", "line", "description", "confidence"}
        )
        if unknown_f:
            errors.append(f"{where} has unknown field(s): {', '.join(unknown_f)}")
        _check_str(errors, finding, "category", where=where)
        _check_str(errors, finding, "defect_type", where=where)
        _check_str(errors, finding, "severity", where=where, allowed=SEVERITIES)
        _check_str(errors, finding, "description", where=where)
        _check_optional_str(errors, finding, "file", where=where)
        line = finding.get("line", None)
        if line is not None and (isinstance(line, bool) or not isinstance(line, int)):
            errors.append(f"{where}.line must be an integer or null")
        if "confidence" in finding and finding["confidence"] is not None:
            _check_confidence(errors, finding["confidence"], f"{where}.confidence")

    overall = doc.get("overall_confidence", None)
    if overall is not None:
        _check_confidence(errors, overall, "overall_confidence")

    return errors


def model_response_from_dict(doc: Any) -> ModelResponse:
    """Validate ``doc`` and build a :class:`ModelResponse`."""
    errors = validate_model_response_dict(doc)
    if errors:
        raise ValidationError(errors, subject="model response")
    findings = [
        PredictedFinding(
            category=f["category"],
            defect_type=f["defect_type"],
            severity=f["severity"],
            description=f["description"],
            file=f.get("file"),
            line=f.get("line"),
            confidence=f.get("confidence"),
        )
        for f in doc["findings"]
    ]
    return ModelResponse(findings=findings, overall_confidence=doc.get("overall_confidence"))


def parse_model_response(text: str) -> ModelResponse:
    """Parse and validate raw provider text into a :class:`ModelResponse`.

    Models frequently wrap JSON in prose or a fenced code block. A single,
    documented extraction step is applied (outermost ``{...}`` span); anything
    that still fails to parse is a malformed response and is reported as such.
    Malformed responses are never silently treated as "no findings".
    """
    if not isinstance(text, str) or not text.strip():
        raise ValidationError(["response is empty"], subject="model response")

    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    try:
        doc = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValidationError(["response is not valid JSON"], subject="model response")
        try:
            doc = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValidationError(
                [f"response is not valid JSON: {exc.msg}"], subject="model response"
            )

    return model_response_from_dict(doc)
