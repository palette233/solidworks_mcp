#!/usr/bin/env python3
"""Recompile immutable staged-chain requests against one current registry.

This is a thin evidence utility over ``run_natural_language_staged_chain.py``.
It never starts CAD.  Source requests remain unchanged; each receives a new
chain id and a generated request/compilation directory under the output root.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _write_once(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def rebase_request(
    payload: dict,
    *,
    registry_path: str,
    chain_suffix: str,
    prototype_estimate_roles: set[str] | None = None,
) -> dict:
    """Return a new request without mutating its immutable source."""

    if not payload.get("chainId") or not payload.get("baseSelection"):
        raise ValueError("staged-chain request is missing chain identity or base")
    if not isinstance(payload.get("steps"), list) or not payload["steps"]:
        raise ValueError("staged-chain request has no ordered stages")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", chain_suffix):
        raise ValueError("chain suffix must be lowercase alphanumeric/hyphen")
    rebased = json.loads(json.dumps(payload, ensure_ascii=False))
    rebased["chainId"] = f"{payload['chainId']}-{chain_suffix}"
    rebased["stationRegistryPath"] = registry_path
    if prototype_estimate_roles is not None:
        top_level_authorized = payload.get("allowPrototypeEstimate") is True
        stage_authorized = {
            str(step.get("moduleRole") or "")
            for step in payload["steps"]
            if step.get("allowPrototypeEstimate") is True
        }
        if not top_level_authorized and not prototype_estimate_roles.issubset(
            stage_authorized
        ):
            raise ValueError(
                "prototype estimate scope can only narrow an explicitly authorized request"
            )
        rebased.pop("allowPrototypeEstimate", None)
        matched: set[str] = set()
        for step in rebased["steps"]:
            role = str(step.get("moduleRole") or "")
            if role in prototype_estimate_roles:
                step["allowPrototypeEstimate"] = True
                matched.add(role)
            else:
                step.pop("allowPrototypeEstimate", None)
        missing = prototype_estimate_roles - matched
        if missing:
            raise ValueError(
                "prototype estimate scope roles are absent from request: "
                + ",".join(sorted(missing))
            )
    return rebased


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", action="append", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--chain-suffix", required=True)
    parser.add_argument(
        "--prototype-estimate-role",
        action="append",
        default=None,
        help=(
            "Narrow an existing top-level prototype-measurement authorization "
            "to stages with this exact moduleRole. May be repeated."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    output = (ROOT / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    registry = (ROOT / args.registry).resolve() if not args.registry.is_absolute() else args.registry.resolve()
    output.relative_to(ROOT)
    registry.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite batch output: {output}")
    if not registry.is_file():
        raise FileNotFoundError(registry)
    output.mkdir(parents=True)

    started_at = datetime.now(timezone.utc).isoformat()
    clock = perf_counter()
    rows = []
    source_ids = set()
    for index, request_value in enumerate(args.request, start=1):
        source = (
            (ROOT / request_value).resolve()
            if not request_value.is_absolute()
            else request_value.resolve()
        )
        source.relative_to(ROOT)
        if not source.is_file():
            raise FileNotFoundError(source)
        source_payload = _read(source)
        source_id = str(source_payload.get("chainId") or "")
        if source_id in source_ids:
            raise ValueError(f"duplicate source chain id: {source_id}")
        source_ids.add(source_id)

        row_dir = output / f"chain-{index:02d}"
        generated_request = row_dir / "request.json"
        compiled_dir = row_dir / "compiled"
        rebased = rebase_request(
            source_payload,
            registry_path=_relative(registry),
            chain_suffix=args.chain_suffix,
            prototype_estimate_roles=(
                set(args.prototype_estimate_role)
                if args.prototype_estimate_role is not None
                else None
            ),
        )
        _write_once(generated_request, rebased)
        command = [
            sys.executable,
            str(ROOT / "scripts/run_natural_language_staged_chain.py"),
            "compile",
            str(generated_request),
            str(compiled_dir),
        ]
        stage_clock = perf_counter()
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, check=False
        )
        compilation_path = compiled_dir / "compilation.json"
        if completed.returncode != 0 or not compilation_path.is_file():
            raise RuntimeError(
                "staged-chain recompilation failed: "
                + completed.stderr.decode("utf-8", errors="replace")
            )
        compilation = _read(compilation_path)
        if (
            compilation.get("status") != "ready_not_started"
            or compilation.get("cadStarted") is not False
            or compilation.get("targetStationPreflightPassed") is not True
        ):
            raise RuntimeError("rebased chain did not pass offline preflight")
        rows.append(
            {
                "sourceRequestPath": _relative(source),
                "sourceRequestSha256": _sha(source),
                "generatedRequestPath": _relative(generated_request),
                "generatedRequestSha256": _sha(generated_request),
                "sourceChainId": source_id,
                "generatedChainId": rebased["chainId"],
                "compilationPath": _relative(compilation_path),
                "compilationSha256": _sha(compilation_path),
                "targetStationPreflightPassed": True,
                "status": "ready_not_started",
                "cadStarted": False,
                "durationSeconds": perf_counter() - stage_clock,
            }
        )

    report = {
        "schemaVersion": "staged-chain-registry-recompilation-batch/v1",
        "registryPath": _relative(registry),
        "registrySha256": _sha(registry),
        "chainSuffix": args.chain_suffix,
        "prototypeEstimateScopeRoles": sorted(
            set(args.prototype_estimate_role or [])
        ),
        "chainCount": len(rows),
        "readyCount": len(rows),
        "chains": rows,
        "startedAtUtc": started_at,
        "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter() - clock,
        "cadStarted": False,
        "claimBoundary": (
            "Offline recompilation and target-station preflight only. No component "
            "was inserted and no CAD closure or functional station was validated."
        ),
    }
    _write_once(output / "batch-report.json", report)
    print(
        json.dumps(
            {
                "chainCount": report["chainCount"],
                "readyCount": report["readyCount"],
                "cadStarted": False,
                "durationSeconds": report["durationSeconds"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
