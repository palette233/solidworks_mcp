#!/usr/bin/env python3
"""Audit and persist the monitored Project 02 mate-reconstruction pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.mate_reconstruction_pipeline import (  # noqa: E402
    apply_graph_audit,
    audit_full_graph_semantics,
    audit_rebuild_closure,
    new_pipeline_status,
    render_pipeline_markdown,
    update_pipeline_stage,
)


DEFAULT_GRAPH = ROOT / "demo/layout_previews/project02_module_mate_graph_v4_semantics.json"
DEFAULT_DIR = ROOT / "demo/mate_reconstruction_pipeline"
DEFAULT_STATUS = DEFAULT_DIR / "project02_mate_reconstruction_pipeline_status.json"
DEFAULT_MARKDOWN = ROOT / "docs/project02_mate_reconstruction_pipeline-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("init", "audit-graph", "audit-rebuild", "set-stage", "show"))
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--run-result", type=Path)
    parser.add_argument("--reopened-graph", type=Path)
    parser.add_argument("--stage")
    parser.add_argument("--stage-status")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--issue", action="append", default=[])
    parser.add_argument("--next-action")
    return parser.parse_args()


def read_or_initialize(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else new_pipeline_status()


def save_status(status: dict, status_path: Path, markdown_path: Path) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_pipeline_markdown(status), encoding="utf-8")


def main() -> int:
    args = parse_args()
    status_path = args.status.resolve()
    markdown_path = args.markdown.resolve()
    if args.command == "init":
        status = read_or_initialize(status_path)
        save_status(status, status_path, markdown_path)
    elif args.command == "audit-graph":
        graph_path = args.graph.resolve()
        audit_path = (args.audit or graph_path.with_suffix(".semantics-audit.json")).resolve()
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        audit = audit_full_graph_semantics(graph)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        status = apply_graph_audit(read_or_initialize(status_path), audit, graph_path, audit_path)
        save_status(status, status_path, markdown_path)
    elif args.command == "audit-rebuild":
        if not args.run_result or not args.reopened_graph:
            raise ValueError("audit-rebuild requires --run-result and --reopened-graph.")
        audit_path = (args.audit or args.run_result.with_suffix(".closure-audit.json")).resolve()
        audit = audit_rebuild_closure(
            json.loads(args.run_result.resolve().read_text(encoding="utf-8-sig")),
            json.loads(args.reopened_graph.resolve().read_text(encoding="utf-8-sig")),
        )
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        status = read_or_initialize(status_path)
    elif args.command == "set-stage":
        if not args.stage or not args.stage_status:
            raise ValueError("set-stage requires --stage and --stage-status.")
        status = update_pipeline_stage(
            read_or_initialize(status_path),
            args.stage,
            args.stage_status,
            evidence=args.evidence,
            issues=args.issue,
            next_action=args.next_action,
        )
        save_status(status, status_path, markdown_path)
    else:
        status = read_or_initialize(status_path)

    print(
        json.dumps(
            {
                "overallStatus": status["overallStatus"],
                "activeStage": status["activeStage"],
                "stages": [{"key": item["key"], "status": item["status"]} for item in status["stages"]],
                "statusFile": str(status_path),
                "markdown": str(markdown_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
