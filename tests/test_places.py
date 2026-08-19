import json

import httpx
import pytest

from seo_finder.config import Settings
from seo_finder.places import (
    FIELD_MASK,
    PlacesAPIError,
    PlacesClient,
    is_independently_controlled_website,
)


@pytest.mark.asyncio
async def test_search_paginates_maps_and_deduplicates_places():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        assert request.headers["X-Goog-FieldMask"] == FIELD_MASK
        if "pageToken" not in body:
            return httpx.Response(
                200,
                json={
                    "places": [
                        {
                            "id": "place-1",
                            "displayName": {"text": "Halo Salon"},
                            "formattedAddress": "New Bern, NC",
                            "websiteUri": "https://example.com",
                            "nationalPhoneNumber": "(252) 555-0100",
                            "rating": 4.9,
                            "userRatingCount": 312,
                            "primaryType": "hair_salon",
                        }
                    ],
                    "nextPageToken": "page-two",
                },
            )
        return httpx.Response(
            200,
            json={
                "places": [
                    {"id": "place-1", "displayName": {"text": "Halo Salon"}},
                    {"id": "place-2", "displayName": {"text": "Second Salon"}},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await PlacesClient(api_key="test-key", client=client).search(
            "New Bern, NC", ["hair salons"], pages_per_niche=2, page_size=10
        )

    assert result.api_requests == 2
    assert len(result.businesses) == 2
    assert result.businesses[0].place_id == "place-1"
    assert str(result.businesses[0].website) == "https://example.com/"
    assert requests[1]["pageToken"] == "page-two"


@pytest.mark.asyncio
async def test_search_requires_api_key():
    config = Settings.model_construct(google_places_api_key=None)
    with pytest.raises(PlacesAPIError, match="GOOGLE_PLACES_API_KEY"):
        await PlacesClient(api_key=None, config=config).search("New Bern, NC", ["salons"])


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://halosalonnewbern.com", True),
        ("https://the-salon-on-middle.sintra.site", True),
        ("https://book.squareup.com/appointments/example", False),
        ("https://example.glossgenius.com", False),
        ("https://www.facebook.com/example", False),
        (None, False),
    ],
)
def test_independently_controlled_website_detection(url, expected):
    assert is_independently_controlled_website(url) is expected
