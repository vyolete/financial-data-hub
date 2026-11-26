"""Shared catalog query bounds and input validation."""

from typing import Annotated, Any

from fastapi import Query
from pydantic import AfterValidator

from fdh.api.schemas import Error


def without_nul(value: str) -> str:
    if "\x00" in value:
        raise ValueError("invalid character")
    return value


Page = Annotated[int, Query(ge=1, le=10000)]
Size = Annotated[int, Query(ge=1, le=100)]
Text = Annotated[str, Query(max_length=200), AfterValidator(without_nul)]
SourceId = Annotated[str, Query(max_length=100), AfterValidator(without_nul)]
UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    503: {"model": Error, "description": "Database unavailable"}
}
COLLECTION = {**UNAVAILABLE, 422: {"model": Error, "description": "Invalid parameters"}}
RESOURCE = {**COLLECTION, 404: {"model": Error, "description": "Unknown or hidden resource"}}
