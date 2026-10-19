from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project_assembly_profile import load_project_assembly_profile


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assembly_path(payload: dict[str, Any]) -> str:
    direct = payload.get("assemblyPath") or payload.get("finalAssemblyPath")
    if direct:
        return str(direct)
    nested = payload.get("assembly") or {}
    return str(nested.get("path") or nested.get("assemblyPath") or "")


def build_index(project_id: str) -> dict[str, Any]:
    profile = load_project_assembly_profile(project_id)
    artifacts = profile["artifacts"]
    mapping = artifacts.get("orderedStepClosures") or {}
    base = str(profile["baseModule"])
    expected = [str(token) for token in profile["validatedSequence"] if str(token) != base]
    if set(mapping) != set(expected):
        raise ValueError(
            f"{project_id} orderedStepClosures coverage mismatch; "
            f"missing={sorted(set(expected)-set(mapping))}, extra={sorted(set(mapping)-set(expected))}"
        )
    steps = []
    for token in expected:
        evidence = (WORKSPACE / str(mapping[token])).resolve()
        if not evidence.is_file():
            raise FileNotFoundError(f"{token} closure evidence does not exist: {evidence}")
        payload = json.loads(evidence.read_text(encoding="utf-8-sig"))
        if payload.get("success") is not True:
            raise ValueError(f"{token} closure is not successful: {evidence}")
        raw_assembly = assembly_path(payload)
        assembly = Path(raw_assembly)
        if not assembly.is_absolute():
            assembly = WORKSPACE / assembly
        assembly = assembly.resolve()
        if not assembly.is_file():
            raise FileNotFoundError(f"{token} assembly artifact does not exist: {assembly}")
        steps.append(
            {
                "moduleToken": token,
                "success": True,
                "assemblyPath": str(assembly),
                "assemblySha256": sha256(assembly),
                "evidencePath": str(evidence),
                "sourceStatus": payload.get("status"),
            }
        )
    full_closure = (WORKSPACE / str(artifacts["fullMachineClosure"])).resolve()
    output = (WORKSPACE / str(artifacts["orderedClosure"])).resolve()
    return {
        "schemaVersion": "validated-ordered-closure-index/v1",
        "projectId": project_id,
        "generatedAt": utc_now(),
        "success": True,
        "artifactReplaySafe": True,
        "sequence": [base, *expected],
        "steps": steps,
        "fullClosurePath": str(full_closure),
        "finalAssemblyPath": steps[-1]["assemblyPath"],
        "profileVersion": profile["profileVersion"],
        "profileDigest": profile["profileDigest"],
        "outputPath": str(output),
        "productionReady": False,
        "boundary": (
            "The index enables validated cumulative artifact replay only; "
            "it does not prove that a new live CAD run occurred."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_id", choices=["project01", "project03"])
    args = parser.parse_args()
    payload = build_index(args.project_id)
    output = Path(payload["outputPath"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "projectId": args.project_id, "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
