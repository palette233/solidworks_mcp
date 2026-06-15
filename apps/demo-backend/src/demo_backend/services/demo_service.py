from __future__ import annotations

import json
from pathlib import Path

from ..adapters.llm_client import LlmClient
from ..adapters.mcp_client import McpClient
from ..face_mappings import FaceMappingStore
from ..mcp_tools import ARRANGE_COMPONENTS_ON_COMMON_BASE_TOOL
from ..models import ApplyLayoutRequest, Coordinate, DemoState, OperationResult, ToolCallPlan
from ..state_store import DemoStateStore


class DemoService:
    def __init__(self, store: DemoStateStore, face_mappings: FaceMappingStore, llm: LlmClient, mcp: McpClient):
        self.store = store
        self.face_mappings = face_mappings
        self.llm = llm
        self.mcp = mcp

    def get_state(self) -> DemoState:
        state = self.store.load()
        self._normalize_state(state)
        return state

    def save_state(self, state: DemoState) -> DemoState:
        self._normalize_state(state)
        return self.store.save(state)

    def reset_state(self) -> DemoState:
        return self.store.reset()

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
        missing = self.face_mappings.missing_bottom_mappings(state.components)
        if missing:
            return OperationResult(
                status="blocked",
                message="\u8bf7\u8bb0\u5f55\u5e95\u9762\u6620\u5c04\u540e\u518d\u6267\u884c\u5171\u5e95\u9762\u64cd\u4f5c\u3002",
                missingFaceMappings=missing,
                state=state,
            )

        plan = [
            *[
                ToolCallPlan(
                    tool="SelectFaceByName",
                    arguments={
                        "faceName": component.bottom_face_name,
                        "componentName": component.component_name,
                        "append": index > 0,
                    },
                )
                for index, component in enumerate(state.components)
            ],
            ToolCallPlan(
                tool=ARRANGE_COMPONENTS_ON_COMMON_BASE_TOOL,
                arguments={
                    "components": [component.component_name for component in state.components],
                    "baseZ": 0,
                },
            )
        ]
        result = await self.mcp.run_plan(plan)
        result.state = state
        return result

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

        plan = self._arrange_plan(state, request.align_bottom)
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

    @staticmethod
    def _arrange_plan(state: DemoState, align_bottom: bool) -> list[ToolCallPlan]:
        workspace = Path(__file__).resolve().parents[5]
        arguments = {
            "alignBottom": align_bottom,
            "baseZ": 0,
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
        if state.assembly_path:
            arguments["assemblyPath"] = state.assembly_path

        return [
            ToolCallPlan(
                tool=ARRANGE_COMPONENTS_ON_COMMON_BASE_TOOL,
                arguments=arguments,
            )
        ]

    @staticmethod
    def _normalize_state(state: DemoState) -> None:
        for component in state.components:
            if component.bottom_face_name in {"\u6434\u66df\u6f70", "\u6434\u66e2\u6f70", "\u4e45\u4e2d"}:
                component.bottom_face_name = "\u5e95\u9762"

    @staticmethod
    def _promote_targets_to_current(state: DemoState) -> None:
        for component in state.components:
            component.current = Coordinate(
                x=component.target.x,
                y=component.target.y,
                z=component.target.z,
            )

    def _apply_arrange_outcome(self, result: OperationResult, state: DemoState) -> None:
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

        if not payload.get("success"):
            result.status = "error"
            result.message = str(payload.get("message") or "MCP arrange tool reported failure.")
            state.last_run = self._last_run_from_payload(result, payload)
            self.store.save(state)
            return

        self._promote_targets_to_current(state)
        state.last_run = self._last_run_from_payload(result, payload)
        self.store.save(state)

    @staticmethod
    def _last_run_from_payload(result: OperationResult, payload: dict) -> dict:
        screenshot = payload.get("screenshot") if isinstance(payload.get("screenshot"), dict) else None
        return {
            "status": result.status,
            "message": result.message,
            "toolSuccess": bool(payload.get("success")),
            "toolMessage": payload.get("message"),
            "screenshotPath": screenshot.get("outputPath") if screenshot else None,
            "components": payload.get("components", []),
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
