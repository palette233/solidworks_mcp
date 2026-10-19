#!/usr/bin/env python3
"""Summarize released cross-project execution coverage by module role."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _status_count(summary: dict, status: str) -> int:
    return int((summary.get("statusCounts") or {}).get(status) or 0)


def _role_projection(summary: dict) -> dict:
    released = _status_count(summary, "released_direct_execution")
    incompatible = _status_count(summary, "incompatible")
    missing = _status_count(summary, "needs_endpoint_or_template")
    return {
        "role": summary.get("group"),
        "releasedDirectionalPairCount": released,
        "incompatibleDirectionalPairCount": incompatible,
        "missingEndpointOrTemplateDirectionalPairCount": missing,
        "directlySubstitutable": released > 0,
    }


def _markdown(report: dict) -> str:
    ready = report["readyRoles"]
    blocked = report["blockedRoles"]
    lines = [
        "# 跨项目模组角色直连准备度",
        "",
        f"- 来源矩阵：`{report['sourceMatrixPath']}`",
        f"- 矩阵摘要：`{report['sourceMatrixDigest']}`",
        f"- 已发布跨项目执行模板：{report['releasedExecutionTemplateCount']} 条",
        f"- 已形成直接替换闭环的角色：{len(ready)} 类",
        f"- CAD启动：否（本报告仅做目录与发布证据审计）",
        f"- 碰撞/B-rep：未评估",
        "",
        "## 已可直接跨项目替换",
        "",
        "| 角色 | 已发布方向对 | 结论 |",
        "|---|---:|---|",
    ]
    for row in ready:
        lines.append(
            f"| {row['role']} | {row['releasedDirectionalPairCount']} | "
            "已存在发布授权的直接机械替换证据 |"
        )
    lines.extend(
        [
            "",
            "## 尚不可直接跨项目替换",
            "",
            "| 角色 | 不兼容方向对 | 缺端口/模板方向对 | 结论 |",
            "|---|---:|---:|---|",
        ]
    )
    for row in blocked:
        lines.append(
            f"| {row['role']} | {row['incompatibleDirectionalPairCount']} | "
            f"{row['missingEndpointOrTemplateDirectionalPairCount']} | "
            "不得直接启动CAD；需补真实接口证据或明确转接接口 |"
        )
    lines.extend(
        [
            "",
            "## 已通过基准定位Demo、但尚非直接机械替换",
            "",
        ]
    )
    datum_roles = report.get("datumPlacementDemoRoles") or []
    if datum_roles:
        lines.extend(
            [
                "| 角色 | 来源 → 目标 | CAD闭环 | 边界 |",
                "|---|---|---|---|",
            ]
        )
        for row in datum_roles:
            lines.append(
                f"| {row['role']} | {row['sourceProjectId']} → {row['targetProjectId']} | "
                "非原型位姿、真实配合、保存重开通过 | "
                "仅证明语义基准定位；不证明孔系、紧固件或转接件兼容 |"
            )
    else:
        lines.append("无。")
    lines.extend(
        [
            "",
            "## 结论",
            "",
            report["statement"],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument(
        "--datum-demo-closure",
        type=Path,
        help="可选的跨项目基准定位Demo闭环；不会被计入直接替换角色。",
    )
    args = parser.parse_args()

    matrix_path = args.matrix.resolve()
    matrix = _read(matrix_path)
    roles = [_role_projection(row) for row in matrix.get("roleSummaries") or []]
    ready = sorted(
        (row for row in roles if row["directlySubstitutable"]),
        key=lambda row: str(row["role"]),
    )
    blocked = sorted(
        (row for row in roles if not row["directlySubstitutable"]),
        key=lambda row: str(row["role"]),
    )
    datum_roles = []
    if args.datum_demo_closure:
        closure_path = args.datum_demo_closure.resolve()
        closure = _read(closure_path)
        if (
            closure.get("schemaVersion")
            != "cross-project-wastecup-datum-closure/v1"
            or closure.get("success") is not True
            or closure.get("releaseEligibleForDatumPlacementDemo") is not True
            or closure.get("releaseEligibleForDirectMechanicalSubstitution")
            is not False
        ):
            raise ValueError("基准定位Demo闭环未通过，或错误宣称为直接机械替换。")
        datum_roles.append(
            {
                "role": closure.get("moduleRole"),
                "sourceProjectId": closure.get("sourceProjectId"),
                "sourceModuleToken": closure.get("sourceModuleToken"),
                "targetProjectId": closure.get("targetProjectId"),
                "targetBaseToken": closure.get("targetBaseToken"),
                "closurePath": str(closure_path),
                "semanticDatumPlacementPassed": True,
                "directMechanicalInterfaceCompatible": "not_evaluated",
            }
        )
    report = {
        "schemaVersion": "cross-project-role-readiness/v1",
        "status": "passed",
        "sourceMatrixPath": str(matrix_path),
        "sourceMatrixDigest": matrix.get("matrixDigest") or _digest(matrix),
        "releasedExecutionTemplateCount": int(
            matrix.get("releasedDirectExecutionCount") or 0
        ),
        "releasedDirectionalPairCount": sum(
            row["releasedDirectionalPairCount"] for row in roles
        ),
        "readyRoleCount": len(ready),
        "readyRoles": ready,
        "blockedRoleCount": len(blocked),
        "blockedRoles": blocked,
        "thirdDirectRoleAvailable": len(ready) >= 3,
        "datumPlacementDemoRoleCount": len(datum_roles),
        "datumPlacementDemoRoles": datum_roles,
        "thirdDatumPlacementDemoRoleAvailable": len(ready) + len(datum_roles) >= 3,
        "cadStarted": False,
        "collisionStatus": "not_evaluated",
        "statement": (
            "当前直接跨项目替换闭环仍仅覆盖Transport与Calibration两类角色；"
            "WasteCup已新增Project05 P000到Project02 A600的跨项目基准定位CAD闭环，"
            "但它不证明孔系、紧固件或实体转接件兼容，不能计入直接机械替换。"
            "其余角色仍须补真实端口、模板或兼容证据。"
        ),
    }

    json_output = args.json_output.resolve()
    markdown_output = args.markdown_output.resolve()
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_output.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
