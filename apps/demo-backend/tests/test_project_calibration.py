from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.project_calibration import build_calibration_portfolio


class ProjectCalibrationTests(unittest.TestCase):
    def _workspace(self, root: Path) -> None:
        demo = root / "demo"
        demo.mkdir()
        projects = []
        capabilities = {
            "01": ["frame_enclosure", "transport", "scanner", "gantry", "calibration"],
            "02": ["frame_enclosure", "transport", "scanner", "ccd_product", "gantry", "cleaning"],
            "03": ["frame_enclosure", "transport", "scanner", "gantry", "weighing"],
            "05": ["frame_enclosure", "transport", "scanner", "ccd_product", "gantry", "calibration"],
            "06": ["frame_enclosure", "transport", "scanner", "ccd_product", "gantry", "calibration"],
        }
        for project_id, caps in capabilities.items():
            projects.append(
                {
                    "projectId": project_id,
                    "family": "test",
                    "sourceAssemblyPath": f"project{project_id}.SLDASM",
                    "modules": [{"cadId": f"M{project_id}", "capabilities": caps}],
                }
            )
        (demo / "multi_project_module_manifest_v1.json").write_text(
            json.dumps({"projects": projects}), encoding="utf-8"
        )

        common = [
            "moduleIdentity",
            "moduleCadPaths",
            "baseOperationFace",
            "baseTopInstallationSurface",
            "transportInstallationFrame",
            "transportWorkPositions",
            "barcodeFaceAndSide",
            "scannerWorkingDistanceAndAxis",
            "dualValveReach",
            "operationSideCapacity",
            "moduleOccupancy",
            "staticCollisionPolicy",
        ]
        for project_id in ("01", "02", "03"):
            ids = list(common)
            ids.append("serviceFunctionPoints")
            if project_id == "02":
                ids.append("ccdWorkingGeometry")
            (demo / f"project{project_id}_parameter_package.json").write_text(
                json.dumps(
                    {
                        "status": "READY",
                        "top3SolveReady": True,
                        "requiredEvidence": [
                            {"id": item_id, "status": "available", "authority": "prototype-calibrated"}
                            for item_id in ids
                        ],
                    }
                ),
                encoding="utf-8",
            )
        (demo / "project05_parameter_package.json").write_text(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "top3SolveReady": False,
                    "requiredEvidence": [
                        {"id": "moduleIdentity", "status": "available"},
                        {"id": "scannerWorkingDistanceAndAxis", "status": "missing"},
                        {"id": "calibrationAndWeighingPoints", "status": "missing"},
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_portfolio_preserves_ready_projects_and_blocks_missing_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._workspace(root)
            result = build_calibration_portfolio(root)
            self.assertEqual(result["summary"]["top3ReadyProjects"], ["01", "02", "03"])
            self.assertEqual(result["summary"]["blockedProjects"], ["05", "06"])
            project06 = next(item for item in result["projects"] if item["projectId"] == "06")
            self.assertEqual(project06["parameterPackageStatus"], "NOT_CREATED")
            self.assertIn("transportInstallationFrame", project06["coarseLayoutBlockers"])
            identity06 = next(item for item in project06["evidence"] if item["id"] == "moduleIdentity")
            paths06 = next(item for item in project06["evidence"] if item["id"] == "moduleCadPaths")
            self.assertEqual(identity06["status"], "available")
            self.assertEqual(paths06["status"], "partial")
            self.assertEqual(
                project06["nextCalibrationActions"][0],
                "resolve independently loadable CAD paths for every selected module",
            )

    def test_capability_specific_ccd_and_service_aliases_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._workspace(root)
            result = build_calibration_portfolio(root)
            project01 = next(item for item in result["projects"] if item["projectId"] == "01")
            ccd01 = next(item for item in project01["evidence"] if item["id"] == "ccdWorkingGeometry")
            self.assertEqual(ccd01["status"], "not_required")
            project05 = next(item for item in result["projects"] if item["projectId"] == "05")
            service05 = next(item for item in project05["evidence"] if item["id"] == "serviceFunctionPoints")
            self.assertEqual(service05["status"], "missing")

    def test_project02_scope_gap_is_nonblocking_but_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._workspace(root)
            result = build_calibration_portfolio(root)
            project02 = next(item for item in result["projects"] if item["projectId"] == "02")
            scope = next(item for item in project02["evidence"] if item["id"] == "solveScopeCoverage")
            self.assertEqual(scope["status"], "partial")
            self.assertFalse(scope["coarseLayoutRequired"])
            self.assertTrue(project02["top3SolveReady"])


if __name__ == "__main__":
    unittest.main()
