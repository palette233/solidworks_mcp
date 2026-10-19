"""Release gating for semantic assembly reconstruction artifacts.

CAD mate reconstruction, validate-only geometry measurements and exact solid
interference answer different questions.  This module deliberately keeps them
separate and only releases an assembly when every required gate has passed.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


def _value(payload: dict[str, Any], pascal: str, camel: str, default: Any = None) -> Any:
    return payload.get(pascal, payload.get(camel, default))


def _leaf_identity(component: dict[str, Any]) -> tuple[str, str]:
    source_name = Path(str(_value(component, "Path", "path", ""))).name.casefold()
    instance_name = str(_value(component, "Name", "name", ""))
    leaf_instance = instance_name.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return source_name, leaf_instance


def _interference_counter(result: dict[str, Any]) -> Counter[tuple[tuple[str, str], tuple[str, str]]]:
    body_pairs = _value(result, "InterferingBodyPairs", "interferingBodyPairs", []) or []
    identities = []
    for item in body_pairs:
        first = _leaf_identity(_value(item, "FirstComponent", "firstComponent", {}) or {})
        second = _leaf_identity(_value(item, "SecondComponent", "secondComponent", {}) or {})
        identities.append(tuple(sorted((first, second))))
    return Counter(identities)


def compare_interference_pair_to_baseline(
    candidate: dict[str, Any], baseline: dict[str, Any]
) -> dict[str, Any]:
    """Compare exact leaf interference as a multiset of stable leaf identities.

    Hierarchy paths change when modules are inserted into a new assembly, so they
    are intentionally not used as identity.  Source file name plus terminal leaf
    instance name preserves repeated instances while tolerating a different root.
    """

    current = _interference_counter(candidate)
    accepted = _interference_counter(baseline)
    common = current & accepted
    new = current - accepted
    missing = accepted - current

    def serialize(counter: Counter) -> list[dict[str, Any]]:
        rows = []
        for identity, count in sorted(counter.items()):
            rows.append(
                {
                    "first": {"sourceFile": identity[0][0], "leafInstance": identity[0][1]},
                    "second": {"sourceFile": identity[1][0], "leafInstance": identity[1][1]},
                    "count": count,
                }
            )
        return rows

    return {
        "schemaVersion": "semantic-assembly-interference-baseline-comparison/v1",
        "candidateInterferenceCount": sum(current.values()),
        "baselineInterferenceCount": sum(accepted.values()),
        "acceptedBaselineMatchCount": sum(common.values()),
        "newInterferenceCount": sum(new.values()),
        "missingBaselineInterferenceCount": sum(missing.values()),
        "passesNoNewInterferenceGate": not new,
        "newInterferenceSignatures": serialize(new),
        "missingBaselineInterferenceSignatures": serialize(missing),
    }


def build_semantic_assembly_release_gate(
    reconstruction: dict[str, Any],
    interference: dict[str, Any],
    baseline_comparisons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # CLI run artifacts wrap the raw SolidWorks result in ``toolResult`` while
    # the HTTP workbench stores it directly.  Accept both without weakening the
    # gate: the wrapper success and the CAD success must both be true.
    raw_reconstruction = reconstruction.get("toolResult")
    if not isinstance(raw_reconstruction, dict):
        raw_reconstruction = reconstruction
    validation_results = _value(raw_reconstruction, "ValidationResults", "validationResults", []) or []
    validation_passed = all(bool(_value(item, "Passed", "passed", False)) for item in validation_results)
    wrapper_passed = bool(_value(reconstruction, "Success", "success", True))
    reconstruction_passed = wrapper_passed and bool(
        _value(raw_reconstruction, "Success", "success", False)
    )
    comparisons = baseline_comparisons or []
    conditional_pairs = interference.get("pairs")
    if isinstance(conditional_pairs, list) and "requestedPairCount" in interference:
        # Conditional leaf-BRep batches already carry a per-pair acceptance
        # decision (zero interference or no new interference over a named
        # prototype baseline).  Consume that durable decision directly instead
        # of forcing the batch into the older all-pairs report schema.
        exact_pair_count = int(interference.get("requestedPairCount") or 0)
        completed_pair_count = int(interference.get("completedPairCount") or 0)
        incomplete_count = max(0, exact_pair_count - completed_pair_count)
        kernel_failure_count = sum(int(item.get("failedBodyPairCount") or 0) for item in conditional_pairs)
        interfering_rows = [item for item in conditional_pairs if item.get("hasInterference") is True]
        interfering_pair_count = len(interfering_rows)
        interference_complete = (
            completed_pair_count == exact_pair_count
            and incomplete_count == 0
            and kernel_failure_count == 0
            and all(item.get("exactCheckComplete") is True for item in conditional_pairs)
        )
        baseline_coverage_complete = all(
            item.get("acceptance", {}).get("policy") != "noNewInterferenceOverAcceptedBaseline"
            or bool(item.get("acceptance", {}).get("baselinePath"))
            for item in interfering_rows
        )
        new_interference_count = sum(
            len(item.get("acceptance", {}).get("addedInterferingPairs") or [])
            for item in conditional_pairs
        )
        baseline_accepted_count = sum(
            int(item.get("interferingBodyPairCount") or 0)
            for item in conditional_pairs
            if item.get("acceptance", {}).get("policy") == "noNewInterferenceOverAcceptedBaseline"
            and item.get("acceptance", {}).get("accepted") is True
        )
        zero_unaccepted_interference = (
            interference_complete
            and baseline_coverage_complete
            and new_interference_count == 0
            and all(item.get("acceptance", {}).get("accepted") is True for item in conditional_pairs)
        )
        interfering_module_pairs = [item.get("pair") for item in interfering_rows]
        component_count = len(
            {
                module
                for item in conditional_pairs
                for module in (item.get("pair") or [])
                if module
            }
        )
        all_pair_count = exact_pair_count
        aabb_proven_pair_count = 0
    else:
        exact_pair_count = int(interference.get("exactCandidatePairCount") or 0)
        completed_pair_count = int(interference.get("completedExactPairCount") or 0)
        incomplete_count = int(interference.get("incompleteExactPairCount") or 0)
        kernel_failure_count = int(interference.get("kernelFailurePairCount") or 0)
        interfering_pair_count = int(interference.get("interferingModulePairCount") or 0)
        interference_complete = (
            interference.get("status") in {"PASSED_ZERO_INTERFERENCE", "FAILED_INTERFERENCE_OR_INCOMPLETE"}
            and completed_pair_count == exact_pair_count
            and incomplete_count == 0
            and kernel_failure_count == 0
        )
        baseline_coverage_complete = (
            interfering_pair_count == 0
            or len(comparisons) == interfering_pair_count
        )
        new_interference_count = sum(int(item.get("newInterferenceCount") or 0) for item in comparisons)
        baseline_accepted_count = sum(
            int(item.get("acceptedBaselineMatchCount") or 0) for item in comparisons
        )
        zero_unaccepted_interference = (
            interference_complete
            and baseline_coverage_complete
            and new_interference_count == 0
            and (
                interfering_pair_count == 0
                or all(bool(item.get("passesNoNewInterferenceGate")) for item in comparisons)
            )
        )
        interfering_module_pairs = interference.get("interferingModulePairs") or []
        component_count = int(interference.get("componentCount") or 0)
        all_pair_count = int(interference.get("allTopLevelPairCount") or 0)
        aabb_proven_pair_count = int(interference.get("aabbProvenPairCount") or 0)

    blocking_issues: list[str] = []
    if not reconstruction_passed:
        blocking_issues.append("CAD配合重建、保存重开或组件语义复核未通过。")
    if not validation_passed:
        blocking_issues.append("至少一条validate_only工艺关系的实测值超出容差或端点恢复失败。")
    if not interference_complete:
        blocking_issues.append("实体干涉精检未完整结束，或SolidWorks几何内核检查失败。")
    elif not baseline_coverage_complete:
        blocking_issues.append(
            f"检测到{interfering_pair_count}对实体干涉，但只有{len(comparisons)}对具有已确认原型基线。"
        )
    elif not zero_unaccepted_interference:
        blocking_issues.append(
            f"相对已确认原型基线新增{new_interference_count}组叶实体干涉。"
        )

    release_allowed = not blocking_issues
    return {
        "schemaVersion": "semantic-assembly-release-gate/v1",
        "releaseAllowed": release_allowed,
        "status": "RELEASE_ALLOWED" if release_allowed else "REJECTED_BY_HARD_GATE",
        "checks": {
            "cadReconstructionPassed": reconstruction_passed,
            "validateOnlyRelationsPassed": validation_passed,
            "validateOnlyRelationCount": len(validation_results),
            "exactInterferenceCheckComplete": interference_complete,
            "zeroUnacceptedInterference": zero_unaccepted_interference,
            "baselineCoverageComplete": baseline_coverage_complete,
        },
        "interferenceSummary": {
            "topLevelComponentCount": component_count,
            "allTopLevelPairCount": all_pair_count,
            "aabbProvenPairCount": aabb_proven_pair_count,
            "exactCandidatePairCount": exact_pair_count,
            "completedExactPairCount": completed_pair_count,
            "interferingModulePairCount": interfering_pair_count,
            "interferingModulePairs": interfering_module_pairs,
            "baselineComparisonCount": len(comparisons),
            "baselineAcceptedInterferenceCount": baseline_accepted_count,
            "newInterferenceCount": new_interference_count,
        },
        "blockingIssues": blocking_issues,
    }
