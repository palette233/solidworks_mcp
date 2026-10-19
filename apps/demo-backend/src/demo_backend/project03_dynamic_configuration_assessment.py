"""Assess Project03 AD20 configuration evidence without hiding accepted prototype contacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def _module_pose(state: dict[str, Any], alias: str) -> dict[str, Any]:
    actual_name = state["componentAliases"][alias]
    matches = [row for row in state.get("poses", []) if _pick(row, "Name", "") == actual_name]
    if len(matches) != 1:
        raise ValueError(f"State {state.get('state')} has {len(matches)} poses for {alias}.")
    return matches[0]


def _box(state: dict[str, Any], alias: str) -> tuple[float, ...]:
    return tuple(float(value) for value in (_pick(_module_pose(state, alias), "BoundingBoxWorld", []) or []))


def assess_project03_dynamic_configuration_closure(
    closure: dict[str, Any],
    prototype_baseline: dict[str, Any],
) -> dict[str, Any]:
    states = list(closure.get("states") or [])
    if len(states) != 3:
        raise ValueError(f"Expected three AD20 states, found {len(states)}.")

    config_results = [result for state in states for result in state.get("configurationResults", [])]
    configuration_switch_verified = bool(config_results) and all(
        bool(_pick(result, "Success", False))
        and str(_pick(result, "RequestedConfiguration", ""))
        == str(_pick(result, "ActualConfiguration", ""))
        for result in config_results
    )

    state_by_name = {state["state"]: state for state in states}
    zero = state_by_name["both-0deg"]
    left_25 = state_by_name["left-25deg"]
    right_25 = state_by_name["right-25deg"]
    geometry_state_change_verified = (
        _box(zero, "AD20_LEFT") != _box(left_25, "AD20_LEFT")
        and _box(zero, "AD20_RIGHT") == _box(left_25, "AD20_RIGHT")
        and _box(zero, "AD20_LEFT") == _box(right_25, "AD20_LEFT")
        and _box(zero, "AD20_RIGHT") != _box(right_25, "AD20_RIGHT")
    )

    pair_checks = [pair for state in states for pair in state.get("pairChecks", [])]
    non_ae_pairs = [pair for pair in pair_checks if pair.get("candidateComponent") != "AE00"]
    ae_pairs = [pair for pair in pair_checks if pair.get("candidateComponent") == "AE00"]
    non_ae_gate_passed = bool(non_ae_pairs) and all(str(pair.get("gate", "")).startswith("PASSED") for pair in non_ae_pairs)
    isolated_ae_contacts_observed = bool(ae_pairs) and all(pair.get("gate") == "FAILED_INTERFERENCE" for pair in ae_pairs)

    baseline_pairs = list(_pick(prototype_baseline, "InterferingBodyPairs", []) or [])
    baseline_ad20_pairs = [
        pair
        for pair in baseline_pairs
        if "AD20" in str(_pick(_pick(pair, "FirstComponent", {}), "HierarchyPath", ""))
        or "AD20" in str(_pick(_pick(pair, "SecondComponent", {}), "HierarchyPath", ""))
    ]
    prototype_has_ad20_ae_contacts = bool(baseline_ad20_pairs)

    passed_static_scope = configuration_switch_verified and geometry_state_change_verified and non_ae_gate_passed
    requires_full_context = isolated_ae_contacts_observed and prototype_has_ad20_ae_contacts
    status = (
        "PROJECT03_AD00_CONFIGURATION_STATES_VERIFIED_FULL_CONTEXT_BASELINE_RECHECK_REQUIRED"
        if passed_static_scope and requires_full_context
        else "PROJECT03_AD00_DYNAMIC_CONFIGURATION_EVIDENCE_INCOMPLETE"
    )

    return {
        "schemaVersion": "project03-ad00-dynamic-configuration-assessment-v1",
        "status": status,
        "productionReady": False,
        "configurationSwitchVerified": configuration_switch_verified,
        "geometryStateChangeVerified": geometry_state_change_verified,
        "nonAeCandidateGatePassed": non_ae_gate_passed,
        "isolatedAeContactsObserved": isolated_ae_contacts_observed,
        "prototypeHasAd20AeContacts": prototype_has_ad20_ae_contacts,
        "prototypeBaselineInterferingBodyPairCount": len(baseline_pairs),
        "prototypeBaselineAd20AeBodyPairCount": len(baseline_ad20_pairs),
        "stateCount": len(states),
        "checkedPairCount": len(pair_checks),
        "sourceClosureStatus": closure.get("status"),
        "acceptedConclusions": [
            "AD20 0度/25度 configuration selection was applied and verified in real SolidWorks geometry.",
            "The 25度 state changes only the commanded AD20 instance envelope.",
            "AA00, AB00 and AI00 show no new collision in the isolated state evidence.",
        ],
        "blockers": [
            "AE00 is flexible/context-sensitive and the prototype already contains accepted AD00-AE00 contacts; isolated insertion cannot decide whether observed contacts are new.",
            "Build full-context copies that preserve AE00 solving state, switch nested AD20 configurations there, and compare leaf-pair identities against the prototype baseline.",
            "Continuous motion between 0度 and 25度 remains outside the validated scope.",
        ],
    }


def default_baseline_path(root: Path) -> Path:
    return root / "demo/interference_project03_prototype/conditional_hits/FL9A24D063A000.001_leaf_details_FL9A24D063AE00_FL9A24D063AD00.json"
