from __future__ import annotations

import unittest

from demo_backend.mate_overconstraint_audit import (
    analyze_mate_overconstraint_evidence,
    analyze_mate_overconstraint_isolation_results,
    analyze_full_semantics_baseline,
)


class MateOverconstraintAuditTests(unittest.TestCase):
    def test_finds_cross_mode_first_overdefined_mate_and_propagation(self) -> None:
        graph = {
            "Mates": [
                {"MateName": "距离8", "ModuleTokens": ["A500", "A700"]},
                {"MateName": "宽度10", "ModuleTokens": ["A600", "A700"]},
                {"MateName": "距离29", "ModuleTokens": ["A600", "A700"]},
            ]
        }
        results = [
            {
                "Mode": mode,
                "MateResults": [
                    {"MateName": "距离8", "Success": True, "ErrorName": "swAddMateError_NoError"},
                    {"MateName": "宽度10", "Success": True, "ErrorName": "swAddMateError_OverDefinedAssembly"},
                    {"MateName": "距离29", "Success": True, "ErrorName": "swAddMateError_OverDefinedAssembly"},
                ],
                "ComponentResults": [
                    {"ModuleToken": "A500", "ConstrainedStatusName": "swOverConstrained"},
                    {"ModuleToken": "A700", "ConstrainedStatusName": "swOverConstrained"},
                ],
            }
            for mode in ("source_pose", "mate_only", "residual_anchors")
        ]
        report = analyze_mate_overconstraint_evidence(graph, results)
        self.assertEqual(report["firstCommonOverdefinedMate"], "宽度10")
        self.assertEqual(report["secondaryCandidates"], ["距离29"])
        self.assertTrue(report["inference"]["a500OverconstraintMayBePropagatedThroughA700"])
        self.assertEqual(report["inference"]["confidence"], "high-cross-mode-repeatability")

    def test_isolation_audit_distinguishes_rebuild_error_from_source_health(self) -> None:
        source = {
            "MateResults": [
                {
                    "MateName": name,
                    "ErrorName": "swAddMateError_OverDefinedAssembly",
                    "AdvancedOptions": {
                        "SourceFeatureErrorCode": 0,
                        "SourceFeatureIsWarning": False,
                    },
                }
                for name in ("宽度10", "距离29")
            ]
        }
        runs = [
            {
                "id": "without-width",
                "removedMateNames": ["宽度10"],
                "result": {
                    "Success": True,
                    "ToolResult": {
                        "MateResults": [
                            {"MateName": "距离29", "ErrorName": "swAddMateError_OverDefinedAssembly"}
                        ]
                    },
                },
            },
            {
                "id": "without-both",
                "removedMateNames": ["宽度10", "距离29"],
                "result": {
                    "Success": True,
                    "ToolResult": {
                        "MateResults": [
                            {"MateName": "重合38", "ErrorName": "swAddMateError_NoError"}
                        ]
                    },
                },
            },
        ]

        report = analyze_mate_overconstraint_isolation_results(source, runs)

        self.assertTrue(report["findings"]["sourceCandidatesHealthy"])
        self.assertTrue(report["findings"]["removingWidth10AloneIsInsufficient"])
        self.assertTrue(report["findings"]["removingBothClearsCreationOverdefinedErrors"])
        self.assertEqual(
            report["findings"]["classification"],
            "reconstruction-redundancy-or-semantic-difference",
        )

    def test_full_semantics_baseline_confirms_flexible_state_gap(self) -> None:
        old = {
            "MateResults": [
                {
                    "MateName": name,
                    "ErrorName": "swAddMateError_OverDefinedAssembly",
                    "AdvancedOptions": {"WidthConstraintType": 0} if name == "宽度10" else None,
                }
                for name in ("宽度10", "距离29")
            ],
            "ComponentResults": [
                {"ModuleToken": "A700", "ConstrainedStatusName": "swOverConstrained"}
            ],
        }
        graph = {
            "Modules": [
                {
                    "ModuleToken": "A700",
                    "SolvingState": 1,
                    "SolvingStateName": "swComponentFlexibleSolving",
                }
            ],
            "Mates": [
                {"MateName": "宽度10", "AdvancedOptions": {"WidthConstraintType": 0}},
                {"MateName": "距离29"},
            ],
        }
        new = {
            "Success": True,
            "ToolResult": {
                "MateResults": [
                    {"MateName": name, "ErrorName": "swAddMateError_NoError"}
                    for name in ("宽度10", "距离29")
                ],
                "ComponentStatuses": [
                    {
                        "ModuleToken": "A700",
                        "ConstrainedStatusName": "swUnderConstrained",
                        "ObservedSolvingStateName": "swComponentFlexibleSolving",
                        "SolvingStateMatches": True,
                    }
                ],
                "MateCreationErrorsClear": True,
                "ReopenedComponentsNotOverConstrained": True,
                "ReopenedComponentSemanticsMatch": True,
                "ReopenedMateParametersMatch": True,
            },
        }

        report = analyze_full_semantics_baseline(old, graph, new)

        self.assertTrue(report["finding"]["confirmed"])
        self.assertEqual(
            report["finding"]["classification"],
            "confirmed-missing-a700-flexible-solving-state",
        )


if __name__ == "__main__":
    unittest.main()
