"""Thin synchronous wrapper over the official MCP Python SDK (streamable HTTP).

Discovery records every tool's input schema and a stable hash of it, so a changed
schema can stop only the dependent adapter. `readOnlyHint` is recorded but never
treated as an access control - the local allowlist decides which tools may be called.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from director.adapters.base import Capability
from director.jobs.worker import PermanentError, RetryableError

log = logging.getLogger("director.mcp")


def schema_hash(schema: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(schema, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class MCPToolCall:
    name: str
    arguments: dict[str, Any]
    structured: Any = None
    text: str = ""
    is_error: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> Any:
        if self.structured is not None:
            return self.structured
        if self.text:
            try:
                return json.loads(self.text)
            except json.JSONDecodeError:
                return {"text": self.text}
        return None


class MCPClient:
    """Sync facade; each public method opens a session, does the work, closes it."""

    def __init__(
        self, url: str, token: str = "", *, allowlist: set[str] | None = None, timeout: float = 60.0
    ):
        if not url:
            raise PermanentError("MCP url not configured")
        self.url = url
        self.token = token
        self.allowlist = allowlist
        self.timeout = timeout

    # -- transport -----------------------------------------------------------------
    def _transport(self):
        from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else None
        http_client = create_mcp_http_client(headers=headers)
        return streamable_http_client(self.url, http_client=http_client)

    async def _list_tools_async(self) -> tuple[list[Capability], dict[str, Any]]:
        from mcp import Client

        caps: list[Capability] = []
        async with Client(self._transport(), read_timeout_seconds=self.timeout) as client:
            cursor: str | None = None
            seen_cursors: set[str] = set()
            while True:  # full pagination of tools/list
                result = await client.list_tools(cursor=cursor)
                for tool in result.tools:
                    ann = getattr(tool, "annotations", None)
                    caps.append(
                        Capability(
                            tool_name=tool.name,
                            description=tool.description or "",
                            input_schema=dict(tool.input_schema or {}),
                            read_only_hint=getattr(ann, "read_only_hint", None) if ann else None,
                        )
                    )
                cursor = getattr(result, "next_cursor", None)
                if not cursor or cursor in seen_cursors:
                    break
                seen_cursors.add(cursor)
            info = {
                "server_info": getattr(getattr(client, "server_info", None), "model_dump", lambda: None)(),
                "protocol_version": getattr(client, "protocol_version", None),
            }
        return caps, info

    async def _call_async(self, name: str, arguments: dict[str, Any]) -> MCPToolCall:
        from mcp import Client

        async with Client(self._transport(), read_timeout_seconds=self.timeout) as client:
            result = await client.call_tool(name, arguments)
        text_parts = [
            getattr(c, "text", "") for c in (result.content or []) if getattr(c, "type", "") == "text"
        ]
        return MCPToolCall(
            name=name,
            arguments=arguments,
            structured=getattr(result, "structured_content", None),
            text="\n".join(p for p in text_parts if p),
            is_error=bool(getattr(result, "is_error", False)),
            raw=result.model_dump(mode="json") if hasattr(result, "model_dump") else {},
        )

    # -- public --------------------------------------------------------------------
    def list_tools(self) -> tuple[list[Capability], dict[str, Any]]:
        try:
            return asyncio.run(self._list_tools_async())
        except PermanentError:
            raise
        except Exception as exc:  # network / protocol errors
            raise RetryableError(f"MCP tools/list failed: {exc}") from exc

    def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolCall:
        if self.allowlist is not None and name not in self.allowlist:
            raise PermanentError(f"MCP tool '{name}' is not in the local allowlist")
        try:
            return asyncio.run(self._call_async(name, arguments))
        except PermanentError:
            raise
        except Exception as exc:
            raise RetryableError(f"MCP tools/call {name} failed: {exc}") from exc


def filter_arguments(schema: dict[str, Any], candidates: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Keep only candidate arguments the tool's input schema declares. Never invent parameters."""
    props = (schema or {}).get("properties") or {}
    kept = {k: v for k, v in candidates.items() if k in props}
    required = [r for r in (schema or {}).get("required", []) if r not in kept]
    return kept, required
