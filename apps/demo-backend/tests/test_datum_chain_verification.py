import copy

import pytest

from demo_backend.datum_chain_verification import compare_cad_states


def state(tokens=("AA00", "GN00")):
    identity=[1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.]
    return {"success": True, "observed":{"readOnly":True,
        "components":[{"sourcePath":f"D:/cad/FL9{t}.001.SLDASM", "name":f"FL9{t}.001-1",
            "transform":identity[:],"configuration":"Default","solvingState":0,
            "constrainedStatus":3,"isFixed":t=="AA00"} for t in tokens],
        "allTopLevelMates":[{"name":f"mate{i}","mateType":5,"alignment":0,
            "isSuppressed":False,"errorCode":0,"dimensionSystemValue":.354+i} for i in range(3)]}}


def test_equivalent_observations():
    first=state()
    assert compare_cad_states(first,copy.deepcopy(first),base_token="AA00")["success"]


def test_only_parameter_target_moves_signed():
    first=state()
    second=copy.deepcopy(first)
    second["observed"]["components"][1]["transform"][9]=.01
    second["observed"]["allTopLevelMates"][0]["dimensionSystemValue"]+=.01
    assert compare_cad_states(first,second,base_token="AA00",moved_token="GN00",expected_displacement_meters=[.01,0.,0.],expected_parameter_changes={"mate0":(.354,.364)})["success"]
    assert not compare_cad_states(first,second,base_token="AA00",moved_token="GN00",expected_displacement_meters=[-.01,0.,0.],expected_parameter_changes={"mate0":(.354,.364)})["success"]
    assert not compare_cad_states(first,second,base_token="AA00",moved_token="GN00",expected_displacement_meters=[.01,0.,0.],expected_parameter_changes={"mate1":(1.354,1.364)})["success"]
    assert not compare_cad_states(first,second,base_token="AA00",moved_token="GN00",expected_displacement_meters=[.01,0.,0.],expected_parameter_changes={"mate0":(.354,1.354)})["success"]
    with pytest.raises(ValueError):
        compare_cad_states(first,second,base_token="AA00",moved_token="GN00",expected_displacement_meters=[.01,0.,0.])


def test_missing_metadata_not_equivalent():
    first=state()
    first["observed"]["components"][1].pop("solvingState")
    with pytest.raises(ValueError):
        compare_cad_states(first,first,base_token="AA00")


def test_append_preserves_old_objects():
    first=state()
    second=state(("AA00","GN00","P000"))
    second["observed"]["allTopLevelMates"] += [{**m,"name":m["name"]+"new"} for m in first["observed"]["allTopLevelMates"]]
    assert compare_cad_states(first,second,base_token="AA00",added_token="P000")["success"]
    second["observed"]["components"][1]["transform"][10]=.002
    assert not compare_cad_states(first,second,base_token="AA00",added_token="P000")["success"]


def test_suppression_and_extra_parameter_changes_fail():
    first=state()
    second=copy.deepcopy(first)
    second["observed"]["allTopLevelMates"][0]["isSuppressed"]=True
    assert not compare_cad_states(first,second,base_token="AA00")["success"]
