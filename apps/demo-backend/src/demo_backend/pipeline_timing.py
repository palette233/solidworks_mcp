"""Small, serializable wall-clock and monotonic pipeline timing helper."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import time
from typing import Any, Iterator
from uuid import uuid4


def utc_now_iso() -> str:
    """Return a stable UTC timestamp suitable for persisted machine evidence."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class PipelineTiming:
    """Collect stage timestamps and monotonic durations for one pipeline run."""

    def __init__(self, pipeline: str, *, run_id: str | None = None) -> None:
        self.pipeline = pipeline
        self.run_id = run_id or (
            f"{pipeline}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-"
            f"{uuid4().hex[:8]}"
        )
        self.started_at_utc = utc_now_iso()
        self._started = time.perf_counter()
        self._finished_at_utc: str | None = None
        self._duration_seconds: float | None = None
        self.stages: list[dict[str, Any]] = []

    @contextmanager
    def stage(self, name: str, **metadata: Any) -> Iterator[None]:
        started_at_utc = utc_now_iso()
        started = time.perf_counter()
        record: dict[str, Any] = {
            "name": name,
            "sequence": len(self.stages) + 1,
            "startedAtUtc": started_at_utc,
            **metadata,
        }
        try:
            yield
        except Exception as exc:
            record["status"] = "failed"
            record["errorType"] = type(exc).__name__
            raise
        else:
            record["status"] = "completed"
        finally:
            record["finishedAtUtc"] = utc_now_iso()
            record["durationSeconds"] = round(time.perf_counter() - started, 6)
            self.stages.append(record)

    def finish(self, *, status: str = "completed") -> dict[str, Any]:
        if self._finished_at_utc is None:
            self._finished_at_utc = utc_now_iso()
            self._duration_seconds = round(time.perf_counter() - self._started, 6)
        return {
            "schemaVersion": 1,
            "runId": self.run_id,
            "pipeline": self.pipeline,
            "status": status,
            "startedAtUtc": self.started_at_utc,
            "finishedAtUtc": self._finished_at_utc,
            "durationSeconds": self._duration_seconds,
            "stageCount": len(self.stages),
            "stages": [dict(item) for item in self.stages],
        }
