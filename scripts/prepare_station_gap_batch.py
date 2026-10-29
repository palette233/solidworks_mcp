"""Batch reuse of station data; no CAD and no per-pair scripts."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.station_gap_batch import prepare_station_gap_batch

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--measurement-index", help="Versioned reusable measurement inventory; never execution authority")
    parser.add_argument("--capability-index", help="Authenticated cleaning-service capability coverage; never CAD authority")
    parser.add_argument("--functional-screening-index", help="Authenticated published-pose functional screen; never CAD authority")
    parser.add_argument("--candidate-decision-index", help="Authenticated station candidate decisions; never CAD authority")
    parser.add_argument("--transport-work-area-review-index", help="Authenticated transport-context work-area review; never CAD or publication authority")
    parser.add_argument("--scanner-rule-readiness-index", help="Authenticated exact/composed/measurement-required scanner readiness; never CAD authority")
    args = parser.parse_args()
    result = prepare_station_gap_batch(ROOT, args.coverage, args.registry, ROOT / args.output,
                                      measurement_index_path=args.measurement_index,
                                      capability_index_path=args.capability_index,
                                      functional_screening_index_path=args.functional_screening_index,
                                      candidate_decision_index_path=args.candidate_decision_index,
                                      transport_work_area_review_index_path=args.transport_work_area_review_index,
                                      scanner_rule_readiness_index_path=args.scanner_rule_readiness_index)
    print(json.dumps({"summary": result["summary"], "durationSeconds": result["durationSeconds"], "cadExecuted": False}, ensure_ascii=True))
