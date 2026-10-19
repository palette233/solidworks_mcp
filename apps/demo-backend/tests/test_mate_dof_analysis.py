from demo_backend.mate_dof_analysis import analyze_target_mate_dof


def endpoint(index, token, normal, center):
    return {
        "Index": index,
        "ModuleToken": token,
        "GeometryType": "Face",
        "FaceNormalWorld": normal,
        "FaceCenterWorld": center,
    }


def cylinder_endpoint(index, token, axis, origin):
    return {
        "Index": index,
        "ModuleToken": token,
        "GeometryType": "Face",
        "SurfaceType": "Cylinder",
        "CylinderAxisWorld": axis,
        "CylinderOriginWorld": origin,
    }


def slot_mate(constraint=0):
    return {
        "MateName": "slot-x",
        "MateType": 21,
        "ModuleTokens": ["A700", "A600"],
        "IsSuppressed": False,
        "Endpoints": [
            cylinder_endpoint(0, "A700", [0, 1, 0], [0.2, 0.1, 0.3]),
            cylinder_endpoint(1, "A600", [0, 1, 0], [0.1, 0.1, 0.3]),
        ],
        "AdvancedOptions": {"SlotConstraint": constraint},
        "AnalysisGeometry": {"SlotDirectionWorld": [1, 0, 0]},
    }


def graph(normals):
    mates = []
    for index, normal in enumerate(normals):
        mates.append({
            "MateName": f"plane-{index}",
            "MateType": 0,
            "ModuleTokens": ["A700", "A600"],
            "IsSuppressed": False,
            "Endpoints": [
                endpoint(0, "A700", normal, [0.1 * index, 0.2 * index, 0.3 * index]),
                endpoint(1, "A600", [-value for value in normal], [0, 0, 0]),
            ],
        })
    return {
        "Modules": [{"ModuleToken": "A700"}, {"ModuleToken": "A600"}],
        "Mates": mates,
    }


def test_one_plane_leaves_three_rigid_body_dof():
    result = analyze_target_mate_dof(graph([[0, 1, 0]]), "A700")
    assert result["constraintRank"] == 3
    assert result["residualDof"] == 3
    assert result["closed"] is False
    assert len(result["residualDofBasis"]) == 3


def test_two_nonparallel_planes_leave_one_translation_dof():
    result = analyze_target_mate_dof(graph([[1, 0, 0], [0, 1, 0]]), "A700")
    assert result["constraintRank"] == 5
    assert result["residualDof"] == 1


def test_three_orthogonal_planes_close_six_dof():
    result = analyze_target_mate_dof(
        graph([[1, 0, 0], [0, 1, 0], [0, 0, 1]]), "A700"
    )
    assert result["constraintRank"] == 6
    assert result["residualDof"] == 0
    assert result["closed"] is True
    assert result["residualDofBasis"] == []


def test_unsupported_geometry_is_fail_closed():
    value = graph([[0, 1, 0]])
    value["Mates"][0]["Endpoints"][0].pop("FaceNormalWorld")
    result = analyze_target_mate_dof(value, "A700")
    assert result["constraintRank"] == 0
    assert result["residualDof"] == 6
    assert result["unsupportedRelations"]


def test_width_center_plane_adds_one_conservative_constraint():
    value = graph([[0, 1, 0], [1, 0, 0]])
    value["Mates"].insert(
        1,
        {
            "MateName": "width-z",
            "MateType": 11,
            "ModuleTokens": ["A700", "A600"],
            "IsSuppressed": False,
            "Endpoints": [
                endpoint(0, "A700", [0, 0, 1], [0, 0, 0.25]),
                endpoint(1, "A700", [0, 0, -1], [0, 0, -0.25]),
                endpoint(2, "A600", [0, 0, 1], [0, 0, 0.5]),
                endpoint(3, "A600", [0, 0, -1], [0, 0, -0.5]),
            ],
        },
    )

    result = analyze_target_mate_dof(value, "A700")

    assert result["constraintRank"] == 6
    assert result["residualDof"] == 0
    width = next(row for row in result["relations"] if row["mateName"] == "width-z")
    assert width["independentConstraintCount"] == 1
    assert width["conservativeModel"] == "width_center_plane_offset_only"


def test_concentric_cylinders_leave_axis_translation_and_rotation_free():
    value = {
        "Modules": [{"ModuleToken": "A700"}, {"ModuleToken": "A600"}],
        "Mates": [{
            "MateName": "concentric-z",
            "MateType": 1,
            "ModuleTokens": ["A700", "A600"],
            "IsSuppressed": False,
            "Endpoints": [
                cylinder_endpoint(0, "A700", [0, 0, 1], [0.2, 0.1, 0]),
                cylinder_endpoint(1, "A600", [0, 0, -1], [0, 0, 0]),
            ],
        }],
    }

    result = analyze_target_mate_dof(value, "A700")

    assert result["constraintRank"] == 4
    assert result["residualDof"] == 2
    relation = result["relations"][0]
    assert relation["conservativeModel"] == "coaxial_axis_alignment_four_constraints"


def test_concentric_without_analytic_axis_is_fail_closed():
    value = {
        "Modules": [{"ModuleToken": "A700"}, {"ModuleToken": "A600"}],
        "Mates": [{
            "MateName": "concentric-missing-axis",
            "MateType": 1,
            "ModuleTokens": ["A700", "A600"],
            "IsSuppressed": False,
            "Endpoints": [
                endpoint(0, "A700", None, [0, 0, 0]),
                endpoint(1, "A600", None, [0, 0, 0]),
            ],
        }],
    }

    result = analyze_target_mate_dof(value, "A700")

    assert result["constraintRank"] == 0
    assert result["residualDof"] == 6
    assert result["unsupportedRelations"][0]["reason"].startswith(
        "concentric_axis_geometry_missing"
    )


def test_free_slot_keeps_along_slot_translation_and_axis_translation_rotation():
    value = {
        "Modules": [{"ModuleToken": "A700"}, {"ModuleToken": "A600"}],
        "Mates": [slot_mate(0)],
    }

    result = analyze_target_mate_dof(value, "A700")

    assert result["constraintRank"] == 3
    assert result["residualDof"] == 3
    assert result["relations"][0]["slotConstraintName"] == "free"


def test_positioned_slot_adds_along_slot_constraint():
    value = {
        "Modules": [{"ModuleToken": "A700"}, {"ModuleToken": "A600"}],
        "Mates": [slot_mate(2)],
    }

    result = analyze_target_mate_dof(value, "A700")

    assert result["constraintRank"] == 4
    assert result["residualDof"] == 2
    assert result["relations"][0]["slotConstraintName"] == "distance"


def test_slot_wall_on_target_uses_explicit_axis_and_context_pin_reference():
    mate = slot_mate(0)
    mate["Endpoints"] = [
        endpoint(0, "A700", [0, 0, -1], [0.2, 0.1, 0.3]),
        cylinder_endpoint(1, "A600", [0, 1, 0], [0.1, 0.1, 0.3]),
    ]
    mate["AnalysisGeometry"]["SlotAxisWorld"] = [0, 1, 0]
    mate["AnalysisGeometry"]["SlotReferencePointWorld"] = [0.1, 0.1, 0.3]
    value = {
        "Modules": [{"ModuleToken": "A700"}, {"ModuleToken": "A600"}],
        "Mates": [mate],
    }

    result = analyze_target_mate_dof(value, "A700")

    assert result["constraintRank"] == 3
    assert result["residualDof"] == 3
    assert result["unsupportedRelations"] == []


def test_slot_without_derived_direction_fails_closed():
    mate = slot_mate(0)
    mate.pop("AnalysisGeometry")
    value = {
        "Modules": [{"ModuleToken": "A700"}, {"ModuleToken": "A600"}],
        "Mates": [mate],
    }

    result = analyze_target_mate_dof(value, "A700")

    assert result["constraintRank"] == 0
    assert result["unsupportedRelations"][0]["reason"].startswith(
        "slot_direction_geometry_missing"
    )
