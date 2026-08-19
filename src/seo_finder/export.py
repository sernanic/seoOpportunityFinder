import csv
from pathlib import Path

from .models import AuditResult


def export_csv(results: list[AuditResult], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "name",
                "website",
                "address",
                "phone",
                "business_type",
                "opportunity_score",
                "pages_crawled",
                "top_findings",
            ],
        )
        writer.writeheader()
        for result in sorted(results, key=lambda item: item.score.opportunity_score, reverse=True):
            writer.writerow(
                {
                    "name": result.business.name,
                    "website": str(result.business.website or ""),
                    "address": result.business.address or "",
                    "phone": result.business.phone or "",
                    "business_type": result.business.business_type or "",
                    "opportunity_score": result.score.opportunity_score,
                    "pages_crawled": len(result.pages),
                    "top_findings": "; ".join(
                        f.title
                        for f in sorted(result.findings, key=lambda f: f.gap_points, reverse=True)[
                            :3
                        ]
                    ),
                }
            )
