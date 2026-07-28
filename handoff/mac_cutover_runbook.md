# WSL to Mac cutover runbook

This prepares a cutover; it does not authorize sending. GitHub `main` is the
code source. A single frozen WSL bundle is the runtime source. Never run workers
on both machines.

## Migration classification

| Class | Contents | Transfer |
| --- | --- | --- |
| REQUIRED_RUNTIME | Current recipient queues, authoritative send/domain logs, suppression/outcome databases and current dashboard/dispatch state | Frozen bundle |
| REQUIRED_LEAD_OPS | Current lead/check/triage/verify outputs and run-specific dispatch previews | Frozen bundle |
| CODE_GIT_ONLY | Python, JS, CSS, tests, templates, reference files and scripts | GitHub `main` |
| REGENERATED_MAC | `.venv`, caches, temporary files, lock files, SQLite WAL/SHM sidecars, runtime heartbeats | Recreate |
| OPTIONAL_ARCHIVE_NOT_INCLUDED | Old bundles, audits, backups, debug artifacts and historical temp runs | Keep offline if desired |
| REQUIRED_PRIVATE_TRANSFER | `.env` and local credential files | Direct encrypted SSH/SCP only |
| MUST_NOT_TRANSFER | Active locks, worker PIDs/sessions, plaintext secrets in a bundle, unrelated recipient exports | Never |

The bundler remaps repository-root strings in staged JSON copies from the WSL
root to the Mac root. It does not edit WSL runtime files. SQLite files are
captured with SQLite's backup API and checked before packaging.

## Freeze and package on WSL

Do not stop anything until the operator approves the final freeze window.
Before packaging, stop the dashboard/tunnel and all queue-writing jobs, then:

```bash
cd /home/jc/email-automation
git status --short
git fetch origin
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
pgrep -af 'send_shard.py --profile' || echo 'PASS: no sender processes'
pgrep -af 'uvicorn live_dashboard:app|cloudflared' || echo 'PASS: dashboard and tunnel stopped'
python tools/mac_runtime_migration.py inventory
python tools/mac_runtime_migration.py bundle
python tools/mac_runtime_migration.py verify _migration/emailautomation_runtime_<UTC>.tgz
sha256sum _migration/emailautomation_runtime_<UTC>.tgz
```

The bundler refuses active sender/dashboard/tunnel processes, active current job
JSON, held locks, a dirty tracked tree, a non-`origin/main` commit, and archive
overwrite. Do not package until all three known High sender/dispatch integrity
defects are fixed and tested. Even a valid bundle does not enable Mac sending.

## Encrypted direct transfer

No public or cloud upload is permitted. Replace `<mac-host>` with the operator's
verified SSH hostname:

```bash
ssh <mac-host> 'mkdir -p /Users/windellereboquio/AstraHandoff/_incoming && chmod 700 /Users/windellereboquio/AstraHandoff/_incoming'
scp -p _migration/emailautomation_runtime_<UTC>.tgz <mac-host>:/Users/windellereboquio/AstraHandoff/_incoming/
scp -p .env <mac-host>:/Users/windellereboquio/AstraHandoff/_incoming/emailautomation.env
ssh <mac-host> 'chmod 600 /Users/windellereboquio/AstraHandoff/_incoming/emailautomation.env'
```

Direct SSH is encrypted. Never put `.env` in the runtime archive, Git, email,
chat, or public/cloud storage.

## Prepare and restore on Mac

```bash
set -euo pipefail
TARGET=/Users/windellereboquio/AstraHandoff/emailautomation
INCOMING=/Users/windellereboquio/AstraHandoff/_incoming
mkdir -p /Users/windellereboquio/AstraHandoff
git clone https://github.com/WindzJC/emailautomation.git "$TARGET"
cd "$TARGET"
git fetch origin
git checkout main
git pull --ff-only origin main
test -z "$(git status --porcelain)"
BUNDLE="$INCOMING/emailautomation_runtime_<UTC>.tgz"
EXPECTED_COMMIT="$(tar -xOf "$BUNDLE" manifest.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["expected_commit"])')"
test "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT"
pgrep -af 'send_shard.py --profile|uvicorn live_dashboard:app|cloudflared' && exit 1 || true
python3 tools/mac_runtime_migration.py verify "$BUNDLE"
python3 tools/mac_runtime_migration.py restore "$BUNDLE"
install -m 600 "$INCOMING/emailautomation.env" .env
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m py_compile settings.py live_dashboard.py dashboard_core.py send_shard.py important_leads_workflow.py
./.venv/bin/python -m pytest -q tests/test_send_shard.py tests/test_dashboard_core.py tests/test_live_dashboard.py
node --check web_dashboard/app.js
```

Use the actual `expected_commit` from the bundle manifest if it differs from the
example. Restore refuses existing runtime-file conflicts and starts no process.

## Safe Mac verification

Profile preflight is allowed only after checksum validation and with no WSL
sender process:

```bash
./.venv/bin/python tools/mac_runtime_migration.py profiles
./.venv/bin/python send_shard.py --profile private_jc --preflight
```

The current inventory identifies `private_jc` as the only non-empty intended
profile. Re-run `profiles` against the frozen restore and preflight every name
listed in `active_intended_profiles`; do not assume this remains true. Never
omit `--preflight`.

For local-only dashboard health, bind loopback, use valid independent
credentials, and keep live actions and auto-start disabled:

```bash
export DASHBOARD_ENABLE_LIVE_ACTIONS=0 DASHBOARD_ALLOW_AUTO_START=0
./.venv/bin/python -m uvicorn live_dashboard:app --host 127.0.0.1 --port 8001 &
DASHBOARD_PID=$!
trap 'kill "$DASHBOARD_PID" 2>/dev/null || true' EXIT
curl --fail --silent --show-error http://127.0.0.1:8001/api/health >/dev/null
kill "$DASHBOARD_PID"
wait "$DASHBOARD_PID" || true
trap - EXIT
pgrep -af 'send_shard.py --profile|uvicorn live_dashboard:app|cloudflared' && exit 1 || true
```

Do not weaken authentication or enable live actions.

## Final go/no-go checklist

- WSL senders, dashboard, tunnel, dispatch, check, triage and verification jobs are stopped.
- Frozen bundle and every manifest checksum verify on Mac.
- Mac checkout is clean and exactly matches the manifest commit.
- `.env` arrived only over encrypted direct SSH, is mode `600`, and secrets were not printed.
- Queue row counts and authoritative log/state file counts match the manifest.
- SQLite snapshots pass integrity checks.
- Compilation and focused tests pass.
- All three known High integrity defects are fixed and tested.
- WSL remains the only authorized sender until a separate operator GO.
- Mac has no sender, dashboard or tunnel process after verification.

Any failed item is NO-GO.

## Rollback

Before final cutover, rollback means deleting only the new Mac clone/incoming
copy after verifying the WSL runtime remains frozen and intact. After an
authorized cutover, stop all Mac processes first, preserve its runtime for
diagnosis, verify WSL has not changed since the frozen manifest, and only then
return authority to WSL. Never run both sides during rollback.
