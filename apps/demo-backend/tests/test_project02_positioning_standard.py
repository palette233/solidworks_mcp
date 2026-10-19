from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from demo_backend.project02_positioning_standard import (
    Project02PositioningStandardError,
    audit_project02_positioning_standard,
    load_project02_positioning_standard,
    positioning_standard_binding,
    validate_project02_positioning_standard,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _raw_standard() -> dict:
    loaded = load_project02_positioning_standard()
    return {
        key: deepcopy(value)
        for key, value in loaded.items()
        if key not in {"standardPath", "standardDigest"}
    }


def test_project02_inferred_standard_is_ready_for_coarse_layout_only() -> None:
    audit = audit_project02_positioning_standard(WORKSPACE)

    assert audit["coarseLayoutReady"] is True
    assert audit["productionReady"] is False
    assert audit["resultStatus"] == "PROJECT02_INFERRED_POSITIONING_STANDARD_READY_FOR_COARSE_LAYOUT"
    assert audit["missingEvidence"] == []
    assert set(audit["pendingAuthorityRequirementIds"]) == {
        "transport-installation-datum",
        "scanner-optical-geometry",
    }
    assert {row["moduleToken"] for row in audit["modules"]} == {"A800", "A180"}


def test_standard_exposes_traceable_bindings_for_both_modules() -> None:
    standard = load_project02_positioning_standard()

    a800 = positioning_standard_binding(standard, "A800")
    a180 = positioning_standard_binding(standard, "a180")

    assert a800["ruleId"] == "A600-A800-inferred-positioning-v1"
    assert a180["ruleId"] == "A600-A180-mechanical-A800-optical-positioning-v1"
    assert a800["standardDigest"] == a180["standardDigest"]
    assert a800["coarseLayoutUseAllowed"] is True
    assert a180["productionUseAllowed"] is False


def test_a800_must_expose_its_longitudinal_residual_dof() -> None:
    payload = _raw_standard()
    payload["modules"]["A800"]["mechanical"]["residualDofClosure"]["dof"] = "none"

    with pytest.raises(Project02PositioningStandardError, match="沿X方向"):
        validate_project02_positioning_standard(payload)


def test_a180_working_distance_order_is_fail_closed() -> None:
    payload = _raw_standard()
    distance = payload["modules"]["A180"]["functional"]["workingDistanceMeters"]
    distance["minimum"] = 0.2

    with pytest.raises(Project02PositioningStandardError, match="工作距离"):
        validate_project02_positioning_standard(payload)
