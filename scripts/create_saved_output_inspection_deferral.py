#!/usr/bin/env python3
"""Create an immutable deferral for a strict saved-output inspection gap."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--failed-process", type=Path, required=True)
    parser.add_argument(
        "--reason-code",
        choices=(
            "source_model_unresolved_references",
            "historical_output_not_pair_isolated",
        ),
        default="source_model_unresolved_references",
    )
    parser.add_argument("--dependency-inventory", type=Path)
    parser.add_argument("--resolution-report", type=Path)
    parser.add_argument("--observed-state", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths: dict[str, Path] = {
        "request": args.request.resolve(),
        "failedProcess": args.failed_process.resolve(),
    }
    if args.dependency_inventory:
        paths["dependencyInventory"] = args.dependency_inventory.resolve()
    if args.resolution_report:
        paths["resolutionReport"] = args.resolution_report.resolve()
    if args.observed_state:
        paths["observedState"] = args.observed_state.resolve()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite deferral: {args.output}")
    if any(not path.is_file() for path in paths.values()):
        raise FileNotFoundError("deferral input evidence is missing")
    request = _read(paths["request"])
    process = _read(paths["failedProcess"])
    source_token = args.source.split("::", 1)[-1]
    base_token = args.base.split("::", 1)[-1]
    if request.get("sourceModuleDefinitionId") not in (None, args.source):
        raise ValueError("request source identity differs")
    if request.get("targetToken") != source_token or request.get("baseToken") != base_token:
        raise ValueError("request tokens differ from the deferral pair")
    if (
        Path(str(process.get("requestPath") or "")).resolve() != paths["request"]
        or process.get("requestDigest") != request.get("requestDigest")
        or int(process.get("returnCode") or 0) == 0
    ):
        raise ValueError("failed process is not bound to the request")
    unresolved_references: list[dict] = []
    context_details: dict = {}
    if args.reason_code == "source_model_unresolved_references":
        if "dependencyInventory" not in paths or "resolutionReport" not in paths:
            raise ValueError("source-reference deferral requires dependency evidence")
        inventory = _read(paths["dependencyInventory"])
        resolution = _read(paths["resolutionReport"])
        if (
            inventory.get("schemaVersion")
            != "solidworks-document-dependency-inventory/v1"
            or resolution.get("schemaVersion")
            != "solidworks-reference-resolution-manifest/v1"
            or resolution.get("success") is not False
            or int(resolution.get("unresolvedCount") or 0) < 1
            or resolution.get("assemblySha256") != request.get("outputAssemblySha256")
        ):
            raise ValueError("dependency evidence does not prove unresolved references")
        inventory_binding = resolution.get("dependencyInventory") or {}
        if (
            Path(str(inventory_binding.get("path") or "")).resolve()
            != paths["dependencyInventory"]
            or inventory_binding.get("sha256") != _sha(paths["dependencyInventory"])
        ):
            raise ValueError("resolution report does not bind the dependency inventory")
        unresolved_references = resolution.get("unresolved") or []
        reason = (
            "Strict read-only reopen returned SolidWorks error 2 after exact-path "
            "recovery; source CAD still contains unresolved leaf references."
        )
        next_action = "restore_missing_source_references_then_repeat_readonly_postcheck"
    else:
        if "observedState" not in paths:
            raise ValueError("pair-isolation deferral requires the observed state")
        observed = _read(paths["observedState"])
        checks = observed.get("checks") or {}
        components = (observed.get("observed") or {}).get("components") or []
        expected_count = int(request.get("expectedTopLevelComponentCount") or 0)
        if (
            observed.get("schemaVersion") != "p000-support-position-readonly-state/v1"
            or observed.get("assemblySha256") != request.get("outputAssemblySha256")
            or observed.get("success") is not False
            or checks.get("expectedTopLevelComponentCount") is not False
            or len(components) <= expected_count
            or any(
                value is not True
                for key, value in checks.items()
                if key != "expectedTopLevelComponentCount"
            )
        ):
            raise ValueError("observed state does not prove a non-isolated historical pair")
        context_details = {
            "expectedTopLevelComponentCount": expected_count,
            "observedTopLevelComponentCount": len(components),
            "observedTopLevelComponentNames": [row.get("name") for row in components],
        }
        reason = (
            "The historical saved output contains additional top-level modules. "
            "Its active pair mates are not sufficient evidence for an isolated "
            "base-and-target CAD validation."
        )
        next_action = "materialize_exact_pair_nonprototype_cad_candidate"
    evidence = [
        {"kind": key, "path": str(path), "sha256": _sha(path)}
        for key, path in paths.items()
    ]
    report = {
        "schemaVersion": "saved-output-inspection-deferral/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceModuleDefinitionId": args.source,
        "targetBaseDefinitionId": args.base,
        "reasonCode": args.reason_code,
        "reason": reason,
        "unresolvedReferences": unresolved_references,
        "contextDetails": context_details,
        "nextAction": next_action,
        "evidence": evidence,
        "strictStationValidationPassed": False,
        "cadReexecutionAuthorized": False,
        "claimBoundary": (
            "The pair remains an explicit coverage gap. Deferral only permits "
            "independent queue items to continue; it does not count as validation."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
