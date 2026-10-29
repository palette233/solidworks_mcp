from copy import deepcopy
from pathlib import Path

import pytest

from demo_backend.native_cleaning_station import build_native_cleaning_station
from demo_backend.station_rule_registry import read, sha


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "data/assembly_stations/cleaning-n000-a000-native-v1.json"
GROUPED_CONFIG = ROOT / "data/assembly_stations/cleaning-gn00-jj00-native-v1.json"


def config():
    return read(CONFIG)


def native_modules(cfg):
    graph = read(ROOT / cfg["inputs"]["nativeGraph"])
    source = next(
        row for row in graph["Modules"]
        if row["ModuleToken"] == cfg["sourceToken"]
        and row["HierarchyPath"] == cfg["nativeInstanceHierarchyPath"]
    )
    base = next(
        row for row in graph["Modules"]
        if row["ModuleToken"] == cfg["baseToken"]
        and row["HierarchyPath"] == cfg["baseInstanceHierarchyPath"]
    )
    return source, base


def saved_state(tmp_path, cfg, *, source_shift=0.0):
    source, base = native_modules(cfg)
    assembly = tmp_path / "saved.SLDASM"
    assembly.write_bytes(b"offline saved-state fixture; not CAD evidence")
    transform = list(source["SourceTransform"])
    transform[9] += source_shift
    return {
        "success": True,
        "assemblyPath": str(assembly),
        "assemblySha256": sha(assembly),
        "observed": {
            "readOnly": True,
            "components": [
                {
                    "name": "base-1",
                    "sourcePath": base["Path"],
                    "configuration": "Default",
                    "isFixed": True,
                    "solvingState": 0,
                    "transform": base["SourceTransform"],
                },
                {
                    "name": "cleaning-1",
                    "sourcePath": source["Path"],
                    "configuration": "Default",
                    "isFixed": False,
                    "solvingState": 0,
                    "transform": transform,
                },
            ],
        },
    }


def test_real_n000_measurement_binds_three_separate_service_groups():
    report = build_native_cleaning_station(ROOT, config())
    proxy = report["serviceProxy"]
    assert [row["subtree"] for row in proxy["includedGroups"]] == [
        "FL9C251093NB00.001-1",
        "FL9C251093NC00.001-1",
        "FL9C251093ND00.001-1",
    ]
    assert proxy["excludedGroups"] == ["FL9C251093NA00.001-1"]
    assert proxy["proxyGeometryPassed"] is None
    assert report["mechanicalPlacementAuthority"]["sourceWorldPoseCopied"] is False
    assert report["functionalPassed"] is None


def test_real_gn00_grouped_subtree_capture_binds_four_service_groups():
    report = build_native_cleaning_station(ROOT, read(GROUPED_CONFIG))
    proxy = report["serviceProxy"]
    assert proxy["captureMode"] == "complete_grouped_subtree_unions"
    assert [row["subtree"] for row in proxy["includedGroups"]] == [
        "FJ00",
        "GN10",
        "GN20",
        "GN30",
    ]
    assert proxy["excludedGroups"] == ["GN00-common-support"]
    assert proxy["proxyGeometryPassed"] is None
    assert report["mechanicalPlacementAuthority"]["sourceWorldPoseCopied"] is False
    assert report["newCadExecuted"] is False


def test_grouped_capture_frame_mismatch_fails_closed(monkeypatch):
    from demo_backend import native_cleaning_station as native

    original = native.read

    def changed(path):
        payload = deepcopy(original(path))
        if Path(path).name == "project01_module_occupancy.json":
            payload["modules"]["GN00"]["prototypeAnchorInstallationMeters"]["u"] += 0.01
        return payload

    monkeypatch.setattr(native, "read", changed)
    with pytest.raises(ValueError, match="graph frames disagree"):
        build_native_cleaning_station(ROOT, read(GROUPED_CONFIG))


def test_native_saved_pose_reprojects_all_groups_within_tolerance(tmp_path):
    cfg = config()
    report = build_native_cleaning_station(ROOT, cfg, saved_state(tmp_path, cfg))
    assert report["proxyGeometryPassed"] is True
    assert all(row["maximumBoundErrorMeters"] < 1e-12 for row in report["serviceProxy"]["observations"])
    assert report["stateBinding"]["sourceFixed"] is False
    assert report["stateBinding"]["baseFixed"] is True


def test_shifted_cleaning_root_fails_service_station_proxy(tmp_path):
    cfg = config()
    report = build_native_cleaning_station(ROOT, cfg, saved_state(tmp_path, cfg, source_shift=0.01))
    assert report["proxyGeometryPassed"] is False
    assert all(row["maximumBoundErrorMeters"] > 0.009 for row in report["serviceProxy"]["observations"])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("nativeRoleModuleDefinitionId", "project03::AG00", "explicit service-group correspondence"),
        ("nativeInstanceHierarchyPath", "FL9C251093N000.001-3", "identities disagree"),
        ("expectedGlobalTemplateId", "template/not-authorized", "does not authorize"),
        ("occupancySource", "leaf-subtree-unions", "complete captured leaf occupancy"),
    ],
)
def test_identity_release_and_capture_scope_fail_closed(field, value, message):
    cfg = config()
    cfg[field] = value
    with pytest.raises(ValueError, match=message):
        build_native_cleaning_station(ROOT, cfg)


def test_only_base_may_be_fixed(tmp_path):
    cfg = config()
    state = saved_state(tmp_path, cfg)
    state["observed"]["components"][1]["isFixed"] = True
    with pytest.raises(ValueError, match="only the base"):
        build_native_cleaning_station(ROOT, cfg, state)


def test_label_file_and_capture_inputs_are_hash_pinned_by_config():
    cfg = config()
    for key, expected in cfg["inputSha256"].items():
        assert sha(ROOT / cfg["inputs"][key]) == expected
