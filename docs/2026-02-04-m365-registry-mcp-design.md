# M365 Registry MCP Design

**Date:** Feb 4, 2026

## Overview

A dedicated MCP server that owns the M365 connection registry (`~/.m365-connections.json`). Other MCPs read from the registry file but only this MCP writes to it.

## Problem

- Multiple MCPs (exo-mcp, pwsh-manager, pp-admin-mcp, pnp-m365) need connection info
- No unified way to add/remove connections
- Manual JSON editing is error-prone
- PnP multi-tenant app was retired Sept 2024 - custom apps are now required

## Solution

A `m365-registry` MCP with tools to manage connections.

## Tools

### `registry_add_connection`

Add a new connection to the registry.

**Required parameters:**
- `name` (string) - Connection identifier (e.g., "Contoso-GA", "ClientX")
- `tenant` (string) - Tenant domain (e.g., "contoso.com", "clientx.onmicrosoft.com")
- `appId` (string) - Azure AD app registration ID (REQUIRED - no default)
- `description` (string) - REQUIRED explanation of what this app/account is for
- `mcps` (array) - Which MCP servers can use this connection

**Behavior:**
- Validates all fields are present
- Checks appId format (GUID)
- Refuses to create without appId - provides `m365 setup` instructions instead
- Writes to `~/.m365-connections.json`

### `registry_remove_connection`

Remove a connection by name.

**Parameters:**
- `name` (string) - Connection name to remove

**Behavior:**
- Removes from registry
- Does NOT revoke tokens or delete the Azure AD app

### `registry_update_connection`

Update an existing connection.

**Parameters:**
- `name` (string) - Connection name to update
- `appId` (string, optional) - New app ID
- `tenant` (string, optional) - New tenant
- `description` (string, optional) - New description
- `mcps` (array, optional) - New MCP list

### `registry_list_connections`

List all connections or filter by MCP.

**Parameters:**
- `mcp` (string, optional) - Filter to connections available to this MCP

### `registry_setup_instructions`

Show instructions for creating a new Azure AD app registration.

**Parameters:**
- `tenant` (string, optional) - Tenant to show instructions for

**Output:**
- CLI for Microsoft 365 install command
- `m365 setup` instructions
- What to do with the resulting app ID

## Registry Schema

```json
{
  "_schema": "Universal M365 connection registry - shared across MCPs",
  "_rules": [
    "connectionName is ALWAYS required - NO DEFAULTS EVER",
    "Each connection = tenant + appId + description + mcps array",
    "mcps array controls which MCP servers can use this connection",
    "description is REQUIRED - must explain what this app/account combination is for"
  ],
  "connections": {
    "ConnectionName": {
      "appId": "guid-here",
      "tenant": "domain.onmicrosoft.com",
      "description": "What this connection is used for",
      "mcps": ["pnp-m365", "exo", "pwsh-manager"]
    }
  }
}
```

## Implementation

### Location

`mm/` (within this repository)

### Stack

- Python + MCP SDK (consistent with other MCPs)
- Single file: `server.py`
- No external dependencies beyond mcp sdk

### File Locking

Use `fcntl.flock()` for safe concurrent writes.

## Changes to Existing MCPs

Existing MCPs continue to read `~/.m365-connections.json` directly. No code changes required.

The registry MCP is the single source of truth for writes.

## Testing

1. Add a test connection
2. Verify it appears in registry file
3. Verify other MCPs can read it
4. Remove the test connection
5. Verify it's gone
