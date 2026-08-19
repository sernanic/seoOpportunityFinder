from seo_finder.audit import audit
from seo_finder.crawler import CrawlResult, parse_page
from seo_finder.models import Business
from seo_finder.scoring import calculate_score


def test_parse_page_collects_evidence():
    page = parse_page(
        "https://example.com/",
        200,
        """
        <html><head><title>Electrician in New Bern</title><meta name="description" content="Local help">
        <link rel="canonical" href="https://example.com/"><script type="application/ld+json">{"@type":"LocalBusiness"}</script></head>
        <body><h1>New Bern Electrician</h1><a href="tel:123">Call now</a><img src="x.jpg"><a href="/services">Services</a></body></html>
    """,
    )
    assert page.has_local_business_schema
    assert page.has_clickable_phone
    assert page.images_missing_alt == 1
    assert page.internal_links == ["https://example.com/services"]


def test_audit_and_score_surface_opportunity():
    page = parse_page(
        "http://example.com/", 200, "<html><body><h2>Welcome</h2><img src='x'></body></html>"
    )
    business = Business(
        name="Example Electric", website="http://example.com", review_count=25, rating=4.5
    )
    findings = audit(business, CrawlResult([page], True, False), "New Bern")
    codes = {finding.code for finding in findings}
    assert {
        "missing_sitemap",
        "missing_titles",
        "city_not_title",
        "missing_schema",
        "weak_cta",
        "thin_site",
    } <= codes
    assert calculate_score(business, findings).opportunity_score > 40
