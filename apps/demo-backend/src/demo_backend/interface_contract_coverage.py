"""Validated aggregate view of project-independent interface-contract families."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .mechanical_interface_contracts import (
    load_contextual_transport_contract_catalog,
    load_contextual_scanner_contract_catalog,
    load_ccd_contract_catalog,
    load_native_wastecup_contract_catalog,
    load_calibration_contract_catalog,
    load_cleaning_weighing_contract_catalog,
    load_scanner_contract_catalog,
    load_transport_contract_catalog,
    load_wastecup_contract_catalog,
)


SCHEMA = "interface-contract-coverage/v1"


class InterfaceContractCoverageError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_interface_contract_coverage(workspace: Path) -> dict[str, Any]:
    catalogs = [
        load_cleaning_weighing_contract_catalog(workspace),
        load_transport_contract_catalog(workspace),
        load_calibration_contract_catalog(workspace),
        load_scanner_contract_catalog(workspace),
        load_wastecup_contract_catalog(workspace),
        load_contextual_transport_contract_catalog(workspace),
        load_contextual_scanner_contract_catalog(workspace),
        load_ccd_contract_catalog(workspace),
        load_native_wastecup_contract_catalog(workspace),
    ]
    families = []
    for report in catalogs:
        matrix = report["compatibilityMatrix"]
        families.append(
            {
                "role": report["role"],
                "schemaVersion": report["schemaVersion"],
                "movingModuleCount": sum(row["side"] == "moving_module" for row in report["contracts"]),
                "baseSlotCount": sum(row["side"] == "base_slot" for row in report["contracts"]),
                "candidatePairCount": len(matrix),
                "compatiblePairCount": sum(row["compatible"] for row in matrix),
                "incompatiblePairCount": sum(not row["compatible"] for row in matrix),
                "releasedPairCount": sum(row["existingPairReleaseReusable"] for row in matrix),
                "readOnlyProcessPortCount": len(report.get("processPorts") or []),
                "directMechanicalCompatibilityClaim": report["summary"].get(
                    "directMechanicalCompatibilityClaim", True
                ),
                "moduleDefinitionIds": sorted(
                    row["moduleDefinitionId"] for row in report["contracts"]
                    if row["side"] == "moving_module"
                ),
                "slotDefinitionIds": sorted(
                    row["moduleDefinitionId"] for row in report["contracts"]
                    if row["side"] == "base_slot"
                ),
            }
        )
    core = {
        "schemaVersion": SCHEMA,
        "families": families,
        "totals": {
            "familyCount": len(families),
            "movingModuleContractCount": sum(row["movingModuleCount"] for row in families),
            "baseSlotContractCount": sum(row["baseSlotCount"] for row in families),
            "candidatePairCount": sum(row["candidatePairCount"] for row in families),
            "compatiblePairCount": sum(row["compatiblePairCount"] for row in families),
            "incompatiblePairCount": sum(row["incompatiblePairCount"] for row in families),
            "releasedPairCount": sum(row["releasedPairCount"] for row in families),
            "readOnlyProcessPortCount": sum(row["readOnlyProcessPortCount"] for row in families),
        },
        "remainingPriorityGaps": [],
        "excludedFromCurrentMainline": [
            "Project06",
            "A700 internal flexible structure",
            "collision and B-rep",
            "vendor fastening certification",
        ],
        "status": "nine_interface_catalogs_operational_priority_mechanical_port_queue_closed",
    }
    return {**core, "coverageDigest": _digest(core)}


def validate_interface_contract_coverage(report: dict[str, Any]) -> None:
    if report.get("schemaVersion") != SCHEMA:
        raise InterfaceContractCoverageError("unsupported coverage schema")
    core = {key: value for key, value in report.items() if key != "coverageDigest"}
    if report.get("coverageDigest") != _digest(core):
        raise InterfaceContractCoverageError("coverage digest mismatch")
    totals = report.get("totals") or {}
    if totals.get("familyCount") != len(report.get("families") or []):
        raise InterfaceContractCoverageError("family count mismatch")
    if int(totals.get("releasedPairCount", -1)) > int(totals.get("compatiblePairCount", -1)):
        raise InterfaceContractCoverageError("released pair count exceeds compatibility count")


def load_interface_contract_coverage(workspace: Path) -> dict[str, Any]:
    path = workspace / "demo/cross_project_substitution/interface-contract-coverage-v1/coverage-report.json"
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_interface_contract_coverage(report)
    return report
