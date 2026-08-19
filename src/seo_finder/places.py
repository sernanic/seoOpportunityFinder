from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .config import Settings, settings
from .models import Business

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    (
        "places.id",
        "places.displayName.text",
        "places.formattedAddress",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.rating",
        "places.userRatingCount",
        "places.primaryType",
        "nextPageToken",
    )
)


class PlacesAPIError(ValueError):
    """Raised when Google Places rejects a discovery request."""


THIRD_PARTY_WEBSITE_HOSTS = {
    "acuityscheduling.com",
    "booksy.com",
    "business.site",
    "facebook.com",
    "fresha.com",
    "glossgenius.com",
    "google.com",
    "instagram.com",
    "linktr.ee",
    "linkedin.com",
    "mapquest.com",
    "mindbodyonline.com",
    "schedulicity.com",
    "square.site",
    "squareup.com",
    "styleseat.com",
    "vagaro.com",
    "yellowpages.com",
    "yelp.com",
}


def is_independently_controlled_website(url: str | None) -> bool:
    """Return whether a URL appears to be the business's site, not a hosted profile."""
    if not url:
        return False
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return bool(hostname) and not any(
        hostname == blocked or hostname.endswith(f".{blocked}")
        for blocked in THIRD_PARTY_WEBSITE_HOSTS
    )


@dataclass
class DiscoveryResult:
    businesses: list[Business]
    queries: int
    api_requests: int


class PlacesClient:
    def __init__(
        self,
        api_key: str | None = None,
        config: Settings = settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or config.google_places_api_key
        self.config = config
        self._client = client

    async def search(
        self,
        city: str,
        niches: list[str],
        *,
        pages_per_niche: int = 1,
        page_size: int = 20,
    ) -> DiscoveryResult:
        if not self.api_key:
            raise PlacesAPIError(
                "GOOGLE_PLACES_API_KEY is missing. Add it to .env or export it in your shell."
            )
        if not niches:
            raise PlacesAPIError("At least one niche is required.")
        if not 1 <= pages_per_niche <= 3:
            raise PlacesAPIError("pages_per_niche must be between 1 and 3.")
        if not 1 <= page_size <= 20:
            raise PlacesAPIError("page_size must be between 1 and 20.")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.request_timeout_seconds)
        found: dict[str, Business] = {}
        request_count = 0
        try:
            for niche in niches:
                page_token: str | None = None
                for _ in range(pages_per_niche):
                    body: dict[str, str | int] = {
                        "textQuery": f"{niche} in {city}",
                        "pageSize": page_size,
                    }
                    if page_token:
                        body["pageToken"] = page_token
                    try:
                        response = await client.post(TEXT_SEARCH_URL, headers=headers, json=body)
                    except httpx.HTTPError as exc:
                        raise PlacesAPIError(f"Could not reach Google Places: {exc}") from exc
                    request_count += 1
                    if response.status_code >= 400:
                        try:
                            message = response.json().get("error", {}).get("message")
                        except ValueError:
                            message = None
                        raise PlacesAPIError(
                            f"Google Places returned HTTP {response.status_code}: "
                            f"{message or 'request failed'}"
                        )
                    payload = response.json()
                    for place in payload.get("places", []):
                        place_id = place.get("id")
                        name = place.get("displayName", {}).get("text")
                        if not place_id or not name:
                            continue
                        candidate = Business(
                            place_id=place_id,
                            name=name,
                            website=place.get("websiteUri") or None,
                            address=place.get("formattedAddress"),
                            phone=place.get("nationalPhoneNumber"),
                            rating=place.get("rating"),
                            review_count=place.get("userRatingCount", 0),
                            business_type=place.get("primaryType") or niche,
                        )
                        existing = found.get(place_id)
                        if existing is None or (
                            existing.website is None and candidate.website is not None
                        ):
                            found[place_id] = candidate
                    page_token = payload.get("nextPageToken")
                    if not page_token:
                        break
        finally:
            if owns_client:
                await client.aclose()
        return DiscoveryResult(
            businesses=list(found.values()), queries=len(niches), api_requests=request_count
        )
