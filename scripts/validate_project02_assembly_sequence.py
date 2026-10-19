from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def validate(preview: dict[str, Any]) -> dict[str, Any]:
    plan = preview.get("assemblySequencePlan") or {}
    stages = plan.get("stages") or []
    by_id = {str(stage.get("id")): stage for stage in stages}
    checks = [
        _check("sequence-plan-present", bool(plan)),
        _check("five-mechanical-stages", len(stages) == 5, actual=len(stages)),
        _check("a600-is-base", plan.get("baseModuleCode") == "A600", actual=plan.get("baseModuleCode")),
        _check(
            "operation-face-engineering-meaning-confirmed",
            plan.get("operationFaceConfirmed") is True,
            actual=plan.get("operationFaceConfirmed"),
        ),
        _check(
            "a600-installation-frame-resolved",
            plan.get("installationFrameResolved") is True
            and plan.get("operationSide") == "front",
            actual={
                "resolved": plan.get("installationFrameResolved"),
                "operationSide": plan.get("operationSide"),
            },
        ),
        _check(
            "current-eight-module-result-not-mislabeled",
            plan.get("currentLayoutSolverMode") == "legacy-joint-eight-module"
            and plan.get("sequentialSolverReady") is False,
            actual={
                "mode": plan.get("currentLayoutSolverMode"),
                "ready": plan.get("sequentialSolverReady"),
            },
        ),
        _check(
            "a600-coarse-installation-geometry-resolved",
            plan.get("installationGeometryResolved") is True
            and int((plan.get("installationGeometry") or {}).get("hardKeepoutRegionCount", 0)) > 0,
            actual=plan.get("installationGeometry"),
        ),
        _check(
            "a600-a800-mate-evidence-preserved",
            _evidence_available(by_id.get("02-transport-interface"), "A600与A800"),
        ),
        _check(
            "a800-prototype-interface-seed-resolved",
            plan.get("prototypeTransportInterfaceResolved") is True
            and _evidence_available(by_id.get("02-transport-interface"), "原型位姿"),
        ),
        _check(
            "a800-mate-interface-resolves-yz-and-exposes-free-x",
            plan.get("mateDerivedTransportInterfaceResolved") is True
            and ((plan.get("mateDerivedTransportInterface") or {}).get(
                "constraintInterpretation"
            ) or {}).get("fixedTranslationAxes") == ["Y", "Z"]
            and ((plan.get("mateDerivedTransportInterface") or {}).get(
                "constraintInterpretation"
            ) or {}).get("freeTranslationAxes") == ["X"]
            and _evidence_available(
                by_id.get("02-transport-interface"), "配合面已恢复Y/Z"
            ),
            actual=plan.get("mateDerivedTransportInterface"),
        ),
        _check(
            "project02-a800-prototype-case-anchor-confirmed",
            plan.get("project02PrototypeTransportReuseConfirmed") is True
            and by_id.get("02-transport-interface", {}).get("status") == "ready"
            and (by_id.get("02-transport-interface", {}).get("measured") or {}).get(
                "positioningAuthority"
            )
            == "project02PrototypeCaseAnchor",
            actual={
                "confirmed": plan.get("project02PrototypeTransportReuseConfirmed"),
                "status": by_id.get("02-transport-interface", {}).get("status"),
                "authority": (
                    by_id.get("02-transport-interface", {}).get("measured") or {}
                ).get("positioningAuthority"),
            },
        ),
        _check(
            "scanner-is-process-not-direct-mate",
            (by_id.get("03-scanner-visibility", {}).get("measured") or {}).get(
                "directScannerTransportMateExists"
            )
            is False,
        ),
        _check(
            "scanner-vendor-range-and-directed-axis-estimated",
            _evidence_available(
                by_id.get("03-scanner-visibility"), "厂商读取范围"
            )
            and _evidence_available(
                by_id.get("03-scanner-visibility"), "有向光轴"
            )
            and _evidence_available(
                by_id.get("03-scanner-visibility"), "五个条码载具"
            ),
        ),
        _check(
            "scanner-carrier-8-station-audited-for-coarse-layout",
            plan.get("scanStationInferenceResolved") is True
            and (plan.get("scanStationInference") or {}).get(
                "selectedCarrierInstance"
            )
            == "056-19475000-00_ASM_165_ASM-8"
            and (plan.get("scanStationInference") or {}).get("candidateCount")
            == 5
            and (plan.get("scanStationInference") or {}).get(
                "dynamicScanStopConfirmed"
            )
            is False,
            actual=plan.get("scanStationInference"),
        ),
        _check(
            "scanner-dynamic-stop-window-audited-but-not-mislabeled-confirmed",
            plan.get("dynamicScanWindowResolved") is True
            and (plan.get("dynamicScanWindow") or {}).get(
                "estimatedStopToleranceMeters"
            )
            == 0.005
            and (plan.get("dynamicScanWindow") or {}).get(
                "engineeringConfirmed"
            )
            is False
            and _evidence_available(
                by_id.get("03-scanner-visibility"), "动态停靠窗口两端"
            ),
            actual=plan.get("dynamicScanWindow"),
        ),
        _check(
            "service-modules-prefer-operation-face",
            _evidence_available(
                by_id.get("04-service-side-selection"),
                "功能模组优先靠近操作面",
            ),
        ),
        _check(
            "operation-side-nonconvex-capacity-estimated",
            plan.get("operationSideCapacityEstimated") is True
            and plan.get("selectedServiceSide") == "front"
            and _evidence_available(
                by_id.get("04-service-side-selection"), "非凸空间"
            ),
            actual={
                "estimated": plan.get("operationSideCapacityEstimated"),
                "selectedSide": plan.get("selectedServiceSide"),
            },
        ),
        _check(
            "parameter-robustness-audited-with-replay-routing",
            plan.get("parameterRobustnessAudited") is True
            and (plan.get("parameterRobustness") or {}).get("scenarioCount") == 12
            and ((plan.get("parameterRobustness") or {}).get("summary") or {})
            .get("dynamicScan", {})
            .get("maximumTestedLayoutPreservingValue")
            == 0.02
            and ((plan.get("parameterRobustness") or {}).get("summary") or {})
            .get("dualValveReach", {})
            .get("maximumTestedLayoutPreservingValue")
            == 0.0,
            actual=(plan.get("parameterRobustness") or {}).get("summary"),
        ),
        _check(
            "missing-engineering-inputs-explicit",
            all(
                any(fragment in item for item in plan.get("nextRequiredInputs") or [])
                for fragment in ("扫描光轴原点", "操作侧非凸可用空间", "双阀真实行程")
            ),
            actual=plan.get("nextRequiredInputs") or [],
        ),
        _check(
            "a600-geometry-no-longer-listed-as-missing",
            not any("A600整体几何" in item for item in plan.get("nextRequiredInputs") or []),
            actual=plan.get("nextRequiredInputs") or [],
        ),
        _check(
            "coarse-layout-remains-feasible",
            bool((preview.get("metrics") or {}).get("hardFeasible")),
        ),
    ]
    passed = all(item["passed"] for item in checks)
    return {
        "schemaVersion": "project02-assembly-sequence-validation/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_SEQUENCE_GATE_EXPLICITLY_BLOCKED_PENDING_MEASUREMENTS" if passed else "FAIL",
        "passedCount": sum(item["passed"] for item in checks),
        "checkCount": len(checks),
        "checks": checks,
        "interpretation": (
            "当前八模组结果可继续用于粗排与碰撞筛选；A600锚定顺序求解已建立显式门禁，"
            "需补齐列出的工程输入后才能升级为正式顺序求解。"
        ),
    }


def _check(check_id: str, passed: bool, *, actual: Any = None) -> dict[str, Any]:
    item = {"id": check_id, "passed": bool(passed)}
    if actual is not None:
        item["actual"] = actual
    return item


def _evidence_available(stage: dict[str, Any] | None, label_fragment: str) -> bool:
    return any(
        label_fragment in str(item.get("label") or "") and item.get("available") is True
        for item in (stage or {}).get("evidence") or []
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preview",
        default="demo/layout_previews/project02_preview.json",
    )
    parser.add_argument(
        "--output",
        default="demo/layout_previews/project02_assembly_sequence_validation.json",
    )
    args = parser.parse_args()
    preview_path = Path(args.preview).resolve()
    output_path = Path(args.output).resolve()
    result = validate(json.loads(preview_path.read_text(encoding="utf-8")))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "outputPath": str(output_path)}, ensure_ascii=False))
    return 0 if result["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
