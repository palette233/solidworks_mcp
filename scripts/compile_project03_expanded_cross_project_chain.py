#!/usr/bin/env python3
"""Compile the released Project03 mixed-project eight-module demo chain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_natural_language_manifest import (  # noqa: E402
    compile_natural_language_manifest_job,
)


RELEASE = (
    "demo/global_assembly_catalog/releases/"
    "relation-v62-project03-expanded-cross-project-chain-driving-20261014/"
    "release-manifest.json"
)
REQUIREMENTS = [
    "请先建立项目03 AA00设备箱体与固定安装环境。",
    "随后把项目01 SS00产品传输模组安装到当前基座。",
    "在传输线入口附近增加项目03 AI00条码扫描模组。",
    "在设备操作区域增加项目01 BD00喷嘴校准模组。",
    "在当前基座上增加项目03 AD00定位模组。",
    "在当前基座上增加项目03 AJ00供胶系统。",
    "在当前基座上增加项目03 AG00清洁称重模组。",
    "最后在当前基座上安装项目03 AB00龙门点胶模组。",
]

SHUFFLED_REQUIREMENTS = [
    "最后增加项目03 AB00龙门点胶模组。",
    "增加项目03 AG00清洁称重模组。",
    "安装项目01 SS00产品传输模组。",
    "建立项目03 AA00设备箱体与固定安装环境。",
    "增加项目03 AJ00供胶系统。",
    "增加项目01 BD00喷嘴校准模组。",
    "增加项目03 AI00条码扫描模组。",
    "增加项目03 AD00定位模组。",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--context-id", default="nl-project03-expanded-cross-project-v2"
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--idempotency-key")
    parser.add_argument(
        "--shuffled-input",
        action="store_true",
        help="Deliberately scramble the requirement order and let released dependencies reorder it.",
    )
    args = parser.parse_args()
    result = compile_natural_language_manifest_job(
        ROOT,
        {
            "contextId": args.context_id,
            "displayName": "Project03扩展跨项目8模组链",
            "requirements": SHUFFLED_REQUIREMENTS if args.shuffled_input else REQUIREMENTS,
            "releaseManifestPath": RELEASE,
            "autoOrderByReleasedDependencies": args.shuffled_input,
            "overwrite": args.overwrite,
            "idempotencyKey": args.idempotency_key,
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
