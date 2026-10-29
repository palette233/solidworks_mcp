#!/usr/bin/env python3
"""Materialize the seven currently CAD-ready broad-combination pairs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.broad_combination_cad_validation_batch import (  # noqa: E402
    build_broad_combination_cad_validation_batch,
)


DEFAULT_COVERAGE = (
    ROOT / "demo/global_assembly_catalog/broad-combination-coverage-v1/coverage.json"
)
DEFAULT_QUEUE = ROOT / (
    "demo/cross_project_substitution/parameterized-datum-placement-v1/"
    "validation-queue-20261026-v15"
)
DEFAULT_DIRECT = ROOT / (
    "demo/cross_project_substitution/calibration-project01-to-project02-v1/"
    "bd00-a600-validation-v2/validation-package.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/cross_project_substitution/broad-combination-cad-validation-v1/"
    "batch-20261026-v3"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--queue-dir", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--direct-package", type=Path, default=DEFAULT_DIRECT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable batch: {output}")
    batch = build_broad_combination_cad_validation_batch(
        ROOT,
        coverage_path=args.coverage,
        parameterized_queue_dir=args.queue_dir,
        direct_package_path=args.direct_package,
    )
    output.mkdir(parents=True)
    (output / "batch-plan.json").write_text(
        json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = "\n".join(
        f"|{row['sequence']}|{row['moduleDefinitionId']}|{row['baseDefinitionId']}|"
        f"{row['adapter']}|待CAD与发布|"
        for row in batch["items"]
    )
    (output / "README-CN.md").write_text(
        "# 广泛组合CAD验证批次 v1\n\n"
        "本批次只收录全量68项矩阵中已有完整候选、无需再补语义的7个精确组合。"
        "每次只能执行一项；SolidWorks必须为零打开文档；首项失败立即停止；"
        "完成真实非原型CAD、保存重开和不可变精确配对发布后，才可进入正常累计装配。\n\n"
        "|顺序|移动模组|目标基座|执行适配器|当前状态|\n"
        "|---:|---|---|---|---|\n"
        + rows
        + "\n\n碰撞/B-rep、实际紧固方式和生产签认不属于本批次门禁。\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": True,
                "outputDirectory": str(output),
                "batchDigest": batch["batchDigest"],
                "summary": batch["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
