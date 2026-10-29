"""Audit why a WasteCup datum demo is not a direct installation interface."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from demo_backend.project05_p000_physical_attachment_candidate import (
    validate_project05_p000_physical_attachment_candidate,
)


SCHEMA = "cross-project-wastecup-mechanical-interface-gap/v1"


class CrossProjectWasteCupInterfaceGapError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _single(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    matches = [row for row in rows if str(row.get(key) or "") == value]
    if len(matches) != 1:
        raise CrossProjectWasteCupInterfaceGapError(
            f"expected one {key}={value}, found {len(matches)}"
        )
    return matches[0]


def build_wastecup_mechanical_interface_gap_audit(
    *,
    catalog: dict[str, Any],
    datum_closure: dict[str, Any],
    datum_effective_graph: dict[str, Any],
    physical_attachment_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if catalog.get("schemaVersion") != "global-module-catalog/v1":
        raise CrossProjectWasteCupInterfaceGapError("unsupported global catalog")
    if datum_closure.get("schemaVersion") != (
        "cross-project-wastecup-datum-closure/v1"
    ):
        raise CrossProjectWasteCupInterfaceGapError("unsupported datum closure")
    if datum_closure.get("success") is not True:
        raise CrossProjectWasteCupInterfaceGapError("datum closure did not pass")

    template = _single(
        list(catalog.get("connectionTemplates") or []),
        "legacyTemplateId",
        "P000_to_A000_source_installation",
    )
    port_ids = [
        *list(template.get("candidatePortIdsA") or []),
        *list(template.get("candidatePortIdsB") or []),
    ]
    ports = [
        row
        for row in catalog.get("semanticPorts") or []
        if row.get("globalPortId") in port_ids
    ]
    if len(ports) != 2:
        raise CrossProjectWasteCupInterfaceGapError(
            "source installation template must resolve two ports"
        )
    source_endpoint_classes = sorted(
        {
            str(endpoint.get("geometryClass") or "")
            for port in ports
            for endpoint in port.get("endpointEvidence") or []
        }
    )
    source_mate_types = [
        str(row.get("mateTypeName") or "") for row in template.get("mateSteps") or []
    ]
    demo_mates = list(datum_effective_graph.get("Mates") or [])
    demo_distances = sorted(
        float(row["Distance"])
        for row in demo_mates
        if row.get("Distance") is not None
    )
    closure_checks = datum_closure.get("checks") or {}
    if not (
        closure_checks.get("threeOfThreeMatesCreated") is True
        and closure_checks.get("targetFullyConstrained") is True
        and closure_checks.get("saveCloseReopenPassed") is True
    ):
        raise CrossProjectWasteCupInterfaceGapError(
            "datum closure lacks required CAD checks"
        )

    candidate_summary = None
    source_candidate_found = False
    if physical_attachment_candidate is not None:
        validate_project05_p000_physical_attachment_candidate(physical_attachment_candidate)
        signature = physical_attachment_candidate.get(
            "candidateInterfaceSignature"
        ) or {}
        source_candidate_found = True
        candidate_summary = {
            "status": physical_attachment_candidate.get("status"),
            "candidateKind": signature.get("candidateKind"),
            "supportPlaneEndpointId": (
                signature.get("supportPlane") or {}
            ).get("endpointId"),
            "slotArcEndpointIds": [
                endpoint_id for slot in signature["slots"]
                for endpoint_id in slot["arcEndpointIds"]
            ],
            "slotWidthMeters": signature["slotWidthMeters"],
            "slotCenterlineSpacingMeters": signature["slotCenterlineSpacingMeters"],
            "mechanicalMeaningConfirmed": True,
            "confirmationScope": signature["confirmationScope"],
            "candidateDigest": physical_attachment_candidate.get(
                "candidateDigest"
            ),
        }

    core = {
        "schemaVersion": SCHEMA,
        "status": (
            "source_slot_installation_confirmed_target_interface_pending"
            if source_candidate_found
            else "physical_attachment_interface_missing"
        ),
        "role": "WasteCup",
        "source": {"projectId": "project05", "moduleToken": "P000"},
        "target": {"projectId": "project02", "baseToken": "A600"},
        "sourceNativeInstallation": {
            "scope": "legacy_template_only_not_complete_prototype_mates",
            "templateId": template.get("globalTemplateId"),
            "mateStepCount": len(template.get("mateSteps") or []),
            "mateTypes": source_mate_types,
            "endpointGeometryClasses": source_endpoint_classes,
            "residualDofPolicy": (template.get("constraintEffect") or {}).get(
                "residualDofPolicy"
            ),
            "containsPhysicalHoleAxisOrSlotEvidence": any(
                value in {"Cylinder", "Axis", "Edge", "Point"}
                for value in source_endpoint_classes
            ),
        },
        "completePrototypeInstallation": (
            physical_attachment_candidate["originalTopLevelEvidence"]
            if source_candidate_found else None
        ),
        "sourcePhysicalAttachmentCandidate": candidate_summary,
        "crossProjectDatumDemo": {
            "passed": True,
            "mateCount": len(demo_mates),
            "mateTypes": [str(row.get("MateTypeName") or "") for row in demo_mates],
            "distanceParametersMeters": demo_distances,
            "fullyConstrained": True,
            "saveCloseReopenPassed": True,
            "directMechanicalInterfaceCompatible": False,
            "meaning": (
                "80 mm与390 mm距离只定义P000在A600上的演示位姿，不是孔、销、槽、"
                "螺钉或夹紧结构的机械接口证据。"
            ),
        },
        "missingEvidence": [
            {
                "code": (
                    "EXPLICIT_ALONG_SLOT_INSTALLATION_POSITION_REQUIRED"
                    if source_candidate_found
                    else "SOURCE_PHYSICAL_ATTACHMENT_UNIDENTIFIED"
                ),
                "description": (
                    "原型已证明支承面与长圆槽参与对外安装；自由槽保留沿槽1个平移自由度，"
                    "需要显式安装位置参数，不应照搬原型完整位姿。"
                    if source_candidate_found
                    else "旧安装模板仅有平面关系，需核对完整原型配合图，不能据此断言无孔槽接口。"
                ),
            },
            {
                "code": "TARGET_SLOT_ATTACHMENT_UNIDENTIFIED",
                "description": "A600目标位只登记三基准面，未登记与P000对应的紧固/定位特征。",
            },
            {
                "code": "FASTENER_OR_CLAMPING_METHOD_UNKNOWN",
                "description": "螺钉、定位销、压板或其他固定方式及尺寸均未确认。",
            },
            {
                "code": "DATUM_OFFSETS_ARE_NOT_ATTACHMENT_FEATURES",
                "description": "两条距离配合是位姿参数，不能独立证明实体安装可行。",
            },
        ],
        "recommendedEvidenceAcquisition": [
            (
                "按已确认的支承面＋双长圆槽搜索A600对应孔位，记录槽宽、间距和允许沿槽位置。"
                if source_candidate_found
                else "先从Project05 P000原型配合、BOM名称和静止安装叶中识别真实固定方式。"
            ),
            "目标接口匹配后补齐显式沿槽安装位置及方向，复用既有槽口配合执行器。",
            "若仅通过独立支架或夹具固定，将支架/夹具作为显式接口提供方，不把三基准面冒充安装端口。",
            "只有接口签名匹配后，才从非原型位姿执行真实配合并保存重开。",
        ],
        "cadLaunchAllowed": False,
        "semanticPortPublished": False,
        "collisionOrBrepRequiredAtThisStage": False,
        "nextAction": (
            "match-a600-support-and-hole-pattern-to-p000-parallel-slots"
            if source_candidate_found
            else "identify-p000-physical-attachment-before-slot-search"
        ),
    }
    return {**core, "auditDigest": _digest(core)}
