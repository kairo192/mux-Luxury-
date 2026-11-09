# POS / Desktop CMS update strategy

The Windows Desktop CMS is a Tauri 2 application that each boutique installs
on its own hardware. Its update path is separate from the server release
path on purpose: a cloud API deploy must never silently break running POS
installations.

## Three pillars

1. **Signed releases.** Every v* tag produces a `.msi` / `.exe` installer
   signed with the Tauri updater key. The POS binary ships the matching
   public key baked in; `tauri-plugin-updater` refuses any update signed
   by any other key.
2. **Version-compatibility probe.** On startup the POS calls
   `GET /api/v1/pos/compat?client_version=1.2.3`. The server returns the
   min supported version and the latest available version; the POS either
   runs, warns the user ("a newer version is available"), or refuses to
   start ("your version is no longer supported — please update").
3. **Forward-compatible API.** API changes that break the POS protocol
   require bumping `POS_API_CONTRACT_VERSION` and raising
   `POS_MIN_SUPPORTED_VERSION` at the same time, in the same release.
   Additive changes (new optional fields) do neither.

## Release flow

```
developer                     GitHub                           operator
    │                           │                                 │
    │  git tag v1.3.0           │                                 │
    │  git push origin v1.3.0 ─▶│                                 │
    │                           │                                 │
    │                           ├─ cd-production.yml ────────────▶│
    │                           │   deploys server                 │ server
    │                           │                                 │ live at 1.3.0
    │                           │                                 │
    │                           ├─ build-desktop-cms.yml ────────▶│
    │                           │   builds signed .msi/.exe       │
    │                           │   uploads latest.json to the     │
    │                           │   v1.3.0 GitHub release          │
    │                           │                                 │
    ▼                           ▼                                 │
                                                                  │
POS installation                                                  │
    on next launch pulls                                          │
    https://github.com/kairo192/mux-Luxury-/releases/latest/download/latest.json
    verifies signature                                            │
    prompts user: "Update to 1.3.0? [Install later / Install now]"
```

## Breaking the contract

If the server release really needs an incompatible change:

1. In the same server release, raise `POS_MIN_SUPPORTED_VERSION` in
   `/opt/luxe/shared/.env`. Clients below the min version get
   `supported: false` and refuse to run.
2. Ship the matching POS release **before** the server release, give
   boutiques a week of lead time, and announce the cutoff in the POS
   itself (`deprecated: true`).
3. Deploy the server. POS installations below the cutoff see "please
   update" and the updater handles the rest.

`POS_MIN_SUPPORTED_VERSION` is a plain env var exactly so this knob can be
turned without redeploying code.

## Offline POS

When a boutique is offline, the POS keeps writing to its local SQLite WAL
and syncs when the network comes back via `POST /api/v1/admin/pos/sync`.
A POS that cannot reach the server for its version probe uses the last
known compat response (cached in Tauri's store), so offline operation
never breaks because of version checks.

## If the signing key is lost or leaked

Rotating the Tauri signing key invalidates every installed POS — the
updater refuses manifests signed by the new key. Plan:

1. Generate a new keypair: `npx tauri signer generate -w ~/.tauri/mux_luxury.key`.
2. Update `apps/desktop-cms/src-tauri/tauri.conf.json` `plugins.updater.pubkey`
   with the new public key, bump the Desktop CMS major version, tag.
3. Tell boutiques to download the new installer manually from the GitHub
   release (not from their old POS's updater).
4. Starting from this version, updates work normally again.

Store the signing key offline (password-protected on a USB stick plus a
printed paper backup of the base64 content). Never commit it.
