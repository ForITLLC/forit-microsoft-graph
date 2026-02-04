# M365 MCP Suite

Unified Microsoft 365 MCP (Model Context Protocol) servers for AI assistants.

## Components

| MCP | Purpose | Type |
|-----|---------|------|
| **registry** | Central connection management | Python |
| **graph** | Microsoft Graph API (mail, calendar, OneDrive) | TypeScript |
| **pnp** | CLI for Microsoft 365 (SharePoint, Teams, Planner) | TypeScript |
| **pwsh-manager** | PowerShell sessions (EXO, Azure, Teams, Power Platform) | Python/Docker |

All MCPs share a common connection registry at `~/.m365-connections.json`.

## Quick Start

### 1. Install dependencies

```bash
# Graph MCP
cd graph && npm install && npm run build

# PnP MCP
cd pnp && npm install && npm run build

# Registry MCP
cd registry && python3 -m venv .venv && .venv/bin/pip install "mcp[cli]"

# pwsh-manager (Docker)
cd pwsh-manager && docker-compose up -d
```

### 2. Register with MCPJungle

```bash
mcpjungle register --conf graph/mcpjungle-config.json
mcpjungle register --conf pnp/mcpjungle-config.json
mcpjungle register --conf registry/mcpjungle-config.json
mcpjungle register --conf pwsh-manager/mcpjungle-config.json
```

### 3. Add a connection

Use the registry MCP or edit `~/.m365-connections.json`:

```json
{
  "connections": {
    "MyTenant": {
      "appId": "your-azure-ad-app-id",
      "tenant": "mytenant.onmicrosoft.com",
      "description": "What this connection is for",
      "mcps": ["graph", "pnp", "pwsh-manager"]
    }
  }
}
```

## App Registration

**The PnP multi-tenant app was retired September 9, 2024.** You must create your own Azure AD app registration.

See [docs/M365-CLI-SETUP.md](docs/M365-CLI-SETUP.md) for instructions.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AI Assistant                          │
└─────────────────────┬───────────────────────────────────┘
                      │ MCP Protocol
    ┌─────────────────┼─────────────────┐
    │                 │                 │
    ▼                 ▼                 ▼
┌─────────┐    ┌───────────┐    ┌─────────────┐
│  graph  │    │    pnp    │    │ pwsh-manager│
│ (REST)  │    │   (CLI)   │    │ (PowerShell)│
└────┬────┘    └─────┬─────┘    └──────┬──────┘
     │               │                 │
     └───────────────┼─────────────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │ ~/.m365-connections │
          │       .json         │
          └─────────────────────┘
                     ▲
                     │
              ┌──────┴──────┐
              │  registry   │
              │    MCP      │
              └─────────────┘
```

## License

MIT
