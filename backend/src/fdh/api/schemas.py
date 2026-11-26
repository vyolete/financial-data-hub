"""Response models for the read-only catalog API."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, WithJsonSchema, field_validator

from fdh.observability.logging import redact


class Health(BaseModel):
    status: Literal["ok"]


class ErrorFields(BaseModel):
    code: str
    message: str


class Error(BaseModel):
    error: ErrorFields


class PageMeta(BaseModel):
    page: int
    page_size: int = Field(le=100)
    total: int


Permission = Literal["allowed", "denied", "undetermined"]


ReviewStatus = Literal["pending", "verified"]


class License(BaseModel):
    name: str | None
    url: str | None
    note: str | None


class Attribution(BaseModel):
    text: str | None
    data_sources: list[str]
    data_updated_at: datetime | None
    citation_requirement: str | None


class DatasetSummary(BaseModel):
    id: UUID
    source_id: str
    external_id: str
    title: str
    description: str | None
    provider: str
    platform: str
    publisher: str | None
    categories: list[str]
    topics: list[str]
    review_status: ReviewStatus
    licenses: list[License]
    attribution: Attribution
    last_seen_at: datetime


class SourceInfo(BaseModel):
    official_url: Annotated[str, WithJsonSchema({"type": "string", "format": "uri"})]
    verified_at: date
    access_conditions: str | None
    redistribution_conditions: str | None
    license_name: str | None
    license_url: str | None
    terms_url: str | None
    terms_checked_on: date | None


class Locator(BaseModel):
    kind: str
    url: str
    source_field: str
    status: Literal["unverified", "invalid"]


class Observation(BaseModel):
    run_id: UUID
    query_term: str | None
    source_url: str
    observed_at: datetime


class RecentProvenance(BaseModel):
    total: int = Field(ge=0)
    items: list[Observation] = Field(max_length=20)


class DatasetDetail(DatasetSummary):
    tags: list[str]
    official_url: str | None
    created_at: datetime | None
    published_at: datetime | None
    metadata_updated_at: datetime | None
    data_updated_at: datetime | None
    updated_at: datetime | None
    access_conditions: str | None
    redistribution_conditions: str | None
    extraction_permission: Permission
    redistribution_permission: Permission
    source: SourceInfo
    locators: list[Locator]
    first_seen_at: datetime
    provenance: RecentProvenance


RunStatus = Literal["running", "succeeded", "partial", "failed"]


class Run(BaseModel):
    id: UUID
    source_id: str
    status: RunStatus
    truncated: bool
    started_at: datetime
    finished_at: datetime | None
    pages_processed: int
    received: int
    created: int
    updated: int
    unchanged: int
    rejected: int
    failures: int
    requests: int | None
    duration_ms: int | None
    persistence_ms: int | None


class RunQuery(BaseModel):
    query_index: int
    term: str | None
    pages_processed: int
    total_declared: int | None
    truncated: bool


class RunError(BaseModel):
    code: str
    message: str
    query_index: int | None
    http_status: int | None
    attempts: int | None

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, value: str) -> str:
        return redact(value)


class RunDetail(Run):
    rejection_reasons: dict[str, int] | None
    queries: list[RunQuery]
    errors: list[RunError]


class DatasetPage(PageMeta):
    items: list[DatasetSummary] = Field(max_length=100)


class ObservationPage(PageMeta):
    items: list[Observation] = Field(max_length=100)


class ValuePage(PageMeta):
    items: list[str] = Field(max_length=100)


class RunPage(PageMeta):
    items: list[Run] = Field(max_length=100)
