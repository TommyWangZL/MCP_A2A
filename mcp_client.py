"""MCP HTTP client for initialize + tools/call with SSE/JSON handling."""

from __future__ import annotations

from typing import Any, Dict, Optional
import uuid
import json

import httpx

from config import MCP_URL

MCP_BASE_URL = MCP_URL
MCP_SESSION_ID: Optional[str] = None  # set on first initialize


async def mcp_init_session() -> str:
    """Initialize MCP session via `initialize`.

    Uses protocolVersion, capabilities, and clientInfo fields per MCP spec.
    Expects the FastMCP server to return a `Mcp-Session-Id` header.
    """
    global MCP_SESSION_ID

    initialize_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "python-client",
                "version": "0.1",
            },
        },
    }

    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(MCP_BASE_URL, headers=headers, json=initialize_payload)
        resp.raise_for_status()

        session_id = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
        if not session_id:
            raise RuntimeError("MCP initialize did not return a session ID in the headers.")

        MCP_SESSION_ID = session_id
        print(f"✅ MCP session initialized: {session_id}")
        return session_id


def _parse_mcp_sse_response(text: str) -> Dict[str, Any]:
    """Parse an SSE (text/event-stream) MCP response.

    We look for lines starting with 'data:' that contain JSON, and return the
    `result` field from the last JSON-RPC response object.
    """
    last_result: Optional[Dict[str, Any]] = None

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue

        data_str = line[len("data:") :].strip()
        if not data_str:
            continue

        try:
            obj = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        if isinstance(obj, dict) and "result" in obj:
            last_result = obj["result"]

    if last_result is None:
        raise ValueError(
            "Could not find a JSON-RPC result in SSE response. "
            f"First 200 chars:\n{text[:200]}"
        )

    return last_result


async def mcp_call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call an MCP tool using the `tools/call` method over HTTP.

    Handles:
    - Session initialization
    - Re-initialization if the server reports an invalid session
    - Both JSON (`application/json`) and SSE (`text/event-stream`) responses
    """
    global MCP_SESSION_ID

    if MCP_SESSION_ID is None:
        await mcp_init_session()

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "Mcp-Session-Id": MCP_SESSION_ID or "",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(MCP_BASE_URL, headers=headers, json=payload)

        if resp.status_code == 400 and "No valid session ID" in resp.text:
            print("⚠️ MCP session invalid, reinitializing...")
            await mcp_init_session()
            headers["Mcp-Session-Id"] = MCP_SESSION_ID or ""
            resp = await client.post(MCP_BASE_URL, headers=headers, json=payload)

        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        if content_type.startswith("text/event-stream"):
            return _parse_mcp_sse_response(resp.text)

        try:
            data = resp.json()
        except Exception as e:  # pragma: no cover - debug path
            raise RuntimeError(
                f"Failed to parse MCP JSON response: {e}\n"
                f"Raw body (first 200 chars): {resp.text[:200]}"
            ) from e

        return data.get("result", {})
