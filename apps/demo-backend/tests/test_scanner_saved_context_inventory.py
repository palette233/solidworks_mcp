from __future__ import annotations

import json
from pathlib import Path

from demo_backend.scanner_saved_context_inventory import (
    build_scanner_saved_context_inventory,
)


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _catalog(path: Path) -> Path:
    return _write(
        path,
        {
            "moduleDefinitions": [
                {
                    "projectAliases": [
                        {"projectId": "project01", "moduleToken": "S"}
                    ],
                    "cadSources": [{"path": "C:/cad/scanner.sldasm"}],
                },
                {
                    "projectAliases": [
                        {"projectId": "project01", "moduleToken": "T"}
                    ],
                    "cadSources": [{"path": "C:/cad/transport.sldasm"}],
                },
                {
                    "projectAliases": [
                        {"projectId": "project02", "moduleToken": "B"}
                    ],
                    "cadSources": [{"path": "C:/cad/base.sldasm"}],
                },
            ]
        },
    )


def _queue(path: Path) -> Path:
    return _write(
        path,
        {
            "schemaVersion": "scanner-transport-binding-review-queue/v1",
            "candidates": [
                {
                    "sourceModuleDefinitionId": "project01::S",
                    "transportModuleDefinitionId": "project01::T",
                    "targetBaseDefinitionId": "project02::B",
                    "status": "ready_for_exact_chain_instance_selection",
                }
            ],
        },
    )


def _state(path: Path, *, include_transport: bool = True) -> Path:
    components = [
        {
            "name": "scanner-1",
            "sourcePath": "C:/cad/scanner.sldasm",
            "isFixed": False,
            "transform": [1] * 16,
        },
        {
            "name": "base-1",
            "sourcePath": "C:/cad/base.sldasm",
            "isFixed": True,
            "transform": [1] * 16,
        },
    ]
    if include_transport:
        components.append(
            {
                "name": "transport-1",
                "sourcePath": "C:/cad/transport.sldasm",
                "isFixed": False,
                "transform": [1] * 16,
            }
        )
    return _write(
        path,
        {
            "schemaVersion": "test-state/v1",
            "success": True,
            "assemblyPath": "C:/out/test.sldasm",
            "assemblySha256": "a" * 64,
            "observed": {"components": components},
        },
    )


def test_inventory_finds_one_exact_unique_triple(tmp_path: Path):
    queue = _queue(tmp_path / "queue.json")
    catalog = _catalog(tmp_path / "catalog.json")
    state = _state(tmp_path / "read-only-chain-verification.json")

    result = build_scanner_saved_context_inventory(
        workspace_root=tmp_path,
        review_queue_path=queue,
        module_catalog_path=catalog,
        state_paths=[state],
    )

    assert result["summary"]["exactSavedContextAvailableCount"] == 1
    assert result["summary"]["newCumulativeChainContextRequiredCount"] == 0
    row = result["candidates"][0]
    assert row["status"] == "exact_saved_context_available"
    assert row["savedContexts"][0]["scannerInstance"]["instanceId"] == "scanner-1"
    assert row["savedContexts"][0]["targetBaseInstance"]["isFixed"] is True


def test_inventory_requires_complete_triple(tmp_path: Path):
    result = build_scanner_saved_context_inventory(
        workspace_root=tmp_path,
        review_queue_path=_queue(tmp_path / "queue.json"),
        module_catalog_path=_catalog(tmp_path / "catalog.json"),
        state_paths=[
            _state(
                tmp_path / "read-only-chain-verification.json",
                include_transport=False,
            )
        ],
    )

    assert result["summary"]["exactSavedContextAvailableCount"] == 0
    assert result["summary"]["newCumulativeChainContextRequiredCount"] == 1
    assert (
        result["candidates"][0]["status"]
        == "new_cumulative_chain_context_required"
    )


def test_inventory_rejects_ambiguous_instances(tmp_path: Path):
    state = _state(tmp_path / "read-only-chain-verification.json")
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["observed"]["components"].append(
        {
            "name": "scanner-2",
            "sourcePath": "C:/cad/scanner.sldasm",
            "isFixed": False,
            "transform": [1] * 16,
        }
    )
    state.write_text(json.dumps(payload), encoding="utf-8")

    result = build_scanner_saved_context_inventory(
        workspace_root=tmp_path,
        review_queue_path=_queue(tmp_path / "queue.json"),
        module_catalog_path=_catalog(tmp_path / "catalog.json"),
        state_paths=[state],
    )
    assert result["summary"]["exactSavedContextAvailableCount"] == 0
