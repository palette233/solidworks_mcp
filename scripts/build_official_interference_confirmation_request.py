#!/usr/bin/env python3
"""Build exact component-pair confirmation requests from provisional new hits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def component_signature(component: dict[str, Any]) -> tuple[str, str]:
    name = str(component.get("Name", component.get("name", "")))
    leaf = name.rsplit("/", 1)[-1].casefold()
    path = str(component.get("Path", component.get("path", ""))).replace("/", "\\")
    source = path.rsplit("\\", 1)[-1].casefold()
    return source, leaf


def signature_key(first: tuple[str, str], second: tuple[str, str]) -> tuple[tuple[str, str], tuple[str, str]]:
    return tuple(sorted((first, second)))  # type: ignore[return-value]


def build_request(
    report: dict[str, Any], comparison: dict[str, Any], first_token: str, second_token: str
) -> dict[str, Any]:
    matches = []
    for row in report.get("exactChecks", []):
        pair_text = " ".join(str(value) for value in row.get("pair", []))
        if first_token.casefold() in pair_text.casefold() and second_token.casefold() in pair_text.casefold():
            matches.append(row)
    if len(matches) != 1:
        raise ValueError(
            f"Expected one exact check for {first_token}/{second_token}; found {len(matches)}"
        )
    wanted = set()
    for item in comparison.get("newInterferenceSignatures", []):
        wanted.add(
            signature_key(
                (
                    str(item["first"]["sourceFile"]).casefold(),
                    str(item["first"]["leafInstance"]).casefold(),
                ),
                (
                    str(item["second"]["sourceFile"]).casefold(),
                    str(item["second"]["leafInstance"]).casefold(),
                ),
            )
        )
    hierarchy_pairs: list[tuple[str, str]] = []
    for item in matches[0]["result"].get("InterferingBodyPairs", []):
        first = item.get("FirstComponent", {})
        second = item.get("SecondComponent", {})
        if signature_key(component_signature(first), component_signature(second)) not in wanted:
            continue
        first_hierarchy = str(first.get("HierarchyPath", first.get("Name", "")))
        second_hierarchy = str(second.get("HierarchyPath", second.get("Name", "")))
        pair = (first_hierarchy, second_hierarchy)
        if pair not in hierarchy_pairs:
            hierarchy_pairs.append(pair)
    return {
        "schemaVersion": "official-interference-confirmation-request/v1",
        "modulePair": matches[0]["pair"],
        "requestedSignatureCount": len(wanted),
        "requestedLeafComponentPairCount": len(hierarchy_pairs),
        "ExactCheckComplete": False,
        "FailedBodyPairCount": len(hierarchy_pairs),
        "Failures": [
            f"{first} <-> {second}: official confirmation requested"
            for first, second in hierarchy_pairs
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-report", required=True, type=Path)
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--first-token", required=True)
    parser.add_argument("--second-token", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = build_request(
        load(args.candidate_report),
        load(args.comparison),
        args.first_token,
        args.second_token,
    )
    if payload["requestedLeafComponentPairCount"] == 0:
        raise ValueError("No candidate leaf component pair matched the provisional signatures")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "pairCount": payload["requestedLeafComponentPairCount"], "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
