from __future__ import annotations

import json
import urllib.request
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000/api/demo/state"
SOURCE_DIR = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目02\01-项目3D图纸\FL9A24D062A000.001"
)
SOURCE_ASSEMBLY = SOURCE_DIR / "FL9A24D062A000.001.SLDASM"

COMPONENT_FILES = [
    ("FL9A24D062A500.001-1", "FL9A24D062A500.001.SLDASM"),
    ("FL9A24D062A100.001-1", "FL9A24D062A100.001.SLDASM"),
    ("FL9A24D062A180.001-1", "FL9A24D062A180.001.SLDASM"),
    ("T401AA-07388-0-1", "T401AA-07388-0.SLDPRT"),
    ("FL9A24D062A200.001-1", "FL9A24D062A200.001.SLDASM"),
    ("FL9A24D062A800.001-1", "FL9A24D062A800.001.SLDASM"),
    ("FL9A24D062A700.001-1", "FL9A24D062A700.001.SLDASM"),
    ("FL9A24D062A300.001-1", "FL9A24D062A300.001.SLDASM"),
]


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def component_id(component_name: str) -> str:
    return component_name.lower().replace(".", "-")


def main() -> None:
    state = request_json(API)
    state["assemblyPath"] = str(SOURCE_ASSEMBLY)
    state["commonBaseReady"] = False
    state["components"] = [
        {
            "id": component_id(name),
            "displayName": name,
            "componentName": name,
            "filePath": str(SOURCE_DIR / file_name),
            "bottomFaceName": "底面",
            "current": {"x": 0.0, "y": 0.0, "z": 0.0},
            "target": {"x": 0.0, "y": 0.0, "z": 0.0},
        }
        for name, file_name in COMPONENT_FILES
    ]
    state["lastRun"] = {
        "status": "ok",
        "message": "Synced the eight real CAD components; A180=scanner and A700=cleaning+weighing composite.",
    }
    updated = request_json(API, "PUT", state)
    print(
        json.dumps(
            {
                "assemblyPath": updated.get("assemblyPath"),
                "componentCount": len(updated.get("components") or []),
                "components": [item["componentName"] for item in updated.get("components") or []],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
