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
SPECIFICATION_HEADING = "SPECIFICATION"
FEATURES_HEADING = "FEATURES"


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
    _validate_title_policy(normalized, policy_pack, errors)
    _validate_bullet_quality(normalized, policy_pack, errors)
    _validate_description_opening(normalized, errors)
    _validate_features_distinct_from_bullets(normalized, errors)
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
    if "<p" not in value.lower() or "</p>" not in value.lower():
        errors.append(
            _issue(
                "description_text",
                "html_structure",
                "Description must use paragraph HTML lines.",
            )
        )
        return
    _validate_description_section_structure(value, errors)


def _validate_description_section_structure(
    value: str,
    errors: list[ValidationIssue],
) -> None:
    paragraphs = _paragraph_texts(value)
    if not paragraphs:
        return
    if _has_raw_text_outside_paragraphs(value):
        errors.append(
            _issue(
                "description_text",
                "raw_text_outside_paragraphs",
                "Description must not include raw text outside paragraph blocks.",
            )
        )
    spec_index = _find_section_heading(paragraphs, SPECIFICATION_HEADING)
    features_index = _find_section_heading(paragraphs, FEATURES_HEADING)
    if spec_index is None:
        errors.append(
            _issue(
                "description_text",
                "missing_specification_section",
                "Description must include <p><b>SPECIFICATION:</b></p>.",
            )
        )
        return
    if spec_index == 0:
        errors.append(
            _issue(
                "description_text",
                "missing_opening_paragraph",
                "Description must start with an opening paragraph before SPECIFICATION.",
            )
        )
    if features_index is None:
        errors.append(
            _issue(
                "description_text",
                "missing_features_section",
                "Description must include <p><b>FEATURES:</b></p>.",
            )
        )
        return
    if features_index <= spec_index:
        errors.append(
            _issue(
                "description_text",
                "section_order",
                "Description must place SPECIFICATION before FEATURES.",
            )
        )
        return
    specification_items = paragraphs[spec_index + 1 : features_index]
    feature_items = paragraphs[features_index + 1 :]
    if not specification_items:
        errors.append(
            _issue(
                "description_text",
                "empty_specification_section",
                "Description must include specification paragraphs after SPECIFICATION.",
            )
        )
    if not feature_items:
        errors.append(
            _issue(
                "description_text",
                "empty_features_section",
                "Description must include feature paragraphs after FEATURES.",
            )
        )
        return
    invalid_features = [
        item
        for item in feature_items
        if not item.lstrip().startswith("-")
    ]
    if invalid_features:
        errors.append(
            _issue(
                "description_text",
                "feature_paragraph_format",
                "Each FEATURES paragraph must start with a hyphen.",
            )
        )


def _validate_title_policy(
    draft: dict[str, Any],
    policy_pack: dict[str, Any],
    errors: list[ValidationIssue],
) -> None:
    title = str(draft.get("title") or "").strip()
    if not title:
        return
    product_facts = policy_pack.get("product_facts") if isinstance(policy_pack, dict) else {}
    brand = str((product_facts or {}).get("brand") or "").strip()
    if brand:
        if len(brand) > 8:
            errors.append(
                _issue(
                    "title",
                    "brand_length",
                    "Brand from product facts exceeds the 8-character title rule.",
                )
            )
        if not title.lower().startswith(brand.lower()):
            errors.append(
                _issue(
                    "title",
                    "brand_position",
                    "Title must start with the verified brand.",
                )
            )


def _validate_bullet_quality(
    draft: dict[str, Any],
    policy_pack: dict[str, Any],
    errors: list[ValidationIssue],
) -> None:
    bullets = draft.get("bullets")
    if not isinstance(bullets, list) or not all(isinstance(item, str) for item in bullets):
        return
    for left_index, left in enumerate(bullets):
        for right_index, right in enumerate(bullets[left_index + 1 :], start=left_index + 1):
            similarity = _jaccard_similarity(left, right)
            if similarity > 0.7:
                errors.append(
                    _issue(
                        "bullets",
                        "bullet_duplicate_similarity",
                        (
                            "Bullet "
                            f"{left_index + 1} and bullet {right_index + 1} are too similar."
                        ),
                    )
                )
    core_features = _flatten_text((policy_pack.get("product_facts") or {}).get("core_features"))
    if not core_features:
        return
    for bullet_index, bullet in enumerate(bullets, start=1):
        for feature in core_features:
            if _is_near_copy(bullet, feature):
                errors.append(
                    _issue(
                        "bullets",
                        "bullet_core_feature_copy",
                        (
                            f"Bullet {bullet_index} is too close to a core feature; "
                            "it should synthesize product facts into buyer benefits."
                        ),
                    )
                )
                break


def _validate_description_opening(
    draft: dict[str, Any],
    errors: list[ValidationIssue],
) -> None:
    title = str(draft.get("title") or "")
    bullets = draft.get("bullets") if isinstance(draft.get("bullets"), list) else []
    opening = _first_paragraph_text(str(draft.get("description_text") or ""))
    if not opening:
        return
    if title and _jaccard_similarity(opening, title) > 0.65:
        errors.append(
            _issue(
                "description_text",
                "description_opening_matches_title",
                "Description opening is too similar to the title.",
            )
        )
    bullet_text = " ".join(item for item in bullets if isinstance(item, str))
    if bullet_text and _jaccard_similarity(opening, bullet_text) < 0.03:
        errors.append(
            _issue(
                "description_text",
                "description_opening_missing_bullet_summary",
                "Description opening should summarize the bullet-point benefits.",
            )
        )


def _validate_features_distinct_from_bullets(
    draft: dict[str, Any],
    errors: list[ValidationIssue],
) -> None:
    bullets = draft.get("bullets") if isinstance(draft.get("bullets"), list) else []
    features = _feature_paragraphs(str(draft.get("description_text") or ""))
    if not bullets or not features:
        return
    for feature_index, feature in enumerate(features, start=1):
        for bullet_index, bullet in enumerate(bullets, start=1):
            if not isinstance(bullet, str):
                continue
            if _jaccard_similarity(feature, bullet) > 0.65:
                errors.append(
                    _issue(
                        "description_text",
                        "features_duplicate_bullets",
                        (
                            f"Feature {feature_index} is too similar to bullet "
                            f"{bullet_index}."
                        ),
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
    evidence_terms = _flatten_text(
        (policy_pack.get("claims_policy") or {}).get("requires_evidence")
    )
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
        "materials": [
            "cotton",
            "steel",
            "stainless steel",
            "plastic",
            "silicone",
            "wood",
            "leather",
        ],
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


def _is_near_copy(value: str, source: str) -> bool:
    normalized_value = _normalize_space(value).lower()
    normalized_source = _normalize_space(source).lower()
    if not normalized_value or not normalized_source:
        return False
    if normalized_source in normalized_value or normalized_value in normalized_source:
        return True
    return _jaccard_similarity(value, source) > 0.8


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1
    ]


def _first_paragraph_text(value: str) -> str:
    paragraphs = _paragraph_texts(value)
    return paragraphs[0] if paragraphs else _strip_html(value).strip()


def _feature_paragraphs(value: str) -> list[str]:
    paragraphs = _paragraph_texts(value)
    for index, paragraph in enumerate(paragraphs):
        if paragraph.strip().lower().rstrip(":") == "features":
            return paragraphs[index + 1 :]
    return []


def _find_section_heading(paragraphs: list[str], heading: str) -> int | None:
    normalized_heading = heading.strip().upper().rstrip(":")
    for index, paragraph in enumerate(paragraphs):
        if _normalize_heading(paragraph) == normalized_heading:
            return index
    return None


def _normalize_heading(value: str) -> str:
    return _normalize_space(value).strip().upper().rstrip(":")


def _has_raw_text_outside_paragraphs(value: str) -> bool:
    remainder = re.sub(
        r"<p\b[^>]*>.*?</p>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return bool(_normalize_space(_strip_html(remainder)))


def _paragraph_texts(value: str) -> list[str]:
    matches = re.findall(r"<p\b[^>]*>(.*?)</p>", value, flags=re.IGNORECASE | re.DOTALL)
    return [
        _normalize_space(_strip_html(match))
        for match in matches
        if _normalize_space(_strip_html(match))
    ]


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def _normalize_space(value: str) -> str:
    return " ".join(str(value).split())


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
