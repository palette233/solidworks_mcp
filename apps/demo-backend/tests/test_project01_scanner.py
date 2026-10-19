from __future__ import annotations

import unittest

from demo_backend.project01_scanner import infer_project01_scanner_geometry


class Project01ScannerTests(unittest.TestCase):
    def test_two_explicit_beams_separate_carrier_and_product_readers(self) -> None:
        scanner_path = r"C:\parts\FL209AG-00072.SLDPRT"
        sensor_path = r"C:\parts\FL201AB-00043.SLDPRT"
        capture = {
            "captures": [
                {
                    "TopLevelComponent": {"Name": "FL9C24N074SM00.001-1"},
                    "LeafComponentCount": 3,
                    "BodyCount": 5,
                    "FailedBodyCount": 0,
                    "CoverageComplete": True,
                    "Bodies": [
                        {"Component": {"Name": "root/carrier-reader", "Path": scanner_path}, "BodyIndex": 0, "BoundingBoxWorld": [-0.05, -0.02, -0.02, 0.0, 0.02, 0.02]},
                        {"Component": {"Name": "root/carrier-reader", "Path": scanner_path}, "BodyIndex": 1, "BoundingBoxWorld": [0.0, -0.005, -0.005, 0.2, 0.005, 0.005]},
                        {"Component": {"Name": "root/product-reader", "Path": scanner_path}, "BodyIndex": 0, "BoundingBoxWorld": [-0.02, -0.05, -0.02, 0.02, 0.0, 0.02]},
                        {"Component": {"Name": "root/product-reader", "Path": scanner_path}, "BodyIndex": 1, "BoundingBoxWorld": [-0.005, 0.0, -0.005, 0.005, 0.2, 0.005]},
                        {"Component": {"Name": "root/missing-product-sensor", "Path": sensor_path}, "BodyIndex": 0, "BoundingBoxWorld": [0, 0, 0, 0.01, 0.01, 0.01]},
                    ],
                }
            ]
        }
        geometry = {
            "transportInstallationInterface": {
                "originWorldMeters": [0, 0, 0],
                "flowAxisWorld": [0, 0, 1],
                "transverseAxisWorld": [1, 0, 0],
                "upAxisWorld": [0, 1, 0],
            }
        }
        result = infer_project01_scanner_geometry(capture, geometry)
        by_role = {item["role"]: item for item in result["scanners"]}
        self.assertEqual(result["scannerCount"], 2)
        self.assertEqual(by_role["carrierBarcodeScanner"]["opticalDirectionWorld"], [1.0, 0.0, 0.0])
        self.assertEqual(by_role["productBarcodeScanner"]["opticalDirectionWorld"], [0.0, 1.0, 0.0])
        self.assertEqual(by_role["productBarcodeScanner"]["motionAxisWorld"], [0.0, 0.0, 1.0])
        self.assertAlmostEqual(by_role["carrierBarcodeScanner"]["modeledWorkingDistanceMeters"], 0.2)
        self.assertEqual(result["nonBarcodeDetectionSensor"]["role"], "carrierMissingProductDetection")


if __name__ == "__main__":
    unittest.main()
