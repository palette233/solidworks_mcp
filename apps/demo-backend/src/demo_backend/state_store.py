from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import DemoState, default_demo_state


class DemoStateStore:
    def __init__(self, state_path: Path, asset_dir: Path):
        self.state_path = state_path
        self.asset_dir = asset_dir

    def load(self) -> DemoState:
        if not self.state_path.exists():
            state = default_demo_state(self.asset_dir)
            self.save(state)
            return state

        raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        return DemoState.model_validate(raw)

    def save(self, state: DemoState) -> DemoState:
        state.updated_at = datetime.now(timezone.utc)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            state.model_dump_json(by_alias=True, indent=2),
            encoding="utf-8",
        )
        return state

    def reset(self) -> DemoState:
        return self.save(default_demo_state(self.asset_dir))
