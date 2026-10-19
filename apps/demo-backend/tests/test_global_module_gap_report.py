from __future__ import annotations

import copy
import json
from pathlib import Path

from demo_backend.global_module_gap_report import (
    build_global_module_gap_report,
    validate_global_module_gap_report,
)


ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def _project05_package() -> dict:
    root = Path(
        "demo/global_assembly_catalog/releases/"
        "relation-v28-project05-all-eight-addon-portable-driving-20261011"
    )
    return {
        "catalog": _read(str(root / "global_module_catalog.json")),
        "manifest": _read(str(root / "release-manifest.json")),
        "evidence": _read(str(root / "driving-release-evidence.json")),
        "manifestPath": str(root / "release-manifest.json"),
    }


def _project01_combination_package() -> dict:
    root = Path(
        "demo/global_assembly_catalog/releases/"
        "relation-v38-project01-topology-bound-combination-driving-20261011"
    )
    return {
        "catalog": _read(str(root / "global_module_catalog.json")),
        "manifest": _read(str(root / "release-manifest.json")),
        "evidence": _read(str(root / "driving-release-evidence.json")),
        "manifestPath": str(root / "release-manifest.json"),
    }


def test_project05_rigid_modules_are_distinguished_from_open_external_pose():
    report = build_global_module_gap_report(
        _read("demo/global_assembly_catalog/v1/global_module_catalog.json"),
        [_project05_package()],
        active_project_ids=("project05",),
        deferred_module_refs=(),
    )
    validation = validate_global_module_gap_report(report)
    assert validation["success"] is True
    by_ref = {
        ref: row
        for row in report["modules"]
        for ref in row["projectModuleRefs"]
    }
    for ref in ("project05:M000", "project05:N000", "project05:P000"):
        assert by_ref[ref]["status"] == "portable_verified"
        assert by_ref[ref]["verifiedTemplateCount"] >= 1
    assert by_ref["project05:G000"]["status"] == "external_pose_evidence_required"
    assert by_ref["project05:A000"]["status"] == "context_provider_verified"


def test_runtime_revocation_overrides_immutable_release_authorization():
    package = _project05_package()
    target = next(
        row
        for row in package["catalog"]["connectionTemplates"]
        if row.get("legacyTemplateId") == "N000_to_A000_nonanchor_driving_v2"
    )
    registry = {
        "templates": [
            {
                "globalTemplateId": target["globalTemplateId"],
                "status": "blocked_external_pose_branch",
            }
        ]
    }
    report = build_global_module_gap_report(
        _read("demo/global_assembly_catalog/v1/global_module_catalog.json"),
        [copy.deepcopy(package)],
        safety_registry=registry,
        active_project_ids=("project05",),
        deferred_module_refs=(),
    )
    n000 = next(
        row for row in report["modules"] if "project05:N000" in row["projectModuleRefs"]
    )
    assert n000["status"] == "runtime_safety_blocked"
    assert n000["nextAction"] == "keep_blocked_until_new_external_pose_evidence"


def test_authorized_template_combination_closes_gn00_external_placement():
    report = build_global_module_gap_report(
        _read("demo/global_assembly_catalog/v1/global_module_catalog.json"),
        [_project01_combination_package()],
        active_project_ids=("project01",),
        deferred_module_refs=(),
    )
    gn00 = next(
        row for row in report["modules"] if "project01:GN00" in row["projectModuleRefs"]
    )
    assert gn00["status"] == "portable_verified"
    assert any(
        row["authorizationKind"] == "template_combination"
        for row in gn00["bestEvidence"]
    )


def test_a700_is_explicitly_deferred_in_active_scope():
    report = build_global_module_gap_report(
        _read("demo/global_assembly_catalog/v1/global_module_catalog.json"),
        [],
        active_project_ids=("project02",),
    )
    a700 = next(
        row for row in report["modules"] if "project02:A700" in row["projectModuleRefs"]
    )
    assert a700["status"] == "deferred"
    assert a700["nextAction"] == "keep_deferred"


def test_complete_project01_templates_with_bidirectional_edges_are_release_pending():
    report = build_global_module_gap_report(
        _read("demo/global_assembly_catalog/v1/global_module_catalog.json"),
        [_project01_combination_package()],
        active_project_ids=("project01",),
        deferred_module_refs=(),
    )
    by_ref = {
        ref: row
        for row in report["modules"]
        for ref in row["projectModuleRefs"]
    }
    for ref in ("project01:FF00", "project01:GJ00"):
        assert by_ref[ref]["status"] == "release_pending"
        assert by_ref[ref]["declaredCompleteTemplateCount"] >= 1
        assert by_ref[ref]["completeInstallationTemplateCount"] >= 1
        assert by_ref[ref]["nextAction"] == "audit_and_publish_existing_template"


def test_empirical_nonanchor_failure_overrides_declared_complete_template():
    empirical = {
        "modules": [
            {
                "projectId": "project03",
                "moduleToken": "AG00",
                "state": "complete_installation_bundle_required",
            }
        ]
    }
    report = build_global_module_gap_report(
        _read("demo/global_assembly_catalog/v1/global_module_catalog.json"),
        [],
        empirical_evidence_audit=empirical,
        active_project_ids=("project03",),
        deferred_module_refs=(),
    )
    ag00 = next(
        row for row in report["modules"] if "project03:AG00" in row["projectModuleRefs"]
    )

    assert ag00["status"] == "installation_bundle_repair_required"
    assert ag00["nextAction"] == "add_independent_installation_datum_then_rerun_cad"
    assert ag00["blockers"] == ["NONANCHOR_CAD_PROVES_EXTERNAL_DOF_REMAINS"]
