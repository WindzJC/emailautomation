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

## Emergency Mac provenance takeover

Use this only when WSL is inaccessible, the specified verified legacy bundle
has already been restored, and Mac has no runtime authority:

```bash
ASTRA_MACHINE_ID=mac ./handoff emergency-takeover \
  --bundle /Users/windellereboquio/AstraHandoff/_incoming/emailautomation_runtime_20260728T211005Z.tgz \
  --machine mac \
  --profile private_jc \
  --reason "WSL source machine inaccessible"
```

This command is deliberately pinned to the expected bundle SHA-256, source
commit, 2,574-recipient count, and queue fingerprint recorded for that incident.
It creates immutable checked/intended/reject provenance from the verified
bundled queue and replaces only the active campaign-source snapshot. It does
not initialize authority or start anything. A new matching private-JC preview
must still be generated and validated before normal authority initialization
can succeed.

If export succeeds but transfer/import fails, do not reactivate the source.
Both sides remain unable to send. Correct the failure and retry import with the
same bundle only if target activation never succeeded. Use `rollback` only to
restore target data for inspection; rollback deliberately remains unauthorized.
