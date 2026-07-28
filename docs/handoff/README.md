# Bidirectional runtime handoff

The runtime authority is fail-closed. Before the first production use on the
currently authoritative machine, initialize it explicitly:

```bash
ASTRA_MACHINE_ID=windows-wsl ./handoff activate --initialize
```

Configure Tailscale SSH destinations in the shell profile, not Git:

```bash
export HANDOFF_MAC_HOST="user@mac-tailscale-name"
export HANDOFF_WINDOWS_HOST="user@windows-tailscale-name"
```

Use `./handoff switch-to-mac` on WSL, and `./handoff switch-to-windows` on the
Mac. Each command freezes the source, exports the complete runtime, transfers
the mode-0600 archive with SCP, verifies and activates the target, and never
starts a sender. `./handoff status` reports local authority and blockers.

Windows PowerShell operators can use:

```powershell
.\handoff.ps1 switch-to-mac
.\handoff.ps1 status
```

The PowerShell wrapper invokes the WSL repository through `wsl.exe`.

If export succeeds but transfer/import fails, do not reactivate the source.
Both sides remain unable to send. Correct the failure and retry import with the
same bundle only if target activation never succeeded. Use `rollback` only to
restore target data for inspection; rollback deliberately remains unauthorized.
