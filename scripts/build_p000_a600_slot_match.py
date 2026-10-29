"""Bounded A600 slot search; no CAD launch or semantic publication side effects."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.parallel_slot_mount_match import screen_catalog
from demo_backend.project05_p000_physical_attachment_candidate import validate_project05_p000_physical_attachment_candidate

PACKAGE = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"
OUT = PACKAGE / "a600-slot-match-v1"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    started = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    source = PACKAGE / "p000_physical_attachment_candidate.json"
    source_evidence = read(source)
    validate_project05_p000_physical_attachment_candidate(source_evidence)
    signature = source_evidence["candidateInterfaceSignature"]
    spacing = signature["slotCenterlineSpacingMeters"]
    width = signature["slotWidthMeters"]
    travel = min(s["endCenterSpacingMeters"] for s in signature["slots"])
    prototype = ROOT / "demo/layout_previews/project02_module_mate_graph_v6_all_bodies.json"
    mates = read(prototype)["Mates"]
    paths = [
        ROOT / "demo/cross_project_substitution/alternate-slot-discovery-v1/project02_A600_calibration_slot_acquisition/a600-native-service-leaf-face-catalog-v1.json",
        ROOT / "demo/semantic_ports/project02_a800_a180_dof_audit_v1/a600-a180-support-leaf-face-catalog.json",
    ]
    native = OUT / "a600-native-wastecup-support-faces.json"
    if native.exists():
        paths.append(native)
    reports = []
    for path in paths:
        data = read(path)
        report = screen_catalog(data, slot_spacing=spacing, slot_width=width, slot_travel=travel)
        index = {row["EndpointId"]: row["Endpoint"] for row in data["Endpoints"]}
        for candidate in report["candidates"]:
            references = {}
            for endpoint_id in [candidate["supportEndpointId"], *candidate["holeEndpointIds"]]:
                ep = index[endpoint_id]
                references[endpoint_id] = [mate["MateName"] for mate in mates
                    if mate.get("IsSuppressed") is False and any(
                        endpoint.get("RelativeLeafHierarchyPath") == ep["RelativeLeafHierarchyPath"]
                        and endpoint.get("SourceAssemblyPersistentReferenceBase64")
                        and endpoint.get("SourceAssemblyPersistentReferenceBase64") == ep.get("SourceAssemblyPersistentReferenceBase64")
                        for endpoint in mate.get("Endpoints") or [])]
            candidate["sourceMateReferences"] = references
            candidate["targetSupportPurposeConfirmed"] = bool(references[candidate["supportEndpointId"]])
            candidate["targetHolePurposeConfirmed"] = all(references[i] for i in candidate["holeEndpointIds"])
            candidate["fastenerSpecificationConfirmed"] = False
            candidate["semanticPortPublished"] = False
        report["catalogPath"] = str(path)
        reports.append(report)
    successful = [c for r in reports for c in r["candidates"] if c["positions"]["fits"]]
    confirmed_support = [c for c in successful if c["targetSupportPurposeConfirmed"]]
    result = {
        "schemaVersion": "p000-a600-parallel-slot-screening/v1",
        "status": "geometry_candidates_pending_target_interface_confirmation" if successful else "no_candidate_in_scanned_scope",
        "sourceProject": "project05", "sourceModule": "P000", "targetProject": "project02", "targetModule": "A600",
        "scope": "cached_installation_leaves_plus_native_wastecup_support_leaf",
        "sourceSlotSpacingMeters": spacing, "sourceSlotTravelMeters": travel,
        "sourceSlotWidthMeters": width,
        "explicitDesignPolicy": {"endReserveMeters": .002, "authority": "demo_search_policy_not_vendor_specification",
                                 "placement": "common_feasible_interval_midpoint",
                                 "prototypeTopLevelPoseUsed": False},
        "catalogReports": reports,
        "geometryCandidateCount": len(successful),
        "uniqueHolePairCount": len({tuple(sorted(c["holeEndpointIds"])) for c in successful}),
        "sourceConfirmedSupportCandidateCount": len(confirmed_support),
        "countingNote": "geometryCandidateCount includes opposite support sides; uniqueHolePairCount deduplicates them",
        "preferredCandidateForReview": confirmed_support[0] if confirmed_support else None,
        "cadLaunchAllowed": False, "semanticPortPublished": False,
        "blockingChecks": ["target_hole_purpose", "finite_support_footprint", "installation_side_and_fastener_fit"],
        "cadValidation": {"executed": False, "reason": "target_interface_not_yet_confirmed",
                          "nonPrototypeInitialPose": "not_executed", "saveReopen": "not_executed"},
        "evidence": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                     for p in [source, prototype, *paths]],
        "startedAtUtc": started, "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": time.perf_counter()-clock,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / "slot-match-report.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "status": result["status"],
        "geometryCandidateCount": len(successful), "cadLaunchAllowed": False,
        "catalogs": [{"path": r["catalogPath"], "counts": r["counts"],
                       "candidateCount": len(r["candidates"])} for r in reports],
        "durationSeconds": result["durationSeconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
