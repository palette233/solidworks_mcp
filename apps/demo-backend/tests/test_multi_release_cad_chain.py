from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from demo_backend.multi_release_cad_chain import (
    MultiReleaseCadChainError,
    rebase_single_packet_manifest_for_external_checkpoint,
    validate_multi_release_cad_chain,
)


ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / (
    "demo/global_assembly_catalog/releases/"
    "relation-v64-project02-project05-wastecup-executable-demo-20261015"
)
CHAIN_ROOT = ROOT / (
    "demo/cross_project_substitution/wastecup-project05-to-project02-v1/"
    "extended-chain-v2"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_single_packet_demo_manifest_can_be_rebased_without_changing_relation():
    source = _read(RELEASE / "explicit-demo.cad-transaction-manifest.json")
    rebased = rebase_single_packet_manifest_for_external_checkpoint(
        source, source_stage_id="direct-installation-stage"
    )

    assert source["packets"][0]["cumulativeInput"]["kind"] == "base_module_source"
    assert rebased["packets"][0]["cumulativeInput"] == {
        "kind": "previous_transaction_checkpoint",
        "packetId": "direct-installation-stage:final",
        "externalStageId": "direct-installation-stage",
    }
    assert rebased["relationReleaseBinding"] == source["relationReleaseBinding"]
    assert rebased["packets"][0]["connections"] == source["packets"][0][
        "connections"
    ]
    assert rebased["manifestDigest"] != source["manifestDigest"]


def test_project02_plus_wastecup_multi_release_chain_revalidates_live_evidence():
    chain = _read(CHAIN_ROOT / "multi-release-chain.json")
    validate_multi_release_cad_chain(ROOT, chain)
    plan = _read(CHAIN_ROOT / "wastecup-append.execution-plan.json")

    assert chain["status"] == "ready_for_staged_execution"
    assert [row["relationExecutionMode"] for row in chain["stages"]] == [
        "direct_installation",
        "datum_placement_demo",
    ]
    assert chain["packetCount"] == 4
    assert plan["targetModuleToken"] == "P000"
    assert plan["cumulativeInputKind"] == "previous_transaction_checkpoint"
    assert plan["requestedMateCount"] == 3
    assert plan["effectiveGraphMateCoverage"]["status"] == "exact"


def test_multi_release_chain_digest_tampering_fails_closed():
    chain = _read(CHAIN_ROOT / "multi-release-chain.json")
    tampered = copy.deepcopy(chain)
    tampered["packetCount"] = 99

    with pytest.raises(MultiReleaseCadChainError, match="摘要不一致"):
        validate_multi_release_cad_chain(ROOT, tampered)
