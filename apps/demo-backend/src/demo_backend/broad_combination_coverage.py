"""Authoritative all-model x all-base coverage for the six-role milestone.

The existing readiness report answers whether each *role* has some usable
evidence.  This report answers the stricter question needed by the current
mainline: for every catalogued module model and every catalogued base, what
exactly is still required before that pair can be executed without inheriting
the source prototype pose?

It deliberately does not infer geometry.  Released native relations,
parameterized-datum queue rows and explicitly listed mixed-topology gaps are
kept as different states so a representative success cannot be mistaken for
all-model coverage.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "broad-cross-project-combination-coverage/v1"
READINESS_SCHEMA = "short-term-cross-project-scope-readiness/v2"
QUEUE_SCHEMA = "parameterized-datum-validation-queue/v1"

ROLE_BY_GROUP = {
    "transport": "Transport",
    "scanner": "Scanner",
    "calibration": "Calibration",
    "cleaning_weighing": "CleaningWeighing",
    "waste_handling": "WasteCup",
}

# These are not generic three-plane datum modules.  Recording the required
# topology here is safer than relabelling a cylinder/slot as a plane merely to
# make the generic fallback accept it.
MIXED_TOPOLOGY_GAPS = {
    "project01::SS00": "mixed_support_two_axis_recipe_required",
    "project03::AE00": "mixed_support_two_axis_recipe_required",
    "project01::BD00": "mixed_support_two_axis_recipe_required",
    "project03::AH00": "mixed_support_two_axis_recipe_required",
    "project05::G000": "mixed_support_orientation_slot_recipe_required",
    "project05::F000": "base_axis_endpoint_capture_required",
}

STATE_PRIORITY = {
    "native_relation_released": 0,
    "parameterized_relation_released": 1,
    "ready_for_nonprototype_cad_validation": 2,
    "direct_relation_cad_validation_required": 3,
    "explicit_position_parameters_required": 4,
    "explicit_axis_selection_required": 5,
    "explicit_axis_pair_selection_required": 6,
    "explicit_flexible_slot_selection_required": 7,
    "axis_pair_not_found_in_authoritative_catalog": 8,
    "flexible_slot_axis_not_found_in_authoritative_catalog": 9,
    "mixed_support_two_axis_recipe_required": 10,
    "mixed_support_orientation_slot_recipe_required": 11,
    "base_axis_endpoint_capture_required": 12,
    "semantic_port_capture_required": 13,
}


class BroadCombinationCoverageError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _definition_id(project_ref: str) -> str:
    value = str(project_ref or "")
    if "::" in value:
        return value
    if value.count(":") == 1:
        project, token = value.split(":", 1)
        return f"{project}::{token}"
    raise BroadCombinationCoverageError(f"invalid project module reference: {value}")


def _direct_indexes(
    catalogs: Iterable[dict[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    released: dict[tuple[str, str], dict[str, Any]] = {}
    compatible: dict[tuple[str, str], dict[str, Any]] = {}
    for catalog in catalogs:
        for row in catalog.get("compatibilityMatrix") or []:
            pair = (
                str(row.get("moduleDefinitionId") or ""),
                str(row.get("slotDefinitionId") or ""),
            )
            if not all(pair):
                continue
            if row.get("existingPairReleaseReusable") is True:
                released[pair] = copy.deepcopy(row)
            elif row.get("compatible") is True and row.get("mateInstantiationAllowed") is True:
                compatible[pair] = copy.deepcopy(row)
    return released, compatible


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _definition_from_port(
    port: dict[str, Any], known_definition_ids: set[str]
) -> str | None:
    provenances = port.get("provenance") or []
    candidates: set[str] = set()
    for provenance in provenances:
        project_id = str(
            provenance.get("portProjectId") or provenance.get("projectId") or ""
        )
        raw_token = str(provenance.get("moduleToken") or "").upper()
        if not project_id or not raw_token:
            continue
        for definition_id in known_definition_ids:
            project, token = definition_id.split("::", 1)
            if project == project_id and (
                raw_token == token.upper() or raw_token.endswith(token.upper())
            ):
                candidates.add(definition_id)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def discover_global_relation_release_pairs(
    workspace: Path,
    *,
    known_definition_ids: Iterable[str],
    base_definition_ids: Iterable[str],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Resolve exact released pairs omitted by role-specific interface catalogs.

    Some validated alternate slots, notably AH00 -> A600, live directly in the
    immutable global relation release lineage.  Reading the active global
    catalog once and authenticating release manifests avoids both hard-coding
    that pair and repeatedly loading every historical catalog snapshot.
    """

    workspace = workspace.resolve()
    catalog_path = workspace / "demo/global_assembly_catalog/v1/global_module_catalog.json"
    if not catalog_path.is_file():
        raise FileNotFoundError(catalog_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    catalog_core = {
        key: value for key, value in catalog.items() if key != "catalogDigest"
    }
    if catalog.get("catalogDigest") != _digest(catalog_core):
        raise BroadCombinationCoverageError("active global module catalog digest mismatch")

    released_templates: dict[str, list[dict[str, Any]]] = {}
    release_catalog_paths: dict[str, list[Path]] = {}
    release_root = workspace / "demo/global_assembly_catalog/releases"
    safety_path = (
        workspace
        / "demo/cross_project_substitution/parameterized-datum-placement-v1/"
        "release-safety-registry.json"
    )
    revoked_global_release_ids: set[str] = set()
    if safety_path.is_file():
        safety = json.loads(safety_path.read_text(encoding="utf-8-sig"))
        if safety.get("schemaVersion") != "parameterized-datum-release-safety-registry/v1":
            raise BroadCombinationCoverageError(
                "unsupported datum release safety registry"
            )
        revoked_global_release_ids = {
            str(release_id)
            for row in safety.get("revokedReleases") or []
            for release_id in row.get("globalRelationReleaseIds") or []
            if str(release_id)
        }
    for path in sorted(release_root.glob("*/release-manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        if not (
            manifest.get("schemaVersion") == "global-relation-catalog-release/v1"
            and manifest.get("status") == "released_for_demo_relation_execution"
            and any(
                row.get("passed") is True
                and row.get("drivingInitialPoseIndependent") is True
                for row in manifest.get("validationEvidence") or []
            )
        ):
            continue
        if str(manifest.get("releaseId") or "") in revoked_global_release_ids:
            continue
        core = {key: value for key, value in manifest.items() if key != "releaseDigest"}
        if manifest.get("releaseDigest") != _digest(core):
            raise BroadCombinationCoverageError(
                f"global relation release digest mismatch: {path}"
            )
        for validation in manifest.get("validationEvidence") or []:
            evidence_path = Path(str(validation.get("path") or ""))
            if not evidence_path.is_absolute():
                evidence_path = workspace / evidence_path
            if (
                validation.get("passed") is True
                and validation.get("fileSha256")
                and (
                    not evidence_path.is_file()
                    or _sha256_file(evidence_path) != validation.get("fileSha256")
                )
            ):
                raise BroadCombinationCoverageError(
                    f"global relation CAD evidence drifted: {evidence_path}"
                )
        evidence = {
            "releaseId": manifest.get("releaseId"),
            "releaseDigest": manifest.get("releaseDigest"),
            "manifestPath": str(path.resolve()),
        }
        released_catalog_path = Path(str(manifest.get("releasedCatalogPath") or ""))
        if not released_catalog_path.is_absolute():
            relative = str(manifest.get("releasedCatalogRelativePath") or "")
            released_catalog_path = workspace / relative
        if not released_catalog_path.is_file():
            raise BroadCombinationCoverageError(
                f"released global catalog is missing: {released_catalog_path}"
            )
        expected_catalog_sha = str(manifest.get("releasedCatalogFileSha256") or "")
        if expected_catalog_sha and _sha256_file(released_catalog_path) != expected_catalog_sha:
            raise BroadCombinationCoverageError(
                f"released global catalog drifted: {released_catalog_path}"
            )
        for template_id in manifest.get("derivedTemplateIds") or []:
            key = str(template_id)
            released_templates.setdefault(key, []).append(evidence)
            release_catalog_paths.setdefault(key, []).append(released_catalog_path)

    known = set(str(value) for value in known_definition_ids)
    bases = set(str(value) for value in base_definition_ids)
    pair_releases: dict[tuple[str, str], dict[str, Any]] = {}

    def admit_template(
        template: dict[str, Any], source_catalog: dict[str, Any], evidence_rows: list[dict[str, Any]]
    ) -> bool:
        template_id = str(template.get("globalTemplateId") or "")
        port_index = {
            str(row.get("globalPortId") or ""): row
            for row in source_catalog.get("semanticPorts") or []
            if row.get("globalPortId")
        }
        port_ids = {
            str(value)
            for key in ("candidatePortIdsA", "candidatePortIdsB")
            for value in template.get(key) or []
        }
        definitions = {
            definition
            for port_id in port_ids
            if (port := port_index.get(port_id)) is not None
            if (definition := _definition_from_port(port, known)) is not None
        }
        base_matches = definitions & bases
        module_matches = definitions - bases
        if len(base_matches) != 1 or len(module_matches) != 1:
            return False
        pair = (next(iter(module_matches)), next(iter(base_matches)))
        prior = pair_releases.get(pair)
        if prior is None:
            pair_releases[pair] = {
                "source": "immutable_global_relation_release",
                "globalTemplateId": template_id,
                "legacyTemplateId": template.get("legacyTemplateId"),
                "releaseEvidence": copy.deepcopy(evidence_rows),
            }
        else:
            identities = {
                str(row.get("releaseId") or "")
                for row in prior.get("releaseEvidence") or []
            }
            prior["releaseEvidence"].extend(
                copy.deepcopy(row)
                for row in evidence_rows
                if str(row.get("releaseId") or "") not in identities
            )
        return True

    active_templates = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
        if row.get("globalTemplateId")
    }
    unresolved: set[str] = set()
    for template_id, evidence_rows in released_templates.items():
        template = active_templates.get(template_id)
        if template is None or not admit_template(template, catalog, evidence_rows):
            unresolved.add(template_id)

    catalog_cache: dict[Path, dict[str, Any]] = {}
    for template_id in sorted(unresolved):
        resolved = False
        for source_path in release_catalog_paths.get(template_id) or []:
            source_catalog = catalog_cache.get(source_path)
            if source_catalog is None:
                source_catalog = json.loads(source_path.read_text(encoding="utf-8-sig"))
                catalog_cache[source_path] = source_catalog
            template = next(
                (
                    row
                    for row in source_catalog.get("connectionTemplates") or []
                    if row.get("globalTemplateId") == template_id
                ),
                None,
            )
            if template is not None and admit_template(
                template, source_catalog, released_templates[template_id]
            ):
                resolved = True
                break
        # A release can legitimately describe a template outside the six-role
        # scope.  It remains ignored rather than being coerced into a pair.
        if not resolved:
            continue
    return pair_releases


def _queue_index(queue: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in queue.get("pairs") or []:
        pair = (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in rows:
            raise BroadCombinationCoverageError(
                f"parameterized queue contains an empty or duplicate pair: {pair}"
            )
        rows[pair] = copy.deepcopy(row)
    return rows


def _state_from_queue(row: dict[str, Any]) -> str:
    state = str(row.get("state") or "")
    if state == "released":
        return "parameterized_relation_released"
    if state in {
        "ready_for_nonprototype_cad_validation",
        "explicit_position_parameters_required",
        "explicit_axis_selection_required",
        "explicit_axis_pair_selection_required",
        "explicit_flexible_slot_selection_required",
        "axis_pair_not_found_in_authoritative_catalog",
        "flexible_slot_axis_not_found_in_authoritative_catalog",
    }:
        return state
    if state == "blocked_before_cad":
        return "semantic_port_capture_required"
    raise BroadCombinationCoverageError(f"unsupported queue state: {state}")


def build_broad_combination_coverage(
    *,
    readiness: dict[str, Any],
    parameterized_queue: dict[str, Any],
    direct_catalogs: Iterable[dict[str, Any]],
    released_relation_pairs: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if readiness.get("schemaVersion") != READINESS_SCHEMA:
        raise BroadCombinationCoverageError("unsupported six-role readiness schema")
    if parameterized_queue.get("schemaVersion") != QUEUE_SCHEMA:
        raise BroadCombinationCoverageError("unsupported parameterized queue schema")

    base_group = next(
        (row for row in readiness.get("groups") or [] if row.get("groupId") == "base_environment"),
        None,
    )
    if not base_group:
        raise BroadCombinationCoverageError("base group is missing")
    bases = sorted(_definition_id(row) for row in base_group.get("projectModuleRefs") or [])
    if len(bases) != 4 or len(set(bases)) != len(bases):
        raise BroadCombinationCoverageError("expected four unique base contexts")

    released_direct, compatible_direct = _direct_indexes(direct_catalogs)
    released_global = released_relation_pairs or {}
    queue_rows = _queue_index(parameterized_queue)
    pair_rows: list[dict[str, Any]] = []
    role_summaries: list[dict[str, Any]] = []

    for group in readiness.get("groups") or []:
        group_id = str(group.get("groupId") or "")
        if group_id not in ROLE_BY_GROUP:
            continue
        role = ROLE_BY_GROUP[group_id]
        modules = sorted(
            _definition_id(row) for row in group.get("projectModuleRefs") or []
        )
        start = len(pair_rows)
        for module_id in modules:
            for base_id in bases:
                pair = (module_id, base_id)
                global_release = released_global.get(pair)
                direct = released_direct.get(pair)
                queued = queue_rows.get(pair)
                compatible = compatible_direct.get(pair)
                evidence: dict[str, Any] = {}
                if direct is not None:
                    state = "native_relation_released"
                    evidence = {
                        "source": "released_direct_interface_catalog",
                        "releaseId": (direct.get("pairReleaseEvidence") or {}).get("releaseId"),
                        "releaseDigest": (direct.get("pairReleaseEvidence") or {}).get("releaseDigest"),
                        "interfaceFamily": direct.get("interfaceFamily"),
                    }
                elif (
                    queued is not None
                    and queued.get("state") == "released"
                    and queued.get("releaseSource")
                    != "immutable_global_relation_release"
                ):
                    state = "parameterized_relation_released"
                    evidence = {
                        "source": "parameterized_datum_validation_queue",
                        "queueDigest": parameterized_queue.get("queueDigest"),
                        "candidateKind": queued.get("candidateKind"),
                        "nextAction": queued.get("nextAction"),
                    }
                elif global_release is not None:
                    state = "native_relation_released"
                    evidence = copy.deepcopy(global_release)
                elif queued is not None and queued.get("state") == "released":
                    state = "parameterized_relation_released"
                    evidence = {
                        "source": "parameterized_datum_validation_queue",
                        "queueDigest": parameterized_queue.get("queueDigest"),
                        "candidateKind": queued.get("candidateKind"),
                        "nextAction": queued.get("nextAction"),
                    }
                elif queued is not None:
                    state = _state_from_queue(queued)
                    evidence = {
                        "source": "parameterized_datum_validation_queue",
                        "queueDigest": parameterized_queue.get("queueDigest"),
                        "candidateKind": queued.get("candidateKind"),
                        "nextAction": queued.get("nextAction"),
                    }
                elif compatible is not None:
                    state = "direct_relation_cad_validation_required"
                    evidence = {
                        "source": "compatible_direct_interface_contract",
                        "matchId": compatible.get("matchId"),
                        "interfaceFamily": compatible.get("interfaceFamily"),
                    }
                else:
                    state = MIXED_TOPOLOGY_GAPS.get(
                        module_id, "semantic_port_capture_required"
                    )
                    evidence = {
                        "source": "explicit_uncovered_topology_audit",
                        "reason": state,
                    }
                pair_rows.append(
                    {
                        "role": role,
                        "groupId": group_id,
                        "moduleDefinitionId": module_id,
                        "baseDefinitionId": base_id,
                        "crossProject": module_id.split("::", 1)[0]
                        != base_id.split("::", 1)[0],
                        "state": state,
                        "cadLaunchAllowed": state
                        in {"native_relation_released", "parameterized_relation_released"},
                        "prototypeTopLevelPoseAllowed": False,
                        "evidence": evidence,
                    }
                )
        role_rows = pair_rows[start:]
        counts = Counter(str(row["state"]) for row in role_rows)
        role_summaries.append(
            {
                "role": role,
                "groupId": group_id,
                "moduleCount": len(modules),
                "baseCount": len(bases),
                "expectedPairCount": len(modules) * len(bases),
                "stateCounts": dict(sorted(counts.items())),
                "releasedExecutionCount": sum(
                    counts[state]
                    for state in (
                        "native_relation_released",
                        "parameterized_relation_released",
                    )
                ),
                "cadValidationReadyCount": counts[
                    "ready_for_nonprototype_cad_validation"
                ]
                + counts["direct_relation_cad_validation_required"],
                "engineeringDecisionRequiredCount": counts[
                    "explicit_position_parameters_required"
                ]
                + counts["explicit_axis_selection_required"]
                + counts["explicit_axis_pair_selection_required"]
                + counts["explicit_flexible_slot_selection_required"],
                "incompatibleOrAlternateStrategyRequiredCount": counts[
                    "axis_pair_not_found_in_authoritative_catalog"
                ]
                + counts[
                    "flexible_slot_axis_not_found_in_authoritative_catalog"
                ],
                "semanticImplementationRequiredCount": sum(
                    counts[state]
                    for state in (
                        "mixed_support_two_axis_recipe_required",
                        "mixed_support_orientation_slot_recipe_required",
                        "base_axis_endpoint_capture_required",
                        "semantic_port_capture_required",
                    )
                ),
            }
        )

    pair_rows.sort(
        key=lambda row: (
            row["groupId"],
            STATE_PRIORITY[row["state"]],
            row["moduleDefinitionId"],
            row["baseDefinitionId"],
        )
    )
    state_counts = Counter(str(row["state"]) for row in pair_rows)
    core = {
        "schemaVersion": SCHEMA,
        "baseDefinitionIds": bases,
        "roleSummaries": role_summaries,
        "pairs": pair_rows,
        "summary": {
            "movingModuleCount": sum(row["moduleCount"] for row in role_summaries),
            "baseCount": len(bases),
            "expectedPairCount": sum(row["expectedPairCount"] for row in role_summaries),
            "releasedExecutionCount": sum(row["cadLaunchAllowed"] for row in pair_rows),
            "cadValidationReadyCount": sum(
                row["state"]
                in {
                    "ready_for_nonprototype_cad_validation",
                    "direct_relation_cad_validation_required",
                }
                for row in pair_rows
            ),
            "engineeringDecisionRequiredCount": sum(
                row["state"]
                in {
                    "explicit_position_parameters_required",
                    "explicit_axis_selection_required",
                    "explicit_axis_pair_selection_required",
                    "explicit_flexible_slot_selection_required",
                }
                for row in pair_rows
            ),
            "incompatibleOrAlternateStrategyRequiredCount": sum(
                row["state"] == "axis_pair_not_found_in_authoritative_catalog"
                or row["state"]
                == "flexible_slot_axis_not_found_in_authoritative_catalog"
                for row in pair_rows
            ),
            "semanticImplementationRequiredCount": sum(
                row["state"]
                in {
                    "mixed_support_two_axis_recipe_required",
                    "mixed_support_orientation_slot_recipe_required",
                    "base_axis_endpoint_capture_required",
                    "semantic_port_capture_required",
                }
                for row in pair_rows
            ),
            "stateCounts": dict(sorted(state_counts.items())),
        },
        "claimBoundary": {
            "statement": (
                "This matrix proves planning coverage only. CAD launch is allowed solely for "
                "exact released pairs; CAD-ready and decision-required rows are not releases."
            ),
            "collisionOrBrep": "not_part_of_current_gate",
            "actualFastening": "not_inferred_for_parameterized_rows",
            "prototypeTopLevelPose": "forbidden_by_default",
        },
    }
    return {**core, "coverageDigest": _digest(core)}


def validate_broad_combination_coverage(report: dict[str, Any]) -> None:
    if report.get("schemaVersion") != SCHEMA:
        raise BroadCombinationCoverageError("unsupported coverage schema")
    core = {key: value for key, value in report.items() if key != "coverageDigest"}
    if report.get("coverageDigest") != _digest(core):
        raise BroadCombinationCoverageError("coverage digest mismatch")
    summary = report.get("summary") or {}
    pairs = report.get("pairs") or []
    if int(summary.get("expectedPairCount", -1)) != len(pairs):
        raise BroadCombinationCoverageError("pair cardinality mismatch")
    identities = {
        (row.get("moduleDefinitionId"), row.get("baseDefinitionId")) for row in pairs
    }
    if len(identities) != len(pairs):
        raise BroadCombinationCoverageError("duplicate exact pair")
    if any(row.get("state") not in STATE_PRIORITY for row in pairs):
        raise BroadCombinationCoverageError("unknown pair state")
    if any(
        row.get("cadLaunchAllowed") is True
        and row.get("state")
        not in {"native_relation_released", "parameterized_relation_released"}
        for row in pairs
    ):
        raise BroadCombinationCoverageError("unreleased pair permits CAD launch")
    if any(row.get("prototypeTopLevelPoseAllowed") is not False for row in pairs):
        raise BroadCombinationCoverageError("prototype top-level pose is not fail-closed")
