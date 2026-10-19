from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVIDENCE_MANIFEST_SCHEMA = "assembly-evidence-manifest/v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evidence_file_record(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    path = Path(value).resolve()
    record: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
    }
    if path.is_file():
        record.update({"sizeBytes": path.stat().st_size, "sha256": _sha256(path)})
    return record


def build_job_evidence_manifest(
    job: dict[str, Any],
    *,
    events_path: Path | None = None,
) -> dict[str, Any]:
    steps = []
    missing: list[str] = []
    job_directory = events_path.parent.resolve() if events_path else None
    for step in job.get("steps") or []:
        checkpoint = step.get("checkpoint") or {}
        assembly = evidence_file_record(checkpoint.get("assemblyPath"))
        validation = evidence_file_record(checkpoint.get("evidencePath"))
        action_values = list(checkpoint.get("cadActionEvidencePaths") or [])
        if not action_values and job_directory:
            action_values = [
                str(path)
                for path in sorted(
                    (job_directory / "cad-working").glob(
                        f"{step.get('stepId')}-attempt*-action*.context-insert.result.json"
                    )
                )
            ]
        action_records = [
            evidence_file_record(str(value))
            for value in action_values
        ]
        if step.get("status") == "succeeded":
            if not assembly or assembly.get("exists") is not True:
                missing.append(f"{step.get('stepId')}:assembly")
            if not validation or validation.get("exists") is not True:
                # Preserve the v1 diagnostic token for existing tooling.  The
                # manifest's validationEvidenceKind disambiguates save/reopen
                # evidence from an engineering collision gate.
                missing.append(f"{step.get('stepId')}:gate-evidence")
            for index, record in enumerate(action_records, start=1):
                if not record or record.get("exists") is not True:
                    missing.append(f"{step.get('stepId')}:cad-action-{index}")
        steps.append(
            {
                "stepId": step.get("stepId"),
                "moduleToken": step.get("moduleToken"),
                "status": step.get("status"),
                "attemptCount": step.get("attemptCount"),
                "inputAssemblyPath": checkpoint.get("inputAssemblyPath"),
                "assembly": assembly,
                # Kept for consumers of v1 while the explicit field tells
                # whether this is save/reopen evidence or a collision gate.
                "gateEvidence": validation,
                "validationEvidence": validation,
                "validationEvidenceKind": checkpoint.get("validationEvidenceKind"),
                "validationProfile": checkpoint.get("validationProfile"),
                "assemblyStatus": checkpoint.get("assemblyStatus"),
                "collisionStatus": checkpoint.get("collisionStatus"),
                "cadActionEvidence": action_records,
                "committedAt": checkpoint.get("committedAt"),
                "attempts": step.get("attempts") or [],
                "error": step.get("error"),
            }
        )

    initial = job.get("initialCommittedCheckpoint") or {}
    preflight_path = events_path.parent / "preflight.json" if events_path else None
    manifest = {
        "schemaVersion": EVIDENCE_MANIFEST_SCHEMA,
        "generatedAt": _utc_now(),
        "jobId": job.get("jobId"),
        "jobSchemaVersion": job.get("schemaVersion"),
        "executionMode": job.get("executionMode"),
        "validationProfile": job.get("validationProfile"),
        "assemblyStatus": job.get("assemblyStatus"),
        "collisionStatus": job.get("collisionStatus"),
        "status": job.get("status"),
        "projectId": (job.get("plan") or {}).get("projectId"),
        "projectProfile": (job.get("plan") or {}).get("projectProfile") or {},
        "intentDigest": (job.get("plan") or {}).get("intentDigest"),
        "planDigest": (job.get("plan") or {}).get("planDigest"),
        "startedAt": job.get("startedAt"),
        "completedAt": job.get("completedAt"),
        "executionDurationSeconds": job.get("executionDurationSeconds"),
        "initialVerifiedCheckpoint": {
            "stepId": initial.get("stepId"),
            "moduleToken": initial.get("moduleToken"),
            "assembly": evidence_file_record(initial.get("assemblyPath")),
            "evidence": evidence_file_record(initial.get("evidencePath")),
        }
        if initial
        else None,
        "steps": steps,
        "events": evidence_file_record(str(events_path.resolve()))
        if events_path and events_path.is_file()
        else None,
        "preflightEvidence": evidence_file_record(str(preflight_path.resolve()))
        if preflight_path and preflight_path.is_file()
        else None,
        "lastCommittedCheckpoint": job.get("lastCommittedCheckpoint"),
        "demoCheckpoint": job.get("demoCheckpoint"),
        "engineeringCheckpoint": job.get("engineeringCheckpoint"),
        "rollback": job.get("rollback"),
        "missingEvidence": missing,
        "evidenceComplete": not missing,
        "staticExecutionAccepted": job.get("status") == "succeeded" and not missing,
    }
    return manifest


def write_job_evidence_manifest(job: dict[str, Any], job_directory: Path) -> Path:
    directory = job_directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest = build_job_evidence_manifest(job, events_path=directory / "events.jsonl")
    target = directory / "evidence-manifest.json"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return target
