"""Project01 BD00 calibration-module work-packet specialization."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from .project01_three_datum_work_packet import build_project01_three_datum_work_packet

CONTEXT = ["JJ00", "HL00", "SS00", "FF00", "SM00", "GN00"]

def build_project01_bd00_work_packet(source_graph: dict[str, Any], prior_effective_graph: dict[str, Any], prototype_assembly: Path) -> dict[str, Any]:
    result = build_project01_three_datum_work_packet(
        source_graph=source_graph, prior_effective_graph=prior_effective_graph,
        prototype_assembly=prototype_assembly, target_token="BD00", prior_context_tokens=CONTEXT,
        canonical_coincident_name="重合7", canonical_concentric_names_by_sorted_axis=["同心13", "同心12"], sort_axis=2,
        expected_hole_spacing_meters=0.05, interface_type="project01_calibration_frame_installation",
        target_port_id="BD00.frame_installation", base_port_id="JJ00.calibration_installation",
        template_id="BD00_to_JJ00_three_datum_installation", target_display_name="BD00校准模组安装端口",
        base_display_name="JJ00校准模组承载端口", capabilities=["installation", "nozzle_calibration"],
        step_id="step-05-add-BD00",
        extra_limits=["The calibration prism point is a prototype leaf-geometry proxy, not an authored datum."],
    )
    result["summary"]["calibrationEvidenceRequired"] = {
        "targetId": "calibration-prism-target", "evidencePath": "demo/layout_previews/project01_service_points.json"
    }
    return result
