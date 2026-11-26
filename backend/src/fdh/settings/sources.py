"""Load and validate config/sources.toml (contracts/sources-config.md)."""

import tomllib
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Self
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from fdh.domain.locators import is_https_url
from fdh.domain.permissions import Permission
from fdh.domain.sources import (
    KNOWN_PLATFORMS,
    DiscoveryLimits,
    DiscoveryQuery,
    PublicationDecision,
    SourceDefinition,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
LIMIT_FIELDS = (
    "page_size",
    "max_pages",
    "attempt_timeout_s",
    "max_retries",
    "max_retry_after_s",
)


class ConfigError(Exception):
    """The configuration cannot be used. Messages name fields, never values."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Limits(Strict):
    page_size: int | None = Field(default=None, ge=1, le=100, strict=True)
    max_pages: int | None = Field(default=None, ge=1, le=100, strict=True)
    attempt_timeout_s: float | None = Field(default=None, gt=0, le=120)
    max_retries: int | None = Field(default=None, ge=0, le=3, strict=True)
    max_retry_after_s: int | None = Field(default=None, ge=0, le=3600, strict=True)


class Publication(Strict):
    value: Permission = Permission.UNDETERMINED
    declared_by: Text | None = None
    declared_on: date | None = None
    evidence: Text | None = None

    @model_validator(mode="after")
    def decisions_are_audited(self) -> Self:
        audited = self.declared_by and self.declared_on and self.evidence
        if self.value is not Permission.UNDETERMINED and not audited:
            raise ValueError("a decision requires declared_by, declared_on and evidence")
        return self


class Query(Strict):
    term: Text | None = None
    filters: dict[str, str] = Field(default_factory=dict)


class Source(Limits):
    source_id: str = Field(pattern=r"^[a-z0-9-]+$", max_length=100)
    provider: Text
    platform: str
    base_url: str
    allowed_hosts: list[str] = Field(min_length=1)
    official_url: str
    verified_at: date
    attribution: Text | None = None
    access_conditions: Text | None = None
    redistribution_conditions: Text | None = None
    license_name: Text | None = None
    license_url: str | None = None
    terms_url: str | None = None
    terms_checked_on: date | None = None
    options: dict[str, str] = Field(default_factory=dict)
    metadata_publication: Publication = Field(default_factory=Publication)
    queries: list[Query] = Field(min_length=1)

    @model_validator(mode="after")
    def urls_are_safe(self) -> Self:
        if self.platform not in KNOWN_PLATFORMS:
            raise ValueError("unknown platform")
        for name in ("base_url", "official_url", "license_url", "terms_url"):
            value = getattr(self, name)
            if value is not None and not is_https_url(value):
                raise ValueError(f"{name} must be an HTTPS URL without credentials")
        if urlsplit(self.base_url).hostname not in self.allowed_hosts:
            raise ValueError("the host of base_url must be listed in allowed_hosts")
        return self


class Document(Strict):
    defaults: Limits = Field(default_factory=Limits)
    sources: list[Source] = Field(min_length=1)


def _definition(source: Source, defaults: Limits) -> SourceDefinition:
    limits: dict[str, Any] = {}
    for name in LIMIT_FIELDS:
        own, default = getattr(source, name), getattr(defaults, name)
        value = own if own is not None else default
        if value is not None:
            limits[name] = value
    publication = source.metadata_publication
    return SourceDefinition(
        source_id=source.source_id,
        provider=source.provider,
        platform=source.platform,
        base_url=source.base_url,
        allowed_hosts=tuple(source.allowed_hosts),
        official_url=source.official_url,
        verified_at=source.verified_at,
        queries=tuple(DiscoveryQuery(q.term, dict(q.filters)) for q in source.queries),
        limits=DiscoveryLimits(**limits),
        publication=PublicationDecision(
            publication.value,
            publication.declared_by,
            publication.declared_on,
            publication.evidence,
        ),
        attribution=source.attribution,
        access_conditions=source.access_conditions,
        redistribution_conditions=source.redistribution_conditions,
        license_name=source.license_name,
        license_url=source.license_url,
        terms_url=source.terms_url,
        terms_checked_on=source.terms_checked_on,
        options=dict(source.options),
    )


def load_sources(path: Path) -> tuple[SourceDefinition, ...]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"configuration file not found: {path}") from None
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"cannot read {path}: {type(error).__name__}") from None
    try:
        document = Document.model_validate(raw)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(map(str, item['loc'])) or 'file'}: {item['msg']}"
            for item in error.errors(include_input=False, include_url=False)
        )
        raise ConfigError(f"invalid configuration: {details}") from None
    identifiers = [source.source_id for source in document.sources]
    if len(identifiers) != len(set(identifiers)):
        raise ConfigError("invalid configuration: duplicated source_id")
    return tuple(_definition(source, document.defaults) for source in document.sources)
