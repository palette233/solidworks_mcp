from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from create_global_cad_base_wrapper import (  # noqa: E402
    normalized_document_path,
    restore_open_document_baseline,
)


class FakeClient:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = list(documents)
        self.closed: list[str] = []

    def call_tool(self, name: str, arguments: dict):
        assert name == "ListDocuments"
        assert arguments == {}
        return list(self.documents)

    def call_tool_text(self, name: str, arguments: dict) -> str:
        assert name == "CloseDocument"
        path = arguments["path"]
        self.closed.append(path)
        self.documents = [row for row in self.documents if row["Path"] != path]
        return f"Closed: {path}"


def test_restore_open_document_baseline_closes_only_documents_opened_by_wrapper() -> None:
    baseline = r"D:\user\already-open.SLDASM"
    source = r"D:\project\source.SLDASM"
    leaf = r"D:\project\leaf.SLDPRT"
    client = FakeClient(
        [
            {"Path": baseline, "Type": 2},
            {"Path": leaf, "Type": 1},
            {"Path": source, "Type": 2},
        ]
    )

    result = restore_open_document_baseline(
        client,
        {normalized_document_path(baseline)},
    )

    assert result["sessionRestored"] is True
    assert result["errors"] == []
    assert client.closed == [source, leaf]
    assert client.documents == [{"Path": baseline, "Type": 2}]


def test_restore_open_document_baseline_is_noop_for_clean_session() -> None:
    client = FakeClient([])

    result = restore_open_document_baseline(client, set())

    assert result == {"closedPaths": [], "errors": [], "sessionRestored": True}
    assert client.closed == []
