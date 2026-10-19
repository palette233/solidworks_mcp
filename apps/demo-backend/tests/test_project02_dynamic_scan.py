import unittest

from demo_backend.project02_dynamic_scan import build_project02_dynamic_scan_window


class Project02DynamicScanTests(unittest.TestCase):
    def test_builds_half_qr_width_stop_window_without_claiming_confirmation(self):
        request = {
            "moduleSemantics": {
                "FL9A24D062A800.001-1": {
                    "moduleType": "transport",
                    "points": {"barcode": {"u": -0.13, "v": 0.01}},
                    "parameters": {"barcodeHeightMeters": 0.001},
                }
            }
        }
        inference = {
            "success": True,
            "usableForCoarseLayout": True,
            "selectedCarrierInstance": "056-19475000-00_ASM_165_ASM-8",
            "candidateCount": 5,
            "nearestDistanceMarginMeters": 0.4145,
        }
        optical = {
            "entries": {
                "barcode": {"faceDimensionsMeters": [0.01, 0.01]}
            }
        }

        updated, report = build_project02_dynamic_scan_window(
            request, inference, optical
        )

        transport = updated["moduleSemantics"]["FL9A24D062A800.001-1"]
        self.assertAlmostEqual(transport["points"]["barcodeStopLowU"]["u"], -0.135)
        self.assertAlmostEqual(transport["points"]["barcodeStopHighU"]["u"], -0.125)
        self.assertEqual(
            transport["parameters"]["dynamicScanWindowPointNames"],
            ["barcodeStopLowU", "barcodeStopHighU"],
        )
        self.assertFalse(report["engineeringConfirmed"])
        self.assertFalse(report["plcTriggerConfirmed"])
        self.assertTrue(report["usableForCoarseLayout"])


if __name__ == "__main__":
    unittest.main()
