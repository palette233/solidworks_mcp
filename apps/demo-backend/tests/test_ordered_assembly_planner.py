from __future__ import annotations

import pytest

from demo_backend.ordered_assembly_planner import (
    OrderedAssemblyPlannerError,
    preview_ordered_assembly,
)


@pytest.mark.parametrize(
    ("project_id", "command", "expected", "expected_missing", "expected_cad"),
    [
        (
            "project01",
            "项目01：以JJ00为基座，先添加SS00，再添加FF00，然后添加SM00，接着添加GN00，再添加BD00，然后添加GJ00，最后添加LM00。",
            ["SS00", "FF00", "SM00", "GN00", "BD00", "GJ00", "LM00"],
            0,
            7,
        ),
        (
            "project03",
            "项目03：以AA00为基座，先添加AE00，再添加AD00，然后添加AI00，接着添加AG00，再添加AH00，然后添加AJ00，最后添加AB00。",
            ["AE00", "AD00", "AI00", "AG00", "AH00", "AJ00", "AB00"],
            0,
            7,
        ),
    ],
)
def test_cross_project_preview_is_order_valid_but_cad_gated(
    project_id: str,
    command: str,
    expected: list[str],
    expected_missing: int,
    expected_cad: int,
) -> None:
    result = preview_ordered_assembly(project_id, command)
    plan = result["plan"]
    assert [row["moduleToken"] for row in plan["steps"]] == expected
    assert plan["summary"]["orderValid"] is True
    assert plan["summary"]["missingImplementationCount"] == expected_missing
    assert plan["summary"]["cadExecutableStepCount"] == expected_cad
    assert plan["executionBoundary"]["safeToStartCad"] is (expected_missing == 0)
    assert result["contracts"]["intent"]["intentDigest"]
    assert result["contracts"]["plan"]["planDigest"]


def test_cross_project_preview_rejects_missing_dependencies() -> None:
    result = preview_ordered_assembly(
        "project01",
        "项目01：先添加LM00，再添加SS00。",
    )
    assert result["plan"]["summary"]["orderValid"] is False
    assert result["plan"]["orderBlockers"]
    assert result["plan"]["executionBoundary"]["safeToStartCad"] is False


def test_cross_project_preview_requires_explicit_project() -> None:
    with pytest.raises(OrderedAssemblyPlannerError, match="必须明确指定项目03"):
        preview_ordered_assembly("project03", "先添加AE00，再添加AD00。")
