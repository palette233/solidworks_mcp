import importlib.util
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "scripts/summarize_project05_released_permutation_cad.py"


def _module():
    spec = importlib.util.spec_from_file_location("project05_permutation_summary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_real_project05_released_permutations_close_cleanly():
    report = _module().build_report()

    assert report["status"] == "passed"
    assert report["checks"]["ordersAreReversePermutations"] is True
    assert report["checks"]["sameImmutableReleaseUsed"] is True
    assert report["collisionStatus"] == "not_evaluated"
    assert [case["actualOrder"] for case in report["cases"]] == [
        ["D000", "F000"],
        ["F000", "D000"],
    ]
    assert all(
        step["checks"]["noCaseAnchor"] is True
        for case in report["cases"]
        for step in case["steps"]
    )


def test_real_three_addon_permutations_close_cleanly():
    module = _module()
    report = module.build_report(
        (
            ("project05-job-5ccdb04e298d", ["D000", "F000", "M000"]),
            ("project05-job-2797a59ca15e", ["M000", "F000", "D000"]),
        ),
        "relation-v21-project05-d000-f000-m000-portable-driving-20261011",
    )

    assert report["status"] == "passed"
    assert report["checks"]["ordersAreReversePermutations"] is True
    assert [len(case["steps"]) for case in report["cases"]] == [3, 3]
    assert all(
        step["checks"]["requestedMateCountCreated"] is True
        for case in report["cases"]
        for step in case["steps"]
    )


def test_real_p000_and_f000_reverse_permutations_allow_mixed_mate_counts():
    module = _module()
    report = module.build_report(
        (
            ("project05-job-86d75a60f96b", ["P000", "F000"]),
            ("project05-job-fa4696e9edc0", ["F000", "P000"]),
        ),
        "relation-v25-project05-five-addon-portable-driving-20261011",
    )

    assert report["status"] == "passed"
    assert report["checks"]["ordersAreReversePermutations"] is True
    assert all(
        step["checks"]["requestedMateCountCreated"] is True
        for case in report["cases"]
        for step in case["steps"]
    )


def test_real_four_addon_permutations_preserve_flexible_internal_state():
    module = _module()
    report = module.build_report(
        (
            ("project05-job-79b398759907", ["D000", "F000", "M000", "G000"]),
            ("project05-job-b1c6ba3274a5", ["G000", "M000", "F000", "D000"]),
        ),
        "relation-v23-project05-four-addon-portable-driving-20261011",
    )

    assert report["status"] == "passed"
    assert report["checks"]["ordersAreReversePermutations"] is True
    assert [len(case["steps"]) for case in report["cases"]] == [4, 4]
    g000_steps = [
        step
        for case in report["cases"]
        for step in case["steps"]
        if step["moduleToken"] == "G000"
    ]
    assert len(g000_steps) == 2
    assert all(step["status"] == "passed" for step in g000_steps)
    assert all(
        step["constraintStateObservation"]["acceptedFlexibleInternalState"] is True
        for step in g000_steps
    )
