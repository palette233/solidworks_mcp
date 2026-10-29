"""Read-only comparisons for cumulative rigid-module assembly evidence.

These checks compare measured CAD states, not transforms copied from a design
graph. Collision, fastening and functional process validity are out of scope.
"""
from __future__ import annotations

import math
import ntpath
from typing import Any

from .rigid_transform_interpolation import relative_transform


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _rigid(values):
    if not isinstance(values, list) or len(values) != 16 or not all(_finite(v) for v in values):
        return False
    if abs(values[12]-1) > 1e-8 or any(abs(v)>1e-8 for v in values[13:]):
        return False
    axes = [values[i:i+3] for i in (0, 3, 6)]
    if any(abs(sum(a*b for a,b in zip(axes[i],axes[j]))-int(i==j))>1e-7 for i in range(3) for j in range(3)):
        return False
    a,b,c=axes
    determinant=a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
    return abs(determinant-1)<1e-7


def _components(state):
    rows = (state.get("observed") or {}).get("components") or []
    result = {}
    for row in rows:
        source = str(row.get("sourcePath") or "")
        if not ntpath.isabs(source):
            raise ValueError("组件源路径缺失。")
        key = ntpath.normcase(ntpath.normpath(source))
        if key in result:
            raise ValueError("此比较需要唯一模组实例，不能按源文件合并重复实例。")
        if not _rigid(row.get("transform")):
            raise ValueError("组件变换不是有效刚体变换。")
        if not isinstance(row.get("configuration"), str) or not row["configuration"]:
            raise ValueError("未观测配置。")
        if type(row.get("solvingState")) is not int or row["solvingState"] not in (0,1):
            raise ValueError("未观测有效刚柔状态。")
        if type(row.get("constrainedStatus")) is not int or row["constrainedStatus"] not in (2,3):
            raise ValueError("未观测有效约束状态。")
        result[key]=row
    if not result:
        raise ValueError("组件列表为空。")
    return result


def compare_cad_states(before: dict, after: dict, *, base_token: str,
                       added_token: str | None = None, moved_token: str | None = None,
                       expected_displacement_meters: list[float] | None = None,
                       mate_name_map: dict[str, str] | None = None,
                       expected_parameter_changes: dict[str, tuple[float, float]] | None = None,
                       translation_tolerance=1e-6, rotation_tolerance=1e-6) -> dict[str, Any]:
    """Compare same chain/order, append preservation, or one signed translation.

    Displacement is expressed in the observed base's local frame. For a parameter
    edit supply its analytically derived signed vector, not the measured delta.
    """
    if moved_token and (not isinstance(expected_displacement_meters, list) or len(expected_displacement_meters)!=3 or not all(_finite(v) for v in expected_displacement_meters)):
        raise ValueError("参数变化需要独立给定有限的有符号位移。")
    expected_parameters = expected_parameter_changes or {}
    if moved_token and (len(expected_parameters)!=1 or any(
            not isinstance(values,(tuple,list)) or len(values)!=2 or not all(_finite(v) for v in values)
            for values in expected_parameters.values())):
        raise ValueError("参数响应验证必须绑定具体配合名与修改前后数值。")
    if not moved_token and expected_parameters:
        raise ValueError("非参数变化比较不接受参数修改期望。")
    left,right=_components(before),_components(after)
    base_key = next((k for k in left if f"{base_token.lower()}.001" in ntpath.basename(k)), None)
    if not base_key or base_key not in right:
        raise ValueError("没有唯一共同基座。")
    additions=set(right)-set(left)
    checks={
        "bothReadOnlyStatesPassed": all(s.get("success") is True and s.get("observed",{}).get("readOnly") is True for s in (before,after)),
        "sourceSetCorrect": set(left)<=set(right) and (len(additions)==1 and any(f"{added_token.lower()}.001" in ntpath.basename(k) for k in additions) if added_token else not additions),
        "onlyBaseFixed": all(all(row.get("isFixed") is (key==base_key) for key,row in rows.items()) for rows in (left,right)),
        "movingRootsFullyConstrained": all(row["constrainedStatus"]==3 for rows in (left,right) for key,row in rows.items() if key!=base_key),
    }
    results=[]
    for key,row in left.items():
        other=right.get(key)
        if not other:
            checks["sourceSetCorrect"]=False
            continue
        a=relative_transform(left[base_key]["transform"],row["transform"])
        b=relative_transform(right[base_key]["transform"],other["transform"])
        delta=[b[i]-a[i] for i in (9,10,11)]
        moving=bool(moved_token and f"{moved_token.lower()}.001" in ntpath.basename(key))
        expected=expected_displacement_meters if moving else [0.,0.,0.]
        error=math.dist(delta,expected)
        frob=math.sqrt(sum((x-y)**2 for x,y in zip(a[:9],b[:9])))
        rotation=2*math.asin(min(1.,frob/(2*math.sqrt(2))))
        results.append({"sourcePath":row["sourcePath"],"movedTarget":moving,"observedDisplacementMeters":delta,
                        "expectedDisplacementMeters":expected,"translationErrorMeters":error,"rotationErrorRadians":rotation,
                        "posePassed":error<=translation_tolerance and rotation<=rotation_tolerance,
                        "semanticsMatch":all(row[k]==other[k] for k in ("configuration","solvingState","constrainedStatus","isFixed"))})
    checks["allExpectedPosesMatch"]=len(results)==len(left) and all(r["posePassed"] for r in results)
    checks["componentSemanticsPreserved"]=all(r["semanticsMatch"] for r in results)
    if moved_token:
        checks["exactlyOneMovedTarget"]=sum(r["movedTarget"] for r in results)==1
    mates=[]
    rename = mate_name_map or {}
    if len(set(rename.values())) != len(rename):
        raise ValueError("新旧配合名称映射必须一一对应。")
    reverse = {new:old for old,new in rename.items()}
    for index,state in enumerate((before,after)):
        raw=state.get("observed",{}).get("allTopLevelMates") or []
        by_name={r["name"]:r for r in raw if r.get("name")}
        if len(by_name)!=len(raw) or not raw:
            raise ValueError("配合名字缺失/重复，或没有观测到配合。")
        if index == 1 and rename:
            if not set(reverse) <= set(by_name):
                raise ValueError("参数化模板的新配合名称没有实测证据。")
            by_name = {reverse.get(name,name):row for name,row in by_name.items()}
            if len(by_name)!=len(raw):
                raise ValueError("配合名称归一化产生重复。")
        mates.append(by_name)
    if not set(rename) <= set(mates[0]):
        raise ValueError("旧配合名称映射没有实测证据。")
    checks["allMatesActiveAndClean"]=all(r.get("isSuppressed") is False and type(r.get("errorCode")) is int and r["errorCode"]==0 for group in mates for r in group.values())
    # A moved parameter may alter one dimension, but must not remove original mates.
    checks["oldMateNamesPreserved"]=set(mates[0])<=set(mates[1])
    changed=[]
    for name,a in mates[0].items():
        b=mates[1].get(name,{})
        if any(k not in a or k not in b or a[k]!=b[k] for k in ("mateType","alignment","isSuppressed","errorCode")):
            checks["oldMateNamesPreserved"]=False
        if a.get("dimensionSystemValue")!=b.get("dimensionSystemValue"):
            x,y=a.get("dimensionSystemValue"),b.get("dimensionSystemValue")
            if not (_finite(x) and _finite(y) and abs(x-y)<=1e-8):
                changed.append({"name":name,"before":x,"after":y})
    checks["parameterChangesExpected"]=(set(c["name"] for c in changed)==set(expected_parameters)
        and all(abs(c["before"]-expected_parameters[c["name"]][0])<=1e-8
                and abs(c["after"]-expected_parameters[c["name"]][1])<=1e-8 for c in changed))
    if not added_token:
        checks["mateNamesEqual"]=set(mates[0])==set(mates[1])
    else:
        checks["exactlyThreeMatesAdded"]=len(set(mates[1])-set(mates[0]))==3
    return {"schemaVersion":"datum-chain-state-comparison/v1","success":all(v is True for v in checks.values()),
            "checks":checks,"moduleComparisons":results,"changedParameters":changed,"mateNameMap":rename,
            "expectedParameterChanges":expected_parameters,
            "collisionOrBrep":"not_evaluated","actualFasteningMethod":"not_verified"}
