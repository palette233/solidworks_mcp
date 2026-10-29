from pathlib import Path

from demo_backend.goal_matched_alternate_slot_cases import (
    compile_gn00_aa00_204mm_candidate,
)


ROOT = Path(__file__).resolve().parents[3]


def test_gn00_aa00_candidate_uses_exact_reviewed_axes_and_nonprototype_pose():
    package = compile_gn00_aa00_204mm_candidate(ROOT)
    graph = package["effectiveGraph"]

    assert package["status"] == "ready_for_nonprototype_cad_validation"
    assert package["requiredSpacingMeters"] == 0.204
    assert package["sourceTopLevelPoseUsed"] is False
    assert package["leafPoseAnchorsUsed"] is False
    assert package["physicalFasteningVerified"] is False
    assert graph["EditPolicy"]["fixedModuleTokens"] == ["AA00"]
    assert graph["EditPolicy"]["targetModuleToken"] == "GN00"
    assert graph["EditPolicy"]["casePoseAnchors"] == []
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert next(
        row for row in graph["Modules"] if row["ModuleToken"] == "GN00"
    )["SourceTransform"] == [
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 1.0,
        0.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
    ]
    assert [row["MateTypeName"] for row in graph["Mates"]] == [
        "swMateCOINCIDENT",
        "swMateCONCENTRIC",
        "swMateCONCENTRIC",
    ]
    assert [row["AlignmentName"] for row in graph["Mates"]] == [
        "swMateAlignANTI_ALIGNED",
        "swMateAlignALIGNED",
        "swMateAlignALIGNED",
    ]
    assert package["selectedLocatingEndpointIds"] == [
        "face:fl9a24d063aa00:005b6eb8fd8655a9",
        "face:fl9a24d063aa00:4b5af1f59c835728",
    ]
