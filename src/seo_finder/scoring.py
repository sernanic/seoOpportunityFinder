from statistics import mean

from .models import Business, Finding, ScoreBreakdown

CATEGORIES = {
    "technical_gap": {
        "missing_sitemap",
        "broken_pages",
        "noindex",
        "missing_titles",
        "duplicate_titles",
        "missing_meta",
        "missing_canonical",
        "h1_structure",
        "missing_alt",
        "slow_response",
        "no_pages",
    },
    "local_seo_gap": {"city_not_title", "city_not_h1", "missing_schema"},
    "content_gap": {"thin_site", "duplicate_titles", "missing_meta"},
    "conversion_gap": {"phone_not_clickable", "weak_cta", "missing_social_proof"},
}


def _category(findings: list[Finding], codes: set[str]) -> float:
    values = [finding.gap_points for finding in findings if finding.code in codes]
    return round(mean(values), 1) if values else 0.0


def calculate_score(business: Business, findings: list[Finding]) -> ScoreBreakdown:
    values = {name: _category(findings, codes) for name, codes in CATEGORIES.items()}
    visibility = (
        70.0 if business.review_count < 10 else 45.0 if business.review_count < 30 else 20.0
    )
    commercial = min(100.0, 30 + business.review_count * 1.2 + (business.rating or 0) * 6)
    total = (
        values["technical_gap"] * 0.25
        + values["local_seo_gap"] * 0.25
        + values["content_gap"] * 0.20
        + values["conversion_gap"] * 0.15
        + visibility * 0.10
        + commercial * 0.05
    )
    return ScoreBreakdown(
        **values,
        visibility_gap=visibility,
        commercial_value=round(commercial, 1),
        opportunity_score=round(total, 1),
    )
