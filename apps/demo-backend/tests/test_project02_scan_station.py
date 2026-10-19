import unittest

from demo_backend.project02_scan_station import infer_project02_scan_station


class Project02ScanStationTests(unittest.TestCase):
    def test_carrier_8_is_unique_nearest_and_only_candidate_in_band(self):
        optical = {
            "entries": {
                "scanner": {"worldCenterMeters": [0.0, 0.0, 0.0]},
                "barcode": {
                    "carrierInstance": "056-19475000-00_ASM_165_ASM-8"
                },
            }
        }
        distances = {1: 0.90, 2: 0.80, 5: 0.60, 7: 0.55, 8: 0.127}
        bodies = {
            "captures": [
                {
                    "Bodies": [
                        {
                            "Component": {
                                "Name": (
                                    "A800/056-19475000-00_ASM_165_ASM-"
                                    f"{carrier}/模拟二维码-1"
                                )
                            },
                            "BoundingBoxWorld": [
                                -0.005,
                                distance - 0.0005,
                                -0.005,
                                0.005,
                                distance + 0.0005,
                                0.005,
                            ],
                        }
                        for carrier, distance in distances.items()
                    ]
                }
            ]
        }

        result = infer_project02_scan_station(optical, bodies)

        self.assertTrue(result["success"])
        self.assertTrue(result["usableForCoarseLayout"])
        self.assertEqual(result["selectedCarrierNumber"], 8)
        self.assertEqual(result["candidateRanking"][0]["carrierNumber"], 8)
        self.assertEqual(result["candidateCount"], 5)
        self.assertFalse(result["dynamicScanStopConfirmed"])

    def test_rejects_non_unique_or_incomplete_candidate_set(self):
        optical = {
            "entries": {
                "scanner": {"worldCenterMeters": [0.0, 0.0, 0.0]},
                "barcode": {
                    "carrierInstance": "056-19475000-00_ASM_165_ASM-8"
                },
            }
        }
        bodies = {
            "captures": [
                {
                    "Bodies": [
                        {
                            "Component": {
                                "Name": "A800/056-19475000-00_ASM_165_ASM-8/模拟二维码-1"
                            },
                            "BoundingBoxWorld": [0.0, 0.12, 0.0, 0.01, 0.121, 0.01],
                        }
                    ]
                }
            ]
        }

        result = infer_project02_scan_station(optical, bodies)

        self.assertFalse(result["success"])
        self.assertFalse(result["usableForCoarseLayout"])


if __name__ == "__main__":
    unittest.main()
