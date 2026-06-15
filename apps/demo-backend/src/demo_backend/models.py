from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0


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
