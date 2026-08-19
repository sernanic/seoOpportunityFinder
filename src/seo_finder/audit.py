from __future__ import annotations

from collections import Counter

from .crawler import CrawlResult
from .models import Business, Finding, Severity


def audit(business: Business, crawl: CrawlResult, target_city: str) -> list[Finding]:
    pages = crawl.pages
    if not pages:
        return [
            Finding(
                code="no_pages",
                title="Website could not be audited",
                detail="No crawlable HTML pages were found.",
                severity=Severity.HIGH,
                gap_points=100,
            )
        ]
    findings: list[Finding] = []

    def add(
        code: str,
        title: str,
        detail: str,
        severity: Severity,
        points: float,
        url: str | None = None,
    ) -> None:
        findings.append(
            Finding(
                code=code,
                title=title,
                detail=detail,
                severity=severity,
                gap_points=points,
                page_url=url,
            )
        )

    if not crawl.sitemap_found:
        add(
            "missing_sitemap",
            "XML sitemap not found",
            "The conventional /sitemap.xml URL did not return successfully.",
            Severity.MEDIUM,
            45,
        )
    broken = [p for p in pages if p.status_code >= 400]
    if broken:
        add(
            "broken_pages",
            "Broken pages found",
            f"{len(broken)} crawled pages returned an error status.",
            Severity.HIGH,
            80,
        )
    noindex = [p for p in pages if p.has_noindex]
    if noindex:
        add(
            "noindex",
            "Pages excluded from indexing",
            f"{len(noindex)} pages contain a noindex directive.",
            Severity.HIGH,
            90,
        )
    missing_titles = [p for p in pages if not p.title]
    if missing_titles:
        add(
            "missing_titles",
            "Missing page titles",
            f"{len(missing_titles)} of {len(pages)} pages have no title.",
            Severity.HIGH,
            75,
        )
    duplicate_titles = [
        title for title, count in Counter(p.title for p in pages if p.title).items() if count > 1
    ]
    if duplicate_titles:
        add(
            "duplicate_titles",
            "Duplicate page titles",
            f"{len(duplicate_titles)} titles are reused across pages.",
            Severity.MEDIUM,
            55,
        )
    missing_meta = [p for p in pages if not p.meta_description]
    if missing_meta:
        add(
            "missing_meta",
            "Missing meta descriptions",
            f"{len(missing_meta)} of {len(pages)} pages lack a meta description.",
            Severity.MEDIUM,
            55,
        )
    missing_canonical = [p for p in pages if not p.canonical]
    if missing_canonical:
        add(
            "missing_canonical",
            "Missing canonical URLs",
            f"{len(missing_canonical)} pages lack a canonical link.",
            Severity.MEDIUM,
            40,
        )
    bad_h1 = [p for p in pages if len(p.h1s) != 1]
    if bad_h1:
        add(
            "h1_structure",
            "Unclear H1 structure",
            f"{len(bad_h1)} pages have zero or multiple H1 headings.",
            Severity.MEDIUM,
            50,
        )
    images = sum(p.image_count for p in pages)
    missing_alt = sum(p.images_missing_alt for p in pages)
    if missing_alt:
        add(
            "missing_alt",
            "Images missing alternative text",
            f"{missing_alt} of {images} images lack useful alt text.",
            Severity.MEDIUM,
            min(70, 25 + missing_alt * 3),
        )
    home = pages[0]
    city = target_city.lower()
    if city not in (home.title or "").lower():
        add(
            "city_not_title",
            "Target city absent from homepage title",
            f"The homepage title does not mention {target_city}.",
            Severity.HIGH,
            75,
            home.url,
        )
    if not any(city in h.lower() for h in home.h1s):
        add(
            "city_not_h1",
            "Target city absent from homepage H1",
            f"The main heading does not mention {target_city}.",
            Severity.MEDIUM,
            60,
            home.url,
        )
    if not any(p.has_local_business_schema for p in pages):
        add(
            "missing_schema",
            "LocalBusiness schema not found",
            "No crawled page contains LocalBusiness JSON-LD.",
            Severity.MEDIUM,
            60,
        )
    if not home.has_clickable_phone:
        add(
            "phone_not_clickable",
            "Phone number is not click-to-call",
            "No telephone link was found on the homepage.",
            Severity.HIGH,
            70,
            home.url,
        )
    if not (home.has_contact_form or home.has_cta):
        add(
            "weak_cta",
            "Weak contact path",
            "The homepage has no obvious form or action-oriented contact language.",
            Severity.HIGH,
            75,
            home.url,
        )
    if not any(p.has_testimonials for p in pages):
        add(
            "missing_social_proof",
            "Testimonials or reviews not found",
            "The crawl found no clear customer proof section.",
            Severity.MEDIUM,
            45,
        )
    if len(pages) < 4:
        add(
            "thin_site",
            "Very few useful pages found",
            f"Only {len(pages)} crawlable pages were discovered.",
            Severity.HIGH,
            75,
        )
    if home.elapsed_ms > 2500:
        add(
            "slow_response",
            "Slow initial response",
            f"The homepage request took {home.elapsed_ms} ms (not a full Core Web Vitals test).",
            Severity.MEDIUM,
            55,
            home.url,
        )
    return findings
