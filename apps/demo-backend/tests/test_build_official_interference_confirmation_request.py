from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_official_interference_confirmation_request import build_request  # noqa: E402


def test_build_request_deduplicates_body_hits_for_same_leaf_pair() -> None:
    first = {
        "Name": "root/Frame-1",
        "Path": r"C:\Models\Frame.SLDPRT",
        "HierarchyPath": "root/Frame-1",
    }
    second = {
        "Name": "root/Bracket-4",
        "Path": r"C:\Models\Bracket.SLDPRT",
        "HierarchyPath": "root/Bracket-4",
    }
    report = {
        "exactChecks": [
            {
                "pair": ["AA00", "AE00"],
                "result": {
                    "InterferingBodyPairs": [
                        {"FirstComponent": first, "SecondComponent": second},
                        {"FirstComponent": first, "SecondComponent": second},
                    ]
                },
            }
        ]
    }
    comparison = {
        "newInterferenceSignatures": [
            {
                "first": {"sourceFile": "frame.sldprt", "leafInstance": "frame-1"},
                "second": {
                    "sourceFile": "bracket.sldprt",
                    "leafInstance": "bracket-4",
                },
                "count": 2,
            }
        ]
    }

    payload = build_request(report, comparison, "AA00", "AE00")

    assert payload["requestedSignatureCount"] == 1
    assert payload["requestedLeafComponentPairCount"] == 1
    assert len(payload["Failures"]) == 1
