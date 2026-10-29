"""Bind a released native cleaning installation to explicit service envelopes.

The released mate recipe remains the only placement authority.  Captured
subtree envelopes are read-only functional proxies: they prove that the saved
CAD result returned the selected cleaning module to its registered native
service station, not that cleaning, collision or fastening was validated.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from . import role_station_geometry as geometry
from .global_relation_catalog_release import load_relation_catalog_release
from .station_rule_registry import read, sha, workspace_file


CAPTURE_MODES = {
    "isolated_complete_leaf_capture",
    "complete_grouped_subtree_unions",
}


def _one(rows: list[dict[str, Any]], message: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise ValueError(message)
    return rows[0]


def _same_path(first: str | Path, second: str | Path) -> bool:
    return str(Path(first).resolve()).casefold() == str(Path(second).resolve()).casefold()


def _max_bound_delta(first: dict[str, float], second: dict[str, float]) -> float:
    keys = ("minU", "maxU", "minV", "maxV", "minN", "maxN")
    return max(abs(float(first[key]) - float(second[key])) for key in keys)


def build_native_cleaning_station(
    workspace: Path | str,
    config: dict[str, Any],
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    if config.get("sourceModuleDefinitionId") != config.get("nativeRoleModuleDefinitionId"):
        raise ValueError("different cleaning models require explicit service-group correspondence")
    tolerance = (config.get("acceptance") or {}).get("groupBoundsToleranceMeters")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("service-group tolerance must be finite and positive")

    evidence: dict[str, str] = {}

    def load(value: str) -> dict[str, Any]:
        path = workspace_file(root, value)
        evidence[str(path)] = sha(path)
        return read(path)

    inputs = config.get("inputs") or {}
    occupancy = load(inputs["movingOccupancy"])
    labels = load(inputs["subtreeLabels"])
    graph = load(inputs["nativeGraph"])
    release_path = workspace_file(root, inputs["referenceReleasePath"])
    evidence[str(release_path)] = sha(release_path)
    _, release = load_relation_catalog_release(release_path, workspace_root=root)
    template_id = config.get("expectedGlobalTemplateId")
    authorized = set((release.get("scope") or {}).get("authorizedDrivingTemplateIds") or [])
    if (
        not isinstance(template_id, str)
        or template_id not in set(release.get("derivedTemplateIds") or [])
        or template_id not in authorized
    ):
        raise ValueError("reference release does not authorize the configured cleaning template")

    source_token, base_token = config["sourceToken"], config["baseToken"]
    try:
        captured = occupancy["modules"][source_token]
    except KeyError as error:
        raise ValueError("cleaning occupancy does not contain the configured source") from error
    capture_mode = config.get("captureMode", "isolated_complete_leaf_capture")
    if capture_mode not in CAPTURE_MODES:
        raise ValueError("cleaning service proxy capture mode is unsupported")
    boxes = captured.get("occupancyBoxes") or []
    if capture_mode == "isolated_complete_leaf_capture":
        if (
            captured.get("leafCoverageComplete") is not True
            or captured.get("occupancySource") != config.get("occupancySource")
            or not isinstance(captured.get("leafBodyCount"), int)
            or captured["leafBodyCount"] <= 0
            or len(captured.get("leafBodyOccupancyBoxes") or [])
            != captured["leafBodyCount"]
        ):
            raise ValueError("cleaning service proxy requires complete captured leaf occupancy")
        captured_leaf_count = captured["leafBodyCount"]
    else:
        captured_leaf_count = sum(int(row.get("leafBodyCount") or 0) for row in boxes)
        if (
            captured.get("leafCoverageComplete") is not True
            or not boxes
            or captured_leaf_count <= 0
            or any(
                row.get("source") != config.get("occupancySource")
                or not isinstance(row.get("leafBodyCount"), int)
                or row["leafBodyCount"] <= 0
                for row in boxes
            )
        ):
            raise ValueError(
                "cleaning service proxy requires complete grouped subtree-union occupancy"
            )

    native = _one(
        [
            row
            for row in graph.get("Modules") or []
            if row.get("ModuleToken") == source_token
            and row.get("HierarchyPath") == config.get("nativeInstanceHierarchyPath")
        ],
        "native cleaning instance is missing or ambiguous",
    )
    base = _one(
        [
            row
            for row in graph.get("Modules") or []
            if row.get("ModuleToken") == base_token
            and row.get("HierarchyPath") == config.get("baseInstanceHierarchyPath")
        ],
        "native base instance is missing or ambiguous",
    )
    if not _same_path(captured.get("filePath", ""), native.get("Path", "")):
        raise ValueError("captured cleaning source differs from selected native instance")

    binding = captured.get("captureFrameBinding") or {}
    if capture_mode == "isolated_complete_leaf_capture":
        if (
            binding.get("schemaVersion") != "occupancy-capture-frame-binding/v1"
            or binding.get("instanceName") != native.get("HierarchyPath")
            or labels.get("capturedInstanceName") != native.get("HierarchyPath")
            or max(
                abs(a - b)
                for a, b in zip(
                    geometry._transform(binding.get("capturedTransform")),
                    geometry._transform(native.get("SourceTransform")),
                    strict=True,
                )
            )
            > 1e-8
        ):
            raise ValueError("cleaning capture, label and native-instance identities disagree")
        for path_key, hash_key in (
            ("capturePath", "captureSha256"),
            ("originalOccupancyPath", "originalOccupancySha256"),
        ):
            path = Path(binding.get(path_key, ""))
            if not path.is_file() or sha(path) != binding.get(hash_key):
                raise ValueError("cleaning capture-frame evidence changed")
            evidence[str(path.resolve())] = sha(path)
    else:
        anchor = captured.get("prototypeAnchorInstallationMeters") or {}
        if (
            labels.get("capturedInstanceName") != native.get("HierarchyPath")
            or any(key not in anchor for key in "uvn")
        ):
            raise ValueError("cleaning grouped capture, label and native identity disagree")
        frame = geometry._frame_transform(occupancy.get("installationFrame"))
        observed_anchor = geometry._point(
            geometry._transform(native.get("SourceTransform"))[9:12],
            frame,
            inverse=True,
        )
        expected_anchor = [float(anchor[key]) for key in "uvn"]
        if max(
            abs(a - b)
            for a, b in zip(observed_anchor, expected_anchor, strict=True)
        ) > 1e-8:
            raise ValueError("cleaning grouped occupancy and native graph frames disagree")

    groups = labels.get("groups") or []
    names = [row.get("subtree") for row in groups]
    if (
        labels.get("moduleDefinitionId") != config.get("sourceModuleDefinitionId")
        or not groups
        or any(not isinstance(name, str) or not name for name in names)
        or len(set(names)) != len(names)
        or set(names) != {row.get("subtree") for row in boxes}
        or sum(int(row.get("leafBodyCount") or 0) for row in boxes)
        != captured_leaf_count
    ):
        raise ValueError("cleaning service-subtree labels do not cover the captured occupancy exactly")
    included = [row for row in groups if row.get("serviceProxyIncluded") is True]
    excluded = [row for row in groups if row.get("serviceProxyIncluded") is False]
    if not included or not excluded or any(row.get("detailedFunction") != "not_evaluated" for row in included):
        raise ValueError("cleaning service proxy requires explicit included and excluded subtree groups")
    expected_source = config.get("occupancySource")
    box_by_name = {row["subtree"]: row for row in boxes}
    if any(box_by_name[row["subtree"]].get("source") != expected_source for row in groups):
        raise ValueError("cleaning subtree occupancy source differs from the reviewed capture")

    frame = geometry._frame_transform(occupancy["installationFrame"])
    native_pose = geometry._transform(native["SourceTransform"])
    native_base_pose = geometry._transform(base["SourceTransform"])
    expected_groups = []
    local_corners: dict[str, list[list[float]]] = {}
    for row in included:
        box = box_by_name[row["subtree"]]["installationBoundsMeters"]
        corners = [geometry._point(geometry._point(point, frame), native_pose, inverse=True)
                   for point in geometry._corners(box)]
        local_corners[row["subtree"]] = corners
        expected_groups.append({
            "subtree": row["subtree"],
            "role": row["role"],
            "detailedFunction": row["detailedFunction"],
            "expectedBoundsInstallationMeters": box,
            "leafBodyCount": box_by_name[row["subtree"]]["leafBodyCount"],
        })

    observations = None
    passed = None
    state_binding = None
    if state is not None:
        assembly = Path(state.get("assemblyPath", ""))
        if (
            state.get("success") is not True
            or state.get("observed", {}).get("readOnly") is not True
            or not assembly.is_file()
            or sha(assembly) != state.get("assemblySha256")
        ):
            raise ValueError("current saved CAD state is not verified")
        components = state["observed"].get("components") or []
        actual = _one(
            [row for row in components if _same_path(row.get("sourcePath", ""), native["Path"])],
            "current cleaning instance is missing or ambiguous",
        )
        actual_base = _one(
            [row for row in components if _same_path(row.get("sourcePath", ""), base["Path"])],
            "current base instance is missing or ambiguous",
        )
        if actual.get("isFixed") is not False or actual_base.get("isFixed") is not True:
            raise ValueError("only the base may be fixed for native cleaning station verification")
        actual_pose = geometry._transform(actual["transform"])
        actual_base_pose = geometry._transform(actual_base["transform"])

        def current_installation(point: list[float]) -> list[float]:
            world = geometry._point(point, actual_pose)
            base_local = geometry._point(world, actual_base_pose, inverse=True)
            native_world = geometry._point(base_local, native_base_pose)
            return geometry._point(native_world, frame, inverse=True)

        observations = []
        for expected in expected_groups:
            actual_bounds = geometry._bounds(
                [current_installation(point) for point in local_corners[expected["subtree"]]]
            )
            delta = _max_bound_delta(
                actual_bounds, expected["expectedBoundsInstallationMeters"]
            )
            observations.append({
                "subtree": expected["subtree"],
                "actualBoundsInstallationMeters": actual_bounds,
                "maximumBoundErrorMeters": delta,
                "passed": delta <= tolerance,
            })
        passed = all(row["passed"] for row in observations)
        state_binding = {
            "assemblyPath": str(assembly.resolve()),
            "assemblySha256": sha(assembly),
            "sourceComponentName": actual.get("name"),
            "baseComponentName": actual_base.get("name"),
            "sourceFixed": actual.get("isFixed"),
            "baseFixed": actual_base.get("isFixed"),
        }
        evidence[str(assembly.resolve())] = sha(assembly)

    return {
        "schemaVersion": "native-cleaning-station-audit/v1",
        "sourceModuleDefinitionId": config["sourceModuleDefinitionId"],
        "targetBaseDefinitionId": config["targetBaseDefinitionId"],
        "nativeInstanceHierarchyPath": native["HierarchyPath"],
        "mechanicalPlacementAuthority": {
            "kind": "immutable_released_mate_recipe",
            "releaseManifestPath": str(release_path),
            "releaseId": release["releaseId"],
            "releaseDigest": release["releaseDigest"],
            "globalTemplateId": template_id,
            "sourceWorldPoseCopied": False,
        },
        "serviceProxy": {
            "selection": "explicit_separate_captured_subtree_envelopes",
            "captureMode": capture_mode,
            "includedGroups": expected_groups,
            "excludedGroups": [row["subtree"] for row in excluded],
            "observations": observations,
            "groupBoundsToleranceMeters": tolerance,
            "proxyGeometryPassed": passed,
            "functionalPassed": None,
        },
        "proxyGeometryPassed": passed,
        "functionalPassed": None,
        "stateBinding": state_binding,
        "evidence": [{"path": path, "sha256": value} for path, value in sorted(evidence.items())],
        "sourceWorldPoseExecutionAuthorized": False,
        "newCadExecuted": False,
        "collisionOrBrep": "not_evaluated",
        "actualFastening": "not_verified",
        "claimBoundary": (
            "The explicitly included service subtrees are separate measured envelope proxies. "
            "Matching them after save/reopen proves the released native station was recovered; "
            "detailed actions, real process performance, internal motion, collision and "
            "fastening remain unverified."
        ),
    }
