from pathlib import Path

from demo_backend.global_assembly_context import (
    apply_global_command_preview,
    preview_global_assembly_command,
)
from demo_backend.global_cad_transaction_packets import (
    compile_global_cad_transaction_manifest,
)
from demo_backend.global_relation_catalog_release import (
    load_relation_catalog_release,
)
from demo_backend.project05_complete_cumulative_chain import (
    D000_REFRESH_LEGACY_ID,
    MODULE_ORDER,
    NATURAL_LANGUAGE_REQUIREMENTS,
    build_d000_deterministic_candidate,
    audit_complete_chain_manifest,
    build_candidate_catalog,
    build_release_spec,
    build_scenario,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def test_project05_complete_chain_catalog_contains_exact_seven_current_templates():
    catalog, provenance = build_candidate_catalog(WORKSPACE)
    ids = {
        row["globalTemplateId"]
        for row in catalog["connectionTemplates"]
    }

    assert provenance["status"] == "ready_for_immutable_release"
    assert provenance["moduleOrder"] == list(MODULE_ORDER)
    assert provenance["optionalExcludedModules"] == ["K000"]
    assert "template/project05/g000-to-a000-static-four-relation-v2/f738bc665b" in ids
    assert "template/project05/d000-to-a000-deterministic-three-mate-v3/741d02e8d3" in ids
    assert "template/project05/d000-to-a000-scoped-driving-v2/465c1f471a" not in ids
    assert "template/project05/g000-to-a000-nonanchor-driving-v1/8502cf3dab" not in ids


def test_project05_complete_chain_release_spec_binds_every_packet_to_evidence(tmp_path):
    candidate_path = WORKSPACE / ".tmp" / tmp_path.name / "candidate.json"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text("{}", encoding="utf-8")
    spec = build_release_spec(
        WORKSPACE,
        release_id="test-project05-complete-chain",
        candidate_catalog_path=candidate_path,
    )

    assert len(spec["templates"]) == 7
    assert [row["legacyTemplateId"].split("_", 1)[0] for row in spec["templates"]] == list(
        MODULE_ORDER
    )
    assert all(row["evidencePath"] for row in spec["templates"])
    g000 = next(row for row in spec["templates"] if row["legacyTemplateId"].startswith("G000_"))
    assert g000["expectedMateCount"] == 4
    assert g000["repeatabilityBaselineEvidencePath"]


def test_project05_complete_chain_scenario_keeps_post_checks_independent():
    scenario = build_scenario("release-test")

    assert len(NATURAL_LANGUAGE_REQUIREMENTS) == 8
    assert scenario["expectedPacketOrder"] == list(MODULE_ORDER)
    assert scenario["acceptance"]["nonPrototypeInitialPosePerPacket"] is True
    assert scenario["acceptance"]["realMateCreationPerPacket"] is True
    assert scenario["acceptance"]["saveCloseReopenPerPacket"] is True
    assert scenario["acceptance"]["collisionOrBrepRequired"] is False
    assert scenario["acceptance"]["dynamicProcessRequired"] is False


def test_d000_refresh_changes_only_identity_and_non_source_placement_policy():
    source = WORKSPACE / (
        "demo/global_assembly_catalog/v1/driving-v1-preview/"
        "project05_D000_A000_scoped_driving_v2/semantic_port_catalog.json"
    )
    graph_path = WORKSPACE / (
        "demo/semantic_ports/project05_resolved_pair_jobs/"
        "project05-job-2fd5dca2ddd7/attempt-01/transaction/effective-graph.json"
    )
    import json

    semantic_source = json.loads(source.read_text(encoding="utf-8-sig"))
    graph_source = json.loads(graph_path.read_text(encoding="utf-8-sig"))
    semantic, graph = build_d000_deterministic_candidate(
        semantic_source,
        graph_source,
        semantic_catalog_path="candidate/semantic.json",
        endpoint_catalog_path="candidate/endpoints.json",
        effective_graph_path="candidate/graph.json",
        initial_placement_variant=1,
    )

    before = semantic_source["connectionTemplates"][0]
    after = semantic["connectionTemplates"][0]
    assert after["templateId"] == D000_REFRESH_LEGACY_ID
    assert after["mateSteps"] == before["mateSteps"]
    assert graph["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert graph["EditPolicy"]["initialPlacementVariant"] == 1
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []


def test_complete_chain_preflight_rejects_historical_source_pose_manifest():
    import json

    path = WORKSPACE / (
        "demo/global_assembly_contexts/"
        "project05-complete-seven-addon-v1.cad-transaction-manifest.json"
    )
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    report = audit_complete_chain_manifest(
        WORKSPACE,
        manifest,
        expected_release_id=(
            "relation-v59-project05-complete-seven-addon-driving-20261014"
        ),
    )

    assert report["status"] == "blocked"
    d000 = report["packets"][0]
    assert d000["moduleToken"] == "D000"
    assert d000["initialPlacementMode"] == "source_pose"
    assert "forbidden_initial_placement_mode:source_pose" in d000["blockers"]
    assert report["collisionIncludedInPreflightDecision"] is False


def test_complete_chain_preflight_accepts_v61_nonprototype_manifest():
    import json

    release_id = "relation-v61-project05-complete-seven-addon-driving-20261014"
    catalog, _ = load_relation_catalog_release(
        WORKSPACE
        / "demo/global_assembly_catalog/releases"
        / release_id
        / "release-manifest.json",
        workspace_root=WORKSPACE,
    )
    # The active context path is intentionally mutable and can be reused by a
    # later UI demo.  Rebuild revision 8 from the immutable revision-7 snapshot
    # instead of letting test order or a previous demo overwrite this fixture.
    context_path = WORKSPACE / (
        "demo/global_assembly_contexts/"
        "project05-complete-seven-addon-v2.revisions/revision-000007.json"
    )
    context = json.loads(context_path.read_text(encoding="utf-8-sig"))
    preview = preview_global_assembly_command(
        catalog,
        context,
        {"requirement": "最后安装项目05的龙门与双阀Z轴运动组。"},
    )
    assert preview["status"] == "ready"
    context = apply_global_command_preview(
        context,
        preview,
        preview_digest=preview["previewDigest"],
        confirmed=True,
    )
    manifest = compile_global_cad_transaction_manifest(catalog, context)
    report = audit_complete_chain_manifest(
        WORKSPACE,
        manifest,
        expected_release_id=release_id,
    )

    assert report["status"] == "passed"
    assert report["actualModuleOrder"] == list(MODULE_ORDER)
    assert all(row["passed"] for row in report["packets"])
    assert all(row["casePoseAnchorCount"] == 0 for row in report["packets"])
    assert all(row["targetLeafPoseAnchorCount"] == 0 for row in report["packets"])
