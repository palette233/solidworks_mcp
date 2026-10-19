from __future__ import annotations

import unittest

from scripts.generate_a100_a200_repair_candidates import (
    DEFAULT_OFFSETS,
    parse_offsets,
)


class RepairCandidateOffsetTests(unittest.TestCase):
    def test_default_a200_search_is_preserved_for_a200_repairs(self) -> None:
        self.assertEqual(DEFAULT_OFFSETS, parse_offsets(None))

    def test_specialized_repair_preserves_a200_without_explicit_offset(self) -> None:
        self.assertEqual(((0.0, 0.0),), parse_offsets(None, preserve_a200=True))

    def test_explicit_a200_offset_wins_during_coordinated_repair(self) -> None:
        self.assertEqual(
            ((0.03, -0.01),),
            parse_offsets(["0.03,-0.01"], preserve_a200=True),
        )


if __name__ == "__main__":
    unittest.main()
