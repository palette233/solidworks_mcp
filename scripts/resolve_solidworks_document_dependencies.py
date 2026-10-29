#!/usr/bin/env python3
"""Resolve missing saved SolidWorks references by exact filename under narrow roots."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_resolution(inventory_path: Path, search_roots: list[Path]) -> dict:
    clock = perf_counter()
    inventory_path = inventory_path.resolve()
    inventory = _read(inventory_path)
    if inventory.get("schemaVersion") != "solidworks-document-dependency-inventory/v1":
        raise ValueError("unsupported SolidWorks dependency inventory")
    assembly = Path(str(inventory.get("assemblyPath") or "")).resolve()
    if not assembly.is_file() or _sha(assembly) != inventory.get("assemblySha256"):
        raise ValueError("dependency inventory assembly is missing or changed")
    roots = [root.resolve() for root in search_roots]
    if not roots or any(not root.is_dir() for root in roots):
        raise ValueError("all reference search roots must be existing directories")
    index: dict[str, list[Path]] = {}
    for root in roots:
        for candidate in root.rglob("*"):
            if candidate.is_file():
                index.setdefault(candidate.name.casefold(), []).append(candidate.resolve())
    mappings, unresolved, ambiguous = [], [], []
    for row in inventory.get("dependencies") or []:
        if row.get("pathExists") is True:
            continue
        saved = str(row.get("savedPath") or "")
        matches = sorted(set(index.get(Path(saved).name.casefold(), [])))
        if len(matches) == 1:
            resolved = matches[0]
            mappings.append(
                {
                    "documentName": row.get("documentName"),
                    "savedPath": saved,
                    "resolvedPath": str(resolved),
                    "sha256": _sha(resolved),
                }
            )
        elif matches:
            ambiguous.append(
                {
                    "documentName": row.get("documentName"),
                    "savedPath": saved,
                    "matches": [str(match) for match in matches],
                }
            )
        else:
            unresolved.append(
                {"documentName": row.get("documentName"), "savedPath": saved}
            )
    missing_count = int(inventory.get("missingDependencyCount") or 0)
    return {
        "schemaVersion": "solidworks-reference-resolution-manifest/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter() - clock,
        "dependencyInventory": {
            "path": str(inventory_path),
            "sha256": _sha(inventory_path),
        },
        "assemblyPath": str(assembly),
        "assemblySha256": inventory["assemblySha256"],
        "searchRoots": [str(root) for root in roots],
        "missingDependencyCount": missing_count,
        "resolvedCount": len(mappings),
        "unresolvedCount": len(unresolved),
        "ambiguousCount": len(ambiguous),
        "mappings": mappings,
        "unresolved": unresolved,
        "ambiguous": ambiguous,
        "success": len(mappings) == missing_count and not unresolved and not ambiguous,
        "claimBoundary": (
            "Exact-filename path recovery only. It does not rewrite the assembly, "
            "prove geometric equivalence, or relax CAD acceptance."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--search-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite resolution manifest: {args.output}")
    report = build_resolution(args.inventory, args.search_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
