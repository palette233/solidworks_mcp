from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0


class Layout2d(BaseModel):
    x: float
    y: float
    theta_degrees: float | None = Field(default=None, alias="thetaDegrees")
    theta_axis: str | None = Field(default=None, alias="thetaAxis")
    normal_offset_meters: float = Field(default=0.0, alias="normalOffsetMeters")

    model_config = {"populate_by_name": True}


class LayoutComponentSummary(BaseModel):
    component_name: str = Field(alias="componentName")
    file_path: str | None = Field(default=None, alias="filePath")
    bottom_face_name: str = Field(default="\u5e95\u9762", alias="bottomFaceName")
    layout2d: Layout2d | None = None
    face_mapping_found: bool | None = Field(default=None, alias="faceMappingFound")

    model_config = {"populate_by_name": True}


class LayoutJsonInfo(BaseModel):
    path: str
    success: bool | None = None
    message: str | None = None
    base_component_name: str | None = Field(default=None, alias="baseComponentName")
    component_count: int = Field(default=0, alias="componentCount")
    components: list[LayoutComponentSummary] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class DemoComponent(BaseModel):
    id: str
    display_name: str = Field(alias="displayName")
    component_name: str = Field(alias="componentName")
    file_path: str = Field(alias="filePath")
    bottom_face_name: str = Field(default="\u5e95\u9762", alias="bottomFaceName")
    current: Coordinate = Field(default_factory=Coordinate)
    target: Coordinate = Field(default_factory=Coordinate)

    model_config = {"populate_by_name": True}


class DemoState(BaseModel):
    assembly_path: str | None = Field(default=None, alias="assemblyPath")
    common_base_ready: bool = Field(default=False, alias="commonBaseReady")
    layout_json_path: str | None = Field(default=None, alias="layoutJsonPath")
    layout_info: LayoutJsonInfo | None = Field(default=None, alias="layoutInfo")
    components: list[DemoComponent]
    last_run: dict | None = Field(default=None, alias="lastRun")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="updatedAt")

    model_config = {"populate_by_name": True}


class LayoutTarget(BaseModel):
    id: str | None = None
    component_name: str | None = Field(default=None, alias="componentName")
    x: float
    y: float
    z: float = 0

    model_config = {"populate_by_name": True}


class ApplyLayoutRequest(BaseModel):
    components: list[LayoutTarget]
    use_llm: bool = Field(default=False, alias="useLlm")
    align_bottom: bool = Field(default=True, alias="alignBottom")

    model_config = {"populate_by_name": True}


class ProjectRequirementRequest(BaseModel):
    requirement: str = Field(min_length=1)


class ProjectModuleConfirmationRequest(BaseModel):
    requirement: str = Field(min_length=1)
    selected_module_codes: list[str] = Field(default_factory=list, alias="selectedModuleCodes")

    model_config = {"populate_by_name": True}


class RecordSelectedFaceRequest(BaseModel):
    component_name: str = Field(alias="componentName")
    face_name: str = Field(default="\u5e95\u9762", alias="faceName")

    model_config = {"populate_by_name": True}


class HighlightFaceEndpointRequest(BaseModel):
    catalog_path: str | None = Field(default=None, alias="catalogPath")
    endpoint_id: str = Field(alias="endpointId", min_length=1)
    zoom_to_selection: bool = Field(default=True, alias="zoomToSelection")

    model_config = {"populate_by_name": True}


class FaceMatePatchPreviewRequest(BaseModel):
    catalog_path: str | None = Field(default=None, alias="catalogPath")
    source_graph_path: str | None = Field(default=None, alias="sourceGraphPath")
    face_a_endpoint_id: str = Field(alias="faceAEndpointId", min_length=1)
    face_b_endpoint_id: str = Field(alias="faceBEndpointId", min_length=1)
    mate_type: int = Field(alias="mateType")
    mate_name: str | None = Field(default=None, alias="mateName")
    alignment: int = 0
    distance_meters: float | None = Field(default=None, alias="distanceMeters")
    angle_degrees: float | None = Field(default=None, alias="angleDegrees")

    model_config = {"populate_by_name": True}


class FaceMatePatchApplyRequest(FaceMatePatchPreviewRequest):
    preview_digest: str = Field(alias="previewDigest", min_length=64, max_length=64)
    output_assembly_path: str = Field(alias="outputAssemblyPath", min_length=1)
    confirmed: bool = False

    model_config = {"populate_by_name": True}


class SelectLayoutJsonRequest(BaseModel):
    layout_json_path: str = Field(alias="layoutJsonPath")
    sync_components: bool = Field(default=True, alias="syncComponents")

    model_config = {"populate_by_name": True}


class UploadLayoutJsonRequest(BaseModel):
    file_name: str = Field(alias="fileName")
    content: str
    sync_components: bool = Field(default=True, alias="syncComponents")

    model_config = {"populate_by_name": True}


class ApplyCapturedLayoutRequest(BaseModel):
    xy_tolerance_meters: float | None = Field(default=None, alias="xyToleranceMeters")
    theta_tolerance_degrees: float | None = Field(default=None, alias="thetaToleranceDegrees")

    model_config = {"populate_by_name": True}


class DiscoverComponentsRequest(BaseModel):
    source_assembly_path: str | None = Field(default=None, alias="sourceAssemblyPath")
    scope: str = "topLevelOnly"
    include_parts: bool = Field(default=False, alias="includeParts")
    include_suppressed: bool = Field(default=False, alias="includeSuppressed")
    default_bottom_face_name: str = Field(default="\u5e95\u9762", alias="defaultBottomFaceName")

    model_config = {"populate_by_name": True}


class DiscoveredComponent(BaseModel):
    component_name: str = Field(alias="componentName")
    display_name: str = Field(alias="displayName")
    file_path: str = Field(alias="filePath")
    hierarchy_path: str = Field(default="", alias="hierarchyPath")
    depth: int = 0
    is_assembly: bool = Field(default=False, alias="isAssembly")
    is_part: bool = Field(default=False, alias="isPart")
    is_suppressed: bool = Field(default=False, alias="isSuppressed")
    is_hidden: bool = Field(default=False, alias="isHidden")
    transform: list[float] | None = None
    translation: list[float] | None = None
    x_axis: list[float] | None = Field(default=None, alias="xAxis")
    y_axis: list[float] | None = Field(default=None, alias="yAxis")
    z_axis: list[float] | None = Field(default=None, alias="zAxis")
    default_bottom_face_name: str = Field(default="\u5e95\u9762", alias="defaultBottomFaceName")

    model_config = {"populate_by_name": True}


class DiscoveryResult(BaseModel):
    success: bool
    message: str
    source_assembly_path: str | None = Field(default=None, alias="sourceAssemblyPath")
    scope: str = "topLevelOnly"
    include_parts: bool = Field(default=False, alias="includeParts")
    include_suppressed: bool = Field(default=False, alias="includeSuppressed")
    component_count: int = Field(default=0, alias="componentCount")
    components: list[DiscoveredComponent] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class SyncDiscoveredComponentsRequest(BaseModel):
    components: list[DiscoveredComponent]

    model_config = {"populate_by_name": True}


class CaptureProjectLayoutRequest(BaseModel):
    source_assembly_path: str | None = Field(default=None, alias="sourceAssemblyPath")
    base_component_name: str | None = Field(default=None, alias="baseComponentName")
    output_path: str | None = Field(default=None, alias="outputPath")
    project_config_path: str | None = Field(default=None, alias="projectConfigPath")

    model_config = {"populate_by_name": True}


class ProvisionalComponentSpec(BaseModel):
    component_name: str = Field(alias="componentName", min_length=1)
    width_meters: float = Field(alias="widthMeters", gt=0)
    depth_meters: float = Field(alias="depthMeters", gt=0)
    height_meters: float = Field(alias="heightMeters", gt=0)
    anchor_u: float = Field(default=0.0, alias="anchorU")
    anchor_v: float = Field(default=0.0, alias="anchorV")
    file_path: str | None = Field(default=None, alias="filePath")
    bottom_face_name: str = Field(default="底面", alias="bottomFaceName")
    reason: str = Field(default="User-approved provisional component for coarse reconstruction.")
    replayable: bool = False

    model_config = {"populate_by_name": True}


class GenerateConstraintLayoutRequest(BaseModel):
    source_assembly_path: str | None = Field(default=None, alias="sourceAssemblyPath")
    base_component_name: str | None = Field(default=None, alias="baseComponentName")
    output_path: str | None = Field(default=None, alias="outputPath")
    geometry_capture_path: str | None = Field(default=None, alias="geometryCapturePath")
    role_overrides: dict[str, Literal["gantry", "transport", "glue", "functional"]] = Field(
        default_factory=dict,
        alias="roleOverrides",
    )
    margin_ratios: list[float] = Field(default_factory=lambda: [0.05, 0.03, 0.01, 0.0], alias="marginRatios")
    minimum_clearance_meters: float = Field(default=0.01, ge=0, alias="minimumClearanceMeters")
    glue_distance_meters: float = Field(default=0.05, ge=0, alias="glueDistanceMeters")
    allow_rotation: bool = Field(default=False, alias="allowRotation")
    portal_pass_through: dict[str, list[str]] = Field(
        default_factory=dict,
        alias="portalPassThrough",
    )
    portal_opening_width_ratio: float = Field(
        default=0.8,
        gt=0,
        le=1,
        alias="portalOpeningWidthRatio",
    )
    portal_opening_height_ratio: float = Field(
        default=0.75,
        gt=0,
        le=1,
        alias="portalOpeningHeightRatio",
    )
    module_semantics: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        alias="moduleSemantics",
    )
    process_constraints: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="processConstraints",
    )
    auto_generate_process_constraints: bool = Field(
        default=True,
        alias="autoGenerateProcessConstraints",
    )
    provisional_components: list[ProvisionalComponentSpec] = Field(
        default_factory=list,
        alias="provisionalComponents",
    )
    prefer_source_layout: bool = Field(default=False, alias="preferSourceLayout")
    source_position_independent: bool = Field(
        default=False,
        alias="sourcePositionIndependent",
    )
    allowed_projected_overlap_pairs: list[list[str]] = Field(
        default_factory=list,
        alias="allowedProjectedOverlapPairs",
    )
    minimum_transport_gantry_overlap_ratio: float = Field(
        default=0.5,
        ge=0,
        le=1,
        alias="minimumTransportGantryOverlapRatio",
    )
    minimum_portal_gantry_overlap_ratio: float = Field(
        default=0.5,
        ge=0,
        le=1,
        alias="minimumPortalGantryOverlapRatio",
    )
    minimum_functional_gantry_overlap_ratio: float = Field(
        default=0.0,
        ge=0,
        le=1,
        alias="minimumFunctionalGantryOverlapRatio",
    )
    minimum_functional_gantry_boundary_clearance_meters: float = Field(
        default=0.0,
        ge=0,
        alias="minimumFunctionalGantryBoundaryClearanceMeters",
    )
    maximum_transport_gantry_center_offset_meters: float | None = Field(
        default=None,
        ge=0,
        alias="maximumTransportGantryCenterOffsetMeters",
    )
    require_reach_inside_gantry: bool = Field(default=True, alias="requireReachInsideGantry")
    sync_layout: bool = Field(default=True, alias="syncLayout")

    model_config = {"populate_by_name": True}


class ToolCallPlan(BaseModel):
    tool: str
    arguments: dict


class OperationResult(BaseModel):
    status: Literal["ok", "dry-run", "blocked", "error"]
    message: str
    plan: list[ToolCallPlan] = Field(default_factory=list)
    tool_results: list[dict] = Field(default_factory=list, alias="toolResults")
    state: DemoState | None = None
    missing_face_mappings: list[dict[str, str]] = Field(default_factory=list, alias="missingFaceMappings")
    layout_info: LayoutJsonInfo | None = Field(default=None, alias="layoutInfo")
    discovery: DiscoveryResult | None = None
    constraint_layout: dict | None = Field(default=None, alias="constraintLayout")

    model_config = {"populate_by_name": True}


class McpHealthResult(BaseModel):
    status: Literal["ok", "dry-run", "blocked", "error"]
    message: str
    active_document: dict | None = Field(default=None, alias="activeDocument")
    expected_assembly_path: str | None = Field(default=None, alias="expectedAssemblyPath")
    active_assembly_matches_state: bool | None = Field(default=None, alias="activeAssemblyMatchesState")
    face_mapping_path: str | None = Field(default=None, alias="faceMappingPath")
    mcp_face_mapping_path: str | None = Field(default=None, alias="mcpFaceMappingPath")
    face_mapping_paths_match: bool | None = Field(default=None, alias="faceMappingPathsMatch")
    mcp_face_mapping_info: dict | None = Field(default=None, alias="mcpFaceMappingInfo")
    tool_results: list[dict] = Field(default_factory=list, alias="toolResults")

    model_config = {"populate_by_name": True}


def default_demo_state(asset_dir: Path) -> DemoState:
    components = [
        DemoComponent(
            id="a",
            displayName="Subassembly A",
            componentName="A-1",
            filePath=str(asset_dir / "A.SLDASM"),
            target=Coordinate(x=0.0, y=0.0, z=0.0),
        ),
        DemoComponent(
            id="b",
            displayName="Subassembly B",
            componentName="B-1",
            filePath=str(asset_dir / "B.SLDASM"),
            target=Coordinate(x=0.2, y=0.0, z=0.0),
        ),
        DemoComponent(
            id="c",
            displayName="Subassembly C",
            componentName="C-1",
            filePath=str(asset_dir / "C.SLDASM"),
            target=Coordinate(x=0.4, y=0.1, z=0.0),
        ),
    ]
    return DemoState(assemblyPath=None, components=components)
