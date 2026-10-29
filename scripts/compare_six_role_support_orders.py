"""Compare two completed six-role CAD orders without launching or modifying CAD."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import ntpath
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.rigid_transform_interpolation import relative_transform

TOKENS = ("AA00", "SS00", "AI00", "BD00", "AG00", "P000")
TRANSLATION_TOLERANCE = 1e-6
ROTATION_TOLERANCE = 1e-6  # radians, about 0.0000573 degrees
PARAMETER_TOLERANCE = 1e-8  # SystemValue: metres for distances, radians for angles


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def source_identity(value: object) -> str | None:
    """Windows CAD identity includes the whole absolute path, never just its leaf."""
    if not isinstance(value, str) or not value.strip() or not ntpath.isabs(value):
        return None
    return ntpath.normcase(ntpath.normpath(value.replace("/", "\\")))


def components_by_token(state: dict) -> dict:
    rows = (state.get("observed") or {}).get("components") or []
    if not isinstance(rows, list) or len(rows) != 6:
        return {}
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            return {}
        matches = [token for token in TOKENS if f"{token}.001-" in str(row.get("name") or "")]
        if len(matches) != 1 or matches[0] in result:
            return {}
        result[matches[0]] = row
    return result if set(result) == set(TOKENS) else {}


def rigid_transform_valid(values: object) -> bool:
    if not isinstance(values, list) or len(values) != 16 or not all(finite(value) for value in values):
        return False
    if abs(values[12] - 1) > 1e-9 or any(abs(value) > 1e-9 for value in values[13:]):
        return False
    axes = [values[offset:offset + 3] for offset in (0, 3, 6)]
    for i in range(3):
        for j in range(3):
            if abs(sum(a * b for a, b in zip(axes[i], axes[j])) - int(i == j)) > 1e-7:
                return False
    a, b, c = axes
    determinant = a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
    return abs(determinant - 1) <= 1e-7


def named_mates(state: dict) -> dict:
    rows = (state.get("observed") or {}).get("allTopLevelMates") or []
    if not isinstance(rows, list) or len(rows) != 15 or any(not isinstance(row, dict) or not row.get("name") for row in rows):
        return {}
    result = {row["name"]: row for row in rows}
    return result if len(result) == 15 else {}


def component_semantics_valid(row: dict) -> bool:
    """Require observed values; two absent fields are not matching evidence.

    Values follow this installation's SolidWorks.Interop.swconst enums:
    rigid/flexible solving = 0/1, under/fully constrained = 2/3. Unknown,
    over-constrained, no/invalid solution and autosolve-off are not accepted.
    """
    configuration = row.get("configuration")
    solving, constrained = row.get("solvingState"), row.get("constrainedStatus")
    return (isinstance(configuration, str) and bool(configuration.strip())
            and type(solving) is int and solving in (0, 1)
            and type(constrained) is int and constrained in (2, 3))


def compare_observations(standard_closure: dict, standard_state: dict, reordered_closure: dict, reordered_state: dict) -> dict:
    """Pure comparison: failed checks are returned, never repaired or hidden."""
    closures, states = [standard_closure, reordered_closure], [standard_state, reordered_state]
    components = [components_by_token(state) for state in states]
    orders = [closure.get("moduleSequence") or [] for closure in closures]
    checks = {
        "bothClosuresPassed": all(closure.get("schemaVersion") == "six-role-support-position-chain-closure/v1"
                                  and closure.get("success") is True
                                  and closure.get("status") == "PASSED_SIX_ROLE_SUPPORT_POSITION_CHAIN_DEMO"
                                  and bool(closure.get("checks")) and all(value is True for value in closure["checks"].values()) for closure in closures),
        "bothReadOnlyObservationsPassed": all(state.get("success") is True and (state.get("observed") or {}).get("readOnly") is True for state in states),
        "sixModulesEach": all(len(rows) == 6 for rows in components) and all(closure.get("topLevelModuleCount") == 6 for closure in closures),
        "validRecordedOrders": all(len(order) == 6 and set(order) == set(TOKENS) and order[0] == "AA00" and order[-1] == "P000" for order in orders),
        "actualOrdersDiffer": bool(orders[0]) and bool(orders[1]) and orders[0] != orders[1],
        "onlyAA00Fixed": all(len(rows) == 6 and all(row.get("isFixed") is (token == "AA00") for token, row in rows.items()) for rows in components),
    }
    module_results = []
    for token in TOKENS:
        left, right = components[0].get(token, {}), components[1].get(token, {})
        left_source, right_source = source_identity(left.get("sourcePath")), source_identity(right.get("sourcePath"))
        source_equal = left_source is not None and left_source == right_source
        semantics_valid = component_semantics_valid(left) and component_semantics_valid(right)
        semantics_equal = semantics_valid and all(left[key] == right[key] for key in ("configuration", "solvingState", "constrainedStatus"))
        transforms = [left.get("transform"), right.get("transform")]
        bases = [rows.get("AA00", {}).get("transform") for rows in components]
        valid = all(rigid_transform_valid(value) for value in [*transforms, *bases])
        translation_error, rotation_error = None, None
        relative = []
        if valid:
            relative = [relative_transform(base, transform) for base, transform in zip(bases, transforms)]
            translation_error = math.dist(relative[0][9:12], relative[1][9:12])
            frobenius = math.sqrt(sum((a - b) ** 2 for a, b in zip(relative[0][:9], relative[1][:9])))
            rotation_error = 2 * math.asin(min(1.0, frobenius / (2 * math.sqrt(2))))
        equivalent = valid and translation_error <= TRANSLATION_TOLERANCE and rotation_error <= ROTATION_TOLERANCE
        module_results.append({"moduleToken": token, "sourceIdentityMatches": source_equal,
                               "standardSourcePath": left.get("sourcePath"), "reorderedSourcePath": right.get("sourcePath"),
                               "componentSemanticsObservedAndValid": semantics_valid,
                               "componentSemanticsMatch": semantics_equal, "rigidTransformsValid": valid,
                               "translationErrorMeters": translation_error, "rotationErrorRadians": rotation_error,
                               "relativeToAA00Equivalent": equivalent,
                               "standardRelativeTransform": relative[0] if relative else None,
                               "reorderedRelativeTransform": relative[1] if relative else None})
    checks.update({"moduleSourceIdentitiesMatch": all(row["sourceIdentityMatches"] for row in module_results),
                   "componentSemanticsEquivalent": all(row["componentSemanticsMatch"] for row in module_results),
                   "relativePosesEquivalent": all(row["relativeToAA00Equivalent"] for row in module_results)})
    first_mates, second_mates = [named_mates(state) for state in states]
    mate_results = []
    for name in sorted(set(first_mates) | set(second_mates)):
        left, right = first_mates.get(name, {}), second_mates.get(name, {})
        fields = ("mateType", "alignment", "isSuppressed", "errorCode", "isWarning")
        type_state_equal = bool(left) and bool(right) and all(key in left and key in right and left[key] == right[key] for key in fields)
        clean_active = all(row.get("isSuppressed") is False and row.get("errorCode") == 0 for row in (left, right))
        a, b = left.get("dimensionSystemValue"), right.get("dimensionSystemValue")
        parameter_equal = "dimensionSystemValue" in left and "dimensionSystemValue" in right and (
            (a is None and b is None and left.get("mateType") not in (5, 6))
            or (finite(a) and finite(b) and abs(a - b) <= PARAMETER_TOLERANCE))
        mate_results.append({"name": name, "typeAndStateEquivalent": type_state_equal,
                             "cleanAndActive": clean_active, "parameterEquivalent": parameter_equal,
                             "standard": left, "reordered": right})
    checks.update({"fifteenNamedMatesEach": len(first_mates) == len(second_mates) == 15,
                   "mateNamesMatch": bool(first_mates) and set(first_mates) == set(second_mates),
                   "mateTypesParametersStatesEquivalent": len(mate_results) == 15 and all(
                       row["typeAndStateEquivalent"] and row["cleanAndActive"] and row["parameterEquivalent"] for row in mate_results)})
    return {"checks": checks, "moduleComparisons": module_results, "mateComparisons": mate_results,
            "standardOrder": orders[0], "reorderedOrder": orders[1],
            "timingSeconds": {"standardExecution": standard_closure.get("timingSeconds"), "reorderedExecution": reordered_closure.get("timingSeconds")}}


def build_comparison(standard_root: Path, reordered_root: Path) -> dict:
    started, clock = datetime.now(timezone.utc).isoformat(), perf_counter()
    inputs, errors, payloads = [], [], []
    for label, folder in (("standard", standard_root), ("reordered", reordered_root)):
        pair = []
        for filename in ("chain-closure.json", "read-only-chain-verification.json"):
            path = folder.resolve() / filename
            row = {"variant": label, "path": str(path)}
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
                if not isinstance(payload, dict):
                    raise ValueError("证据根节点不是JSON对象")
                row["sha256"] = file_sha(path)
            except (OSError, ValueError) as exc:
                payload = {}
                row["error"] = str(exc)
                errors.append(f"{label}/{filename}: {exc}")
            inputs.append(row)
            pair.append(payload)
        payloads.extend(pair)
    try:
        report = compare_observations(*payloads)
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        errors.append(f"invalid evidence structure: {exc}")
        report = {"checks": {"inputStructureValid": False}, "moduleComparisons": [], "mateComparisons": [],
                  "standardOrder": [], "reorderedOrder": [], "timingSeconds": {}}
    output_bindings = []
    for label, closure, state in (("standard", payloads[0], payloads[1]), ("reordered", payloads[2], payloads[3])):
        path = Path(str(closure.get("outputAssemblyPath") or ""))
        row = {"variant": label, "path": str(path), "bound": False}
        try:
            if not path.is_absolute() or not path.is_file():
                raise ValueError("装配体绝对路径缺失或文件不存在")
            row["sha256"] = file_sha(path)
            row["bound"] = row["sha256"] == closure.get("outputAssemblySha256") == state.get("assemblySha256")
            row["bound"] = row["bound"] and source_identity(state.get("assemblyPath")) == source_identity(str(path))
        except (OSError, ValueError) as exc:
            row["error"] = str(exc)
            errors.append(f"{label}/output: {exc}")
        output_bindings.append(row)
    report["checks"]["inputsReadable"] = not errors
    report["checks"]["bothOutputFilesBoundIndependently"] = all(row["bound"] for row in output_bindings)
    success = all(value is True for value in report["checks"].values())
    return {"schemaVersion": "six-role-support-order-comparison/v1", "success": success,
            "status": "PASSED_SIX_ROLE_ORDER_EQUIVALENCE" if success else "FAILED_SIX_ROLE_ORDER_EQUIVALENCE",
            **report, "failedChecks": [name for name, value in report["checks"].items() if value is not True],
            "inputEvidence": inputs, "outputBindings": output_bindings, "errors": errors,
            "startedAtUtc": started, "finishedAtUtc": datetime.now(timezone.utc).isoformat(), "durationSeconds": perf_counter() - clock,
            "tolerances": {"translationMeters": TRANSLATION_TOLERANCE, "rotationRadians": ROTATION_TOLERANCE, "mateSystemValue": PARAMETER_TOLERANCE},
            "collisionOrBrep": "not_evaluated", "actualFixationMethod": "not_verified",
            "limitations": ["只验证已实际执行的两种添加顺序，不证明任意顺序都可执行。",
                            "两套装配体分别绑定自己的SHA；不要求不同装配文件的SHA相同。",
                            "对比顶层模组源文件身份、相对AA00刚体位姿及15条配合的类型/参数/状态；不新增面恢复或运动学证明。",
                            "排胶杯实际固定方式、碰撞/B-rep及工艺合理性未验证。"]}


def write_report(root: Path, report: dict) -> None:
    paths = [root / name for name in ("order-comparison.json", "order-comparison-CN.md")]
    if any(path.exists() for path in paths):
        raise FileExistsError("拒绝覆盖已有变序比较报告（包含失败报告）。")
    root.mkdir(parents=True, exist_ok=True)
    text = ["# 六类累计装配变序比较", "", f"状态：`{report['status']}`", "",
            "标准顺序：" + " → ".join(report["standardOrder"]), "",
            "变更顺序：" + " → ".join(report["reorderedOrder"]), "",
            "位姿比较基准：各模组相对AA00；平移容差1 μm，旋转容差1e-6 rad。", "",
            f"比较耗时：{report['durationSeconds']:.3f}秒。", "", "## 检查结果", "",
            *[f"- {'通过' if passed else '未通过'}：{name}" for name, passed in report["checks"].items()],
            "", "## 能力边界", "", *[f"- {item}" for item in report["limitations"]], ""]
    for path, content in ((paths[0], json.dumps(report, ensure_ascii=False, indent=2) + "\n"), (paths[1], "\n".join(text))):
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard-root", required=True, type=Path)
    parser.add_argument("--reordered-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_root.resolve()
    if any((output / name).exists() for name in ("order-comparison.json", "order-comparison-CN.md")):
        raise FileExistsError("拒绝覆盖已有变序比较报告。")
    report = build_comparison(args.standard_root, args.reordered_root)
    write_report(output, report)
    print(json.dumps({key: report[key] for key in ("status", "failedChecks", "durationSeconds")}, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
