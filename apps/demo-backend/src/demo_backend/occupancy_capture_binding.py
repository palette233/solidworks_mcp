"""Bind legacy occupancy to its original capture; never infer from a mate graph."""
from __future__ import annotations

import copy
import hashlib
import itertools
from pathlib import Path

from . import role_station_geometry as geometry


def bind_occupancy_capture(occupancy_path: Path, capture_path: Path, token: str) -> dict:
    occupancy, capture = geometry._read(occupancy_path), geometry._read(capture_path)
    module = occupancy["modules"][token]
    if capture.get("coverageComplete") is not True or module.get("leafCoverageComplete") is not True:
        raise ValueError("complete leaf coverage is required")
    instances = capture.get("instanceCaptures", [])
    if len(instances) != 1 or capture.get("instanceCount") != 1:
        raise ValueError("capture must bind exactly one module instance")
    instance = instances[0]
    pose = instance["moduleTopLevelPose"]
    if (instance.get("instanceName") != module["componentName"] or pose.get("Name") != module["componentName"]
            or not geometry._same_path(pose["Path"], module["filePath"])
            or not geometry._same_path(capture["sourceStandaloneAssemblyPath"], module["filePath"])
            or capture.get("moduleToken") != token):
        raise ValueError("capture module identity mismatch")
    transform = geometry._transform(pose["Transform"])
    frame_data = copy.deepcopy(occupancy["installationFrame"])
    if "axesWorld" not in frame_data:
        frame_data["axesWorld"] = dict(zip("uvn", [frame_data[key] for key in
            ("flowAxisWorld", "transverseAxisWorld", "upAxisWorld")]))
    frame = geometry._frame_transform(frame_data)
    bodies = capture.get("bodies", [])
    if (not bodies or len(bodies) != module["leafBodyCount"] or len(bodies) != capture.get("bodyCount")
            or bodies != instance.get("bodies") or len(bodies) != instance.get("bodyCount")):
        raise ValueError("capture body coverage/count mismatch")
    grouped = {}
    projected = []
    for body in bodies:
        if body.get("TopLevelInstanceName") != module["componentName"]:
            raise ValueError("capture body belongs to another instance")
        path = body["Component"].get("HierarchyPath") or body["Component"]["Name"]
        subtree = path.split("/")[0]
        bounds = body["BoundingBoxWorld"]
        if len(bounds) != 6:
            raise ValueError("invalid captured body bounds")
        if any(bounds[i] > bounds[i + 3] for i in range(3)):
            raise ValueError("reversed captured body bounds")
        points = [geometry._point(geometry._vector(list(point)), frame, inverse=True)
                  for point in itertools.product(*[(bounds[i], bounds[i + 3]) for i in range(3)])]
        grouped.setdefault(subtree, []).extend(points)
        projected.append(geometry._bounds(points))
    boxes = module["occupancyBoxes"]
    if len(boxes) != len(grouped) or {b["subtree"] for b in boxes} != set(grouped):
        raise ValueError("capture subtree coverage mismatch")
    def equal_bounds(actual, expected):
        return all(abs(actual[key] - expected[key]) <= 1e-8 for key in actual)
    for box in boxes:
        if not equal_bounds(geometry._bounds(grouped[box["subtree"]]), box["installationBoundsMeters"]):
            raise ValueError("capture and occupancy subtree coordinates disagree")
    leaves = module["leafBodyOccupancyBoxes"]
    if len(leaves) != len(projected) or any(not equal_bounds(a, b["installationBoundsMeters"]) for a, b in zip(projected, leaves)):
        raise ValueError("capture and occupancy leaf coordinates disagree")
    anchor = geometry._point(transform[9:12], frame, inverse=True)
    result = copy.deepcopy(occupancy)
    result["installationFrame"] = frame_data
    target = result["modules"][token]
    old = target.get("prototypeAnchorInstallationMeters")
    if old is not None and any(abs(old[key] - anchor[i]) > 1e-8 for i, key in enumerate("uvn")):
        raise ValueError("existing capture anchor disagrees")
    target["prototypeAnchorInstallationMeters"] = dict(zip("uvn", anchor))
    target["captureFrameBinding"] = {
        "schemaVersion": "occupancy-capture-frame-binding/v1",
        "capturePath": str(capture_path.resolve()),
        "captureSha256": hashlib.sha256(capture_path.read_bytes()).hexdigest(),
        "originalOccupancyPath": str(occupancy_path.resolve()),
        "originalOccupancySha256": hashlib.sha256(occupancy_path.read_bytes()).hexdigest(),
        "instanceName": module["componentName"], "capturedTransform": transform,
        "verifiedLeafBodyCount": len(bodies), "verifiedSubtreeCount": len(grouped),
        "purpose": "historical_coordinate_binding_only", "cadAcceptanceEvaluated": False,
    }
    return result
