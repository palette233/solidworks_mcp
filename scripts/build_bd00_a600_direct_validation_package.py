#!/usr/bin/env python3
"""Materialize the unpublished Project01 BD00 -> Project02 A600 CAD package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.direct_interface_validation import (  # noqa: E402
    compile_direct_interface_validation_package,
)
from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    load_calibration_contract_catalog,
)


DEFAULT_OUTPUT = (
    ROOT
    / "demo/cross_project_substitution/calibration-project01-to-project02-v1/"
    "bd00-a600-validation-v2"
)
BD00_ROOT = ROOT / "demo/semantic_ports/project01_BD00_fifth_increment_v1"
A600_ROOT = ROOT / "demo/semantic_ports/project02_A600_project03_AH00_cross_project_slot_v1"
ACQUISITION_ROOT = (
    ROOT
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition"
)
WRAPPER = (
    ROOT
    / "demo/global_assembly_contexts/manifest_jobs/"
    "project02-job-6e3c1b72de5d/packet-runs/packet-001-attempt-01/"
    "base-context-wrapper.SLDASM"
)
BD00_SOURCE = (
    ROOT.parents[1]
    / "cad_data/001-给港中文AI训练用资料_20260624/项目01/01-项目3D图纸/"
    "CITLB24N074&CITLB24N075/8.FL9C24N074BD00.001_标定模组/"
    "FL9C24N074BD00.001.SLDASM"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite validation package: {output}")

    request = _read(ACQUISITION_ROOT / "slot_acquisition_request.json")
    package = compile_direct_interface_validation_package(
        contract_catalog=load_calibration_contract_catalog(ROOT),
        module_definition_id="project01::BD00",
        slot_definition_id="project02::A600",
        module_face_catalog=_read(BD00_ROOT / "face_endpoint_catalog.json"),
        slot_face_catalog=_read(A600_ROOT / "face_endpoint_catalog.json"),
        module_source_path=BD00_SOURCE,
        slot_source_path=Path(request["targetBase"]["cadPath"]),
        base_wrapper_path=WRAPPER,
        module_hierarchy_path="FL9C24N074BD00.001-1",
        slot_hierarchy_path="FL9A24D062A600.001-1",
    )
    output.mkdir(parents=True)
    graph = package.pop("effectiveMateGraph")
    endpoints = package.pop("selectedEndpointCatalog")
    (output / "effective-mate-graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "selected-face-endpoint-catalog.json").write_text(
        json.dumps(endpoints, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    import hashlib

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    package["artifacts"] = {
        "effectiveGraph": {
            "path": str((output / "effective-mate-graph.json").resolve()),
            "sha256": sha(output / "effective-mate-graph.json"),
        },
        "selectedEndpointCatalog": {
            "path": str((output / "selected-face-endpoint-catalog.json").resolve()),
            "sha256": sha(output / "selected-face-endpoint-catalog.json"),
        },
    }
    (output / "validation-package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "README-CN.md").write_text(
        "# BD00 → A600 精确配对 CAD 候选\n\n"
        "复用A600已由AH00验证的50 mm支承面＋双定位轴备用槽。"
        "本目录只证明候选可从接口契约编译；尚未运行SolidWorks，"
        "不得作为累计装配执行授权。后续必须从非原型初始位姿建立三条配合、"
        "确认完全约束并保存关闭重开，再生成不可变精确配对发布。\n\n"
        "碰撞/B-rep与实际紧固方式不属于本轮门禁。\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": True,
                "outputDir": str(output),
                "status": package["status"],
                "packageDigest": package["packageDigest"],
                "effectiveMateGraphDigest": package["effectiveMateGraphDigest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
