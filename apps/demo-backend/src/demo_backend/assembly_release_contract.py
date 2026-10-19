"""Uniform static/live/dynamic release contract for every project profile."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .project_assembly_profile import load_project_assembly_profile


SCHEMA = "assembly-release-contract/v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _static_closure_success(payload: dict[str, Any]) -> bool:
    release = payload.get("releaseDecision") or {}
    return bool(
        payload.get("success") is True
        or payload.get("macroStaticPassed") is True
        or release.get("staticTenObjectDemoReleaseAllowed") is True
        or release.get("staticSevenModuleDemoReleaseAllowed") is True
    )


def build_assembly_release_contract(workspace: Path, project_id: str) -> dict[str, Any]:
    workspace = workspace.resolve()
    profile = load_project_assembly_profile(project_id)
    boundary = profile.get("releaseBoundary") or {}
    artifacts = profile.get("artifacts") or {}

    static_path = (workspace / str(artifacts.get("fullMachineClosure") or "")).resolve()
    static_document = _load(static_path) if static_path.is_file() else {}
    static_success = static_path.is_file() and _static_closure_success(static_document)
    static_allowed = static_success and boundary.get("staticDemoMayPass") is True

    live_explicit = boundary.get("liveCadApiMayStart")
    if live_explicit is None:
        live_explicit = boundary.get("fullProjectLiveCadReady")
    live_allowed = bool(static_allowed and live_explicit is True)

    dynamic_config = boundary.get("dynamicEvidence") or {}
    dynamic_relative = str(dynamic_config.get("artifact") or "")
    dynamic_path = (workspace / dynamic_relative).resolve() if dynamic_relative else None
    dynamic_exists = bool(dynamic_path and dynamic_path.is_file())
    dynamic_document = _load(dynamic_path) if dynamic_exists and dynamic_path else {}
    dynamic_schema_matches = bool(
        dynamic_exists
        and (
            not dynamic_config.get("schemaVersion")
            or dynamic_document.get("schemaVersion") == dynamic_config.get("schemaVersion")
        )
    )
    dynamic_production_ready = bool(
        dynamic_schema_matches
        and dynamic_document.get("productionReady") is True
        and dynamic_document.get("continuousPathVerified") is True
    )

    confidence_counts = Counter(
        str(row.get("sourceConfidence") or "unknown")
        for row in profile["modules"].values()
    )
    prototype_dependent_count = sum(
        count
        for confidence, count in confidence_counts.items()
        if confidence in {"inferred-from-prototype", "temporary-estimate"}
    )
    dynamic_requirements = [str(value) for value in boundary.get("productionDynamicRequires") or []]
    production_blockers: list[str] = []
    if not static_allowed:
        production_blockers.append("静态整机闭包未通过统一发布契约。")
    if not live_allowed:
        production_blockers.append("现场CAD整链尚未由项目配置显式放行。")
    if not dynamic_exists:
        production_blockers.append("项目配置尚未登记可读取的动态证据闭包。")
    elif not dynamic_schema_matches:
        production_blockers.append("动态证据闭包版本与项目配置不一致。")
    elif not dynamic_production_ready:
        production_blockers.append("动态证据未证明连续路径可用于生产。")
    if prototype_dependent_count:
        production_blockers.append(
            f"仍有{prototype_dependent_count}个模组使用原型推断或临时估计参数。"
        )
    production_blockers.extend(dynamic_requirements)
    production_allowed = not production_blockers

    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": profile["projectId"],
        "profile": {
            "version": profile["profileVersion"],
            "digest": profile["profileDigest"],
            "path": profile["profilePath"],
        },
        "static": {
            "allowed": static_allowed,
            "closureExists": static_path.is_file(),
            "closureSuccess": static_success,
            "evidencePath": str(static_path),
        },
        "liveCad": {
            "allowed": live_allowed,
            "explicitlyReleasedByProfile": live_explicit is True,
        },
        "dynamic": {
            "configured": bool(dynamic_relative),
            "evidenceExists": dynamic_exists,
            "schemaMatches": dynamic_schema_matches,
            "productionReady": dynamic_production_ready,
            "commandGateEnabled": dynamic_config.get("commandGateEnabled") is True,
            "status": dynamic_document.get("status") if dynamic_exists else "DYNAMIC_EVIDENCE_NOT_REGISTERED",
            "continuousPathVerified": dynamic_document.get("continuousPathVerified") is True,
            "verifiedSafeSampledAnglesDegrees": dynamic_document.get("verifiedSafeSampledAnglesDegrees") or [],
            "rejectedSampledAnglesDegrees": dynamic_document.get("rejectedSampledAnglesDegrees") or [],
            "firstObservedCollisionBracketDegrees": dynamic_document.get("firstObservedCollisionBracketDegrees"),
            "knownPairFirstContactRefinement": dynamic_document.get("knownPairFirstContactRefinement"),
            "evidencePath": str(dynamic_path) if dynamic_path else None,
        },
        "parameterAuthority": {
            "confidenceCounts": dict(sorted(confidence_counts.items())),
            "prototypeOrTemporaryModuleCount": prototype_dependent_count,
            "productionAuthorityClosed": prototype_dependent_count == 0,
        },
        "release": {
            "staticDemoAllowed": static_allowed,
            "liveCadAllowed": live_allowed,
            "productionAllowed": production_allowed,
            "productionBlockers": production_blockers,
        },
    }
