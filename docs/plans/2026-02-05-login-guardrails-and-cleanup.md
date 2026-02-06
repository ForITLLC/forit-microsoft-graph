# Login Guardrails & Process Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent wrong-account logins and zombie processes across PNP and MM MCPs by adding pre-login reminders, post-login email verification, and proper subprocess cleanup.

**Architecture:** Add `expectedEmail` field to connection registry. Both PNP and MM show expected account before device code, verify authenticated email after login. PNP gets subprocess lifecycle management (track, timeout, kill). Session pool returns authenticated identity from health check output.

**Tech Stack:** TypeScript (PNP), Python (MM, Session Pool), JSON (connection registry)

---

### Task 1: Add expectedEmail to Connection Registry

**Files:**
- Modify: `~/.m365-connections.json`

**Step 1: Update the connection registry with expectedEmail for each connection**

Add `expectedEmail` field to each connection. These values come from:
- ForIT-GA: `GA_B.Thomas@foritllc.onmicrosoft.com` (from `m365 status`)
- ForIT-Personal: (user to provide - likely `B.Thomas@forit.io`)
- Pivot: (user to provide)
- GreatNorth-GA: (user to provide)
- GreatNorth-Personal: (user to provide)
- WMA: `g178@wmaviationorg.onmicrosoft.com` (from CLI connections file)

Example structure:
```json
{
  "connections": {
    "ForIT-GA": {
      "appId": "068893e1-...",
      "tenant": "forit.io",
      "description": "Global Admin tenant operations",
      "expectedEmail": "GA_B.Thomas@foritllc.onmicrosoft.com",
      "mcps": ["pnp-m365", "microsoft-graph", "exo", "pwsh-manager"]
    }
  }
}
```

**Step 2: Commit**

```bash
# No code commit needed - registry is user config, not in repo
```

---

### Task 2: PNP - Pre-Login Account Reminder

**Files:**
- Modify: `pnp/src/util.ts:19-25` (ConnectionEntry interface)
- Modify: `pnp/src/util.ts:237-253` (device code display in loginWithDeviceCode)

**Step 1: Add expectedEmail to ConnectionEntry interface**

```typescript
interface ConnectionEntry {
    appId: string | null;
    tenant: string;
    description: string;
    mcps: string[];
    cliConnectionName: string | null;
    expectedEmail: string | null;  // ADD THIS
}
```

**Step 2: Add expectedEmail to device code display**

In `loginWithDeviceCode()`, update the device code box (lines 237-253) to prominently show the expected account:

```typescript
resolve(`
████████████████████████████████████████████████████████████
██                                                        ██
██   DEVICE CODE: ${deviceCode.padEnd(12)}                       ██
██                                                        ██
██   Go to: https://microsoft.com/devicelogin            ██
██                                                        ██
████████████████████████████████████████████████████████████

⚠️  SIGN IN AS: ${entry.expectedEmail || `(any @${entry.tenant} account)`}

Connection: ${connectionName}
Tenant: ${entry.tenant}
App ID: ${entry.appId}
Description: ${entry.description}

Complete auth in browser. The CLI will store the token automatically.
Run m365_list_connections to verify after authenticating.
`);
```

**Step 3: Build and verify**

Run: `cd pnp && npx tsc`
Expected: Clean compile

**Step 4: Commit**

```bash
git add pnp/src/util.ts
git commit -m "feat(pnp): add pre-login account reminder in device code display"
```

---

### Task 3: PNP - Subprocess Lifecycle Management (Kill Zombies)

**Files:**
- Modify: `pnp/src/util.ts:209-261` (loginWithDeviceCode subprocess handling)

**Step 1: Track and manage the spawned subprocess**

Replace the fire-and-forget `spawn()` with proper lifecycle management:

```typescript
// At module level, add a map to track active login processes
const activeLoginProcesses = new Map<string, ReturnType<typeof spawn>>();

// In loginWithDeviceCode(), after spawning:
// Kill any existing login process for this connection
const existing = activeLoginProcesses.get(connectionName);
if (existing) {
    existing.kill();
    activeLoginProcesses.delete(connectionName);
}

const subprocess = spawn(loginCmd, {
    shell: true,
    stdio: ['pipe', 'pipe', 'pipe']
});

activeLoginProcesses.set(connectionName, subprocess);

// Clean up on exit (success or failure)
subprocess.on('exit', (code) => {
    activeLoginProcesses.delete(connectionName);
});

// Kill after 15 minutes (device codes expire in 15 min)
const killTimer = setTimeout(() => {
    if (!subprocess.killed) {
        subprocess.kill();
        activeLoginProcesses.delete(connectionName);
    }
}, 15 * 60 * 1000);

// Don't let the timer prevent Node from exiting
killTimer.unref();

subprocess.on('exit', () => {
    clearTimeout(killTimer);
});
```

**Step 2: Build and verify**

Run: `cd pnp && npx tsc`
Expected: Clean compile

**Step 3: Commit**

```bash
git add pnp/src/util.ts
git commit -m "fix(pnp): kill login subprocess after timeout, prevent zombies"
```

---

### Task 4: PNP - Post-Login Email Verification

**Files:**
- Modify: `pnp/src/util.ts:265-341` (runCliCommand - add first-command verification)
- Modify: `pnp/src/util.ts:96-125` (listConnections - add mismatch warnings)

**Step 1: Add email mismatch check to listConnections**

In `listConnections()`, add a warning field when connectedAs doesn't match expectedEmail:

```typescript
const results = entries.map(([name, entry]) => {
    const cliConn = findCliConnection(entry, cliConnections);
    const connectedAs = cliConn?.identityName || null;
    const emailMismatch = entry.expectedEmail && connectedAs &&
        connectedAs.toLowerCase() !== entry.expectedEmail.toLowerCase();
    return {
        name,
        tenant: entry.tenant,
        appId: entry.appId,
        description: entry.description,
        loggedIn: !!cliConn,
        connectedAs,
        expectedEmail: entry.expectedEmail || null,
        warning: emailMismatch ? `⚠️ WRONG ACCOUNT: expected ${entry.expectedEmail}, got ${connectedAs}` : null,
        cliConnectionName: cliConn?.name || null,
        needsSetup: !entry.appId ? 'Missing appId - needs app consent in tenant' : null
    };
});
```

**Step 2: Add email mismatch warning to runCliCommand**

In `runCliCommand()`, after finding the CLI connection (line 310-317), add verification:

```typescript
const cliConn = findCliConnection(entry, cliConnections);

if (!cliConn) {
    return JSON.stringify({
        error: `Connection "${connectionName}" not logged in`,
        hint: `Run m365_login with connectionName="${connectionName}"`
    }, null, 2);
}

// Verify correct account
if (entry.expectedEmail && cliConn.identityName &&
    cliConn.identityName.toLowerCase() !== entry.expectedEmail.toLowerCase()) {
    return JSON.stringify({
        error: `Wrong account logged in for "${connectionName}"`,
        expected: entry.expectedEmail,
        actual: cliConn.identityName,
        hint: `Logout and re-login with the correct account. Run m365_login with connectionName="${connectionName}"`
    }, null, 2);
}
```

**Step 3: Build and verify**

Run: `cd pnp && npx tsc`
Expected: Clean compile

**Step 4: Commit**

```bash
git add pnp/src/util.ts
git commit -m "feat(pnp): verify authenticated email matches expected account"
```

---

### Task 5: MM - Pre-Login Account Reminder

**Files:**
- Modify: `microsoft-master/server.py:226-231` (auth_required response)

**Step 1: Load expectedEmail from registry and include in device code display**

When status is `auth_required`, look up the connection's expectedEmail and show it:

```python
if status == "auth_required":
    device_code = result.get("device_code", "")
    # Load expected email from registry
    registry = load_registry()
    conn_config = registry.get("connections", {}).get(connection, {})
    expected_email = conn_config.get("expectedEmail", "")
    sign_in_hint = f"\n⚠️  SIGN IN AS: {expected_email}" if expected_email else f"\n⚠️  Sign in with your @{conn_config.get('tenant', '')} account"
    return [TextContent(
        type="text",
        text=f"**DEVICE CODE: {device_code}**\nGo to: https://microsoft.com/devicelogin\n{sign_in_hint}\n\nConnection: {connection}\nModule: {module}\n\nAfter authenticating, retry the command."
    )]
```

**Step 2: Commit**

```bash
git add microsoft-master/server.py
git commit -m "feat(mm): add pre-login account reminder with expectedEmail"
```

---

### Task 6: Session Pool - Return Authenticated Identity After Auth

**Files:**
- Modify: `m365-session-pool/session_pool.py:382-419` (check_auth_complete - capture identity)
- Modify: `m365-session-pool/session_pool.py:143-160` (Session dataclass - add authenticated_as field)
- Modify: `m365-session-pool/session_pool.py:434-475` (run_command - include identity in response)

**Step 1: Add authenticated_as field to Session dataclass**

```python
@dataclass
class Session:
    tenant: str
    module: str
    connection_name: str
    app_id: str = ""
    process: Optional[subprocess.Popen] = None
    process_lock: threading.Lock = field(default_factory=threading.Lock)
    state: str = "initializing"
    device_code: Optional[str] = None
    auth_initiated_by: Optional[str] = None
    last_command: Optional[datetime] = None
    last_error: Optional[str] = None
    authenticated_as: Optional[str] = None  # ADD THIS
```

**Step 2: Extract identity from health check output in check_auth_complete**

After the health check succeeds (line 409-413), parse the JSON output to extract the identity:

```python
if re.search(module_config["health_pattern"], health_output):
    self.state = "authenticated"
    self.device_code = None
    self.auth_initiated_by = None

    # Extract authenticated identity from health output
    try:
        health_data = json.loads(health_output.strip())
        if self.module == "exo":
            self.authenticated_as = health_data.get("UserPrincipalName") or health_data.get("Organization")
        elif self.module == "azure":
            account = health_data.get("Account", {})
            self.authenticated_as = account.get("Id") if isinstance(account, dict) else str(account)
        elif self.module == "teams":
            self.authenticated_as = health_data.get("DisplayName")
        elif self.module == "pnp":
            self.authenticated_as = health_data.get("Url")
    except (json.JSONDecodeError, AttributeError):
        pass  # Health output may not be clean JSON

    logger.info(f"[{self.session_id}] Auth completed! Identity: {self.authenticated_as}")
    return True
```

**Step 3: Include authenticated_as in run_command success response on first command after auth**

In `run_command()`, after the auth check passes at line 441-442, add identity info:

```python
if self.state == "auth_pending":
    if self.auth_initiated_by == caller_id:
        if self.check_auth_complete():
            pass  # Continue to execute - authenticated_as now set
```

And in the success response (line 469):
```python
response = {"status": "success", "output": output}
if self.authenticated_as:
    response["authenticated_as"] = self.authenticated_as
return response
```

**Step 4: Commit**

```bash
git add m365-session-pool/session_pool.py
git commit -m "feat(session-pool): extract and return authenticated identity from health check"
```

---

### Task 7: MM - Post-Login Email Verification

**Files:**
- Modify: `microsoft-master/server.py:239-244` (success response handling)

**Step 1: Check authenticated_as against expectedEmail on success**

After the session pool returns success, verify the identity:

```python
if status == "success":
    output = result.get("output", "")
    output = re.sub(r'\x1b\[[0-9;]*m', '', output)
    output = re.sub(r'\x1b\[\?[0-9]+[hl]', '', output)

    # Check for email mismatch
    authenticated_as = result.get("authenticated_as")
    if authenticated_as:
        registry = load_registry()
        conn_config = registry.get("connections", {}).get(connection, {})
        expected_email = conn_config.get("expectedEmail", "")
        if expected_email and expected_email.lower() != authenticated_as.lower():
            warning = f"\n\n⚠️ WARNING: Wrong account! Expected {expected_email}, got {authenticated_as}"
            output = warning + "\n\n" + output

    return [TextContent(type="text", text=output.strip() if output.strip() else "(no output)")]
```

**Step 2: Commit**

```bash
git add microsoft-master/server.py
git commit -m "feat(mm): verify authenticated identity matches expectedEmail"
```

---

### Task 8: Update Connection Registry with Known Emails

**Files:**
- Modify: `~/.m365-connections.json`

**Step 1: Populate expectedEmail for known connections**

Set expectedEmail for connections where we know the value:
- ForIT-GA: `GA_B.Thomas@foritllc.onmicrosoft.com`
- WMA: `g178@wmaviationorg.onmicrosoft.com`

**Step 2: Ask user for remaining connection emails**

Prompt user for:
- ForIT-Personal
- Pivot
- GreatNorth-GA
- GreatNorth-Personal

---

### Task 9: Build, Test, and Final Commit

**Step 1: Build PNP**

Run: `cd pnp && npx tsc`
Expected: Clean compile

**Step 2: Verify PNP login shows expected account**

Run: `m365_login` with connectionName `ForIT-GA`
Expected: Device code box shows `SIGN IN AS: GA_B.Thomas@foritllc.onmicrosoft.com`

**Step 3: Verify PNP list shows mismatch warnings**

Run: `m365_list_connections`
Expected: Each connection shows `expectedEmail` field, mismatch shows warning

**Step 4: Verify zombie cleanup**

After login, check: `ps aux | grep m365 | grep login`
Expected: Process exists but has timeout, will be killed after 15 minutes

**Step 5: Final commit with all changes**

```bash
git add -A
git commit -m "feat: login guardrails - pre-login reminders, post-login verification, zombie cleanup"
```
