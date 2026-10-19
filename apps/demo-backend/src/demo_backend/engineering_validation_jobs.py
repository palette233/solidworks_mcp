"""Independent engineering validation jobs for immutable Demo checkpoints.

These jobs never rebuild or move CAD components.  They bind to the exact bytes
of one previously committed Demo assembly, run the selected engineering gate,
and then attach a separate engineering checkpoint to the source assembly job.
A rejected or failed validation must not invalidate, quarantine, or delete the
source Demo artifact.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from .semantic_assembly_jobs import AssemblyJobError, DurableAssemblyJobStore


ENGINEERING_VALIDATION_SCHEMA = "engineering-validation-job/v1"
TERMINAL_STATUSES = {"succeeded", "rejected", "failed"}
EngineeringGate = Callable[[dict[str, Any], dict[str, Any], Path, Path | None], dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise AssemblyJobError(f"工程验证输入装配体不存在：{resolved}")
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "sizeBytes": stat.st_size,
        "sha256": digest.hexdigest(),
    }


class EngineeringValidationJobStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _dir(self, validation_job_id: str) -> Path:
        if not validation_job_id or any(value in validation_job_id for value in ("/", "\\", "..")):
            raise AssemblyJobError("Invalid engineering validation job id")
        return self.root / validation_job_id

    def _path(self, validation_job_id: str) -> Path:
        return self._dir(validation_job_id) / "engineering-validation.json"

    def load(self, validation_job_id: str) -> dict[str, Any]:
        path = self._path(validation_job_id)
        if not path.is_file():
            raise AssemblyJobError(f"Unknown engineering validation job: {validation_job_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, job: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            job["updatedAt"] = utc_now()
            directory = self._dir(str(job["validationJobId"]))
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / "engineering-validation.json"
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(
                json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            temporary.replace(target)
        return job

    def append_event(self, validation_job_id: str, event_type: str, **payload: Any) -> None:
        row = {"timestamp": utc_now(), "eventType": event_type, **payload}
        with self._lock:
            directory = self._dir(validation_job_id)
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / "events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def create(
        self,
        source_job: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if source_job.get("status") != "succeeded":
            raise AssemblyJobError("只有成功的Demo装配任务可以发起独立工程验证。")
        checkpoint = source_job.get("demoCheckpoint") or source_job.get("lastCommittedCheckpoint") or {}
        assembly_path = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
        identity = file_identity(assembly_path)
        source_job_id = str(source_job.get("jobId") or "")
        project_id = str(source_job.get("projectId") or "project02")
        key = idempotency_key or hashlib.sha256(
            json.dumps(
                {
                    "sourceJobId": source_job_id,
                    "sourceCheckpoint": checkpoint.get("committedAt"),
                    "assemblySha256": identity["sha256"],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        with self._lock:
            for path in self.root.glob("*/engineering-validation.json"):
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("idempotencyKey") == key:
                    return existing
            validation_job_id = f"{project_id}-engineering-validation-{uuid4().hex[:12]}"
            now = utc_now()
            job = {
                "schemaVersion": ENGINEERING_VALIDATION_SCHEMA,
                "validationJobId": validation_job_id,
                "projectId": project_id,
                "sourceJobId": source_job_id,
                "idempotencyKey": key,
                "status": "queued",
                "collisionStatus": "not_evaluated",
                "createdAt": now,
                "updatedAt": now,
                "startedAt": None,
                "completedAt": None,
                "durationSeconds": None,
                "sourceDemoCheckpoint": checkpoint,
                "sourceAssemblyIdentity": identity,
                "engineeringCheckpoint": None,
                "evidencePath": None,
                "error": None,
            }
            self.save(job)
            self.append_event(validation_job_id, "engineering-validation-created")
            return job


def run_engineering_validation_job(
    *,
    validation_store: EngineeringValidationJobStore,
    assembly_store: DurableAssemblyJobStore,
    validation_job_id: str,
    hard_gate: EngineeringGate,
) -> dict[str, Any]:
    """Validate one immutable Demo assembly and update only validation fields."""

    started = perf_counter()
    job = validation_store.load(validation_job_id)
    if job.get("status") in TERMINAL_STATUSES:
        return job
    if job.get("status") != "queued":
        raise AssemblyJobError(
            f"工程验证任务{validation_job_id}不能从{job.get('status')}运行。"
        )
    job["status"] = "running"
    job["startedAt"] = utc_now()
    validation_store.save(job)
    validation_store.append_event(validation_job_id, "engineering-validation-started")

    try:
        source_job = assembly_store.load(str(job["sourceJobId"]))
        checkpoint = source_job.get("demoCheckpoint") or source_job.get("lastCommittedCheckpoint") or {}
        expected_checkpoint = job.get("sourceDemoCheckpoint") or {}
        if source_job.get("status") != "succeeded":
            raise AssemblyJobError("来源Demo任务已不再处于成功状态。")
        if str(checkpoint.get("assemblyPath") or "") != str(
            expected_checkpoint.get("assemblyPath") or ""
        ) or str(checkpoint.get("committedAt") or "") != str(
            expected_checkpoint.get("committedAt") or ""
        ):
            raise AssemblyJobError("来源Demo检查点已变化，禁止验证旧绑定。")

        assembly_path = Path(str(expected_checkpoint.get("assemblyPath") or "")).resolve()
        before = file_identity(assembly_path)
        if before != job.get("sourceAssemblyIdentity"):
            raise AssemblyJobError("来源Demo装配体字节已变化，必须重新创建工程验证任务。")

        synthetic_job = {"jobId": validation_job_id}
        synthetic_step = {
            "stepId": "full-demo-checkpoint",
            "moduleToken": "FULL",
            "attemptCount": 1,
        }
        gate = hard_gate(synthetic_job, synthetic_step, assembly_path, None)
        after = file_identity(assembly_path)
        if after != before:
            raise AssemblyJobError("工程验证过程中来源Demo装配体发生变化，结果作废。")

        accepted = gate.get("accepted") is True
        evidence_path = str(gate.get("evidencePath") or "")
        job["status"] = "succeeded" if accepted else "rejected"
        job["collisionStatus"] = "passed" if accepted else "rejected"
        job["evidencePath"] = evidence_path or None
        job["completedAt"] = utc_now()
        job["durationSeconds"] = round(perf_counter() - started, 6)
        job["error"] = None if accepted else str(gate.get("message") or "工程碰撞门禁拒绝。")

        source_job["collisionStatus"] = job["collisionStatus"]
        source_job["collisionValidation"] = {
            "validationJobId": validation_job_id,
            "status": job["status"],
            "evidencePath": job["evidencePath"],
            "completedAt": job["completedAt"],
            "sourceAssemblyIdentity": before,
        }
        if accepted:
            engineering_checkpoint = {
                **checkpoint,
                "validationProfile": "engineering",
                "collisionStatus": "passed",
                "validationEvidenceKind": "collision_hard_gate",
                "evidencePath": evidence_path,
                "validatedAt": job["completedAt"],
                "sourceValidationJobId": validation_job_id,
                "sourceAssemblyIdentity": before,
            }
            job["engineeringCheckpoint"] = engineering_checkpoint
            source_job["engineeringCheckpoint"] = engineering_checkpoint
        else:
            # Preserve the immutable Demo checkpoint and assembly success.
            job["engineeringCheckpoint"] = None
            source_job["engineeringCheckpoint"] = None
        assembly_store.save(source_job)
        from .assembly_evidence_manifest import write_job_evidence_manifest

        write_job_evidence_manifest(
            source_job,
            assembly_store._dir(str(source_job["jobId"])),
        )
        validation_store.save(job)
        validation_store.append_event(
            validation_job_id,
            "engineering-validation-completed",
            status=job["status"],
            collisionStatus=job["collisionStatus"],
            evidencePath=job["evidencePath"],
        )
        return job
    except Exception as exc:
        job["status"] = "failed"
        job["collisionStatus"] = "not_evaluated"
        job["completedAt"] = utc_now()
        job["durationSeconds"] = round(perf_counter() - started, 6)
        job["error"] = str(exc)
        validation_store.save(job)
        validation_store.append_event(
            validation_job_id, "engineering-validation-failed", error=str(exc)
        )
        return job
