"""Saved-Replay broad-phase and strict-pair audit for Project 01."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _code(name: str, marker: str = "N074") -> str:
    stem = name.split("-", 1)[0]
    if marker not in stem:
        raise ValueError(f"Cannot derive module code from '{name}' using marker '{marker}'.")
    return stem.split(marker, 1)[1].split(".", 1)[0]


def _bounds(box: dict[str, Any], shift: tuple[float, float]) -> tuple[float, ...]:
    raw = box["installationBoundsMeters"]
    return (
        float(raw["minU"]) + shift[0],
        float(raw["minV"]) + shift[1],
        float(raw["minN"]),
        float(raw["maxU"]) + shift[0],
        float(raw["maxV"]) + shift[1],
        float(raw["maxN"]),
    )


def _overlap(first: tuple[float, ...] | list[float], second: tuple[float, ...] | list[float], inflation: float = 0.0) -> bool:
    return all(
        float(first[index]) - inflation <= float(second[index + 3]) + inflation
        and float(second[index]) - inflation <= float(first[index + 3]) + inflation
        for index in range(3)
    )


def _union(boxes: list[list[float]]) -> list[float]:
    return [
        min(box[0] for box in boxes), min(box[1] for box in boxes), min(box[2] for box in boxes),
        max(box[3] for box in boxes), max(box[4] for box in boxes), max(box[5] for box in boxes),
    ]


def _component_matches(component: dict[str, Any], criterion: dict[str, Any]) -> bool:
    path_name = Path(str(component.get("Path") or component.get("path") or "")).name.casefold()
    hierarchy = str(component.get("HierarchyPath") or component.get("hierarchyPath") or "").casefold()
    expected_file = str(criterion.get("componentPathFileName") or "").casefold()
    fragments = [str(item).casefold() for item in criterion.get("hierarchyContainsAll") or []]
    return (not expected_file or path_name == expected_file) and all(fragment in hierarchy for fragment in fragments)


def _pair_matches(pair: dict[str, Any], rule: dict[str, Any]) -> bool:
    first = pair.get("FirstComponent") or pair.get("firstComponent") or {}
    second = pair.get("SecondComponent") or pair.get("secondComponent") or {}
    participants = rule.get("participants") or []
    if len(participants) != 2:
        raise ValueError(f"Allowed-contact rule '{rule.get('id')}' must have exactly two participants.")
    return (
        _component_matches(first, participants[0]) and _component_matches(second, participants[1])
    ) or (
        _component_matches(first, participants[1]) and _component_matches(second, participants[0])
    )


def evaluate_project01_allowed_contacts(
    exact_documents: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Classify exact B-rep hits against narrow, instance-aware provisional rules."""

    rules = policy.get("allowedContacts") or []
    hits = [
        pair
        for document in exact_documents
        for pair in document.get("InterferingBodyPairs") or document.get("interferingBodyPairs") or []
    ]
    matched_rows: list[dict[str, Any]] = []
    illegal_rows: list[dict[str, Any]] = []
    use_count = {str(rule.get("id")): 0 for rule in rules}
    for pair in hits:
        matching = [rule for rule in rules if _pair_matches(pair, rule)]
        if len(matching) != 1:
            illegal_rows.append({"pair": pair, "matchingRuleIds": [item.get("id") for item in matching]})
            continue
        rule = matching[0]
        rule_id = str(rule["id"])
        use_count[rule_id] += 1
        matched_rows.append({"ruleId": rule_id, "pair": pair})

    unused_or_mismatched = []
    for rule in rules:
        rule_id = str(rule["id"])
        expected = int(rule.get("expectedOccurrenceCount", 1))
        actual = use_count[rule_id]
        if actual != expected:
            unused_or_mismatched.append({"ruleId": rule_id, "expectedOccurrenceCount": expected, "actualOccurrenceCount": actual})

    all_classified = not illegal_rows and not unused_or_mismatched
    return {
        "policyId": policy.get("policyId"),
        "policyStatus": policy.get("status"),
        "engineeringConfirmed": policy.get("engineeringConfirmed") is True,
        "allInterferencesClassified": all_classified,
        "detectedInterferenceCount": len(hits),
        "temporarilyAllowedCount": len(matched_rows),
        "illegalInterferenceCount": len(illegal_rows),
        "ruleCount": len(rules),
        "matched": matched_rows,
        "illegal": illegal_rows,
        "unusedOrMismatchedRules": unused_or_mismatched,
    }


def build_project01_replay_screening(
    occupancy: dict[str, Any],
    replay_layout: dict[str, Any],
    replay_result: dict[str, Any],
    source_poses: dict[str, Any],
    *,
    project_id: str = "project01",
    code_marker: str = "N074",
) -> dict[str, Any]:
    pose_payload = next(
        (step.get("payload") for step in replay_result.get("steps") or [] if step.get("tool") == "list_component_poses"),
        None,
    )
    if not isinstance(pose_payload, list):
        raise ValueError("Replay result has no saved top-level pose payload.")
    actual_by_name = {item["Name"]: item for item in pose_payload}
    source_by_name = {item["Name"]: item for item in source_poses.get("components") or []}
    if set(actual_by_name) != set(source_by_name):
        raise ValueError("Saved Replay and source top-level component sets differ.")

    layout_by_name = {
        item["componentName"]: item
        for item in replay_layout.get("components") or []
    }
    pose_rows = []
    for name in sorted(source_by_name):
        actual = actual_by_name[name]
        source = source_by_name[name]
        placement = layout_by_name.get(name, {})
        expected_transform = list(source["Transform"])
        target_axes = (
            placement.get("targetXAxisWorld"),
            placement.get("targetYAxisWorld"),
            placement.get("targetZAxisWorld"),
        )
        if all(isinstance(axis, list) and len(axis) == 3 for axis in target_axes):
            expected_transform[0:3] = target_axes[0]
            expected_transform[3:6] = target_axes[1]
            expected_transform[6:9] = target_axes[2]
        target_translation = placement.get("targetComponentTranslation")
        if isinstance(target_translation, list) and len(target_translation) == 3:
            expected_transform[9:12] = target_translation
        transform_error = max(
            abs(float(a) - float(b))
            for a, b in zip(actual["Transform"], expected_transform)
        )
        delta_world = placement.get("replayDeltaWorldMeters") or [0.0, 0.0, 0.0]
        expected_aabb = [
            float(value) + float(delta_world[index % 3])
            for index, value in enumerate(source["BoundingBoxWorld"])
        ]
        aabb_error = max(
            abs(float(a) - float(b))
            for a, b in zip(actual["BoundingBoxWorld"], expected_aabb)
        )
        try:
            code = _code(name, code_marker)
        except ValueError:
            code = name.split("-", 1)[0]
        pose_rows.append({"code": code, "componentName": actual["Name"], "maximumTransformElementError": transform_error, "maximumWorldAabbErrorMeters": aabb_error})

    objects = {item["id"]: item for item in occupancy.get("layoutObjects") or []}
    expected_codes = {code for item in objects.values() for code in item.get("memberCodes") or []}
    actual_by_code = {}
    for item in pose_payload:
        try:
            code = _code(item["Name"], code_marker)
        except ValueError:
            continue
        if code in expected_codes:
            actual_by_code[code] = item
    replay_components = replay_layout.get("components") or []
    shifts: dict[str, tuple[float, float]] = {}
    for item in replay_components:
        shift = item.get("replayDeltaInstallationMeters") or [0.0, 0.0]
        value = (float(shift[0]), float(shift[1]))
        previous = shifts.setdefault(item["layoutObjectId"], value)
        if previous != value:
            raise ValueError(f"Members of '{item['layoutObjectId']}' do not share one rigid shift.")

    policy = occupancy["staticCollisionPolicy"]
    margin = float(policy["aabbInflationPerSideMeters"])
    strict_rows = []
    for profile in policy.get("strictPairProfiles") or []:
        first_id, second_id = profile["pair"]
        leaf = profile["occupancyMode"] == "partner-scoped-leaf-body-boxes"
        key = "leafBodyOccupancyBoxes" if leaf else "occupancyBoxes"
        first_boxes = [_bounds(box, shifts.get(first_id, (0.0, 0.0))) for box in objects[first_id][key]]
        second_boxes = [_bounds(box, shifts.get(second_id, (0.0, 0.0))) for box in objects[second_id][key]]
        hits = sum(_overlap(first, second, margin) for first in first_boxes for second in second_boxes)
        strict_rows.append({"pair": [first_id, second_id], "occupancyMode": profile["occupancyMode"], "inflatedAabbHitCount": hits, "success": hits == 0})

    world_box_by_object = {
        object_id: _union([actual_by_code[code]["BoundingBoxWorld"] for code in item["memberCodes"]])
        for object_id, item in objects.items()
    }
    conditional_rows = []
    for item in policy.get("conditionalBrepPairs") or []:
        first_id, second_id = item["pair"]
        overlaps = _overlap(world_box_by_object[first_id], world_box_by_object[second_id])
        conditional_rows.append({"pair": [first_id, second_id], "worldAabbOverlaps": overlaps, "route": "leaf-brep" if overlaps else "world-aabb-clear", "reason": item["reason"]})
    installation_rows = []
    for item in policy.get("installationContactPairs") or []:
        first_id, second_id = item["pair"]
        overlaps = _overlap(world_box_by_object[first_id], world_box_by_object[second_id])
        installation_rows.append({"pair": [first_id, second_id], "worldAabbOverlaps": overlaps, "route": "installation-penetration-audit" if overlaps else "world-aabb-clear", "reason": item["reason"]})

    strict_success = all(item["success"] for item in strict_rows)
    pose_success = max(item["maximumTransformElementError"] for item in pose_rows) <= 1e-6
    pending_conditional = [item for item in conditional_rows if item["route"] == "leaf-brep"]
    pending_installation = [item for item in installation_rows if item["route"] == "installation-penetration-audit"]
    return {
        "schemaVersion": 1,
        "caseId": project_id,
        "status": f"{project_id.upper()}_PRIORITY_BREP_READY" if strict_success and pose_success else f"{project_id.upper()}_REPLAY_SCREENING_FAILED",
        "productionReady": False,
        "replayPoseAudit": {
            "success": pose_success,
            "componentCount": len(pose_rows),
            "maximumTransformElementError": max(item["maximumTransformElementError"] for item in pose_rows),
            "maximumWorldAabbErrorMeters": max(item["maximumWorldAabbErrorMeters"] for item in pose_rows),
            "largestWorldAabbChangeCode": max(pose_rows, key=lambda item: item["maximumWorldAabbErrorMeters"])["code"],
            "components": pose_rows,
        },
        "strictAabb": {"success": strict_success, "pairCount": len(strict_rows), "failedPairCount": sum(not item["success"] for item in strict_rows), "pairs": strict_rows},
        "conditionalBrep": {"policyPairCount": len(conditional_rows), "pendingPairCount": len(pending_conditional), "worldAabbClearPairCount": len(conditional_rows) - len(pending_conditional), "pairs": conditional_rows},
        "installationContact": {"policyPairCount": len(installation_rows), "pendingPairCount": len(pending_installation), "worldAabbClearPairCount": len(installation_rows) - len(pending_installation), "pairs": installation_rows},
        "nextAction": "Run leaf B-rep for conditional pairs, then compare installation-contact interference with the prototype mate/contact baseline.",
    }
