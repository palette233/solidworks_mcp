"""Finalize the Project03 AI00 scanner incremental CAD checkpoint."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


TOKENS = (
    "FL9A24D063AA00",
    "FL9A24D063AF00",
    "FL9A24D063AE00",
    "FL9A24D063AD00",
    "FL9A24D063AI00",
)
AI00 = "FL9A24D063AI00"
AE00 = "FL9A24D063AE00"


def _token(text: str) -> str:
    matches = [token for token in TOKENS if token in str(text).upper()]
    if len(matches) != 1:
        raise ValueError(f"Cannot identify one Project03 module in {text!r}.")
    return matches[0]


def _get(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_project03_ai00_incremental_closure(
    *,
    source_graph: dict[str, Any],
    failed_all_driving_result: dict[str, Any],
    insert_result: dict[str, Any],
    poses: dict[str, Any],
    screening: dict[str, Any],
    scanner_geometry: dict[str, Any],
    prototype_ae_ai_brep: dict[str, Any],
    assembly_path: Path,
) -> dict[str, Any]:
    """Build an auditable closure without claiming absolute zero interference."""

    assembly_path = assembly_path.resolve()
    if not assembly_path.is_file():
        raise FileNotFoundError(assembly_path)

    source = {
        str(row["ModuleToken"]): row
        for row in source_graph.get("Modules") or []
        if str(row.get("ModuleToken") or "") in TOKENS
    }
    observed = {
        _token(row.get("Name") or row.get("HierarchyPath") or ""): row
        for row in poses.get("components") or []
    }
    if set(source) != set(TOKENS) or set(observed) != set(TOKENS):
        raise ValueError("Expected exactly AA00, AF00, AE00, AD00 and AI00.")

    pose_rows: list[dict[str, Any]] = []
    for token in TOKENS:
        expected = [float(value) for value in source[token]["SourceTransform"]]
        actual = [float(value) for value in observed[token]["Transform"]]
        if len(expected) != len(actual):
            raise ValueError(f"Transform length mismatch for {token}.")
        maximum_error = max((abs(a - b) for a, b in zip(expected, actual)), default=0.0)
        source_path = Path(str(observed[token]["Path"]))
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        pose_rows.append(
            {
                "moduleToken": token,
                "maximumTransformElementError": maximum_error,
                "sourcePoseEquivalent": maximum_error <= 1e-12,
                "sourceFilePath": str(source_path.resolve()),
                "sourceFileSha256": _sha256(source_path),
            }
        )
    pose_ok = all(row["sourcePoseEquivalent"] for row in pose_rows)

    tool = insert_result.get("toolResult") or {}
    validations = list(_get(tool, "ValidationResults", []) or [])
    expected_distances = {"距离1": 0.29, "距离2": 0.01}
    validation_rows = []
    for row in validations:
        name = str(_get(row, "RelationName", ""))
        validation_rows.append(
            {
                "relationName": name,
                "expectedDistanceMeters": float(_get(row, "ExpectedDistanceMeters", 0.0)),
                "measuredDistanceMeters": float(_get(row, "MeasuredDistanceMeters", 0.0)),
                "absoluteErrorMeters": float(_get(row, "AbsoluteErrorMeters", 0.0)),
                "toleranceMeters": float(_get(row, "ToleranceMeters", 0.0)),
                "passed": _get(row, "Passed") is True,
            }
        )
    validation_ok = bool(
        len(validation_rows) == 2
        and {row["relationName"] for row in validation_rows} == set(expected_distances)
        and all(row["passed"] for row in validation_rows)
        and all(
            abs(row["expectedDistanceMeters"] - expected_distances[row["relationName"]]) <= 1e-9
            for row in validation_rows
        )
    )
    insert_ok = bool(
        insert_result.get("success")
        and _get(tool, "IndependentComponentInserted") is True
        and int(_get(tool, "CreatedMateCount", -1)) == 3
        and _get(tool, "ReopenedMateParametersMatch") is True
        and _get(tool, "TargetFullyConstrained") is True
        and _get(tool, "MateSolveClean") is True
        and validation_ok
    )

    failed_tool = failed_all_driving_result.get("toolResult") or {}
    failed_mates = list(_get(failed_tool, "MateResults", []) or [])
    overdefined_names = [
        str(_get(row, "MateName", ""))
        for row in failed_mates
        if _get(row, "ErrorName") == "swAddMateError_OverDefinedAssembly"
    ]
    failure_evidence_ok = bool(
        failed_all_driving_result.get("success") is False
        and int(_get(failed_tool, "CreatedMateCount", -1)) == 5
        and set(overdefined_names) == {"同心31", "同心32"}
        and _get(failed_tool, "MateSolveClean") is False
    )

    baseline_ok = bool(
        _get(prototype_ae_ai_brep, "ExactCheckComplete") is True
        and int(_get(prototype_ae_ai_brep, "FailedBodyPairCount", -1)) == 0
        and int(_get(prototype_ae_ai_brep, "InterferingBodyPairCount", -1)) == 2
    )
    pair_rows = []
    for row in screening.get("broadPhase") or []:
        pair = sorted((_token(row["pair"][0]), _token(row["pair"][1])))
        if row.get("requiresExactLeafBrep") is not True:
            decision = "accepted-by-strict-world-aabb-separation"
        elif set(pair) == {AE00, AI00}:
            decision = "accepted-by-prototype-exact-brep-and-identical-relative-pose"
        else:
            decision = "accepted-by-identical-source-files-and-relative-pose"
        pair_rows.append(
            {
                "pair": pair,
                "broadPhaseStatus": row.get("broadPhaseStatus"),
                "decision": decision,
                "accepted": True,
            }
        )
    collision_ok = bool(
        len(pair_rows) == 10
        and int(screening.get("aabbProvenPairCount") or 0) == 2
        and int(screening.get("exactCandidatePairCount") or 0) == 8
        and baseline_ok
        and pose_ok
    )

    scanners = list(scanner_geometry.get("scanners") or [])
    scanner = scanners[0] if len(scanners) == 1 else {}
    optical_model_ok = bool(
        scanner_geometry.get("coarseLayoutUsable") is True
        and scanner_geometry.get("scannerModel") == "KEYENCE SR-X100"
        and scanner_geometry.get("scannerCount") == 1
        and scanner.get("opticalDirectionWorld") == [0.0, 1.0, 0.0]
        and abs(float(scanner.get("modeledWorkingDistanceMeters") or 0.0) - 0.1) <= 1e-12
        and len(scanner.get("opticalOriginWorldMeters") or []) == 3
        and len(scanner.get("targetProxyWorldMeters") or []) == 3
    )
    optical_preserved = optical_model_ok and pose_ok
    optical_production_ready = bool(
        optical_preserved
        and scanner_geometry.get("engineeringConfirmed") is True
        and (scanner_geometry.get("barcodeInterfaces") or {}).get("carrierBarcode", {}).get("status") == "available"
    )

    success = bool(
        insert_ok
        and failure_evidence_ok
        and pose_ok
        and collision_ok
        and optical_preserved
    )
    timing = {
        "failedAllDrivingAttemptSeconds": float(failed_all_driving_result.get("durationSeconds") or 0.0),
        "successfulIncrementalInsertSeconds": float(insert_result.get("durationSeconds") or 0.0),
        "poseCaptureSeconds": float(poses.get("durationSeconds") or 0.0),
        "broadPhaseCaptureSeconds": float((screening.get("timing") or {}).get("totalDurationSeconds") or 0.0),
    }
    timing["successfulPathMeasuredSeconds"] = (
        timing["successfulIncrementalInsertSeconds"]
        + timing["poseCaptureSeconds"]
        + timing["broadPhaseCaptureSeconds"]
    )
    timing["engineeringIterationMeasuredSeconds"] = sum(
        value for key, value in timing.items() if key.endswith("Seconds") and "Measured" not in key
    )

    return {
        "schemaVersion": "project03-ai00-incremental-closure/v1",
        "projectId": "project03",
        "status": "PROJECT03_AI00_STATIC_INCREMENT_CLOSED" if success else "PROJECT03_AI00_INCREMENT_BLOCKED",
        "success": success,
        "staticDemoCheckpointPassed": success,
        "productionReady": False,
        "zeroInterferenceClaimed": False,
        "noNewInterferenceOverPrototype": collision_ok,
        "assemblyPath": str(assembly_path),
        "assemblySha256": _sha256(assembly_path),
        "componentCount": len(observed),
        "relationSemantics": {
            "drivingMateCount": int(_get(tool, "CreatedMateCount", 0)),
            "validationRelationCount": len(validation_rows),
            "drivingMateNames": ["重合8", "同心31", "同心32"],
            "validationRelations": validation_rows,
            "passed": insert_ok,
        },
        "overconstraintRepairAudit": {
            "passed": failure_evidence_ok,
            "failedAttemptDrivingMateCount": int(_get(failed_tool, "CreatedMateCount", 0)),
            "overdefinedMateNames": overdefined_names,
            "repair": "距离1/距离2由驱动配合改为只验证关系；重合8与同心31/32继续驱动定位。",
        },
        "poseAudit": {
            "passed": pose_ok,
            "maximumTransformElementError": max(row["maximumTransformElementError"] for row in pose_rows),
            "modules": pose_rows,
        },
        "opticalGate": {
            "passedForStaticDemo": optical_preserved,
            "productionReady": optical_production_ready,
            "scannerModel": scanner_geometry.get("scannerModel"),
            "opticalDirectionWorld": scanner.get("opticalDirectionWorld"),
            "modeledWorkingDistanceMeters": scanner.get("modeledWorkingDistanceMeters"),
            "targetKind": "CAD beam endpoint proxy",
            "carrierBarcodeStatus": (scanner_geometry.get("barcodeInterfaces") or {}).get("carrierBarcode", {}).get("status"),
        },
        "collisionGate": {
            "passed": collision_ok,
            "pairCount": len(pair_rows),
            "aabbSeparatedPairCount": sum("strict-world-aabb" in row["decision"] for row in pair_rows),
            "sourcePoseEquivalentCandidatePairCount": sum("source-files-and-relative-pose" in row["decision"] for row in pair_rows),
            "prototypeAe00Ai00InterferingBodyPairCount": 2,
            "pairs": pair_rows,
        },
        "timingSeconds": timing,
        "blockers": [
            "100 mm工作距离来自项目03 CAD光束建模，不是SR-X100厂商确认范围。",
            "产品条码目标仍是光束端点代理，并非持久命名的实物条码面。",
            "载具身份头/第二扫码头角色仍为部分确认。",
            "AE00/AI00原型基线含2对叶级实体相交；本闭环只证明没有新增干涉。",
        ],
        "nextStep": (
            "将AI00登记为项目03第三个已验证CAD动作，随后建立AG00安装端口和服务目标闭环。"
            if success
            else "暂停AG00；先修复AI00的关系语义、位姿、光学或碰撞门禁。"
        ),
    }

