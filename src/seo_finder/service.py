from __future__ import annotations

from .audit import audit
from .crawler import Crawler
from .models import AuditResult, Business
from .scoring import calculate_score


async def audit_business(
    business: Business, target_city: str, crawler: Crawler | None = None
) -> AuditResult:
    if business.website is None:
        raise ValueError("Business has no website; route it to the website-development lead list.")
    crawl = await (crawler or Crawler()).crawl(str(business.website))
    findings = audit(business, crawl, target_city)
    return AuditResult(
        business=business,
        pages=crawl.pages,
        findings=findings,
        score=calculate_score(business, findings),
        robots_allowed=crawl.robots_allowed,
        sitemap_found=crawl.sitemap_found,
    )
