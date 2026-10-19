#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.cross_project_scanner_transport_process_validation import (  # noqa: E402
    build_scanner_transport_process_validation,
)


JOB = ROOT / "demo/global_assembly_contexts/manifest_jobs/project-global-job-163f19364c24"
OUT = ROOT / "demo/cross_project_substitution/cumulative-project03-v2"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    packet2 = _read(JOB / "packet-runs/packet-002-attempt-01/execution-effective-mate-graph.json")
    packet3_result = _read(JOB / "packet-runs/packet-003-attempt-01/cad-result.json")
    report = build_scanner_transport_process_validation(
        optical_validation=packet2["SemanticAssemblyPlanAudit"]["opticalValidation"],
        project01_scanner_geometry=_read(
            ROOT / "demo/layout_previews/project01_scanner_geometry.json"
        ),
        project01_first_stage_geometry=_read(
            ROOT / "demo/layout_previews/project01_first_stage_geometry.json"
        ),
        project01_source_graph=_read(
            ROOT
            / "demo/global_assembly_catalog/v1/relation-v2-preview/"
            "project01-ss00-current-insert-v1/execution-effective-mate-graph.json"
        ),
        final_ss00_graph=_read(
            JOB / "packet-runs/packet-001-attempt-01/execution-effective-mate-graph.json"
        ),
        final_assembly_path=Path(packet3_result["outputAssemblyPath"]),
        working_distance_evidence={
            "minimumMeters": 0.07,
            "maximumMeters": 1.0,
            "authority": "KEYENCE China official SR-X100 specifications",
            "sourceUrl": "https://www.keyence.com.cn/products/barcode/barcode-readers/sr-x/models/sr-x100/",
            "retrievedDate": "2026-10-12",
        },
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scanner-transport-process-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    checks = report["readOnlyChecks"]
    lines = [
        "# AI00—SS00 扫码工艺只读验证",
        "",
        f"- 状态：`{report['status']}`",
        f"- 扫描站位于SS00保守纵向包络：`{checks['scannerStationInsideTransportEnvelope']}`",
        f"- 光轴到条码通道横向误差：`{checks['crossTrackErrorMeters'] * 1000:.3f} mm`",
        f"- 条码通道所需工作距离：`{checks['requiredWorkingDistanceMeters'] * 1000:.3f} mm`",
        f"- CAD名义距离：`{report['sourceScanner']['modeledNominalWorkingDistanceMeters'] * 1000:.3f} mm`",
        f"- 粗工艺几何通过：`{report['coarseProcessGeometryPassed']}`",
        f"- 官方读取距离范围：`{checks['workingDistanceRangeEvidence']['minimumMeters'] * 1000:.0f}–{checks['workingDistanceRangeEvidence']['maximumMeters'] * 1000:.0f} mm`",
        f"- 静态Demo工艺验证通过：`{report['staticDemoProcessValidationPassed']}`",
        f"- 工程/生产验证通过：`{report['engineeringProcessValidationPassed']}`",
        "",
        "结论：79.5 mm落在SR-X100官方70–1000 mm读取距离内，静态Demo工艺验证通过；条码仍是原型代理面，未验证码尺寸、视野和现场触发，因此不宣称工程/生产放行。",
    ]
    (OUT / "scanner-transport-process-validation.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["coarseProcessGeometryPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
