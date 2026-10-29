#!/usr/bin/env python3
"""Plan every confirmed transport station candidate through the common chain API."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.station_rule_planner import plan_station_chain  # noqa: E402


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selection(definition_id: str) -> dict:
    project, token = definition_id.split("::", 1)
    return {"projectId": project, "moduleToken": token, "confirmed": True}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    bundle_path = (ROOT / args.bundle).resolve()
    registry_path = (ROOT / args.registry).resolve()
    output = (ROOT / args.output).resolve()
    for path in (bundle_path, registry_path):
        path.relative_to(ROOT)
        if not path.is_file():
            raise FileNotFoundError(path)
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite transport planning evidence: {output}")
    bundle = _read(bundle_path)
    if bundle.get("schemaVersion") != "transport-position-station-candidate-bundle/v1":
        raise ValueError("unsupported transport candidate bundle")
    rules = bundle.get("candidateRules") or []
    if len(rules) != bundle.get("candidateCount"):
        raise ValueError("transport candidate bundle count mismatch")
    registry_rel = str(registry_path.relative_to(ROOT)).replace("\\", "/")
    output.mkdir(parents=True)
    results = []
    for rule in rules:
        request = {
            "chainId": rule["ruleId"] + "-planning",
            "baseRequirement": "建立目标设备基座。",
            "baseSelection": _selection(rule["targetBaseDefinitionId"]),
            "stationRegistryPath": registry_rel,
            "placementValidationMode": "target_role_station",
            "steps": [{
                "stageId": "install-transport",
                "moduleRole": "Transport",
                "requirement": "在目标基座的已确认传输工位安装产品传输模组。",
                "moduleSelection": _selection(rule["sourceModuleDefinitionId"]),
                "stationRuleId": rule["ruleId"],
                "allowDatumFallback": True,
            }],
        }
        pair_dir = output / rule["ruleId"]
        _write(pair_dir / "request.json", request)
        started = perf_counter()
        chain_plan = plan_station_chain(ROOT, request, prepare_candidates=True)
        elapsed = perf_counter() - started
        chain_plan["planningDurationSeconds"] = elapsed
        stage = (chain_plan.get("stages") or [{}])[0]
        stage_plan = stage.get("plan") or {}
        package = stage_plan.get("validationPackage")
        package_path = pair_dir / "validation-package.json"
        if isinstance(package, dict):
            package = json.loads(json.dumps(package))
            artifacts = {}
            for key, filename in (
                ("effectiveGraph", "effective-mate-graph.json"),
                ("selectedEndpointCatalog", "selected-face-endpoint-catalog.json"),
            ):
                payload = package.pop(key, None)
                if not isinstance(payload, dict):
                    raise ValueError(
                        f"transport candidate package has no {key}: {rule['ruleId']}"
                    )
                artifact_path = pair_dir / filename
                _write(artifact_path, payload)
                artifacts[key] = {
                    "path": str(artifact_path.resolve()),
                    "sha256": _sha256(artifact_path),
                }
            package["artifacts"] = artifacts
            _write(package_path, package)
        _write(pair_dir / "chain-plan.json", chain_plan)
        _write(pair_dir / "station-plan.json", stage_plan)
        results.append({
            "ruleId": rule["ruleId"],
            "sourceModuleDefinitionId": rule["sourceModuleDefinitionId"],
            "targetBaseDefinitionId": rule["targetBaseDefinitionId"],
            "planned": stage.get("planned") is True,
            "blockingReasonCodes": stage.get("blockingReasonCodes") or [],
            "validationPackagePrepared": package_path.is_file(),
            "planningDurationSeconds": elapsed,
            "planPath": str((pair_dir / "station-plan.json").relative_to(ROOT)).replace("\\", "/"),
            "chainPlanPath": str((pair_dir / "chain-plan.json").relative_to(ROOT)).replace("\\", "/"),
            "candidatePackagePath": (
                str(package_path.relative_to(ROOT)).replace("\\", "/")
                if package_path.is_file()
                else None
            ),
        })
    summary = {
        "schemaVersion": "transport-position-station-planning-report/v1",
        "candidateCount": len(results),
        "plannedCount": sum(row["planned"] for row in results),
        "validationPackageCount": sum(row["validationPackagePrepared"] for row in results),
        "results": results,
        "cadStarted": False,
        "claimBoundary": (
            "Planning and package preparation only. No SolidWorks operation, saved-output "
            "postcheck, fastening, collision or production approval is claimed."
        ),
    }
    _write(output / "planning-report.json", summary)
    print(json.dumps({key: summary[key] for key in (
        "candidateCount", "plannedCount", "validationPackageCount", "cadStarted"
    )}, ensure_ascii=False))
    return 0 if summary["plannedCount"] == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
