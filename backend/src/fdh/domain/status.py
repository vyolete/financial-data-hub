"""Outcome of a discovery run."""

from enum import StrEnum


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


def final_status(*, valid: int, rejected: int, failures: int) -> RunStatus:
    """Status of a finished run.

    ``valid`` counts distinct valid datasets recovered. Truncation is deliberately not an
    input: reaching the page limit is not an error.
    """
    if min(valid, rejected, failures) < 0:
        raise ValueError("counts cannot be negative")
    if rejected == 0 and failures == 0:
        return RunStatus.SUCCEEDED
    return RunStatus.PARTIAL if valid > 0 else RunStatus.FAILED
