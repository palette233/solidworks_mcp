from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


class Settings:
    def __init__(self) -> None:
        self.app_name = os.environ.get("DEMO_APP_NAME", "SolidWorks Demo Backend")
        self.state_path = Path(
            os.environ.get("DEMO_STATE_PATH", str(workspace_root() / "demo" / "demo_state.json"))
        )
        self.asset_dir = Path(
            os.environ.get("DEMO_ASSET_DIR", str(workspace_root() / "demo" / "testdata"))
        )
        self.face_mapping_path = Path(
            os.environ.get(
                "DEMO_FACE_MAPPING_PATH",
                str(workspace_root() / "artifacts" / "solidworks-mcp-20260615-demo-mate" / "face_mappings.json"),
            )
        )
        self.mcp_mode = os.environ.get("DEMO_MCP_MODE", "dry-run")
        self.llm_mode = os.environ.get("DEMO_LLM_MODE", "dry-run")
        self.mcp_command = os.environ.get("DEMO_MCP_COMMAND")
        self.mcp_args = os.environ.get("DEMO_MCP_ARGS", "")
        self.mcp_cwd = os.environ.get("DEMO_MCP_CWD")
        self.mcp_pipe_name = os.environ.get("DEMO_MCP_PIPE_NAME", "SolidWorksMcpHub")
        self.mcp_timeout_seconds = float(os.environ.get("DEMO_MCP_TIMEOUT_SECONDS", "180"))

    @property
    def resolved_state_path(self) -> Path:
        return self.state_path if self.state_path.is_absolute() else workspace_root() / self.state_path

    @property
    def resolved_asset_dir(self) -> Path:
        return self.asset_dir if self.asset_dir.is_absolute() else workspace_root() / self.asset_dir

    @property
    def resolved_face_mapping_path(self) -> Path:
        return self.face_mapping_path if self.face_mapping_path.is_absolute() else workspace_root() / self.face_mapping_path

    @property
    def resolved_mcp_cwd(self) -> Path | None:
        if not self.mcp_cwd:
            return None
        path = Path(self.mcp_cwd)
        return path if path.is_absolute() else workspace_root() / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
