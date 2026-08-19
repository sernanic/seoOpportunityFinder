import asyncio
import json
from collections import deque
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .config import Settings, settings
from .models import PageEvidence


@dataclass
class CrawlResult:
    pages: list[PageEvidence]
    robots_allowed: bool
    sitemap_found: bool


def _normalize(url: str) -> str:
    clean, _ = urldefrag(url)
    parsed = urlparse(clean)
    path = parsed.path or "/"
    return parsed._replace(path=path.rstrip("/") or "/", query="").geturl()


def _is_priority_path(url: str) -> bool:
    return any(
        word in urlparse(url).path.lower()
        for word in (
            "service",
            "about",
            "contact",
            "location",
            "area",
            "project",
            "blog",
        )
    )


def parse_page(url: str, status_code: int, html: str, elapsed_ms: int = 0) -> PageEvidence:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    description = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
    robots = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "robots"})
    canonical = soup.find("link", attrs={"rel": lambda x: x and "canonical" in x})
    links = []
    origin = urlparse(url).netloc
    for anchor in soup.find_all("a", href=True):
        target = _normalize(urljoin(url, anchor["href"]))
        if urlparse(target).scheme in {"http", "https"} and urlparse(target).netloc == origin:
            links.append(target)
    schemas = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            schemas.append(json.loads(script.string or "{}"))
        except json.JSONDecodeError:
            continue
    schema_text = json.dumps(schemas).lower()
    visible_text = soup.get_text(" ", strip=True)
    lower_text = visible_text.lower()
    images = soup.find_all("img")
    return PageEvidence(
        url=url,
        status_code=status_code,
        title=title,
        meta_description=description.get("content", "").strip() if description else None,
        canonical=canonical.get("href") if canonical else None,
        h1s=[h.get_text(" ", strip=True) for h in soup.find_all("h1")],
        image_count=len(images),
        images_missing_alt=sum(not image.get("alt", "").strip() for image in images),
        internal_links=list(dict.fromkeys(links)),
        has_noindex="noindex" in (robots.get("content", "").lower() if robots else ""),
        has_local_business_schema="localbusiness" in schema_text,
        has_clickable_phone=bool(soup.select_one('a[href^="tel:"]')),
        has_contact_form=bool(soup.find("form")),
        has_cta=any(
            term in lower_text
            for term in ("get a quote", "book now", "contact us", "call now", "schedule")
        ),
        has_testimonials=any(
            term in lower_text for term in ("testimonial", "what our customers say", "reviews")
        ),
        text=visible_text[:20_000],
        elapsed_ms=elapsed_ms,
    )


class Crawler:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    async def crawl(self, start_url: str) -> CrawlResult:
        start_url = _normalize(start_url)
        base = urlparse(start_url)
        robots_url = f"{base.scheme}://{base.netloc}/robots.txt"
        sitemap_url = f"{base.scheme}://{base.netloc}/sitemap.xml"
        headers = {"User-Agent": self.config.user_agent}
        async with httpx.AsyncClient(
            headers=headers, timeout=self.config.request_timeout_seconds, follow_redirects=True
        ) as client:
            robots = RobotFileParser(robots_url)
            robots_allowed = True
            try:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    robots.parse(response.text.splitlines())
                    robots_allowed = robots.can_fetch(self.config.user_agent, start_url)
            except httpx.HTTPError:
                pass
            if not robots_allowed:
                return CrawlResult([], False, False)
            try:
                sitemap_found = (await client.get(sitemap_url)).status_code == 200
            except httpx.HTTPError:
                sitemap_found = False

            queue = deque([start_url])
            visited: set[str] = set()
            pages: list[PageEvidence] = []
            while queue and len(pages) < self.config.max_pages:
                url = queue.popleft()
                if url in visited or (
                    robots.url and not robots.can_fetch(self.config.user_agent, url)
                ):
                    continue
                visited.add(url)
                try:
                    response = await client.get(url)
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        continue
                    page = parse_page(
                        url,
                        response.status_code,
                        response.text,
                        int(response.elapsed.total_seconds() * 1000),
                    )
                    pages.append(page)
                    unseen = [link for link in page.internal_links if link not in visited]
                    queue.extend(sorted(unseen, key=lambda link: not _is_priority_path(link)))
                except httpx.HTTPError:
                    continue
                if self.config.request_delay_seconds:
                    await asyncio.sleep(self.config.request_delay_seconds)
        return CrawlResult(pages, robots_allowed, sitemap_found)
