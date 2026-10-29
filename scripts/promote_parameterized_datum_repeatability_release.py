#!/usr/bin/env python3
"""Promote already completed dual-pose CAD evidence without rerunning CAD."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
sys.path.insert(0, str(ROOT / "scripts"))

from demo_backend.parameterized_datum_placement import (  # noqa: E402
    publish_parameterized_datum_pair_release,
)
from run_parameterized_datum_validation_queue import (  # noqa: E402
    _publish_relation_authority,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish authenticated finite-support repeatability evidence."
    )
    parser.add_argument("source_candidate", type=Path)
    parser.add_argument("output_candidate", type=Path)
    args = parser.parse_args()
    source = args.source_candidate.resolve()
    output = args.output_candidate.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite promotion directory: {output}")
    package_path = source / "validation-package.json"
    result_path = source / "cad-result.json"
    package = _read(package_path)
    result = _read(result_path)
    witness = result.get("externalPlacementRepeatability") or {}
    if witness.get("passed") is not True:
        raise RuntimeError("source candidate has no passing repeatability witness")
    release = publish_parameterized_datum_pair_release(package, result)
    output.mkdir(parents=True)
    # The relation publisher deliberately replays the pair-release checks from
    # the package and CAD result found in the candidate directory.  Materialize
    # those immutable inputs here instead of asking it to trust a promoted
    # boolean or a release file in isolation.  Paths embedded in the package
    # continue to point at the original authenticated graph/endpoints/CAD
    # output, whose hashes are checked again by the publisher.
    shutil.copy2(package_path, output / "validation-package.json")
    shutil.copy2(result_path, output / "cad-result.json")
    _write(output / "pair-release.json", release)
    provenance = {
        "schemaVersion": "parameterized-datum-repeatability-promotion/v1",
        "sourceCandidateDirectory": str(source),
        "sourceValidationPackagePath": str(package_path),
        "sourceCadResultPath": str(result_path),
        "pairReleaseId": release["releaseId"],
        "pairReleaseDigest": release["releaseDigest"],
        "cadRerun": False,
        "reason": (
            "The two CAD variants had already completed successfully; only the "
            "release identity was upgraded to bind their repeatability witness."
        ),
    }
    _write(output / "promotion-provenance.json", provenance)
    try:
        relation = _publish_relation_authority(output)
    except Exception as exc:
        _write(
            output / "release-candidate-status.json",
            {
                "schemaVersion": "parameterized-datum-release-candidate-status/v1",
                "status": "failed",
                "pairReleaseId": release["releaseId"],
                "errorType": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise
    _write(output / "promotion-result.json", {"pairRelease": release, "relation": relation})
    _write(
        output / "release-candidate-status.json",
        {
            "schemaVersion": "parameterized-datum-release-candidate-status/v1",
            "status": "released",
            "pairReleaseId": release["releaseId"],
            "relationReleaseId": relation["relationRelease"]["releaseId"],
        },
    )
    print(json.dumps({"release": release["releaseId"], "relation": relation["relationRelease"]["releaseId"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
