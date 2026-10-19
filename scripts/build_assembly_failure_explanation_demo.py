from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.global_assembly_workbench import (  # noqa: E402
    preview_released_relation_intent,
)


MATRIX = ROOT / (
    "demo/cross_project_substitution/coverage-v1/"
    "cross_project_candidate_matrix.json"
)
OUTPUT = ROOT / "demo/cross_project_substitution/failure-explanations-v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _row_case(matrix: dict, reason_code: str) -> dict:
    row = next(
        item
        for item in matrix.get("rows") or []
        if (item.get("userFailureExplanation") or {}).get("reasonCode")
        == reason_code
    )
    return {
        "kind": "cross_project_candidate",
        "source": {
            "projectIds": row.get("sourceProjectIds") or [],
            "moduleTokens": row.get("sourceModuleTokens") or [],
        },
        "target": {
            "projectIds": row.get("targetProjectIds") or [],
            "moduleTokens": row.get("targetModuleTokens") or [],
        },
        "candidateStatus": row.get("status"),
        "userFailureExplanation": row["userFailureExplanation"],
        "cadStarted": False,
    }


def _markdown(report: dict) -> str:
    lines = [
        "# 自然语言装配失败原因示例",
        "",
        "以下结论来自现有机械证据和发布门禁；解释层不改变兼容性判断，也不启动SolidWorks。",
        "",
    ]
    for index, case in enumerate(report["cases"], start=1):
        failure = case["userFailureExplanation"]
        lines.extend(
            [
                f"## {index}. {failure['summary']}",
                "",
                f"- 原因码：`{failure['reasonCode']}`",
                f"- 类别：`{failure['category']}`",
                f"- 解释：{failure['explanation']}",
                f"- CAD：`{failure['cadLaunchDecision']}`",
                "- 建议：",
            ]
        )
        lines.extend(
            f"  - {action}" for action in failure.get("suggestedActions") or []
        )
        lines.append("")
    lines.extend(
        [
            "> 碰撞/B-rep不是这些前置失败的解决条件；应先补齐机械接口、语义端口或发布授权。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    matrix = _read(MATRIX)
    release_preview = preview_released_relation_intent(
        ROOT,
        {
            "requirement": "让两个安装面重合",
            "executionMode": "drive",
        },
    )
    cases = [
        _row_case(matrix, "INSTALLATION_TOPOLOGY_INCOMPATIBLE"),
        _row_case(matrix, "LOCATING_PATTERN_MISMATCH"),
        _row_case(matrix, "TARGET_SLOT_NOT_REGISTERED"),
        {
            "kind": "natural_language_relation_preview",
            "requirement": "让两个安装面重合",
            "previewStatus": release_preview.get("status"),
            "userFailureExplanation": release_preview[
                "userFailureExplanation"
            ],
            "cadStarted": False,
        },
    ]
    report = {
        "schemaVersion": "assembly-failure-explanation-demo/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "sourceMatrixDigest": matrix.get("matrixDigest"),
        "caseCount": len(cases),
        "reasonCodes": [
            case["userFailureExplanation"]["reasonCode"] for case in cases
        ],
        "cases": cases,
        "collisionStatus": "not_evaluated",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT / "failure-explanation-demo.json"
    markdown_path = OUTPUT / "failure-explanation-demo.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "reasonCodes": report["reasonCodes"],
                "jsonPath": str(json_path),
                "markdownPath": str(markdown_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
