# M365 MCP Suite

## Architecture
Six MCP servers sharing `~/.m365-connections.json` as the universal connection registry:
- **pnp** - CLI for Microsoft 365 (SharePoint, Teams, Planner)
- **graph** - Microsoft Graph REST API (mail, calendar, OneDrive)
- **pwsh-manager** - PowerShell sessions in Docker (EXO, Azure, Teams, Power Platform)
- **registry** - Connection management MCP
- **m365-session-pool** - Isolated Docker session containers per connection
- **mm-mcp** - Meeting minutes/transcription MCP

## Connection Rules - NO DEFAULTS EVER
- Universal registry: `~/.m365-connections.json`
- Every command REQUIRES `connectionName` parameter
- NEVER use the word "default" in any M365 MCP code
- Connection = Account + AppId + Tenant + Description + mcps array
- Connections: ForIT-GA, ForIT-Personal, Pivot, GreatNorth-GA, GreatNorth-Personal, WMA

## Authentication
- ALWAYS use MCP login tools, NEVER Bash for M365 auth
- `pnp-m365`: Use `pnp_login` tool (NOT `m365 login` via Bash)
- `pwsh-manager`: Use `pwsh_login` tool (NOT raw PowerShell)
- MCP tools format device codes prominently; Bash truncates them
- Display device codes as:
  ```
  **DEVICE CODE: XXXXXXXX**
  Go to: https://microsoft.com/devicelogin
  ```

## M365 Session Pool (Docker)
- Each connection gets an isolated Docker container
- Router on port 5200, individual containers on 5210-5215
- `docker-compose.yml` manages the full stack
- Health checks built in - containers report healthy when ready

## Token Storage
- M365_CLI_CONFIG_HOME controls where tokens are stored per connection
- Each connection gets its own config directory to prevent token collision
- Known issue: token storage path conflicts when multiple connections share a container

## PnP CLI Notes
- The PnP multi-tenant app was retired September 9, 2024
- Custom Azure AD app registrations required for each tenant
- See `docs/M365-CLI-SETUP.md` for app registration instructions

## Testing
```bash
# Check all containers healthy
docker ps --format "{{.Names}}\t{{.Status}}" | grep m365

# Test a specific connection
mcpjungle test pnp-m365 --tool m365_run_command --args '{"command":"m365 status","connectionName":"ForIT"}'
```

## MCPJungle Registration
```bash
mcpjungle register --conf graph/mcpjungle-config.json
mcpjungle register --conf pnp/mcpjungle-config.json
mcpjungle register --conf registry/mcpjungle-config.json
mcpjungle register --conf pwsh-manager/mcpjungle-config.json
mcpjungle register --conf m365-session-pool/mcpjungle-config.json
mcpjungle register --conf mm-mcp/mcpjungle-config.json
```
