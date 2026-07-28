# Mac Handoff Audit

> Historical audit only. Its paths and queue counts are not current operating
> instructions. Use [`README.md`](README.md) for bidirectional handoff.

Generated: 2026-05-25T23:23:58+08:00
Repo path: `/home/jc/email-automation`
Latest commit: `83e07ae Fix manual author staged dispatch flow`

## Canonical Live Queue Paths

Canonical sender queues are the root `recipients_*.csv` files in `/home/jc/email-automation`. `send_shard.py`, dashboard safety/readiness, dispatch, and queue repair now resolve live queues through `settings.SHARDS_DIR`, which defaults to the repo root.

`data/shards/` is legacy/non-canonical for live sending in this repo state. Do not use it as the Mac live queue source unless the sender is intentionally refactored again.

| Queue | Rows | Lines | Canonical path |
| --- | ---: | ---: | --- |
| `recipients_private_jc.csv` | 1788 | 1789 | `/home/jc/email-automation/recipients_private_jc.csv` |
| `recipients_sendgrid_1.csv` | 120 | 121 | `/home/jc/email-automation/recipients_sendgrid_1.csv` |
| `recipients_sendgrid_2.csv` | 133 | 134 | `/home/jc/email-automation/recipients_sendgrid_2.csv` |
| `recipients_sendgrid_3.csv` | 128 | 129 | `/home/jc/email-automation/recipients_sendgrid_3.csv` |
| `recipients_sendgrid_4.csv` | 127 | 128 | `/home/jc/email-automation/recipients_sendgrid_4.csv` |
| `recipients_sendgrid_5.csv` | 126 | 127 | `/home/jc/email-automation/recipients_sendgrid_5.csv` |

Latest root SendGrid already-sent repair removed 449 logged recipients. Current canonical queues: Private JC 1,788 rows; SendGrid total 634 rows; SG1-SG5 120, 133, 128, 127, 126.

## Queue Path Repair

Latest root queue repair backup: `/home/jc/email-automation/data/state/backups/root_queue_path_repair/20260525_232240`
Stale root SendGrid queues were archived before rewrite. Root queues were rebuilt from the latest confirmed dispatch preview assignment only.

Latest SendGrid already-sent repair backup: `/home/jc/email-automation/data/state/backups/root_sendgrid_already_sent_repair/20260525_234339`

## Validation

- `./.venv/bin/python -m unittest tests.test_live_dashboard tests.test_web_dashboard_app`
- `node --check web_dashboard/app.js`
- `git diff --check -- send_shard.py live_dashboard.py dashboard_core.py tools/rebuild_recipient_queues.py web_dashboard/app.js web_dashboard/styles.css tests/test_live_dashboard.py tests/test_web_dashboard_app.py settings.py`

## Secrets

Do not include `.env`, `.env.local`, `KEYS/`, OAuth tokens, Gmail credentials, SendGrid API keys, or other local auth/session files in shared handoff archives. Recreate those manually on the Mac.

## Current Git Status

```text
M dashboard_core.py
 M data/shards/recipients_private_jc.csv
 M live_dashboard.py
 M recipients_sendgrid_1.csv
 M recipients_sendgrid_2.csv
 M recipients_sendgrid_3.csv
 M recipients_sendgrid_4.csv
 M recipients_sendgrid_5.csv
 M settings.py
 M tests/test_live_dashboard.py
 M tests/test_web_dashboard_app.py
 M tools/rebuild_recipient_queues.py
 M web_dashboard/app.js
 M web_dashboard/index.html
 M web_dashboard/styles.css
?? recipients_private_jc.csv
```
