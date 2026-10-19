from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from demo_backend.parameter_authority_registry import (
    ParameterAuthorityRegistryError,
    audit_parameter_authorities,
    compile_authoritative_parameter_overlay,
    load_parameter_authority_registry,
    validate_parameter_authority_registry,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _raw_registry() -> dict:
    loaded = load_parameter_authority_registry("project02")
    return {
        key: deepcopy(value)
        for key, value in loaded.items()
        if key not in {"registryPath", "registryDigest"}
    }


def test_project02_registry_keeps_static_demo_but_blocks_production() -> None:
    audit = audit_parameter_authorities(WORKSPACE, "project02")

    assert audit["requirementCount"] == 9
    assert audit["productionAcceptedRequirementCount"] == 0
    assert audit["staticDemoParameterEvidenceAccepted"] is True
    assert audit["productionParameterAuthorityAccepted"] is False
    assert len(audit["productionBlockers"]) == 9
    assert {row["moduleToken"] for row in audit["modules"]} == {
        "A600",
        "A800",
        "A180",
        "A700",
        "A300",
        "A500",
        "A100",
        "A200",
        "T401",
    }


def test_project01_registry_reports_nonstar_bundle_and_demo_service_estimate() -> None:
    audit = audit_parameter_authorities(WORKSPACE, "project01")

    assert audit["requirementCount"] == 3
    assert audit["staticDemoParameterEvidenceAccepted"] is True
    assert audit["productionParameterAuthorityAccepted"] is False
    rows = {row["requirementId"]: row for row in audit["requirements"]}
    assert rows["transport-installation-datum"]["baselineAuthority"] == "cad-measured"
    assert rows["service-module-installation-and-anti-rotation"][
        "ownerModules"
    ] == ["GN00", "SS00"]
    assert rows["service-target-proxies"]["baselineAuthority"] == (
        "temporary-estimate"
    )


def test_confirmed_baselines_form_an_authoritative_overlay(tmp_path: Path) -> None:
    payload = _raw_registry()
    for row in payload["requirements"]:
        row["decision"] = {
            "mode": "approve-baseline",
            "authority": "engineer-confirmed",
            "approvedBy": "test-engineer",
            "approvedAt": "2026-09-30T00:00:00Z",
            "evidencePaths": ["demo/project02_parameter_package.json"],
        }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    audit = audit_parameter_authorities(WORKSPACE, "project02", path=path)
    overlay = compile_authoritative_parameter_overlay("project02", path=path)

    assert audit["productionParameterAuthorityAccepted"] is True
    assert audit["productionAcceptedRequirementCount"] == 9
    assert all(row["productionAuthorityAccepted"] for row in audit["modules"])
    assert len(overlay["decisions"]) == 9
    assert overlay["overlayDigest"]


def test_replacement_requires_exact_declared_values() -> None:
    payload = _raw_registry()
    row = payload["requirements"][0]
    row["decision"] = {
        "mode": "replace",
        "authority": "vendor-confirmed",
        "approvedBy": "vendor",
        "approvedAt": "2026-09-30T00:00:00Z",
        "evidencePaths": ["demo/project02_parameter_package.json"],
        "values": {"operationFace": "face-1"},
    }

    with pytest.raises(ParameterAuthorityRegistryError, match="替换值字段不匹配"):
        validate_parameter_authority_registry(payload)


def test_overlay_refuses_pending_production_requirements() -> None:
    with pytest.raises(ParameterAuthorityRegistryError, match="生产参数仍未闭环"):
        compile_authoritative_parameter_overlay("project02")
