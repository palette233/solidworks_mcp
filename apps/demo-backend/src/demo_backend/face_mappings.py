from __future__ import annotations

import json
from pathlib import Path

from .models import DemoComponent


class FaceMappingStore:
    def __init__(self, mapping_path: Path):
        self.mapping_path = mapping_path

    def load(self) -> dict:
        if not self.mapping_path.exists():
            return {}
        try:
            raw = self.mapping_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def has_face_mapping(self, component_name: str, face_name: str) -> bool:
        mappings = self.load()
        component_entry = mappings.get(component_name)
        return isinstance(component_entry, dict) and face_name in component_entry

    def missing_bottom_mappings(self, components: list[DemoComponent]) -> list[dict[str, str]]:
        mappings = self.load()
        missing: list[dict[str, str]] = []
        for component in components:
            component_entry = mappings.get(component.component_name)
            if not isinstance(component_entry, dict) or component.bottom_face_name not in component_entry:
                missing.append(
                    {
                        "id": component.id,
                        "componentName": component.component_name,
                        "faceName": component.bottom_face_name,
                        "message": (
                            f"\u8bf7\u5148\u4e3a\u7ec4\u4ef6 {component.component_name} "
                            f"\u8bb0\u5f55\u5e95\u9762\u6620\u5c04 {component.bottom_face_name}"
                        ),
                    }
                )
        return missing
