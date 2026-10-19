import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "replace_top_level_component_and_set_rigid.py"
)
SPEC = importlib.util.spec_from_file_location("replace_top_level_component_and_set_rigid", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_detects_needs_regen_by_decoded_warning_name():
    payload = {
        "Diagnostics": {
            "Warnings": [
                {
                    "Value": 32,
                    "Name": "swFileLoadWarning_NeedsRegen",
                    "Description": "Needs Regen.",
                }
            ]
        }
    }
    assert MODULE.open_needs_regen(payload) is True


def test_does_not_confuse_already_open_with_needs_regen():
    payload = {
        "Diagnostics": {
            "Warnings": [{"Name": "swFileLoadWarning_AlreadyOpen"}]
        }
    }
    assert MODULE.open_needs_regen(payload) is False


def test_rebuild_state_rejects_needs_rebuild_and_failed_summary():
    assert MODULE.rebuild_state_is_healthy({"NeedsRebuild": False, "Summary": "OK"})
    assert not MODULE.rebuild_state_is_healthy({"NeedsRebuild": True, "Summary": ""})
    assert not MODULE.rebuild_state_is_healthy(
        {"NeedsRebuild": False, "Summary": "Rebuild failed"}
    )


def health(*issues, blocking=False, ready=True, needs_rebuild=False):
    return {
        "ReadyForVerificationGate": ready,
        "HasBlockingIssues": blocking,
        "Rebuild": {"StatusAfter": {"NeedsRebuild": needs_rebuild, "Summary": "OK"}},
        "ActionableDiagnostics": {"CurrentIssues": list(issues)},
    }


def issue(code, name, warning=True):
    return {"ErrorCode": code, "ErrorName": name, "IsWarning": warning}


def test_baseline_health_accepts_same_nonblocking_warning():
    baseline = {"health": health(issue(51, "swSketchErrorExtRefFail"))}
    candidate = health(issue(51, "swSketchErrorExtRefFail"))
    assert MODULE.baseline_health_allows(candidate, baseline) is True


def test_baseline_health_rejects_new_issue_or_blocking_state():
    baseline = {"health": health(issue(51, "swSketchErrorExtRefFail"))}
    assert not MODULE.baseline_health_allows(
        health(issue(51, "swSketchErrorExtRefFail"), issue(6, "newError", False)),
        baseline,
    )
    assert not MODULE.baseline_health_allows(
        health(issue(51, "swSketchErrorExtRefFail"), blocking=True), baseline
    )
