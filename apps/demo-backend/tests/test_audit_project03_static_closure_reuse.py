from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_project03_static_closure_reuse import audit_closure_reuse  # noqa: E402
from finalize_project03_full_static_collision_closure import (  # noqa: E402
    integrity_manifest,
)


def test_reuse_audit_accepts_unchanged_registered_artifacts(tmp_path: Path) -> None:
    artifact = tmp_path / "assembly.SLDASM"
    artifact.write_bytes(b"assembly")
    closure = {
        "success": True,
        "status": "PASSED_FULL_STATIC_GEOMETRY_NO_NEW_INTERFERENCE",
        "integrity": integrity_manifest([artifact]),
    }

    result = audit_closure_reuse(closure)

    assert result["reusable"] is True
    assert result["validArtifactCount"] == 1


def test_reuse_audit_invalidates_changed_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "assembly.SLDASM"
    artifact.write_bytes(b"assembly")
    closure = {
        "success": True,
        "status": "PASSED_FULL_STATIC_GEOMETRY_NO_NEW_INTERFERENCE",
        "integrity": integrity_manifest([artifact]),
    }
    artifact.write_bytes(b"changed")

    result = audit_closure_reuse(closure)

    assert result["reusable"] is False
    assert result["invalidArtifacts"][0]["sha256Matches"] is False
