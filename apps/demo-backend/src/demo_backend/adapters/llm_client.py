from __future__ import annotations

from ..mcp_tools import ARRANGE_COMPONENTS_ON_COMMON_BASE_TOOL
from ..models import ApplyLayoutRequest, ToolCallPlan


class LlmClient:
    """Placeholder LLM adapter.

    The future implementation should call the selected model and let it choose
    the SolidWorks MCP tool invocation. For demo stability, this skeleton keeps
    the resulting tool plan deterministic.
    """

    def __init__(self, mode: str = "dry-run"):
        self.mode = mode

    async def plan_apply_layout(self, request: ApplyLayoutRequest) -> list[ToolCallPlan]:
        return [
            ToolCallPlan(
                tool=ARRANGE_COMPONENTS_ON_COMMON_BASE_TOOL,
                arguments={
                    "alignBottom": request.align_bottom,
                    "components": [
                        target.model_dump(by_alias=True)
                        for target in request.components
                    ],
                },
            )
        ]
