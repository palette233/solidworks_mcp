"""Read only the native waste-cup support leaf, preserving existing documents."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from capture_assembly_entity_annotations import McpClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"
OUT = PACKAGE / "a600-slot-match-v1"


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    source = PACKAGE / "project02-A600-project05-P000-datum-v1.SLDASM"
    output = OUT / "a600-native-wastecup-support-faces.json"
    evidence = OUT / "native-support-scan-run.json"
    if output.exists() or evidence.exists():
        raise FileExistsError("Read existing evidence instead of overwriting a scan")
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"startedAtUtc": now(), "source": str(source), "readOnly": True,
              "phases": [],
              "sourceHashBefore": hashlib.sha256(source.read_bytes()).hexdigest()}
    started = time.perf_counter()
    exe = ROOT / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
    with McpClient(exe, "P000NativeSupportBoundedScan", 120, "newline", direct_stdio=True) as client:
        phase_started, phase_clock = now(), time.perf_counter()
        before = client.call_tool("ListDocuments", {})
        report["phases"].append({"name": "document_baseline", "startedAtUtc": phase_started,
                                "finishedAtUtc": now(), "durationSeconds": time.perf_counter()-phase_clock})
        baseline = {str(row.get("Path", "")).casefold() for row in before}
        report["baselineDocumentCount"] = len(before)
        report["preexistingAssemblyTitles"] = [row.get("Title") for row in before if row.get("Type") == 2]
        try:
            phase_started, phase_clock = now(), time.perf_counter()
            result = client.call_tool("BuildLeafFaceEndpointCatalog", {
                "sourceAssemblyPath": str(source), "moduleToken": "A600",
                "leafSelector": "FL9A24D062A610.001-1/FL5B24D062A600001.04-1/24D062-FL5B24D062A600001.01-12-1-1",
                "outputPath": str(output), "planarOnly": False,
                "minimumFaceArea": 1e-8, "maximumFaceCount": 500, "saveJson": True})
            report["success"] = output.is_file()
            report["endpointCount"] = result.get("EndpointCount")
        except Exception as exc:
            report["success"] = False
            report["error"] = str(exc)
        finally:
            report["phases"].append({"name": "native_leaf_scan", "startedAtUtc": phase_started,
                                    "finishedAtUtc": now(), "durationSeconds": time.perf_counter()-phase_clock})
            phase_started, phase_clock = now(), time.perf_counter()
            # Only this task's newly opened wrapper may be closed. In particular
            # never close/save the user's already modified GN00 assembly.
            if str(source).casefold() not in baseline and report.get("success"):
                try:
                    client.call_tool_text("CloseDocument", {"path": str(source)})
                    report["inspectionWrapperClosedWithoutSave"] = True
                except Exception as exc:
                    report["cleanupError"] = str(exc)
            report["finishedAtUtc"] = now()
            report["phases"].append({"name": "close_inspection_wrapper", "startedAtUtc": phase_started,
                                    "finishedAtUtc": now(), "durationSeconds": time.perf_counter()-phase_clock})
            report["durationSeconds"] = time.perf_counter() - started
            report["sourceHashAfter"] = hashlib.sha256(source.read_bytes()).hexdigest()
            evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
