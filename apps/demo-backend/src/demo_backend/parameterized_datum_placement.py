"""Parameterized datum-placement fallback for mechanically incompatible slots.

The native mechanical interface remains the first choice.  This layer only
describes a CAD pose using three stable, mutually orthogonal planar datums:
support, longitudinal and lateral.  It deliberately does not claim that a
bolt, pin, hole or bracket exists at the resulting location.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .finite_support_gate import (
    FiniteSupportGateError,
    evaluate_finite_support_gate,
)
from .mechanical_interface_contracts import (
    DATUM_PLACEMENT_CATALOG_SCHEMA,
    MechanicalInterfaceContractError,
    build_support_position_contract,
    instantiate_connection_template,
    match_interface_contracts,
    plan_module_slot_connection,
    validate_contract_catalog,
)


PLAN_SCHEMA = "preferred-mechanical-or-datum-placement-plan/v1"
VALIDATION_PACKAGE_SCHEMA = "parameterized-datum-validation-package/v1"
PAIR_RELEASE_SCHEMA = "parameterized-datum-pair-release/v1"
IDENTITY_TRANSFORM = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _released_manifest(workspace: Path, release_id: str) -> dict[str, Any]:
    return _read(
        workspace
        / "demo/global_assembly_catalog/releases"
        / release_id
        / "release-manifest.json"
    )


def _endpoint_index(path: Path) -> dict[str, dict[str, Any]]:
    report = _read(path)
    return {
        str(row.get("EndpointId")): row
        for row in report.get("Endpoints") or []
        if row.get("EndpointId")
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _catalog_source_for_contract(
    report: dict[str, Any], contract: dict[str, Any], *, module_role: str
) -> str:
    rows = [
        row
        for row in report.get("datumFrameAudit") or []
        if row.get("owner") == contract.get("moduleDefinitionId")
        and row.get("side") == contract.get("side")
        and (
            contract.get("side") == "moving_module"
            or row.get("acceptedRole") == module_role
        )
    ]
    if len(rows) != 1 or not rows[0].get("source"):
        raise MechanicalInterfaceContractError(
            "datum contract must resolve to one endpoint catalog"
        )
    return str(rows[0]["source"])


def _selected_endpoint_rows(
    catalog: dict[str, Any], contract: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    index = {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
        if row.get("EndpointId")
    }
    selected: dict[str, dict[str, Any]] = {}
    for binding in contract.get("endpointBindings") or []:
        role = str(binding.get("role") or "")
        endpoint_id = str(binding.get("endpointId") or "")
        if role in selected or endpoint_id not in index:
            raise MechanicalInterfaceContractError(
                f"datum endpoint binding cannot be resolved: {role}/{endpoint_id}"
            )
        selected[role] = copy.deepcopy(index[endpoint_id])
    if set(selected) != {"support_datum", "longitudinal_datum", "lateral_datum"}:
        raise MechanicalInterfaceContractError("datum contract does not bind all three roles")
    return selected


def _persistent_reference(endpoint_row: dict[str, Any]) -> str:
    return str(
        ((endpoint_row.get("Endpoint") or endpoint_row).get(
            "SourceAssemblyPersistentReferenceBase64"
        ))
        or ""
    )


def _resolve_three_plane_pair_release(
    release: dict[str, Any],
    module_endpoints: dict[str, dict[str, Any]],
    slot_endpoints: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Resolve immutable graph evidence against the current endpoint catalogs."""

    graph = _read(Path(str(release.get("effectiveGraphPath") or "")))
    suffix_roles = {
        "_SUPPORT": "support_datum",
        "_LONGITUDINAL": "longitudinal_datum",
        "_LATERAL": "lateral_datum",
    }
    graph_rows: dict[str, dict[str, Any]] = {}
    for mate in graph.get("Mates") or []:
        name = str(mate.get("MateName") or "")
        role = next(
            (value for suffix, value in suffix_roles.items() if name.endswith(suffix)),
            None,
        )
        if role:
            if role in graph_rows or len(mate.get("Endpoints") or []) != 2:
                raise MechanicalInterfaceContractError(
                    "released three-plane graph has ambiguous datum mates"
                )
            graph_rows[role] = mate
    if set(graph_rows) != set(suffix_roles.values()):
        raise MechanicalInterfaceContractError(
            "released three-plane graph does not contain all datum roles"
        )
    longitudinal = graph_rows["longitudinal_datum"].get("Distance")
    lateral = graph_rows["lateral_datum"].get("Distance")
    support = graph_rows["support_datum"]
    support_gap = 0.0 if support.get("MateTypeName") == "swMateCOINCIDENT" else support.get("Distance")
    parameters = {
        "longitudinal": longitudinal,
        "lateral": lateral,
        "supportGap": support_gap,
    }
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0
        for value in parameters.values()
    ):
        raise MechanicalInterfaceContractError(
            "released three-plane graph has invalid position parameters"
        )
    distance_flips = {
        role.removesuffix("_datum"): bool(
            (graph_rows[role].get("AdvancedOptions") or {}).get(
                "DistanceFlipDimension", False
            )
        )
        for role in ("longitudinal_datum", "lateral_datum")
    }
    distance_flips["supportGap"] = bool(
        (support.get("AdvancedOptions") or {}).get("DistanceFlipDimension", False)
    )
    module_matches = all(
        _persistent_reference(graph_rows[role]["Endpoints"][0])
        == _persistent_reference(module_endpoints[role])
        for role in suffix_roles.values()
    )
    slot_matches = all(
        _persistent_reference(graph_rows[role]["Endpoints"][1])
        == _persistent_reference(slot_endpoints[role])
        for role in suffix_roles.values()
    )
    return {
        "positionParametersMeters": {
            key: float(value) for key, value in parameters.items()
        },
        "distanceFlipDimensions": distance_flips,
        "moduleEndpointReferencesMatch": module_matches,
        "slotEndpointReferencesMatch": slot_matches,
        "currentCatalogBindingsMatch": module_matches and slot_matches,
    }


def _module_record(
    catalog: dict[str, Any], endpoint_rows: dict[str, dict[str, Any]], token: str, *,
    nonprototype_target: bool,
) -> dict[str, Any]:
    module_rows = list(catalog.get("Modules") or [])
    matches = [
        row
        for row in module_rows
        if str(row.get("ModuleToken") or "").upper().endswith(token.upper())
        or str(row.get("Name") or "").upper().startswith(token.upper())
        or token.upper() in str(row.get("Name") or "").upper()
    ]
    sample = next(iter(endpoint_rows.values()))
    endpoint = sample.get("Endpoint") or {}
    if len(matches) == 1:
        module = copy.deepcopy(matches[0])
    else:
        hierarchy = str(endpoint.get("ModuleHierarchyPath") or "")
        path = str(sample.get("ModulePath") or "")
        if not hierarchy or not path:
            raise MechanicalInterfaceContractError(
                f"cannot reconstruct module record for {token}"
            )
        module = {
            "ModuleToken": token,
            "Name": hierarchy.split("/")[0],
            "Path": path,
            "HierarchyPath": hierarchy,
            "SourceTransform": list(IDENTITY_TRANSFORM),
            "IsSuppressed": False,
            "SuppressionState": 2,
            "SuppressionStateName": "swComponentFullyResolved",
            "VisibilityState": 1,
            "ReferencedConfiguration": sample.get("ModuleReferencedConfiguration") or "Default",
            "SolvingState": 0,
            "SolvingStateName": "swComponentRigidSolving",
        }
    module["ModuleToken"] = token
    if nonprototype_target:
        module["SourceTransform"] = list(IDENTITY_TRANSFORM)
    return module


def _base_wrapper_source(workspace: Path, base_token: str) -> tuple[Path, Path]:
    cache_root = workspace / "demo/global_assembly_contexts/base_wrapper_cache"
    exact_rows: list[tuple[Path, Path]] = []
    suffix_rows: list[tuple[Path, Path]] = []
    for entry_path in cache_root.glob("*/cache-entry.json"):
        entry = _read(entry_path)
        registered = str((entry.get("inputs") or {}).get("baseContextModuleToken") or "")
        assembly = entry_path.parent / str(entry.get("assemblyFile") or "")
        if not assembly.is_file():
            continue
        if registered.upper() == base_token.upper():
            exact_rows.append((entry_path, assembly))
        elif registered.upper().endswith(base_token.upper()):
            suffix_rows.append((entry_path, assembly))
    # New cache entries use the normalized module token.  Historical entries
    # may retain the full CAD prefix (for example FL9A24D063AA00).  Prefer one
    # exact normalized entry and only fall back to suffix matching when no
    # exact entry exists; silently choosing between multiple exact entries
    # would make the wrapper authority ambiguous.
    rows = exact_rows if exact_rows else suffix_rows
    if len(rows) != 1:
        raise MechanicalInterfaceContractError(
            f"expected one immutable base wrapper for {base_token}, found {len(rows)}"
        )
    return rows[0]


def _datum_release_safety_registry(workspace: Path) -> dict[str, Any]:
    safety_path = (
        workspace
        / "demo/cross_project_substitution/parameterized-datum-placement-v1/"
        "release-safety-registry.json"
    )
    if not safety_path.is_file():
        return {
            "schemaVersion": "parameterized-datum-release-safety-registry/v1",
            "revokedReleases": [],
        }
    safety = _read(safety_path)
    if safety.get("schemaVersion") != "parameterized-datum-release-safety-registry/v1":
        raise MechanicalInterfaceContractError("unsupported datum release safety registry")
    return safety


def _candidate_reuse_safety_blocks(
    workspace: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Return exact module/base recipes that must not be silently retried.

    Revoking an immutable release is not always sufficient: the same position
    parameters may otherwise reappear as a fresh CAD-validation candidate.  A
    row with ``blockCandidateReuse`` therefore fail-closes the exact pair until
    a different, explicitly reviewed station recipe replaces it.
    """

    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _datum_release_safety_registry(workspace).get("revokedReleases") or []:
        if row.get("blockCandidateReuse") is not True:
            continue
        pair = (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        )
        if not all(pair):
            raise MechanicalInterfaceContractError(
                "candidate reuse safety block is missing the module/base identity"
            )
        if pair in rows:
            raise MechanicalInterfaceContractError(
                f"duplicate candidate reuse safety block: {pair}"
            )
        rows[pair] = copy.deepcopy(row)
    return rows


def _validated_pair_releases(workspace: Path) -> list[dict[str, Any]]:
    root = workspace / "demo/cross_project_substitution"
    releases: list[dict[str, Any]] = []
    safety = _datum_release_safety_registry(workspace)
    revoked_release_ids = {
        str(row.get("releaseId") or "")
        for row in safety.get("revokedReleases") or []
        if row.get("releaseId")
    }
    # Queue successors may live below the broad-combination batch rather than
    # the original parameterized-datum directory.  A successful queue runner
    # writes its immutable pair release beside the candidate evidence, so scan
    # the bounded cross-project evidence tree instead of one queue lineage.
    # Duplicate exact-pair releases remain an error.
    for path in root.rglob("pair-release.json"):
        candidate_status_path = path.parent / "release-candidate-status.json"
        if candidate_status_path.is_file():
            candidate_status = _read(candidate_status_path)
            if candidate_status.get("status") == "failed":
                # Preserve failed immutable promotion evidence without allowing
                # an incomplete candidate to enter the executable catalog.
                continue
        row = _read(path)
        if row.get("schemaVersion") != PAIR_RELEASE_SCHEMA:
            # Other validated adapters (for example direct mechanical
            # interfaces) intentionally use their own pair-release schemas in
            # the same bounded evidence tree.  They are authenticated by
            # their own catalogs and must not be imported as datum releases.
            continue
        expected = _digest({key: value for key, value in row.items() if key != "releaseDigest"})
        if row.get("releaseDigest") != expected:
            raise MechanicalInterfaceContractError(f"pair release digest mismatch: {path}")
        for path_key, digest_key in (
            ("outputAssemblyPath", "outputAssemblySha256"),
            ("effectiveGraphPath", "effectiveGraphSha256"),
            ("cadResultPath", "cadResultSha256"),
        ):
            evidence_path = Path(str(row.get(path_key) or ""))
            if not evidence_path.is_file() or _sha256_file(evidence_path) != row.get(digest_key):
                raise MechanicalInterfaceContractError(
                    f"pair release evidence changed: {path_key}"
                )
        if row.get("nonPrototypeCadValidated") is not True:
            raise MechanicalInterfaceContractError("pair release lacks CAD validation")
        if str(row.get("releaseId") or "") in revoked_release_ids:
            continue
        releases.append(row)
    pair_keys = [
        (row.get("moduleDefinitionId"), row.get("slotDefinitionId"))
        for row in releases
    ]
    if len(pair_keys) != len(set(pair_keys)):
        raise MechanicalInterfaceContractError("duplicate datum pair release")
    return sorted(
        releases,
        key=lambda row: (str(row.get("moduleDefinitionId")), str(row.get("slotDefinitionId"))),
    )


def _mate_row(
    *, step: dict[str, Any], target_token: str, base_token: str,
    target_endpoint: dict[str, Any], base_endpoint: dict[str, Any],
) -> dict[str, Any]:
    endpoints = []
    for index, (row, token) in enumerate(
        ((target_endpoint, target_token), (base_endpoint, base_token))
    ):
        endpoint = copy.deepcopy(row.get("Endpoint") or {})
        endpoint["Index"] = index
        endpoint["ModuleToken"] = token
        endpoints.append(endpoint)
    core = {
        "MateName": step["mateName"],
        "MateType": step["mateType"],
        "MateTypeName": step["mateTypeName"],
        "Alignment": step["alignment"],
        "AlignmentName": step["alignmentName"],
        "Distance": step.get("distanceMeters"),
        "Angle": None,
        "IsSuppressed": False,
        "Endpoints": endpoints,
        "ModuleTokens": [target_token, base_token],
        "ModuleHierarchyPaths": [
            endpoints[0]["ModuleHierarchyPath"],
            endpoints[1]["ModuleHierarchyPath"],
        ],
        "IsBasicTwoFaceRebuildable": True,
        "RebuildRejectionReason": None,
        "AdvancedOptions": (
            {
                "DistanceFlipDimension": bool(
                    step.get("distanceFlipDimension", False)
                )
            }
            if step["mateTypeName"] == "swMateDISTANCE"
            else {}
        ),
    }
    core["MateId"] = "mate:parameterized-datum:" + _digest(core)[:16]
    return core


def _dot(first: list[float], second: list[float]) -> float:
    return sum(float(first[index]) * float(second[index]) for index in range(3))


def _cross(first: list[float], second: list[float]) -> list[float]:
    return [
        float(first[1]) * float(second[2]) - float(first[2]) * float(second[1]),
        float(first[2]) * float(second[0]) - float(first[0]) * float(second[2]),
        float(first[0]) * float(second[1]) - float(first[1]) * float(second[0]),
    ]


def _alignment_sign(step: dict[str, Any]) -> int:
    alignment = step.get("alignment")
    name = str(step.get("alignmentName") or "")
    if alignment == 0 and name == "swMateAlignALIGNED":
        return 1
    if alignment == 1 and name == "swMateAlignANTI_ALIGNED":
        return -1
    raise MechanicalInterfaceContractError(
        "parameterized datum alignment must be ALIGNED or ANTI_ALIGNED"
    )


def _set_alignment(step: dict[str, Any], sign: int) -> None:
    if sign not in {-1, 1}:
        raise MechanicalInterfaceContractError("invalid datum alignment sign")
    step["alignment"] = 0 if sign == 1 else 1
    step["alignmentName"] = (
        "swMateAlignALIGNED" if sign == 1 else "swMateAlignANTI_ALIGNED"
    )


def _frame_handedness(normals: dict[str, list[float]]) -> int:
    value = _dot(
        normals["support_datum"],
        _cross(normals["longitudinal_datum"], normals["lateral_datum"]),
    )
    if abs(abs(value) - 1.0) > 1e-5:
        raise MechanicalInterfaceContractError(
            "datum frame normals do not form an orthonormal handed frame"
        )
    return 1 if value > 0 else -1


def _derive_support_position_alignments(
    template: dict[str, Any],
    module_endpoints: dict[str, dict[str, Any]],
    slot_endpoints: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Keep a three-plane mate recipe a proper rotation, never a reflection.

    Face normals in independently captured base catalogs are not guaranteed to
    share the same polarity.  Reusing a fixed ALIGNED/ALIGNED/ANTI_ALIGNED
    recipe can therefore ask SolidWorks to realize a reflection, which is
    impossible for a rigid component and manifests as an overdefined mate.
    Preserve the longitudinal and support semantics, then derive the lateral
    polarity from the handedness of both registered datum frames.
    """

    roles = ("support_datum", "longitudinal_datum", "lateral_datum")
    module_index = {row["EndpointId"]: row for row in module_endpoints.values()}
    slot_index = {row["EndpointId"]: row for row in slot_endpoints.values()}
    bindings = [
        {"role": role, "endpointId": module_endpoints[role]["EndpointId"]}
        for role in roles
    ]
    module_frame = _validate_planar_frame(module_index, bindings)
    bindings = [
        {"role": role, "endpointId": slot_endpoints[role]["EndpointId"]}
        for role in roles
    ]
    slot_frame = _validate_planar_frame(slot_index, bindings)

    steps = list(template.get("mateSteps") or [])
    by_role = {str(step.get("endpointRoleA") or ""): step for step in steps}
    if set(by_role) != set(roles):
        raise MechanicalInterfaceContractError(
            "support-position recipe must contain exactly three datum-role mates"
        )
    longitudinal_sign = _alignment_sign(by_role["longitudinal_datum"])
    support_sign = _alignment_sign(by_role["support_datum"])
    module_handedness = _frame_handedness(module_frame["normals"])
    slot_handedness = _frame_handedness(slot_frame["normals"])
    lateral_sign = (
        module_handedness
        * support_sign
        * longitudinal_sign
        * slot_handedness
    )
    original_lateral_sign = _alignment_sign(by_role["lateral_datum"])
    _set_alignment(by_role["lateral_datum"], lateral_sign)
    return {
        "method": "proper_rotation_from_registered_datum_frame_handedness",
        "moduleFrameHandedness": module_handedness,
        "slotFrameHandedness": slot_handedness,
        "longitudinalAlignmentSign": longitudinal_sign,
        "supportAlignmentSign": support_sign,
        "originalLateralAlignmentSign": original_lateral_sign,
        "derivedLateralAlignmentSign": lateral_sign,
        "lateralAlignmentChanged": original_lateral_sign != lateral_sign,
        "moduleOrthogonalityResiduals": module_frame["orthogonalityResiduals"],
        "slotOrthogonalityResiduals": slot_frame["orthogonalityResiduals"],
    }


def _validate_planar_frame(
    endpoint_index: dict[str, dict[str, Any]],
    bindings: list[dict[str, str]],
) -> dict[str, Any]:
    if {row.get("role") for row in bindings} != {
        "support_datum",
        "longitudinal_datum",
        "lateral_datum",
    }:
        raise MechanicalInterfaceContractError(
            "datum frame requires support, longitudinal and lateral bindings"
        )
    normals: dict[str, list[float]] = {}
    for binding in bindings:
        endpoint_id = str(binding.get("endpointId") or "")
        endpoint = endpoint_index.get(endpoint_id)
        if not endpoint or endpoint.get("GeometryClass") != "Plane":
            raise MechanicalInterfaceContractError(
                f"datum endpoint is missing or is not planar: {endpoint_id}"
            )
        normal = ((endpoint.get("Endpoint") or {}).get("FaceNormalWorld") or [])
        if len(normal) != 3 or not all(
            isinstance(value, (int, float)) and math.isfinite(float(value))
            for value in normal
        ):
            raise MechanicalInterfaceContractError(
                f"datum endpoint has no finite normal: {endpoint_id}"
            )
        length = math.sqrt(_dot(normal, normal))
        if length <= 1e-9:
            raise MechanicalInterfaceContractError(
                f"datum endpoint normal is degenerate: {endpoint_id}"
            )
        normals[str(binding["role"])] = [float(value) / length for value in normal]
    residuals = {
        "supportLongitudinal": abs(
            _dot(normals["support_datum"], normals["longitudinal_datum"])
        ),
        "supportLateral": abs(
            _dot(normals["support_datum"], normals["lateral_datum"])
        ),
        "longitudinalLateral": abs(
            _dot(normals["longitudinal_datum"], normals["lateral_datum"])
        ),
    }
    if max(residuals.values()) > 1e-5:
        raise MechanicalInterfaceContractError(
            "selected datum faces are not mutually orthogonal"
        )
    return {"normals": normals, "orthogonalityResiduals": residuals}


def _port(
    *,
    port_id: str,
    module_token: str,
    endpoint_ids: tuple[str, str, str],
) -> dict[str, Any]:
    return {
        "portId": port_id,
        "moduleToken": module_token,
        "endpointBindings": [
            {"role": "support_datum", "endpointId": endpoint_ids[0]},
            {"role": "longitudinal_datum", "endpointId": endpoint_ids[1]},
            {"role": "lateral_datum", "endpointId": endpoint_ids[2]},
        ],
    }


def build_parameterized_datum_placement_catalog(workspace: Path) -> dict[str, Any]:
    """Build the bounded first catalog from already captured persistent faces."""

    from .hybrid_plane_axis_slot_selection import (
        build_f000_hybrid_axis_slot_catalog,
    )

    source_specs = {
        "project02::A180": {
            "role": "Scanner",
            "token": "A180",
            "release": "relation-v30-project02-a800-a180-portable-driving-20261011",
            "catalog": "demo/semantic_ports/project02_A180_scanner_installation_v1/face_endpoint_catalog.json",
            # The source installation bundle already contains three planar,
            # mutually orthogonal faces.  The original slot face is planar and
            # is reused only as an explicit lateral datum; no cylindrical or
            # slot geometry is relabelled as a plane.
            "endpoints": (
                "face:a180:551cf5f2dad5f601",
                "face:a180:a6bd2b4633f596f1",
                "face:a180:1a5350d5b6f13b3d",
            ),
        },
        "project03::AI00": {
            "role": "Scanner",
            "token": "AI00",
            "release": "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012",
            "catalog": "demo/semantic_ports/project03_AI00_third_increment_v1/face_endpoint_catalog.json",
            "endpoints": (
                "face:fl9a24d063ai00:916bba1ff4ce84b0",
                "face:fl9a24d063ai00:6af00867073c548b",
                "face:fl9a24d063ai00:054aac68437671a6",
            ),
        },
        "project01::SM00": {
            "role": "Scanner",
            "token": "SM00",
            "release": "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014",
            "catalog": "demo/cross_project_substitution/parameterized-datum-placement-v1/sm00-reference-leaf-face-catalog.json",
            "endpoints": (
                "face:sm00:e5f2f95cec24c438",
                "face:sm00:5728544439ac8430",
                "face:sm00:e7c4794522309563",
            ),
        },
        "project01::GN00": {
            "role": "CleaningWeighing",
            "token": "GN00",
            "release": "relation-v65-project01-gn00-base-only-two-hole-driving-20261022",
            "catalog": "demo/cross_project_substitution/cleaning-weighing-base-only-v1/project01_GN00_project03_AG00/gn00-primary-mount-leaf-face-catalog.json",
            "endpoints": (
                "face:fl9c24n074gn00.001-1:00d6db3b04b7ee00",
                "face:fl9c24n074gn00.001-1:c94aa631af78bf22",
                "face:fl9c24n074gn00.001-1:b9615e9c57819b4f",
            ),
        },
        "project05::N000": {
            "role": "CleaningWeighing",
            "token": "N000",
            "release": "relation-v27-project05-seven-addon-portable-driving-20261011",
            "catalog": "demo/semantic_ports/project05_n000_locator_discovery_v1/n000-mount-leaf-face-catalog.json",
            "endpoints": (
                "face:fl9c251093n000.001-4:6e2021051647e92c",
                "face:fl9c251093n000.001-4:8bc2c2cdbc852cd8",
                "face:fl9c251093n000.001-4:fc0ff231aec1b1f6",
            ),
        },
        "project03::AG00": {
            "role": "CleaningWeighing",
            "token": "AG00",
            "release": "relation-v54-project03-ag00-three-datum-driving-20261014",
            "catalog": "demo/cross_project_substitution/parameterized-datum-placement-v1/ag00-reference-leaf-face-catalog.json",
            "endpoints": (
                "face:fl9a24d063ag00:63944fef6c83a84f",
                "face:fl9a24d063ag00:9d9bc80a6517c165",
                "face:fl9a24d063ag00:7b98894685365262",
            ),
        },
        "project02::A300": {
            "role": "WasteCup",
            "token": "A300",
            "release": "relation-v34-project02-six-addon-portable-driving-20261011",
            "catalog": "demo/semantic_ports/project02_service_installations_v1/A300/face_endpoint_catalog.json",
            # A300's native A600 installation already uses these three real,
            # mutually orthogonal planes as two distances plus support
            # coincidence.  Re-registering the same faces here does not claim
            # that another base has matching holes or fasteners.
            "endpoints": (
                "face:a300:960fc2e356786f7b",
                "face:a300:e38cf1f316aa7f50",
                "face:a300:8a1d29a9d7267029",
            ),
        },
        "project05::P000": {
            "role": "WasteCup",
            "token": "P000",
            "release": "relation-p000-aa00-support-position-demo-20261023-v1",
            "catalog": "demo/cross_project_substitution/wastecup-project05-to-project03-v1/support-position-demo-v1/semantic-package-v1/face_endpoint_catalog.json",
            "endpoints": (
                "face:p000:7598af6ac4af7a69",
                "face:p000:locator:02131bc386306bb8",
                "face:p000:e4735aef3bf5510d",
            ),
        },
        "project02::A800": {
            "role": "Transport",
            "token": "A800",
            "release": "relation-v30-project02-a800-a180-portable-driving-20261011",
            "catalog": "demo/global_assembly_catalog/v1/combination-v1-preview/project02-a800-a180-driving-v1/A800/face_endpoint_catalog.json",
            "endpoints": (
                "face:a800:9ef1e306dd187e0d",
                "face:a800:locator:85076ec7476d155b",
                "face:a800:ed2ff0a605620317",
            ),
        },
        "project05::D000": {
            "role": "Transport",
            "token": "D000",
            "release": "relation-v60-project05-d000-deterministic-driving-20261014",
            "catalog": "demo/global_assembly_catalog/coverage-v2/d000-deterministic-candidate-v1/face_endpoint_catalog.json",
            "endpoints": (
                "face:d000:bee7afa026bf5514",
                "face:d000:6c9f6752fce4aa63",
                "face:d000:fbf5cfa9e7656f83",
            ),
        },
        "project02::A500": {
            "role": "Calibration",
            "token": "A500",
            "release": "relation-v31-project02-a800-a180-a500-portable-driving-20261011",
            "catalog": "demo/global_assembly_catalog/v1/combination-v1-preview/project02-a800-a180-a500-driving-v2/A500/face_endpoint_catalog.json",
            "endpoints": (
                "face:a500:ac632c2f2f1cc391",
                "face:a500:4d31dcd5193457e9",
                "face:a500:7d587bfd92815e6f",
            ),
        },
    }
    # SS00/AE00 remain on their native support+58 mm two-axis route unless a
    # bounded leaf scan has produced a real, explicitly confirmed three-plane
    # alternative. Confirmations are optional and fail closed on stale
    # digests, missing persistent endpoints or non-orthogonal geometry.
    from .transport_datum_port_acquisition import (
        load_confirmed_transport_datum_source_specs,
    )

    source_specs.update(load_confirmed_transport_datum_source_specs(workspace))
    slot_specs = [
        {
            "definition": "project01::JJ00",
            "role": "Scanner",
            "token": "JJ00",
            "release": "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014",
            "catalog": "demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/jj00-scanner-support-leaf-face-catalog.json",
            "endpoints": (
                "face:jj00:046bf2789cf6c785",
                "face:jj00:e44c72a6880619cd",
                "face:jj00:692db7bed55b33c9",
            ),
            "parametersByModule": {
                "project03::AI00": {"longitudinal": 0.070, "lateral": 0.0435, "supportGap": 0.0},
                "project01::SM00": {"longitudinal": 0.070, "lateral": 0.102, "supportGap": 0.0},
            },
            "parameterSource": "module_calibrated_scanner_station_projection",
        },
        {
            "definition": "project03::AA00",
            "role": "Scanner",
            "token": "AA00",
            "release": "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012",
            "catalog": "demo/cross_project_substitution/scanner-slot-discovery-v1/project03_AA00_project01_SM00/aa00-scanner-support-leaf-face-catalog.json",
            "endpoints": (
                "face:aa00:640ce034eb768594",
                "face:aa00:ae9c22cef02ef7bd",
                "face:aa00:929f91708da17e03",
            ),
            "parametersByModule": {
                "project03::AI00": {"longitudinal": 0.070, "lateral": 0.0435, "supportGap": 0.0},
                "project01::SM00": {"longitudinal": 0.070, "lateral": 0.102, "supportGap": 0.0},
            },
            "parameterSource": "module_calibrated_scanner_station_projection",
        },
        {
            "definition": "project02::A600",
            "role": "Scanner",
            "token": "A600",
            "release": "relation-v34-project02-six-addon-portable-driving-20261011",
            "catalog": "demo/semantic_ports/project02_service_installations_v1/A300/face_endpoint_catalog.json",
            "endpoints": (
                "face:a600:f3e3801b99066522",
                "face:a600:614f7ba702b31193",
                "face:a600:17cd6e89a8e64c1e",
            ),
            # A600 already exposes a verified orthogonal frame, but no common
            # station has been approved for A180/AI00/SM00.  Registering the
            # frame makes an explicitly positioned cross-project scanner
            # candidate expressible without inheriting a prototype pose.
            "parametersByModule": {},
            "parameterSource": "stable_base_frame_scanner_station_not_confirmed",
        },
        {
            "definition": "project05::A000",
            "role": "Scanner",
            "token": "A000",
            "release": "relation-v27-project05-seven-addon-portable-driving-20261011",
            "catalog": "demo/semantic_ports/project05_p000_locator_discovery_v1/a000-p000-support-leaf-face-catalog.json",
            "endpoints": (
                "face:fl9c254098a000.001-1:e244c64422de6274",
                "face:fl9c254098a000.001-1:288089408c864285",
                "face:fl9c254098a000.001-1:d38d71808a7006af",
            ),
            "parametersByModule": {},
            "parameterSource": "stable_base_frame_scanner_station_not_confirmed",
        },
        {
            "definition": "project03::AA00",
            "role": "CleaningWeighing",
            "token": "AA00",
            "release": "relation-v54-project03-ag00-three-datum-driving-20261014",
            "catalog": "demo/cross_project_substitution/scanner-slot-discovery-v1/project03_AA00_project01_SM00/aa00-scanner-support-leaf-face-catalog.json",
            "endpoints": (
                "face:aa00:0dea78ae25e9aab4",
                "face:aa00:ae9c22cef02ef7bd",
                "face:aa00:929f91708da17e03",
            ),
            "parametersByModule": {
                "project01::GN00": {"longitudinal": 0.354, "lateral": 0.2535, "supportGap": 0.0},
                "project03::AG00": {"longitudinal": 0.540, "lateral": 0.2385, "supportGap": 0.0},
                "project05::N000": {"longitudinal": 0.465, "lateral": 0.7125, "supportGap": 0.0},
            },
            "parameterSource": "module_calibrated_cleaning_station_projection",
        },
        {
            "definition": "project01::JJ00",
            "role": "CleaningWeighing",
            "token": "JJ00",
            "release": "relation-v65-project01-gn00-base-only-two-hole-driving-20261022",
            "catalog": "demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/jj00-scanner-support-leaf-face-catalog.json",
            "endpoints": (
                "face:jj00:4d272809c45d46b4",
                "face:jj00:e44c72a6880619cd",
                "face:jj00:692db7bed55b33c9",
            ),
            "parametersByModule": {
                "project01::GN00": {"longitudinal": 0.354, "lateral": 0.2535, "supportGap": 0.0},
                "project03::AG00": {"longitudinal": 0.540, "lateral": 0.2385, "supportGap": 0.0},
                "project05::N000": {"longitudinal": 0.465, "lateral": 0.7125, "supportGap": 0.0},
            },
            "parameterSource": "module_calibrated_cleaning_station_projection",
        },
        {
            "definition": "project05::A000",
            "role": "CleaningWeighing",
            "token": "A000",
            "release": "relation-v27-project05-seven-addon-portable-driving-20261011",
            "catalog": "demo/semantic_ports/project05_p000_locator_discovery_v1/a000-p000-support-leaf-face-catalog.json",
            "endpoints": (
                "face:fl9c254098a000.001-1:e244c64422de6274",
                "face:fl9c254098a000.001-1:288089408c864285",
                "face:fl9c254098a000.001-1:d38d71808a7006af",
            ),
            "parametersByModule": {
                "project01::GN00": {"longitudinal": 0.354, "lateral": 0.2535, "supportGap": 0.0},
                "project03::AG00": {"longitudinal": 0.540, "lateral": 0.2385, "supportGap": 0.0},
                "project05::N000": {"longitudinal": 0.465, "lateral": 0.7125, "supportGap": 0.0},
            },
            "parameterSource": "module_calibrated_cleaning_station_projection",
        },
        {
            "definition": "project02::A600",
            "role": "CleaningWeighing",
            "token": "A600",
            "release": "relation-v34-project02-six-addon-portable-driving-20261011",
            "catalog": "demo/semantic_ports/project02_service_installations_v1/A300/face_endpoint_catalog.json",
            "endpoints": (
                "face:a600:f3e3801b99066522",
                "face:a600:614f7ba702b31193",
                "face:a600:17cd6e89a8e64c1e",
            ),
            # The N000 distance magnitudes came from the reviewed station
            # projection.  The former release applied the lateral distance to
            # the outward side of A600's edge datum, so it was fully
            # constrained but physically outside the finite platform.  Keep
            # the magnitude and make the direction plus finite-support proof
            # explicit.
            "parametersByModule": {
                "project05::N000": {
                    "longitudinal": 0.465,
                    "lateral": 0.7125,
                    "supportGap": 0.0,
                },
            },
            "distanceFlipsByModule": {
                "project05::N000": {
                    "longitudinal": False,
                    "lateral": True,
                    "supportGap": False,
                },
            },
            "finiteSupportProfilesByModule": {
                "project05::N000": {
                    "schemaVersion": "finite-support-profile/v1",
                    "required": True,
                    "coordinateFrame": "A600_INSTALLATION_FRAME",
                    "safeBoundary": {
                        "minX": 0.03,
                        "minY": -0.7700000000000017,
                        "maxX": 1.6105000000000007,
                        "maxY": 0.7700000000000085,
                    },
                    "baseDatumCoordinates": {
                        "longitudinal": -0.0002,
                        "lateral": -0.8,
                    },
                    "distanceDirectionWhenNotFlipped": {
                        "longitudinal": 1,
                        "lateral": -1,
                    },
                    "movingFootprintOffsetsFromDatum": {
                        "minLongitudinal": -0.02635046556066454,
                        "maxLongitudinal": 0.17089973068033522,
                        "minLateral": -0.488631527911684,
                        "maxLateral": 0.01754123607131603,
                    },
                    "evidence": {
                        "supportSurface": "demo/layout_previews/project02_a600_installation_surface.json",
                        "installationFrame": "demo/layout_previews/project02_a600_installation_frame.json",
                        "preRepairAudit": ".codex-artifacts/final-assembly-live-audit.json",
                        "formerReleaseId": "datum-placement-9a2449cb1402b751",
                    },
                },
            },
            "parameterSource": "a600_local_frame_projection_with_finite_support_gate",
        },
        {
            "definition": "project02::A600",
            "role": "WasteCup",
            "token": "A600",
            "release": "relation-v34-project02-six-addon-portable-driving-20261011",
            "catalog": "demo/semantic_ports/project02_service_installations_v1/A300/face_endpoint_catalog.json",
            "endpoints": (
                "face:a600:f3e3801b99066522",
                "face:a600:614f7ba702b31193",
                "face:a600:17cd6e89a8e64c1e",
            ),
            "parametersByModule": {
                "project02::A300": {"longitudinal": 0.080, "lateral": 0.390, "supportGap": 0.0},
                "project05::P000": {"longitudinal": 0.080, "lateral": 0.390, "supportGap": 0.0},
            },
            "parameterSource": "released_project02_service_station_and_p000_demo_projection",
        },
        {
            "definition": "project03::AA00",
            "role": "WasteCup",
            "token": "AA00",
            "release": "relation-p000-aa00-support-position-demo-20261023-v1",
            "catalog": "demo/cross_project_substitution/wastecup-project05-to-project03-v1/support-position-demo-v1/semantic-package-v1/face_endpoint_catalog.json",
            "endpoints": (
                "face:aa00:0dea78ae25e9aab4",
                "face:aa00:ae9c22cef02ef7bd",
                "face:aa00:9ef0fb60b1085456",
            ),
            "parametersByModule": {
                "project05::P000": {"longitudinal": 0.400, "lateral": 0.200, "supportGap": 0.0},
            },
            "parameterSource": "released_p000_aa00_support_position_demo",
        },
        {
            "definition": "project01::JJ00",
            "role": "WasteCup",
            "token": "JJ00",
            "release": "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014",
            "catalog": "demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/jj00-scanner-support-leaf-face-catalog.json",
            "endpoints": (
                "face:jj00:4d272809c45d46b4",
                "face:jj00:e44c72a6880619cd",
                "face:jj00:692db7bed55b33c9",
            ),
            # The stable base frame is known, but no waste-cup station has
            # been approved on JJ00.  The empty map deliberately keeps every
            # exact pair behind explicit position confirmation.
            "parametersByModule": {},
            "parameterSource": "stable_base_frame_position_not_confirmed",
        },
        {
            "definition": "project05::A000",
            "role": "WasteCup",
            "token": "A000",
            "release": "relation-v27-project05-seven-addon-portable-driving-20261011",
            "catalog": "demo/semantic_ports/project05_p000_locator_discovery_v1/a000-p000-support-leaf-face-catalog.json",
            "endpoints": (
                "face:fl9c254098a000.001-1:e244c64422de6274",
                "face:fl9c254098a000.001-1:288089408c864285",
                "face:fl9c254098a000.001-1:d38d71808a7006af",
            ),
            # P000 has a released native slot/parallel/distance interface on
            # A000.  A three-plane fallback is registered only as an explicit
            # alternative and therefore has no implicit position preset.
            "parametersByModule": {},
            "parameterSource": "stable_base_frame_native_interface_preferred",
        },
        # A800 and D000 expose real support/longitudinal/lateral planes, but
        # the desired station on a different base is a design input.  Register
        # the four stable base frames with no implicit presets so the planner
        # can accept explicit parameters without inheriting prototype poses.
        *[
            {
                "definition": definition,
                "role": "Transport",
                "token": token,
                "release": release_id,
                "catalog": catalog_path,
                "endpoints": endpoints,
                "parametersByModule": {},
                "parameterSource": "stable_base_frame_transport_station_not_confirmed",
            }
            for definition, token, release_id, catalog_path, endpoints in (
                (
                    "project01::JJ00",
                    "JJ00",
                    "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014",
                    "demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/jj00-scanner-support-leaf-face-catalog.json",
                    (
                        "face:jj00:4d272809c45d46b4",
                        "face:jj00:e44c72a6880619cd",
                        "face:jj00:692db7bed55b33c9",
                    ),
                ),
                (
                    "project02::A600",
                    "A600",
                    "relation-v34-project02-six-addon-portable-driving-20261011",
                    "demo/semantic_ports/project02_service_installations_v1/A300/face_endpoint_catalog.json",
                    (
                        "face:a600:f3e3801b99066522",
                        "face:a600:614f7ba702b31193",
                        "face:a600:17cd6e89a8e64c1e",
                    ),
                ),
                (
                    "project03::AA00",
                    "AA00",
                    "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012",
                    "demo/cross_project_substitution/scanner-slot-discovery-v1/project03_AA00_project01_SM00/aa00-scanner-support-leaf-face-catalog.json",
                    (
                        "face:aa00:0dea78ae25e9aab4",
                        "face:aa00:ae9c22cef02ef7bd",
                        "face:aa00:929f91708da17e03",
                    ),
                ),
                (
                    "project05::A000",
                    "A000",
                    "relation-v27-project05-seven-addon-portable-driving-20261011",
                    "demo/semantic_ports/project05_p000_locator_discovery_v1/a000-p000-support-leaf-face-catalog.json",
                    (
                        "face:fl9c254098a000.001-1:e244c64422de6274",
                        "face:fl9c254098a000.001-1:288089408c864285",
                        "face:fl9c254098a000.001-1:d38d71808a7006af",
                    ),
                ),
            )
        ],
        # A500 has the same three-plane evidence quality.  Its native A600
        # width-centering interface remains preferred; these fields only make
        # an explicitly positioned cross-base alternative expressible.
        *[
            {
                "definition": definition,
                "role": "Calibration",
                "token": token,
                "release": release_id,
                "catalog": catalog_path,
                "endpoints": endpoints,
                "parametersByModule": {},
                "parameterSource": "stable_base_frame_calibration_station_not_confirmed",
            }
            for definition, token, release_id, catalog_path, endpoints in (
                (
                    "project01::JJ00",
                    "JJ00",
                    "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014",
                    "demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/jj00-scanner-support-leaf-face-catalog.json",
                    (
                        "face:jj00:4d272809c45d46b4",
                        "face:jj00:e44c72a6880619cd",
                        "face:jj00:692db7bed55b33c9",
                    ),
                ),
                (
                    "project02::A600",
                    "A600",
                    "relation-v31-project02-a800-a180-a500-portable-driving-20261011",
                    "demo/semantic_ports/project02_service_installations_v1/A300/face_endpoint_catalog.json",
                    (
                        "face:a600:f3e3801b99066522",
                        "face:a600:614f7ba702b31193",
                        "face:a600:17cd6e89a8e64c1e",
                    ),
                ),
                (
                    "project03::AA00",
                    "AA00",
                    "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012",
                    "demo/cross_project_substitution/scanner-slot-discovery-v1/project03_AA00_project01_SM00/aa00-scanner-support-leaf-face-catalog.json",
                    (
                        "face:aa00:0dea78ae25e9aab4",
                        "face:aa00:ae9c22cef02ef7bd",
                        "face:aa00:929f91708da17e03",
                    ),
                ),
                (
                    "project05::A000",
                    "A000",
                    "relation-v27-project05-seven-addon-portable-driving-20261011",
                    "demo/semantic_ports/project05_p000_locator_discovery_v1/a000-p000-support-leaf-face-catalog.json",
                    (
                        "face:fl9c254098a000.001-1:e244c64422de6274",
                        "face:fl9c254098a000.001-1:288089408c864285",
                        "face:fl9c254098a000.001-1:d38d71808a7006af",
                    ),
                ),
            )
        ],
    ]

    contracts: list[dict[str, Any]] = []
    datum_audit: list[dict[str, Any]] = []
    for definition_id, spec in source_specs.items():
        path = workspace / str(spec["catalog"])
        port = _port(
            port_id=f"{spec['token']}.parameterized_datum_installation.v1",
            module_token=str(spec["token"]),
            endpoint_ids=spec["endpoints"],
        )
        audit = _validate_planar_frame(_endpoint_index(path), port["endpointBindings"])
        datum_audit.append(
            {"owner": definition_id, "side": "moving_module", "source": spec["catalog"], **audit}
        )
        contracts.append(
            build_support_position_contract(
                port=port,
                release_manifest=_released_manifest(workspace, str(spec["release"])),
                side="moving_module",
                module_role=str(spec["role"]),
                module_definition_id=definition_id,
            )
        )

    for index, spec in enumerate(slot_specs, start=1):
        path = workspace / str(spec["catalog"])
        port = _port(
            port_id=f"{spec['token']}.{str(spec['role']).lower()}_datum_field.v1",
            module_token=str(spec["token"]),
            endpoint_ids=spec["endpoints"],
        )
        audit = _validate_planar_frame(_endpoint_index(path), port["endpointBindings"])
        datum_audit.append(
            {
                "owner": spec["definition"],
                "side": "base_slot",
                "acceptedRole": spec["role"],
                "source": spec["catalog"],
                **audit,
            }
        )
        parameter_map = copy.deepcopy(spec["parametersByModule"])
        contract_kwargs: dict[str, Any] = {}
        if parameter_map:
            contract_kwargs["position_parameters_meters"] = copy.deepcopy(
                next(iter(parameter_map.values()))
            )
        if spec.get("distanceFlipsByModule"):
            contract_kwargs[
                "distance_flip_dimensions_by_module_definition_id"
            ] = copy.deepcopy(spec["distanceFlipsByModule"])
        if spec.get("finiteSupportProfilesByModule"):
            contract_kwargs[
                "finite_support_profiles_by_module_definition_id"
            ] = copy.deepcopy(spec["finiteSupportProfilesByModule"])
        contract = build_support_position_contract(
            port=port,
            release_manifest=_released_manifest(workspace, str(spec["release"])),
            side="base_slot",
            module_role="Base",
            module_definition_id=str(spec["definition"]),
            accepted_module_roles=[str(spec["role"])],
            position_parameters_by_module_definition_id=parameter_map,
            **contract_kwargs,
        )
        contract["geometrySignature"]["parameterSource"] = spec["parameterSource"]
        contract["geometrySignature"]["notVendorDatum"] = True
        # The metadata changes the contract identity and is intentionally part
        # of its immutable content.
        contract["contractId"] = "interface-contract/" + _digest(
            {key: value for key, value in contract.items() if key != "contractId"}
        )[:16]
        contracts.append(contract)

    modules = [row for row in contracts if row["side"] == "moving_module"]
    slots = [row for row in contracts if row["side"] == "base_slot"]
    released_pair_evidence = _validated_pair_releases(workspace)
    enriched_pair_evidence: list[dict[str, Any]] = []
    for release in released_pair_evidence:
        if release.get("placementMode") in {
            "reviewed_hybrid_plane_axis_datum",
            "reviewed_flexible_calibration_slot",
        }:
            enriched_pair_evidence.append(release)
            continue
        module_rows = [
            row
            for row in modules
            if row.get("moduleDefinitionId") == release.get("moduleDefinitionId")
        ]
        if len(module_rows) != 1:
            raise MechanicalInterfaceContractError(
                "released datum pair no longer resolves to one moving-module contract"
            )
        module_contract = module_rows[0]
        slot_rows = [
            row
            for row in slots
            if row.get("moduleDefinitionId") == release.get("slotDefinitionId")
            and module_contract.get("moduleRole")
            in (row.get("acceptedModuleRoles") or [])
        ]
        if len(slot_rows) != 1:
            raise MechanicalInterfaceContractError(
                "released datum pair no longer resolves to one role-compatible slot"
            )
        slot_contract = slot_rows[0]
        module_catalog_path = workspace / _catalog_source_for_contract(
            {"datumFrameAudit": datum_audit},
            module_contract,
            module_role=str(module_contract.get("moduleRole") or ""),
        )
        slot_catalog_path = workspace / _catalog_source_for_contract(
            {"datumFrameAudit": datum_audit},
            slot_contract,
            module_role=str(module_contract.get("moduleRole") or ""),
        )
        resolution = _resolve_three_plane_pair_release(
            release,
            _selected_endpoint_rows(_read(module_catalog_path), module_contract),
            _selected_endpoint_rows(_read(slot_catalog_path), slot_contract),
        )
        enriched = copy.deepcopy(release)
        enriched["catalogResolution"] = resolution
        enriched_pair_evidence.append(enriched)
        if resolution["currentCatalogBindingsMatch"]:
            geometry = slot_contract["geometrySignature"]
            geometry.setdefault("positionParametersByModuleDefinitionId", {})[
                str(release["moduleDefinitionId"])
            ] = copy.deepcopy(resolution["positionParametersMeters"])
            if not geometry.get("positionParametersMeters"):
                geometry["positionParametersMeters"] = copy.deepcopy(
                    resolution["positionParametersMeters"]
                )
            geometry.setdefault("distanceFlipDimensionsByModuleDefinitionId", {})[
                str(release["moduleDefinitionId"])
            ] = copy.deepcopy(resolution["distanceFlipDimensions"])
    for slot in slots:
        slot["contractId"] = "interface-contract/" + _digest(
            {key: value for key, value in slot.items() if key != "contractId"}
        )[:16]
    released_pair_evidence = enriched_pair_evidence
    pair_release_index = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): row
        for row in released_pair_evidence
    }
    candidate_reuse_blocks = _candidate_reuse_safety_blocks(workspace)
    matrix: list[dict[str, Any]] = []
    templates: list[dict[str, Any]] = []
    for module in modules:
        for slot in slots:
            pair = (module["moduleDefinitionId"], slot["moduleDefinitionId"])
            match = match_interface_contracts(
                module,
                slot,
                pair_release_evidence=pair_release_index.get(
                    pair
                ),
            )
            safety_block = candidate_reuse_blocks.get(pair)
            if safety_block is not None and match["compatible"]:
                match["candidateReuseBlocked"] = True
                match["status"] = "blocked_by_release_safety_policy"
                match["mateInstantiationAllowed"] = False
                match["requiresNewPairCadValidation"] = False
                match["existingPairReleaseReusable"] = False
                match["safetyBlocker"] = {
                    "code": safety_block.get("reasonCode"),
                    "detail": safety_block.get("reason"),
                    "replacementPolicy": safety_block.get("replacementPolicy"),
                }
            matrix.append(match)
            if match["compatible"] and not match.get("candidateReuseBlocked"):
                templates.append(instantiate_connection_template(match, module, slot))

    hybrid_catalog = build_f000_hybrid_axis_slot_catalog(workspace)
    hybrid_rows = []
    for row in hybrid_catalog["baseSlots"]:
        pair = (
            str(hybrid_catalog["moduleDefinitionId"]),
            str(row["slotDefinitionId"]),
        )
        evidence = pair_release_index.get(pair)
        if evidence:
            if evidence.get("placementMode") != "reviewed_hybrid_plane_axis_datum":
                raise MechanicalInterfaceContractError(
                    "F000 hybrid pair release has the wrong placement mode"
                )
            selected_axis = str(evidence.get("selectedAxisEndpointId") or "")
            candidate_ids = {
                str(candidate.get("endpointId") or "")
                for candidate in row.get("axisCandidates") or []
            }
            if not selected_axis or selected_axis not in candidate_ids:
                raise MechanicalInterfaceContractError(
                    "F000 hybrid pair release references an unknown base axis"
                )
            hybrid_rows.append(
                {
                    "moduleDefinitionId": pair[0],
                    "slotDefinitionId": pair[1],
                    "interfaceFamily": hybrid_catalog["interfaceFamily"],
                    "recipeId": hybrid_catalog["recipeId"],
                    "status": "released_hybrid_pair",
                    "candidateAxisLineCount": row["candidateAxisLineCount"],
                    "requiresExplicitAxisSelection": False,
                    "readyForReleasedCadExecution": True,
                    "selectedAxisEndpointId": selected_axis,
                    "pairReleaseEvidence": copy.deepcopy(evidence),
                }
            )
            continue
        hybrid_rows.append(
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                "interfaceFamily": hybrid_catalog["interfaceFamily"],
                "recipeId": hybrid_catalog["recipeId"],
                "status": row["state"],
                "candidateAxisLineCount": row["candidateAxisLineCount"],
                "requiresExplicitAxisSelection": row[
                    "requiresExplicitAxisSelection"
                ],
                "readyForReleasedCadExecution": row[
                    "readyForReleasedCadExecution"
                ],
            }
        )
    report = {
        "schemaVersion": DATUM_PLACEMENT_CATALOG_SCHEMA,
        "role": "ParameterizedDatumPlacementFallback",
        "contracts": contracts,
        "releasedPairEvidence": released_pair_evidence,
        "compatibilityMatrix": matrix,
        "instantiatedTemplates": templates,
        "datumFrameAudit": datum_audit,
        "alternateRecipeCandidates": hybrid_rows,
        "alternateRecipeCatalog": {
            "schemaVersion": hybrid_catalog["schemaVersion"],
            "catalogDigest": hybrid_catalog["catalogDigest"],
            "moduleDefinitionId": hybrid_catalog["moduleDefinitionId"],
            "claimBoundary": hybrid_catalog["claimBoundary"],
        },
        "captureGaps": [],
        "summary": {
            "modulePortCount": len(modules),
            "alternateRecipeModulePortCount": 1,
            "totalRegisteredMovingModulePortCount": len(modules) + 1,
            "baseSlotCount": len(slots),
            "compatiblePairCount": sum(row["compatible"] for row in matrix),
            "incompatiblePairCount": sum(not row["compatible"] for row in matrix),
            "releasedPairCount": sum(
                row["existingPairReleaseReusable"] for row in matrix
            ),
            "genericRecipeCount": 2,
            "cadValidationCandidateCount": sum(
                row["requiresNewPairCadValidation"] for row in matrix
            ),
            "candidateReuseSafetyBlockedCount": sum(
                row.get("candidateReuseBlocked") is True for row in matrix
            ),
            "explicitAxisSelectionRequiredCount": sum(
                row["status"] == "explicit_axis_selection_required"
                for row in hybrid_rows
            ),
            "alternateRecipeReleasedNativePairCount": int(
                hybrid_catalog["summary"]["releasedNativePairCount"]
            ),
            "alternateRecipeReleasedPairCount": sum(
                row["status"] in {
                    "released_native_pair",
                    "released_hybrid_pair",
                }
                for row in hybrid_rows
            ),
            "captureGapCount": 0,
        },
        "selectionPolicy": [
            "native_mechanical_interface",
            "confirmed_alternate_mechanical_slot",
            "parameterized_datum_placement",
            "adapter_or_manual_resolution",
        ],
        "claimBoundary": (
            "Compatible rows only prove that three stable planar datums can express a rigid CAD pose. "
            "Every pair still requires non-prototype CAD validation and an explicit release; physical "
            "fastening, collision, B-rep and production approval are not claimed."
        ),
    }
    report["catalogDigest"] = _digest(report)
    validate_contract_catalog(report)
    return report


def load_parameterized_datum_placement_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/parameterized-datum-placement-v1/"
        "interface-contract-catalog.json"
    )
    report = _read(path)
    validate_contract_catalog(report)
    if report.get("schemaVersion") != DATUM_PLACEMENT_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError(
            "not a parameterized datum-placement catalog"
        )
    return report


def plan_parameterized_datum_placement(
    workspace: Path,
    module_definition_id: str,
    *,
    selected_slot_definition_id: str | None = None,
) -> dict[str, Any]:
    report = load_parameterized_datum_placement_catalog(workspace)
    modules = [
        row
        for row in report["contracts"]
        if row.get("side") == "moving_module"
        and row.get("moduleDefinitionId") == module_definition_id
    ]
    if not modules:
        alternate = [
            row
            for row in report.get("alternateRecipeCandidates") or []
            if row.get("moduleDefinitionId") == module_definition_id
            and (
                selected_slot_definition_id is None
                or row.get("slotDefinitionId") == selected_slot_definition_id
            )
        ]
        if alternate:
            selected = alternate[0] if len(alternate) == 1 else None
            selected_status = str((selected or {}).get("status") or "")
            released = selected_status in {
                "released_native_pair",
                "released_hybrid_pair",
            }
            selected_match = None
            if selected and released:
                selected_match = {
                    "compatible": True,
                    "mateInstantiationAllowed": True,
                    "requiresNewPairCadValidation": False,
                    "existingPairReleaseReusable": True,
                    "pairReleaseEvidence": copy.deepcopy(
                        selected.get("pairReleaseEvidence")
                    ),
                    "moduleDefinitionId": module_definition_id,
                    "slotDefinitionId": selected.get("slotDefinitionId"),
                    "interfaceFamily": selected.get("interfaceFamily"),
                    "status": "compatible_released_pair",
                }
            return {
                "schemaVersion": PLAN_SCHEMA,
                "moduleDefinitionId": module_definition_id,
                "selectedSlotDefinitionId": selected_slot_definition_id,
                "status": (
                    "released_hybrid_native_pair"
                    if selected_status == "released_native_pair"
                    else "released_hybrid_pair_ready"
                    if selected_status == "released_hybrid_pair"
                    else "hybrid_axis_selection_required"
                    if selected
                    else "hybrid_axis_slot_confirmation_required"
                ),
                "placementMode": "reviewed_hybrid_plane_axis_datum",
                "readyForTemplateCompilation": released,
                "readyForReleasedCadExecution": bool(
                    released and selected.get("readyForReleasedCadExecution")
                ),
                "selectedMatch": selected_match,
                "requiresExplicitAxisSelection": bool(
                    selected and selected.get("requiresExplicitAxisSelection")
                ),
                "candidateAxisLineCount": (
                    selected.get("candidateAxisLineCount") if selected else None
                ),
                "alternateRecipeCandidates": alternate,
                "physicalFasteningVerified": False,
                "productionReady": False,
                "captureGap": None,
            }
        gap = next(
            (
                row
                for row in report.get("captureGaps") or []
                if row.get("moduleDefinitionId") == module_definition_id
            ),
            None,
        )
        return {
            "schemaVersion": PLAN_SCHEMA,
            "moduleDefinitionId": module_definition_id,
            "status": "datum_port_capture_required" if gap else "module_not_registered",
            "readyForTemplateCompilation": False,
            "readyForReleasedCadExecution": False,
            "captureGap": gap,
        }
    slots = [row for row in report["contracts"] if row.get("side") == "base_slot"]
    selected_contract_id: str | None = None
    if selected_slot_definition_id:
        role = modules[0].get("moduleRole")
        selected = [
            row
            for row in slots
            if row.get("moduleDefinitionId") == selected_slot_definition_id
            and role in (row.get("acceptedModuleRoles") or [])
        ]
        if len(selected) != 1:
            return {
                "schemaVersion": PLAN_SCHEMA,
                "moduleDefinitionId": module_definition_id,
                "selectedSlotDefinitionId": selected_slot_definition_id,
                "status": "datum_slot_not_registered_for_role",
                "readyForTemplateCompilation": False,
                "readyForReleasedCadExecution": False,
            }
        selected_contract_id = selected[0]["contractId"]
        safety_blocked = next(
            (
                row
                for row in report.get("compatibilityMatrix") or []
                if row.get("moduleDefinitionId") == module_definition_id
                and row.get("slotContractId") == selected_contract_id
                and row.get("candidateReuseBlocked") is True
            ),
            None,
        )
        if safety_blocked is not None:
            return {
                "schemaVersion": PLAN_SCHEMA,
                "moduleDefinitionId": module_definition_id,
                "selectedSlotDefinitionId": selected_slot_definition_id,
                "status": "datum_candidate_blocked_by_safety_policy",
                "placementMode": "parameterized_datum_placement",
                "readyForTemplateCompilation": False,
                "readyForReleasedCadExecution": False,
                "physicalFasteningVerified": False,
                "productionReady": False,
                "acceptsExplicitPositionParameters": False,
                "selectedMatch": copy.deepcopy(safety_blocked),
                "safetyBlocker": copy.deepcopy(
                    safety_blocked.get("safetyBlocker") or {}
                ),
                "instantiatedTemplate": None,
                "candidates": [copy.deepcopy(safety_blocked)],
            }
    plan = plan_module_slot_connection(
        modules[0],
        slots,
        selected_slot_contract_id=selected_contract_id,
        pair_release_evidence=report.get("releasedPairEvidence") or [],
    )
    selected_match = plan.get("selectedMatch") or {}
    explicit_parameter_candidate = None
    if selected_slot_definition_id and plan.get("status") == "selected_slot_incompatible":
        candidates = [
            row
            for row in plan.get("candidates") or []
            if row.get("slotDefinitionId") == selected_slot_definition_id
            and {item.get("code") for item in row.get("blockers") or []}
            in (
                {"MODULE_POSITION_PRESET_MISSING"},
                {"POSITION_PARAMETERS_MISSING"},
            )
        ]
        if len(candidates) == 1:
            explicit_parameter_candidate = candidates[0]
    return {
        "schemaVersion": PLAN_SCHEMA,
        "moduleDefinitionId": module_definition_id,
        "selectedSlotDefinitionId": selected_slot_definition_id,
        "status": (
            "datum_candidate_blocked_by_safety_policy"
            if selected_match.get("candidateReuseBlocked") is True
            else
            "released_datum_placement_ready"
            if selected_match.get("existingPairReleaseReusable") is True
            else "datum_fallback_candidate_requires_cad_validation"
            if selected_match.get("compatible") is True
            else "datum_fallback_requires_explicit_position_parameters"
            if explicit_parameter_candidate is not None
            else plan["status"]
        ),
        "placementMode": "parameterized_datum_placement",
        "readyForTemplateCompilation": (
            plan["readyForTemplateCompilation"]
            and selected_match.get("candidateReuseBlocked") is not True
        ),
        "readyForReleasedCadExecution": (
            selected_match.get("existingPairReleaseReusable") is True
        ),
        "physicalFasteningVerified": False,
        "productionReady": False,
        "acceptsExplicitPositionParameters": explicit_parameter_candidate is not None,
        "explicitPositionParameterSchema": (
            {
                "required": ["longitudinal", "lateral", "supportGap"],
                "unit": "metre",
                "finiteNonnegative": True,
            }
            if explicit_parameter_candidate is not None
            else None
        ),
        "explicitParameterCandidate": explicit_parameter_candidate,
        "catalogPlan": plan,
        "selectedMatch": plan.get("selectedMatch"),
        "instantiatedTemplate": plan.get("instantiatedTemplate"),
        "candidates": plan.get("candidates"),
    }


def compile_parameterized_datum_validation_package(
    workspace: Path,
    module_definition_id: str,
    slot_definition_id: str,
    *,
    initial_placement_variant: int = 1,
    position_parameters: dict[str, float] | None = None,
    distance_flip_dimensions: dict[str, bool] | None = None,
    bounded_role_station_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile one unreleased pair into an auditable non-prototype CAD graph.

    This function deliberately stops before CAD execution.  The graph carries
    an identity target transform plus a deterministic placement variant, so a
    later run cannot silently inherit the target's prototype top-level pose.
    """

    pair = (module_definition_id, slot_definition_id)
    safety_block = _candidate_reuse_safety_blocks(workspace).get(pair)
    if safety_block is not None:
        if bounded_role_station_candidate is None:
            raise MechanicalInterfaceContractError(
                "datum candidate is blocked by release safety policy: "
                f"{safety_block.get('reasonCode')}; "
                f"{safety_block.get('replacementPolicy')}"
            )
        from .bounded_role_station import validate_bounded_role_station_candidate

        validate_bounded_role_station_candidate(
            bounded_role_station_candidate,
            module_definition_id=module_definition_id,
            slot_definition_id=slot_definition_id,
            position_parameters=position_parameters,
            distance_flip_dimensions=distance_flip_dimensions,
            safety_block=safety_block,
        )

    if (
        isinstance(initial_placement_variant, bool)
        or not isinstance(initial_placement_variant, int)
        or initial_placement_variant < 0
    ):
        raise MechanicalInterfaceContractError(
            "initial placement variant must be a non-negative integer"
        )
    if position_parameters is not None and (
        set(position_parameters) != {"longitudinal", "lateral", "supportGap"}
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in position_parameters.values()
        )
    ):
        raise MechanicalInterfaceContractError(
            "position parameters require finite nonnegative longitudinal/lateral/supportGap metres"
        )
    if distance_flip_dimensions is not None and (
        position_parameters is None
        or set(distance_flip_dimensions) != {"longitudinal", "lateral", "supportGap"}
        or any(type(value) is not bool for value in distance_flip_dimensions.values())
    ):
        raise MechanicalInterfaceContractError("distance direction override requires explicit position parameters and three boolean flips")
    report = load_parameterized_datum_placement_catalog(workspace)
    all_contracts = list(report.get("contracts") or [])
    if position_parameters is not None:
        module_rows = [
            row
            for row in all_contracts
            if row.get("side") == "moving_module"
            and row.get("moduleDefinitionId") == module_definition_id
        ]
        if len(module_rows) != 1:
            raise MechanicalInterfaceContractError(
                "explicit position candidate requires one registered module datum port"
            )
        module_contract = module_rows[0]
        module_role = str(module_contract.get("moduleRole") or "")
        slot_rows = [
            row
            for row in all_contracts
            if row.get("side") == "base_slot"
            and row.get("moduleDefinitionId") == slot_definition_id
            and module_role in (row.get("acceptedModuleRoles") or [])
        ]
        if len(slot_rows) != 1:
            raise MechanicalInterfaceContractError(
                "explicit position candidate requires one role-compatible base datum field"
            )
        slot_contract = copy.deepcopy(slot_rows[0])
        if distance_flip_dimensions is not None:
            slot_contract["geometrySignature"]["distanceFlipDimensions"] = copy.deepcopy(distance_flip_dimensions)
            slot_contract["geometrySignature"].setdefault(
                "distanceFlipDimensionsByModuleDefinitionId", {}
            )[module_definition_id] = copy.deepcopy(distance_flip_dimensions)
        slot_contract["geometrySignature"]["positionParametersMeters"] = copy.deepcopy(
            position_parameters
        )
        slot_contract["geometrySignature"].setdefault(
            "positionParametersByModuleDefinitionId", {}
        )[module_definition_id] = copy.deepcopy(position_parameters)
        slot_contract["geometrySignature"][
            "parameterSource"
        ] = "explicit_validation_candidate_override"
        slot_contract["contractId"] = "interface-contract/" + _digest(
            {key: value for key, value in slot_contract.items() if key != "contractId"}
        )[:16]
        selected = match_interface_contracts(module_contract, slot_contract)
        if selected.get("compatible") is not True:
            raise MechanicalInterfaceContractError(
                "explicit position parameters did not produce a compatible datum pair: "
                + json.dumps(selected.get("blockers") or [], ensure_ascii=False)
            )
        template = instantiate_connection_template(
            selected, module_contract, slot_contract
        )
        released_pair = False
    else:
        plan = plan_parameterized_datum_placement(
            workspace,
            module_definition_id,
            selected_slot_definition_id=slot_definition_id,
        )
        released_pair = plan.get("status") == "released_datum_placement_ready"
        if plan.get("status") not in {
            "datum_fallback_candidate_requires_cad_validation",
            "released_datum_placement_ready",
        }:
            raise MechanicalInterfaceContractError(
                "validation package requires one compatible unreleased datum pair"
            )
        selected = plan.get("selectedMatch") or {}
        contracts = {row["contractId"]: row for row in all_contracts}
        try:
            module_contract = contracts[str(selected["moduleContractId"])]
            slot_contract = contracts[str(selected["slotContractId"])]
        except KeyError as exc:
            raise MechanicalInterfaceContractError(
                "selected pair does not resolve to two catalog contracts"
            ) from exc
        template = copy.deepcopy(plan["instantiatedTemplate"])
    module_role = str(module_contract.get("moduleRole") or "")
    module_catalog_path = workspace / _catalog_source_for_contract(
        report, module_contract, module_role=module_role
    )
    slot_catalog_path = workspace / _catalog_source_for_contract(
        report, slot_contract, module_role=module_role
    )
    module_catalog = _read(module_catalog_path)
    slot_catalog = _read(slot_catalog_path)
    module_endpoints = _selected_endpoint_rows(module_catalog, module_contract)
    slot_endpoints = _selected_endpoint_rows(slot_catalog, slot_contract)
    template = copy.deepcopy(template)
    alignment_derivation = _derive_support_position_alignments(
        template, module_endpoints, slot_endpoints
    )
    target_token = str(module_contract.get("moduleToken") or "")
    base_token = str(slot_contract.get("moduleToken") or "")
    if not target_token or not base_token or target_token == base_token:
        raise MechanicalInterfaceContractError("invalid target/base token pair")
    target_module = _module_record(
        module_catalog, module_endpoints, target_token, nonprototype_target=True
    )
    base_module = _module_record(
        slot_catalog, slot_endpoints, base_token, nonprototype_target=False
    )
    if not Path(str(target_module.get("Path") or "")).is_file():
        raise MechanicalInterfaceContractError("target module source assembly is missing")
    cache_entry_path, source_assembly_path = _base_wrapper_source(
        workspace, base_token
    )
    mates = [
        _mate_row(
            step=step,
            target_token=target_token,
            base_token=base_token,
            target_endpoint=module_endpoints[str(step["endpointRoleA"])],
            base_endpoint=slot_endpoints[str(step["endpointRoleB"])],
        )
        for step in template.get("mateSteps") or []
    ]
    if len(mates) != 3:
        raise MechanicalInterfaceContractError("datum validation graph requires three mates")
    slot_geometry = slot_contract.get("geometrySignature") or {}
    parameter_overrides = slot_geometry.get(
        "positionParametersByModuleDefinitionId"
    ) or {}
    effective_position_parameters = copy.deepcopy(
        position_parameters
        or parameter_overrides.get(module_definition_id)
        or slot_geometry.get("positionParametersMeters")
        or {}
    )
    flip_overrides = slot_geometry.get(
        "distanceFlipDimensionsByModuleDefinitionId"
    ) or {}
    effective_distance_flips = copy.deepcopy(
        distance_flip_dimensions
        or flip_overrides.get(module_definition_id)
        or slot_geometry.get("distanceFlipDimensions")
        or {"longitudinal": False, "lateral": False, "supportGap": False}
    )
    support_profile = copy.deepcopy(
        (
            slot_geometry.get("finiteSupportProfilesByModuleDefinitionId")
            or {}
        ).get(module_definition_id)
    )
    finite_support_gate = None
    if support_profile:
        try:
            finite_support_gate = evaluate_finite_support_gate(
                module_definition_id=module_definition_id,
                slot_definition_id=slot_definition_id,
                profile=support_profile,
                position_parameters=effective_position_parameters,
                distance_flip_dimensions=effective_distance_flips,
            )
        except FiniteSupportGateError as exc:
            raise MechanicalInterfaceContractError(
                f"FINITE_SUPPORT_PROFILE_INVALID: {exc}"
            ) from exc
        if support_profile.get("required") is True and finite_support_gate.get(
            "passed"
        ) is not True:
            footprint = finite_support_gate.get("predictedFootprint") or {}
            raise MechanicalInterfaceContractError(
                "FINITE_SUPPORT_FOOTPRINT_OUTSIDE: "
                + json.dumps(footprint, ensure_ascii=False, sort_keys=True)
            )
    policy = {
        "mode": "parameterized_datum_placement",
        "actualFixationMethod": "not_verified",
        "directMechanicalCompatibilityClaim": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "physicalFasteningVerified": False,
        "templateId": template["templateId"],
        "finiteSupportGateRequired": bool(
            support_profile and support_profile.get("required") is True
        ),
    }
    effective_graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": None,
        "ModuleCount": 2,
        "InterModuleMateCount": 3,
        "Modules": [base_module, target_module],
        "Mates": mates,
        "BaseGraphPolicy": {
            "status": "parameterized_datum_validation_candidate",
            "caseAnchorAllowed": False,
            "prototypeTopLevelTargetPoseAllowed": False,
            "targetLeafPoseAnchorsAllowed": False,
        },
        "CaseAnchor": None,
        "TargetLeafPoseAnchors": [],
        "EditPolicy": {
            "baseModuleToken": base_token,
            "initialPlacementMode": "deterministic",
            "initialPlacementVariant": initial_placement_variant,
            "sourceGraphImmutable": True,
            "fixedModuleTokens": [base_token],
            "caseAnchoredModuleTokens": [],
            "targetLeafPoseAnchors": [],
            "fixCaseAnchorBeforeMates": False,
        },
        "ParameterizedDatumPlacementPolicy": policy,
    }
    selected_endpoint_catalog = {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "CatalogMode": "parameterized-datum-validation-selected-endpoints",
        "SourceMateFacesOnly": False,
        "ModuleCount": 2,
        "Modules": copy.deepcopy(effective_graph["Modules"]),
        "EndpointCount": 6,
        "Endpoints": [
            *[copy.deepcopy(module_endpoints[role]) for role in ("support_datum", "longitudinal_datum", "lateral_datum")],
            *[copy.deepcopy(slot_endpoints[role]) for role in ("support_datum", "longitudinal_datum", "lateral_datum")],
        ],
    }
    package = {
        "schemaVersion": VALIDATION_PACKAGE_SCHEMA,
        "status": (
            "released_pair_ready_for_explicit_revalidation"
            if released_pair
            else "ready_for_explicit_nonprototype_cad_validation"
        ),
        "moduleDefinitionId": module_definition_id,
        "slotDefinitionId": slot_definition_id,
        "targetModuleToken": target_token,
        "baseModuleToken": base_token,
        "sourceAssemblyPath": str(source_assembly_path.resolve()),
        "sourceAssemblySha256": _sha256_file(source_assembly_path),
        "baseWrapperCacheEntryPath": str(cache_entry_path.resolve()),
        "baseWrapperCacheEntrySha256": _sha256_file(cache_entry_path),
        "moduleEndpointCatalogPath": str(module_catalog_path.resolve()),
        "slotEndpointCatalogPath": str(slot_catalog_path.resolve()),
        "initialPlacementMode": "deterministic",
        "initialPlacementVariant": initial_placement_variant,
        "prototypeTopLevelTargetPoseUsed": False,
        "caseAnchorUsed": False,
        "targetLeafPoseAnchorsUsed": False,
        "readyForReleasedCadExecution": released_pair,
        "validationRequiredBeforeRelease": not released_pair,
        "physicalFasteningVerified": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "instantiatedTemplate": template,
        "alignmentDerivation": alignment_derivation,
        "positionParametersOverride": copy.deepcopy(position_parameters),
        "effectivePositionParameters": effective_position_parameters,
        "effectiveDistanceFlipDimensions": effective_distance_flips,
        "finiteSupportGate": finite_support_gate,
        "boundedRoleStationCandidate": copy.deepcopy(bounded_role_station_candidate),
        "effectiveGraph": effective_graph,
        "selectedEndpointCatalog": selected_endpoint_catalog,
        "claimBoundary": (
            "This package may be run only as an explicit candidate validation. "
            "It does not authorize normal released execution or claim physical fastening."
        ),
    }
    package["packageDigest"] = _digest(package)
    return package


def publish_parameterized_datum_pair_release(
    package_manifest: dict[str, Any],
    cad_result: dict[str, Any],
) -> dict[str, Any]:
    """Promote a candidate only after a successful save/reopen CAD run."""

    if package_manifest.get("schemaVersion") != VALIDATION_PACKAGE_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported validation package")
    artifacts = package_manifest.get("artifacts") or {}
    graph_binding = artifacts.get("effectiveGraph") or {}
    graph_path = Path(str(graph_binding.get("path") or ""))
    if not graph_path.is_file() or _sha256_file(graph_path) != graph_binding.get("sha256"):
        raise MechanicalInterfaceContractError("validation graph changed after compilation")
    if cad_result.get("success") is not True:
        raise MechanicalInterfaceContractError("CAD validation did not succeed")
    if cad_result.get("effectiveGraphSha256") != graph_binding.get("sha256"):
        raise MechanicalInterfaceContractError("CAD result is not bound to validation graph")
    graph = _read(graph_path)
    finite_support = package_manifest.get("finiteSupportGate")
    finite_support_required = bool(
        ((graph.get("ParameterizedDatumPlacementPolicy") or {}).get(
            "finiteSupportGateRequired"
        ))
    )
    if finite_support_required and (
        not isinstance(finite_support, dict)
        or finite_support.get("required") is not True
        or finite_support.get("passed") is not True
    ):
        raise MechanicalInterfaceContractError(
            "CAD validation cannot be released without the required finite-support gate"
        )
    external_repeatability = cad_result.get("externalPlacementRepeatability") or {}
    finite_repeatability_ok = not finite_support_required
    if finite_support_required:
        repeatability_path = Path(str(external_repeatability.get("path") or ""))
        finite_repeatability_ok = (
            external_repeatability.get("passed") is True
            and repeatability_path.is_file()
            and _sha256_file(repeatability_path)
            == external_repeatability.get("sha256")
            and _read(repeatability_path).get("passed") is True
            and _read(repeatability_path).get("repeatabilityKind")
            == "rigid_finite_support_pose"
        )
    placement_mode = str(
        package_manifest.get("placementMode") or "parameterized_three_plane_datum"
    )
    is_flexible_slot = placement_mode == "reviewed_flexible_calibration_slot"
    tool = cad_result.get("toolResult") or {}
    expected_mate_count = 4 if is_flexible_slot else 3
    repeatability = cad_result.get("flexibleExternalPlacementRepeatability") or {}
    repeatability_ok = not is_flexible_slot
    if is_flexible_slot:
        repeatability_path = Path(str(repeatability.get("path") or ""))
        repeatability_ok = (
            repeatability.get("passed") is True
            and repeatability_path.is_file()
            and _sha256_file(repeatability_path) == repeatability.get("sha256")
            and _read(repeatability_path).get("passed") is True
        )
        target_token = str(package_manifest.get("targetModuleToken") or "")
        target_modules = [
            row
            for row in graph.get("Modules") or []
            if str(row.get("ModuleToken") or "") == target_token
        ]
        if (
            len(target_modules) != 1
            or target_modules[0].get("SolvingState") != 1
            or target_modules[0].get("SolvingStateName")
            != "swComponentFlexibleSolving"
        ):
            raise MechanicalInterfaceContractError(
                "flexible-slot release requires the declared flexible target state"
            )
    if is_flexible_slot:
        checks = {
            "independentComponentInserted": tool.get("IndependentComponentInserted")
            is True,
            "fourOfFourMatesCreated": int(tool.get("RequestedMateCount") or 0)
            == expected_mate_count
            and int(tool.get("CreatedMateCount") or 0) == expected_mate_count,
            "saveCloseReopenPassed": tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True,
            "targetFlexibleConstraintStateAccepted": tool.get(
                "TargetConstraintStateAccepted"
            )
            is True,
            "flexibleExternalPlacementRepeatable": repeatability_ok,
            "mateSolveClean": tool.get("MateSolveClean") is True,
            "noPrototypePoseAnchor": tool.get("TargetCaseAnchored") is False
            and int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0,
            "sourceAssemblyUnchanged": cad_result.get("sourceAssemblyUnchanged")
            is True,
            "outputClosed": cad_result.get("outputClosedAfterVerification") is True,
            "targetSourceSessionClean": cad_result.get(
                "targetSourceSessionClean"
            )
            is True,
            **(
                {
                    "finiteSupportFootprintInside": True,
                    "finiteSupportExternalPlacementRepeatable": finite_repeatability_ok,
                }
                if finite_support_required
                else {}
            ),
        }
    else:
        # Preserve the historical check names and insertion order so already
        # published immutable three-mate releases remain byte-for-byte
        # reproducible when their evidence is revalidated.
        checks = {
            "independentComponentInserted": tool.get("IndependentComponentInserted")
            is True,
            "threeOfThreeMatesCreated": int(tool.get("RequestedMateCount") or 0)
            == 3
            and int(tool.get("CreatedMateCount") or 0) == 3,
            "saveCloseReopenPassed": tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True,
            "targetFullyConstrained": tool.get("TargetConstraintStateAccepted")
            is True
            and tool.get("TargetFullyConstrained") is True,
            "mateSolveClean": tool.get("MateSolveClean") is True,
            "noPrototypePoseAnchor": tool.get("TargetCaseAnchored") is False
            and int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0,
            "sourceAssemblyUnchanged": cad_result.get("sourceAssemblyUnchanged")
            is True,
            "outputClosed": cad_result.get("outputClosedAfterVerification") is True,
            "targetSourceSessionClean": cad_result.get(
                "targetSourceSessionClean"
            )
            is True,
            **(
                {
                    "finiteSupportFootprintInside": True,
                    "finiteSupportExternalPlacementRepeatable": finite_repeatability_ok,
                }
                if finite_support_required
                else {}
            ),
        }
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise MechanicalInterfaceContractError(
            "CAD validation cannot be released: " + ", ".join(failed)
        )
    output = Path(str(cad_result.get("outputAssemblyPath") or ""))
    if not output.is_file() or _sha256_file(output) != cad_result.get("outputAssemblySha256"):
        raise MechanicalInterfaceContractError("validated output assembly changed")
    result_path = output.parent / "cad-result.json"
    if not result_path.is_file() or _read(result_path) != cad_result:
        raise MechanicalInterfaceContractError("CAD result file is missing or differs")
    module_id = str(package_manifest.get("moduleDefinitionId") or "")
    slot_id = str(package_manifest.get("slotDefinitionId") or "")
    if placement_mode == "reviewed_hybrid_plane_axis_datum":
        hybrid = package_manifest.get("hybridAxisSelection") or {}
        selection_digest = str(hybrid.get("selectionDigest") or "")
        selected_axis_endpoint_id = str(
            hybrid.get("selectedAxisEndpointId") or ""
        )
        if not selection_digest or not selected_axis_endpoint_id:
            raise MechanicalInterfaceContractError(
                "hybrid validation package is missing its reviewed axis selection"
            )
        placement_evidence = {
            "placementMode": placement_mode,
            "hybridAxisSelectionDigest": selection_digest,
            "selectedAxisEndpointId": selected_axis_endpoint_id,
            "diameterCompatibility": "not_evaluated",
        }
        claim_boundary = (
            "Released only for CAD pose construction with the reviewed support plane, "
            "orientation plane and locating axis. Diameter fit, physical fastening, "
            "collision and production approval remain unverified."
        )
    elif is_flexible_slot:
        selection = package_manifest.get("flexibleSlotSelection") or {}
        selection_digest = str(selection.get("selectionDigest") or "")
        selected_axis_endpoint_id = str(
            selection.get("selectedAxisEndpointId") or ""
        )
        if not selection_digest or not selected_axis_endpoint_id:
            raise MechanicalInterfaceContractError(
                "flexible-slot package is missing reviewed selection evidence"
            )
        placement_evidence = {
            "placementMode": placement_mode,
            "flexibleSlotSelectionDigest": selection_digest,
            "selectedAxisEndpointId": selected_axis_endpoint_id,
            "longitudinalOffsetMeters": package_manifest.get(
                "positionParametersOverride", {}
            ).get("longitudinalOffsetMeters"),
            "externalPlacementRepeatability": copy.deepcopy(repeatability),
            "internalFlexibilityPreserved": True,
        }
        claim_boundary = (
            "Released only for repeatable external CAD pose construction with the "
            "reviewed support, orientation, distance and Free-slot bundle. Internal "
            "motion remains flexible; fastening, collision/B-rep and production "
            "approval remain unverified."
        )
    else:
        # Keep the original three-plane release byte-compatible with already
        # published immutable evidence.  Only the new hybrid recipe needs an
        # explicit discriminator because it cannot truthfully inherit the
        # historic three-planar-datum claim.
        placement_evidence = (
            {
                "finiteSupportGate": copy.deepcopy(finite_support),
                "externalPlacementRepeatability": copy.deepcopy(
                    external_repeatability
                ),
            }
            if finite_support_required
            else {}
        )
        claim_boundary = (
            "Released only for repeatable CAD pose construction inside the registered "
            "finite support surface using the recorded three planar datums and position "
            "parameters. Physical fastening, collision and production approval remain "
            "unverified."
            if finite_support_required
            else "Released only for CAD pose construction with the recorded three planar "
            "datums and position parameters. Physical fastening, collision and "
            "production approval remain unverified."
        )
    release_identity: list[Any] = [module_id, slot_id, graph_binding["sha256"]]
    if finite_support_required:
        # A graph hash alone cannot distinguish a single-run release from a
        # later release that carries the required dual-initial-pose witness.
        # Bind the stronger evidence into the immutable release identity.
        release_identity.extend(
            [
                external_repeatability.get("sha256"),
                _digest(finite_support),
            ]
        )
    release_id = "datum-placement-" + _digest(release_identity)[:16]
    core = {
        "schemaVersion": PAIR_RELEASE_SCHEMA,
        "releaseId": release_id,
        "moduleDefinitionId": module_id,
        "slotDefinitionId": slot_id,
        "moduleContractId": package_manifest["instantiatedTemplate"]["moduleContractId"],
        "slotContractId": package_manifest["instantiatedTemplate"]["slotContractId"],
        "templateId": package_manifest["instantiatedTemplate"]["templateId"],
        "nonPrototypeCadValidated": True,
        "prototypeTopLevelTargetPoseUsed": False,
        "caseAnchorUsed": False,
        "targetLeafPoseAnchorsUsed": False,
        "physicalFasteningVerified": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        **placement_evidence,
        "checks": checks,
        "durationSeconds": cad_result.get("durationSeconds"),
        "effectiveGraphPath": str(graph_path.resolve()),
        "effectiveGraphSha256": graph_binding["sha256"],
        "cadResultPath": str(result_path.resolve()),
        "cadResultSha256": _sha256_file(result_path),
        "outputAssemblyPath": str(output.resolve()),
        "outputAssemblySha256": _sha256_file(output),
        "claimBoundary": claim_boundary,
    }
    core["releaseDigest"] = _digest(core)
    return core
