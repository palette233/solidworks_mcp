from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_natural_language_manifest import (  # noqa: E402
    compile_natural_language_manifest_job,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile 2-20 ordered natural-language module requests into a queued generic CAD job."
    )
    parser.add_argument("context_id")
    parser.add_argument("requirements", nargs="+")
    parser.add_argument("--display-name")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--idempotency-key")
    parser.add_argument(
        "--auto-order-by-released-dependencies",
        action="store_true",
        help=(
            "Resolve a unique base and deterministically reorder module requests "
            "from immutable released installation evidence before compilation."
        ),
    )
    parser.add_argument(
        "--release-manifest",
        help=(
            "Bind compilation to an immutable released relation catalog. "
            "Only templates authorized by that release may drive CAD placement."
        ),
    )
    parser.add_argument("--start-order", type=int, default=1)
    parser.add_argument("--packet-limit", type=int)
    parser.add_argument(
        "--positioning-standard-id",
        choices=["project02-inferred-v1"],
        help="Explicitly opt into a versioned project positioning baseline.",
    )
    parser.add_argument(
        "--driving-strategy-selection",
        action="append",
        default=[],
        metavar="TEMPLATE_ID=STRATEGY_ID",
        help=(
            "Explicitly select a non-portable calibrated fallback for one driving "
            "template. The selection is recorded and confirmed; it is never automatic."
        ),
    )
    args = parser.parse_args()
    selections = []
    for raw in args.driving_strategy_selection:
        template_id, separator, strategy_id = raw.partition("=")
        if not separator or not template_id.strip() or not strategy_id.strip():
            parser.error(
                "--driving-strategy-selection必须使用TEMPLATE_ID=STRATEGY_ID格式"
            )
        selections.append(
            {
                "globalTemplateId": template_id.strip(),
                "strategyId": strategy_id.strip(),
                "confirmed": True,
            }
        )
    result = compile_natural_language_manifest_job(
        ROOT,
        {
            "contextId": args.context_id,
            "requirements": args.requirements,
            "displayName": args.display_name,
            "overwrite": args.overwrite,
            "idempotencyKey": args.idempotency_key,
            "releaseManifestPath": args.release_manifest,
            "autoOrderByReleasedDependencies": (
                args.auto_order_by_released_dependencies
            ),
            "startOrder": args.start_order,
            "packetLimit": args.packet_limit,
            "positioningStandardId": args.positioning_standard_id,
            "drivingStrategySelections": selections,
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
