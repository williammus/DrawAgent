from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class MCPStdIOClient:
    def __init__(
        self,
        *,
        command: str,
        args: list[str],
        cwd: Path,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.command = command
        self.args = args
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds
        self._process: subprocess.Popen | None = None
        self._request_id = 0

    def __enter__(self) -> "MCPStdIOClient":
        self._process = subprocess.Popen(
            [self.command, *self.args],
            cwd=str(self.cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def _write_message(self, payload: dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP process is not running.")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self._process.stdin.write(header)
        self._process.stdin.write(body)
        self._process.stdin.flush()

    def _read_message(self) -> dict[str, Any]:
        if not self._process or not self._process.stdout:
            raise RuntimeError("MCP process is not running.")
        headers: dict[str, str] = {}
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise RuntimeError("MCP process closed the stdout stream unexpectedly.")
            if line in {b"\r\n", b"\n"}:
                break
            name, value = line.decode("utf-8").split(":", 1)
            headers[name.strip().lower()] = value.strip()
        content_length = int(headers.get("content-length", "0"))
        if content_length <= 0:
            raise RuntimeError("Invalid MCP message content length.")
        body = self._process.stdout.read(content_length)
        return json.loads(body.decode("utf-8"))

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        self._write_message(request)
        response = self._read_message()
        if response.get("error"):
            raise RuntimeError(f"MCP error from {method}: {response['error']}")
        return response.get("result") or {}

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        self._write_message(payload)

    def initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "drawagent-v2", "version": "0.1.0"},
            },
        )
        self._notify("notifications/initialized", {})

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list", {})
        return list(result.get("tools") or [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
        if isinstance(result.get("structuredContent"), dict):
            return result["structuredContent"]
        content = result.get("content") or []
        if content and isinstance(content[0], dict) and content[0].get("text"):
            return json.loads(str(content[0]["text"]))
        raise RuntimeError("MCP tool call did not return structured content.")

