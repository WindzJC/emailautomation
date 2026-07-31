# Astra Linux cloud deployment

This deployment keeps the existing fail-closed, single-machine runtime authority
model. `cloud` is a third supported machine identity alongside `mac` and
`windows-wsl`. A checkout, environment file, or systemd unit never grants
authority by itself.

The packaged paths assume:

- repository: `/opt/astra/emailautomation`
- service account: `astra`
- protected dashboard/backup environment: `/etc/astra-emailautomation/astra.env`
- protected per-profile sender environments:
  `/etc/astra-emailautomation/profiles/PROFILE.env`
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

Each sender instance loads only its own profile environment, never the
dashboard environment or another sender's credentials. Create the selected
profile file from the mapping in `profile-env.example`:

```bash
sudoedit /etc/astra-emailautomation/profiles/private_jc.env
sudo chown root:astra /etc/astra-emailautomation/profiles/private_jc.env
sudo chmod 0640 /etc/astra-emailautomation/profiles/private_jc.env
```

Every profile file contains the exact deployed commit and exactly one
credential variable. Do not consolidate credentials into a shared sender
environment.

## Configured sender profiles

| Profile | Provider | Queue | Preview | Credential variable |
| --- | --- | --- | --- | --- |
| `private_alison` | private SMTP | `recipients_4.csv` | `private_alison_message_preview.csv` | `PRIVATE_ALISON_APP_PW` |
| `private_annette` | private SMTP | `recipients_1.csv` | `private_annette_message_preview.csv` | `PRIVATE_ANNETTE_APP_PW` |
| `private_fiorela` | private SMTP | `recipients_5.csv` | `private_fiorela_message_preview.csv` | `PRIVATE_FIORELA_APP_PW` |
| `private_jc` | private SMTP | `recipients_private_jc.csv` | `private_jc_message_preview.csv` | `PRIVATE_JC_PASSWORD` |
| `private_jc_warm` | private SMTP, pre-rendered | `recipients_private_jc_warm.csv` | `private_jc_warm_message_preview.csv` | `PRIVATE_JC_PASSWORD` |
| `private_jodi` | private SMTP | `recipients_3.csv` | `private_jodi_message_preview.csv` | `PRIVATE_JODI_APP_PW` |
| `private_jordan` | private SMTP | `recipients_2.csv` | `private_jordan_message_preview.csv` | `PRIVATE_JORDAN_APP_PW` |
| `sendgrid_alison` | SendGrid API | `recipients_sendgrid_4.csv` | `sendgrid_alison_message_preview.csv` | `SENDGRID_API_KEY` |
| `sendgrid_annette` | SendGrid API | `recipients_sendgrid_1.csv` | `sendgrid_annette_message_preview.csv` | `SENDGRID_API_KEY` |
| `sendgrid_fiorela` | SendGrid API | `recipients_sendgrid_5.csv` | `sendgrid_fiorela_message_preview.csv` | `SENDGRID_API_KEY` |
| `sendgrid_jodi` | SendGrid API | `recipients_sendgrid_3.csv` | `sendgrid_jodi_message_preview.csv` | `SENDGRID_API_KEY` |
| `sendgrid_jordan` | SendGrid API | `recipients_sendgrid_2.csv` | `sendgrid_jordan_message_preview.csv` | `SENDGRID_API_KEY` |

The unit, verifier, dashboard backend, and sender CLI all independently reject
unknown profile identifiers. A profile cannot silently fall back to
`private_jc`.

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
     deploy/cloud/verify.sh --profile private_jc --require-authority
   ```

5. Review `./handoff status` and service logs. Enabling or starting the sender is
   a separate explicit, profile-specific operator action:

   ```bash
   sudo systemctl enable astra-dashboard.service
   sudo systemctl start astra-dashboard.service
   sudo systemctl enable astra-sender@private_jc.service
   sudo systemctl start astra-sender@private_jc.service
   ```

`astra-sender@.service` requires an explicit instance name. Each instance loads
only `/etc/astra-emailautomation/profiles/PROFILE.env`, runs
`send_shard.py --profile PROFILE`, holds a profile-specific systemd `flock`,
and then acquires the application's profile runtime lock. Exit code 75 means
another instance owns that profile's service lock and is not restarted.

The root-owned polkit rule grants the `astra` dashboard account permission to
start or stop only the 12 configured sender instances. The dashboard uses the
systemd runtime backend on cloud, so per-profile Start, Stop, active status, and
delivery-guard stops all address the selected template instance. Bulk cloud
startup is intentionally refused.

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

`verify.sh` is inspection-only and requires `--profile`; there is no default.
It requires a clean tracked checkout and exact `ASTRA_EXPECTED_GIT_COMMIT`,
checks Python/system dependencies, reads handoff status, resolves only the
selected profile's queue/preview/credential mapping, applies the same strict
preview decision as activation, and runs:

```bash
python send_shard.py --profile private_jc --preflight
```

Preflight bypasses send authority and cannot submit a message. Passing
`--require-authority` additionally requires active cloud authority and is used
as the sender instance's `ExecCondition`; in that mode the selected credential
must also exist in the selected protected profile environment.

## Backups

Restic provides encrypted, content-addressed, checksummed backups. The backup
includes `data/`, `_important/`, and `.runtime_handoff/` and explicitly excludes
environment files, virtual environments, source, and handoff archives. All
profile queues, previews, logs, suppressions, ledgers, and authority state are
included as runtime data; no `/etc/astra-emailautomation` credential file is
inside the repository backup scope.

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

1. Stop every active sender instance, the dashboard, and other cloud runtime
   services/jobs, then confirm
   `ASTRA_MACHINE_ID=cloud ./handoff status` has no blockers.
   Inventory instances explicitly:

   ```bash
   systemctl list-units 'astra-sender@*.service'
   systemctl list-unit-files 'astra-sender@*.service'
   ```

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
