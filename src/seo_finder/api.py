from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .models import AuditResult, Business
from .service import audit_business

app = FastAPI(title="SEO Opportunity Finder", version="0.1.0")


class AuditRequest(BaseModel):
    business: Business
    target_city: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/audits", response_model=AuditResult)
async def create_audit(request: AuditRequest) -> AuditResult:
    try:
        return await audit_business(request.business, request.target_city)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
