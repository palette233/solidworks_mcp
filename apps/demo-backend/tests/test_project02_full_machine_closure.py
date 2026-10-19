from scripts.summarize_project02_full_machine_closure import (
    canonical_pair,
    module_token,
    strict_aabb_separated,
)


def test_canonical_pair_is_order_independent():
    assert canonical_pair(("T401-1", "A200-1")) == canonical_pair(("A200-1", "T401-1"))
    assert module_token("A100_WITH_A150_SLOT0_RIGID_V3-1") == "A100"


def test_strict_aabb_separation_is_safe_on_any_axis():
    assert strict_aabb_separated([0, 0, 0, 1, 1, 1], [2, 0, 0, 3, 1, 1]) is True
    assert strict_aabb_separated([0, 0, 0, 1, 1, 1], [0.5, 0.5, 0.5, 2, 2, 2]) is False
    # Face contact is not strict separation and must therefore reach the exact gate.
    assert strict_aabb_separated([0, 0, 0, 1, 1, 1], [1, 0, 0, 2, 1, 1]) is False
