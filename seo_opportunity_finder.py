#!/usr/bin/env python3
"""Command-line script for auditing and ranking local-business websites."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow this script to run from a fresh checkout without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from seo_finder.export import export_csv
from seo_finder.models import Business
from seo_finder.places import PlacesClient, is_independently_controlled_website
from seo_finder.service import audit_business


async def audit_one(args: argparse.Namespace) -> int:
    business = Business(
        name=args.name,
        website=args.url,
        address=args.address,
        phone=args.phone,
        rating=args.rating,
        review_count=args.reviews,
        business_type=args.niche,
    )
    result = await audit_business(business, args.city)
    payload = result.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Saved audit to {args.output}")
    else:
        print(payload)
    return 0


async def audit_many(args: argparse.Namespace) -> int:
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError("Input must be a JSON array of business objects.")
    businesses = [Business.model_validate(item) for item in raw]
    without_websites = [business for business in businesses if business.website is None]
    results = []
    for index, business in enumerate((item for item in businesses if item.website), start=1):
        print(f"[{index}] Auditing {business.name}...", file=sys.stderr)
        results.append(await audit_business(business, args.city))
    export_csv(results, args.output)
    print(f"Exported {len(results)} ranked SEO leads to {args.output}")
    if without_websites:
        no_site_output = args.output.with_name(f"{args.output.stem}-no-website.csv")
        no_site_output.parent.mkdir(parents=True, exist_ok=True)
        lines = ["name,address,phone,business_type"]
        for business in without_websites:
            fields = [
                business.name,
                business.address or "",
                business.phone or "",
                business.business_type or "",
            ]
            lines.append(",".join(json.dumps(field) for field in fields))
        no_site_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Exported {len(without_websites)} website-development leads to {no_site_output}")
    return 0


async def discover(args: argparse.Namespace) -> int:
    result = await PlacesClient().search(
        args.city,
        args.niches,
        pages_per_niche=args.pages_per_niche,
        page_size=args.page_size,
    )
    qualified = [
        business
        for business in result.businesses
        if (business.rating or 0) >= args.min_rating and business.review_count >= args.min_reviews
    ]
    businesses = [
        business
        for business in qualified
        if is_independently_controlled_website(str(business.website or ""))
    ]
    businesses_without_websites = []
    for business in qualified:
        if business in businesses:
            continue
        if business.website:
            business = business.model_copy(
                update={"website": None, "external_profile_url": business.website}
            )
        businesses_without_websites.append(business)
    no_website_output = args.no_website_output or args.output.with_name(
        f"{args.output.stem}_no_website{args.output.suffix}"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = [business.model_dump(mode="json", exclude_none=True) for business in businesses]
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    no_website_output.parent.mkdir(parents=True, exist_ok=True)
    no_website_payload = [
        business.model_dump(mode="json", exclude_none=True)
        for business in businesses_without_websites
    ]
    no_website_output.write_text(json.dumps(no_website_payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"Discovered {len(result.businesses)} unique businesses using "
        f"{result.api_requests} API requests."
    )
    print(
        f"Qualified {len(qualified)} with rating >= {args.min_rating} and "
        f"at least {args.min_reviews} reviews; excluded "
        f"{len(result.businesses) - len(qualified)} below those thresholds."
    )
    print(f"Saved {len(businesses)} businesses with websites to {args.output}")
    print(
        f"Saved {len(businesses_without_websites)} businesses without websites "
        f"to {no_website_output}"
    )
    print(
        "Next: python seo_opportunity_finder.py audit-file "
        f"{args.output} --city {json.dumps(args.city)} --output data/leads.csv"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Find evidence-backed local SEO sales opportunities."
    )
    commands = root.add_subparsers(dest="command", required=True)

    one = commands.add_parser("audit", help="Audit one website")
    one.add_argument("url", help="Website URL, including http:// or https://")
    one.add_argument("--city", required=True, help="Target city, such as 'New Bern'")
    one.add_argument("--name", default="Unknown business")
    one.add_argument("--address")
    one.add_argument("--phone")
    one.add_argument("--rating", type=float)
    one.add_argument("--reviews", type=int, default=0)
    one.add_argument("--niche")
    one.add_argument("--output", type=Path, help="Save the full audit as JSON")
    one.set_defaults(handler=audit_one)

    many = commands.add_parser("audit-file", help="Audit a JSON list and export ranked CSV leads")
    many.add_argument("input", type=Path)
    many.add_argument("--city", required=True)
    many.add_argument("--output", type=Path, default=Path("data/leads.csv"))
    many.set_defaults(handler=audit_many)

    places = commands.add_parser("discover", help="Find local businesses with Google Places")
    places.add_argument("--city", required=True, help="City and state, such as 'New Bern, NC'")
    places.add_argument(
        "--niches",
        nargs="+",
        required=True,
        help="One or more quoted niches, such as 'hair salons' 'roofing contractors'",
    )
    places.add_argument("--pages-per-niche", type=int, choices=(1, 2, 3), default=1)
    places.add_argument("--page-size", type=int, choices=range(1, 21), default=20)
    places.add_argument(
        "--min-rating",
        type=float,
        default=3.5,
        help="Minimum Google rating (default: 3.5)",
    )
    places.add_argument(
        "--min-reviews",
        type=int,
        default=5,
        help="Minimum Google review count (default: 5)",
    )
    places.add_argument("--output", type=Path, default=Path("data/businesses.json"))
    places.add_argument(
        "--no-website-output",
        type=Path,
        help="Optional path for no-website leads; defaults beside --output",
    )
    places.set_defaults(handler=discover)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return asyncio.run(args.handler(args))
    except (TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
