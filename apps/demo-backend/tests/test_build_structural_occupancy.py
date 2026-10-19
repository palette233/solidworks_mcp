from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_structural_occupancy import parse_component_pairs


class StructuralOccupancyPairTests(unittest.TestCase):
    def test_full_leaf_pair_is_symmetric_and_deduplicated(self):
        pairs, partners = parse_component_pairs(
            ["A100:A300", "a300:a100", "A300:A800"]
        )

        self.assertEqual(
            pairs,
            {
                frozenset(("A100", "A300")),
                frozenset(("A300", "A800")),
            },
        )
        self.assertEqual(partners["A100"], ("A300",))
        self.assertEqual(partners["A300"], ("A100", "A800"))
        self.assertEqual(partners["A800"], ("A300",))

    def test_full_leaf_pair_rejects_invalid_or_unknown_codes(self):
        for raw in ("A100", "A100:A100", "A100:A999"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_component_pairs([raw])


if __name__ == "__main__":
    unittest.main()
