from __future__ import annotations

import unittest

from demo_backend.project03_scanner import infer_project03_scanner_geometry


class Project03ScannerTests(unittest.TestCase):
    def test_recovers_explicit_upward_beam_and_separate_identity_head(self) -> None:
        def body(name: str, index: int, bounds: list[float]) -> dict:
            return {
                "Component": {"Name": name},
                "BodyIndex": index,
                "BoundingBoxWorld": bounds,
            }

        scanner_name = "AI00/AI10/FL209AG-00072-3"
        capture = {
            "captures": [
                {
                    "TopLevelComponent": {"Name": "FL9A24D063AI00.001-1"},
                    "LeafComponentCount": 5,
                    "BodyCount": 5,
                    "FailedBodyCount": 0,
                    "CoverageComplete": True,
                    "Bodies": [
                        body(scanner_name, 0, [-0.05, -0.04, -0.04, 0.05, 0.0, 0.04]),
                        body(scanner_name, 1, [-0.005, 0.0, -0.005, 0.005, 0.1, 0.005]),
                        body("AI00/AI10/FL412AI-00411/rail", 0, [-0.02, -0.02, -0.25, 0.02, 0.02, 0.25]),
                        body("AI00/FL201AQ-00046-2", 0, [-0.01, 0.1, -0.01, 0.01, 0.1001, 0.01]),
                        body("AI00/bracket", 0, [-0.1, -0.1, -0.1, 0.1, 0.1, 0.1]),
                    ],
                }
            ]
        }
        geometry = {
            "transportInstallationInterface": {
                "originWorldMeters": [0.0, 0.0, 0.0],
                "flowAxisWorld": [0.0, 0.0, 1.0],
                "transverseAxisWorld": [1.0, 0.0, 0.0],
                "upAxisWorld": [0.0, 1.0, 0.0],
            }
        }
        result = infer_project03_scanner_geometry(capture, geometry)
        scanner = result["scanners"][0]
        self.assertEqual(result["scannerCount"], 1)
        self.assertAlmostEqual(scanner["modeledWorkingDistanceMeters"], 0.1)
        self.assertEqual(scanner["opticalDirectionWorld"], [0.0, 1.0, 0.0])
        self.assertEqual(scanner["motionAxisWorldUnsigned"], [0.0, 0.0, 1.0])
        self.assertEqual(result["barcodeInterfaces"]["productBarcode"]["status"], "available")
        self.assertEqual(result["barcodeInterfaces"]["carrierBarcode"]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
