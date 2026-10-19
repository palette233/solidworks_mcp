from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mate_dof_analysis import analyze_target_mate_dof  # noqa: E402


PACKAGE_ROOT = ROOT / "demo/semantic_ports/project02_a200_t401_installations_v1"
DISCOVERY_ROOT = ROOT / "demo/semantic_ports/project02_t401_locator_discovery_v1"
T401_1_GRAPH = PACKAGE_ROOT / "T401-1/assembly_plan_effective.json"
T401_2_GRAPH = PACKAGE_ROOT / "T401-2/assembly_plan_effective.json"
A600_FACES = DISCOVERY_ROOT / "a600-t401-support-leaf-face-catalog.json"
A200_FACES = DISCOVERY_ROOT / "a200-support-leaf-face-catalog.json"
T401_1_FACES = ROOT / (
    "demo/mate_reconstruction_pipeline/project02_T401_instance1_face_catalog_v1.json"
)
T401_2_FACES = ROOT / (
    "demo/mate_reconstruction_pipeline/project02_T401_instance2_face_catalog_v1.json"
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _catalog_face(
    catalog: dict[str, Any], token: str, body: int, face: int
) -> dict[str, Any]:
    matches = [
        copy.deepcopy(row.get("Endpoint") or {})
        for row in catalog.get("Endpoints") or []
        if str((row.get("Endpoint") or {}).get("ModuleToken") or "").upper()
        == token.upper()
        and int((row.get("Endpoint") or {}).get("BodyIndex", -1)) == body
        and int((row.get("Endpoint") or {}).get("FaceIndexInBody", -1)) == face
    ]
    if len(matches) != 1:
        raise ValueError(f"{token} body={body} face={face}命中{len(matches)}项。")
    return matches[0]


def _vector(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("端点缺少三维向量。")
    return [float(item) for item in value[:3]]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _length(vector: list[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: list[float]) -> list[float]:
    length = _length(vector)
    if length <= 1e-12:
        raise ValueError("端点法向为零。")
    return [item / length for item in vector]


def _plane_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    normal = _normalize(_vector(first.get("FaceNormalWorld")))
    other = _normalize(_vector(second.get("FaceNormalWorld")))
    if abs(abs(_dot(normal, other)) - 1.0) > 1e-6:
        raise ValueError("定位距离两端面不平行。")
    delta = [
        left - right
        for left, right in zip(
            _vector(first.get("FaceCenterWorld")),
            _vector(second.get("FaceCenterWorld")),
        )
    ]
    return abs(_dot(delta, normal))


def _distance_mate(
    name: str,
    target: dict[str, Any],
    context: dict[str, Any],
    *,
    alignment: int,
    purpose: str,
) -> dict[str, Any]:
    target["Index"] = 0
    context["Index"] = 1
    distance = _plane_distance(target, context)
    return {
        "MateName": name,
        "MateType": 5,
        "MateTypeName": "swMateDISTANCE",
        "Alignment": alignment,
        "AlignmentName": (
            "swMateAlignALIGNED" if alignment == 0 else "swMateAlignANTI_ALIGNED"
        ),
        "Distance": distance,
        "Angle": None,
        "IsSuppressed": False,
        "ModuleTokens": ["T401", str(context.get("ModuleToken") or "").upper()],
        "ModuleHierarchyPaths": [
            target.get("ModuleHierarchyPath"),
            context.get("ModuleHierarchyPath"),
        ],
        "Endpoints": [target, context],
        "AdvancedOptions": {
            "WidthConstraintType": None,
            "WidthPercentDistanceFromEnd": None,
            "WidthDistanceFromEnd": None,
            "WidthFlipDimension": None,
            "WidthEndpointIndices": [],
            "TabEndpointIndices": [],
            "SlotConstraint": None,
            "SlotDistance": None,
            "SlotPercent": None,
            "SlotFlipDirection": None,
            "DistanceFlipDimension": False,
            "SourceFeatureErrorCode": 0,
            "SourceFeatureIsWarning": False,
        },
        "DerivedEngineeringDatum": {
            "authority": "prototype_estimate",
            "purpose": purpose,
            "notVendorDatum": True,
            "productionReady": False,
            "distanceMeters": distance,
        },
    }


def _prepare_nonanchor(graph: dict[str, Any], base_token: str) -> None:
    source_names = [str(row.get("MateName") or "") for row in graph.get("Mates") or []]
    policy = graph.setdefault("EditPolicy", {})
    policy["baseModuleToken"] = base_token
    policy["initialPlacementMode"] = "deterministic"
    policy["caseAnchoredModuleTokens"] = []
    policy["targetLeafPoseAnchors"] = []
    policy["fixedModuleTokens"] = [base_token]
    policy["sourceMateNamesToSuppress"] = source_names
    graph["BaseGraphPolicy"] = {
        "moduleTokens": [base_token],
        "fixedAtKnownContextPoses": False,
        "sourceMateNamesRepresentedByFixedContext": [],
        "purpose": f"Use the existing {base_token} instance as the fixed connection context.",
    }
    audit = graph.setdefault("SemanticAssemblyPlanAudit", {})
    audit.pop("caseAnchorEvidence", None)
    audit["constraintAssessment"] = {
        "sourceSemanticMateSetReproduced": True,
        "fullyLocatesAddedComponent": "pending_dof_and_cad_verification",
        "reason": "T401 starts from a deterministic pose and is located only by the explicit mate graph.",
        "caseAnchoredModuleTokens": [],
    }


def build_graphs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    a600_faces = _read(A600_FACES)
    a200_faces = _read(A200_FACES)
    t401_1_faces = _read(T401_1_FACES)
    t401_2_faces = _read(T401_2_FACES)

    first = copy.deepcopy(_read(T401_1_GRAPH))
    _prepare_nonanchor(first, "A600")
    first_mate = _distance_mate(
        "T401_1_LOCATING_DISTANCE_Z",
        _catalog_face(t401_1_faces, "T401", 17, 70),
        _catalog_face(a600_faces, "A600", 0, 1),
        alignment=0,
        purpose="close the source T401-1 residual Z translation",
    )
    first.setdefault("Mates", []).append(first_mate)
    first["InterModuleMateCount"] = len(first["Mates"])
    first_dof = analyze_target_mate_dof(first, "T401")
    if first_dof.get("closed") is not True or int(first_dof.get("residualDof", -1)) != 0:
        raise ValueError("T401-1追加Z定位后仍未闭合。")
    first["Project02T401NonAnchorExperiment"] = {
        "schemaVersion": "project02-t401-nonanchor-graph/v1",
        "occurrence": 1,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "contextModuleToken": "A600",
        "initialPlacementMode": "deterministic",
        "caseAnchorsRemoved": True,
        "prototypePoseUsedForParameterEstimation": True,
        "derivedMateNames": [first_mate["MateName"]],
        "dofAnalysis": first_dof,
        "collisionStatus": "not_evaluated",
    }

    second = copy.deepcopy(_read(T401_2_GRAPH))
    _prepare_nonanchor(second, "A200")
    second_y = _distance_mate(
        "T401_2_LOCATING_DISTANCE_Y",
        _catalog_face(t401_2_faces, "T401", 29, 6),
        _catalog_face(a200_faces, "A200", 0, 4),
        alignment=0,
        purpose="close T401-2 residual Y translation and Z-axis rotation",
    )
    second_x = _distance_mate(
        "T401_2_LOCATING_DISTANCE_X",
        _catalog_face(t401_2_faces, "T401", 52, 19),
        _catalog_face(a200_faces, "A200", 0, 0),
        alignment=1,
        purpose="close T401-2 residual X translation",
    )
    second.setdefault("Mates", []).extend([second_y, second_x])
    second["InterModuleMateCount"] = len(second["Mates"])
    second_dof = analyze_target_mate_dof(second, "T401")
    if second_dof.get("closed") is not True or int(second_dof.get("residualDof", -1)) != 0:
        raise ValueError("T401-2追加X/Y定位后仍未闭合。")
    second["Project02T401NonAnchorExperiment"] = {
        "schemaVersion": "project02-t401-nonanchor-graph/v1",
        "occurrence": 2,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "contextModuleToken": "A200",
        "initialPlacementMode": "deterministic",
        "caseAnchorsRemoved": True,
        "prototypePoseUsedForParameterEstimation": True,
        "derivedMateNames": [second_y["MateName"], second_x["MateName"]],
        "dofAnalysis": second_dof,
        "collisionStatus": "not_evaluated",
    }

    report = {
        "schemaVersion": "project02-t401-locator-discovery/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project02",
        "status": "ready_for_authoritative_cad_checkpoint",
        "occurrences": [
            {
                "occurrence": 1,
                "contextModuleToken": "A600",
                "sourceMateNames": ["重合14", "距离10"],
                "sourceResidualDof": 1,
                "derivedMates": [first_mate],
                "closedDofAnalysis": first_dof,
            },
            {
                "occurrence": 2,
                "contextModuleToken": "A200",
                "sourceMateNames": ["距离28"],
                "sourceResidualDof": 3,
                "derivedMates": [second_y, second_x],
                "closedDofAnalysis": second_dof,
            },
        ],
        "parameterAuthority": "prototype_estimate",
        "productionReady": False,
        "collisionStatus": "not_evaluated",
        "graphDigests": {"T401-1": _digest(first), "T401-2": _digest(second)},
    }
    return first, second, report


def main() -> int:
    parser = argparse.ArgumentParser(description="生成Project02两套T401无锚点最小定位执行图。")
    parser.add_argument("--output-root", type=Path, default=DISCOVERY_ROOT)
    args = parser.parse_args()
    first, second, report = build_graphs()
    root = args.output_root.resolve()
    _write(root / "t401-1-nonanchor-effective.json", first)
    _write(root / "t401-2-nonanchor-effective.json", second)
    _write(root / "project02-t401-locator-discovery.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
