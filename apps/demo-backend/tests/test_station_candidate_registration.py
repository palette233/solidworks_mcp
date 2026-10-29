"""Offline registration tests; synthetic closures are not CAD evidence."""
import json
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import register_station_candidate_evidence as registration


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    def save(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path
    rule = {"ruleId": "cup", "validation": {"status": "candidate"},
            "evaluator": {"inputPath": "config.json"}}
    scope = save("scope.json", {"scope": "synthetic"})
    save("config.json", {"synthetic": True})
    registry = save("registry.json", {"scopePath": "scope.json", "rules": []})
    plan = save("plan.json", {"ruleBinding": {"rule": rule, "scopePath": str(scope)}})
    cad, state = save("cad.json", {}), save("state.json", {})
    monkeypatch.setattr(registration, "ROOT", tmp_path)
    monkeypatch.setattr(registration, "verify_station_stage", lambda *_a, **_k:
                        {"cadPassed": True, "targetStationValidated": True})
    monkeypatch.setattr(registration, "validate_rule", lambda *_a:
                        {"validatedStationRule": True, "blockingReasonCodes": []})
    return [registry, plan, cad, state, tmp_path / "new-registry.json"], save, rule


def test_register_preserves_input_and_does_not_grant_mechanical_authority(candidate):
    args, _, rule = candidate
    before = args[0].read_bytes()
    result = registration.register(*args)
    assert args[0].read_bytes() == before
    registered = json.loads(args[-1].read_text())["rules"][0]
    assert registered["validation"]["status"] == "experimental_cad_verified"
    assert registered["validation"]["configurationSha256"]
    assert not result["newCadExecuted"] and not result["mechanicalReleasePromoted"]
    assert rule["validation"] == {"status": "candidate"}


@pytest.mark.parametrize("failure", ["existing_output", "scope", "noncandidate", "cad", "station", "conflict", "duplicate", "validation"])
def test_registration_rejects_invalid_evidence_without_output(candidate, monkeypatch, failure):
    args, save, rule = candidate
    if failure == "existing_output": save("new-registry.json", {"keep": True})
    if failure == "scope":
        save("different-scope.json", {"scope": "other"})
        save("registry.json", {"scopePath": "different-scope.json", "rules": []})
    if failure == "noncandidate":
        plan = json.loads(args[1].read_text())
        plan["ruleBinding"]["rule"]["validation"]["status"] = "released_demo"
        save("plan.json", plan)
    if failure in {"cad", "station"}:
        monkeypatch.setattr(registration, "verify_station_stage", lambda *_a, **_k:
                            {"cadPassed": failure != "cad", "targetStationValidated": failure != "station"})
    if failure in {"conflict", "duplicate"}:
        other = deepcopy(rule)
        if failure == "conflict": other["changed"] = True
        save("registry.json", {"scopePath": "scope.json", "rules": [other] if failure == "conflict" else [other, other]})
    if failure == "validation":
        monkeypatch.setattr(registration, "validate_rule", lambda *_a:
                            {"validatedStationRule": False, "blockingReasonCodes": ["changed"]})
    with pytest.raises((ValueError, FileExistsError)):
        registration.register(*args)
    if failure == "existing_output": assert json.loads(args[-1].read_text()) == {"keep": True}
    else: assert not args[-1].exists()
