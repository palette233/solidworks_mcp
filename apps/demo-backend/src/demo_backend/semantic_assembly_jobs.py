"""Durable background-job state machine for ordered assembly execution.

The state machine is deliberately independent of SolidWorks so it can be
exhaustively tested with a fake step runner.  A real runner may invoke the
context-incremental CAD scripts, while the meeting/demo runner binds steps to
already validated artifacts.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4


JOB_SCHEMA = "ordered-assembly-job/v2"
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
RESUMABLE_STATUSES = {"failed", "cancelled", "paused"}


class AssemblyJobError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_key(plan: dict[str, Any], execution_mode: str) -> str:
    return hashlib.sha256(
        canonical_json({"plan": plan, "executionMode": execution_mode}).encode("utf-8")
    ).hexdigest()


def _step_operation(job: dict[str, Any], step: dict[str, Any]) -> str:
    direct = str(step.get("operation") or "").upper()
    if direct:
        return direct
    step_id = str(step.get("stepId") or "")
    return next(
        (
            str(row.get("operation") or "").upper()
            for row in (job.get("plan") or {}).get("steps") or []
            if str(row.get("stepId") or "") == step_id
        ),
        "",
    )


class DurableAssemblyJobStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _dir(self, job_id: str) -> Path:
        if not job_id or any(value in job_id for value in ("/", "\\", "..")):
            raise AssemblyJobError("Invalid job id")
        return self.root / job_id

    def _path(self, job_id: str) -> Path:
        return self._dir(job_id) / "job.json"

    def load(self, job_id: str) -> dict[str, Any]:
        path = self._path(job_id)
        if not path.is_file():
            raise AssemblyJobError(f"Unknown assembly job: {job_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, job: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            job["updatedAt"] = utc_now()
            directory = self._dir(str(job["jobId"]))
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / "job.json"
            temporary = directory / "job.json.tmp"
            temporary.write_text(
                json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            temporary.replace(target)
        return job

    def append_event(self, job_id: str, event_type: str, **payload: Any) -> None:
        row = {"timestamp": utc_now(), "eventType": event_type, **payload}
        with self._lock:
            directory = self._dir(job_id)
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / "events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def quarantine_artifact(self, job_id: str, step_id: str, artifact: Path) -> Path | None:
        """Move an uncommitted step artifact into a recoverable job-local area."""
        artifact = artifact.resolve()
        if not artifact.is_file():
            return None
        quarantine = self._dir(job_id) / "rejected"
        quarantine.mkdir(parents=True, exist_ok=True)
        target = quarantine / f"{step_id}__{artifact.name}"
        if target.exists():
            target = quarantine / f"{step_id}__{uuid4().hex[:8]}__{artifact.name}"
        try:
            shutil.move(str(artifact), str(target))
            mode = "moved"
            original_retained = False
        except OSError as exc:
            # SolidWorks can keep the document locked after a bridge/process
            # failure. Preserve a rejected copy and explicitly record that the
            # working file remains uncommitted instead of losing the job error.
            try:
                shutil.copy2(str(artifact), str(target))
            except OSError:
                return None
            mode = "copied-because-source-locked"
            original_retained = True
            metadata = target.with_suffix(target.suffix + ".quarantine.json")
            metadata.write_text(
                json.dumps(
                    {
                        "schemaVersion": "assembly-job-quarantine/v1",
                        "sourcePath": str(artifact),
                        "rejectedCopyPath": str(target),
                        "mode": mode,
                        "originalRetainedDueToLock": original_retained,
                        "error": str(exc),
                        "recordedAt": utc_now(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return target

    def create(
        self,
        plan: dict[str, Any],
        *,
        execution_mode: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        project_id = str(plan.get("projectId") or "project02").strip().lower()
        if not project_id.startswith("project") or not project_id.replace("-", "").replace("_", "").isalnum():
            raise AssemblyJobError(f"Invalid project id in assembly plan: {project_id!r}")
        key = idempotency_key or request_key(plan, execution_mode)
        with self._lock:
            for path in self.root.glob("*/job.json"):
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("idempotencyKey") == key:
                    return existing
            job_id = f"{project_id}-job-{uuid4().hex[:12]}"
            steps = [
                {
                    "index": index,
                    "stepId": step["stepId"],
                    "moduleToken": step["moduleToken"],
                    "operation": step.get("operation"),
                    "status": "pending",
                    "attemptCount": 0,
                    "attempts": [],
                    "checkpoint": None,
                    "error": None,
                }
                for index, step in enumerate(plan.get("steps") or [])
            ]
            now = utc_now()
            job = {
                "schemaVersion": JOB_SCHEMA,
                "jobId": job_id,
                "projectId": project_id,
                "idempotencyKey": key,
                "executionMode": execution_mode,
                "validationProfile": str(plan.get("validationProfile") or "engineering"),
                "status": "queued",
                "assemblyStatus": "pending",
                "validationStatus": (
                    "pending"
                    if any(
                        str(step.get("operation") or "").upper()
                        == "VERIFY_RELATION"
                        for step in plan.get("steps") or []
                    )
                    else "not_requested"
                ),
                "collisionStatus": "not_evaluated",
                "cancelRequested": False,
                "pauseRequested": False,
                "createdAt": now,
                "updatedAt": now,
                "startedAt": None,
                "completedAt": None,
                "plan": plan,
                "steps": steps,
                "lastCommittedCheckpoint": None,
                "demoCheckpoint": None,
                "engineeringCheckpoint": None,
                "rollback": None,
                "error": None,
                "executionDurationSeconds": 0.0,
            }
            self.save(job)
            self.append_event(job_id, "job-created", executionMode=execution_mode)
            return job

    def request_cancel(self, job_id: str) -> dict[str, Any]:
        job = self.load(job_id)
        if job["status"] in TERMINAL_STATUSES:
            return job
        job["cancelRequested"] = True
        self.save(job)
        self.append_event(job_id, "cancel-requested")
        return job

    def request_pause(self, job_id: str) -> dict[str, Any]:
        job = self.load(job_id)
        if job["status"] in TERMINAL_STATUSES or job["status"] == "paused":
            return job
        job["pauseRequested"] = True
        self.save(job)
        self.append_event(job_id, "pause-requested")
        return job

    def request_start(self, job_id: str) -> tuple[dict[str, Any], bool]:
        """Idempotently mark a queued job for explicit execution scheduling."""
        with self._lock:
            job = self.load(job_id)
            if job["status"] != "queued" or job.get("startedAt"):
                raise AssemblyJobError(
                    f"Job {job_id} cannot start from {job['status']}"
                )
            if job.get("startRequestedAt"):
                return job, False
            job["startRequestedAt"] = utc_now()
            self.save(job)
            self.append_event(job_id, "job-start-requested")
            return job, True

    def seed_verified_checkpoint(
        self,
        job_id: str,
        *,
        step_id: str,
        module_token: str,
        assembly_path: Path,
        evidence_path: Path,
    ) -> dict[str, Any]:
        """Start a new job from an externally verified cumulative checkpoint.

        This is intentionally stricter than assigning ``lastCommittedCheckpoint``
        directly: both the CAD artifact and its evidence must exist, and a job
        may only be seeded before execution.  It lets long live-CAD chains resume
        from a previously accepted stage without pretending that the earlier
        steps were rerun in the new job.
        """
        job = self.load(job_id)
        if job["status"] != "queued" or job.get("startedAt"):
            raise AssemblyJobError("Only a not-yet-started queued job may be seeded")
        assembly = assembly_path.resolve()
        evidence = evidence_path.resolve()
        if not assembly.is_file():
            raise AssemblyJobError(f"Seed assembly does not exist: {assembly}")
        if not evidence.is_file():
            raise AssemblyJobError(f"Seed evidence does not exist: {evidence}")
        checkpoint = {
            "stepId": step_id,
            "moduleToken": module_token,
            "assemblyPath": str(assembly),
            "evidencePath": str(evidence),
            "committedAt": utc_now(),
            "externalVerifiedSeed": True,
        }
        job["initialCommittedCheckpoint"] = checkpoint
        job["lastCommittedCheckpoint"] = checkpoint
        job["demoCheckpoint"] = checkpoint
        job["assemblyStatus"] = "seeded"
        self.save(job)
        self.append_event(job_id, "verified-checkpoint-seeded", **checkpoint)
        return job

    def prepare_resume(self, job_id: str) -> dict[str, Any]:
        job = self.load(job_id)
        if job["status"] not in RESUMABLE_STATUSES:
            raise AssemblyJobError(f"Job {job_id} is not resumable from {job['status']}")
        retrying_validation = False
        for step in job["steps"]:
            if step["status"] in {"failed", "cancelled", "running"}:
                retrying_validation = retrying_validation or (
                    _step_operation(job, step) == "VERIFY_RELATION"
                )
                step["status"] = "pending"
                step["error"] = None
        job.update(
            {
                "status": "queued",
                "cancelRequested": False,
                "pauseRequested": False,
                "startedAt": None,
                "startRequestedAt": None,
                "completedAt": None,
                "error": None,
                "rollback": None,
            }
        )
        if retrying_validation:
            job["validationStatus"] = "pending"
        self.save(job)
        self.append_event(job_id, "job-resumed")
        return job


StepRunner = Callable[[dict[str, Any], dict[str, Any], Path | None], dict[str, Any]]


class AssemblyJobExecutor:
    def __init__(self, store: DurableAssemblyJobStore, step_runner: StepRunner):
        self.store = store
        self.step_runner = step_runner

    def run(self, job_id: str) -> dict[str, Any]:
        run_started = perf_counter()
        job = self.store.load(job_id)
        if job["status"] == "succeeded":
            return job
        if job["status"] not in {"queued", "running"}:
            raise AssemblyJobError(f"Job {job_id} cannot run from {job['status']}")
        job["status"] = "running"
        job["assemblyStatus"] = "in_progress"
        job["startedAt"] = job["startedAt"] or utc_now()
        self.store.save(job)
        self.store.append_event(job_id, "job-started")

        for step_index in range(len(job["steps"])):
            step = job["steps"][step_index]
            if step["status"] == "succeeded":
                continue
            job = self.store.load(job_id)
            step = job["steps"][step_index]
            if job.get("cancelRequested"):
                step["status"] = "cancelled"
                job["status"] = "cancelled"
                job["assemblyStatus"] = (
                    "partial" if job.get("demoCheckpoint") else "cancelled"
                )
                job["completedAt"] = utc_now()
                job["rollback"] = {
                    "mode": "restore-last-committed-checkpoint",
                    "checkpoint": job.get("lastCommittedCheckpoint"),
                }
                job["executionDurationSeconds"] = round(
                    float(job.get("executionDurationSeconds") or 0.0)
                    + perf_counter()
                    - run_started,
                    6,
                )
                self.store.save(job)
                self.store.append_event(job_id, "job-cancelled", stepId=step["stepId"])
                from .assembly_evidence_manifest import write_job_evidence_manifest

                write_job_evidence_manifest(job, self.store._dir(job_id))
                return job
            if job.get("pauseRequested"):
                job["status"] = "paused"
                job["assemblyStatus"] = (
                    "partial" if job.get("demoCheckpoint") else "paused"
                )
                job["completedAt"] = utc_now()
                job["executionDurationSeconds"] = round(
                    float(job.get("executionDurationSeconds") or 0.0)
                    + perf_counter()
                    - run_started,
                    6,
                )
                self.store.save(job)
                self.store.append_event(
                    job_id,
                    "job-paused",
                    nextStepId=step["stepId"],
                    checkpoint=job.get("lastCommittedCheckpoint"),
                )
                from .assembly_evidence_manifest import write_job_evidence_manifest

                write_job_evidence_manifest(job, self.store._dir(job_id))
                return job

            step["status"] = "running"
            step["attemptCount"] += 1
            step["attempts"].append(
                {
                    "attempt": step["attemptCount"],
                    "startedAt": utc_now(),
                    "completedAt": None,
                    "durationSeconds": None,
                }
            )
            attempt_started = perf_counter()
            self.store.save(job)
            self.store.append_event(job_id, "step-started", stepId=step["stepId"])
            checkpoint_path = (
                Path(job["lastCommittedCheckpoint"]["assemblyPath"])
                if job.get("lastCommittedCheckpoint")
                else None
            )
            output: Path | None = None
            try:
                result = self.step_runner(job, step, checkpoint_path)
                # The runner may take minutes.  Reload before committing so a
                # concurrent cancellation request is not overwritten by this
                # worker's older in-memory job snapshot.
                job = self.store.load(job_id)
                step = job["steps"][step_index]
                output_value = str(result.get("assemblyPath") or "").strip()
                output = Path(output_value).resolve() if output_value else None
                if result.get("accepted") is not True:
                    raise AssemblyJobError(str(result.get("message") or "Step hard gate rejected"))
                if output is None or not output.is_file():
                    raise AssemblyJobError(f"Step runner produced no assembly: {output}")
                checkpoint = {
                    "stepId": step["stepId"],
                    "moduleToken": step["moduleToken"],
                    "inputAssemblyPath": str(checkpoint_path.resolve()) if checkpoint_path else None,
                    "assemblyPath": str(output),
                    "evidencePath": result.get("evidencePath"),
                    "cadActionEvidencePaths": list(result.get("cadActionEvidencePaths") or []),
                    "executionMode": job.get("executionMode"),
                    "validationProfile": result.get("validationProfile")
                    or job.get("validationProfile"),
                    "assemblyStatus": result.get("assemblyStatus") or "assembled",
                    "collisionStatus": result.get("collisionStatus") or "not_evaluated",
                    "validationEvidenceKind": result.get("validationEvidenceKind"),
                    "packetId": result.get("packetId"),
                    "packetDigest": result.get("packetDigest"),
                    "manifestDigest": result.get("manifestDigest"),
                    "timingBreakdown": result.get("timingBreakdown") or {},
                    "committedAt": utc_now(),
                }
                step["status"] = "succeeded"
                step["attempts"][-1]["completedAt"] = utc_now()
                step["attempts"][-1]["durationSeconds"] = round(
                    perf_counter() - attempt_started, 6
                )
                step["checkpoint"] = checkpoint
                job["lastCommittedCheckpoint"] = checkpoint
                job["demoCheckpoint"] = checkpoint
                job["assemblyStatus"] = "assembled"
                if _step_operation(job, step) == "VERIFY_RELATION":
                    job["validationStatus"] = "passed"
                job["collisionStatus"] = checkpoint["collisionStatus"]
                if checkpoint["collisionStatus"] == "passed":
                    job["engineeringCheckpoint"] = checkpoint
                self.store.save(job)
                self.store.append_event(job_id, "step-committed", **checkpoint)
                from .assembly_evidence_manifest import write_job_evidence_manifest

                write_job_evidence_manifest(job, self.store._dir(job_id))
            except Exception as exc:
                try:
                    quarantined = (
                        self.store.quarantine_artifact(job_id, step["stepId"], output)
                        if output is not None
                        else None
                    )
                except OSError:
                    quarantined = None
                step["status"] = "failed"
                step["attempts"][-1]["completedAt"] = utc_now()
                step["attempts"][-1]["durationSeconds"] = round(
                    perf_counter() - attempt_started, 6
                )
                step["error"] = str(exc)
                job["status"] = "failed"
                read_only_verification = _step_operation(job, step) == "VERIFY_RELATION"
                if read_only_verification:
                    job["validationStatus"] = "failed"
                job["assemblyStatus"] = (
                    "assembled"
                    if read_only_verification and job.get("demoCheckpoint")
                    else "partial"
                    if job.get("demoCheckpoint")
                    else "failed"
                )
                job["completedAt"] = utc_now()
                job["error"] = str(exc)
                job["rollback"] = {
                    "mode": "restore-last-committed-checkpoint",
                    "checkpoint": job.get("lastCommittedCheckpoint"),
                    "uncommittedOutputAccepted": False,
                    "quarantinedArtifactPath": str(quarantined) if quarantined else None,
                }
                job["executionDurationSeconds"] = round(
                    float(job.get("executionDurationSeconds") or 0.0)
                    + perf_counter()
                    - run_started,
                    6,
                )
                self.store.save(job)
                self.store.append_event(
                    job_id, "step-failed", stepId=step["stepId"], error=str(exc)
                )
                from .assembly_evidence_manifest import write_job_evidence_manifest

                write_job_evidence_manifest(job, self.store._dir(job_id))
                return job

        job["status"] = "succeeded"
        job["assemblyStatus"] = "assembled"
        if job.get("validationStatus") == "pending":
            job["validationStatus"] = "passed"
        job["completedAt"] = utc_now()
        job["executionDurationSeconds"] = round(
            float(job.get("executionDurationSeconds") or 0.0)
            + perf_counter()
            - run_started,
            6,
        )
        self.store.save(job)
        self.store.append_event(job_id, "job-succeeded")
        from .assembly_evidence_manifest import write_job_evidence_manifest

        write_job_evidence_manifest(job, self.store._dir(job_id))
        return job


def validated_artifact_step_runner(
    closure: dict[str, Any], workspace: Path
) -> StepRunner:
    rows = {str(item["moduleToken"]): item for item in closure.get("steps") or []}

    def run(job: dict[str, Any], step: dict[str, Any], _: Path | None) -> dict[str, Any]:
        row = rows.get(str(step["moduleToken"]))
        if not row or row.get("success") is not True:
            raise AssemblyJobError(
                f"No accepted validated artifact for {step['moduleToken']}"
            )
        assembly = Path(str(row.get("assemblyPath") or ""))
        if not assembly.is_absolute():
            assembly = workspace / assembly
        evidence = Path(str(row.get("evidencePath") or ""))
        if not evidence.is_absolute():
            evidence = workspace / evidence
        if not assembly.is_file():
            raise AssemblyJobError(
                f"Validated assembly artifact does not exist for {step['moduleToken']}: {assembly}"
            )
        if not evidence.is_file():
            raise AssemblyJobError(
                f"Validated evidence does not exist for {step['moduleToken']}: {evidence}"
            )
        return {
            "accepted": True,
            "assemblyPath": str(assembly.resolve()),
            "evidencePath": str(evidence.resolve()),
            "mode": "validated_artifact_replay",
        }

    return run
