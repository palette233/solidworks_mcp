from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..adapters.llm_client import LlmClient
from ..adapters.mcp_client import McpClient
from ..face_mappings import FaceMappingStore
from ..mcp_tools import (
    APPEND_COMPONENTS_TO_COMMON_BASE_ASSEMBLY_TOOL,
    ARRANGE_COMPONENTS_ON_COMMON_BASE_TOOL,
    APPLY_CAPTURED_COMMON_BASE_LAYOUT_TOOL,
    CAPTURE_COMMON_BASE_LAYOUT_TOOL,
    DISCOVER_LAYOUT_COMPONENTS_TOOL,
    FINALIZE_COMMON_BASE_ASSEMBLY_TOOL,
    INITIALIZE_COMMON_BASE_ASSEMBLY_TOOL,
    MOVE_COMPONENTS_ON_COMMON_BASE_TOOL,
)
from ..models import (
    ApplyCapturedLayoutRequest,
    ApplyLayoutRequest,
    CaptureProjectLayoutRequest,
    Coordinate,
    DemoComponent,
    DemoState,
    DiscoverComponentsRequest,
    DiscoveryResult,
    Layout2d,
    LayoutComponentSummary,
    LayoutJsonInfo,
    McpHealthResult,
    OperationResult,
    RecordSelectedFaceRequest,
    SelectLayoutJsonRequest,
    SyncDiscoveredComponentsRequest,
    ToolCallPlan,
    UploadLayoutJsonRequest,
)
from ..state_store import DemoStateStore


class DemoService:
    def __init__(
        self,
        store: DemoStateStore,
        face_mappings: FaceMappingStore,
        llm: LlmClient,
        mcp: McpClient,
        replay_xy_tolerance_meters: float = 1e-6,
        replay_theta_tolerance_degrees: float = 1e-4,
        initialize_batch_size: int = 4,
        target_assembly_path: Path | str | None = None,
    ):
        self.store = store
        self.face_mappings = face_mappings
        self.llm = llm
        self.mcp = mcp
        self.replay_xy_tolerance_meters = replay_xy_tolerance_meters
        self.replay_theta_tolerance_degrees = replay_theta_tolerance_degrees
        self.initialize_batch_size = max(1, initialize_batch_size)
        self.target_assembly_path = (
            Path(target_assembly_path)
            if target_assembly_path is not None
            else self._workspace() / "demo" / "ABC_arrange_demo.SLDASM"
        )

    def get_state(self) -> DemoState:
        state = self.store.load()
        self._normalize_state(state)
        return state

    def save_state(self, state: DemoState) -> DemoState:
        self._normalize_state(state)
        return self.store.save(state)

    def reset_state(self) -> DemoState:
        return self.store.reset()

    async def mcp_health(self) -> McpHealthResult:
        state = self.store.load()
        self._normalize_state(state)
        expected = state.assembly_path
        expected_mapping_path = str(self.face_mappings.mapping_path)
        plan = [
            ToolCallPlan(tool="get_active_document", arguments={}),
            ToolCallPlan(tool="get_face_mapping_store_info", arguments={}),
        ]
        result = await self.mcp.run_plan(plan)
        active = self._json_payload_at(result, 0)
        mcp_mapping_info = self._json_payload_at(result, 1)
        mcp_mapping_path = self._mapping_payload_path(mcp_mapping_info)
        matches = self._paths_match(expected, self._payload_path(active)) if expected else None
        mapping_matches = self._paths_match(expected_mapping_path, mcp_mapping_path) if mcp_mapping_path else None
        return McpHealthResult(
            status=result.status,
            message=result.message if result.status != "ok" else "MCP health probe completed.",
            activeDocument=active if isinstance(active, dict) else None,
            expectedAssemblyPath=expected,
            activeAssemblyMatchesState=matches,
            faceMappingPath=expected_mapping_path,
            mcpFaceMappingPath=mcp_mapping_path,
            faceMappingPathsMatch=mapping_matches,
            mcpFaceMappingInfo=mcp_mapping_info if isinstance(mcp_mapping_info, dict) else None,
            toolResults=result.tool_results,
        )

    def list_layout_json_files(self) -> list[LayoutJsonInfo]:
        workspace = self._workspace()
        candidates = [
            *(workspace / "demo").glob("*.json"),
            *(workspace / "demo" / "uploaded_layouts").glob("*.json"),
        ]
        results: list[LayoutJsonInfo] = []
        for path in sorted({item.resolve() for item in candidates}):
            if path.name.startswith("demo_state"):
                continue
            info = self._read_layout_info(path)
            if info is not None:
                results.append(info)
        return results

    def select_layout_json(self, request: SelectLayoutJsonRequest) -> OperationResult:
        state = self.store.load()
        self._normalize_state(state)

        path = self._resolve_workspace_path(request.layout_json_path)
        info = self._read_layout_info(path)
        if info is None:
            return OperationResult(
                status="error",
                message=f"Layout JSON is missing or invalid: {path}",
                state=state,
            )

        state.layout_json_path = str(path)
        state.layout_info = info
        if request.sync_components:
            self._sync_components_from_layout(state, info)
        self.store.save(state)
        return OperationResult(
            status="ok",
            message=f"Selected layout JSON: {path}",
            state=state,
            layoutInfo=info,
        )

    def upload_layout_json(self, request: UploadLayoutJsonRequest) -> OperationResult:
        state = self.store.load()
        self._normalize_state(state)

        try:
            parsed = json.loads(request.content)
        except json.JSONDecodeError as exc:
            return OperationResult(
                status="error",
                message=f"Uploaded layout JSON is not valid JSON: {exc}",
                state=state,
            )

        safe_name = Path(request.file_name).name or "uploaded_layout.json"
        if not safe_name.lower().endswith(".json"):
            safe_name += ".json"
        output_dir = self._workspace() / "demo" / "uploaded_layouts"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / safe_name
        output_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

        return self.select_layout_json(
            SelectLayoutJsonRequest(layoutJsonPath=str(output_path), syncComponents=request.sync_components)
        )

    async def verify_face_mappings(self) -> OperationResult:
        # 前端 Verify Faces 的后端入口。
        # 先做本地 face_mappings.json 缺失检查，再确认 SolidWorks 活动装配体与 state.assembly_path 一致；
        # 通过后，对每个组件依次调用 select_face_by_name + get_selected_face_mapping_probe。
        # 这一步不修改装配体，只验证“记录的底面能否被选回，以及选回后是否能读取中心/法向”。
        state = self.store.load()
        self._normalize_state(state)

        missing = self.face_mappings.missing_bottom_mappings(state.components)
        if missing:
            result = OperationResult(
                status="blocked",
                message="Some components are missing bottom-face mappings. Record mappings before running Common Base or Replay Layout.",
                missingFaceMappings=missing,
                state=state,
            )
            state.last_run = {
                "status": result.status,
                "message": result.message,
                "missingFaceMappings": missing,
            }
            self.store.save(state)
            return result

        active_check = await self._check_active_assembly_matches_state(state)
        if active_check is not None:
            return active_check

        plan: list[ToolCallPlan] = []
        for component in state.components:
            plan.extend(
                [
                    ToolCallPlan(
                        tool="select_face_by_name",
                        arguments={
                            "componentName": component.component_name,
                            "faceName": component.bottom_face_name,
                            "append": False,
                            "mark": 0,
                        },
                    ),
                    ToolCallPlan(
                        tool="get_selected_face_mapping_probe",
                        arguments={
                            "componentName": component.component_name,
                            "faceName": component.bottom_face_name,
                        },
                    ),
                ]
            )

        result = await self.mcp.run_plan(plan)
        state.last_run = {
            "status": result.status,
            "message": result.message,
            "toolResults": result.tool_results,
            "missingFaceMappings": [],
        }
        self.store.save(state)
        result.state = state
        return result

    async def import_components(self) -> OperationResult:
        state = self.store.load()
        plan = [
            ToolCallPlan(tool="NewDocument", arguments={"type": "Assembly"}),
            *[
                ToolCallPlan(
                    tool="InsertComponent",
                    arguments={
                        "filePath": component.file_path,
                        "x": component.target.x,
                        "y": component.target.y,
                        "z": component.target.z,
                    },
                )
                for component in state.components
            ],
        ]
        result = await self.mcp.run_plan(plan)
        result.state = state
        return result

    async def align_bottom(self) -> OperationResult:
        state = self.store.load()
        self._normalize_state(state)
        result = await self._ensure_common_base_ready(state)
        result.state = state
        return result

    async def initialize_common_base(self, request: ApplyLayoutRequest) -> OperationResult:
        state = self._merge_targets(self.store.load(), request)
        self._normalize_state(state)
        self.store.save(state)

        if state.assembly_path:
            return OperationResult(
                status="ok",
                message="Common-base assembly is already initialized. Use finalize once, then arrange to move components.",
                state=state,
            )

        if len(state.components) > self.initialize_batch_size:
            return await self._initialize_common_base_batched(state)

        plan = self._initialize_plan(state, align_bottom=False)
        result = await self.mcp.run_plan(plan)
        self._apply_arrange_outcome(result, state)
        result.state = state
        return result

    async def finalize_common_base(self) -> OperationResult:
        state = self.store.load()
        self._normalize_state(state)
        result = await self._ensure_common_base_ready(state)
        result.state = state
        return result

    async def capture_common_base_layout(self) -> OperationResult:
        state = self.store.load()
        self._normalize_state(state)

        if not state.assembly_path:
            return OperationResult(
                status="blocked",
                message="Assembly has not been initialized. Run initialize before capturing layout2d.",
                state=state,
            )

        missing = self.face_mappings.missing_bottom_mappings(state.components)
        if missing:
            return OperationResult(
                status="blocked",
                message="Please record bottom face mappings before capturing layout2d.",
                missingFaceMappings=missing,
                state=state,
            )

        plan = self._capture_common_base_layout_plan(state)
        result = await self.mcp.run_plan(plan)
        self._apply_arrange_outcome(result, state, promote_targets=False)
        result.state = state
        return result

    async def discover_components(self, request: DiscoverComponentsRequest) -> OperationResult:
        state = self.store.load()
        self._normalize_state(state)
        default_bottom_face_name = self._normalize_face_name(request.default_bottom_face_name)
        plan = [
            ToolCallPlan(
                tool=DISCOVER_LAYOUT_COMPONENTS_TOOL,
                arguments={
                    "sourceAssemblyPath": request.source_assembly_path,
                    "scope": request.scope,
                    "includeParts": request.include_parts,
                    "includeSuppressed": request.include_suppressed,
                    "defaultBottomFaceName": default_bottom_face_name,
                },
            )
        ]
        result = await self.mcp.run_plan(plan)
        payload = self._arrange_payload(result)
        discovery = None
        if isinstance(payload, dict):
            try:
                discovery = DiscoveryResult.model_validate(payload)
            except ValueError:
                discovery = None
        if result.status == "ok" and discovery is None:
            result.status = "error"
            result.message = "MCP tool did not return a parseable discovery result."
        result.discovery = discovery
        result.state = state
        state.last_run = {
            "status": result.status,
            "message": result.message,
            "discovery": payload,
        }
        self.store.save(state)
        return result

    def sync_discovered_components(self, request: SyncDiscoveredComponentsRequest) -> OperationResult:
        state = self.store.load()
        duplicate_names = self._duplicate_component_names([item.component_name for item in request.components])
        if duplicate_names:
            state.last_run = {
                "status": "blocked",
                "message": "Discovered components contain duplicate componentName values.",
                "duplicateComponentNames": duplicate_names,
            }
            self.store.save(state)
            return OperationResult(
                status="blocked",
                message=(
                    "Discovered components contain duplicate componentName values. "
                    "Filter the recursive discovery result or use top-level discovery before syncing. "
                    f"Duplicates: {', '.join(duplicate_names)}"
                ),
                state=state,
            )

        components: list[DemoComponent] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(request.components, start=1):
            component_id = self._component_id(item.component_name, index, seen_ids)
            bottom_face_name = self._normalize_face_name(item.default_bottom_face_name)
            components.append(
                DemoComponent(
                    id=component_id,
                    displayName=item.display_name or item.component_name,
                    componentName=item.component_name,
                    filePath=item.file_path,
                    bottomFaceName=bottom_face_name,
                    current=Coordinate(),
                    target=Coordinate(),
                )
            )

        state.components = components
        state.common_base_ready = False
        state.last_run = {
            "status": "ok",
            "message": f"Synced {len(components)} discovered components into demo state.",
        }
        self.store.save(state)
        return OperationResult(
            status="ok",
            message=f"Synced {len(components)} discovered components into demo state.",
            state=state,
        )

    async def capture_project_layout(self, request: CaptureProjectLayoutRequest) -> OperationResult:
        state = self.store.load()
        self._normalize_state(state)

        missing = self.face_mappings.missing_bottom_mappings(state.components)
        if missing:
            return OperationResult(
                status="blocked",
                message="Please record bottom face mappings before generating a project layout JSON.",
                missingFaceMappings=missing,
                state=state,
            )

        workspace = self._workspace()
        output_path = request.output_path or str(workspace / "demo" / "project_layout2d.json")
        project_config_path = request.project_config_path or str(workspace / "demo" / "project_config.json")
        plan = [
            ToolCallPlan(
                tool=CAPTURE_COMMON_BASE_LAYOUT_TOOL,
                arguments={
                    "sourceAssemblyPath": request.source_assembly_path or state.assembly_path,
                    "baseComponentName": request.base_component_name
                    or (state.components[0].component_name if state.components else None),
                    "outputPath": output_path,
                    "components": [
                        {
                            "componentName": component.component_name,
                            "bottomFaceName": component.bottom_face_name,
                        }
                        for component in state.components
                    ],
                },
            )
        ]
        result = await self.mcp.run_plan(plan)
        self._apply_arrange_outcome(result, state, promote_targets=False)
        if result.status == "ok":
            self._write_project_config(
                state=self.store.load(),
                source_assembly_path=request.source_assembly_path or state.assembly_path,
                base_component_name=request.base_component_name
                or (state.components[0].component_name if state.components else None),
                layout_json_path=output_path,
                project_config_path=project_config_path,
            )
            state = self.store.load()
            self._normalize_state(state)
            last_run = state.last_run if isinstance(state.last_run, dict) else {}
            last_run["projectConfigPath"] = str(self._resolve_workspace_path(project_config_path))
            state.last_run = last_run
            self.store.save(state)
        result.state = state
        return result

    async def apply_captured_layout(self, request: ApplyCapturedLayoutRequest | None = None) -> OperationResult:
        state = self.store.load()
        self._normalize_state(state)

        if not state.assembly_path:
            return OperationResult(
                status="blocked",
                message="Assembly has not been initialized. Run initialize before replaying captured layout2d.",
                state=state,
            )

        plan = self._apply_captured_layout_plan(state)
        result = await self.mcp.run_plan(plan)
        self._apply_arrange_outcome(result, state, promote_targets=False)
        if result.status == "ok":
            await self._append_replay_validation(
                state,
                xy_tolerance_meters=(
                    request.xy_tolerance_meters
                    if request and request.xy_tolerance_meters is not None
                    else self.replay_xy_tolerance_meters
                ),
                theta_tolerance_degrees=(
                    request.theta_tolerance_degrees
                    if request and request.theta_tolerance_degrees is not None
                    else self.replay_theta_tolerance_degrees
                ),
            )
            state = self.store.load()
            self._normalize_state(state)
        result.state = state
        return result

    async def record_selected_face(self, request: RecordSelectedFaceRequest) -> OperationResult:
        state = self.store.load()
        self._normalize_state(state)
        plan = [
            ToolCallPlan(
                tool="record_face_mapping",
                arguments={
                    "componentName": request.component_name,
                    "faceName": request.face_name,
                },
            ),
            ToolCallPlan(
                tool="get_selected_face_mapping_probe",
                arguments={
                    "componentName": request.component_name,
                    "faceName": request.face_name,
                },
            ),
        ]
        result = await self.mcp.run_plan(plan)
        self._repair_mojibake_face_mapping_key(request.component_name, request.face_name)
        state.last_run = {
            "status": result.status,
            "message": result.message,
            "toolResults": result.tool_results,
        }
        self.store.save(state)
        result.state = state
        return result

    def _repair_mojibake_face_mapping_key(self, component_name: str, face_name: str) -> None:
        if face_name == "??":
            return

        path = self.face_mappings.mapping_path
        mappings = self.face_mappings.load()
        target_component_entry = mappings.setdefault(component_name, {})
        if not isinstance(target_component_entry, dict):
            return

        repaired = False
        mojibake_component_name = self._ascii_lossy_key(component_name)
        source_component_keys = [component_name]
        if mojibake_component_name != component_name:
            source_component_keys.append(mojibake_component_name)

        for source_component_key in source_component_keys:
            component_entry = mappings.get(source_component_key)
            if not isinstance(component_entry, dict):
                continue

            mojibake_entry = component_entry.get("??")
            if not isinstance(mojibake_entry, dict):
                continue

            target_component_entry[face_name] = mojibake_entry
            component_entry.pop("??", None)
            if source_component_key != component_name and not component_entry:
                mappings.pop(source_component_key, None)
            repaired = True

        if not repaired:
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(mappings, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _ascii_lossy_key(value: str) -> str:
        return "".join(char if ord(char) < 128 else "?" for char in value)

    async def apply_layout(self, request: ApplyLayoutRequest) -> OperationResult:
        if not request.use_llm:
            return await self.arrange(request)

        state = self._merge_targets(self.store.load(), request)
        self._normalize_state(state)
        self.store.save(state)

        if request.align_bottom:
            missing = self.face_mappings.missing_bottom_mappings(state.components)
            if missing:
                return OperationResult(
                    status="blocked",
                    message="\u8bf7\u8bb0\u5f55\u5e95\u9762\u6620\u5c04\u540e\u518d\u53d1\u9001\u5e03\u5c40\u3002\u672a\u8bb0\u5f55\u6620\u5c04\u65f6\u4e0d\u4f1a\u8c03\u7528 SelectFaceByName\u3002",
                    missingFaceMappings=missing,
                    state=state,
                )

        if request.use_llm:
            plan = await self.llm.plan_apply_layout(request)
        else:
            plan = self._arrange_plan(state, request.align_bottom)

        result = await self.mcp.run_plan(plan)
        self._apply_arrange_outcome(result, state)
        result.state = state
        return result

    async def arrange(self, request: ApplyLayoutRequest) -> OperationResult:
        state = self._merge_targets(self.store.load(), request)
        self._normalize_state(state)
        self.store.save(state)

        if request.align_bottom:
            missing = self.face_mappings.missing_bottom_mappings(state.components)
            if missing:
                return OperationResult(
                    status="blocked",
                    message="\u8bf7\u8bb0\u5f55\u5e95\u9762\u6620\u5c04\u540e\u518d\u53d1\u9001\u5e03\u5c40\u3002\u672a\u8bb0\u5f55\u6620\u5c04\u65f6\u4e0d\u4f1a\u8c03\u7528 SelectFaceByName\u3002",
                    missingFaceMappings=missing,
                    state=state,
                )

        if not state.assembly_path:
            return OperationResult(
                status="blocked",
                message="Assembly has not been initialized. Run initialize first, then finalize common base, then arrange.",
                state=state,
            )

        plan = self._arrange_plan(state, request.align_bottom)
        if request.align_bottom and state.assembly_path and not state.common_base_ready:
            return OperationResult(
                status="blocked",
                message=(
                    "Common-base assembly has been initialized but common-base mating is not ready. "
                    "Run finalize common base once, verify/remap bottom faces if needed, then arrange again."
                ),
                state=state,
            )

        result = await self.mcp.run_plan(plan)
        self._apply_arrange_outcome(result, state)
        result.state = state
        return result

    @staticmethod
    def _select_bottom_face_plan(state: DemoState) -> list[ToolCallPlan]:
        return [
            ToolCallPlan(
                tool="SelectFaceByName",
                arguments={
                    "faceName": component.bottom_face_name,
                    "componentName": component.component_name,
                    "append": index > 0,
                },
            )
            for index, component in enumerate(state.components)
        ]

    @staticmethod
    def _merge_targets(state: DemoState, request: ApplyLayoutRequest) -> DemoState:
        by_id = {component.id: component for component in state.components}
        by_name = {component.component_name: component for component in state.components}

        for target in request.components:
            component = None
            if target.id:
                component = by_id.get(target.id)
            if component is None and target.component_name:
                component = by_name.get(target.component_name)
            if component is None:
                continue
            component.target = Coordinate(x=target.x, y=target.y, z=target.z)

        return state

    def _arrange_plan(self, state: DemoState, align_bottom: bool) -> list[ToolCallPlan]:
        if state.assembly_path:
            return DemoService._move_existing_plan(state)
        return self._initialize_plan(state, align_bottom)

    def _initialize_plan(self, state: DemoState, align_bottom: bool) -> list[ToolCallPlan]:
        workspace = Path(__file__).resolve().parents[5]
        arguments = {
            "outputAssemblyPath": str(self.target_assembly_path),
            "basePlaneName": "Front Plane",
            "basePlaneSelectionType": "PLANE",
            "screenshotPath": str(workspace / "demo" / "arrange_result_frontend.png"),
            "screenshotWidth": 1600,
            "screenshotHeight": 900,
            "includeScreenshotBase64Data": False,
            "components": [
                {
                    "componentName": component.component_name,
                    "filePath": component.file_path,
                    "x": component.target.x,
                    "y": component.target.y,
                    "z": component.target.z,
                    "bottomFaceName": component.bottom_face_name,
                    "currentX": component.current.x,
                    "currentY": component.current.y,
                    "currentZ": component.current.z,
                }
                for component in state.components
            ],
        }

        return [
            ToolCallPlan(
                tool=INITIALIZE_COMMON_BASE_ASSEMBLY_TOOL,
                arguments=arguments,
            )
        ]

    async def _initialize_common_base_batched(self, state: DemoState) -> OperationResult:
        workspace = Path(__file__).resolve().parents[5]
        output_assembly_path = str(self.target_assembly_path)
        screenshot_path = str(workspace / "demo" / "arrange_result_frontend.png")
        batches = [
            state.components[index : index + self.initialize_batch_size]
            for index in range(0, len(state.components), self.initialize_batch_size)
        ]
        batch_records: list[dict] = []
        all_tool_results: list[dict] = []
        inserted_components: list[dict] = []
        final_payload: dict | None = None

        for batch_index, batch in enumerate(batches, start=1):
            is_final_batch = batch_index == len(batches)
            plan = [
                ToolCallPlan(
                    tool=APPEND_COMPONENTS_TO_COMMON_BASE_ASSEMBLY_TOOL,
                    arguments={
                        "components": [
                            self._component_initialize_argument(component)
                            for component in batch
                        ],
                        "outputAssemblyPath": output_assembly_path,
                        "basePlaneName": "Front Plane",
                        "basePlaneSelectionType": "PLANE",
                        "screenshotPath": screenshot_path if is_final_batch else None,
                        "screenshotWidth": 1600,
                        "screenshotHeight": 900,
                        "includeScreenshotBase64Data": False,
                    },
                )
            ]
            result = await self.mcp.run_plan(plan)
            all_tool_results.extend(result.tool_results)
            payload = self._arrange_payload(result)
            final_payload = payload or final_payload
            if payload:
                self._apply_assembly_path_from_payload(state, payload)
                inserted_components.extend(payload.get("components", []) if isinstance(payload.get("components"), list) else [])

            batch_record = {
                "batchIndex": batch_index,
                "batchCount": len(batches),
                "componentCount": len(batch),
                "components": [component.component_name for component in batch],
                "status": result.status,
                "message": result.message,
                "toolSuccess": payload.get("success") if isinstance(payload, dict) else None,
                "toolMessage": payload.get("message") if isinstance(payload, dict) else None,
            }
            batch_records.append(batch_record)
            state.last_run = {
                "status": result.status,
                "message": result.message,
                "assemblyPath": state.assembly_path,
                "initializationMode": "batched",
                "initializeBatchSize": self.initialize_batch_size,
                "initializationBatches": batch_records,
            }
            self.store.save(state)

            if result.status != "ok" or not payload or not payload.get("success"):
                return OperationResult(
                    status=result.status if result.status != "ok" else "error",
                    message=(
                        f"Batch initialization stopped at batch {batch_index}/{len(batches)}: "
                        f"{payload.get('message') if isinstance(payload, dict) else result.message}"
                    ),
                    toolResults=all_tool_results,
                    state=state,
                )

        state.common_base_ready = False
        state.last_run = {
            "status": "ok",
            "message": f"Batched InitializeCommonBaseAssembly completed in {len(batches)} batches.",
            "toolSuccess": True,
            "toolMessage": final_payload.get("message") if isinstance(final_payload, dict) else None,
            "assemblyPath": state.assembly_path or output_assembly_path,
            "screenshotPath": (
                final_payload.get("screenshot", {}).get("outputPath")
                if isinstance(final_payload, dict) and isinstance(final_payload.get("screenshot"), dict)
                else None
            ),
            "components": inserted_components,
            "initializationMode": "batched",
            "initializeBatchSize": self.initialize_batch_size,
            "initializationBatches": batch_records,
        }
        if not state.assembly_path:
            state.assembly_path = output_assembly_path
        self.store.save(state)
        return OperationResult(
            status="ok",
            message=f"Batched InitializeCommonBaseAssembly completed in {len(batches)} batches.",
            toolResults=all_tool_results,
            state=state,
        )

    @staticmethod
    def _component_initialize_argument(component: DemoComponent) -> dict:
        return {
            "componentName": component.component_name,
            "filePath": component.file_path,
            "x": component.target.x,
            "y": component.target.y,
            "z": component.target.z,
            "bottomFaceName": component.bottom_face_name,
            "currentX": component.current.x,
            "currentY": component.current.y,
            "currentZ": component.current.z,
        }

    @staticmethod
    def _move_existing_plan(state: DemoState) -> list[ToolCallPlan]:
        workspace = Path(__file__).resolve().parents[5]
        arguments = {
            "assemblyPath": state.assembly_path,
            "basePlaneName": "Front Plane",
            "screenshotPath": str(workspace / "demo" / "arrange_result_frontend.png"),
            "screenshotWidth": 1600,
            "screenshotHeight": 900,
            "includeScreenshotBase64Data": False,
            "components": [
                {
                    "componentName": component.component_name,
                    "x": component.target.x,
                    "y": component.target.y,
                    "z": component.target.z,
                    "bottomFaceName": component.bottom_face_name,
                    "currentX": component.current.x,
                    "currentY": component.current.y,
                    "currentZ": component.current.z,
                }
                for component in state.components
            ],
        }

        return [
            ToolCallPlan(
                tool=MOVE_COMPONENTS_ON_COMMON_BASE_TOOL,
                arguments=arguments,
            )
        ]

    @staticmethod
    def _finalize_common_base_plan(
        state: DemoState,
        components: list[DemoComponent] | None = None,
        include_screenshot: bool = True,
    ) -> list[ToolCallPlan]:
        # Common Base 的 MCP 调用计划。
        # 后端只把组件名、底面名、当前/目标坐标和 assemblyPath 传给 MCP；
        # 真正的选面、mate、法向检查都在 DemoTools.FinalizeCommonBaseAssembly 中完成。
        workspace = Path(__file__).resolve().parents[5]
        selected_components = components or state.components
        arguments = {
            "assemblyPath": state.assembly_path,
            "screenshotPath": str(workspace / "demo" / "arrange_result_frontend.png") if include_screenshot else None,
            "screenshotWidth": 1600,
            "screenshotHeight": 900,
            "includeScreenshotBase64Data": False,
            "components": [
                {
                    "componentName": component.component_name,
                    "x": component.target.x,
                    "y": component.target.y,
                    "z": component.target.z,
                    "bottomFaceName": component.bottom_face_name,
                    "currentX": component.current.x,
                    "currentY": component.current.y,
                    "currentZ": component.current.z,
                }
                for component in selected_components
            ],
        }

        return [
            ToolCallPlan(
                tool=FINALIZE_COMMON_BASE_ASSEMBLY_TOOL,
                arguments=arguments,
            )
        ]

    @staticmethod
    def _capture_common_base_layout_plan(state: DemoState) -> list[ToolCallPlan]:
        workspace = Path(__file__).resolve().parents[5]
        return [
            ToolCallPlan(
                tool=CAPTURE_COMMON_BASE_LAYOUT_TOOL,
                arguments={
                    "sourceAssemblyPath": state.assembly_path,
                    "baseComponentName": state.components[0].component_name if state.components else None,
                    "outputPath": str(workspace / "demo" / "captured_common_base_layout.json"),
                    "components": [
                        {
                            "componentName": component.component_name,
                            "bottomFaceName": component.bottom_face_name,
                        }
                        for component in state.components
                    ],
                },
            )
        ]

    @staticmethod
    def _apply_captured_layout_plan(state: DemoState) -> list[ToolCallPlan]:
        # Replay Layout 的 MCP 调用计划。
        # layout JSON 中保存了每个组件相对共同底平面的 x/y/theta；
        # MCP 会再次选回底面并 probe 当前中心，再用 MoveComponent/RotateComponent 恢复到 layout2d 指定位置。
        workspace = Path(__file__).resolve().parents[5]
        layout_path = state.layout_json_path or str(workspace / "demo" / "captured_common_base_layout.json")
        return [
            ToolCallPlan(
                tool=APPLY_CAPTURED_COMMON_BASE_LAYOUT_TOOL,
                arguments={
                    "layoutJsonPath": layout_path,
                    "assemblyPath": state.assembly_path,
                    "screenshotPath": str(workspace / "demo" / "apply_captured_layout_result.png"),
                    "screenshotWidth": 1600,
                    "screenshotHeight": 900,
                    "includeScreenshotBase64Data": False,
                },
            )
        ]

    @staticmethod
    def _normalize_state(state: DemoState) -> None:
        for component in state.components:
            component.bottom_face_name = DemoService._normalize_face_name(component.bottom_face_name)

    @staticmethod
    def _normalize_face_name(face_name: str | None) -> str:
        if not face_name or face_name in {"??", "\u6434\u66df\u6f70", "\u6434\u66e2\u6f70", "\u4e45\u4e2d", "\u6401\u66e6\u6f70"}:
            return "\u5e95\u9762"
        return face_name

    @staticmethod
    def _promote_targets_to_current(state: DemoState) -> None:
        for component in state.components:
            component.current = Coordinate(
                x=component.target.x,
                y=component.target.y,
                z=component.target.z,
            )

    def _apply_arrange_outcome(self, result: OperationResult, state: DemoState, promote_targets: bool = True) -> None:
        if result.status != "ok":
            state.last_run = {
                "status": result.status,
                "message": result.message,
            }
            self.store.save(state)
            return

        payload = self._arrange_payload(result)
        if not payload:
            result.status = "error"
            result.message = "MCP tool did not return a parseable arrange result."
            state.last_run = {
                "status": result.status,
                "message": result.message,
            }
            self.store.save(state)
            return

        self._apply_assembly_path_from_payload(state, payload)
        last_tool = result.plan[-1].tool if result.plan else None
        if last_tool == INITIALIZE_COMMON_BASE_ASSEMBLY_TOOL:
            state.common_base_ready = False
        if last_tool == CAPTURE_COMMON_BASE_LAYOUT_TOOL:
            output_path = payload.get("outputPath")
            if isinstance(output_path, str) and output_path.strip():
                layout_path = self._resolve_workspace_path(output_path)
                state.layout_json_path = str(layout_path)
                state.layout_info = self._read_layout_info(layout_path)

        if not payload.get("success"):
            result.status = "error"
            result.message = str(payload.get("message") or "MCP arrange tool reported failure.")
            state.last_run = self._last_run_from_payload(result, payload)
            self.store.save(state)
            return

        if promote_targets:
            self._promote_targets_to_current(state)
        state.last_run = self._last_run_from_payload(result, payload)
        self.store.save(state)

    async def _ensure_common_base_ready(self, state: DemoState) -> OperationResult:
        if not state.assembly_path:
            return OperationResult(
                status="blocked",
                message="Assembly has not been initialized yet. Run arrange once to create ABC_arrange_demo.SLDASM.",
                state=state,
            )

        missing = self.face_mappings.missing_bottom_mappings(state.components)
        if missing:
            return OperationResult(
                status="blocked",
                message="\u8bf7\u8bb0\u5f55\u5e95\u9762\u6620\u5c04\u540e\u518d\u6267\u884c\u5171\u5e95\u9762\u64cd\u4f5c\u3002",
                missingFaceMappings=missing,
                state=state,
            )

        if len(state.components) > self.initialize_batch_size:
            return await self._ensure_common_base_ready_batched(state)

        plan = self._finalize_common_base_plan(state)
        result = await self.mcp.run_plan(plan)
        if result.status != "ok":
            state.last_run = {
                "status": result.status,
                "message": result.message,
            }
            self.store.save(state)
            return result

        payload = self._arrange_payload(result)
        if not payload:
            result.status = "error"
            result.message = "MCP tool did not return a parseable common-base result."
            state.last_run = {
                "status": result.status,
                "message": result.message,
            }
            self.store.save(state)
            return result

        self._apply_assembly_path_from_payload(state, payload)
        state.common_base_ready = bool(payload.get("success"))
        if not payload.get("success"):
            result.status = "error"
            result.message = str(payload.get("message") or "MCP common-base tool reported failure.")

        state.last_run = self._last_run_from_payload(result, payload)
        self.store.save(state)
        return result

    async def _ensure_common_base_ready_batched(self, state: DemoState) -> OperationResult:
        # 10+ 组件场景下的分批 Common Base。
        # 每批都带上第一个组件作为 anchor，只把一部分 target 与 anchor 做共底面，
        # 这样可以降低单次 SolidWorks mate/重建的耗时和卡顿风险。
        # 需要注意：如果某一批的面映射选错或法向异常，后续批次会停止，前端会保留该批的诊断信息。
        anchor = state.components[0]
        target_batch_size = max(1, self.initialize_batch_size - 1)
        targets = state.components[1:]
        batches = [
            targets[index : index + target_batch_size]
            for index in range(0, len(targets), target_batch_size)
        ]
        batch_records: list[dict] = []
        all_tool_results: list[dict] = []
        all_components: list[dict] = []
        all_corrections: list[dict] = []
        all_checks: list[dict] = []
        final_payload: dict | None = None

        for batch_index, target_batch in enumerate(batches, start=1):
            is_final_batch = batch_index == len(batches)
            batch_components = [anchor, *target_batch]
            plan = self._finalize_common_base_plan(
                state,
                components=batch_components,
                include_screenshot=is_final_batch,
            )
            result = await self.mcp.run_plan(plan)
            all_tool_results.extend(result.tool_results)
            payload = self._arrange_payload(result)
            final_payload = payload or final_payload
            if isinstance(payload, dict):
                all_components.extend(payload.get("components", []) if isinstance(payload.get("components"), list) else [])
                all_corrections.extend(
                    payload.get("orientationCorrections", [])
                    if isinstance(payload.get("orientationCorrections"), list)
                    else []
                )
                all_checks.extend(
                    payload.get("orientationChecks", [])
                    if isinstance(payload.get("orientationChecks"), list)
                    else []
                )
                self._apply_assembly_path_from_payload(state, payload)

            batch_record = {
                "batchIndex": batch_index,
                "batchCount": len(batches),
                "anchorComponent": anchor.component_name,
                "targetComponents": [component.component_name for component in target_batch],
                "status": result.status,
                "message": result.message,
                "toolSuccess": payload.get("success") if isinstance(payload, dict) else None,
                "toolMessage": payload.get("message") if isinstance(payload, dict) else None,
            }
            batch_records.append(batch_record)
            state.last_run = {
                "status": result.status,
                "message": result.message,
                "assemblyPath": state.assembly_path,
                "commonBaseMode": "batched",
                "commonBaseBatchSize": self.initialize_batch_size,
                "commonBaseBatches": batch_records,
                "orientationCorrections": all_corrections,
                "orientationChecks": all_checks,
            }
            self.store.save(state)

            if result.status != "ok" or not payload or not payload.get("success"):
                return OperationResult(
                    status=result.status if result.status != "ok" else "error",
                    message=(
                        f"Batched common-base stopped at batch {batch_index}/{len(batches)}: "
                        f"{payload.get('message') if isinstance(payload, dict) else result.message}"
                    ),
                    toolResults=all_tool_results,
                    state=state,
                )

        state.common_base_ready = True
        state.last_run = {
            "status": "ok",
            "message": f"Batched FinalizeCommonBaseAssembly completed in {len(batches)} batches.",
            "toolSuccess": True,
            "toolMessage": final_payload.get("message") if isinstance(final_payload, dict) else None,
            "assemblyPath": state.assembly_path,
            "screenshotPath": (
                final_payload.get("screenshot", {}).get("outputPath")
                if isinstance(final_payload, dict) and isinstance(final_payload.get("screenshot"), dict)
                else None
            ),
            "components": all_components,
            "commonBaseMode": "batched",
            "commonBaseBatchSize": self.initialize_batch_size,
            "commonBaseBatches": batch_records,
            "orientationCorrections": all_corrections,
            "orientationChecks": all_checks,
        }
        self.store.save(state)
        return OperationResult(
            status="ok",
            message=f"Batched FinalizeCommonBaseAssembly completed in {len(batches)} batches.",
            toolResults=all_tool_results,
            state=state,
        )

    async def _check_active_assembly_matches_state(self, state: DemoState) -> OperationResult | None:
        if not state.assembly_path or self.mcp.mode == "dry-run":
            return None

        plan = [ToolCallPlan(tool="get_active_document", arguments={})]
        result = await self.mcp.run_plan(plan)
        active = self._first_json_payload(result)
        active_path = self._payload_path(active)
        if result.status != "ok":
            state.last_run = {
                "status": result.status,
                "message": result.message,
                "activeDocumentCheck": {
                    "expectedAssemblyPath": state.assembly_path,
                    "activeDocument": active,
                    "matches": False,
                },
            }
            self.store.save(state)
            return OperationResult(
                status="blocked",
                message=f"Could not verify active SolidWorks assembly before selecting faces: {result.message}",
                state=state,
            )

        if not self._paths_match(state.assembly_path, active_path):
            state.last_run = {
                "status": "blocked",
                "message": "Active SolidWorks assembly does not match demo_state assemblyPath.",
                "activeDocumentCheck": {
                    "expectedAssemblyPath": state.assembly_path,
                    "activeDocument": active,
                    "activeDocumentPath": active_path,
                    "matches": False,
                },
            }
            self.store.save(state)
            return OperationResult(
                status="blocked",
                message=(
                    "Active SolidWorks assembly does not match demo_state assemblyPath. "
                    "Open or activate the expected assembly before Verify Faces."
                ),
                state=state,
            )

        return None

    async def _append_replay_validation(
        self,
        state: DemoState,
        xy_tolerance_meters: float,
        theta_tolerance_degrees: float,
    ) -> None:
        if not state.assembly_path or not state.layout_json_path or self.mcp.mode == "dry-run":
            return

        validation_path = self._workspace() / "demo" / "replay_validation_layout2d.json"
        plan = [
            ToolCallPlan(
                tool=CAPTURE_COMMON_BASE_LAYOUT_TOOL,
                arguments={
                    "sourceAssemblyPath": state.assembly_path,
                    "baseComponentName": state.components[0].component_name if state.components else None,
                    "outputPath": str(validation_path),
                    "components": [
                        {
                            "componentName": component.component_name,
                            "bottomFaceName": component.bottom_face_name,
                        }
                        for component in state.components
                    ],
                },
            )
        ]
        capture_result = await self.mcp.run_plan(plan)
        target_payload = self._read_json_file_payload(Path(state.layout_json_path))
        actual_payload = self._arrange_payload(capture_result)
        validation = self._compare_layout_payloads(
            target_payload,
            actual_payload,
            xy_tolerance_meters=xy_tolerance_meters,
            theta_tolerance_degrees=theta_tolerance_degrees,
        )
        validation["captureStatus"] = capture_result.status
        validation["captureMessage"] = capture_result.message
        validation["captureOutputPath"] = str(validation_path)

        state = self.store.load()
        self._normalize_state(state)
        last_run = state.last_run if isinstance(state.last_run, dict) else {}
        last_run["replayValidation"] = validation
        state.last_run = last_run
        self.store.save(state)

    @staticmethod
    def _first_json_payload(result: OperationResult) -> dict | None:
        return DemoService._json_payload_at(result, 0)

    @staticmethod
    def _json_payload_at(result: OperationResult, index: int) -> dict | None:
        if not result.tool_results:
            return None
        if index < 0 or index >= len(result.tool_results):
            return None
        texts = result.tool_results[index].get("text", [])
        if not isinstance(texts, list) or not texts:
            return None
        text = texts[-1]
        if not isinstance(text, str) or text.strip() == "null":
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _payload_path(payload: dict | None) -> str | None:
        if not isinstance(payload, dict):
            return None
        for key in ("path", "Path", "documentPath", "DocumentPath"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    @staticmethod
    def _mapping_payload_path(payload: dict | None) -> str | None:
        if not isinstance(payload, dict):
            return None
        for key in ("mappingPath", "MappingPath", "path", "Path"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    @staticmethod
    def _paths_match(left: str | None, right: str | None) -> bool | None:
        if not left or not right:
            return None
        try:
            return Path(left).resolve() == Path(right).resolve()
        except OSError:
            return str(left).lower().replace("/", "\\") == str(right).lower().replace("/", "\\")

    @staticmethod
    def _read_json_file_payload(path: Path) -> dict | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @classmethod
    def _compare_layout_payloads(
        cls,
        target: dict | None,
        actual: dict | None,
        xy_tolerance_meters: float = 1e-6,
        theta_tolerance_degrees: float = 1e-4,
    ) -> dict:
        if not isinstance(target, dict) or not isinstance(actual, dict):
            return {
                "success": False,
                "message": "Replay validation could not parse target or captured layout JSON.",
                "xyToleranceMeters": xy_tolerance_meters,
                "thetaToleranceDegrees": theta_tolerance_degrees,
                "components": [],
            }

        target_components = cls._layout_component_map(target)
        actual_components = cls._layout_component_map(actual)
        rows: list[dict] = []
        max_xy_error = 0.0
        max_theta_error = 0.0
        success = True
        for name, target_item in target_components.items():
            actual_item = actual_components.get(name)
            if actual_item is None:
                success = False
                rows.append(
                    {
                        "componentName": name,
                        "success": False,
                        "message": "Component missing from captured replay layout.",
                    }
                )
                continue

            target_layout = target_item.get("layout2d") if isinstance(target_item.get("layout2d"), dict) else {}
            actual_layout = actual_item.get("layout2d") if isinstance(actual_item.get("layout2d"), dict) else {}
            xy_error = cls._xy_error(target_layout, actual_layout)
            theta_error = cls._theta_error(target_layout, actual_layout)
            max_xy_error = max(max_xy_error, xy_error if xy_error is not None else 0.0)
            max_theta_error = max(max_theta_error, theta_error if theta_error is not None else 0.0)
            row_success = (xy_error is not None and xy_error <= xy_tolerance_meters) and (
                theta_error is None or theta_error <= theta_tolerance_degrees
            )
            success = success and row_success
            rows.append(
                {
                    "componentName": name,
                    "success": row_success,
                    "xyError": xy_error,
                    "thetaErrorDegrees": theta_error,
                    "xyToleranceMeters": xy_tolerance_meters,
                    "thetaToleranceDegrees": theta_tolerance_degrees,
                    "target": target_layout,
                    "actual": actual_layout,
                    "message": "ok" if row_success else "Replay layout differs from target.",
                }
            )

        return {
            "success": success,
            "message": "Replay validation completed." if success else "Replay validation found layout differences.",
            "maxXyError": max_xy_error,
            "maxThetaErrorDegrees": max_theta_error,
            "xyToleranceMeters": xy_tolerance_meters,
            "thetaToleranceDegrees": theta_tolerance_degrees,
            "components": rows,
        }

    @staticmethod
    def _layout_component_map(payload: dict) -> dict[str, dict]:
        result: dict[str, dict] = {}
        items = payload.get("components")
        if not isinstance(items, list):
            return result
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("componentName")
            if isinstance(name, str) and name.strip():
                result[name] = item
        return result

    @staticmethod
    def _xy_error(target_layout: dict, actual_layout: dict) -> float | None:
        try:
            dx = float(actual_layout["x"]) - float(target_layout["x"])
            dy = float(actual_layout["y"]) - float(target_layout["y"])
        except (KeyError, TypeError, ValueError):
            return None
        return (dx * dx + dy * dy) ** 0.5

    @classmethod
    def _theta_error(cls, target_layout: dict, actual_layout: dict) -> float | None:
        target = target_layout.get("thetaDegrees")
        actual = actual_layout.get("thetaDegrees")
        if target is None or actual is None:
            return None
        try:
            delta = float(actual) - float(target)
        except (TypeError, ValueError):
            return None
        return abs(cls._normalize_angle_degrees(delta))

    @staticmethod
    def _normalize_angle_degrees(value: float) -> float:
        normalized = (value + 180.0) % 360.0 - 180.0
        return 180.0 if normalized == -180.0 else normalized

    @staticmethod
    def _component_id(component_name: str, index: int, seen: set[str]) -> str:
        candidate = "".join(ch.lower() if ch.isalnum() else "-" for ch in component_name).strip("-")
        if not candidate:
            candidate = f"component-{index}"
        base = candidate
        suffix = 2
        while candidate in seen:
            candidate = f"{base}-{suffix}"
            suffix += 1
        seen.add(candidate)
        return candidate

    @staticmethod
    def _duplicate_component_names(names: list[str]) -> list[str]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for name in names:
            key = name.strip().lower()
            if not key:
                continue
            if key in seen:
                duplicates.add(name)
            seen.add(key)
        return sorted(duplicates, key=str.lower)

    @staticmethod
    def _apply_assembly_path_from_payload(state: DemoState, payload: dict) -> None:
        assembly_path = payload.get("assemblyPath")
        if isinstance(assembly_path, str) and assembly_path.strip():
            state.assembly_path = assembly_path

    @staticmethod
    def _last_run_from_payload(result: OperationResult, payload: dict) -> dict:
        screenshot = payload.get("screenshot") if isinstance(payload.get("screenshot"), dict) else None
        return {
            "status": result.status,
            "message": result.message,
            "toolSuccess": bool(payload.get("success")),
            "toolMessage": payload.get("message"),
            "assemblyPath": payload.get("assemblyPath"),
            "screenshotPath": screenshot.get("outputPath") if screenshot else None,
            "components": payload.get("components", []),
            "orientationCorrections": payload.get("orientationCorrections", []),
            "orientationChecks": payload.get("orientationChecks", []),
            "missingFaceMappings": payload.get("missingFaceMappings", []),
        }

    @staticmethod
    def _arrange_payload(result: OperationResult) -> dict | None:
        if not result.tool_results:
            return None

        last = result.tool_results[-1]
        texts = last.get("text", [])
        if not isinstance(texts, list) or not texts:
            return None

        try:
            payload = json.loads(texts[-1])
        except (TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _workspace() -> Path:
        return Path(__file__).resolve().parents[5]

    @classmethod
    def _resolve_workspace_path(cls, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else cls._workspace() / path

    def _write_project_config(
        self,
        state: DemoState,
        source_assembly_path: str | None,
        base_component_name: str | None,
        layout_json_path: str,
        project_config_path: str,
    ) -> None:
        output = self._resolve_workspace_path(project_config_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        layout_path = self._resolve_workspace_path(layout_json_path)
        payload = {
            "schemaVersion": 1,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceAssemblyPath": source_assembly_path,
            "targetAssemblyPath": state.assembly_path,
            "baseComponentName": base_component_name,
            "layoutJsonPath": str(layout_path),
            "faceMappingPath": str(self.face_mappings.mapping_path),
            "replayTolerance": {
                "xyMeters": self.replay_xy_tolerance_meters,
                "thetaDegrees": self.replay_theta_tolerance_degrees,
            },
            "components": [
                {
                    "id": component.id,
                    "displayName": component.display_name,
                    "componentName": component.component_name,
                    "filePath": component.file_path,
                    "bottomFaceName": component.bottom_face_name,
                    "enabled": True,
                }
                for component in state.components
            ],
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_layout_info(self, path: Path) -> LayoutJsonInfo | None:
        if not path.exists() or path.suffix.lower() != ".json":
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or "components" not in data:
            return None

        components: list[LayoutComponentSummary] = []
        for item in data.get("components", []):
            if not isinstance(item, dict):
                continue
            component_name = item.get("componentName")
            if not isinstance(component_name, str) or not component_name.strip():
                continue
            layout2d = item.get("layout2d") if isinstance(item.get("layout2d"), dict) else None
            components.append(
                LayoutComponentSummary(
                    componentName=component_name,
                    filePath=item.get("filePath") if isinstance(item.get("filePath"), str) else None,
                    bottomFaceName=item.get("bottomFaceName") if isinstance(item.get("bottomFaceName"), str) else "\u5e95\u9762",
                    layout2d=Layout2d.model_validate(layout2d) if layout2d else None,
                    faceMappingFound=item.get("faceMappingFound") if isinstance(item.get("faceMappingFound"), bool) else None,
                )
            )

        return LayoutJsonInfo(
            path=str(path),
            success=data.get("success") if isinstance(data.get("success"), bool) else None,
            message=data.get("message") if isinstance(data.get("message"), str) else None,
            baseComponentName=data.get("baseComponentName") if isinstance(data.get("baseComponentName"), str) else None,
            componentCount=len(components),
            components=components,
        )

    @staticmethod
    def _component_id_from_name(component_name: str, index: int) -> str:
        normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in component_name).strip("-")
        return normalized or f"component-{index + 1}"

    def _sync_components_from_layout(self, state: DemoState, info: LayoutJsonInfo) -> None:
        existing = {component.component_name: component for component in state.components}
        next_components: list[DemoComponent] = []
        for index, item in enumerate(info.components):
            existing_component = existing.get(item.component_name)
            layout = item.layout2d
            target = Coordinate(
                x=layout.x if layout else existing_component.target.x if existing_component else 0,
                y=layout.y if layout else existing_component.target.y if existing_component else 0,
                z=existing_component.target.z if existing_component else 0,
            )
            file_path = item.file_path or (existing_component.file_path if existing_component else "")
            next_components.append(
                DemoComponent(
                    id=existing_component.id if existing_component else self._component_id_from_name(item.component_name, index),
                    displayName=existing_component.display_name if existing_component else item.component_name,
                    componentName=item.component_name,
                    filePath=file_path,
                    bottomFaceName=item.bottom_face_name,
                    current=existing_component.current if existing_component else Coordinate(),
                    target=target,
                )
            )
        if next_components:
            state.components = next_components
