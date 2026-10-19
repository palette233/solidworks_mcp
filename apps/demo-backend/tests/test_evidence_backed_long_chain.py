import json
from pathlib import Path

import pytest

from demo_backend.evidence_backed_long_chain import (
    EvidenceBackedLongChainError,
    build_evidence_backed_long_chain_plan,
    order_requirements_by_released_installation_dependencies,
)
from demo_backend.global_relation_catalog_release import (
    load_relation_catalog_release,
)
from demo_backend.global_assembly_context import (
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _release(name: str):
    return load_relation_catalog_release(
        WORKSPACE
        / "demo/global_assembly_catalog/releases"
        / name
        / "release-manifest.json",
        workspace_root=WORKSPACE,
    )


def test_existing_four_module_cross_project_chain_is_release_backed():
    catalog, manifest = _release(
        "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
    )
    plan = build_evidence_backed_long_chain_plan(
        catalog,
        manifest,
        base_module="project03:AA00",
        ordered_modules=["project01:SS00", "project03:AI00", "project01:BD00"],
    )

    assert plan["status"] == "ready_for_natural_language_job_compilation"
    assert plan["finalTopLevelModuleCount"] == 4
    assert plan["crossProjectAdditionCount"] == 2
    assert plan["nativeAdditionCount"] == 1
    assert all(row["declaredResidualDof"] == 0 for row in plan["steps"])
    assert all(row["prototypeTopLevelPoseRequired"] is False for row in plan["steps"])


def test_unreleased_native_module_is_blocked_even_when_catalog_contains_template():
    catalog, manifest = _release(
        "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
    )
    plan = build_evidence_backed_long_chain_plan(
        catalog,
        manifest,
        base_module="project03:AA00",
        ordered_modules=["project03:AD00"],
    )

    assert plan["status"] == "blocked"
    assert plan["plannedAdditionCount"] == 0
    assert plan["blockers"][0]["code"] == "NO_AUTHORIZED_INSTALLATION_TEMPLATE"


def test_release_catalog_digest_mismatch_is_rejected():
    catalog, manifest = _release(
        "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
    )
    tampered = dict(manifest)
    tampered["catalogDigest"] = "wrong"
    with pytest.raises(EvidenceBackedLongChainError, match="摘要不匹配"):
        build_evidence_backed_long_chain_plan(
            catalog,
            tampered,
            base_module="project03:AA00",
            ordered_modules=["project03:AI00"],
        )


def test_plan_digest_is_deterministic():
    catalog, manifest = _release(
        "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
    )
    kwargs = {
        "base_module": "project03:AA00",
        "ordered_modules": ["project01:SS00", "project03:AI00"],
    }
    assert build_evidence_backed_long_chain_plan(
        catalog, manifest, **kwargs
    )["planDigest"] == build_evidence_backed_long_chain_plan(
        catalog, manifest, **kwargs
    )["planDigest"]


def test_release_bound_candidates_exclude_historical_templates_and_collapse_direction():
    catalog, manifest = _release(
        "relation-v62-project03-expanded-cross-project-chain-driving-20261014"
    )
    context = create_global_assembly_context(
        "symmetric-choice",
        catalog_digest=catalog["catalogDigest"],
        relation_release_binding={
            "releaseId": manifest["releaseId"],
            "releaseDigest": manifest["releaseDigest"],
            "releaseManifestPath": (
                "demo/global_assembly_catalog/releases/"
                "relation-v62-project03-expanded-cross-project-chain-driving-20261014/"
                "release-manifest.json"
            ),
            "catalogDigest": manifest["catalogDigest"],
            "authorizedDrivingTemplateIds": (
                manifest["scope"]["authorizedDrivingTemplateIds"]
            ),
        },
    )
    base = preview_global_assembly_command(
        catalog, context, {"requirement": "先安装项目03 AA00基座"}
    )
    assert base["status"] == "ready"
    context = apply_global_command_preview(
        context,
        base,
        preview_digest=base["previewDigest"],
        confirmed=True,
    )
    gantry = preview_global_assembly_command(
        catalog, context, {"requirement": "在基座上安装项目03 AB00龙门模组"}
    )

    assert gantry["status"] == "ready"
    assert len(gantry["connectionCandidates"]) == 1
    assert gantry["connectionCandidates"][0]["portable"] is True
    assert gantry["blockers"] == []


def test_shuffled_requirements_are_ordered_by_released_installation_dependencies():
    catalog, manifest = _release(
        "relation-v62-project03-expanded-cross-project-chain-driving-20261014"
    )
    shuffled = [
        "最后增加项目03 AB00龙门点胶模组。",
        "增加项目03 AG00清洁称重模组。",
        "安装项目01 SS00产品传输模组。",
        "建立项目03 AA00设备箱体与固定安装环境。",
        "增加项目03 AJ00供胶系统。",
        "增加项目01 BD00喷嘴校准模组。",
        "增加项目03 AI00条码扫描模组。",
        "增加项目03 AD00定位模组。",
    ]

    result = order_requirements_by_released_installation_dependencies(
        catalog,
        manifest,
        shuffled,
    )

    assert result["status"] == "ready"
    assert result["reordered"] is True
    assert [row["primaryRole"] for row in result["steps"]] == [
        "Base",
        "Transport",
        "Scanner",
        "Calibration",
        "Positioning",
        "GlueSupply",
        "CleaningWeighing",
        "Gantry",
    ]
    assert result["steps"][0]["inputOrder"] == 4
    assert all(
        row["dependsOnPlannedOrder"] == [1] for row in result["steps"][1:]
    )
    assert result["cadStarted"] is False
