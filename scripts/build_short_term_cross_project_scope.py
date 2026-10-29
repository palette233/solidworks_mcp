#!/usr/bin/env python3
"""Build the six-family short-term cross-project assembly readiness report."""

from __future__ import annotations

import json
import hashlib
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_module_substitution import (  # noqa: E402
    build_module_role_overlay,
)
from demo_backend.short_term_cross_project_scope import (  # noqa: E402
    build_short_term_cross_project_scope_readiness,
    validate_short_term_cross_project_scope_readiness,
)


OUTPUT = ROOT / "demo/global_assembly_catalog/short-term-cross-project-scope-v1"
PARAMETERIZED_DATUM_QUEUE_ROOT = ROOT / (
    "demo/cross_project_substitution/parameterized-datum-placement-v1"
)
PARAMETERIZED_DATUM_CATALOG = ROOT / (
    "demo/cross_project_substitution/parameterized-datum-placement-v1/"
    "interface-contract-catalog.json"
)
SIX_ROLE_ROOT = ROOT / "demo/cross_project_substitution/six-role-project03-base-v1"


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _discover_current_parameterized_datum_queue(
    queue_root: Path,
    catalog_digest: str,
) -> tuple[Path, dict[str, Any]]:
    """Select the highest immutable queue version bound to the current catalog."""

    matches: list[tuple[int, Path, dict[str, Any]]] = []
    for path in queue_root.glob("validation-queue-*-v*/validation-queue.json"):
        version_match = re.search(r"-v(\d+)$", path.parent.name)
        if version_match is None:
            continue
        payload = _json(path)
        if payload.get("sourceCatalogDigest") != catalog_digest:
            continue
        expected = hashlib.sha256(
            json.dumps(
                {key: value for key, value in payload.items() if key != "queueDigest"},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if payload.get("queueDigest") != expected:
            raise ValueError(f"当前参数化队列摘要不匹配: {path}")
        matches.append((int(version_match.group(1)), path.resolve(), payload))
    if not matches:
        raise ValueError("没有找到与当前规范接口目录匹配的参数化验证队列。")
    matches.sort(key=lambda row: (row[0], str(row[1])))
    _, path, payload = matches[-1]
    return path, payload


def _support_position_evidence(path: Path, *, cumulative: bool = False) -> dict[str, Any] | None:
    """Read optional new evidence without upgrading its mechanical claim."""
    if not path.is_file():
        return None
    closure = _json(path)
    expected_schema = (
        "p000-support-position-chain-closure/v1" if cumulative
        else "cross-project-wastecup-datum-closure/v1"
    )
    expected_status = "PASSED_SUPPORT_POSITION_CHAIN_DEMO" if cumulative else "PASSED_SUPPORT_POSITION_DEMO"
    if not (
        closure.get("schemaVersion") == expected_schema
        and closure.get("mode") == "support_position_demo"
        and closure.get("holePatternMatchRequired") is False
        and closure.get("actualFixationMethod") == "not_verified"
        and closure.get("directMechanicalInterfaceCompatible", "not_evaluated") in (False, "not_evaluated")
        and closure.get("directMechanicalCompatibilityClaim", False) is False
        and (
            closure.get("directMechanicalCompatibilityClaim") is False if cumulative
            else closure.get("releaseEligibleForDirectMechanicalSubstitution") is False
        )
    ):
        raise ValueError(f"支承定位Demo证据边界或版本不匹配: {path}")
    passed = closure.get("success") is True and closure.get("status") == expected_status
    checks = closure.get("checks") or {}
    assembly_path = Path(closure.get("outputAssemblyPath") or "")
    sequence = (closure.get("moduleSequence") or []) if cumulative else ["A600", "P000"]
    count = closure.get("topLevelModuleCount") if cumulative else 2
    if passed:
        required_chain_checks = {
            "fiveModulesReopened", "upstreamComponentsUnchanged", "upstreamMatesUnchanged",
            "threeActiveTargetMates", "targetNotFixed", "noPoseAnchors", "sourceCheckpointUnchanged",
        }
        if not checks or not all(value is True for value in checks.values()):
            raise ValueError(f"支承定位Demo存在未通过的闭环检查: {path}")
        if not assembly_path.is_file() or hashlib.sha256(assembly_path.read_bytes()).hexdigest() != closure.get("outputAssemblySha256"):
            raise ValueError(f"支承定位Demo输出文件或SHA-256不匹配: {path}")
        if cumulative and not (
            sequence == ["A600", "A800", "A180", "A500", "P000"]
            and count == 5
            and required_chain_checks.issubset(checks)
            and closure.get("sourceStageReused") is True
            and closure.get("reexecutedPacketCount") == 1
        ):
            raise ValueError(f"支承定位累计链缺少五模组清点、前置复用或追加检查: {path}")
    return {
        "chainId": "project02-project05-p000-support-position-chain-v3" if cumulative
        else "project02-project05-p000-support-position-demo-v2",
        "status": "passed" if passed else "failed",
        "evidenceKind": "datum_placement_demo",
        "mode": "support_position_demo",
        "relationExecutionMode": "datum_placement_demo",
        "roles": ["WasteCup"],
        # Five modules cover five roles, not the missing cleaning/weighing family.
        "groupIds": ["base_environment", "transport", "scanner", "calibration", "waste_handling"]
        if cumulative else ["base_environment", "waste_handling"],
        "topLevelModuleCount": count,
        "moduleSequence": sequence,
        "cadEvidenceVerified": passed,
        "cumulativeAssemblyVerified": cumulative and passed,
        "actualFixationMethod": "not_verified",
        "holePatternMatchRequired": False,
        "directMechanicalCompatibilityClaim": False,
        "directMechanicalInterfaceCompatible": False,
        "sourceStageReused": closure.get("sourceStageReused") if cumulative else False,
        "reexecutedPacketCount": closure.get("reexecutedPacketCount") if cumulative else 1,
        "outputAssemblyPath": str(assembly_path),
        "outputAssemblySha256": closure.get("outputAssemblySha256"),
        "closurePath": str(path),
        "closureSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "collisionStatus": "not_evaluated",
    }


def _six_role_support_evidence(path: Path) -> dict[str, Any] | None:
    """Optional AA00 six-role evidence, separate from the previous A600 chain."""
    if not path.is_file():
        return None
    closure = _json(path)
    if not (
        closure.get("schemaVersion") == "six-role-support-position-chain-closure/v1"
        and closure.get("mode") == "support_position_demo"
        and closure.get("actualFixationMethod") == "not_verified"
        and closure.get("holePatternMatchRequired") is False
        and closure.get("directMechanicalCompatibilityClaim") is False
    ):
        raise ValueError(f"六类支承定位累计链证据边界或版本不匹配: {path}")
    passed = closure.get("success") is True and closure.get("status") == "PASSED_SIX_ROLE_SUPPORT_POSITION_CHAIN_DEMO"
    checks = closure.get("checks") or {}
    sequence = closure.get("moduleSequence") or []
    projects = closure.get("crossProjectIds") or []
    roles = closure.get("roleCoverage") or []
    output = Path(closure.get("outputAssemblyPath") or "")
    required = {
        "sixModulesReopened", "upstreamComponentsUnchanged", "upstreamMatesUnchanged",
        "threeActiveTargetMates", "targetNotFixedAndFullyConstrained", "noPoseAnchors",
        "sourceCheckpointUnchanged", "fourDirectPacketsAndOneAppend", "actualOrderBound",
        "supportPolicyPreserved", "signedSupportPositionMatches",
    }
    if passed:
        if not checks or not all(v is True for v in checks.values()) or not required.issubset(checks):
            raise ValueError(f"六类支承定位累计链缺少或未通过关键闭环检查: {path}")
        if not (len(sequence) == 6 and sequence[0] == "AA00" and sequence[-1] == "P000"
                and set(sequence) == {"AA00", "SS00", "AI00", "BD00", "AG00", "P000"}
                and closure.get("topLevelModuleCount") == 6 and closure.get("executedPacketCount") == 5
                and sorted(projects) == ["project01", "project03", "project05"]
                and set(roles) == {"Base", "Transport", "Scanner", "Calibration", "CleaningWeighing", "WasteCup"}):
            raise ValueError(f"六类支承定位累计链模组、项目、角色或执行包清点不匹配: {path}")
        if not output.is_file() or hashlib.sha256(output.read_bytes()).hexdigest() != closure.get("outputAssemblySha256"):
            raise ValueError(f"六类支承定位累计链输出文件或SHA-256不匹配: {path}")
        geometry = closure.get("signedSupportGeometryVerification") or {}
        if not (geometry.get("success") is True and geometry.get("assemblySha256") == closure.get("outputAssemblySha256")
                and bool(geometry.get("checks")) and all(v is True for v in geometry["checks"].values())):
            raise ValueError(f"六类支承定位累计链缺少绑定当前装配体的有符号几何验证: {path}")
    return {
        "chainId": closure.get("chainId"), "status": "passed" if passed else "failed",
        "evidenceKind": "datum_placement_demo", "mode": "support_position_demo",
        "relationExecutionMode": "mixed_direct_installation_and_datum_placement_demo",
        "roles": ["WasteCup"], "roleCoverage": roles,
        "groupIds": ["base_environment", "transport", "scanner", "calibration", "cleaning_weighing", "waste_handling"],
        "targetBaseToken": "AA00", "topLevelModuleCount": closure.get("topLevelModuleCount"),
        "moduleSequence": sequence, "crossProjectIds": projects,
        "cadEvidenceVerified": passed, "cumulativeAssemblyVerified": passed,
        "actualFixationMethod": "not_verified", "holePatternMatchRequired": False,
        "directMechanicalCompatibilityClaim": False, "directMechanicalInterfaceCompatible": False,
        "outputAssemblyPath": str(output), "outputAssemblySha256": closure.get("outputAssemblySha256"),
        "closurePath": str(path), "closureSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "readOnlyVerificationPath": closure.get("readOnlyVerificationPath"),
        "timingSeconds": closure.get("timingSeconds"), "collisionStatus": "not_evaluated",
    }


def _six_role_order_comparison(path: Path, chains: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Only promote a comparison still bound to both actual six-module runs."""
    if not path.is_file():
        return None
    comparison = _json(path)
    if comparison.get("schemaVersion") != "six-role-support-order-comparison/v1":
        raise ValueError(f"六类变序比较版本不匹配: {path}")
    passed = comparison.get("success") is True and comparison.get("status") == "PASSED_SIX_ROLE_ORDER_EQUIVALENCE"
    rows = {Path(row["closurePath"]).parent.name: row for row in chains}
    if passed:
        checks = comparison.get("checks") or {}
        required = {"relativePosesEquivalent", "moduleSourceIdentitiesMatch", "fifteenNamedMatesEach",
                    "mateTypesParametersStatesEquivalent", "actualOrdersDiffer", "bothOutputFilesBoundIndependently"}
        if not checks or not all(v is True for v in checks.values()) or not required.issubset(checks):
            raise ValueError(f"六类变序比较缺少或未通过关键检查: {path}")
        if set(rows) != {"standard", "reordered"} or any(row.get("status") != "passed" for row in rows.values()):
            raise ValueError(f"六类变序比较缺少两条已通过的累计链: {path}")
        if comparison.get("standardOrder") != rows["standard"]["moduleSequence"] or comparison.get("reorderedOrder") != rows["reordered"]["moduleSequence"]:
            raise ValueError(f"六类变序比较顺序与当前闭环不匹配: {path}")
        expected_inputs = {}
        for variant, row in rows.items():
            for field in ("closurePath", "readOnlyVerificationPath"):
                if not row.get(field):
                    raise ValueError(f"六类变序比较输入路径缺失: {path}")
                expected_inputs[(variant, str(Path(row[field]).resolve()))] = Path(row[field])
        inputs = comparison.get("inputEvidence") or []
        actual_inputs = {(row.get("variant"), str(Path(row.get("path") or "").resolve())): row for row in inputs}
        if len(inputs) != 4 or set(actual_inputs) != set(expected_inputs):
            raise ValueError(f"六类变序比较输入绑定不完整: {path}")
        for key, source in expected_inputs.items():
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != actual_inputs[key].get("sha256"):
                raise ValueError(f"六类变序比较输入SHA-256不匹配: {source}")
        bindings = comparison.get("outputBindings") or []
        if len(bindings) != 2 or {row.get("variant") for row in bindings} != set(rows):
            raise ValueError(f"六类变序比较输出绑定不完整: {path}")
        for binding in bindings:
            row = rows[binding["variant"]]
            output_path = Path(row["outputAssemblyPath"])
            if not (binding.get("bound") is True and Path(binding.get("path") or "").resolve() == Path(row["outputAssemblyPath"]).resolve()
                    and output_path.is_file()
                    and binding.get("sha256") == row["outputAssemblySha256"] == hashlib.sha256(output_path.read_bytes()).hexdigest()):
                raise ValueError(f"六类变序比较输出身份不匹配: {path}")
    return {"status": "passed" if passed else "failed", "cadEvidenceVerified": passed,
            "comparisonPath": str(path), "comparisonSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "standardOrder": comparison.get("standardOrder"), "reorderedOrder": comparison.get("reorderedOrder"),
            "durationSeconds": comparison.get("durationSeconds"), "failedChecks": comparison.get("failedChecks") or []}


def _chain_evidence() -> list[dict[str, Any]]:
    project05_job = _json(
        ROOT
        / "demo/global_assembly_contexts/manifest_jobs/"
        "project05-job-72463661a6a2/job.json"
    )
    waste_demo = _json(
        ROOT
        / "demo/cross_project_substitution/wastecup-project05-to-project02-v1/"
        "datum-placement-demo-closure.json"
    )
    waste_gap = _json(
        ROOT
        / "demo/cross_project_substitution/wastecup-project05-to-project02-v1/"
        "mechanical_interface_gap_audit.json"
    )
    waste_attachment_candidate = _json(
        ROOT
        / "demo/cross_project_substitution/wastecup-project05-to-project02-v1/"
        "p000_physical_attachment_candidate.json"
    )
    evidence = [
        {
            "chainId": "project05-complete-seven-addon-v2",
            "status": "passed" if project05_job.get("status") == "succeeded" else "failed",
            "evidenceKind": "released_cumulative_cad_chain",
            "jobId": project05_job.get("jobId"),
            "groupIds": [
                "base_environment",
                "transport",
                "scanner",
                "calibration",
                "cleaning_weighing",
                "waste_handling",
            ],
            "topLevelModuleCount": 8,
            "nonPrototypeInitialPose": True,
            "saveCloseReopenVerified": True,
            "collisionStatus": project05_job.get("collisionStatus"),
        },
        {
            "chainId": "project02-project05-p000-datum-demo",
            "status": "passed" if waste_demo.get("success") is True else "failed",
            "evidenceKind": "datum_placement_demo",
            "roles": ["WasteCup"],
            "groupIds": ["waste_handling"],
            "directMechanicalInterfaceCompatible": False,
            "physicalInterfaceGapStatus": waste_gap["status"],
            "missingPhysicalInterfaceEvidenceCount": len(
                waste_gap["missingEvidence"]
            ),
            "physicalInterfaceNextAction": waste_gap["nextAction"],
            "physicalInterfaceAuditDigest": waste_gap["auditDigest"],
            "sourceAttachmentCandidateStatus": waste_attachment_candidate[
                "status"
            ],
            "sourceAttachmentCandidateKind": waste_attachment_candidate[
                "candidateInterfaceSignature"
            ]["candidateKind"],
            "sourceAttachmentSlotWidthMeters": waste_attachment_candidate[
                "candidateInterfaceSignature"
            ]["slotWidthMeters"],
            "sourceAttachmentSlotSpacingMeters": waste_attachment_candidate[
                "candidateInterfaceSignature"
            ]["slotCenterlineSpacingMeters"],
            "sourceAttachmentMechanicalMeaningConfirmed": (
                waste_attachment_candidate["candidateInterfaceSignature"][
                    "mechanicalMeaningConfirmed"
                ]
            ),
            "sourceAttachmentCandidateDigest": waste_attachment_candidate[
                "candidateDigest"
            ],
            "collisionStatus": waste_demo.get("collisionStatus", "not_evaluated"),
        },
    ]
    waste_root = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"
    for path, cumulative in (
        (waste_root / "support-position-demo-v2/datum-placement-demo-closure.json", False),
        (waste_root / "support-position-chain-v3/chain-closure.json", True),
    ):
        item = _support_position_evidence(path, cumulative=cumulative)
        if item is not None:
            evidence.append(item)
    six_role_chains = []
    for variant in ("standard", "reordered"):
        item = _six_role_support_evidence(SIX_ROLE_ROOT / variant / "chain-closure.json")
        if item is not None:
            evidence.append(item)
            six_role_chains.append(item)
    order_comparison = _six_role_order_comparison(SIX_ROLE_ROOT / "order-comparison-v1/order-comparison.json", six_role_chains)
    if order_comparison is not None:
        for item in six_role_chains:
            item["orderEquivalenceVerified"] = order_comparison["status"] == "passed"
            item["orderComparisonEvidence"] = order_comparison
    return evidence


def _alternate_installation_routes() -> list[dict[str, Any]]:
    discovery = _json(
        ROOT
        / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
        "project01_JJ00_project03_AI00/scanner_slot_discovery.json"
    )
    recovery = _json(
        ROOT
        / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
        "project01_JJ00_project03_AI00/endpoint_recovery_evidence.json"
    )
    preflight = _json(
        ROOT
        / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
        "project01_JJ00_project03_AI00/scanner_process_preflight.json"
    )
    evaluation = _json(
        ROOT
        / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
        "project01_JJ00_project03_AI00/alternate_route_evaluation.json"
    )
    selected = discovery.get("selectedCandidate") or {}
    endpoint_ids = [
        *list(selected.get("supportPlaneEndpointIds") or []),
        *list(selected.get("locatingEndpointIds") or []),
    ]
    cleaning = _json(
        ROOT
        / "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
        "project01_GN00_project03_AG00/cleaning_weighing_cross_project_route.json"
    )
    cleaning_alternate = _json(
        ROOT
        / "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
        "project01_GN00_project03_AG00/"
        "cleaning_weighing_alternate_slot_discovery.json"
    )
    routes = [
        {
            "schemaVersion": "cross-project-alternate-installation-route/v1",
            "routeId": "project03-ai00-to-project01-jj00-alternate-200mm",
            "role": "Scanner",
            "sourceProjectId": "project03",
            "sourceModuleToken": "AI00",
            "targetProjectId": "project01",
            "targetBaseToken": "JJ00",
            "nativeSlotCompatible": False,
            "nativeSlotBlocker": "LOCATING_FEATURE_SPACING_MISMATCH",
            "status": (
                "alternate_slot_geometry_and_process_proxy_passed_pending_cad"
                if evaluation.get("processProxyValidationPassed") is True
                else "alternate_slot_blocked_process_proxy_mismatch"
            ),
            "candidateCount": int(discovery.get("directCandidateCount") or 0),
            "selectedEndpointIds": endpoint_ids,
            "selectedEndpointCount": len(endpoint_ids),
            "selectedEndpointsRecovered": recovery.get("allRecovered") is True,
            "candidatePoseSolved": evaluation.get(
                "candidatePoseTransformSolved"
            )
            is True,
            "processSemanticsComplete": True,
            "processEvidenceLevel": "prototype_barcode_lane_proxy",
            "processProxyValidationPassed": evaluation.get(
                "processProxyValidationPassed"
            )
            is True,
            "selectedCrossTrackErrorMeters": (
                (evaluation.get("selectedCandidate") or {}).get(
                    "processProxyChecks"
                )
                or {}
            ).get("crossTrackErrorMeters"),
            "missingProcessEvidence": list(preflight.get("missingEvidence") or []),
            "mechanicalReviewRequired": list(
                evaluation.get("mechanicalReviewRequired") or []
            ),
            "cadValidated": False,
            "cadLaunchAllowed": False,
            "nextAction": evaluation.get("nextAction"),
            "discoveryDigest": discovery.get("discoveryDigest"),
            "endpointRecoveryDigest": recovery.get("evidenceDigest"),
            "processPreflightDigest": preflight.get("preflightDigest"),
            "alternateRouteEvaluationDigest": evaluation.get(
                "evaluationDigest"
            ),
        }
    ]
    routes.append(
        {
            "schemaVersion": "cross-project-alternate-installation-route/v1",
            "routeId": cleaning["routeId"],
            "role": cleaning["role"],
            "sourceProjectId": cleaning["source"]["projectId"],
            "sourceModuleToken": cleaning["source"]["moduleToken"],
            "targetProjectId": cleaning["target"]["projectId"],
            "targetModuleToken": cleaning["target"]["moduleToken"],
            "nativeSlotCompatible": cleaning["nativeSlotCompatible"],
            "nativeSlotBlocker": cleaning["nativeSlotBlocker"],
            "status": cleaning_alternate["status"],
            "nativeSourcePortReleased": cleaning["source"][
                "nativePortCadValidated"
            ],
            "nativeTargetPortReleased": cleaning["target"][
                "nativePortCadValidated"
            ],
            "topologyMatches": cleaning["interfaceComparison"][
                "topologyMatches"
            ],
            "sourceLocatingFeatureSpacingMeters": cleaning["source"][
                "locatingFeatureSpacingMeters"
            ],
            "targetLocatingFeatureSpacingMeters": cleaning["target"][
                "locatingFeatureSpacingMeters"
            ],
            "spacingDifferenceMeters": cleaning["interfaceComparison"][
                "spacingDifferenceMeters"
            ],
            "candidateCount": cleaning_alternate["candidateCount"],
            "exactSpacingCandidateCount": cleaning_alternate[
                "exactSpacingCandidateCount"
            ],
            "preferredDistanceFromNativeSlotMeters": (
                cleaning_alternate.get("preferredForMechanicalReview") or {}
            ).get("distanceFromNativeAg00SlotMeters"),
            "mechanicalReviewRequired": cleaning_alternate[
                "mechanicalReviewRequired"
            ],
            "cadValidated": cleaning["crossProjectCadValidated"],
            "cadLaunchAllowed": cleaning_alternate["cadLaunchAllowed"],
            "nextAction": cleaning_alternate["nextAction"],
            "routeDigest": cleaning["routeDigest"],
            "alternateSlotDiscoveryDigest": cleaning_alternate[
                "discoveryDigest"
            ],
        }
    )
    return routes


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 短期跨项目六类模组能力就绪度",
        "",
        f"- 总体状态：`{report['overallStatus']}`",
        f"- 六类端口覆盖：{'完成' if report['modulePortCoverageComplete'] else '未完成'}",
        f"- 完整角色累计链：{'已有' if report['completeRoleChainEvidencePresent'] else '缺失'}",
        f"- 六类齐全的跨项目累计链：{'已有' if report['completeCrossProjectRoleChainEvidencePresent'] else '尚未完成'}",
        f"- 两种真实添加顺序的结果等价复核：{'通过' if report['crossProjectOrderVariationVerified'] else '尚未通过'}",
        f"- 机械评审通过的跨项目Case：{'已有' if report['mechanicallyReviewedCrossProjectCasePresent'] else '缺失'}",
        f"- 已发布直接跨项目角色：{', '.join(report['directCrossProjectRoles']) or '无'}",
        f"- 参数化多基座配对：{report['parameterizedDatumPairCount']}项；"
        f"已发布{report['parameterizedDatumReleasedPairCount']}项，"
        f"待CAD{report['parameterizedDatumCadReadyPairCount']}项，"
        f"待工程确认{report['parameterizedDatumDecisionRequiredPairCount']}项。",
        "- 碰撞/B-rep：当前阶段不作为硬门禁。",
        "",
        "## 六类模组状态",
        "",
        "|类别|目录模组|端口覆盖|跨项目状态|直接执行关系|参数化配对（发布/待CAD/待确认）|",
        "|---|---:|---|---|---:|---:|",
    ]
    for row in report["groups"]:
        lines.append(
            f"|{row['displayName']}|{row['catalogModuleCount']}|"
            f"{'完成' if row['modulePortCoverageReady'] else '缺口'}|"
            f"`{row['crossProjectState']}`|{row['releasedDirectExecutionCount']}|"
            f"{row['parameterizedDatumReleasedPairCount']}/"
            f"{row['parameterizedDatumCadReadyPairCount']}/"
            f"{row['parameterizedDatumDecisionRequiredPairCount']}|"
        )
    if report["completeCrossProjectRoleChains"]:
        lines.extend(["", "## 六类跨项目累计Demo（不增加直接机械兼容结论）", ""])
        for chain in report["completeCrossProjectRoleChains"]:
            lines.append(f"- `{chain['chainId']}`：{chain['topLevelModuleCount']}模组，来自{len(chain['crossProjectIds'])}个项目；顺序：{' → '.join(chain['moduleSequence'])}。")
        lines.append("- 排胶杯采用支承面＋位置参数，实际固定方式暂未验证；六类齐全不等于完整整机。")
    lines.extend(
        [
            "",
        "## 工程处置队列",
            "",
        ]
    )
    for index, row in enumerate(report["engineeringDispositionQueue"], start=1):
        lines.append(
            f"{index}. **{row['displayName']}**：{row['recommendedAction']}"
        )
    lines.extend(
        [
            "",
            "## 结论边界",
            "",
            report["claimBoundary"]["statement"],
            "",
            f"报告摘要：`{report['reportDigest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    catalog = _json(ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json")
    gap = _json(
        ROOT
        / "demo/global_assembly_catalog/coverage-v2/global_module_gap_report.json"
    )
    matrix = _json(
        ROOT
        / "demo/cross_project_substitution/coverage-v1/"
        "cross_project_candidate_matrix.json"
    )
    review = _json(
        ROOT
        / "docs/evidence/cross-project-case02-mechanical-review-decision.json"
    )
    datum_catalog = _json(PARAMETERIZED_DATUM_CATALOG)
    _, datum_queue = _discover_current_parameterized_datum_queue(
        PARAMETERIZED_DATUM_QUEUE_ROOT,
        str(datum_catalog.get("catalogDigest") or ""),
    )
    report = build_short_term_cross_project_scope_readiness(
        role_overlay=build_module_role_overlay(catalog),
        gap_report=gap,
        candidate_matrix=matrix,
        chain_evidence=_chain_evidence(),
        mechanical_review_decisions=review.get("decisions") or [],
        alternate_installation_routes=_alternate_installation_routes(),
        parameterized_datum_queue=datum_queue,
        parameterized_datum_catalog_digest=datum_catalog.get("catalogDigest"),
    )
    validation = validate_short_term_cross_project_scope_readiness(report)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _write_json(OUTPUT / "readiness.json", report)
    (OUTPUT / "readiness-CN.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
