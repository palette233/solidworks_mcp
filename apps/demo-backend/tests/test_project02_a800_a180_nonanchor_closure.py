from __future__ import annotations

from pathlib import Path

from demo_backend.project02_a800_a180_nonanchor_closure import (
    build_project02_a800_a180_nonanchor_closure,
)


ROOT = Path(__file__).resolve().parents[3]
RUN_ROOT = ROOT / "demo/semantic_ports/project02_a800_a180_dof_audit_v1"


def test_real_project02_a800_a180_nonanchor_chain_is_closed() -> None:
    report = build_project02_a800_a180_nonanchor_closure(
        RUN_ROOT / "project02-a600-a800-nonanchor-v1.result.json",
        RUN_ROOT / "project02-a600-a800-a180-source-slot-v2.result.json",
        RUN_ROOT / "project02-a600-a800-a180-nonanchor-v1.result.json",
    )
    assert report["status"] == "passed"
    assert report["checks"]["a180ConsumesA800Checkpoint"] is True
    assert report["checks"]["overconstraintFeedbackCaptured"] is True
    assert report["collisionStatus"] == "not_evaluated"
