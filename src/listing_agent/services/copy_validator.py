import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any


@dataclass(slots=True)
class ValidationIssue:
    field: str
    code: str
    message: str
    severity: str = "hard"

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(slots=True)
class ValidationResult:
    passed: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    normalized_draft: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


class _DescriptionHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:
        self.tags.append(tag.lower())

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text_parts.append(data.strip())


ALLOWED_DESCRIPTION_TAGS = {"p", "b"}
BLOCKED_DESCRIPTION_TAGS = {"script", "style", "iframe"}
REQUIRED_DESCRIPTION_FRAGMENTS = (
    "specification",
    "brand",
    "name",
    "color",
    "material",
    "size",
    "applicable",
    "features",
)


def validate_against_policy_pack(
    draft: dict[str, Any],
    policy_pack: dict[str, Any],
) -> ValidationResult:
    """Validate deterministic listing-copy constraints without scoring copy quality."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    normalized = _normalize_draft(draft, warnings)
    _validate_structure(normalized, errors)
    _validate_description_html(normalized.get("description_text"), errors)
    _validate_forbidden_terms(normalized, policy_pack, errors)
    _validate_missing_facts(normalized, policy_pack, errors)
    _validate_search_terms(normalized, policy_pack, errors, warnings)
    return ValidationResult(
        passed=not errors,
        errors=errors,
        warnings=warnings,
        normalized_draft=normalized,
    )


def _normalize_draft(
    draft: dict[str, Any],
    warnings: list[ValidationIssue],
) -> dict[str, Any]:
    normalized = dict(draft)
    search_terms = normalized.get("search_terms")
    if isinstance(search_terms, list):
        cleaned_terms = _dedupe_text(
            [item.strip() for item in search_terms if isinstance(item, str) and item.strip()]
        )
        if cleaned_terms != search_terms:
            warnings.append(
                ValidationIssue(
                    field="search_terms",
                    code="search_terms_normalized",
                    message="Empty or duplicate search terms were normalized.",
                    severity="soft",
                )
            )
        normalized["search_terms"] = cleaned_terms
    return normalized


def _validate_structure(draft: dict[str, Any], errors: list[ValidationIssue]) -> None:
    if not isinstance(draft.get("title"), str) or not draft["title"].strip():
        errors.append(_issue("title", "required", "Title must be a non-empty string."))
    bullets = draft.get("bullets")
    if not isinstance(bullets, list) or len(bullets) != 5:
        errors.append(_issue("bullets", "count", "Bullets must contain exactly five items."))
    elif not all(isinstance(item, str) and item.strip() for item in bullets):
        errors.append(_issue("bullets", "required", "Each bullet must be a non-empty string."))
    if not isinstance(draft.get("description_text"), str) or not draft["description_text"].strip():
        errors.append(
            _issue("description_text", "required", "Description HTML must be a non-empty string.")
        )
    if not isinstance(draft.get("search_terms"), list) or not all(
        isinstance(item, str) for item in draft.get("search_terms", [])
    ):
        errors.append(_issue("search_terms", "type", "Search terms must be a list of strings."))


def _validate_description_html(value: Any, errors: list[ValidationIssue]) -> None:
    if not isinstance(value, str) or not value.strip():
        return
    parser = _DescriptionHTMLParser()
    parser.feed(value)
    tags = set(parser.tags)
    blocked = sorted(tags & BLOCKED_DESCRIPTION_TAGS)
    if blocked:
        errors.append(
            _issue(
                "description_text",
                "blocked_html_tag",
                f"Description contains blocked HTML tags: {', '.join(blocked)}.",
            )
        )
    unsupported = sorted(tags - ALLOWED_DESCRIPTION_TAGS)
    if unsupported:
        errors.append(
            _issue(
                "description_text",
                "unsupported_html_tag",
                f"Description contains unsupported HTML tags: {', '.join(unsupported)}.",
            )
        )
    lowered = " ".join(parser.text_parts).lower()
    missing = [fragment for fragment in REQUIRED_DESCRIPTION_FRAGMENTS if fragment not in lowered]
    if missing:
        errors.append(
            _issue(
                "description_text",
                "missing_html_section",
                "Description is missing required sections: " + ", ".join(missing) + ".",
            )
        )
    if "<p" not in value.lower() or "</p>" not in value.lower():
        errors.append(
            _issue(
                "description_text",
                "html_structure",
                "Description must use paragraph HTML lines.",
            )
        )


def _validate_forbidden_terms(
    draft: dict[str, Any],
    policy_pack: dict[str, Any],
    errors: list[ValidationIssue],
) -> None:
    forbidden = _forbidden_terms(policy_pack)
    if not forbidden:
        return
    fields = {
        "title": draft.get("title") or "",
        "bullets": " ".join(draft.get("bullets") or []),
        "description_text": draft.get("description_text") or "",
        "search_terms": " ".join(draft.get("search_terms") or []),
    }
    for field_name, text in fields.items():
        matches = _matching_terms(text, forbidden)
        if matches:
            errors.append(
                _issue(
                    field_name,
                    "forbidden_term",
                    f"Field contains forbidden terms: {', '.join(matches)}.",
                )
            )


def _validate_missing_facts(
    draft: dict[str, Any],
    policy_pack: dict[str, Any],
    errors: list[ValidationIssue],
) -> None:
    missing_facts = {str(item).lower() for item in policy_pack.get("missing_facts") or []}
    text = _all_copy_text(draft).lower()
    evidence_terms = _flatten_text((policy_pack.get("claims_policy") or {}).get("requires_evidence"))
    evidence_matches = _matching_terms(text, evidence_terms)
    if evidence_matches:
        errors.append(
            _issue(
                "description_text",
                "claim_requires_evidence",
                "Copy contains claims that require user evidence: "
                + ", ".join(evidence_matches)
                + ".",
            )
        )
    if not missing_facts:
        return
    guarded_terms = {
        "materials": ["cotton", "steel", "stainless steel", "plastic", "silicone", "wood", "leather"],
        "size_info": ["inch", "inches", "cm", "mm", "ft", "feet", "oz", "lb", "lbs", "kg"],
        "certification": ["certified", "fda", "ce", "rohs", "ul listed"],
        "warranty": ["warranty", "guarantee", "guaranteed"],
        "target_audience": ["kids", "children", "baby", "pets", "elderly"],
    }
    for fact_name, terms in guarded_terms.items():
        if fact_name not in missing_facts:
            continue
        matches = _matching_terms(text, terms)
        if matches:
            errors.append(
                _issue(
                    "description_text",
                    "unsupported_missing_fact",
                    f"Copy contains terms tied to missing {fact_name}: {', '.join(matches)}.",
                )
            )


def _validate_search_terms(
    draft: dict[str, Any],
    policy_pack: dict[str, Any],
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
) -> None:
    terms = draft.get("search_terms")
    if not isinstance(terms, list):
        return
    forbidden = _forbidden_terms(policy_pack)
    for term in terms:
        matches = _matching_terms(term, forbidden)
        if matches:
            errors.append(
                _issue(
                    "search_terms",
                    "forbidden_term",
                    f"Search term contains forbidden terms: {', '.join(matches)}.",
                )
            )
    title = str(draft.get("title") or "").strip().lower()
    repeated = [term for term in terms if title and str(term).strip().lower() == title]
    if repeated:
        warnings.append(
            ValidationIssue(
                field="search_terms",
                code="title_repetition",
                message="Search terms repeat the full title.",
                severity="soft",
            )
        )


def _forbidden_terms(policy_pack: dict[str, Any]) -> list[str]:
    keyword_plan = policy_pack.get("keyword_plan") if isinstance(policy_pack, dict) else {}
    claims_policy = policy_pack.get("claims_policy") if isinstance(policy_pack, dict) else {}
    return _dedupe_text(
        _flatten_text((keyword_plan or {}).get("avoid"))
        + _flatten_text((claims_policy or {}).get("forbidden_claims"))
    )


def _all_copy_text(draft: dict[str, Any]) -> str:
    return " ".join(
        [
            str(draft.get("title") or ""),
            " ".join(draft.get("bullets") or []),
            str(draft.get("description_text") or ""),
            " ".join(draft.get("search_terms") or []),
        ]
    )


def _matching_terms(text: str, terms: list[str]) -> list[str]:
    matches = []
    lowered = text.lower()
    for term in terms:
        normalized = term.lower().strip()
        if not normalized:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", lowered):
            matches.append(term)
    return matches


def _flatten_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_flatten_text(item))
        return flattened
    if isinstance(value, dict):
        return _flatten_text(list(value.values()))
    return [str(value).strip()] if str(value).strip() else []


def _dedupe_text(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = " ".join(str(value).split())
        normalized = cleaned.lower()
        if not cleaned or normalized in seen:
            continue
        seen.add(normalized)
        result.append(cleaned)
    return result


def _issue(field: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(field=field, code=code, message=message, severity="hard")
