# Astra Linux cloud deployment

This deployment keeps the existing fail-closed, single-machine runtime authority
model. `cloud` is a third supported machine identity alongside `mac` and
`windows-wsl`. A checkout, environment file, or systemd unit never grants
authority by itself.

The packaged paths assume:

- repository: `/opt/astra/emailautomation`
- service account: `astra`
- protected environment: `/etc/astra-emailautomation/astra.env`
- dashboard listener: `127.0.0.1:8000`

Do not run bootstrap, pull a new commit into the live Mac checkout, stop the Mac
sender, export runtime, or activate cloud authority until a reviewed maintenance
window. The live sender checks its pinned Git commit before every submission.

## Review and bootstrap

Review from the development checkout:

```bash
git branch --show-current
git status --short
git diff --check
git diff -- runtime_authority.py tools/runtime_handoff.py handoff handoff.ps1
git diff -- deploy/cloud tests/test_runtime_handoff.py
```

After the change is committed and reviewed, clone that exact commit on the
cloud host at `/opt/astra/emailautomation`. Then inspect and run:

```bash
sudo ASTRA_REPO_ROOT=/opt/astra/emailautomation \
  /opt/astra/emailautomation/deploy/cloud/bootstrap.sh
sudoedit /etc/astra-emailautomation/astra.env
sudo chmod 0640 /etc/astra-emailautomation/astra.env
sudo chown root:astra /etc/astra-emailautomation/astra.env
```

`bootstrap.sh` installs dependencies and unit files but deliberately does not
enable or start any unit. Install `cloudflared` separately from Cloudflare's
signed package repository if the tunnel is required.

Never copy `.env` to the cloud host. Populate the external environment file
from the secret manager or password vault. Keep the restic password in the
separate file named by `RESTIC_PASSWORD_FILE`, owned by `root:astra` and mode
`0640`. The systemd units set `ASTRA_DISABLE_DOTENV=1`, so application settings
cannot fall back to repository-local `.env` files.

## Runtime transfer and authority cutover

Both source and target must be on the exact reviewed Git commit. The normal
handoff archive contains queues, logs, previews, suppressions, unsubscribe
state, campaign state, counters, consistent SQLite snapshots, idempotency state,
and the handoff authority metadata. It excludes `.env`, virtual environments,
caches, source code, and secrets. Every runtime file has a SHA-256 and size in
the manifest; queue/log counts and SQLite integrity are verified on import.

Import checks the target generation floor and used-bundle ledger, rejects stale
generations and reused archives, archives the prior target runtime, restores
atomically, and never starts a sender. Export first marks the source
`handoff_in_progress`, so a failed transfer leaves both machines unable to send.

During the reviewed cutover window only:

1. Stop and verify the Mac sender/dashboard/tunnel and all dispatch/check/triage
   jobs. Do not proceed while any runtime process is active.
2. Put Mac and cloud on the exact same reviewed commit. If the Mac authority was
   pinned to the previous commit, rebind it only after all Mac runtime processes
   are stopped and queue safety passes:

   ```bash
   ASTRA_MACHINE_ID=mac ./handoff activate --initialize --force
   ```

3. Configure `HANDOFF_CLOUD_HOST` and `HANDOFF_CLOUD_REPO`, then transfer:

   ```bash
   ASTRA_MACHINE_ID=mac ./handoff switch-to-cloud
   ```

   SCP already encrypts transport. For additional encryption at rest, use the
   manual export path instead:

   ```bash
   ASTRA_MACHINE_ID=mac ./.venv/bin/python tools/runtime_handoff.py \
     --repo "$PWD" export --target cloud --output-dir runtime_handoff_bundles
   age -r AGE_PUBLIC_RECIPIENT \
     -o runtime_handoff_bundles/runtime_handoff.age \
     runtime_handoff_bundles/runtime_handoff_mac_to_cloud_*.tgz
   scp runtime_handoff_bundles/runtime_handoff.age CLOUD_HOST:/tmp/
   ```

   Decrypt only on the cloud host into a mode-`0700` temporary directory, then
   pass the resulting `.tgz` to `./handoff receive`. Delete plaintext temporary
   archives after verified import. Never commit any archive.

4. On cloud, verify without sending:

   ```bash
   cd /opt/astra/emailautomation
   sudo -u astra env \
     ASTRA_MACHINE_ID=cloud \
     ASTRA_EXPECTED_GIT_COMMIT="$(git rev-parse HEAD)" \
     deploy/cloud/verify.sh --require-authority
   ```

5. Review `./handoff status` and service logs. Enabling or starting the sender is
   a separate explicit operator action:

   ```bash
   sudo systemctl enable astra-dashboard.service
   sudo systemctl start astra-dashboard.service
   sudo systemctl enable astra-sender.service
   sudo systemctl start astra-sender.service
   ```

The sender unit holds a systemd `flock` and the application also holds its
profile runtime lock, preventing concurrent `private_jc` instances. Exit code
75 means another instance owns the service lock and is not restarted.

## Dashboard and tunnel

The dashboard unit binds only to `127.0.0.1:8000`, enables live actions, loads
credentials only from the protected environment file, and restarts on failure.
Automatic sender startup remains explicitly disabled. The dashboard is not
directly reachable from the public network.

Copy `cloudflared-config.example.yml` to `/etc/cloudflared/config.yml`, replace
the placeholders on-host, and keep the tunnel credentials JSON outside Git with
mode `0600`. Configure Cloudflare Access or another identity-aware policy before
publishing the hostname.

## Verification

`verify.sh` is inspection-only. It requires a clean tracked checkout and exact
`ASTRA_EXPECTED_GIT_COMMIT`, checks Python/system dependencies, reads handoff
status, compares canonical queue/generated/validated preview fingerprints, and
runs:

```bash
python send_shard.py --profile private_jc --preflight
```

Preflight bypasses send authority and cannot submit a message. Passing
`--require-authority` additionally requires active cloud authority and is used
as the sender unit's `ExecCondition`.

## Backups

Restic provides encrypted, content-addressed, checksummed backups. The backup
includes `data/`, `_important/`, and `.runtime_handoff/` and explicitly excludes
environment files, virtual environments, source, and handoff archives.

`backup.sh` refuses unless every sender/dashboard/tunnel/dispatch/check/triage
process and active job is stopped. This protects SQLite, queues, logs, and
ledgers from a cross-file inconsistent snapshot. The timer is therefore opt-in
and must be scheduled inside a real offline cloud maintenance window:

```bash
sudo systemctl enable astra-backup.timer
sudo systemctl start astra-backup.timer
```

Do not restore restic data over a live or newer runtime. Restore into an empty
staging directory, inspect the snapshot, compare its authority generation and
Git commit with the live target, and use the normal verified handoff
export/import flow for authority-bearing migration. A lower generation must
never replace a higher local generation floor.

## Roll back authority to Mac

Rollback means transferring the complete updated cloud runtime back to Mac, not
merely starting the old Mac queue.

1. Stop all cloud runtime services/jobs and confirm
   `ASTRA_MACHINE_ID=cloud ./handoff status` has no blockers.
2. Put Mac and cloud on the same exact reviewed commit.
3. Configure `HANDOFF_MAC_HOST` and `HANDOFF_MAC_REPO`.
4. From cloud:

   ```bash
   ASTRA_MACHINE_ID=cloud ./handoff switch-to-mac
   ```

5. Verify Mac status and preflight. Start the Mac sender only after import
   succeeds and authority explicitly reports `authorized_machine=mac`.

If export or import fails, do not force-activate either side. The source remains
unauthorized after export and the target remains disabled after failed import,
which prevents duplicate sends.
