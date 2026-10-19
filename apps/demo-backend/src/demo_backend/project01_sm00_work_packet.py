"""Project01 SM00 scanner work-packet specialization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .project01_three_datum_work_packet import build_project01_three_datum_work_packet


def build_project01_sm00_work_packet(
    source_graph: dict[str, Any],
    prior_effective_graph: dict[str, Any],
    prototype_assembly: Path,
) -> dict[str, Any]:
    result = build_project01_three_datum_work_packet(
        source_graph=source_graph,
        prior_effective_graph=prior_effective_graph,
        prototype_assembly=prototype_assembly,
        target_token="SM00",
        prior_context_tokens=["JJ00", "HL00", "SS00", "FF00"],
        canonical_coincident_name="重合8",
        canonical_concentric_names_by_sorted_axis=["同心15", "同心14"],
        sort_axis=0,
        expected_hole_spacing_meters=0.022,
        interface_type="project01_scanner_frame_installation",
        target_port_id="SM00.frame_installation",
        base_port_id="JJ00.scanner_installation",
        template_id="SM00_to_JJ00_three_datum_installation",
        target_display_name="SM00双扫描器安装端口",
        base_display_name="JJ00扫描器承载端口",
        capabilities=["installation", "carrier_barcode_scan", "product_barcode_scan"],
        step_id="step-03-add-SM00",
        extra_limits=[
            "The modeled 200 mm optical beams are prototype geometry, not vendor-certified working-distance limits.",
            "Actual printed barcode faces and product-reader travel endpoints remain semantic proxies.",
        ],
    )
    result["summary"]["opticalEvidenceRequired"] = {
        "scannerCount": 2,
        "roles": ["carrierBarcodeScanner", "productBarcodeScanner"],
        "explicitBeamLengthMeters": 0.2,
        "evidencePath": "demo/layout_previews/project01_scanner_geometry.json",
    }
    return result
