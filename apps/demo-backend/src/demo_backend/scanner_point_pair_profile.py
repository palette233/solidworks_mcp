"""Build reusable scanner/transport local point-pair profiles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


SCHEMA = "scanner-local-point-pair-profile/v1"
TARGET_CANDIDATE_CATALOG_SCHEMA = (
    "scanner-transport-barcode-target-candidate-catalog/v1"
)
SOURCE_CANDIDATE_CATALOG_SCHEMA = "scanner-optical-source-candidate-catalog/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _world_to_local(point: list[float], transform: list[float]) -> list[float]:
    delta = [point[index] - transform[9 + index] for index in range(3)]
    return [
        sum(delta[axis] * transform[3 * row + axis] for axis in range(3))
        for row in range(3)
    ]


def _world_vector_to_local(vector: list[float], transform: list[float]) -> list[float]:
    return [
        sum(float(vector[axis]) * transform[3 * row + axis] for axis in range(3))
        for row in range(3)
    ]


def _pointer(value: Any, pointer: str) -> dict[str, Any]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("Optical measurement requires an explicit JSON pointer")
    try:
        for key in pointer.split("/")[1:]:
            key = key.replace("~1", "/").replace("~0", "~")
            value = value[int(key)] if isinstance(value, list) else value[key]
    except (KeyError, ValueError, IndexError, TypeError) as exc:
        raise ValueError("Optical measurement pointer does not resolve") from exc
    if not isinstance(value, dict):
        raise ValueError("Optical measurement pointer must select an object")
    return value


def _module(graph: dict[str, Any], definition_id: str) -> dict[str, Any]:
    token = definition_id.split("::", 1)[1]
    rows = [
        row
        for row in graph.get("Modules") or []
        if str(row.get("ModuleToken") or "").upper().endswith(token.upper())
    ]
    if len(rows) != 1 or not rows[0].get("SourceTransform") or not rows[0].get("HierarchyPath"):
        raise ValueError(f"Scanner graph identity is missing or ambiguous: {definition_id}")
    return rows[0]


def build_transport_barcode_target_candidate_catalog(
    *,
    repository_root: Path,
    optical_geometry_path: Path,
    module_graph_path: Path,
    transport_module_definition_id: str,
    catalog_id: str,
) -> dict[str, Any]:
    """Convert ambiguous native scan targets into transport-local candidates.

    Some prototypes model scanner beams and coarse target points but do not
    author a persistent barcode face or an unambiguous carrier/product role.
    This builder preserves both role alternatives and converts their target
    points into the selected transport module frame.  It deliberately does
    *not* choose a role or create a scanner point-pair rule: an engineering
    role decision is still required before a candidate can enter CAD.
    """

    root = repository_root.resolve()
    optical_path = optical_geometry_path.resolve()
    graph_path = module_graph_path.resolve()
    optical_path.relative_to(root)
    graph_path.relative_to(root)
    optical = _read(optical_path)
    graph = _read(graph_path)
    project_id, separator, _ = transport_module_definition_id.partition("::")
    if not separator or not project_id:
        raise ValueError("Transport module definition must be project::module")
    if optical.get("schemaVersion") != "project05-optical-geometry/v1":
        raise ValueError("Unsupported scanner optical geometry")
    if optical.get("projectId") != project_id:
        raise ValueError("Optical geometry belongs to another project")
    transport = _module(graph, transport_module_definition_id)
    transform = transport["SourceTransform"]
    scanner = optical.get("scanner") or {}
    station = scanner.get("scanStation") or {}
    if scanner.get("captureCoverageComplete") is not True:
        raise ValueError("Scanner beam capture is incomplete")
    if station.get("roleEngineeringConfirmed") is not False:
        raise ValueError("This candidate builder is only for unresolved roles")
    beams = {
        str(row.get("beamId") or ""): row
        for row in scanner.get("beams") or []
        if row.get("beamId")
    }
    role_specs = (
        (
            "carrier-barcode",
            "carrierBeamId",
            "carrierBarcodeTargetProxyInstallationMeters",
        ),
        (
            "four-product-barcodes",
            "productBeamId",
            "productBarcodeTargetProxyInstallationMeters",
        ),
    )
    candidates = []
    for target_role, beam_key, proxy_key in role_specs:
        beam_id = str(station.get(beam_key) or "")
        beam = beams.get(beam_id)
        if beam is None or beam.get("roleConfirmed") is not False:
            raise ValueError(f"Unresolved scanner beam is missing: {beam_id}")
        if target_role not in (beam.get("roleCandidates") or []):
            raise ValueError(f"Beam does not advertise role candidate: {target_role}")
        endpoints = beam.get("endpointWorldMeters")
        if (
            not isinstance(endpoints, list)
            or len(endpoints) != 2
            or any(not isinstance(row, list) or len(row) != 3 for row in endpoints)
        ):
            raise ValueError(f"Beam endpoints are incomplete: {beam_id}")
        target_world = [
            (float(endpoints[0][axis]) + float(endpoints[1][axis])) / 2.0
            for axis in range(3)
        ]
        proxy = station.get(proxy_key)
        if not isinstance(proxy, dict) or not {"u", "v", "normal"}.issubset(proxy):
            raise ValueError(f"Target proxy is incomplete: {proxy_key}")
        candidates.append(
            {
                "candidateId": f"{catalog_id}:{target_role}",
                "targetRole": target_role,
                "sourceBeamId": beam_id,
                "sourcePartToken": beam.get("sourcePartToken"),
                "localBarcodeTargetMeters": _world_to_local(target_world, transform),
                "referenceTransform": transform,
                "prototypeWorldTargetMetersForAuditOnly": target_world,
                "installationFrameProxyMeters": proxy,
                "targetKind": "coarse_barcode_target_proxy",
                "roleEngineeringConfirmed": False,
                "readyForPointPairRule": False,
                "requiredNextDecision": (
                    "confirm_carrier_vs_product_barcode_target_role_and_axis_sign"
                ),
            }
        )
    core = {
        "schemaVersion": TARGET_CANDIDATE_CATALOG_SCHEMA,
        "catalogId": catalog_id,
        "transportModuleDefinitionId": transport_module_definition_id,
        "transportSourcePath": transport.get("Path"),
        "transportHierarchyPath": transport.get("HierarchyPath"),
        "candidates": candidates,
        "sourceEvidence": [
            {"path": str(optical_path), "sha256": _sha(optical_path)},
            {"path": str(graph_path), "sha256": _sha(graph_path)},
        ],
        "roleSelectionRequired": True,
        "prototypePoseAllowedAsCadExecutionAuthority": False,
        "cadStarted": False,
        "claimBoundary": (
            "Two prototype-derived coarse target proxies are normalized into "
            "the D000 module frame. Their carrier/product roles and beam signs "
            "remain unconfirmed; this catalog is not a point-pair rule, CAD "
            "authority, physical barcode-face registration or measured scan success."
        ),
    }
    return {**core, "catalogDigest": _digest(core)}


def build_scanner_optical_source_candidate_catalog(
    *,
    repository_root: Path,
    optical_geometry_path: Path,
    module_graph_path: Path,
    scanner_module_definition_id: str,
    catalog_id: str,
) -> dict[str, Any]:
    """Preserve all unresolved Project05 scanner head/role/sign choices.

    The modeled beam solids provide two endpoints and an unsigned axis, but do
    not uniquely identify the product/carrier head or the emitting end.  The
    catalog therefore emits the Cartesian product of beam, advertised role and
    direction sign.  A later engineering decision may select exactly one row;
    this function never guesses one from geometry ordering.
    """

    root = repository_root.resolve()
    optical_path = optical_geometry_path.resolve()
    graph_path = module_graph_path.resolve()
    optical_path.relative_to(root)
    graph_path.relative_to(root)
    optical = _read(optical_path)
    graph = _read(graph_path)
    project_id, separator, _ = scanner_module_definition_id.partition("::")
    if not separator or optical.get("projectId") != project_id:
        raise ValueError("Scanner optical geometry project does not match")
    if optical.get("schemaVersion") != "project05-optical-geometry/v1":
        raise ValueError("Unsupported scanner optical geometry")
    scanner_module = _module(graph, scanner_module_definition_id)
    transform = scanner_module["SourceTransform"]
    scanner = optical.get("scanner") or {}
    beams = scanner.get("beams") or []
    if (
        scanner.get("captureCoverageComplete") is not True
        or scanner.get("explicitBeamCount") != len(beams)
        or not beams
    ):
        raise ValueError("Scanner beam capture is incomplete")
    candidates = []
    for beam in beams:
        beam_id = str(beam.get("beamId") or "")
        endpoints = beam.get("endpointWorldMeters")
        roles = beam.get("roleCandidates") or []
        if (
            not beam_id
            or beam.get("roleConfirmed") is not False
            or beam.get("directionSignConfirmed") is not False
            or not isinstance(endpoints, list)
            or len(endpoints) != 2
            or any(not isinstance(row, list) or len(row) != 3 for row in endpoints)
            or not roles
        ):
            raise ValueError(f"Scanner beam is not an unresolved explicit beam: {beam_id}")
        for role in roles:
            for start_index, end_index, sign_label in (
                (0, 1, "endpoint_0_to_1"),
                (1, 0, "endpoint_1_to_0"),
            ):
                origin = [float(value) for value in endpoints[start_index]]
                vector = [
                    float(endpoints[end_index][axis]) - origin[axis]
                    for axis in range(3)
                ]
                norm = sum(value * value for value in vector) ** 0.5
                if norm <= 0:
                    raise ValueError(f"Scanner beam has zero length: {beam_id}")
                direction = [value / norm for value in vector]
                candidates.append(
                    {
                        "candidateId": f"{catalog_id}:{beam_id}:{role}:{sign_label}",
                        "sourceBeamId": beam_id,
                        "sourcePartToken": beam.get("sourcePartToken"),
                        "targetRole": role,
                        "directionSignChoice": sign_label,
                        "localOpticalOriginMeters": _world_to_local(origin, transform),
                        "localOpticalDirection": _world_vector_to_local(
                            direction, transform
                        ),
                        "referenceTransform": transform,
                        "prototypeWorldOriginForAuditOnly": origin,
                        "prototypeWorldDirectionForAuditOnly": direction,
                        "roleEngineeringConfirmed": False,
                        "directionSignEngineeringConfirmed": False,
                        "readyForPointPairRule": False,
                        "requiredNextDecision": (
                            "select_scanner_head_role_and_emitting_direction"
                        ),
                    }
                )
    core = {
        "schemaVersion": SOURCE_CANDIDATE_CATALOG_SCHEMA,
        "catalogId": catalog_id,
        "scannerModuleDefinitionId": scanner_module_definition_id,
        "scannerSourcePath": scanner_module.get("Path"),
        "scannerHierarchyPath": scanner_module.get("HierarchyPath"),
        "candidates": candidates,
        "roleAndDirectionSelectionRequired": True,
        "prototypePoseAllowedAsCadExecutionAuthority": False,
        "cadStarted": False,
        "sourceEvidence": [
            {"path": str(optical_path), "sha256": _sha(optical_path)},
            {"path": str(graph_path), "sha256": _sha(graph_path)},
        ],
        "claimBoundary": (
            "All modeled F000 beam, barcode-role and direction-sign alternatives "
            "are normalized into the scanner module frame. No alternative is "
            "selected; this is not a point-pair rule, CAD authority or measured "
            "scan success."
        ),
    }
    return {**core, "catalogDigest": _digest(core)}


def build_point_pair_profile_from_scanner_rule_and_direct_target(
    *,
    repository_root: Path,
    scanner_rule_path: Path,
    target_measurement_path: Path,
    profile_id: str,
) -> dict[str, Any]:
    """Normalize a scanner-rule optical proxy and a direct target face.

    This bridges two already measured module-local facts.  It does not combine
    their historical world poses and does not create mechanical CAD authority.
    The returned points are reprojected from the *current* scanner and transport
    transforms by the normal point-pair evaluator.
    """

    root = repository_root.resolve()
    rule_path = scanner_rule_path.resolve()
    target_path = target_measurement_path.resolve()
    rule_path.relative_to(root)
    target_path.relative_to(root)
    rule = _read(rule_path)
    if rule.get("schemaVersion") != "scanner-target-rule/v1":
        raise ValueError("Unsupported source scanner rule")
    scanner_id = str(rule.get("sourceModuleDefinitionId") or "")
    if scanner_id.count("::") != 1:
        raise ValueError("Source scanner identity is missing")
    inputs: dict[str, dict[str, Any]] = {}
    evidence = [{"path": str(rule_path), "sha256": _sha(rule_path)}]
    for key, relative in (rule.get("inputs") or {}).items():
        path = (root / str(relative)).resolve()
        path.relative_to(root)
        expected = (rule.get("inputSha256") or {}).get(key)
        if not path.is_file() or expected != _sha(path):
            raise ValueError(f"Source scanner rule input changed: {key}")
        inputs[key] = _read(path)
        evidence.append({"path": str(path), "sha256": expected})
    if "scannerGraphPath" not in inputs or "processEvidencePath" not in inputs:
        raise ValueError("Source scanner rule lacks graph or process evidence")
    scanner_module = _module(inputs["scannerGraphPath"], scanner_id)
    scanner_transform = scanner_module["SourceTransform"]
    process = inputs["processEvidencePath"]
    selector = rule.get("opticalMeasurementSelector")
    if selector is not None:
        optical_report = inputs.get("opticalGeometryPath")
        if optical_report is None:
            raise ValueError("Selected scanner optical evidence is missing")
        optical = _pointer(optical_report, selector.get("jsonPointer"))
        project_id, _ = scanner_id.split("::", 1)
        if optical_report.get("projectId") != project_id or not str(
            optical.get("componentName") or ""
        ).startswith(str(scanner_module["HierarchyPath"]) + "/"):
            raise ValueError("Selected optical head does not belong to the scanner module")
        model = str(selector.get("scannerModel") or "")
        distance = (process.get("readOnlyChecks") or {}).get(
            "workingDistanceRangeEvidence"
        ) or {}
        model_token = model.rsplit(" ", 1)[-1]
        if (
            not model
            or model != optical_report.get("scannerModel")
            or not re.search(
                r"(?<![A-Za-z0-9_-])"
                + re.escape(model_token)
                + r"(?![A-Za-z0-9_-])",
                str(distance.get("authority") or ""),
            )
        ):
            raise ValueError("Scanner model does not match working-distance evidence")
        origin = optical.get("opticalOriginWorldMeters")
        direction = optical.get("opticalDirectionWorld")
        quality = "measured_cad_beam_proxy_selected_by_json_pointer"
    else:
        optical = process.get("sourceScanner") or {}
        if f"{optical.get('projectId')}::{optical.get('moduleToken')}" != scanner_id:
            raise ValueError("Process optical evidence belongs to another scanner")
        origin = optical.get("opticalOriginWorldMeters")
        direction = optical.get("opticalDirectionWorld")
        quality = "prototype_process_optical_proxy"
    if not isinstance(origin, list) or len(origin) != 3:
        raise ValueError("Scanner optical origin is incomplete")
    if not isinstance(direction, list) or len(direction) != 3:
        raise ValueError("Scanner optical direction is incomplete")

    target = _read(target_path)
    if target.get("schemaVersion") != "project02-scanner-barcode-points/v1":
        raise ValueError("Unsupported direct barcode target measurement")
    barcode = (target.get("entries") or {}).get("barcode") or {}
    audit = barcode.get("transformAudit") or {}
    if barcode.get("measurementStatus") != "direct-face-measured" or not barcode.get(
        "persistentReferenceBase64"
    ):
        raise ValueError("Target barcode point is not a persistent direct CAD face")
    transport_id = f"project02::{barcode.get('moduleCode')}"
    target_local = audit.get("componentLocalBarcodeCenterMeters")
    target_transform = audit.get("prototypeModuleTransform")
    if not isinstance(target_local, list) or len(target_local) != 3:
        raise ValueError("Target barcode local point is incomplete")
    if not isinstance(target_transform, list) or len(target_transform) != 16:
        raise ValueError("Target transport reference transform is incomplete")
    evidence.append({"path": str(target_path), "sha256": _sha(target_path)})
    range_evidence = (process.get("readOnlyChecks") or {}).get(
        "workingDistanceRangeEvidence"
    ) or {}
    if not {"minimumMeters", "maximumMeters", "authority"}.issubset(range_evidence):
        raise ValueError("Working-distance evidence is incomplete")
    core = {
        "schemaVersion": SCHEMA,
        "profileId": profile_id,
        "sourceScanner": {
            "moduleDefinitionId": scanner_id,
            "localOpticalOriginMeters": _world_to_local(origin, scanner_transform),
            "referenceTransform": scanner_transform,
            "opticalDirectionWorld": direction,
            "coarseLayoutUsable": True,
            "evidenceQuality": quality,
        },
        "targetTransport": {
            "moduleDefinitionId": transport_id,
            "localBarcodeTargetMeters": target_local,
            "referenceTransform": target_transform,
            "targetKind": "direct_cad_face",
            "engineeringConfirmed": True,
            "flowCoordinateBehavior": "fixed_direct_face_on_selected_transport_cad",
        },
        "workingDistanceRangeEvidence": range_evidence,
        "crossTrackToleranceMeters": (process.get("readOnlyChecks") or {}).get(
            "crossTrackToleranceMeters", 0.005
        ),
        "sourceEvidence": evidence,
        "cadStarted": False,
        "claimBoundary": (
            "The scanner optical proxy and direct transport barcode face are converted "
            "to their owning module frames. Historical world poses are not placement "
            "authority; current CAD must reproject both and real scan success remains unknown."
        ),
    }
    return {**core, "profileDigest": _digest(core)}


def build_a180_ss00_point_pair_profile(
    *, source_measurement_path: Path, target_process_path: Path
) -> dict[str, Any]:
    """Normalize existing A180 local optics and SS00 barcode-lane proxy."""

    source_path = source_measurement_path.resolve()
    target_path = target_process_path.resolve()
    source = _read(source_path)
    target = _read(target_path)
    if source.get("schemaVersion") != "project02-scanner-barcode-points/v1":
        raise ValueError("Unsupported A180 source measurement")
    scanner = (source.get("entries") or {}).get("scanner") or {}
    audit = scanner.get("transformAudit") or {}
    if scanner.get("moduleCode") != "A180" or scanner.get("readyForCoarseLayout") is not True:
        raise ValueError("A180 scanner source evidence is incomplete")
    transport = target.get("targetTransport") or {}
    checks = target.get("readOnlyChecks") or {}
    if f"{transport.get('projectId')}::{transport.get('moduleToken')}" != "project01::SS00":
        raise ValueError("Target process evidence is not SS00")
    frame = transport.get("installationFrameWorld") or {}
    station = checks.get("barcodeLaneTargetAtScannerStationMeters")
    if not isinstance(station, list) or len(station) != 3:
        raise ValueError("SS00 barcode-lane station proxy is missing")
    axes = [frame.get("flowAxis"), frame.get("transverseAxis"), frame.get("upAxis")]
    origin = frame.get("origin")
    if any(not isinstance(row, list) or len(row) != 3 for row in [origin, *axes]):
        raise ValueError("SS00 installation frame is incomplete")
    world_target = [
        origin[axis] + sum(station[index] * axes[index][axis] for index in range(3))
        for axis in range(3)
    ]
    reference = transport.get("sourceTransform")
    if not isinstance(reference, list) or len(reference) != 16:
        raise ValueError("SS00 reference transform is missing")
    range_evidence = checks.get("workingDistanceRangeEvidence") or {}
    if checks.get("authoritativeWorkingDistanceRangeAvailable") is not True:
        raise ValueError("Working-distance evidence is not authoritative")
    core = {
        "schemaVersion": SCHEMA,
        "profileId": "scanner-point-pair-a180-ss00-v1",
        "sourceScanner": {
            "moduleDefinitionId": "project02::A180",
            "localOpticalOriginMeters": audit.get("componentLocalOpticalOriginMeters"),
            "referenceTransform": audit.get("prototypeModuleTransform"),
            "opticalDirectionWorld": scanner.get("worldNormal"),
            "coarseLayoutUsable": True,
            "evidenceQuality": "inferred_from_symmetric_illumination_windows",
        },
        "targetTransport": {
            "moduleDefinitionId": "project01::SS00",
            "localBarcodeTargetMeters": _world_to_local(world_target, reference),
            "referenceTransform": reference,
            "targetKind": "barcode_lane_proxy_at_scan_station",
            "engineeringConfirmed": False,
            "flowCoordinateBehavior": "dynamic_with_carrier_proxy_at_selected_scan_station",
        },
        "workingDistanceRangeEvidence": range_evidence,
        "crossTrackToleranceMeters": checks.get("crossTrackToleranceMeters"),
        "sourceEvidence": [
            {"path": str(source_path), "sha256": _sha(source_path)},
            {"path": str(target_path), "sha256": _sha(target_path)},
        ],
        "cadStarted": False,
        "claimBoundary": (
            "A180 optical origin and SS00 barcode lane are coarse proxies converted to "
            "their owning module frames. Current CAD must reproject both; this is not "
            "a physical barcode face or measured scan success."
        ),
    }
    return {**core, "profileDigest": _digest(core)}


def build_scanner_point_pair_rule(
    *,
    repository_root: Path,
    profile_path: Path,
    module_catalog_path: Path,
    target_base_definition_id: str,
    rule_id: str,
) -> dict[str, Any]:
    """Bind one reusable point-pair profile to an exact target base identity."""

    root = repository_root.resolve()
    profile_path = profile_path.resolve()
    catalog_path = module_catalog_path.resolve()
    profile_path.relative_to(root)
    catalog_path.relative_to(root)
    profile = _read(profile_path)
    if profile.get("schemaVersion") != SCHEMA:
        raise ValueError("Unsupported scanner point-pair profile")
    body = dict(profile)
    expected = body.pop("profileDigest", None)
    if expected != _digest(body):
        raise ValueError("Scanner point-pair profile digest mismatch")
    for evidence in profile.get("sourceEvidence") or []:
        path = Path(evidence.get("path") or "").resolve()
        if not path.is_file() or _sha(path) != evidence.get("sha256"):
            raise ValueError("Scanner point-pair profile evidence changed")
    catalog = _read(catalog_path)
    definitions = {
        "scanner": profile["sourceScanner"]["moduleDefinitionId"],
        "transport": profile["targetTransport"]["moduleDefinitionId"],
        "targetBase": target_base_definition_id,
    }

    def source_path(definition_id: str) -> str:
        rows = [
            module
            for module in catalog.get("moduleDefinitions") or []
            if any(
                f"{alias.get('projectId')}::{alias.get('moduleToken')}" == definition_id
                for alias in module.get("projectAliases") or []
            )
        ]
        if len(rows) != 1 or len(rows[0].get("cadSources") or []) != 1:
            raise ValueError(f"Module catalog identity is missing or ambiguous: {definition_id}")
        return str(rows[0]["cadSources"][0]["path"])

    core = {
        "schemaVersion": "scanner-local-point-pair-rule/v1",
        "ruleId": rule_id,
        "sourceModuleDefinitionId": definitions["scanner"],
        "transportModuleDefinitionId": definitions["transport"],
        "targetBaseDefinitionId": definitions["targetBase"],
        "inputs": {
            "measurementPath": profile_path.relative_to(root).as_posix(),
        },
        "componentSourcePaths": {
            role: source_path(definition_id)
            for role, definition_id in definitions.items()
        },
        "inputSha256": {"measurementPath": _sha(profile_path)},
        "workingDistanceRangeEvidence": profile["workingDistanceRangeEvidence"],
        "crossTrackToleranceMeters": profile["crossTrackToleranceMeters"],
        "interpretationLimits": [
            profile["claimBoundary"],
            "The target base changes only the mechanical installation context; scanner and transport points are rebound from the current saved CAD state.",
            "The rule is not CAD authority, a physical barcode-face registration or measured scan success.",
        ],
        "status": "review_candidate_requires_current_saved_context",
        "cadLaunchAllowed": False,
        "prototypePoseAllowedAsCadExecutionAuthority": False,
    }
    core["ruleDigest"] = _digest(core)
    return core
