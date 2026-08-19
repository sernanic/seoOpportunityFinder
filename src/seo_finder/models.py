from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Business(BaseModel):
    name: str
    place_id: Optional[str] = None
    website: Optional[HttpUrl] = None
    external_profile_url: Optional[HttpUrl] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    rating: Optional[float] = None
    review_count: int = 0
    business_type: Optional[str] = None


class PageEvidence(BaseModel):
    url: str
    status_code: int
    title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical: Optional[str] = None
    h1s: list[str] = Field(default_factory=list)
    image_count: int = 0
    images_missing_alt: int = 0
    internal_links: list[str] = Field(default_factory=list)
    has_noindex: bool = False
    has_local_business_schema: bool = False
    has_clickable_phone: bool = False
    has_contact_form: bool = False
    has_cta: bool = False
    has_testimonials: bool = False
    text: str = ""
    elapsed_ms: int = 0


class Finding(BaseModel):
    code: str
    title: str
    detail: str
    severity: Severity
    gap_points: float = Field(ge=0, le=100)
    page_url: Optional[str] = None


class ScoreBreakdown(BaseModel):
    technical_gap: float
    local_seo_gap: float
    content_gap: float
    conversion_gap: float
    visibility_gap: float
    commercial_value: float
    opportunity_score: float


class AuditResult(BaseModel):
    business: Business
    pages: list[PageEvidence]
    findings: list[Finding]
    score: ScoreBreakdown
    robots_allowed: bool = True
    sitemap_found: bool = False
