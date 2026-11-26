"""Derived values of dataset metadata."""

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime

from fdh.domain.datasets import DiscoveredDataset


def _encode(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"unexpected metadata value: {type(value).__name__}")


def metadata_hash(dataset: DiscoveredDataset) -> str:
    """Fingerprint of everything the source declared. Any difference means an update."""
    document = json.dumps(asdict(dataset), default=_encode, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def category_keys(categories: Iterable[str], topics: Iterable[str]) -> list[str]:
    """Case-insensitive filter keys; the original values are stored unchanged."""
    return list(dict.fromkeys(value.casefold() for value in (*categories, *topics)))
