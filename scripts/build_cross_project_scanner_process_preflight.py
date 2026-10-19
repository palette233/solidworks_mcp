#!/usr/bin/env python3
"""Build the fail-closed optical/process preflight for the selected scanner slot."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.cross_project_scanner_process_preflight import (  # noqa: E402
    build_scanner_process_preflight,
)


CASE = (
    ROOT
    / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
    "project01_JJ00_project03_AI00"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    report = build_scanner_process_preflight(
        _read(CASE / "scanner_slot_discovery.json"),
        _read(CASE / "endpoint_recovery_evidence.json"),
        _read(
            ROOT
            / "demo/cross_project_substitution/transport-v1/"
            "cross_project_substitution_catalog.json"
        ),
        target_process_module_token="SS00",
    )
    output = CASE / "scanner_process_preflight.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = CASE / "scanner_process_preflight.md"
    markdown.write_text(
        "\n".join(
            [
                "# Scanner process preflight",
                "",
                f"- Status: `{report['status']}`",
                f"- CAD insertion allowed: `{report['cadInsertionAllowed']}`",
                f"- Native-station displacement: `{report['mechanicalCandidate']['nativeStationDisplacementMeters']}` m",
                f"- Missing evidence: `{', '.join(report['missingEvidence'])}`",
                f"- Next action: `{report['nextAction']}`",
                "",
                "Mechanical hole compatibility is not optical-process compatibility.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
