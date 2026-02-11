# Microsoft Master (MM)

## Architecture
One MCP server — `mm` — for ALL Microsoft operations.
- **mm** - Microsoft Master (Exchange, SharePoint, Teams, Azure, Power Platform, Graph API)
- Two tools: `mm__run` (PowerShell) and `mm__graph_request` (Graph REST API)
- PowerShell backed by `session-pool/` — Docker containers with persistent sessions
- Graph backed by MSAL with per-connection token cache (`~/.mm-graph-tokens/`)
- Connection registry: `~/.m365-connections.json` (READ-ONLY to MCPs)

Old servers (pnp, graph, pwsh-manager, registry) are archived in `_archived/`.

## Connection Rules - NO DEFAULTS EVER
- Universal registry: `~/.m365-connections.json`
- Every command REQUIRES `connection` parameter
- NEVER use the word "default" in any MM code
- Connection = Account + AppId + Tenant + Description
- Naming convention: GA (admin), Individual (your user on work tenant), Personal (your own tenant)
- Manage with `./mm-connections` CLI (list, add, edit, rename, remove, duplicate)

## Authentication
- ALWAYS use MM MCP tools, NEVER Bash for M365 auth
- Both tools auto-trigger device codes when a connection isn't authenticated — no pre-auth step needed
- Display device codes as:
  ```
  **DEVICE CODE: XXXXXXXX**
  Go to: https://microsoft.com/devicelogin
  ```

## MM Tools

### `mm__run` — PowerShell via Session Pool
- No params → list connections
- `connection` + `module` + `command` → execute PowerShell
- Modules: `exo` (Exchange), `pnp` (SharePoint), `azure`, `teams`
- Command guardrails block dangerous operations (see below)

### `mm__graph_request` — Microsoft Graph REST API
- No params → list connections
- `connection` + `endpoint` → GET request to Graph
- `connection` + `endpoint` + `method` + `body` → any Graph operation
- Optional `resource`: `graph` (default) or `flow` (Power Automate)
- Supports `/v1.0/` and `/beta/` endpoints
- OData noise stripped automatically
- Token cache: `~/.mm-graph-tokens/` (per connection, MSAL)

## Request Hooks (mm/server.py)
Both tools have internal hook systems that fire before/after requests:

### `GRAPH_HOOKS` — Graph API request hooks
- `(match_fn, handler_fn)` pairs, all matching hooks fire in order
- Handler: `(endpoint, method, body, conn_config) -> (body, note)`
- Can modify body (e.g. strip email signatures) and/or return notes (e.g. sendMail reminder)
- Notes get prepended to the response as `**Note:** ...`

### `RUN_HOOKS` — PowerShell command hooks
- `(match_fn, handler_fn)` pairs, all matching hooks fire in order
- Handler: `(command, module, conn_config) -> (command, note)`
- Can modify commands, return notes, or block execution (return `None` as command)
- Example: catches cmdlets from uninstalled Az modules and redirects to `Invoke-AzRestMethod`

### Installed Az Modules
Only `Az.Accounts` is installed in the container. All other Az cmdlets should use
`Invoke-AzRestMethod` to call the Azure REST API directly.

## Session Pool

### Deployment Modes
Both modes use the same `session_pool.py` — only `SINGLE_CONNECTION` env var differs.

| Mode | File | Use Case |
|------|------|----------|
| **Unified** | `docker-compose.unified.yml` | Dev, single container, all connections |
| **Isolated** | `docker-compose.isolated.yml` | Production, one container per connection |

### Command Guardrails
The session pool blocks dangerous operations before execution:

**Blocked** (hard reject):
- `Install-Module`, `Uninstall-Module`, `Update-Module` — container integrity
- `New-AzRoleAssignment`, `Remove-AzRoleAssignment` — access escalation
- `Set-AzKeyVaultAccessPolicy`, `Remove-AzKeyVaultAccessPolicy` — vault security
- `New-AzADApplication`, `New-AzADServicePrincipal` — app registration
- Raw OAuth requests to `login.microsoftonline` — auth bypass

**Warned** (logged but allowed):
- `Remove-Az*` — Azure resource deletion
- `Remove-Mailbox`, `Remove-PnP*`, `Remove-Team` — destructive operations
- `ForwardingSmtpAddress`, `Set-InboxRule` with Forward — mail forwarding

### Session Persistence
- Authenticated session metadata saved to `~/.m365-state/` on every auth completion
- On container restart, sessions restore automatically:
  - **Azure**: Tokens cached in `~/.Azure` Docker volume — restores without device code
  - **EXO/Teams**: In-process only — requires re-auth on next use (by design)
  - **PnP**: Token cache in `~/.config` Docker volume — may restore depending on token expiry

### Azure Context Isolation (Unified Mode)
In unified mode, all Azure sessions share `~/.Azure`. To prevent cross-tenant contamination:
- `Disable-AzContextAutosave -Scope Process` prevents writes to shared cache
- `Select-AzContext` by `expectedEmail` from connection config picks the correct tenant

### Logging
Dual output: stdout (`docker logs`) + persistent files (`~/.m365-logs/`).
- Every command's output content logged (first 500 chars preview)
- AADSTS and auth error patterns flagged at WARNING level
- `mm/server.py` also scans "successful" responses for buried auth errors

### Host Directories
| Path | Purpose |
|------|---------|
| `~/.m365-connections.json` | Connection registry (read-only) |
| `~/.m365-logs/` | Persistent log files |
| `~/.m365-state/` | Session state for restart persistence |
| `~/.mm-graph-tokens/` | MSAL token cache for Graph API |

## Testing
```bash
# Check all containers healthy
docker ps --format "{{.Names}}\t{{.Status}}" | grep m365

# Test PowerShell
mcpjungle invoke mm run '{"connection":"<YOUR_CONNECTION>","module":"exo","command":"Get-Mailbox -ResultSize 1"}'

# Test Graph API
mcpjungle invoke mm graph_request '{"connection":"<YOUR_CONNECTION>","endpoint":"/me"}'

# Session status
curl http://localhost:5200/status | jq

# Metrics
curl http://localhost:5200/metrics | jq

# Persistent logs
tail -f ~/.m365-logs/session-pool-unified.log
```

## MCPJungle Registration
```bash
# Copy and edit the example config with your local paths
cp mm/mcpjungle-config.example.json mm/mcpjungle-config.json
# Then register
mcpjungle register --conf mm/mcpjungle-config.json
```
