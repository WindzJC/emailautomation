# Email Sender / Leads Dashboard Context

## Product Goal

This repo manages large lead batches for email outreach.

Target scale: 250k+ leads.

Main workflow:

Raw lead file
→ Check Leads
→ Lead Triage / Fast Triage
→ Quarantine Review if needed
→ Preview
→ Dispatch

The app must stay lightweight by default. Heavy review tools should be manual/lazy-loaded.

---

## Main Pipeline

### 1. Check Leads

Purpose:
Clean raw imported leads before they enter the main pipeline.

Meaning:
“Is this row clean enough to enter the lead system?”

Typical work:
- Remove duplicates
- Reject invalid email syntax
- Reject disposable domains
- Reject role accounts
- Apply suppression checks
- Detect suspicious rows
- Normalize usable lead rows

Outputs:
- `_important/leads.csv`
- `_important/leads_rejected.csv`

Important:
Check Leads is cleaning/hygiene, not final lead quality routing.

---

### 2. Lead Triage / Fast Triage

Purpose:
Route cleaned leads into keep, reject, or quarantine.

Meaning:
“Now that this lead is clean, should it move forward, be rejected, or be manually reviewed?”

Outputs:
- `_important/leads_triaged_keep.csv`
- `_important/leads_triaged_reject.csv`
- `_important/leads_triage_quarantine.csv`

Fast Triage must be local-only.

Fast Triage must NOT do:
- Network requests
- Browser actions
- Public proof checks
- Website fetches
- DNS/MX checks
- Dispatch checks
- Sleeps/retries
- Strict verification

Fast Triage may do:
- Local email syntax validation
- Local name/company/domain checks
- Local scoring
- Local reason assignment
- CSV output writing
- Ledger sync if optimized/batched

---

### 3. Strict Public Proof

Purpose:
Manual/heavy verification for leads that need stronger evidence.

This is allowed to use expensive checks such as:
- Public proof lookup
- Website checks
- Search/evidence gathering
- Network requests
- Retries

Important:
Strict Public Proof must stay separate from Fast Triage.

Fast Triage should never accidentally call Strict Public Proof behavior.

---

### 4. Quarantine Review

Purpose:
Manual review of leads that Fast Triage could not confidently keep or reject.

Must be lazy-loaded.

Rules:
- Quarantine Inbox is collapsed by default.
- Do not fetch quarantine rows until opened.
- Do not auto-select the first lead.
- Do not fetch lead detail until explicit Inspect click.
- Do not load history/actions until a lead is inspected.
- Keep page size small, usually 10.
- Keep bulk actions available.

---

### 5. Preview

Purpose:
Show dispatch-ready leads before send/export.

---

### 6. Dispatch

Purpose:
Send/export eligible leads.

Dispatch should not be mixed into Fast Triage.

---

## Key Frontend File

### `web_dashboard/app.js`

Important frontend behavior:
- `/?tab=leads` should be quiet by default.
- Initial leads page load should only need:
  - `/api/auth/status`
  - `/api/leads/status`
- Do not auto-open WebSocket.
- Do not auto-fetch `/api/snapshot`.
- Do not auto-fetch quarantine rows.
- Do not auto-fetch quarantine lead details.
- Do not poll active jobs unless the relevant panel is open.
- Quarantine Inbox stays collapsed behind `Open Quarantine Inbox`.
- Lead Inspector loads only after explicit `Inspect`.

Known frontend areas:
- Leads tab bootstrapping
- Check Leads controls
- Fast Triage / important verify controls
- Quarantine Inbox
- Active Jobs
- Live Logs / snapshot / WebSocket

---

## Key Backend Files

### `live_dashboard.py`

Important pieces:
- Endpoint:
  - `POST /api/leads/verify-important`
- Job starter:
  - `_start_important_verify_job()`
- Worker:
  - `_run_important_verify_job()`

This is the main backend path for Lead Triage / Fast Triage jobs.

---

### `important_leads_verify.py`

Important pieces:
- Fast Triage:
  - `fast_triage_master_leads()`
- Per-row local classifier:
  - `_classify_fast_triage_row()`
- Strict proof path:
  - `verify_master_leads()`

Important:
`fast_triage_master_leads()` should stay local-only and fast.

`verify_master_leads()` is the slower strict proof path.

---

## Known Performance Issue

Fast Triage classification is local-only, but it can still become very slow for 240k+ leads because of disk I/O.

Observed root causes:
- Per-row SQLite lead ledger sync through `_sync_row_to_lead_ledger()`
- Per-row disk-backed cancel polling through `should_cancel()`
- Frequent output CSV checkpoint rewriting
- Previous checkpoint interval was around 100 rows
- Rewriting full accumulated keep/reject/quarantine CSVs every small interval creates cumulative disk churn

The 11-hour ETA was based on actual measured throughput, not a hardcoded estimate.

Main bottleneck:
Disk I/O, not public proof/network checks.

---

## Current Recommended Backend Fix

Smallest safe optimization:

For Fast Triage only:
- Increase checkpoint/output rewrite interval to around 5,000 rows.
- Poll cancel every around 1,000 rows instead of every row.
- Ensure cancellation still works with a small delay.
- Ensure final outputs are always written at completion.
- Keep Strict Public Proof behavior unchanged.
- Keep API contracts unchanged.
- Keep output filenames unchanged.
- Do not change classification rules.

Potential next optimization:
- Batch SQLite ledger writes in chunks/transactions.
- Avoid per-row commits.
- Review SQLite synchronous mode only if safe.

---

## Current UI Direction

Default Leads page should be summary-first.

Visible by default:
- Run Readiness
- Check Leads
- Last Check Results / compact triage summary
- Open Quarantine Inbox button

Hidden/manual by default:
- Quarantine Inbox
- Strict Public Proof
- Active Jobs
- Live Logs
- Large preview tables
- Lead Inspector
- History/action tables

For 250k+ leads:
- Do not use a row-first UI by default.
- Use summary-first or bucket-first review.
- Load rows only after user opens a section or selects a bucket/filter.

---

## Existing Important Fixes

Leads startup was quieted:
- `?tab=leads` now bootstraps only leads status.
- Quarantine review no longer loads automatically.
- First lead detail no longer auto-loads.
- Active job polling no longer starts by default.
- WebSocket no longer starts on leads page load.
- Switching to leads closes socket.
- Switching away from leads clears relevant polling timers.

Quarantine Inbox was lazy-loaded:
- Collapsed by default.
- Opens via `Open Quarantine Inbox`.
- Default page size changed from 25 to 10.
- Lead Inspector loads only after Inspect.
- Closing inbox clears heavy rendered content.

---

## Request Ownership Map

Frontend owners:
- `/api/auth/status`
  - dashboard auth bootstrap
- `/api/leads/status`
  - `fetchLeadsStatus()`
- `/api/snapshot`
  - `fetchSnapshot()`
- `/ws`
  - `connectSocket()`
- `/api/leads/quarantine-review`
  - `refreshQuarantineReview()`
- `/api/leads/quarantine-review/<lead_id>`
  - `loadQuarantineReviewLeadDetail()`
- `/api/leads/verify-important/active`
  - important verify job hydration/polling
- `/api/leads/dispatch-important/active`
  - important dispatch job hydration/polling
- `/api/leads/check-important/active`
  - important check job hydration/polling

---

## Codex Operating Rules

Use Codex as a patch tool, not an autonomous explorer.

Default rules:
- Patch only.
- Prefer one file.
- Do not run uvicorn unless explicitly asked.
- Do not run browser capture unless explicitly asked.
- Do not run full tests unless explicitly asked.
- Do not inspect unrelated files.
- Do not refactor unrelated code.
- Do not rename functions unless required.
- Do not change backend API contracts unless explicitly required.
- Show files changed and diff summary, then stop.

Preferred prompt opening:

Read `CODEX_CONTEXT.md` first.

Patch-only mode. Conserve usage.

Task:
[exact small task]

Rules:
- Do not run uvicorn.
- Do not run browser capture.
- Do not run tests.
- Show diff and stop.

---

## Important Product Rule

Check Leads and Lead Triage are not the same.

Check Leads:
Clean/hygiene step.

Lead Triage:
Routing step into keep/reject/quarantine.

Strict Public Proof:
Heavy evidence step.

Quarantine Review:
Manual edge-case review.

Do not merge these stages unless explicitly requested.
