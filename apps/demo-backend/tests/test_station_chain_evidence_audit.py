"""Offline guards: an evidence audit must never repair a missing CAD run."""
import importlib.util
from pathlib import Path
import sys

import pytest


def module():
    scripts = Path(__file__).resolve().parents[3] / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("station_evidence_audit_test", scripts / "audit_station_chain_evidence.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_missing_checkpoint_never_enters_cad_capable_verifier(tmp_path, monkeypatch):
    audit = module()
    monkeypatch.setattr(audit.cli, "read", lambda path: {"stages": [{"stageId": "missing"}], "chainSha256": "same"})
    monkeypatch.setattr(audit.cli, "sha", lambda path: "same")
    def forbidden(*args, **kwargs):
        pytest.fail("Must not enter checkpoint verifier with missing report")
    monkeypatch.setattr(audit.cli, "verify_stage_checkpoint", forbidden)
    with pytest.raises(ValueError, match="Missing committed"):
        audit.audit_chain(tmp_path)


def test_changed_chain_rejected_before_any_checkpoint(tmp_path, monkeypatch):
    audit = module()
    monkeypatch.setattr(audit.cli, "read", lambda path: {"chainSha256": "original"})
    monkeypatch.setattr(audit.cli, "sha", lambda path: "changed")
    with pytest.raises(ValueError, match="Compiled chain changed"):
        audit.audit_chain(tmp_path)
