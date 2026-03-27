# Deployment

## Compose stack

This repo now supports a two-service Docker Compose stack:

- `web`: FastAPI dashboard, API, WebSocket, and static frontend
- `worker`: persistent tmux host for sender/runtime processes

The current runtime backend remains `tmux`. In Compose, both services share:

- `/app/data` for uploads, cleaned files, shards, logs, and state
- a named Docker volume mounted at `/tmux`
- `TMUX_TMPDIR=/tmux` so the tmux socket stays on a Linux-native volume instead of the Windows bind mount

## Prerequisites

- Docker
- Docker Compose v2
- A populated `.env` file with working provider secrets

Start from:

```bash
cp .env.example .env
```

Then set at minimum:

- `SENDGRID_API_KEY`
- `SENDGRID_EVENT_PUBLIC_KEY` if webhook signature verification is enabled
- `PRIVATE_ANNETTE_APP_PW`
- `PRIVATE_JORDAN_APP_PW`
- `PRIVATE_JODI_APP_PW`
- `PRIVATE_ALISON_APP_PW`
- `PRIVATE_FIORELA_APP_PW`

Optional Compose-facing settings:

- `HOST_DASHBOARD_PORT=8001`
- `DASHBOARD_PROFILE_GUARD_ENABLED=0`

## Persistent data

Compose bind-mounts the local [data](/mnt/d/VS/email automation/data) directory into `/app/data`.

That means:

- existing managed runtime state is reused
- uploads, cleaned files, shard CSVs, logs, and state survive container restarts
- moving the stack to another host means copying the `data/` directory with the repo

## Start

```bash
docker compose up --build -d
```

Dashboard:

```text
http://localhost:8001
```

If you changed `HOST_DASHBOARD_PORT`, use that port instead.

## Stop

```bash
docker compose down
```

This stops containers but keeps `data/` intact.

## Update

```bash
docker compose build
docker compose up -d
```

## Mac handoff

If you want to continue the same live campaign on a Mac, GitHub alone is not enough.
You also need the managed runtime payload:

- `.env`
- `data/`

From the source machine:

```bash
./sync_to_mac.sh user@host /Users/user/emailautomation
```

Then on the Mac:

```bash
cd /Users/user/emailautomation
./setup_mac_runtime.sh
```

After setup:

- dashboard: `./run_live_dashboard.sh`
- senders: `TMUX_SENDGRID_ATTACH=0 ./run_sendgrid_tmux.sh`

Do not run the Windows and Mac senders at the same time against the same campaign data.

## Logs

Dashboard logs:

```bash
docker compose logs -f web
```

Worker logs:

```bash
docker compose logs -f worker
```

## Notes

- The dashboard routes and frontend behavior are unchanged.
- The worker container does not expose a public port. It exists to keep the tmux runtime server alive.
- The current tmux-backed runtime is intentionally preserved for this phase. A later phase can swap the runtime backend without changing the dashboard layer.
