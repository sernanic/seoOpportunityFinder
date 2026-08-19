from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from .export import export_csv
from .models import Business
from .service import audit_business

app = typer.Typer(help="Find evidence-backed local SEO opportunities.")


@app.command()
def audit(
    url: str = typer.Argument(..., help="Business website URL"),
    city: str = typer.Option(..., help="Target city, e.g. 'New Bern'"),
    name: str = typer.Option("Unknown business"),
    output: Path | None = typer.Option(None, help="Optional JSON output path"),
) -> None:
    """Crawl and audit one business website."""
    result = asyncio.run(audit_business(Business(name=name, website=url), city))
    payload = result.model_dump_json(indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
        typer.echo(f"Saved audit to {output}")
    else:
        typer.echo(payload)


@app.command("audit-file")
def audit_file(
    source: Path, city: str = typer.Option(...), output: Path = typer.Option(Path("data/leads.csv"))
) -> None:
    """Audit businesses from a JSON array and export ranked leads to CSV."""
    businesses = [Business.model_validate(item) for item in json.loads(source.read_text())]

    async def run():
        return [await audit_business(business, city) for business in businesses if business.website]

    results = asyncio.run(run())
    export_csv(results, output)
    typer.echo(f"Exported {len(results)} ranked leads to {output}")


if __name__ == "__main__":
    app()
