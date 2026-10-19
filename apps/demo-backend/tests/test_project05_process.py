from __future__ import annotations

import unittest

from demo_backend.project05_process import build_project05_process_semantics


class Project05ProcessTests(unittest.TestCase):
    def test_ppt_semantics_do_not_claim_missing_cad_coordinates(self) -> None:
        result = build_project05_process_semantics()
        self.assertEqual(result["transportProcess"]["workPositionCount"], 2)
        self.assertEqual(result["scanProcess"]["station"], "buffer-position")
        self.assertEqual(result["scanProcess"]["targets"], ["carrier-barcode", "four-product-barcodes"])
        self.assertFalse(result["scanProcess"]["barcodeLocationsConfirmed"])
        self.assertFalse(result["scanProcess"]["opticalAxisAndDistanceAvailable"])
        self.assertEqual(result["ccdProcess"]["fieldOfViewMillimeters"], [19.0, 14.25])
        self.assertFalse(result["ccdProcess"]["cadOpticalOriginAndAxisAvailable"])


if __name__ == "__main__":
    unittest.main()
