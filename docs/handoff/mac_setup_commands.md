# Mac Setup Commands

> Archived one-way setup notes. Do not use these commands for a current runtime
> handoff; use [`README.md`](README.md) and root `./handoff`.

Place `email_automation_mac_handoff_20260525_234519.tgz` in the Mac home directory, then run:

```bash
cd ~
tar -xzf email_automation_mac_handoff_20260525_234519.tgz
cd email-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./.venv/bin/python -m unittest tests.test_live_dashboard tests.test_web_dashboard_app
node --check web_dashboard/app.js
./.venv/bin/python -m uvicorn live_dashboard:app --host 127.0.0.1 --port 8000
```

Open the dashboard at:

```text
http://127.0.0.1:8000/
```

Before starting any sender, manually recreate secrets from `handoff/mac_secrets_checklist.md`, then run the dashboard preflight/readiness checks.
