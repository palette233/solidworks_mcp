from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from demo_backend.project03_calibrated_parameters import (
    apply_calibrated_pose_anchor,
    validate_project03_calibrated_parameters,
)


ROOT = Path(__file__).resolve().parents[3]


def load_parameters() -> dict:
    return json.loads(
        (ROOT / "demo/semantic_ports/project03_calibrated_parameters_v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_parameter_set_is_versioned_and_explicitly_non_authoritative() -> None:
    validated = validate_project03_calibrated_parameters(load_parameters())
    assert len(validated["parameterSetSha256"]) == 64
    assert set(validated["poseAnchors"]) == {
        "FL9A24D063AG00",
        "FL9A24D063AB00",
    }
    assert all(
        entry["authority"] == "prototype-calibrated-temporary"
        and entry["engineeringConfirmed"] is False
        and entry["replacementRequired"]
        for entry in validated["poseAnchors"].values()
    )


def test_invalid_transform_is_rejected() -> None:
    payload = copy.deepcopy(load_parameters())
    payload["poseAnchors"]["FL9A24D063AG00"]["transform"] = [1.0, 2.0]
    with pytest.raises(ValueError, match="16 finite numbers"):
        validate_project03_calibrated_parameters(payload)


def test_apply_rejects_wrong_module() -> None:
    module = {"ModuleToken": "FL9A24D063AH00", "SourceTransform": [0.0] * 16}
    with pytest.raises(ValueError, match="target mismatch"):
        apply_calibrated_pose_anchor(
            module, "FL9A24D063AG00", load_parameters()
        )
