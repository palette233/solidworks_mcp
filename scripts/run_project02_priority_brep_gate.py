#!/usr/bin/env python3
"""Run one priority batch from the Project 02 staged B-Rep plan.

The command refuses to run when more than one SolidWorks process exists.  It
never runs later batches after an incomplete or interfering pair, and it
updates the machine-readable plan with the durable batch result.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.pipeline_timing import PipelineTiming  # noqa: E402
DEFAULT_PLAN = ROOT / "demo/layout_previews/project02_v34_static_collision_execution_plan.json"
DEFAULT_ASSEMBLY = ROOT / "demo/FL9A24D062A000_8modules_clean_solved_v33.SLDASM"
# Keep the exact-interference runner on the same executable baseline as the
# successful Project02 Replay workflow.  The older 20260824 build does not
# expose activate_document_by_title and therefore fails before geometry work.
DEFAULT_EXE = ROOT / "artifacts/solidworks-mcp-20260810-startupready/SolidWorksMcpApp.exe"


def resolved(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def solidworks_process_count() -> int:
    if sys.platform != "win32":
        return 0
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count",
        ],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return -1
    try:
        return int(completed.stdout.strip())
    except ValueError:
        return -1


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def result_value(item: dict[str, Any], pascal: str, camel: str, default: Any = None) -> Any:
    return item.get(pascal, item.get(camel, default))


def pair_acceptance_passed(item: dict[str, Any]) -> bool:
    """Honor a durable per-pair acceptance decision when one is present.

    Conditional B-rep may legitimately report prototype-existing contact.  In
    that case ``HasInterference`` remains true, while ``acceptance.accepted``
    records that no new leaf-body pair was introduced.  Falling back to the
    raw exact result keeps older zero-interference batches compatible.
    """

    acceptance = item.get("acceptance")
    if isinstance(acceptance, dict) and "accepted" in acceptance:
        return acceptance.get("accepted") is True
    return (
        result_value(item, "ExactCheckComplete", "exactCheckComplete") is True
        and result_value(item, "HasInterference", "hasInterference") is not True
        and int(result_value(item, "FailedBodyPairCount", "failedBodyPairCount", 0) or 0)
        == 0
    )


def main() -> int:
    timing = PipelineTiming("project02.priority-brep-gate")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--assembly", default=str(DEFAULT_ASSEMBLY))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument(
        "--output-root",
        default=None,
        help=(
            "Directory that receives priority batch evidence. Defaults to "
            "demo/interference_<assembly-stem> so evidence from different Replay "
            "versions cannot be mixed."
        ),
    )
    parser.add_argument("--priority", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--exit-solidworks-after-check", action="store_true")
    parser.add_argument(
        "--existing-batch",
        default=None,
        help=(
            "Import an already captured/reevaluated batch without reopening SolidWorks. "
            "The batch must contain exactly the pairs requested by the selected priority."
        ),
    )
    args = parser.parse_args()

    plan_path = resolved(args.plan)
    assembly = resolved(args.assembly)
    exe = resolved(args.exe)
    if not plan_path.exists() or not assembly.exists() or not exe.exists():
        missing = [str(path) for path in (plan_path, assembly, exe) if not path.exists()]
        raise SystemExit(f"Required input does not exist: {missing}")

    existing_batch = resolved(args.existing_batch) if args.existing_batch else None
    process_count = solidworks_process_count() if existing_batch is None else None
    if process_count not in {None, 0, 1}:
        raise SystemExit(
            f"Refusing CAD execution: expected zero or one SLDWORKS process, found {process_count}."
        )

    plan = read_json(plan_path)
    batches = plan.get("conditionalBrep", {}).get("batches") or []
    batch = next(
        (item for item in batches if int(item.get("priority", -1)) == args.priority),
        None,
    )
    if not batch:
        raise SystemExit(f"Plan has no priority batch {args.priority}.")
    if batch.get("status") == "passed":
        print(json.dumps({"status": "BATCH_ALREADY_PASSED", "priority": args.priority}))
        return 0

    requested_pairs: list[list[str]] = []
    for item in batch.get("pairs") or []:
        first, second = item["components"]
        requested_pairs.append([first, second])

    if existing_batch is not None:
        if not existing_batch.is_file():
            raise SystemExit(f"Existing batch does not exist: {existing_batch}")
        batch_file = existing_batch
        completed_returncode = 0
        timing_stage = "import-existing-priority-leaf-interference"
    else:
        output_root = (
            resolved(args.output_root)
            if args.output_root
            else ROOT / "demo" / f"interference_{assembly.stem}"
        )
        output_dir = output_root / f"priority_p{args.priority}"
        command = [
            sys.executable,
            str(ROOT / "scripts/capture_leaf_interference_details.py"),
            "--exe",
            str(exe),
            "--assembly",
            str(assembly),
            "--output-dir",
            str(output_dir),
            "--timeout",
            str(args.timeout),
            "--direct-stdio",
            "--reuse-existing",
            "--stop-on-first-interference",
        ]
        if args.exit_solidworks_after_check:
            command.append("--exit-solidworks-after-check")
        for first, second in requested_pairs:
            command.extend(("--pair", first, second))
        with timing.stage(
            "capture-priority-leaf-interference",
            priority=args.priority,
            requestedPairCount=len(requested_pairs),
        ):
            completed = subprocess.run(command, cwd=ROOT, check=False)
        completed_returncode = completed.returncode
        batch_file = output_dir / f"{assembly.stem}_leaf_details_batch.json"
        timing_stage = "capture-priority-leaf-interference"
        if not batch_file.exists():
            plan["status"] = f"P{args.priority}_BREP_EXECUTION_FAILED"
            batch["status"] = "failed"
            batch["failureReason"] = (
                f"capture command exited {completed_returncode} without durable batch output"
            )
            batch["timing"] = timing.finish(status="failed")
            plan["latestTiming"] = batch["timing"]
            plan_path.write_text(
                json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            return completed_returncode or 1

    if existing_batch is not None:
        with timing.stage(
            timing_stage,
            priority=args.priority,
            requestedPairCount=len(requested_pairs),
            batchPath=str(batch_file),
        ):
            pass

    result = read_json(batch_file)
    checked = result.get("pairs") or []
    checked_pairs = {
        tuple(str(value) for value in item.get("pair") or [])
        for item in checked
    }
    requested_pair_set = {tuple(pair) for pair in requested_pairs}
    hard_failures = [item for item in checked if not pair_acceptance_passed(item)]
    batch_passed = (
        completed_returncode == 0
        and len(checked) == len(requested_pairs)
        and checked_pairs == requested_pair_set
        and not hard_failures
    )
    batch["status"] = "passed" if batch_passed else "failed"
    batch["resultPath"] = str(batch_file)
    batch["requestedPairCount"] = len(requested_pairs)
    batch["completedPairCount"] = len(checked)
    batch["hardFailureCount"] = len(hard_failures)
    if batch_passed:
        remaining = [item for item in batches if item.get("status") != "passed"]
        plan["status"] = (
            "ALL_PRIORITY_BREP_BATCHES_PASSED_FINAL_REOPEN_PENDING"
            if not remaining
            else f"P{args.priority}_BREP_PASSED_NEXT_BATCH_READY"
        )
    else:
        plan["status"] = f"P{args.priority}_INTERFERENCE_FOUND_CONSTRAINT_FEEDBACK_REQUIRED"
    plan["cadPreflight"] = {
        "solidworksProcessCountBeforeRun": process_count,
        "ready": True,
        "solidWorksReopened": existing_batch is None,
    }
    batch["timing"] = timing.finish(
        status="completed" if batch_passed else "failed"
    )
    plan["latestTiming"] = batch["timing"]
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": plan["status"],
                "priority": args.priority,
                "batchPassed": batch_passed,
                "requestedPairCount": len(requested_pairs),
                "completedPairCount": len(checked),
                "hardFailureCount": len(hard_failures),
                "resultPath": str(batch_file),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if batch_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
