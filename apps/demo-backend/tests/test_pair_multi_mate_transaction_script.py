import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_pair_multi_mate_transaction import build_pair_transaction


def test_stale_project05_graph_without_width_roles_is_fail_closed():
    graph = json.loads(
        (ROOT / "demo/layout_previews/project05_module_mate_graph.json").read_text(
            encoding="utf-8-sig"
        )
    )

    with pytest.raises(ValueError, match="Width mate"):
        build_pair_transaction(
            graph,
            target_module_token="D000",
            context_module_token="A000",
        )


def test_refreshed_project05_transport_pair_compiles_as_closed_real_transaction():
    graph = json.loads(
        (ROOT / "demo/layout_previews/project05_module_mate_graph_v2_axes.json").read_text(
            encoding="utf-8-sig"
        )
    )

    subset, patch, effective, preflight = build_pair_transaction(
        graph,
        target_module_token="D000",
        context_module_token="A000",
    )

    assert len(subset["Mates"]) == 3
    assert {row["MateType"] for row in subset["Mates"]} == {0, 5, 11}
    assert len(patch["operations"]) == 3
    assert effective["PatchAudit"]["operationCount"] == 3
    assert preflight["publishAllowed"] is True
    assert preflight["rigidBodyDofAnalysis"]["constraintRank"] == 6
    assert preflight["rigidBodyDofAnalysis"]["residualDof"] == 0
