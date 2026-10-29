"""Bind real Project05 P000 faces to Project03 AA00 support/position datums.

This is a positioning Demo, not a bolt-pattern compatibility assertion.  No CAD
is opened here: the six endpoints come from existing leaf-scoped face catalogs.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.cross_project_wastecup_datum_candidate import (  # noqa: E402
    CrossProjectWasteCupDatumError, _axis_match, _bound_endpoints, _digest,
    _endpoint_index, _mate, _module, _port,
)

P05 = ROOT / "demo/global_assembly_catalog/v1/combination-v1-preview/project05-nonanchor-driving-v6/P000"
AA00_CATALOG = ROOT / "demo/cross_project_substitution/scanner-slot-discovery-v1/project03_AA00_project01_SM00/aa00-scanner-support-leaf-face-catalog.json"
AA00_SUPPORT_EVIDENCE = ROOT / "demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1/assembly_plan_effective.nonprototype.json"
CACHE_ENTRY = ROOT / "demo/global_assembly_contexts/base_wrapper_cache/7d63f8e557c32448109e318405c54fcb38822b7043612411108216f69af810af/cache-entry.json"
OUTPUT = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project03-v1/support-position-demo-v1"
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
AA00_IDS = ["face:aa00:ae9c22cef02ef7bd", "face:aa00:9ef0fb60b1085456", "face:aa00:0dea78ae25e9aab4"]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_candidate(*, aa00_catalog: dict, p000_graph: dict,
                    p000_semantic_catalog: dict, p000_endpoint_catalog: dict,
                    longitudinal_m: float = .4, lateral_m: float = .2,
                    initial_placement_variant: int = 1) -> dict:
    """Pure, fail-closed graph construction; no input dictionaries are mutated."""
    for value in (longitudinal_m, lateral_m):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Position distances must be finite non-negative metres")
    if isinstance(initial_placement_variant, bool) or not isinstance(initial_placement_variant, int) or initial_placement_variant < 0:
        raise ValueError("initial placement variant must be a non-negative integer")
    index = _endpoint_index(aa00_catalog)
    try:
        context = [copy.deepcopy(index[key]) for key in AA00_IDS]
    except KeyError as exc:
        raise ValueError(f"Missing AA00 real face endpoint: {exc.args[0]}") from exc
    target_rows = _bound_endpoints(_port(p000_semantic_catalog, "P000.frame_installation"), p000_endpoint_catalog)
    target = [_axis_match(target_rows, axis) for axis in ((0., -1., 0.), (1., 0., 0.), (0., 0., 1.))]
    for row, expected in zip(context, ((0., 1., 0.), (-1., 0., 0.), (0., 0., -1.))):
        _axis_match([row], expected)
        if row["Endpoint"]["ModuleToken"] != "AA00":
            raise ValueError("Selected support datum does not belong to AA00")
    if len({r["Endpoint"]["RelativeLeafHierarchyPath"] for r in context}) != 1:
        raise ValueError("AA00 datums must be on the same audited rigid support leaf")
    if len({r["Endpoint"]["RelativeLeafHierarchyPath"] for r in target}) != 1:
        raise ValueError("P000 datums must be on the same rigid mounting leaf")

    # Independent geometry arithmetic in the AA00 plate's own coordinates.
    # The chosen aligned side faces plus anti-aligned support imply (-x,-y,+z)
    # between mounting-leaf frames. This diagnostic is NEVER a CAD pose anchor.
    support_box = context[2]["Endpoint"]["FaceBoxLocal"]
    target_box = target[2]["Endpoint"]["FaceBoxLocal"]
    tx = context[1]["Endpoint"]["FaceCenterLocal"][0] - lateral_m + target[1]["Endpoint"]["FaceCenterLocal"][0]
    ty = context[0]["Endpoint"]["FaceCenterLocal"][1] + longitudinal_m + target[0]["Endpoint"]["FaceCenterLocal"][1]
    tz = context[2]["Endpoint"]["FaceCenterLocal"][2]
    footprint = [tx-target_box[3], ty-target_box[4], tz, tx-target_box[0], ty-target_box[1], tz]
    tol = 1e-9
    inside = all(footprint[i] >= support_box[i]-tol and footprint[i+3] <= support_box[i+3]+tol for i in (0, 1))
    if not inside:
        raise ValueError("P000 support footprint is outside the finite AA00 plate bounding region")
    # This is a cheap catalog-based indication, not trim-loop containment/B-rep.
    local_features = [r["EndpointId"] for r in index.values()
                      if r["Endpoint"]["FaceArea"] < .1
                      and r["Endpoint"]["FaceBoxLocal"][0] < footprint[3]-tol
                      and r["Endpoint"]["FaceBoxLocal"][3] > footprint[0]+tol
                      and r["Endpoint"]["FaceBoxLocal"][1] < footprint[4]-tol
                      and r["Endpoint"]["FaceBoxLocal"][4] > footprint[1]+tol]
    finite_region = {
        "status": "inside_support_face_bounding_region",
        "coordinateFrame": "AA00_support_leaf_local",
        "supportFaceBoundingBoxMeters": support_box,
        "targetSupportFootprintBoundingBoxMeters": footprint,
        "withinFiniteSupportBoundingRegion": inside,
        "intersectingSmallFaceBoundingBoxes": local_features,
        "trimLoopContainment": "not_evaluated",
        "collisionOrBrep": "not_evaluated",
        "derivedGeometryUsedAsPoseAnchor": False,
    }
    base = _module(aa00_catalog, "AA00")
    module = _module(p000_graph, "P000")
    module["SourceTransform"] = list(IDENTITY)
    mates = []
    for i, (target_row, context_row) in enumerate(zip(target, context)):
        is_support = i == 2
        mate = _mate(f"P000_AA00_DATUM_{'SUPPORT' if is_support else 'DISTANCE_'+str(i+1)}",
                     0 if is_support else 5, "swMateCOINCIDENT" if is_support else "swMateDISTANCE",
                     1 if is_support else 0, "swMateAlignANTI_ALIGNED" if is_support else "swMateAlignALIGNED",
                     target_row, context_row, distance=None if is_support else (longitudinal_m, lateral_m)[i])
        # _mate is the existing serializer; only graph membership changes here.
        # The actual endpoints above are the ORIGINAL AA00 records, not A600 copies.
        mate["ModuleTokens"] = ["P000", "AA00"]
        mate.pop("MateId")
        mate["MateId"] = "mate:cross-project-wastecup:" + _digest(mate)[:16]
        mates.append(mate)
    policy = {
        "mode": "support_position_demo", "holePatternMatchRequired": False,
        "actualFixationMethod": "not_verified", "actualFixationNotice": "实际固定方式暂未验证",
        "directMechanicalCompatibilityClaim": False,
        "positionParametersMeters": {"longitudinal": longitudinal_m, "lateral": lateral_m, "supportGap": 0},
        "parameterAuthority": "explicit_demo_design_parameters_not_vendor_mounting_dimensions",
        "targetSourceTransformMeaning": "identity_placeholder_not_final_pose_witness",
        "acceptance": "active_real_mates_support_and_distance_parameters_save_close_reopen",
    }
    audit = {
        "schemaVersion": "cross-project-wastecup-datum-candidate/v1",
        "sourceProjectId": "project05", "sourceModuleToken": "P000",
        "targetProjectId": "project03", "targetBaseToken": "AA00", "targetSlotRole": "WasteCup",
        "placementMode": "three_orthogonal_planar_datums", "expectedResidualExternalDof": 0,
        "prototypeTopLevelTargetPoseUsed": False, "caseAnchorUsed": False, "targetLeafPoseAnchorsUsed": False,
        "physicalFastenerCompatibility": "not_evaluated", "adapterCompatibility": "not_evaluated",
        "collisionOrBrep": "not_evaluated", "productionReady": False,
        "status": "ready_for_nonprototype_cad_validation", "cadLaunchAllowed": True,
        "mateCount": 3, "targetEndpointIds": [r["EndpointId"] for r in target],
        "contextEndpointIds": AA00_IDS, "finiteSupportRegionCheck": finite_region,
        "sourceEvidence": {"aa00FaceCatalog": str(AA00_CATALOG),
                           "aa00SupportAlreadyUsedByAG00": str(AA00_SUPPORT_EVIDENCE),
                           "p000FaceCatalog": str(P05 / "face_endpoint_catalog.json"),
                           "p000PortCatalog": str(P05 / "semantic_port_catalog.json")},
        "limitations": ["Positioning only; actual fastening and hole matching are not verified.",
                        "The footprint bounding check is not collision or B-rep verification.",
                        "A real nonprototype CAD run and save-close-reopen verification are required."],
        **policy,
    }
    graph = {
        "SchemaVersion": "editable-module-mate-graph/v1", "SourceAssemblyPath": None,
        "ModuleCount": 2, "InterModuleMateCount": 3, "Modules": [base, module], "Mates": mates,
        "BaseGraphPolicy": {"status": "cross_project_datum_placement_demo", "caseAnchorAllowed": False,
                            "prototypeTopLevelTargetPoseAllowed": False, "targetLeafPoseAnchorsAllowed": False},
        "CaseAnchor": None, "TargetLeafPoseAnchors": [],
        "EditPolicy": {"baseModuleToken": "AA00", "initialPlacementMode": "deterministic",
                       "initialPlacementVariant": initial_placement_variant, "sourceGraphImmutable": True,
                       "fixedModuleTokens": ["AA00"], "caseAnchoredModuleTokens": [],
                       "targetLeafPoseAnchors": [], "fixCaseAnchorBeforeMates": False},
        "SupportPositionDemoPolicy": policy, "CrossProjectWasteCupDatumAudit": copy.deepcopy(audit),
    }
    # A read-only witness lives ONLY in the audit, not in executable pose fields.
    # Infer the known AA00 leaf->module geometry from its three catalog normals
    # and a point, then map P000 leaf points through the new design distances.
    base_transform = base["SourceTransform"]
    def world_to_base(point):
        delta = [point[j]-base_transform[9+j] for j in range(3)]
        return [sum(delta[j]*base_transform[i*3+j] for j in range(3))/base_transform[12] for i in range(3)]
    columns = [[-v for v in context[1]["Endpoint"]["FaceNormalWorld"]],
               context[0]["Endpoint"]["FaceNormalWorld"],
               [-v for v in context[2]["Endpoint"]["FaceNormalWorld"]]]
    source_point = context[2]["Endpoint"]["FaceCenterLocal"]
    source_world = context[2]["Endpoint"]["FaceCenterWorld"]
    offset = [source_world[j]-sum(source_point[k]*columns[k][j] for k in range(3)) for j in range(3)]
    target_support_z = target[2]["Endpoint"]["FaceCenterLocal"][2]
    def leaf_point_to_base(point):
        on_plate = [tx-point[0], ty-point[1], tz+point[2]-target_support_z]
        world = [offset[j]+sum(on_plate[k]*columns[k][j] for k in range(3)) for j in range(3)]
        return world_to_base(world)
    audit["geometricWitness"] = {
        "purpose": "read_only_signed_side_and_support_verification_after_CAD",
        "targetLeafRelativePath": target[2]["Endpoint"]["RelativeLeafHierarchyPath"],
        "baseModuleToken": "AA00", "coordinateFrame": "AA00_module_local",
        "targetModuleTopLevelTransformUsed": False,
        "notAnExecutablePoseAnchor": True,
        "requiredObservation": "Compose runtime P000 leaf transform with P000 top-level transform, then invert AA00 top-level transform; do not assume leaf frame equals module frame.",
        "referencePoints": [{"name": name, "targetLeafPointMeters": point,
                             "expectedBaseModulePointMeters": leaf_point_to_base(point)}
                            for name, point in [("leaf_origin", [0, 0, 0])]
                            + [(f"datum_{i+1}_center", row["Endpoint"]["FaceCenterLocal"]) for i, row in enumerate(target)]],
        "positionToleranceMeters": 1e-6,
    }
    audit["effectiveGraphDigest"] = _digest(graph)
    selected_catalog = {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1", "SourceAssemblyPath": None,
        "Modules": copy.deepcopy(graph["Modules"]), "ModuleCount": 2,
        "Endpoints": target + context, "EndpointCount": 6, "CatalogMode": "selected_real_endpoints",
        "SourceMateFacesOnly": False, "Diagnostics": ["AA00 endpoints are copied from the real leaf catalog; no A600 face substitution."],
    }
    return {"effectiveGraph": graph, "audit": audit, "endpointCatalog": selected_catalog}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--longitudinal-mm", type=float, default=400)
    parser.add_argument("--lateral-mm", type=float, default=200)
    parser.add_argument("--initial-placement-variant", type=int, default=1)
    args = parser.parse_args()
    started, clock = datetime.now(timezone.utc).isoformat(), time.perf_counter()
    if args.output.exists():
        raise FileExistsError("New Demo must not overwrite an existing evidence directory")
    package = build_candidate(aa00_catalog=read(AA00_CATALOG), p000_graph=read(P05 / "assembly_plan_effective.json"),
                              p000_semantic_catalog=read(P05 / "semantic_port_catalog.json"),
                              p000_endpoint_catalog=read(P05 / "face_endpoint_catalog.json"),
                              longitudinal_m=args.longitudinal_mm/1000, lateral_m=args.lateral_mm/1000,
                              initial_placement_variant=args.initial_placement_variant)
    cache = read(CACHE_ENTRY)
    source = CACHE_ENTRY.parent / cache["assemblyFile"]
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_sha != cache["assemblySha256"] or cache["inputs"]["baseContextModuleToken"] != "FL9A24D063AA00":
        raise ValueError("Cached AA00 single-base wrapper identity/hash mismatch")
    args.output.mkdir(parents=True)
    for name, payload in (("candidate_effective_mate_graph.json", package["effectiveGraph"]),
                          ("candidate_audit.json", package["audit"]),
                          ("face_endpoint_catalog.json", package["endpointCatalog"])):
        (args.output/name).write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    graph_path = (args.output / "candidate_effective_mate_graph.json").resolve()
    summary = {"success": True, "sourceAssemblyPath": str(source), "sourceAssemblySha256": source_sha,
               "sourceWrapperCacheEntry": str(CACHE_ENTRY), "effectiveGraphPath": str(graph_path),
               "effectiveGraphSha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
               "outputAssemblyPath": str((args.output / "project03-AA00-project05-P000-support-demo-v1.SLDASM").resolve()),
               "initialPlacementVariant": args.initial_placement_variant,
               "startedAtUtc": started, "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
               "durationSeconds": time.perf_counter()-clock, **package["effectiveGraph"]["SupportPositionDemoPolicy"]}
    (args.output/"build-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
