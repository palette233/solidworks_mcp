"""Validation and application of explicit Project03 temporary calibration data.

The parameters in this module do not become vendor-authoritative merely because
they are versioned.  Their purpose is narrower: stop reading a target module's
top-level prototype transform implicitly at execution time, make the remaining
dependency reviewable, and provide a deterministic replacement point later.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any


SCHEMA_VERSION = "project03-calibrated-parameters/v1"
ALLOWED_AUTHORITY = {
    "prototype-calibrated-temporary",
    "engineering-estimate-temporary",
    "vendor-authoritative",
}


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_project03_calibrated_parameters(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported Project03 calibrated-parameter schema: {payload.get('schemaVersion')}"
        )
    if payload.get("projectId") != "project03":
        raise ValueError("Calibrated parameters must declare projectId=project03.")
    parameter_set_id = str(payload.get("parameterSetId") or "").strip()
    if not parameter_set_id:
        raise ValueError("parameterSetId is required.")
    anchors = payload.get("poseAnchors")
    if not isinstance(anchors, dict) or not anchors:
        raise ValueError("poseAnchors must be a non-empty object.")

    normalized: dict[str, Any] = {}
    for raw_token, raw_entry in anchors.items():
        token = str(raw_token or "").strip().upper()
        if not token or not isinstance(raw_entry, dict):
            raise ValueError("Each pose anchor must have a non-empty token and object value.")
        transform = raw_entry.get("transform")
        if (
            not isinstance(transform, list)
            or len(transform) != 16
            or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in transform)
        ):
            raise ValueError(f"{token}.transform must contain 16 finite numbers.")
        authority = str(raw_entry.get("authority") or "").strip()
        if authority not in ALLOWED_AUTHORITY:
            raise ValueError(f"{token}.authority is unsupported: {authority}")
        residual_scope = raw_entry.get("residualDofScope")
        if (
            not isinstance(residual_scope, list)
            or not residual_scope
            or any(not str(value or "").strip() for value in residual_scope)
        ):
            raise ValueError(f"{token}.residualDofScope must be a non-empty string list.")
        replacement = str(raw_entry.get("replacementRequired") or "").strip()
        if authority != "vendor-authoritative" and not replacement:
            raise ValueError(f"{token} requires a replacementRequired statement.")
        normalized[token] = {
            **copy.deepcopy(raw_entry),
            "transform": [float(value) for value in transform],
            "authority": authority,
            "residualDofScope": [str(value).strip() for value in residual_scope],
            "engineeringConfirmed": bool(raw_entry.get("engineeringConfirmed")),
        }

    result = copy.deepcopy(payload)
    result["poseAnchors"] = normalized
    result["parameterSetSha256"] = _digest(
        {key: value for key, value in result.items() if key != "parameterSetSha256"}
    )
    return result


def apply_calibrated_pose_anchor(
    module: dict[str, Any],
    module_token: str,
    calibrated_parameters: dict[str, Any],
) -> dict[str, Any]:
    parameters = validate_project03_calibrated_parameters(calibrated_parameters)
    token = str(module_token or "").strip().upper()
    module_observed = str(module.get("ModuleToken") or "").strip().upper()
    if module_observed != token:
        raise ValueError(
            f"Calibrated pose target mismatch: expected {token}, module is {module_observed}."
        )
    entry = (parameters.get("poseAnchors") or {}).get(token)
    if entry is None:
        raise ValueError(f"No calibrated pose anchor is registered for {token}.")
    source_transform_before = copy.deepcopy(module.get("SourceTransform"))
    module["SourceTransform"] = copy.deepcopy(entry["transform"])
    return {
        "parameterSetId": parameters["parameterSetId"],
        "parameterSetSha256": parameters["parameterSetSha256"],
        "moduleToken": token,
        "authority": entry["authority"],
        "engineeringConfirmed": entry["engineeringConfirmed"],
        "residualDofScope": copy.deepcopy(entry["residualDofScope"]),
        "sourceEvidence": entry.get("sourceEvidence"),
        "replacementRequired": entry.get("replacementRequired"),
        "runtimePrototypeTopLevelPoseReadRequired": False,
        "overrodeCapturedSourceTransform": source_transform_before != entry["transform"],
        "appliedTransformSha256": _digest(entry["transform"]),
    }
