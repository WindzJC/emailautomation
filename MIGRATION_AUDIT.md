# Migration Audit

Scope: repo audit for moving the current mail-ops dashboard from the current Windows-hosted/WSL-style runtime to a Linux VPS where the dashboard and sender runtime continue working while the original Windows machine is off.

Audit date: 2026-03-25

## Executive Summary

This is not a rewrite.

The current app is already structurally close to a Linux deployment because the primary runtime stack is:

- `FastAPI` + static frontend
- `bash` launch scripts
- `tmux` process orchestration
- `pathlib`/relative file paths
- POSIX file locking via `fcntl`

That said, the repo is not yet deployment-ready for the target end state. The main work is:

- extract storage/config out of repo-root assumptions
- separate web control from worker runtime
- remove direct `tmux` coupling from FastAPI request handlers
- make service startup non-interactive
- containerize and mount persistent volumes

## Current Architecture

- Web/API: `live_dashboard.py`
- Dashboard control/state: `dashboard_core.py`
- Leads upload/clean/preview/write: `leads_workflow.py`
- Sender worker/runtime: `send_shard.py`
- Dashboard launcher: `run_live_dashboard.sh`, `run_dashboard_tmux.sh`
- Sender launcher: `run_sendgrid_tmux.sh`
- Tunnel helper: `run_tunnel_tmux.sh`

Current behavior is already browser-based, but the browser controls local processes and local files on the host machine.

## Findings By Component

| Component | Status | Notes |
| --- | --- | --- |
| `live_dashboard.py` | Needs refactor | FastAPI itself is Linux-safe. The issue is that request handlers directly invoke local process-control functions from `dashboard_core.py`. |
| `dashboard_core.py` | Needs refactor | Strong coupling to `tmux`, `bash`, repo-root files, local env files, and local process inspection. |
| `leads_workflow.py` | Needs refactor | Logic is Linux-safe, but storage is hardwired to repo-relative directories and profile CSV paths. |
| `send_shard.py` | Needs refactor | Core worker logic is Linux-safe, but config, profiles, file paths, counters, and shard mutation are all bound to local files and in-process configuration. |
| `run_live_dashboard.sh` | OK to migrate as-is | Simple Uvicorn wrapper; should become container entrypoint or process command. |
| `run_dashboard_tmux.sh` | Needs refactor | Useful for ops on a host, but not the right final production control plane for Compose/VPS deployment. |
| `run_sendgrid_tmux.sh` | Needs refactor | Interactive secret prompt, credit check, `tmux` pane orchestration, and preflight coupling make it unsuitable as the final worker bootstrap. |
| `run_tunnel_tmux.sh` | Needs refactor | Fine as an ops helper, but not the final deployment model. Tunnel should run as a service or outside the app container stack. |
| `.env.example` | OK to migrate as-is | Good start, but incomplete for the full deployment surface. |
| `streamlit_monitor.py` | Unknown, verify manually | Secondary UI path; likely not needed for the FastAPI deployment target. Contains environment-specific references. |

## Blocker Inventory

### OK to migrate as-is

- FastAPI app structure in `live_dashboard.py`
- Static frontend serving from `web_dashboard/`
- WebSocket live-update pattern
- Pydantic request models
- Leads cleaning/sharding logic in `leads_workflow.py`
- Atomic file replace patterns in leads/shard writes
- POSIX file locking approach for Linux target
- Environment-variable loading pattern already present in several places

### Needs refactor

#### 1) Web and worker are too tightly coupled

Observed:

- `live_dashboard.py` calls `run_sendgrid_launcher()`, `start_sendgrid_profile()`, `stop_sendgrid_profile()`, and `stop_sendgrid_session()` directly.
- `dashboard_core.py` both computes dashboard state and owns process orchestration.

Why it matters:

- The web app should not be the only place that knows how to launch and supervise workers.
- For VPS deployment, worker lifecycle should survive browser disconnects and web process restarts.

Target:

- `web` service for UI/API/WebSocket
- `worker` service for send execution and state/log updates
- shared persisted state or explicit control channel between them

#### 2) Process model is `tmux`-centric

Observed:

- `dashboard_core.py` inspects panes with `tmux list-panes`, `tmux capture-pane`, `tmux send-keys`, and `tmux kill-session`.
- `run_sendgrid_tmux.sh` and `run_dashboard_tmux.sh` build runtime around `tmux`.

Why it matters:

- `tmux` works on Linux, but it is not a clean long-term service boundary for VPS + Docker Compose.
- It is fine as a temporary host-side supervisor, but weak as the final production orchestration layer.

Target:

- either one worker container per sender profile
- or a single worker service with explicit job state
- logging/state exposed without scraping `tmux` panes

#### 3) Storage is anchored to repo root

Observed:

- `leads_workflow.py` writes `uploads/`, `cleaned/`, `reports/`, `backups/leads/`, `leads_dashboard_state.json` under repo root.
- `dashboard_core.py` uses repo-root paths for logs, webhook store, suppressions, counters, and backups.
- `send_shard.py` uses relative paths for CSVs, logs, counters, suppressions, and account maps.

Why it matters:

- This works locally, but production deployment should separate code from mutable data.
- Containers need mounted volumes for durability and easier backup/restore.

Target:

- config-driven data root such as `/app/data`
- mounted subdirs for `uploads`, `cleaned`, `reports`, `shards`, `logs`, `state`, `backups`

#### 4) Config is partially env-based, but still scattered

Observed:

- `dashboard_core.py` loads `.env.local` and `.env` directly.
- `send_shard.py` keeps profile defaults and many path/default constants inline.
- `run_sendgrid_tmux.sh` prompts interactively for `SENDGRID_API_KEY` if absent.

Why it matters:

- VPS deployment must be non-interactive.
- One central settings module is needed so containers and services read the same config model.

Target:

- single settings/config module
- env-driven data paths, ports, profile limits, secrets, dashboard auth flags
- no interactive secret prompts in production start scripts

#### 5) Current working directory assumptions are widespread

Observed:

- multiple scripts do `cd "$ROOT"` and rely on relative filenames
- `send_shard.py` resolves many files through raw `Path(args.csv)`/`Path(args.log)` style values
- tooling assumes repo-root execution

Why it matters:

- Containers can preserve a working directory, but the system will be more robust if path resolution is explicit and centralized.

Target:

- explicit `APP_ROOT` and `DATA_ROOT`
- path building through config, not implicit current directory

#### 6) Authentication is not in the app

Observed:

- `live_dashboard.py` exposes dashboard controls directly
- no app-side auth layer is present

Why it matters:

- This is acceptable behind a trusted local network.
- For remote deployment, auth must exist at the edge or in the app.

Target:

- prepare to sit behind Cloudflare Access or a reverse proxy auth layer
- optionally add simple app auth if edge auth is not guaranteed

### Linux blocker

No confirmed Linux blockers were found in the primary runtime path audited here.

Important nuance:

- `fcntl` locking is a blocker for native Windows portability, but the target platform is Linux, so this is acceptable for the VPS goal.
- `tmux` and `bash` are Linux-native, so they are not Linux blockers. They are architecture refactor items.

### Unknown, verify manually

#### 1) VPS outbound mail/runtime policies

Unknowns:

- whether outbound SMTP from the VPS will be allowed/reliable for any non-SendGrid profiles
- whether the current provider mix is intended to remain exactly the same in production

Why it matters:

- Code may migrate cleanly while deliverability or SMTP egress policy fails operationally.

#### 2) Final worker topology

Unknowns:

- whether to preserve “one sender = one long-running process” exactly
- whether to replace `tmux` with one worker container per profile

Why it matters:

- This affects deployment shape, logs, restart semantics, and control APIs.

#### 3) Timezone/schedule expectations

Observed:

- scheduling and stop windows depend on local time concepts such as `stop_at_local`

Unknowns:

- which timezone should be authoritative on the VPS

Why it matters:

- migration to Linux/VPS can silently change schedule behavior if timezone is not explicit

#### 4) Secondary/legacy paths outside primary FastAPI stack

Observed:

- `streamlit_monitor.py` contains a hardcoded `/mnt/d/VS/email automation` example
- `KEYS` contains a `D:\...` path example

Why it matters:

- These do not block the FastAPI deployment path, but they should be reviewed or retired to avoid ops confusion.

## Direct Answers To The Requested Audit Classes

### Hardcoded Windows paths

Result: mostly absent in the primary runtime path.

Found:

- `streamlit_monitor.py` contains `/mnt/d/VS/email automation`
- `KEYS` contains `D:\VS\MY WEBSITE`

Assessment:

- runtime FastAPI/dashboard path is not obviously blocked by hardcoded Windows paths
- docs/secondary tooling still contain environment-specific references

### Windows-only shell calls

Result: none confirmed.

Assessment:

- current runtime uses Linux/WSL-friendly tools (`bash`, `tmux`, `fcntl`)
- this is good for Linux VPS migration, but it means the system is not truly host-agnostic yet

### Assumptions about current working directory

Result: confirmed, widespread.

Assessment:

- not a blocker, but should be normalized into config-driven paths

### Subprocess calls relying on local console/session behavior

Result: confirmed.

Observed:

- worker control via `tmux send-keys`, session layout creation, pane capture, and shell command composition

Assessment:

- this is the biggest refactor area

### File locking behavior

Result: confirmed use of POSIX locking.

Observed:

- `recipient_file_lock.py`
- multiple lock sites in `send_shard.py`

Assessment:

- okay for Linux target
- must be preserved carefully when moving to mounted volumes

### Local browser / Task Scheduler / desktop session assumptions

Result: no confirmed blocker in the primary FastAPI stack.

Observed:

- no `os.startfile`, browser auto-open, or Task Scheduler dependency found in the main runtime files audited here

### Sender jobs coupled directly to FastAPI request handlers

Result: confirmed.

Assessment:

- needs refactor into a cleaner web/worker boundary

### Secrets in code or flat files

Result: partial risk, not hardcoded-secret blocker.

Observed:

- secrets are not hardcoded in the audited runtime files
- secret loading is spread across env files, shell startup, and direct env lookups
- `run_sendgrid_tmux.sh` falls back to an interactive prompt

Assessment:

- move to a single settings model and non-interactive production boot

### Logs/state stored in unstable temp paths

Result: not unstable, but not production-structured.

Observed:

- logs/state/counters/reports live under repo root

Assessment:

- durable enough locally
- should move into mounted volume paths for VPS deployment

## Recommended Migration Order

1. Audit complete
2. Introduce a central settings module for ports, secrets, and all storage roots
3. Move mutable artifacts into a single data root with subdirectories
4. Separate worker orchestration from dashboard state aggregation
5. Replace or isolate `tmux` supervision behind a worker/service boundary
6. Containerize web and worker
7. Mount persistent volumes
8. Deploy on Linux VPS
9. Put remote access/auth in front of it

## Lowest-Risk Initial Refactor Targets

If work starts after this audit, the first code changes should be:

1. Create a config module that owns:
   - app root
   - data root
   - uploads/cleaned/reports/shards/logs/state paths
   - dashboard port/host
   - sender caps
   - secret/env loading

2. Refactor:
   - `leads_workflow.py`
   - `dashboard_core.py`
   - `send_shard.py`

   so they do not hardcode repo-root mutable data paths.

3. Define the worker boundary:
   - what the web app asks the worker to do
   - where job state is written
   - how logs are tailed without `tmux` pane scraping

## Acceptance Target

Migration is done only when all of these are true:

- original Windows machine is off
- dashboard is reachable remotely in browser
- leads upload/clean/preview/write still works
- send-cap editing still works
- sender jobs run on the Linux host
- logs/state persist across restart
- browser disconnect does not stop active sends

## Bottom Line

This repo does not look blocked on Linux.

The main challenge is not FastAPI and not an obvious Windows-only dependency. The main challenge is turning a local `FastAPI + tmux + repo-root files` ops setup into a proper `web + worker + persistent storage + deployment` system.
