"""Compile the final Project01 LM00+ZZ00 static context-snapshot insertion."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any


TARGET = "LM00_ZZ00_STATIC"
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def build_project01_final_static_snapshot_work_packet(
    prior_effective_graph: dict[str, Any],
    snapshot_path: Path,
    snapshot_run: dict[str, Any],
    lm_comparison: dict[str, Any],
    zz_comparison: dict[str, Any],
) -> dict[str, Any]:
    snapshot = snapshot_path.resolve()
    if not snapshot.is_file():
        raise FileNotFoundError(snapshot)
    if snapshot_run.get("success") is not True:
        raise ValueError("LM00+ZZ00 static context subset has not passed save/reopen verification.")
    if lm_comparison.get("stable") is not True or zz_comparison.get("stable") is not True:
        raise ValueError("LM00+ZZ00 internal subtree pose comparison has not passed.")
    graph = copy.deepcopy(prior_effective_graph)
    prior_tokens = [str(row.get("ModuleToken")) for row in graph.get("Modules") or []]
    if len(prior_tokens) != 8 or len(set(prior_tokens)) != 8:
        raise ValueError("Expected the eight-module Project01 context before the final stage.")
    graph["Modules"].append(
        {
            "ModuleToken": TARGET,
            "Name": f"{snapshot.stem}-1",
            "Path": str(snapshot),
            "HierarchyPath": f"{snapshot.stem}-1",
            "SourceTransform": IDENTITY,
            "IsSuppressed": False,
            "SuppressionState": 3,
            "SuppressionStateName": "swComponentFullyResolved",
            "VisibilityState": 1,
            "ReferencedConfiguration": None,
            "SolvingState": 0,
            "SolvingStateName": "swComponentRigidSolving",
        }
    )
    graph["ModuleCount"] = len(graph["Modules"])
    graph["Mates"] = []
    graph["InterModuleMateCount"] = 0
    graph["MateBundles"] = []
    graph["MateBundleCount"] = 0
    policy = graph.setdefault("EditPolicy", {})
    policy["baseModuleToken"] = prior_tokens[0]
    policy["initialPlacementMode"] = "source_pose"
    policy["fixedModuleTokens"] = prior_tokens
    policy["caseAnchoredModuleTokens"] = [TARGET]
    policy["targetLeafPoseAnchors"] = []
    policy["fixCaseAnchorBeforeMates"] = True
    policy["sourceGraphImmutable"] = True
    audit = graph.setdefault("SemanticAssemblyPlanAudit", {})
    audit["executionMode"] = "incremental-insert-parent-context-static-snapshot"
    audit["finalStaticSnapshot"] = {
        "schemaVersion": "project01-final-static-snapshot-audit/v1",
        "targetModuleToken": TARGET,
        "snapshotAssemblyPath": str(snapshot),
        "snapshotAssemblySha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "sourceTopLevelComponentCount": 2,
        "representedFunctionalModuleTokens": ["LM00", "ZZ00"],
        "lmSubtreeComparedCount": int(lm_comparison["comparedCount"]),
        "zzSubtreeComparedCount": int(zz_comparison["comparedCount"]),
        "maximumInternalTransformElementError": max(
            float(lm_comparison["maximumTransformElementError"]),
            float(zz_comparison["maximumTransformElementError"]),
        ),
        "staticGeometryPreserved": True,
        "originalParentAssemblyCopied": False,
        "independentMotionGraphReconstructed": False,
        "productionReady": False,
    }
    summary = {
        "schemaVersion": "project01-final-static-snapshot-work-packet/v1",
        "projectId": "project01",
        "stepId": "step-07-add-LM00-ZZ00-static-context",
        "baseModules": prior_tokens,
        "targetModule": TARGET,
        "representedFunctionalModules": ["LM00", "ZZ00"],
        "finalFunctionalObjectCount": 10,
        "cadTopLevelObjectCount": 9,
        "safeToStartStaticCad": True,
        "staticDemoOnly": True,
        "productionReady": False,
        "knownLimits": [
            "LM00 and ZZ00 are inserted as one audited static parent-context snapshot.",
            "The static checkpoint preserves geometry but not independent kinematic behavior.",
            "The failed real-mate flexible-state experiments remain authoritative dynamic blockers.",
        ],
    }
    return {"effectiveGraph": graph, "summary": summary}
