from demo_backend.relation_topology_audit import (
    annotate_relation_topology_with_catalog,
    audit_relation_topology,
)


def _profile() -> dict:
    return {
        "projectId": "project-x",
        "baseModule": "BASE",
        "modules": {
            "BASE": {"componentName": "BASE.001"},
            "TRANSPORT": {
                "componentName": "TRANSPORT.001",
                "assemblyPolicy": {"requires": ["BASE"]},
            },
            "SCAN": {
                "componentName": "LONGPREFIXSCAN.001",
                "assemblyPolicy": {"requires": ["TRANSPORT"]},
            },
            "SERVICE": {
                "componentNames": ["SERVICE.001", "LONGPREFIXAUX1.001"],
                "assemblyPolicy": {"requires": ["BASE", "TRANSPORT"]},
            },
        },
    }


def test_process_dependency_is_not_invented_as_mechanical_edge() -> None:
    result = audit_relation_topology(
        _profile(),
        [
            (
                "scan.json",
                {
                    "EditPolicy": {"caseAnchoredModuleTokens": []},
                    "Mates": [
                        {"ModuleTokens": ["LONGPREFIXSCAN", "BASE"]},
                    ],
                },
            )
        ],
    )

    assert result["mechanicalEdgeCount"] == 1
    assert result["nonStarMechanicalEdgeCount"] == 0
    assert {
        (row["targetModuleToken"], row["requiredModuleToken"])
        for row in result["processOnlyDependencies"]
    } >= {("SCAN", "TRANSPORT")}


def test_nonstar_edge_requires_pose_anchor_free_evidence_to_be_portable() -> None:
    result = audit_relation_topology(
        _profile(),
        [
            (
                "anchored.json",
                {
                    "EditPolicy": {"caseAnchoredModuleTokens": ["SERVICE"]},
                    "Mates": [{"ModuleTokens": ["SERVICE", "TRANSPORT"]}],
                },
            ),
            (
                "portable.json",
                {
                    "EditPolicy": {"caseAnchoredModuleTokens": []},
                    "Mates": [{"ModuleTokens": ["SERVICE", "TRANSPORT"]}],
                },
            ),
        ],
    )

    assert result["nonStarMechanicalEdgeCount"] == 1
    assert result["portableNonStarMechanicalEdgeCount"] == 1
    edge = result["portableNonStarMechanicalEdges"][0]
    assert edge["moduleTokens"] == ["SERVICE", "TRANSPORT"]
    assert edge["portableObservationCount"] == 1


def test_unknown_module_tokens_are_reported_not_silently_normalized() -> None:
    result = audit_relation_topology(
        _profile(),
        [("unknown.json", {"Mates": [{"ModuleTokens": ["BASE", "OTHER"]}]})],
    )

    assert result["unknownObservedModuleTokens"] == ["OTHER"]


def test_grouped_component_suffix_is_normalized_to_functional_module() -> None:
    result = audit_relation_topology(
        _profile(),
        [
            (
                "grouped.json",
                {"Mates": [{"ModuleTokens": ["AUX1", "TRANSPORT"]}]},
            )
        ],
    )

    assert result["unknownObservedModuleTokens"] == []
    assert result["mechanicalEdges"][0]["moduleTokens"] == ["SERVICE", "TRANSPORT"]


def test_catalog_annotation_distinguishes_driving_from_validation_only() -> None:
    audit = audit_relation_topology(
        _profile(),
        [
            (
                "edges.json",
                {
                    "Mates": [
                        {"ModuleTokens": ["SERVICE", "TRANSPORT"]},
                        {"ModuleTokens": ["SCAN", "BASE"]},
                    ]
                },
            )
        ],
    )
    catalog = {
        "moduleDefinitions": [
            {
                "moduleDefinitionId": f"def-{token.lower()}",
                "projectAliases": [
                    {"projectId": "project-x", "moduleToken": token}
                ],
            }
            for token in ("BASE", "TRANSPORT", "SCAN", "SERVICE")
        ],
        "semanticPorts": [
            {"globalPortId": f"port-{token.lower()}", "moduleDefinitionId": f"def-{token.lower()}"}
            for token in ("BASE", "TRANSPORT", "SCAN", "SERVICE")
        ],
        "connectionTemplates": [
            {
                "globalTemplateId": "template-validation",
                "legacyTemplateId": "SERVICE_SPACING",
                "candidatePortIdsA": ["port-service"],
                "candidatePortIdsB": ["port-transport"],
                "mateSteps": [
                    {
                        "mateTypeName": "swMateDISTANCE",
                        "applicationMode": "validate_only",
                    }
                ],
                "constraintEffect": {"fullyLocatesAddedComponent": False},
                "provenance": {"projectId": "project-x"},
            },
            {
                "globalTemplateId": "template-legacy-partial-driver",
                "legacyTemplateId": "SERVICE_SPACING_LEGACY_DRIVER",
                "candidatePortIdsA": ["port-service"],
                "candidatePortIdsB": ["port-transport"],
                "mateSteps": [{"mateTypeName": "swMateDISTANCE"}],
                "constraintEffect": {
                    "fullyLocatesAddedComponent": False,
                    "estimatedRemovedScalarDof": 1,
                },
                "provenance": {"projectId": "project-x"},
            },
            {
                "globalTemplateId": "template-driving",
                "legacyTemplateId": "SCAN_INSTALL",
                "candidatePortIdsA": ["port-scan"],
                "candidatePortIdsB": ["port-base"],
                "mateSteps": [{"mateTypeName": "swMateCOINCIDENT"}],
                "constraintEffect": {"fullyLocatesAddedComponent": True},
                "provenance": {"projectId": "project-x"},
            },
        ],
    }

    result = annotate_relation_topology_with_catalog(audit, catalog)
    edges = {
        tuple(row["moduleTokens"]): row["catalogRelationSemantics"]
        for row in result["mechanicalEdges"]
    }
    assert edges[("SERVICE", "TRANSPORT")]["classification"] == "validation_only"
    assert edges[("SERVICE", "TRANSPORT")]["placementDriverReady"] is False
    assert edges[("SERVICE", "TRANSPORT")]["incompleteDrivingTemplateCount"] == 1
    assert edges[("BASE", "SCAN")]["classification"] == "has_driving_template"
    assert edges[("BASE", "SCAN")]["placementDriverReady"] is True
    assert edges[("SERVICE", "TRANSPORT")][
        "drivingAuthorizationImpliedByMechanicalEdge"
    ] is False


def test_catalog_annotation_reports_collectively_closed_bundle_members() -> None:
    profile = _profile()
    profile["modules"]["GUIDE"] = {"assemblyPolicy": {"requires": ["BASE"]}}
    audit = audit_relation_topology(
        profile,
        [
            (
                "bundle.json",
                {
                    "Mates": [
                        {"ModuleTokens": ["SCAN", "BASE"]},
                        {"ModuleTokens": ["SCAN", "GUIDE"]},
                    ]
                },
            )
        ],
    )
    tokens = ("BASE", "SCAN", "GUIDE")
    catalog = {
        "moduleDefinitions": [
            {
                "moduleDefinitionId": f"def-{token.lower()}",
                "projectAliases": [{"projectId": "project-x", "moduleToken": token}],
            }
            for token in tokens
        ],
        "semanticPorts": [
            {
                "globalPortId": f"port-{token.lower()}",
                "moduleDefinitionId": f"def-{token.lower()}",
            }
            for token in tokens
        ],
        "connectionTemplates": [
            {
                "globalTemplateId": "template-primary",
                "legacyTemplateId": "PRIMARY",
                "candidatePortIdsA": ["port-scan"],
                "candidatePortIdsB": ["port-base"],
                "mateSteps": [{"mateTypeName": "swMateCOINCIDENT"}],
                "constraintEffect": {"fullyLocatesAddedComponent": False},
                "provenance": {"projectId": "project-x"},
            },
            {
                "globalTemplateId": "template-anti-rotation",
                "legacyTemplateId": "ANTI_ROTATION",
                "candidatePortIdsA": ["port-scan"],
                "candidatePortIdsB": ["port-guide"],
                "mateSteps": [{"mateTypeName": "swMatePARALLEL"}],
                "constraintEffect": {"fullyLocatesAddedComponent": False},
                "provenance": {"projectId": "project-x"},
            },
        ],
        "templateCombinations": [
            {
                "globalCombinationId": "combination-scan-install",
                "legacyCombinationId": "SCAN_INSTALL",
                "memberGlobalTemplateIds": [
                    "template-primary",
                    "template-anti-rotation",
                ],
                "fullyLocatesAddedComponent": True,
                "expectedResidualDof": 0,
                "exactMemberSetRequired": True,
                "applicationScope": "same_target_insertion",
                "provenance": {"projectId": "project-x"},
            }
        ],
    }

    result = annotate_relation_topology_with_catalog(audit, catalog)
    edges = {
        tuple(row["moduleTokens"]): row["catalogRelationSemantics"]
        for row in result["mechanicalEdges"]
    }
    for pair in (("BASE", "SCAN"), ("GUIDE", "SCAN")):
        assert edges[pair]["classification"] == "collectively_closed_bundle_member"
        assert edges[pair]["placementDriverReady"] is False
        assert edges[pair]["collectivePlacementClosureAvailable"] is True
