import pytest

from demo_backend.mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
)
from demo_backend.parameterized_datum_position_language import (
    compile_parameterized_datum_position_instruction,
)


def test_absolute_semantic_position_compiles_millimetres_to_metres():
    result = compile_parameterized_datum_position_instruction(
        "基座纵向位置70毫米，横向位置120 mm，支承高度0毫米。"
    )
    assert result["mode"] == "absolute_in_base_datum_frame"
    assert result["parametersMeters"] == {
        "longitudinal": 0.070,
        "lateral": 0.120,
        "supportGap": 0.0,
    }
    assert result["coordinateFrame"] == "selected_base_semantic_datum_frame"


def test_delta_instruction_updates_only_longitudinal_from_confirmed_current():
    result = compile_parameterized_datum_position_instruction(
        "沿基座纵向移动10毫米，其余位置参数保持不变。",
        current_parameters_meters={
            "longitudinal": 0.354,
            "lateral": 0.2535,
            "supportGap": 0.0,
        },
    )
    assert result["mode"] == "delta_from_confirmed_current"
    assert result["parametersMeters"] == {
        "longitudinal": pytest.approx(0.364),
        "lateral": 0.2535,
        "supportGap": 0.0,
    }


def test_partial_absolute_can_preserve_explicit_current_parameters():
    result = compile_parameterized_datum_position_instruction(
        "横向位置增加到26厘米，其余位置参数不变。",
        current_parameters_meters={
            "longitudinal": 0.354,
            "lateral": 0.2535,
            "supportGap": 0.0,
        },
    )
    assert result["parametersMeters"]["lateral"] == pytest.approx(0.26)
    assert result["parametersMeters"]["longitudinal"] == 0.354


@pytest.mark.parametrize(
    "instruction,current,match",
    [
        ("沿基座纵向移动10毫米。", None, "requires current parameters"),
        ("基座纵向位置70毫米。", None, "must provide all three"),
        (
            "X方向70毫米，Y方向120毫米，Z方向0毫米。",
            None,
            "bare X/Y/Z is ambiguous",
        ),
        (
            "沿基座纵向减少500毫米，其余位置参数不变。",
            {"longitudinal": 0.1, "lateral": 0.2, "supportGap": 0.0},
            "finite and nonnegative",
        ),
    ],
)
def test_ambiguous_or_incomplete_position_language_fails_closed(
    instruction, current, match
):
    with pytest.raises(MechanicalInterfaceContractError, match=match):
        compile_parameterized_datum_position_instruction(
            instruction, current_parameters_meters=current
        )
