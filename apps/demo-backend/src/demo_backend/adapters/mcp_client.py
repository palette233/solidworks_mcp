from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from ..models import OperationResult, ToolCallPlan


class McpProtocolError(RuntimeError):
    pass


class McpClient:
    """Minimal MCP stdio client for the SolidWorks MCP proxy process."""

    def __init__(
        self,
        mode: str = "dry-run",
        command: str | None = None,
        args: str | list[str] | None = None,
        cwd: Path | str | None = None,
        pipe_name: str = "SolidWorksMcpHub",
        timeout_seconds: float = 180,
    ):
        self.mode = mode
        self.command = command
        self.args = self._normalize_args(args)
        self.cwd = str(cwd) if cwd else None
        self.pipe_name = pipe_name
        self.timeout_seconds = timeout_seconds

    async def run_plan(self, plan: list[ToolCallPlan]) -> OperationResult:
        if self.mode == "dry-run":
            return OperationResult(
                status="dry-run",
                message="MCP execution is not wired for this environment. Returned planned tool calls only.",
                plan=plan,
            )

        if self.mode not in {"stdio", "real", "pipe", "bridge"}:
            return OperationResult(
                status="error",
                message=f"Unsupported MCP mode: {self.mode}",
                plan=plan,
            )

        if self.mode == "pipe":
            try:
                tool_results = await asyncio.wait_for(
                    asyncio.to_thread(self._run_pipe_plan, plan),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                return OperationResult(
                    status="error",
                    message=f"MCP execution failed: {type(exc).__name__}: {exc}",
                    plan=plan,
                )

            return OperationResult(
                status="ok",
                message="MCP execution completed.",
                plan=plan,
                toolResults=tool_results,
            )

        if self.mode == "bridge":
            try:
                tool_results = await asyncio.wait_for(
                    asyncio.to_thread(self._run_bridge_plan, plan),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                return OperationResult(
                    status="error",
                    message=f"MCP execution failed: {type(exc).__name__}: {exc}",
                    plan=plan,
                )

            return OperationResult(
                status="ok",
                message="MCP execution completed.",
                plan=plan,
                toolResults=tool_results,
            )

        if not self.command:
            return OperationResult(
                status="error",
                message="DEMO_MCP_COMMAND is required when DEMO_MCP_MODE=stdio.",
                plan=plan,
            )

        try:
            tool_results = await asyncio.wait_for(self._run_stdio_plan(plan), timeout=self.timeout_seconds)
        except Exception as exc:
            return OperationResult(
                status="error",
                message=f"MCP execution failed: {type(exc).__name__}: {exc}",
                plan=plan,
            )

        return OperationResult(
            status="ok",
            message="MCP execution completed.",
            plan=plan,
            toolResults=tool_results,
        )

    def _run_bridge_plan(self, plan: list[ToolCallPlan]) -> list[dict[str, Any]]:
        command, args = self._bridge_command()
        payload = {
            "tools": [
                {
                    "tool": item.tool,
                    "arguments": item.arguments,
                }
                for item in plan
            ]
        }

        completed = subprocess.run(
            [command, *args],
            cwd=self.cwd,
            input=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout_seconds,
            check=False,
        )

        if completed.returncode != 0:
            raise McpProtocolError(completed.stderr.decode("utf-8", errors="replace").strip())

        data = json.loads(completed.stdout.decode("utf-8"))
        results: list[dict[str, Any]] = []
        for item, raw in zip(plan, data.get("results", [])):
            text = [
                block.get("text")
                for block in raw.get("content", [])
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            results.append(
                {
                    "tool": item.tool,
                    "arguments": item.arguments,
                    "raw": raw,
                    "text": [value for value in text if isinstance(value, str)],
                }
            )
        return results

    def _bridge_command(self) -> tuple[str, list[str]]:
        if self.command:
            return self.command, self.args

        workspace = Path(__file__).resolve().parents[5]
        runner = workspace / "apps" / "demo-backend" / "tools" / "McpToolRunner" / "bin" / "Release" / "net8.0" / "McpToolRunner.dll"
        return "dotnet", [str(runner)]

    def _run_pipe_plan(self, plan: list[ToolCallPlan]) -> list[dict[str, Any]]:
        pipe_path = rf"\\.\pipe\{self.pipe_name}"
        with open(pipe_path, "r+b", buffering=0) as pipe:
            handshake = json.dumps(
                {"type": "connect", "clientName": "DemoBackendArrange", "pid": os.getpid()},
                separators=(",", ":"),
            ).encode("utf-8") + b"\n"
            pipe.write(handshake)
            pipe.flush()
            ready = pipe.readline().decode("utf-8", errors="replace")
            if "\"ready\"" not in ready:
                raise McpProtocolError(f"Unexpected MCP Hub handshake response: {ready}")

            request_id = 1
            self._send_sync_request(
                pipe,
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "solidworks-demo-backend", "version": "0.1.0"},
                    },
                },
            )
            self._read_sync_response(pipe, request_id)

            self._send_sync_request(
                pipe,
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
            )

            results: list[dict[str, Any]] = []
            for item in plan:
                request_id += 1
                self._send_sync_request(
                    pipe,
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": "tools/call",
                        "params": {
                            "name": item.tool,
                            "arguments": item.arguments,
                        },
                    },
                )
                response = self._read_sync_response(pipe, request_id)
                result = response.get("result", {})
                results.append(
                    {
                        "tool": item.tool,
                        "arguments": item.arguments,
                        "raw": result,
                        "text": self._extract_text(result),
                    }
                )

            return results

    async def _run_stdio_plan(self, plan: list[ToolCallPlan]) -> list[dict[str, Any]]:
        process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            cwd=self.cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if process.stdin is None or process.stdout is None:
            raise McpProtocolError("Failed to open MCP process stdio pipes.")

        request_id = 1
        await self._send_request(
            process,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "solidworks-demo-backend", "version": "0.1.0"},
                },
            },
        )
        await self._read_response(process, request_id)

        await self._send_request(
            process,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )

        results: list[dict[str, Any]] = []
        for item in plan:
            request_id += 1
            await self._send_request(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": item.tool,
                        "arguments": item.arguments,
                    },
                },
            )
            response = await self._read_response(process, request_id)
            result = response.get("result", {})
            results.append(
                {
                    "tool": item.tool,
                    "arguments": item.arguments,
                    "raw": result,
                    "text": self._extract_text(result),
                }
            )

        process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

        return results

    @staticmethod
    def _normalize_args(args: str | list[str] | None) -> list[str]:
        if args is None:
            return []
        if isinstance(args, list):
            return args
        return shlex.split(args, posix=False)

    @staticmethod
    async def _send_request(process: asyncio.subprocess.Process, payload: dict[str, Any]) -> None:
        if process.stdin is None:
            raise McpProtocolError("MCP stdin is closed.")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        process.stdin.write(header + body)
        await process.stdin.drain()

    @staticmethod
    def _send_sync_request(pipe, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        pipe.write(header + body)
        pipe.flush()

    async def _read_response(self, process: asyncio.subprocess.Process, request_id: int) -> dict[str, Any]:
        while True:
            message = await self._read_message(process)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise McpProtocolError(f"MCP request {request_id} failed: {message['error']}")
            return message

    def _read_sync_response(self, pipe, request_id: int) -> dict[str, Any]:
        while True:
            message = self._read_sync_message(pipe)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise McpProtocolError(f"MCP request {request_id} failed: {message['error']}")
            return message

    async def _read_message(self, process: asyncio.subprocess.Process) -> dict[str, Any]:
        if process.stdout is None:
            raise McpProtocolError("MCP stdout is closed.")

        headers: dict[str, str] = {}
        while True:
            line = await process.stdout.readline()
            if not line:
                stderr = await self._read_stderr(process)
                raise McpProtocolError(f"MCP process exited before sending a response. stderr={stderr}")
            if line in {b"\r\n", b"\n"}:
                break
            key, _, value = line.decode("ascii").partition(":")
            headers[key.strip().lower()] = value.strip()

        length_text = headers.get("content-length")
        if not length_text:
            raise McpProtocolError("MCP response missing Content-Length header.")
        body = await process.stdout.readexactly(int(length_text))
        return json.loads(body.decode("utf-8"))

    @staticmethod
    def _read_sync_message(pipe) -> dict[str, Any]:
        headers: dict[str, str] = {}
        while True:
            line = pipe.readline()
            if not line:
                raise McpProtocolError("MCP pipe closed before sending a response.")
            if line in {b"\r\n", b"\n"}:
                break
            key, _, value = line.decode("ascii").partition(":")
            headers[key.strip().lower()] = value.strip()

        length_text = headers.get("content-length")
        if not length_text:
            raise McpProtocolError("MCP response missing Content-Length header.")
        body = pipe.read(int(length_text))
        if len(body) != int(length_text):
            raise McpProtocolError("MCP pipe closed during response body.")
        return json.loads(body.decode("utf-8"))

    @staticmethod
    async def _read_stderr(process: asyncio.subprocess.Process) -> str:
        if process.stderr is None:
            return ""
        try:
            data = await asyncio.wait_for(process.stderr.read(), timeout=1)
        except asyncio.TimeoutError:
            return ""
        return data.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _extract_text(result: dict[str, Any]) -> list[str]:
        content = result.get("content", [])
        if not isinstance(content, list):
            return []
        texts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return texts
