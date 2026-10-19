from __future__ import annotations

from copy import deepcopy

import pytest

from demo_backend.assembly_contracts import (
    ASSEMBLY_INTENT_SCHEMA,
    ASSEMBLY_PLAN_SCHEMA,
    AssemblyContractError,
    build_assembly_intent_contract,
    build_assembly_plan_contract,
    validate_assembly_intent_contract,
)
from demo_backend.semantic_assembly_sequence import (
    build_project02_ordered_assembly_plan,
    parse_project02_ordered_assembly_command,
)


COMMAND = "项目02：先添加A800，再添加A180，然后添加A700，接着添加A300，再添加A500，最后添加A100。"


def test_project02_legacy_intent_compiles_to_generic_contract() -> None:
    legacy = parse_project02_ordered_assembly_command(COMMAND)
    contract = build_assembly_intent_contract(legacy)
    assert contract["schemaVersion"] == ASSEMBLY_INTENT_SCHEMA
    assert [step["moduleToken"] for step in contract["orderedSteps"]] == [
        "A800", "A180", "A700", "A300", "A500", "A100"
    ]
    assert len(contract["intentDigest"]) == 64
    assert contract["projectProfile"]["profileVersion"] == "2026-09-30.1"


def test_plan_contract_binds_profile_and_intent_digests() -> None:
    legacy_intent = parse_project02_ordered_assembly_command(COMMAND)
    legacy_plan = build_project02_ordered_assembly_plan(legacy_intent)
    intent = build_assembly_intent_contract(legacy_intent)
    plan = build_assembly_plan_contract(legacy_plan, intent)
    assert plan["schemaVersion"] == ASSEMBLY_PLAN_SCHEMA
    assert plan["intentDigest"] == intent["intentDigest"]
    assert len(plan["planDigest"]) == 64
    assert plan["summary"]["allStepsCadExecutableNow"] is True


def test_contract_digest_changes_when_order_changes() -> None:
    first = build_assembly_intent_contract(
        parse_project02_ordered_assembly_command("项目02：先添加A800，再添加A180。")
    )
    second = build_assembly_intent_contract(
        parse_project02_ordered_assembly_command("项目02：先添加A180，再添加A800。")
    )
    assert first["intentDigest"] != second["intentDigest"]


def test_intent_contract_rejects_duplicate_module() -> None:
    contract = build_assembly_intent_contract(
        parse_project02_ordered_assembly_command("项目02：先添加A800，再添加A180。")
    )
    invalid = deepcopy(contract)
    invalid["orderedSteps"].append(dict(invalid["orderedSteps"][-1], order=3))
    with pytest.raises(AssemblyContractError, match="重复模组"):
        validate_assembly_intent_contract(invalid)
