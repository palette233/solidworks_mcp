"""Project01 GJ00 glue-supply work-packet specialization."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .project01_three_datum_work_packet import build_project01_three_datum_work_packet
CONTEXT=["JJ00","HL00","SS00","FF00","SM00","GN00","BD00"]
def build_project01_gj00_work_packet(source_graph:dict[str,Any],prior_effective_graph:dict[str,Any],prototype_assembly:Path)->dict[str,Any]:
 r=build_project01_three_datum_work_packet(source_graph=source_graph,prior_effective_graph=prior_effective_graph,prototype_assembly=prototype_assembly,target_token="GJ00",prior_context_tokens=CONTEXT,canonical_coincident_name="重合12",canonical_concentric_names_by_sorted_axis=["同心22","同心23"],sort_axis=0,expected_hole_spacing_meters=.22,interface_type="project01_glue_supply_frame_installation",target_port_id="GJ00.frame_installation",base_port_id="JJ00.glue_supply_installation",template_id="GJ00_to_JJ00_three_datum_installation",target_display_name="GJ00供胶模组安装端口",base_display_name="JJ00供胶模组承载端口",capabilities=["installation","glue_supply","maintenance_access"],step_id="step-06-add-GJ00",extra_limits=["Hose routing, bend radius and maintenance sweep are not represented by the three rigid installation mates."])
 r["summary"]["hoseMaintenanceGateReady"]=False
 return r
