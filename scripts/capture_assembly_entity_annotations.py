#!/usr/bin/env python3
"""
Run SolidWorks assembly entity annotation capture outside an LLM/MCP client.

The script controls SolidWorksMcpApp through its stdio MCP proxy, first builds
a reusable target-index.json, then captures targets from that index in short
resumable batches. It continues from manifest.json if a call times out after
partial progress.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_INDEX_TOOL = "BuildActiveAssemblyEntityAnnotationTargetIndex"
INDEX_CAPTURE_TOOL = "CaptureActiveAssemblyEntityAnnotationTargetsFromIndex"
LEGACY_CAPTURE_TOOL = "CaptureActiveAssemblyEntityAnnotationSet"


class McpClient:
    def __init__(self, exe_path: Path, client_name: str, request_timeout: float, framing: str) -> None:
        self.exe_path = exe_path
        self.client_name = client_name
        self.request_timeout = request_timeout
        self.framing = framing
        self._next_id = 1
        self._proc: subprocess.Popen[bytes] | None = None
        self._messages: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._reader_thread: threading.Thread | None = None

    def __enter__(self) -> "McpClient":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def start(self) -> None:
        if self._proc is not None:
            return

        self._proc = subprocess.Popen(
            [
                str(self.exe_path),
                "--proxy",
                "--client",
                self.client_name,
            ],
            cwd=str(self.exe_path.parent),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._reader_thread = threading.Thread(target=self._reader_loop, name="mcp-reader", daemon=True)
        self._reader_thread.start()
        self.initialize()

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return

        try:
            if proc.stdin:
                proc.stdin.close()
        except OSError:
            pass

        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def initialize(self) -> None:
        response = self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": self.client_name, "version": "1.0.0"},
            },
        )
        if "result" not in response:
            raise RuntimeError(f"MCP initialize failed: {response}")
        self.notify("notifications/initialized", {})

    def call_tool_text(self, tool_name: str, arguments: dict[str, Any]) -> str:
        response = self.request(
            "tools/call",
            {
                "name": to_mcp_tool_name(tool_name),
                "arguments": arguments,
            },
        )
        if "error" in response:
            raise RuntimeError(json.dumps(response["error"], ensure_ascii=False))

        result = response.get("result") or {}
        if result.get("isError"):
            raise RuntimeError(extract_tool_text(result) or json.dumps(result, ensure_ascii=False))

        return extract_tool_text(result)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        text = self.call_tool_text(tool_name, arguments)
        if not text:
            return {}

        try:
            return loads_json(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Tool returned non-JSON text: {text}") from exc

    def list_tools(self) -> list[dict[str, Any]]:
        response = self.request("tools/list", {})
        if "error" in response:
            raise RuntimeError(json.dumps(response["error"], ensure_ascii=False))
        return list((response.get("result") or {}).get("tools") or [])

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        message_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": message_id, "method": method, "params": params})

        deadline = time.monotonic() + self.request_timeout
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError(f"MCP request timed out after {self.request_timeout:.0f}s: {method}")

            message = self._read_message(deadline)
            if message.get("id") == message_id:
                return message

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _send(self, message: dict[str, Any]) -> None:
        proc = self._require_proc()
        if proc.stdin is None:
            raise RuntimeError("MCP proxy stdin is closed.")

        raw_json = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if self.framing == "content-length":
            payload = f"Content-Length: {len(raw_json)}\r\n\r\n".encode("ascii") + raw_json
        else:
            payload = raw_json + b"\n"
        proc.stdin.write(payload)
        proc.stdin.flush()

    def _read_message(self, deadline: float) -> dict[str, Any]:
        timeout = max(0.01, deadline - time.monotonic())
        try:
            message = self._messages.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("Timed out while reading MCP response.") from exc

        if isinstance(message, BaseException):
            raise message
        return message

    def _reader_loop(self) -> None:
        try:
            proc = self._require_proc()
            stdout = proc.stdout
            if stdout is None:
                raise RuntimeError("MCP proxy stdout is closed.")

            while True:
                line = stdout.readline()
                if not line:
                    raise RuntimeError(read_process_failure(proc))

                if line.lower().startswith(b"content-length:"):
                    self._messages.put(read_content_length_message(stdout, line))
                    continue

                if not line.strip():
                    continue

                self._messages.put(loads_json(line))
        except BaseException as exc:
            self._messages.put(exc)

    def _require_proc(self) -> subprocess.Popen[bytes]:
        if self._proc is None:
            raise RuntimeError("MCP proxy is not running.")
        if self._proc.poll() is not None:
            raise RuntimeError(read_process_failure(self._proc))
        return self._proc


def extract_tool_text(result: dict[str, Any]) -> str:
    blocks = result.get("content") or []
    texts = [
        block.get("text", "")
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
    ]
    return "\n".join(texts)


def read_content_length_message(stdout: Any, first_header_line: bytes) -> dict[str, Any]:
    headers: dict[str, str] = {}
    current = first_header_line
    while True:
        if current in (b"\r\n", b"\n", b""):
            break
        key, _, value = current.decode("ascii", errors="replace").partition(":")
        headers[key.strip().lower()] = value.strip()
        current = stdout.readline()

    length_text = headers.get("content-length")
    if not length_text:
        raise RuntimeError(f"MCP response did not include Content-Length: {headers}")

    length = int(length_text)
    body = stdout.read(length)
    if len(body) != length:
        raise RuntimeError("MCP stream ended before a full Content-Length body was read.")
    return loads_json(body)


def loads_json(value: str | bytes) -> Any:
    if isinstance(value, bytes):
        return json.loads(value.decode("utf-8-sig"))
    return json.loads(value.lstrip("\ufeff"))


def read_process_failure(proc: subprocess.Popen[bytes]) -> str:
    stderr = b""
    try:
        if proc.stderr:
            stderr = proc.stderr.read() or b""
    except Exception:
        pass
    detail = stderr.decode("utf-8", errors="replace").strip()
    code = proc.poll()
    return f"MCP proxy exited or closed the stream. exit_code={code}, stderr={detail}"


def to_mcp_tool_name(name: str) -> str:
    if "_" in name:
        return name.lower()

    result: list[str] = []
    for index, current in enumerate(name):
        if current.isupper():
            has_previous = index > 0
            previous = name[index - 1] if has_previous else ""
            next_char = name[index + 1] if index + 1 < len(name) else ""
            if has_previous and (previous.islower() or previous.isdigit() or next_char.islower()):
                result.append("_")
            result.append(current.lower())
        else:
            result.append(current)
    return "".join(result)


def resolve_exe_path(configured: str | None) -> Path:
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"SolidWorksMcpApp.exe not found: {path}")
        return path

    env_path = os.environ.get("SOLIDWORKS_MCP_APP_EXE")
    if env_path:
        return resolve_exe_path(env_path)

    artifact_root = REPO_ROOT / "artifacts"
    candidates = list(artifact_root.glob("solidworks-mcp*/SolidWorksMcpApp.exe"))
    candidates.extend(
        [
            REPO_ROOT
            / "vendor"
            / "solidworks-mcp"
            / "app"
            / "SolidWorksMcpApp"
            / "bin"
            / "Release"
            / "net8.0-windows"
            / "win-x64"
            / "SolidWorksMcpApp.exe",
            REPO_ROOT
            / "vendor"
            / "solidworks-mcp"
            / "app"
            / "SolidWorksMcpApp"
            / "bin"
            / "Debug"
            / "net8.0-windows"
            / "win-x64"
            / "SolidWorksMcpApp.exe",
        ]
    )
    existing = [path for path in candidates if path.exists()]
    if not existing:
        raise FileNotFoundError(
            "Could not locate SolidWorksMcpApp.exe. Pass --exe or set SOLIDWORKS_MCP_APP_EXE."
        )
    return max(existing, key=lambda path: path.stat().st_mtime).resolve()


def load_manifest(output_directory: Path) -> dict[str, Any] | None:
    path = output_directory / "manifest.json"
    if not path.exists():
        return None
    return loads_json(path.read_text(encoding="utf-8-sig"))


def load_target_index(output_directory: Path) -> dict[str, Any] | None:
    path = output_directory / "target-index.json"
    if not path.exists():
        return None
    return loads_json(path.read_text(encoding="utf-8-sig"))


def count_existing_targets(output_directory: Path) -> int:
    manifest = load_manifest(output_directory)
    if not manifest:
        return 0
    targets = json_get(manifest, "targets", [])
    return len(targets)


def json_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in data:
        return data[key]
    pascal_key = key[:1].upper() + key[1:]
    if pascal_key in data:
        return data[pascal_key]
    return default


def json_int(data: dict[str, Any], key: str, default: int = 0) -> int:
    value = json_get(data, key, default)
    return default if value is None else int(value)


def close_client(client: McpClient | None) -> None:
    if client is not None:
        client.close()


def build_index_arguments(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "outputDirectory": str(args.output_dir),
        "includeComponents": args.include_components,
        "includeFeatures": args.include_features,
        "includeBodies": args.include_bodies,
        "requireFeatureTypeName": args.require_feature_type_name,
        "overwrite": args.rebuild_index,
    }


def build_capture_arguments(args: argparse.Namespace, start_index: int, batch_size: int) -> dict[str, Any]:
    common = {
        "outputDirectory": str(args.output_dir),
        "width": args.width,
        "height": args.height,
        "maxTargets": batch_size,
        "startIndex": start_index,
        "skipExistingTargets": True,
        "writeManifestAfterEachTarget": True,
        "maxDurationSeconds": args.tool_time_budget,
        "useCleanDisplayMode": args.clean_display,
        "capturePaddingFactor": args.padding,
    }
    if args.legacy_capture:
        common.update(
            {
                "includeComponents": args.include_components,
                "includeFeatures": args.include_features,
                "includeBodies": args.include_bodies,
                "requireFeatureTypeName": args.require_feature_type_name,
            }
        )
    else:
        common["sourceIndex"] = start_index
        common["maxTargets"] = 1
    return common


def ensure_target_index(client: McpClient, args: argparse.Namespace) -> dict[str, Any] | None:
    if args.legacy_capture:
        return None

    existing = None if args.rebuild_index else load_target_index(args.output_dir)
    if existing:
        print(
            "Using existing target index: "
            f"targetCount={json_int(existing, 'targetCount', 0)}, "
            f"path={json_get(existing, 'indexPath', str(args.output_dir / 'target-index.json'))}"
        )
        return existing

    print("Building target index without screenshots...")
    result = client.call_tool(BUILD_INDEX_TOOL, build_index_arguments(args))
    print(
        "Target index ready: "
        f"targetCount={json_int(result, 'targetCount', 0)}, "
        f"path={json_get(result, 'indexPath', str(args.output_dir / 'target-index.json'))}"
    )
    return result


def prepare_solidworks_session(client: McpClient, args: argparse.Namespace) -> None:
    if args.force_reconnect:
        try:
            client.call_tool_text("SolidWorksDisconnect", {})
        except Exception as exc:
            if args.verbose:
                print(f"Disconnect before reconnect ignored: {exc}")

    if args.connect:
        connect_result = client.call_tool("SolidWorksConnect", {})
        if args.verbose:
            print(f"Connect result: {json.dumps(connect_result, ensure_ascii=False)}")

    if args.document:
        open_result = client.call_tool("OpenDocument", {"path": str(args.document.resolve())})
        if args.verbose:
            print(f"OpenDocument result: {json.dumps(open_result, ensure_ascii=False)}")

    list_result = client.call_tool("ListDocuments", {})
    documents = list_result if isinstance(list_result, list) else []
    active_text = client.call_tool_text("GetActiveDocument", {})
    active_doc = parse_nullable_json(active_text)

    print(f"SolidWorks documents visible to MCP: {len(documents)}")
    if active_doc:
        print(
            "Active document visible to MCP: "
            f"{json_get(active_doc, 'title', '<untitled>')} | {json_get(active_doc, 'path', '')}"
        )
    else:
        print("Active document visible to MCP: <none>")

    if not active_doc:
        document_paths = [
            str(json_get(item, "path", ""))
            for item in documents
            if isinstance(item, dict) and json_get(item, "path")
        ]
        hint = (
            "MCP is connected to a SolidWorks session with no active document. "
            "Pass --document <full .SLDASM path>, or close/restart the MCP tray/Hub and SolidWorks so they run in the same user session."
        )
        if document_paths:
            hint += " Documents visible to MCP: " + "; ".join(document_paths)
        raise RuntimeError(hint)


def parse_nullable_json(text: str) -> Any:
    stripped = text.strip()
    if not stripped or stripped.lower() == "null":
        return None
    return loads_json(stripped)


def wait_for_manifest_progress(
    output_directory: Path,
    previous_count: int,
    previous_start_index: int,
    timeout_seconds: float,
) -> tuple[dict[str, Any] | None, int, int]:
    deadline = time.monotonic() + max(0, timeout_seconds)
    manifest = load_manifest(output_directory)
    current_count = len(json_get(manifest or {}, "targets", []))
    next_start_index = json_int(manifest or {}, "nextStartIndex", previous_start_index)

    while time.monotonic() < deadline:
        if current_count > previous_count or next_start_index > previous_start_index:
            return manifest, current_count, next_start_index
        time.sleep(0.25)
        manifest = load_manifest(output_directory)
        current_count = len(json_get(manifest or {}, "targets", []))
        next_start_index = json_int(manifest or {}, "nextStartIndex", previous_start_index)

    return manifest, current_count, next_start_index


def run_capture(args: argparse.Namespace) -> int:
    exe_path = resolve_exe_path(args.exe)
    args.output_dir = args.output_dir.resolve()

    start_index = args.start_index
    if not args.probe_only:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.resume and not args.probe_only:
        manifest = load_manifest(args.output_dir)
        if manifest:
            start_index = json_int(manifest, "nextStartIndex", start_index)

    print(f"Using MCP app: {exe_path}")
    print(f"Output directory: {args.output_dir}")
    print(f"Starting at target index: {start_index}")

    if args.probe_only:
        with McpClient(exe_path, "Python Entity Annotation Capture Probe", args.request_timeout, args.framing) as client:
            tools = client.list_tools()
            names = sorted(tool.get("name", "") for tool in tools)
            build_index_tool = to_mcp_tool_name(BUILD_INDEX_TOOL)
            index_capture_tool = to_mcp_tool_name(INDEX_CAPTURE_TOOL)
            legacy_capture_tool = to_mcp_tool_name(LEGACY_CAPTURE_TOOL)
            print(f"Connected. Tool count: {len(names)}")
            print(f"Build index tool available: {build_index_tool in names} ({build_index_tool})")
            print(f"Index capture tool available: {index_capture_tool in names} ({index_capture_tool})")
            print(f"Legacy capture tool available: {legacy_capture_tool in names} ({legacy_capture_tool})")
            if args.verbose:
                for name in names:
                    print(f"  {name}")
        return 0

    if args.document and not args.document.exists():
        raise FileNotFoundError(f"Document path does not exist: {args.document}")

    completed = False
    attempts = 0
    batches = 0
    last_target_count = count_existing_targets(args.output_dir)
    effective_batch_size = args.batch_size if args.legacy_capture else 1
    stuck_timeouts: dict[int, int] = {}
    client: McpClient | None = None
    indexed_target_count = 0
    index_prepared = False

    try:
        while not completed:
            if args.max_batches and batches >= args.max_batches:
                print(f"Reached --max-batches={args.max_batches}; stopping.")
                break

            batches += 1
            attempts += 1
            capture_args = build_capture_arguments(args, start_index, effective_batch_size)
            print(
                f"\nBatch {batches}: startIndex={start_index}, "
                f"batchSize={effective_batch_size}, toolBudget={args.tool_time_budget}s"
            )

            phase = "capture"
            try:
                if client is None:
                    client = McpClient(exe_path, "Python Entity Annotation Capture", args.request_timeout, args.framing)
                    client.start()
                    prepare_solidworks_session(client, args)
                    phase = "index"
                    if args.rebuild_index and index_prepared:
                        args.rebuild_index = False
                    index = ensure_target_index(client, args)
                    indexed_target_count = json_int(index or {}, "targetCount", indexed_target_count)
                    index_prepared = True

                phase = "capture"
                capture_tool = LEGACY_CAPTURE_TOOL if args.legacy_capture else INDEX_CAPTURE_TOOL
                result = client.call_tool(capture_tool, capture_args)
            except TimeoutError as exc:
                print(f"Timed out: {exc}")
                close_client(client)
                client = None
                if phase == "index":
                    if attempts > args.max_retries:
                        raise
                    print("Target index build timed out before capture started; retrying index build.")
                    time.sleep(args.retry_delay)
                    continue

                previous_start_index = start_index
                manifest, current_count, manifest_next_start = wait_for_manifest_progress(
                    args.output_dir,
                    last_target_count,
                    previous_start_index,
                    args.progress_wait_after_timeout,
                )
                if manifest:
                    start_index = manifest_next_start
                    print(
                        "Recovered progress from manifest: "
                        f"targets={current_count}, nextStartIndex={start_index}, "
                        f"stoppedReason={json_get(manifest, 'stoppedReason')}"
                    )
                elif attempts > args.max_retries:
                    raise

                if current_count <= last_target_count and manifest_next_start <= previous_start_index:
                    effective_batch_size = 1
                    stuck_timeouts[previous_start_index] = stuck_timeouts.get(previous_start_index, 0) + 1
                    if stuck_timeouts[previous_start_index] >= args.skip_stuck_target_after:
                        skipped_index = previous_start_index
                        start_index = previous_start_index + 1
                        attempts = 0
                        stuck_timeouts.pop(previous_start_index, None)
                        print(
                            "No manifest progress after repeated timeouts; "
                            f"skipping source index {skipped_index} and continuing at {start_index}."
                        )

                if current_count <= last_target_count and attempts > args.max_retries:
                    raise RuntimeError(
                        "Timed out repeatedly without manifest progress. "
                        "Reduce --batch-size or --tool-time-budget."
                    ) from exc

                last_target_count = current_count
                time.sleep(args.retry_delay)
                continue
            except Exception as exc:
                print(f"Batch failed: {exc}")
                close_client(client)
                client = None
                if attempts > args.max_retries:
                    raise
                if phase == "index":
                    print("Target index build failed before capture started; retrying index build.")
                time.sleep(args.retry_delay)
                continue

            attempts = 0
            target_count = json_int(result, "targetCount", last_target_count)
            processed_this_run = json_get(result, "processedThisRun")
            total_target_count = json_int(result, "totalTargetCount", indexed_target_count)
            start_index = json_int(result, "nextStartIndex", start_index)
            effective_batch_size = args.batch_size if args.legacy_capture else 1
            stuck_timeouts.pop(start_index, None)
            stopped_reason = json_get(result, "stoppedReason")
            last_target_count = target_count
            print(
                "Batch result: "
                f"targetCount={target_count}, "
                f"processedThisRun={processed_this_run}, "
                f"totalTargetCount={total_target_count}, "
                f"nextStartIndex={start_index}, "
                f"stoppedReason={stopped_reason}"
            )

            completed = stopped_reason == "completed"
            if not completed and start_index >= total_target_count > 0:
                completed = True
    finally:
        close_client(client)

    manifest_path = args.output_dir / "manifest.json"
    print(f"\nDone. Manifest: {manifest_path}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a SolidWorks assembly target index, then capture entity annotation images in resumable MCP calls."
    )
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for manifest.json and entity images.")
    parser.add_argument("--exe", help="Path to SolidWorksMcpApp.exe. Defaults to latest artifacts/solidworks-mcp* exe.")
    parser.add_argument("--document", type=Path, help="Optional full path to a .SLDASM/.SLDPRT document to open and activate before capture.")
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--batch-size", type=int, default=10, help="Targets per MCP call. Smaller values reduce timeout risk.")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--tool-time-budget", type=int, default=30, help="maxDurationSeconds passed to the MCP tool.")
    parser.add_argument("--request-timeout", type=float, default=90, help="Python-side timeout per MCP request.")
    parser.add_argument(
        "--framing",
        choices=["content-length", "newline"],
        default="newline",
        help="MCP stdio framing used by SolidWorksMcpApp proxy.",
    )
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-delay", type=float, default=0.5)
    parser.add_argument(
        "--progress-wait-after-timeout",
        type=float,
        default=2.0,
        help="Seconds to poll manifest.json after a timeout before retrying or skipping.",
    )
    parser.add_argument(
        "--skip-stuck-target-after",
        type=int,
        default=3,
        help="Skip a source index after this many no-progress timeouts at that same index.",
    )
    parser.add_argument("--max-batches", type=int, default=0, help="0 means unlimited.")
    parser.add_argument("--padding", type=float, default=1.35, help="capturePaddingFactor.")
    parser.add_argument("--clean-display", action="store_true", help="Use hidden-lines-removed clean display.")
    parser.add_argument("--connect", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force-reconnect", action="store_true", help="Disconnect the MCP COM session before connecting, useful when the Hub is attached to a stale SolidWorks instance.")
    parser.add_argument("--probe-only", action="store_true", help="Only initialize MCP and list tools; do not capture.")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild target-index.json before capture.")
    parser.add_argument(
        "--legacy-capture",
        action="store_true",
        help="Use the older CaptureActiveAssemblyEntityAnnotationSet tool instead of the two-stage target-index flow.",
    )
    parser.add_argument("--include-components", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-features", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-bodies", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--require-feature-type-name",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Only keep targets with a valid FeatureTypeName; filters ProfileFeature and OneBend.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    try:
        raise SystemExit(run_capture(parse_args(sys.argv[1:])))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
