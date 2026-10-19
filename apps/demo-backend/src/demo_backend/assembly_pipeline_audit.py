from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from .project_assembly_profile import load_project_assembly_profile
from .semantic_assembly_cad_runner import build_live_cad_step_specs
from .semantic_assembly_sequence import load_project02_ordered_assembly_closure


AUDIT_SCHEMA = "natural-language-cad-assembly-pipeline-audit/v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def audit_project02_assembly_pipeline(workspace: Path) -> dict[str, Any]:
    started = perf_counter()
    workspace = workspace.resolve()
    profile = load_project_assembly_profile("project02")
    closure = load_project02_ordered_assembly_closure(workspace)
    blocking: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, evidence: Any, message: str) -> None:
        checks.append(
            {
                "id": check_id,
                "passed": bool(passed),
                "evidence": evidence,
                "message": message,
            }
        )
        if not passed:
            blocking.append(message)

    expected_sequence = profile["validatedSequence"]
    observed_sequence = closure.get("sequence") or []
    check(
        "profile-sequence-matches-closure",
        observed_sequence == expected_sequence,
        {"expected": expected_sequence, "observed": observed_sequence},
        "项目配置顺序与最新CAD闭包顺序不一致。",
    )

    expected_object_count = sum(
        int(row.get("instanceCount", 1)) for row in profile["modules"].values()
    )
    observed_object_count = None
    evidence_path = Path(str(closure.get("evidencePath") or ""))
    if evidence_path.is_file():
        import json

        raw_closure = json.loads(evidence_path.read_text(encoding="utf-8"))
        observed_object_count = raw_closure.get(
            "finalTopLevelObjectCount",
            raw_closure.get("observedTopLevelObjectCountFromPairEvidence"),
        )
    check(
        "top-level-object-count",
        observed_object_count == expected_object_count,
        {"expected": expected_object_count, "observed": observed_object_count},
        "最终顶层CAD对象数量与项目配置不一致。",
    )

    final_assembly = Path(str(closure.get("finalAssemblyPath") or ""))
    check(
        "final-assembly-exists",
        final_assembly.is_file(),
        str(final_assembly),
        "最终SolidWorks装配体不存在。",
    )

    expected_pair_count = expected_object_count * (expected_object_count - 1) // 2
    gate = closure.get("interferenceGate") or {}
    evaluated = int(gate.get("evaluatedPairCount", gate.get("checkedPairCount", 0)) or 0)
    accepted = int(gate.get("acceptedPairCount") or 0)
    check(
        "static-pair-gate-complete",
        evaluated == expected_pair_count and accepted == expected_pair_count,
        {
            "expectedPairCount": expected_pair_count,
            "evaluatedPairCount": evaluated,
            "acceptedPairCount": accepted,
        },
        "静态对象对门禁没有形成完整接受闭包。",
    )

    release = closure.get("releaseDecision") or {}
    check(
        "static-release-allowed",
        release.get("staticTenObjectDemoReleaseAllowed") is True,
        release,
        "静态十对象发布门禁未通过。",
    )
    if release.get("productionReleaseAllowed") is not True:
        warnings.append("生产动态发布尚未通过；静态闭包不得被表述为全行程生产验证。")

    policy = profile.get("collisionPolicy") or {}
    known_tokens = set(profile["modules"])
    invalid_policy_pairs = []
    for key in ("conditionalBrepPairs", "acceptedBaselinePairs"):
        for pair in policy.get(key) or []:
            if len(pair) != 2 or any(str(token).upper() not in known_tokens for token in pair):
                invalid_policy_pairs.append({"kind": key, "pair": pair})
    check(
        "collision-policy-references-known-modules",
        not invalid_policy_pairs,
        invalid_policy_pairs,
        "碰撞策略引用了未登记模组。",
    )

    live_specs_ready = False
    live_specs: dict[str, list[dict[str, str]]] = {}
    try:
        _, live_specs = build_live_cad_step_specs(
            closure,
            required_tokens=set(expected_sequence[1:]),
        )
        live_specs_ready = set(live_specs) == set(expected_sequence[1:])
    except Exception as exc:  # noqa: BLE001 - audit must report, not hide, every preflight failure.
        warnings.append(f"现场CAD动作编译失败：{exc}")
    check(
        "live-cad-actions-compile",
        live_specs_ready,
        {
            token: [action.get("actionKind") for action in actions]
            for token, actions in live_specs.items()
        },
        "至少一个模组缺少可编译的现场CAD动作。",
    )

    return {
        "schemaVersion": AUDIT_SCHEMA,
        "generatedAt": _utc_now(),
        "projectId": "project02",
        "projectProfile": {
            "profileVersion": profile["profileVersion"],
            "profileDigest": profile["profileDigest"],
            "profilePath": profile["profilePath"],
        },
        "checks": checks,
        "blockingIssues": blocking,
        "warnings": warnings,
        "readyForValidatedArtifactReplay": not blocking,
        "readyForLiveCadExecution": not blocking and live_specs_ready,
        "finalAssemblyPath": str(final_assembly),
        "closureEvidencePath": str(evidence_path),
        "timingSeconds": {"total": round(perf_counter() - started, 6)},
    }
