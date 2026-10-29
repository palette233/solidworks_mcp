from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from demo_backend.hybrid_plane_axis_slot_selection import (
    build_f000_hybrid_axis_slot_catalog,
    compile_f000_hybrid_axis_validation_package,
    rank_f000_hybrid_axis_candidates,
)
from demo_backend.parameterized_datum_placement import (
    publish_parameterized_datum_pair_release,
)
from demo_backend.parameterized_datum_relation_release import (
    HYBRID_PLANE_AXIS_INTERFACE_TYPE,
    build_parameterized_datum_catalog_package,
    publish_parameterized_datum_relation_release,
)
from demo_backend.parameterized_datum_validation_execution import (
    derive_parameterized_datum_relation_release_id,
)


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / (
    "demo/cross_project_substitution/expanded-project03-v1/"
    "relation-v62-project03-expanded-cross-project-chain-driving-20261014."
    "catalog-preview.json"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _materialize_synthetic_validated_hybrid_pair(tmp_path: Path) -> Path:
    catalog = build_f000_hybrid_axis_slot_catalog(ROOT)
    ranked = rank_f000_hybrid_axis_candidates(
        catalog,
        "project03::AA00",
        longitudinal_meters=0.078,
        lateral_meters=0.2115,
        limit=1,
    )
    selected = ranked[0]["endpointId"]
    package = compile_f000_hybrid_axis_validation_package(
        ROOT,
        slot_definition_id="project03::AA00",
        selected_axis_endpoint_id=selected,
        evidence={
            "confirmed": True,
            "source": "unit_test_reviewed_semantic_position",
            "confirmedBy": "test-engineer",
            "confirmedAt": "2026-10-26T00:00:00Z",
        },
    )
    validation = tmp_path / "validation-f000-aa00-v1"
    validation.mkdir()
    graph = validation / "effective-mate-graph.json"
    endpoints = validation / "selected-face-endpoint-catalog.json"
    manifest = validation / "validation-package.json"
    materialized = copy.deepcopy(package)
    _write(graph, materialized.pop("effectiveGraph"))
    _write(endpoints, materialized.pop("selectedEndpointCatalog"))
    materialized["artifacts"] = {
        "effectiveGraph": {"path": str(graph.resolve()), "sha256": _sha(graph)},
        "selectedEndpointCatalog": {
            "path": str(endpoints.resolve()),
            "sha256": _sha(endpoints),
        },
    }
    _write(manifest, materialized)

    output = validation / "synthetic-cad-output.SLDASM"
    output.write_bytes(b"hybrid-plane-axis-synthetic-cad-evidence")
    cad_result = {
        "schemaVersion": "checkpoint-selected-face-context-insert-run/v1",
        "jobId": "synthetic-hybrid-pair-unit-test",
        "success": True,
        "effectiveGraphSha256": _sha(graph),
        "toolResult": {
            "Success": True,
            "ExecutionMode": "context_incremental_insert",
            "OriginalComponentRemoved": True,
            "IndependentComponentInserted": True,
            "RequestedMateCount": 3,
            "CreatedMateCount": 3,
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
            "TargetConstraintStateAccepted": True,
            "TargetFullyConstrained": True,
            "MateSolveClean": True,
            "ComponentSemanticsMatch": True,
            "TargetCaseAnchored": False,
            "RequestedTargetLeafPoseAnchorCount": 0,
            "AppliedTargetLeafPoseAnchorCount": 0,
            "MateResults": [{"Success": True} for _ in range(3)],
            "MateVerifications": [
                {
                    "Found": True,
                    "TypeMatches": True,
                    "AlignmentMatches": True,
                    "DistanceMatches": True,
                    "AngleMatches": True,
                    "AdvancedOptionsMatch": True,
                }
                for _ in range(3)
            ],
        },
        "sourceAssemblyUnchanged": True,
        "outputClosedAfterVerification": True,
        "targetSourceSessionClean": True,
        "outputAssemblyPath": str(output.resolve()),
        "outputAssemblySha256": _sha(output),
        "durationSeconds": 1.25,
    }
    _write(validation / "cad-result.json", cad_result)
    pair_release = publish_parameterized_datum_pair_release(
        materialized, cad_result
    )
    _write(validation / "pair-release.json", pair_release)
    return validation


def test_hybrid_pair_release_and_relation_bridge_preserve_axis_semantics(
    tmp_path: Path,
):
    validation = _materialize_synthetic_validated_hybrid_pair(tmp_path)
    pair = json.loads(
        (validation / "pair-release.json").read_text(encoding="utf-8")
    )
    assert pair["placementMode"] == "reviewed_hybrid_plane_axis_datum"
    assert pair["selectedAxisEndpointId"].startswith("face:aa00:")
    assert pair["diameterCompatibility"] == "not_evaluated"
    assert "three planar" not in pair["claimBoundary"]

    base_catalog = json.loads(BASE.read_text(encoding="utf-8-sig"))
    package = build_parameterized_datum_catalog_package(
        base_global_catalog=base_catalog,
        validation_dir=validation,
        semantic_catalog_path="synthetic/semantic_port_catalog.json",
        endpoint_catalog_path="synthetic/face_endpoint_catalog.json",
        base_graph_path="synthetic/base_parameterized_datum_graph.json",
    )
    semantic = package["semanticCatalog"]
    assert {port["interfaceType"] for port in semantic["ports"]} == {
        HYBRID_PLANE_AXIS_INTERFACE_TYPE
    }
    assert {
        binding["role"]
        for port in semantic["ports"]
        for binding in port["endpointBindings"]
    } == {"support_plane", "orientation_datum", "locating_axis"}
    assert sum(
        evidence["geometryClass"] == "Cylinder"
        for port in semantic["ports"]
        for evidence in port["endpointEvidence"]
    ) == 2
    assert [
        step["mateType"] for step in semantic["connectionTemplates"][0]["mateSteps"]
    ] == [0, 3, 1]
    assert package["boundary"]["selectedAxisEndpointId"] == pair[
        "selectedAxisEndpointId"
    ]
    assert package["boundary"]["diameterCompatibility"] == "not_evaluated"


def test_hybrid_pair_publishes_an_immutable_relation_authority():
    work_root = Path(
        tempfile.mkdtemp(prefix=".tmp-hybrid-relation-release-", dir=ROOT / "demo")
    )
    try:
        validation = _materialize_synthetic_validated_hybrid_pair(work_root)
        pair = json.loads(
            (validation / "pair-release.json").read_text(encoding="utf-8")
        )
        release_id = derive_parameterized_datum_relation_release_id(pair)
        output_root = work_root / "relation-releases"
        result = publish_parameterized_datum_relation_release(
            ROOT,
            validation,
            release_id,
            BASE,
            output_root=output_root,
        )
        assert result["releaseId"] == release_id
        assert result["relationExecutionMode"] == "datum_placement_demo"
        assert result["physicalFasteningVerified"] is False
        manifest_path = output_root / release_id / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        binding = manifest["releaseMetadata"]["parameterizedDatumPairBinding"]
        assert binding["placementMode"] == "reviewed_hybrid_plane_axis_datum"
        assert binding["selectedAxisEndpointId"] == pair["selectedAxisEndpointId"]
        assert manifest["releaseMetadata"]["collisionOrBrep"] == "not_evaluated"
    finally:
        shutil.rmtree(work_root, ignore_errors=True)
