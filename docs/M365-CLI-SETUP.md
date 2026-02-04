# CLI for Microsoft 365 Setup

**Last Updated:** Feb 4, 2026

## Why This Matters

**The PnP Management Shell multi-tenant app was deleted on September 9, 2024.** The old app ID `31359c7f-bd7e-475c-86db-fdb8c937548e` no longer works.

**You must create a custom Entra ID app registration for each tenant.** There is no usable default/multi-tenant app anymore. The CLI for M365 has a "default" but it's useless for real work - always create your own.

## Quick Start - CLI for Microsoft 365

### Install

```bash
npm install -g @pnp/cli-microsoft365
```

### Create Your App Registration (REQUIRED)

```bash
m365 setup
```

This interactively:
- Creates an Entra ID app registration in your tenant
- Configures required permissions
- Sets up device code or browser authentication
- Stores the app ID for future use
- **Requires Global Admin or Application Administrator role**

After setup, note the **App ID** - you'll need it for the connection registry.

### Login

```bash
# Using the app created by m365 setup
m365 login --appId YOUR_APP_ID --tenant yourtenant.onmicrosoft.com
```

### Verify

```bash
m365 status
```

## Custom App Registration

If you need specific permissions or want full control:

### Option 1: Via m365 CLI

```bash
m365 entra app add --name "My Custom App" --withSecret --apisApplication "https://graph.microsoft.com/User.Read.All,https://graph.microsoft.com/Mail.ReadWrite"
```

### Option 2: Via PnP PowerShell

```powershell
Register-PnPAzureADApp `
  -ApplicationName "My-MSP-App" `
  -Tenant customer.onmicrosoft.com `
  -Store CurrentUser `
  -GraphApplicationPermissions "User.Read.All", "Mail.ReadWrite" `
  -SharePointApplicationPermissions "Sites.FullControl.All"
```

### Option 3: Via Azure CLI

```bash
az ad app create --display-name "My App" --sign-in-audience AzureADMyOrg
```

## Connection Registry Integration

After creating an app, add it to `~/.m365-connections.json`:

```json
{
  "connections": {
    "MyConnection": {
      "appId": "your-app-id-here",
      "tenant": "yourtenant.onmicrosoft.com",
      "description": "What this connection is used for - REQUIRED",
      "mcps": ["pnp-m365", "exo", "pwsh-manager"]
    }
  }
}
```

## Known App IDs

| Connection | App ID | Tenant | Purpose |
|------------|--------|--------|---------|
| ForIT | `9bc3ab49-b65d-410a-85ad-de819febfddc` | forit.io | M365 admin |
| Personal | `f8031f56-8e99-4ba2-afff-4ff858c7a6c8` | bthomas.io | Personal account |
| Pivot | `255ef919-f1c8-4f43-bd4f-cfced065f41e` | airgeorgian.onmicrosoft.com | SharePoint/Power Automate |
| ForIT PnP CLI | `068893e1-8223-4281-ad8b-8a370eec3086` | forit.io | Created by m365 setup |

## Troubleshooting

### Error: AADSTS700016

```
Application with identifier '31359c7f-bd7e-475c-86db-fdb8c937548e' was not found
```

This means you're trying to use the old PnP Management Shell app. It was deleted Sept 9, 2024. Run `m365 setup` to create a new app.

### Error: Consent Required

Admin consent is needed. Either:
- Have a Global Admin run `m365 login` first
- Or grant consent in Azure Portal > App Registrations > API Permissions

## References

- [PnP Management Shell Changes (Aug 2024)](https://pnp.github.io/blog/post/changes-pnp-management-shell-registration/)
- [CLI for Microsoft 365 Docs](https://pnp.github.io/cli-microsoft365/)
- [Register Entra ID App for PnP](https://o365reports.com/register-an-entra-id-application-to-use-with-pnp-powershell/)
