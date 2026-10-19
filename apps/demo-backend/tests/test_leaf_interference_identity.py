from scripts.capture_leaf_interference_details import (
    component_interference_identity,
    interfering_leaf_pair_set,
)


def component(path: str, name: str):
    return {"Path": path, "Name": f"parent/{name}"}


def test_identity_is_stable_across_copied_project_directories():
    first = component(r"D:\project01\FL222AC-00056.SLDPRT", "FL222AC-00056-1")
    second = component(r"D:\project02\FL222AC-00056.SLDPRT", "FL222AC-00056-1")
    assert component_interference_identity(first) == component_interference_identity(second)


def test_identity_still_distinguishes_part_and_occurrence():
    first = component(r"D:\p\FL222AC-00056.SLDPRT", "FL222AC-00056-1")
    other_part = component(r"D:\p\FL222AC-00058.SLDPRT", "FL222AC-00058-1")
    other_occurrence = component(r"D:\p\FL222AC-00056.SLDPRT", "FL222AC-00056-2")
    assert component_interference_identity(first) != component_interference_identity(other_part)
    assert component_interference_identity(first) != component_interference_identity(other_occurrence)


def test_candidate_and_baseline_sets_match_when_only_copy_root_changes():
    def payload(root: str):
        return {
            "InterferingBodyPairs": [
                {
                    "FirstComponent": component(root + r"\frame.SLDPRT", "frame-1"),
                    "SecondComponent": component(root + r"\ccd.SLDPRT", "ccd-1"),
                }
            ]
        }

    assert interfering_leaf_pair_set(payload(r"D:\project01")) == interfering_leaf_pair_set(
        payload(r"D:\project02")
    )
