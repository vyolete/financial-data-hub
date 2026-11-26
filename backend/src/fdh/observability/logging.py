"""JSON logs on stderr with the run identifier. Credentials and bodies are removed."""

import json
import logging
import re
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

HIDDEN = "[hidden]"
# Libraries that install their own plain-text handlers.
_ROUTED = ("uvicorn", "uvicorn.error", "uvicorn.access", "alembic")
_run_id: ContextVar[str | None] = ContextVar("fdh_run_id", default=None)

_SENSITIVE_WORD = r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|credential)"
_SENSITIVE_KEY = re.compile(rf"{_SENSITIVE_WORD}|^headers$|body", re.IGNORECASE)
_PATTERNS = (
    # credentials embedded in a URL
    (re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"), HIDDEN),
    # "Bearer <value>" and "Basic <value>"
    (re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE), rf"\1 {HIDDEN}"),
    # key=value, key: value and query parameters
    (
        re.compile(
            rf"([\w.-]*{_SENSITIVE_WORD}[\w.-]*[\"']?\s*[=:]\s*[\"']?)"
            r"(?!Bearer\b|Basic\b)[^\s\"'&,;]+",
            re.IGNORECASE,
        ),
        rf"\1{HIDDEN}",
    ),
)
_STANDARD = frozenset(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "taskName",
    "color_message",  # Uvicorn repeats the message with terminal colour codes
}


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _clean(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): HIDDEN if _SENSITIVE_KEY.search(str(key)) else _clean(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_clean(item) for item in value]
    if value is None or isinstance(value, bool | int | float):
        return value
    return redact(str(value))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        if run_id := _run_id.get():
            entry["run_id"] = run_id
        extras = {k: v for k, v in vars(record).items() if k not in _STANDARD}
        entry.update(_clean(extras))
        if record.exc_info and record.exc_info[0]:
            # The type and a redacted message only: tracebacks may carry values.
            entry["error_type"] = record.exc_info[0].__name__
            entry["error"] = redact(str(record.exc_info[1]))[:500]
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for name in _ROUTED:
        library = logging.getLogger(name)
        library.handlers, library.propagate = [], True
        library.setLevel(logging.NOTSET)
    # The transport traces connections at DEBUG level: never let it write request details.
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@contextmanager
def run_context(run_id: str) -> Iterator[None]:
    token = _run_id.set(run_id)
    try:
        yield
    finally:
        _run_id.reset(token)
