from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from run_staged_chain_execution_batch import _build_chain_command  # noqa: E402
from run_station_closure_program import _build_command  # noqa: E402


def _action(action: str = "run", chain_id: str = "chain-a") -> dict[str, str]:
    return {
        "action": action,
        "chainId": chain_id,
        "outputRoot": "demo/compiled/chain-a",
    }


def test_failure_injection_is_added_only_to_selected_first_run() -> None:
    command = _build_chain_command(
        _action(),
        inject_failure_chain_id="chain-a",
        inject_failure_before_stage="s02-scanner",
    )
    assert command[-2:] == ["--inject-failure-before-stage", "s02-scanner"]


def test_failure_injection_is_not_reapplied_on_resume() -> None:
    command = _build_chain_command(
        _action("resume"),
        inject_failure_chain_id="chain-a",
        inject_failure_before_stage="s02-scanner",
    )
    assert "--inject-failure-before-stage" not in command


def test_failure_injection_is_not_applied_to_another_chain() -> None:
    command = _build_chain_command(
        _action(chain_id="chain-b"),
        inject_failure_chain_id="chain-a",
        inject_failure_before_stage="s02-scanner",
    )
    assert "--inject-failure-before-stage" not in command


def test_closure_program_forwards_scoped_six_role_failure_injection() -> None:
    args = SimpleNamespace(
        six_role_chain_batch_report=Path("demo/six-role/batch-report.json"),
        session_check_timeout=120.0,
        six_role_inject_failure_chain_id="chain-a",
        six_role_inject_failure_before_stage="s02-scanner",
    )
    command = _build_command(
        args,
        {
            "nextAction": {
                "phaseId": "new_six_role_cumulative_chain",
                "action": "run_six_role_chain",
            }
        },
    )
    assert command[-4:] == [
        "--inject-failure-chain-id",
        "chain-a",
        "--inject-failure-before-stage",
        "s02-scanner",
    ]
