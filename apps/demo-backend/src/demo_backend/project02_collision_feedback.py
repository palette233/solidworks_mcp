from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .project02_direct_geometry import derive_common_axis_clearance_offsets


SCHEMA_VERSION = "project02-collision-feedback/v1"


def component_code(component_name: str) -> str:
    upper = str(component_name).upper()
    if upper.startswith("T401"):
        return "T401"
    if "D062A" in upper:
        return "A" + upper.split("D062A", 1)[1].split(".", 1)[0]
    return str(component_name)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rank1_pose_signature(preview: dict[str, Any] | None) -> dict[str, Any] | None:
    if not preview or not preview.get("solutions"):
        return None
    modules = []
    for module in preview["solutions"][0].get("modules") or []:
        center = module.get("center") or [0.0, 0.0]
        modules.append(
            {
                "componentName": module.get("componentName"),
                "componentCode": component_code(str(module.get("componentName") or "")),
                "center": [round(float(center[0]), 9), round(float(center[1]), 9)],
                "rotationQuarters": int(module.get("rotationQuarters") or 0),
            }
        )
    modules.sort(key=lambda item: str(item["componentName"]).lower())
    encoded = json.dumps(modules, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return {
        "algorithm": "sha256(componentName,center[1e-9m],rotationQuarters)",
        "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "modules": modules,
    }


def build_collision_feedback(
    batch_path: Path,
    *,
    rejected_preview: dict[str, Any] | None = None,
    forbidden_rotations_by_code: dict[str, list[int]] | None = None,
    request: dict[str, Any] | None = None,
    base_frame: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn complete exact B-rep evidence into auditable solver hardening.

    Only exact, complete checks with no failed body-pair calculations may be
    promoted.  This prevents an interrupted or broad-phase-only CAD run from
    silently becoming a hard design rule.
    """

    batch_path = batch_path.resolve()
    batch = json.loads(batch_path.read_text(encoding="utf-8-sig"))
    pairs = list(batch.get("pairs") or [])
    requested = int(batch.get("requestedPairCount") or len(pairs))
    completed = int(batch.get("completedPairCount") or 0)
    if not pairs or completed != requested or len(pairs) != requested:
        raise ValueError(
            "Exact B-rep batch is incomplete; collision evidence cannot be promoted."
        )
    confirmed_pairs: list[dict[str, Any]] = []
    for row in pairs:
        pair = list(row.get("pair") or [])
        if len(pair) != 2:
            raise ValueError("Exact B-rep batch contains a malformed component pair.")
        if not bool(row.get("exactCheckComplete")):
            raise ValueError(f"Exact B-rep check is incomplete for pair {pair!r}.")
        if int(row.get("failedBodyPairCount") or 0) != 0:
            raise ValueError(f"Exact B-rep check has failed body calculations for {pair!r}.")
        count = int(row.get("interferingBodyPairCount") or 0)
        if bool(row.get("hasInterference")) and count > 0:
            confirmed_pairs.append(
                {
                    "firstComponent": pair[0],
                    "secondComponent": pair[1],
                    "firstCode": component_code(pair[0]),
                    "secondCode": component_code(pair[1]),
                    "interferingBodyPairCount": count,
                    "exactCheckComplete": True,
                    "sourceResultPath": row.get("outputPath"),
                }
            )

    rejected_signature = _rank1_pose_signature(rejected_preview)
    rejected_pose_by_code = {
        str(item["componentCode"]): int(item.get("rotationQuarters") or 0) * 90
        for item in (rejected_signature or {}).get("modules") or []
    }
    restrictions = []
    for code, degrees in sorted((forbidden_rotations_by_code or {}).items()):
        normalized = sorted({int(value) % 360 for value in degrees})
        if normalized:
            restrictions.append(
                {
                    "componentCode": code,
                    "forbiddenRotationDegrees": normalized,
                    "reason": "CAD exact-interference feedback for rejected candidate",
                }
            )

    forbidden_by_code = {
        str(item["componentCode"]): set(item["forbiddenRotationDegrees"])
        for item in restrictions
    }
    conditional_pairs = {
        frozenset((component_code(str(pair[0])), component_code(str(pair[1]))))
        for pair in ((request or {}).get("staticCollisionPolicy") or {}).get(
            "brepOnAabbOverlapPairs", []
        )
        if isinstance(pair, list) and len(pair) == 2
    }
    rejected_modules_by_code = {
        str(item["componentCode"]): item
        for item in (rejected_signature or {}).get("modules") or []
    }
    feedback_policy = (request or {}).get("collisionFeedbackPolicy") or {}
    exclusion_half_width = float(
        feedback_policy.get("relativePoseExclusionHalfWidthMeters", 0.005)
    )
    if exclusion_half_width <= 0 or exclusion_half_width > 0.05:
        raise ValueError(
            "relativePoseExclusionHalfWidthMeters must be within (0, 0.05]."
        )
    for row in confirmed_pairs:
        excluded_by = [
            code
            for code in (row["firstCode"], row["secondCode"])
            if rejected_pose_by_code.get(code) in forbidden_by_code.get(code, set())
        ]
        row["rejectedPoseRotationDegrees"] = {
            code: rejected_pose_by_code.get(code)
            for code in (row["firstCode"], row["secondCode"])
        }
        pair_key = frozenset((row["firstCode"], row["secondCode"]))
        pose_local = not excluded_by and pair_key in conditional_pairs
        row["globalHardeningEligible"] = not excluded_by and not pose_local
        row["poseLocalExclusionEligible"] = pose_local
        row["excludedByForbiddenOrientationCodes"] = excluded_by
        row["enforcementScope"] = (
            "rejected-orientation-only"
            if excluded_by
            else "relative-pose-exclusion"
            if pose_local
            else "global-pair-hardening"
        )
        if pose_local:
            first_pose = rejected_modules_by_code.get(row["firstCode"])
            second_pose = rejected_modules_by_code.get(row["secondCode"])
            if first_pose is None or second_pose is None:
                raise ValueError(
                    "Conditional B-rep collision feedback requires both rejected module poses."
                )
            delta_u = float(first_pose["center"][0]) - float(second_pose["center"][0])
            delta_v = float(first_pose["center"][1]) - float(second_pose["center"][1])
            exact_offsets: list[list[float]] | None = None
            exact_detail_path = Path(str(row.get("sourceResultPath") or ""))
            if not exact_detail_path.is_absolute():
                exact_detail_path = batch_path.parent / exact_detail_path
            projection_frame = base_frame or (rejected_preview or {}).get("baseFrame") or {}
            if exact_detail_path.is_file() and projection_frame:
                exact_detail = json.loads(
                    exact_detail_path.read_text(encoding="utf-8-sig")
                )
                exact_offsets = derive_common_axis_clearance_offsets(
                    exact_detail,
                    projection_frame,
                    moving_component_code=row["firstCode"],
                    clearance_meters=float(
                        (request or {}).get("minimumClearanceMeters", 0.01)
                    ),
                )

            # A complete leaf-level result can describe a much larger forbidden
            # relative-pose region than the small generic neighbourhood.  The
            # four common-axis offsets are sufficient translations for moving
            # the first component clear of every currently intersecting leaf
            # AABB.  Their signed extrema therefore define one forbidden
            # rectangle: a candidate must leave it along at least one axis.
            u_negative = min(
                (item[0] for item in exact_offsets or [] if item[0] < 0.0),
                default=-exclusion_half_width,
            )
            u_positive = max(
                (item[0] for item in exact_offsets or [] if item[0] > 0.0),
                default=exclusion_half_width,
            )
            v_negative = min(
                (item[1] for item in exact_offsets or [] if item[1] < 0.0),
                default=-exclusion_half_width,
            )
            v_positive = max(
                (item[1] for item in exact_offsets or [] if item[1] > 0.0),
                default=exclusion_half_width,
            )
            row["relativePoseExclusion"] = {
                "componentCode": row["firstCode"],
                "referenceComponentCode": row["secondCode"],
                "minDeltaU": delta_u + u_negative,
                "maxDeltaU": delta_u + u_positive,
                "minDeltaV": delta_v + v_negative,
                "maxDeltaV": delta_v + v_positive,
                "halfWidthMeters": exclusion_half_width,
                "derivation": (
                    "exact-leaf-aabb-common-axis-clearance"
                    if exact_offsets
                    else "generic-local-neighbourhood"
                ),
                "candidateEscapeOffsetsMeters": exact_offsets,
            }
    confirmed_pairs.sort(key=lambda row: (row["firstCode"], row["secondCode"]))

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "evidence": {
            "batchPath": str(batch_path),
            "batchSha256": _sha256(batch_path),
            "assemblyPath": batch.get("assemblyPath"),
            "requestedPairCount": requested,
            "completedPairCount": completed,
            # In the batch schema, hardFailureCount means that the
            # zero-interference acceptance rule failed.  Those rows are the
            # collision evidence we intentionally consume; calculation
            # failures are represented separately by failedBodyPairCount.
            "zeroInterferenceRejectionCount": int(batch.get("hardFailureCount") or 0),
            "failedBodyPairCount": 0,
            "exactEvidenceAccepted": True,
        },
        "confirmedCollisionPairs": confirmed_pairs,
        "orientationRestrictions": restrictions,
        "rejectedCandidate": rejected_signature,
        "enforcementPolicy": {
            "confirmedCollisionPairs": (
                "ordinary solid pairs become hard leaf-occupancy separation; conditional "
                "B-rep pairs exclude only the exact failed relative-pose neighbourhood"
            ),
            "orientationRestrictions": "remove forbidden quarter-turn candidates",
            "conditionalBrep": "retained for final exact verification of accepted candidates",
        },
    }


def apply_collision_feedback(
    request: dict[str, Any],
    feedback: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if feedback.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Unsupported Project02 collision-feedback schema.")
    if not (feedback.get("evidence") or {}).get("exactEvidenceAccepted"):
        raise ValueError("Collision feedback is not backed by accepted exact evidence.")

    hardened = copy.deepcopy(request)
    semantics = hardened.get("moduleSemantics") or {}
    names_by_code: dict[str, str] = {}
    for name in semantics:
        code = component_code(name)
        if code in names_by_code:
            raise ValueError(f"Multiple semantic modules resolve to component code {code}.")
        names_by_code[code] = name

    applied_pairs = []
    orientation_scoped_pairs = []
    relative_pose_exclusions = []
    existing_constraint_ids = {
        str(item.get("id") or "") for item in hardened.get("processConstraints") or []
    }
    for row in feedback.get("confirmedCollisionPairs") or []:
        first_code = str(row.get("firstCode") or "")
        second_code = str(row.get("secondCode") or "")
        if first_code not in names_by_code or second_code not in names_by_code:
            raise ValueError(
                f"Feedback pair {first_code}-{second_code} is absent from module semantics."
            )
        if row.get("poseLocalExclusionEligible"):
            exclusion = row.get("relativePoseExclusion") or {}
            component_code_value = str(exclusion.get("componentCode") or first_code)
            reference_code_value = str(
                exclusion.get("referenceComponentCode") or second_code
            )
            evidence_tag = str(
                (feedback.get("evidence") or {}).get("batchSha256") or "unknown"
            )[:8]
            constraint_id = (
                f"cad-feedback-exclude-{first_code.lower()}-"
                f"{second_code.lower()}-{evidence_tag}"
            )
            constraint = {
                "id": constraint_id,
                "type": "relativeAnchorExclusionWindow",
                "component": names_by_code[component_code_value],
                "referenceComponent": names_by_code[reference_code_value],
                "minDeltaU": float(exclusion["minDeltaU"]),
                "maxDeltaU": float(exclusion["maxDeltaU"]),
                "minDeltaV": float(exclusion["minDeltaV"]),
                "maxDeltaV": float(exclusion["maxDeltaV"]),
                "hard": True,
                "retainInReducedPrototype": True,
                "source": "complete exact CAD B-rep rejected relative pose",
            }
            if constraint_id not in existing_constraint_ids:
                hardened.setdefault("processConstraints", []).append(constraint)
                existing_constraint_ids.add(constraint_id)
            repair_parameters = semantics[constraint["component"]].setdefault(
                "parameters", {}
            )
            existing_offsets = list(
                repair_parameters.get("candidateDirectionalOffsetsMeters") or []
            )
            exact_offsets = list(exclusion.get("candidateEscapeOffsetsMeters") or [])
            # Repeated exact failures at adjacent poses mean that a fixed
            # 5.1 mm nudge has reached a collision-count plateau. Escalate the
            # next candidate step by the number of already-recorded exclusions
            # for this ordered pair. Normal process/reach constraints still
            # reject an over-large move, so no engineering rule is relaxed.
            previous_pair_exclusions = sum(
                1
                for item in hardened.get("processConstraints") or []
                if item is not constraint
                and item.get("type") == "relativeAnchorExclusionWindow"
                and item.get("component") == constraint["component"]
                and item.get("referenceComponent")
                == constraint["referenceComponent"]
            )
            if exact_offsets:
                escalated_offsets = exact_offsets
                escape_strategy = "exact-leaf-aabb-common-axis-clearance"
            else:
                escape_step = float(exclusion.get("halfWidthMeters") or 0.005) + 0.0001
                escape = escape_step * (previous_pair_exclusions + 1)
                escalated_offsets = [
                    [escape, 0.0],
                    [-escape, 0.0],
                    [0.0, escape],
                    [0.0, -escape],
                ]
                escape_strategy = "escalated-generic-local-neighbourhood"
            # Candidates are relative to the newest warm start. Retaining the
            # previous 5.1 mm values would let the deterministic solver pick an
            # adjacent failed pose again before it ever reaches the escalated
            # candidate. Preserve them only as provenance, then replace them.
            repair_parameters["previousCollisionFeedbackOffsetsMeters"] = existing_offsets
            repair_parameters["candidateDirectionalOffsetsMeters"] = escalated_offsets
            constraint["candidateEscapeOffsetsMeters"] = escalated_offsets
            constraint["escapeEscalationIndex"] = previous_pair_exclusions + 1
            constraint["escapeStrategy"] = escape_strategy
            relative_pose_exclusions.append(constraint)
            continue
        if row.get("globalHardeningEligible") is False:
            orientation_scoped_pairs.append([first_code, second_code])
            continue
        first_name = names_by_code[first_code]
        second_name = names_by_code[second_code]
        first_parameters = semantics[first_name].setdefault("parameters", {})
        second_parameters = semantics[second_name].setdefault("parameters", {})
        first_targets = list(first_parameters.get("hardOccupancyClearanceWith") or [])
        second_targets = list(second_parameters.get("hardOccupancyClearanceWith") or [])
        if second_name not in first_targets:
            first_targets.append(second_name)
        if first_name not in second_targets:
            second_targets.append(first_name)
        first_parameters["hardOccupancyClearanceWith"] = first_targets
        second_parameters["hardOccupancyClearanceWith"] = second_targets
        applied_pairs.append([first_code, second_code])

    applied_restrictions = []
    for rule in feedback.get("orientationRestrictions") or []:
        code = str(rule.get("componentCode") or "")
        if code not in names_by_code:
            raise ValueError(f"Feedback orientation component {code} is absent from semantics.")
        name = names_by_code[code]
        forbidden = {int(value) % 360 for value in rule.get("forbiddenRotationDegrees") or []}
        allowed = [int(round(float(value))) % 360 for value in semantics[name].get("allowedRotationDegrees") or []]
        retained = [value for value in allowed if value not in forbidden]
        if not retained:
            raise ValueError(f"Feedback removes every allowed orientation for {name}.")
        semantics[name]["allowedRotationDegrees"] = retained
        applied_restrictions.append(
            {"componentCode": code, "retainedRotationDegrees": retained}
        )

    hardened["collisionFeedback"] = {
        "schemaVersion": feedback["schemaVersion"],
        "evidence": feedback["evidence"],
        "confirmedCollisionPairs": applied_pairs,
        "orientationScopedCollisionPairs": orientation_scoped_pairs,
        "relativePoseExclusions": relative_pose_exclusions,
        "orientationRestrictions": applied_restrictions,
        "rejectedCandidateSha256": (feedback.get("rejectedCandidate") or {}).get("sha256"),
    }
    metadata = {
        "confirmedHardOccupancyPairs": applied_pairs,
        "orientationScopedCollisionPairs": orientation_scoped_pairs,
        "relativePoseExclusions": relative_pose_exclusions,
        "orientationRestrictions": applied_restrictions,
        "rejectedCandidateSha256": (feedback.get("rejectedCandidate") or {}).get("sha256"),
    }
    return hardened, metadata


def evaluate_feedback_gate(
    preview: dict[str, Any],
    feedback: dict[str, Any],
) -> dict[str, Any]:
    confirmed = {
        frozenset((str(row["firstCode"]), str(row["secondCode"])))
        for row in feedback.get("confirmedCollisionPairs") or []
        if row.get("globalHardeningEligible") is not False
    }
    local_exclusions = [
        row
        for row in feedback.get("confirmedCollisionPairs") or []
        if row.get("poseLocalExclusionEligible")
    ]
    forbidden = {
        str(row["componentCode"]): {
            (int(value) // 90) % 4 for value in row.get("forbiddenRotationDegrees") or []
        }
        for row in feedback.get("orientationRestrictions") or []
    }
    rejected_hash = (feedback.get("rejectedCandidate") or {}).get("sha256")
    rows = []
    for solution in preview.get("solutions") or []:
        orientation_violations = []
        for module in solution.get("modules") or []:
            code = component_code(str(module.get("componentName") or ""))
            quarter = int(module.get("rotationQuarters") or 0) % 4
            if quarter in forbidden.get(code, set()):
                orientation_violations.append({"componentCode": code, "rotationQuarters": quarter})
        risk_pairs = {
            frozenset((str(row.get("firstCode")), str(row.get("secondCode"))))
            for row in solution.get("conditionalLeafAabbRisks") or []
        }
        confirmed_pair_risks = [sorted(pair) for pair in confirmed & risk_pairs]
        module_by_code = {
            component_code(str(module.get("componentName") or "")): module
            for module in solution.get("modules") or []
        }
        relative_pose_violations = []
        for row in local_exclusions:
            exclusion = row.get("relativePoseExclusion") or {}
            component = module_by_code.get(str(exclusion.get("componentCode") or ""))
            reference = module_by_code.get(
                str(exclusion.get("referenceComponentCode") or "")
            )
            if component is None or reference is None:
                relative_pose_violations.append(
                    {"pair": [row["firstCode"], row["secondCode"]], "missingPose": True}
                )
                continue
            delta_u = float(component["center"][0]) - float(reference["center"][0])
            delta_v = float(component["center"][1]) - float(reference["center"][1])
            if (
                float(exclusion["minDeltaU"]) - 1e-9
                <= delta_u
                <= float(exclusion["maxDeltaU"]) + 1e-9
                and float(exclusion["minDeltaV"]) - 1e-9
                <= delta_v
                <= float(exclusion["maxDeltaV"]) + 1e-9
            ):
                relative_pose_violations.append(
                    {
                        "pair": [row["firstCode"], row["secondCode"]],
                        "deltaU": delta_u,
                        "deltaV": delta_v,
                    }
                )
        candidate_hash = _rank1_pose_signature({"solutions": [solution]})["sha256"]
        rows.append(
            {
                "rank": solution.get("rank"),
                "orientationViolations": orientation_violations,
                "confirmedPairRisks": confirmed_pair_risks,
                "relativePoseExclusionViolations": relative_pose_violations,
                "repeatsRejectedCandidate": bool(rejected_hash and candidate_hash == rejected_hash),
                "passed": not orientation_violations
                and not confirmed_pair_risks
                and not relative_pose_violations
                and not (rejected_hash and candidate_hash == rejected_hash),
            }
        )
    return {
        "solutionCount": len(rows),
        "solutions": rows,
        "passed": bool(rows) and all(row["passed"] for row in rows),
        "rule": "Every returned candidate must avoid forbidden orientations, globally hardened collision pairs, exact failed relative-pose windows, and the rejected pose signature.",
    }
