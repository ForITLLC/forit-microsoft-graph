#!/usr/bin/env python3
"""
mm MCP - Unified Microsoft 365 management.

Wraps the M365 Session Pool API for MSP multi-tenant operations.
Also manages the shared connection registry (~/.m365-connections.json).
"""

import fcntl
import json
import os
import re
import sys
import time
from pathlib import Path
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Shared logger
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from mcp_logger import log_tool_call
except ImportError:
    def log_tool_call(*args, **kwargs): pass

# Session pool endpoint
SESSION_POOL_URL = os.getenv("MM_SESSION_POOL_URL", "http://localhost:5200")

# Connection registry
CONNECTIONS_FILE = Path.home() / ".m365-connections.json"
VALID_MCPS = ["pnp-m365", "microsoft-graph", "mm", "exo", "onenote"]


def load_registry() -> dict:
    try:
        return json.loads(CONNECTIONS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"connections": {}}


def save_registry(data: dict) -> bool:
    try:
        with open(CONNECTIONS_FILE, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
                f.write('\n')
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return True
    except Exception:
        return False


def is_valid_guid(s: str) -> bool:
    return bool(re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', s))

server = Server("mm")


def call_pool(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Call the session pool API."""
    url = f"{SESSION_POOL_URL}{endpoint}"
    try:
        if method == "GET":
            resp = httpx.get(url, timeout=120)
        else:
            resp = httpx.post(url, json=data, timeout=120)
        return resp.json()
    except httpx.TimeoutException:
        return {"status": "error", "error": "Request timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="run",
            description="Execute a PowerShell command. Omit all params to list connections. Provide connection+module+command to execute.",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection": {
                        "type": "string",
                        "description": "Connection name (e.g., 'ForIT-GA')",
                    },
                    "module": {
                        "type": "string",
                        "description": "exo=Exchange, pnp=SharePoint, azure, teams",
                        "enum": ["exo", "pnp", "azure", "teams"],
                    },
                    "command": {
                        "type": "string",
                        "description": "PowerShell command",
                    },
                },
            },
        ),
        Tool(
            name="connection_add",
            description="Add a new M365 connection. Requires appId from an Azure AD app registration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Connection name (e.g., 'ClientX')"},
                    "tenant": {"type": "string", "description": "Tenant domain (e.g., 'clientx.onmicrosoft.com')"},
                    "appId": {"type": "string", "description": "Azure AD app registration ID (GUID)"},
                    "description": {"type": "string", "description": "What this connection is for"},
                    "mcps": {"type": "array", "items": {"type": "string"}, "description": f"Which MCPs can use this. Valid: {VALID_MCPS}"},
                },
                "required": ["name", "tenant", "appId", "description", "mcps"],
            },
        ),
        Tool(
            name="connection_remove",
            description="Remove a connection by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Connection name to remove"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="connection_update",
            description="Update an existing connection's properties.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Connection name to update"},
                    "appId": {"type": "string", "description": "New app ID"},
                    "tenant": {"type": "string", "description": "New tenant"},
                    "description": {"type": "string", "description": "New description"},
                    "mcps": {"type": "array", "items": {"type": "string"}, "description": "New MCP list"},
                },
                "required": ["name"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    start_time = time.time()
    error_msg = None
    result_summary = None
    connection_name = arguments.get("connection") or arguments.get("name")

    try:
        result = _call_tool_impl(name, arguments)
        if result and len(result) > 0:
            text = result[0].text[:100] if hasattr(result[0], 'text') else str(result[0])[:100]
            if "error" in text.lower():
                error_msg = text
            else:
                result_summary = text
        return result
    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            mcp_name="mm",
            tool_name=name,
            arguments=arguments,
            connection_name=connection_name,
            result=result_summary,
            error=error_msg,
            duration_ms=duration_ms,
        )


def _call_tool_impl(name: str, arguments: dict):
    # Registry tools
    if name == "connection_add":
        return _connection_add(arguments)
    if name == "connection_remove":
        return _connection_remove(arguments)
    if name == "connection_update":
        return _connection_update(arguments)
    if name != "run":
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    connection = arguments.get("connection")
    module = arguments.get("module")
    command = arguments.get("command")

    # No params = list connections
    if not connection and not module and not command:
        result = call_pool("/connections")
        connections = result.get("connections", {})
        metrics = call_pool("/metrics")

        output = "**Available Connections:**\n"
        for conn_name, config in connections.items():
            output += f"- {conn_name}: {config.get('tenant', 'unknown')} ({config.get('description', '')})\n"

        output += f"\n**Session Pool Status:**\n"
        output += f"- Uptime: {metrics.get('uptime_human', 'unknown')}\n"
        output += f"- Requests: {metrics.get('total_requests', 0)} ({metrics.get('error_rate', 0)}% errors)\n"
        output += f"- Active sessions: {metrics.get('active_sessions', 0)}\n"
        output += f"- Avg response: {metrics.get('avg_response_ms', 0)}ms\n"

        return [TextContent(type="text", text=output)]

    # Validate required params
    if not all([connection, module, command]):
        return [TextContent(type="text", text="Error: connection, module, and command are all required")]

    # Execute command
    result = call_pool("/run", "POST", {
        "connection": connection,
        "module": module,
        "command": command,
        "caller_id": "mm-mcp",
    })

    status = result.get("status")

    if status == "auth_required":
        device_code = result.get("device_code", "")
        # Look up expected email for pre-login reminder
        registry = load_registry()
        conn_config = registry.get("connections", {}).get(connection, {})
        expected_email = conn_config.get("expectedEmail", "")
        if expected_email:
            sign_in_hint = f"\n>>> SIGN IN AS: {expected_email} <<<"
        else:
            tenant = conn_config.get("tenant", "")
            sign_in_hint = f"\n>>> Sign in with your @{tenant} account <<<" if tenant else ""
        return [TextContent(
            type="text",
            text=f"**DEVICE CODE: {device_code}**\nGo to: https://microsoft.com/devicelogin\n{sign_in_hint}\n\nConnection: {connection}\nModule: {module}\n\nAfter authenticating, retry the command."
        )]

    if status == "auth_in_progress":
        return [TextContent(type="text", text="Auth in progress by another caller. Retry in a few seconds.")]

    if status == "error":
        return [TextContent(type="text", text=f"Error: {result.get('error', 'Unknown error')}")]

    if status == "success":
        output = result.get("output", "")
        # Strip ANSI codes for cleaner output
        output = re.sub(r'\x1b\[[0-9;]*m', '', output)
        output = re.sub(r'\x1b\[\?[0-9]+[hl]', '', output)

        # Check for email mismatch if session pool returned identity
        authenticated_as = result.get("authenticated_as")
        if authenticated_as:
            registry = load_registry()
            conn_config = registry.get("connections", {}).get(connection, {})
            expected_email = conn_config.get("expectedEmail", "")
            if expected_email and expected_email.lower() != authenticated_as.lower():
                warning = f"WARNING: Wrong account! Expected {expected_email}, got {authenticated_as}\n\n"
                output = warning + output

        return [TextContent(type="text", text=output.strip() if output.strip() else "(no output)")]

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _connection_add(args: dict):
    name = args.get("name", "").strip()
    tenant = args.get("tenant", "").strip()
    app_id = args.get("appId", "").strip()
    desc = args.get("description", "").strip()
    mcps = args.get("mcps", [])

    missing = [f for f in ["name", "tenant", "appId", "description", "mcps"] if not args.get(f)]
    if missing:
        return [TextContent(type="text", text=json.dumps({"error": f"Missing: {', '.join(missing)}"}, indent=2))]
    if not is_valid_guid(app_id):
        return [TextContent(type="text", text=json.dumps({"error": f"Invalid appId format: {app_id}"}, indent=2))]

    registry = load_registry()
    if name in registry.get("connections", {}):
        return [TextContent(type="text", text=json.dumps({"error": f"'{name}' already exists. Use connection_update."}, indent=2))]

    registry.setdefault("connections", {})[name] = {"appId": app_id, "tenant": tenant, "description": desc, "mcps": mcps}
    if save_registry(registry):
        return [TextContent(type="text", text=json.dumps({"success": True, "message": f"Connection '{name}' added"}, indent=2))]
    return [TextContent(type="text", text=json.dumps({"error": "Failed to save"}, indent=2))]


def _connection_remove(args: dict):
    name = args.get("name", "").strip()
    if not name:
        return [TextContent(type="text", text=json.dumps({"error": "name is required"}, indent=2))]

    registry = load_registry()
    if name not in registry.get("connections", {}):
        return [TextContent(type="text", text=json.dumps({"error": f"'{name}' not found", "available": list(registry.get("connections", {}).keys())}, indent=2))]

    removed = registry["connections"].pop(name)
    if save_registry(registry):
        return [TextContent(type="text", text=json.dumps({"success": True, "message": f"'{name}' removed", "removed": removed}, indent=2))]
    return [TextContent(type="text", text=json.dumps({"error": "Failed to save"}, indent=2))]


def _connection_update(args: dict):
    name = args.get("name", "").strip()
    if not name:
        return [TextContent(type="text", text=json.dumps({"error": "name is required"}, indent=2))]

    registry = load_registry()
    if name not in registry.get("connections", {}):
        return [TextContent(type="text", text=json.dumps({"error": f"'{name}' not found"}, indent=2))]

    conn = registry["connections"][name]
    updated = []
    for field in ["appId", "tenant", "description"]:
        if args.get(field):
            if field == "appId" and not is_valid_guid(args[field]):
                return [TextContent(type="text", text=json.dumps({"error": f"Invalid appId: {args[field]}"}, indent=2))]
            conn[field] = args[field].strip()
            updated.append(field)
    if args.get("mcps"):
        conn["mcps"] = args["mcps"]
        updated.append("mcps")

    if not updated:
        return [TextContent(type="text", text=json.dumps({"message": "No changes"}, indent=2))]

    if save_registry(registry):
        return [TextContent(type="text", text=json.dumps({"success": True, "updated": updated, "connection": conn}, indent=2))]
    return [TextContent(type="text", text=json.dumps({"error": "Failed to save"}, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
