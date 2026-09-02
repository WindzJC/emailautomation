import fs from "node:fs";
import path from "node:path";

import React from "react";
import { act, cleanup, fireEvent } from "@testing-library/react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardApp } from "./main.jsx";

const INDEX_HTML = fs.readFileSync(
  path.resolve(process.cwd(), "web_dashboard/index.html"),
  "utf8",
);

const FRESH_SOURCE = {
  dispatch_source_mode: "triaged_keep",
  dispatch_source_name: "Fast Triage Keep",
  dispatch_source_path: "/synthetic/fresh/leads_triaged_keep.csv",
  dispatch_source_exists: true,
  dispatch_source_row_count: 20,
  dispatch_eligible_row_count: 20,
  dispatch_block_reason: "",
  verification_file_mtime: "2026-08-28T00:00:00Z",
};

const RECONTACT_SOURCE = {
  dispatch_source_mode: "cleaned",
  dispatch_source_name: "Checked Recontact Pool",
  dispatch_source_path: "/synthetic/recontact/leads.csv",
  dispatch_source_exists: true,
  dispatch_source_row_count: 15203,
  dispatch_eligible_row_count: 15203,
  dispatch_block_reason: "",
  verification_file_mtime: "",
};

function leadCheck(state = "failed") {
  if (state === "success") {
    return {
      state: "success",
      label: "Success — ready for Preview Dispatch",
      message: "Fresh check complete.",
      preview_ready: true,
      preview_state: "ready",
      preview_block_reason: "",
      output_exists: true,
      rejected_exists: true,
      cleaned_rows: 20,
    };
  }
  if (state === "processing") {
    return {
      state: "processing",
      label: "Processing / checking",
      message: "Lead check is processing.",
      preview_ready: false,
      preview_state: "not_ready",
      preview_block_reason: "Lead check is still processing.",
      output_exists: false,
      rejected_exists: false,
      cleaned_rows: 0,
    };
  }
  return {
    state: "failed",
    label: "Failed/Stale — check did not produce outputs",
    message: "Check failed or stale. No cleaned/rejected output files were produced.",
    preview_ready: false,
    preview_state: "not_ready",
    preview_block_reason: "Check failed or stale: No cleaned/rejected output files were produced.",
    output_exists: false,
    rejected_exists: false,
    cleaned_rows: 0,
  };
}

function leadsStatus({
  checkState = "failed",
  freshSource = FRESH_SOURCE,
  recontactSource = RECONTACT_SOURCE,
  preview = {},
  previewCurrent = false,
  activeDispatch = null,
} = {}) {
  const progress = checkState === "failed" ? {
    job_id: "old-fresh-job",
    selected_upload_type: "cold",
    phase: "ready_for_preview",
    status: "ready_for_preview",
    processed_rows: 15203,
    output_exists: false,
    rejected_exists: false,
    row_counts: { cleaned_rows: 0, rejected_rows: 0 },
  } : {};
  return {
    lead_check_status: leadCheck(checkState),
    lead_ops_progress_by_workflow: { cold: progress, warm_research: {} },
    active_important_check_job: null,
    active_important_check_jobs: { cold: null, warm_research: null },
    active_important_verify_job: null,
    active_important_dispatch_job: activeDispatch,
    important_input_label: "/synthetic/stale-fresh/leadschecker.csv",
    important_output_label: "/synthetic/stale-fresh/leads.csv",
    important_rejected_label: "/synthetic/stale-fresh/leads_rejected.csv",
    dispatch_source_mode: "triaged_keep",
    dispatch_source: freshSource,
    dispatch_source_options: {
      triaged_keep: freshSource,
      cleaned: recontactSource,
    },
    latest_auto_dispatch_preview: preview,
    latest_auto_dispatch_preview_current: previewCurrent,
    latest_master_check: {},
    latest_lead_triage: {},
    latest_dispatch: {},
    current_send_safety: { blocked: false, reasons: [] },
    pipeline: {},
    lead_funnel: {},
    jc_queue: { count: 0, fieldnames: ["Email", "BookTitle"] },
    sendgrid_queues: [],
  };
}

function restartedStagedRecontactStatus() {
  const runId = "check_20260831_222138_b8d2806e";
  const freshSource = {
    ...FRESH_SOURCE,
    dispatch_source_path: `/_important/runs/${runId}/leads_triaged_keep.csv`,
    dispatch_source_row_count: 11221,
    dispatch_eligible_row_count: 11221,
    run_id: runId,
    source_resolution: "latest_completed_staged_run",
  };
  const recontactSource = {
    ...RECONTACT_SOURCE,
    dispatch_source_path: `/_important/runs/${runId}/leads.csv`,
    dispatch_source_row_count: 15342,
    dispatch_eligible_row_count: 15342,
    verification_required: false,
    verification_file_mtime: "2026-08-31T22:36:57.412396+00:00",
    run_id: runId,
    source_resolution: "latest_completed_staged_run",
  };
  const progress = {
    job_id: runId,
    current_run_id: runId,
    selected_upload_type: "cold",
    phase: "preview_complete",
    status: "preview_complete",
    processed_rows: 19271,
    total_rows: 19271,
    output_exists: true,
    rejected_exists: true,
    output_path: recontactSource.dispatch_source_path,
    rejected_path: `/_important/runs/${runId}/leads_rejected.csv`,
    row_counts: {
      input_rows: 19271,
      cleaned_rows: 15342,
      rejected_rows: 3929,
      keep_rows: 11221,
      triage_reject_rows: 4121,
      quarantine_rows: 0,
      dispatch_eligible_row_count: 15342,
    },
  };
  const funnelStage = (rowCount) => ({ status: "ready", row_count: rowCount });
  return {
    ...leadsStatus({ checkState: "success", freshSource, recontactSource }),
    lead_check_status: {
      ...leadCheck("success"),
      message: "Cleaned and rejected output files exist for the current upload.",
      cleaned_rows: 15342,
      rejected_rows: 3929,
      outputs_exist: true,
      latest_master_check_matches_current_run: true,
    },
    lead_ops_progress: progress,
    lead_ops_progress_by_workflow: { cold: progress, warm_research: {} },
    dispatch_source_mode: "cleaned",
    dispatch_source: recontactSource,
    dispatch_source_options: {
      triaged_keep: freshSource,
      cleaned: recontactSource,
    },
    latest_master_check: {
      job_id: runId,
      run_id: runId,
      upload_type: "cold",
      input_rows: 19271,
      cleaned_rows: 15342,
      rejected_rows: 3929,
      generated_at_utc: "2026-08-31T22:45:00Z",
    },
    latest_lead_triage: {
      run_id: runId,
      keep_count: 11221,
      reject_count: 4121,
      quarantine_count: 0,
      generated_at_utc: "2026-08-31T22:50:00Z",
    },
    latest_auto_dispatch_preview: {},
    latest_auto_dispatch_preview_current: false,
    pipeline: {
      input_rows: 19271,
      cleaned_rows: 15342,
      rejected_rows: 3929,
      dispatch_eligible_rows: 15342,
    },
    lead_funnel: {
      current_live: {},
      next_batch: {
        run_id: runId,
        raw_input: funnelStage(19271),
        cleaned_after_check: funnelStage(15342),
        check_rejected: funnelStage(3929),
        triage_keep: funnelStage(11221),
        triage_reject: funnelStage(4121),
        triage_quarantine: funnelStage(0),
        final_eligible: funnelStage(15342),
      },
    },
  };
}

function currentRecontactPreview(status, overrides = {}) {
  return {
    preview_id: "dispatch_preview_20260902_004950_8c591597",
    status: "previewed",
    campaign_type: "recontact_cold",
    dispatch_source_mode: "cleaned",
    dispatch_source_kind: "cleaned",
    dispatch_source_path: status.dispatch_source_options.cleaned.dispatch_source_path,
    source_path: status.dispatch_source_options.cleaned.dispatch_source_path,
    source_file_path: status.dispatch_source_options.cleaned.dispatch_source_path,
    dispatch_source_exists: true,
    dispatch_source_row_count: 15342,
    dispatch_eligible_row_count: 15342,
    source_row_count: 15342,
    selected_rows: 15342,
    total_source_rows: 15342,
    total_planned_unique_count: 15341,
    total_rows_would_write: 15341,
    verification_required: false,
    verification_file_mtime: "",
    dispatch_cap: "all",
    queue_safety: { safe: true },
    updated_at_utc: "2026-09-02T00:49:51+00:00",
    ...overrides,
  };
}

function snapshot(active = false) {
  return {
    generated_at: "2026-08-28T00:00:00Z",
    profiles: active ? [{ name: "private_jc", runtime_state: "running", pending_count: 1 }] : [],
    summary: { total_pending: active ? 1 : 0 },
    controls: { send_target_total: 5000 },
    automation: {},
    alerts: [],
    queue_safety: { safe: true },
    private_queue_safety: { safe: true },
    sendgrid_queue_safety: { safe: true },
    domain_breakdown: [],
    campaign_run_history: [],
    latest_failures: [],
    private_bounce_guard: {},
  };
}

function jsonResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(data),
  };
}

function installDashboardDocument() {
  const parsed = new DOMParser().parseFromString(INDEX_HTML, "text/html");
  document.head.innerHTML = parsed.head.innerHTML;
  document.body.innerHTML = parsed.body.innerHTML;
}

async function flushMicrotasks(turns = 10) {
  for (let index = 0; index < turns; index += 1) await Promise.resolve();
}

async function bootController(status, { activeSender = false, previewHandler = null } = {}) {
  installDashboardDocument();
  window.history.replaceState({}, "", activeSender ? "/?tab=ops" : "/?tab=leads&workflow=cold");
  const fetchMock = vi.fn((url, options = {}) => {
    const requestPath = String(url);
    if (requestPath === "/api/auth/status") {
      return Promise.resolve(jsonResponse({
        ok: true,
        authenticated: true,
        auth_enabled: false,
        auth_disabled: true,
        dashboard_mode: "local_dev",
      }));
    }
    if (requestPath.startsWith("/api/snapshot")) return Promise.resolve(jsonResponse(snapshot(activeSender)));
    if (requestPath === "/api/leads/status") return Promise.resolve(jsonResponse({ ok: true, status }));
    if (requestPath === "/api/leads/dispatch-important/preview") {
      return previewHandler
        ? previewHandler(requestPath, options)
        : Promise.resolve(jsonResponse({ ok: false, blocked: true, message: "Synthetic preview stop." }, 409));
    }
    return Promise.resolve(jsonResponse({ ok: true }));
  });
  vi.stubGlobal("fetch", fetchMock);
  const root = createRoot(document.getElementById("dashboard-root"));
  await act(async () => {
    root.render(<DashboardApp />);
    await flushMicrotasks();
  });
  vi.resetModules();
  await act(async () => {
    await import("../app.js");
    await flushMicrotasks();
  });
  if (activeSender) {
    await act(async () => {
      fireEvent.click(document.getElementById("leads-tab-btn"));
      await flushMicrotasks();
    });
  }
  return { root, fetchMock };
}

function previewButton() {
  return document.getElementById("leads-important-dispatch-preview-btn");
}

function confirmButton() {
  return document.getElementById("leads-important-dispatch-confirm-btn");
}

function selectCampaign(mode) {
  fireEvent.click(document.querySelector(`[data-dispatch-mode-card="${mode}"]`));
}

function previewPosts(fetchMock) {
  return fetchMock.mock.calls.filter(([url, options = {}]) => (
    String(url) === "/api/leads/dispatch-important/preview" && options.method === "POST"
  ));
}

function dispatchMutationPosts(fetchMock) {
  return fetchMock.mock.calls.filter(([url, options = {}]) => (
    [
      "/api/leads/dispatch-important/preview",
      "/api/leads/dispatch-important/confirm",
    ].includes(String(url)) && options.method === "POST"
  ));
}

describe("source-scoped Recontact readiness", () => {
  let root;

  afterEach(async () => {
    if (root) await act(async () => root.unmount());
    root = null;
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    document.head.innerHTML = "";
    document.body.innerHTML = "";
  });

  it("keeps failed Fresh blocked while allowing the independent checked Recontact source", async () => {
    const boot = await bootController(leadsStatus());
    root = boot.root;

    expect(document.getElementById("lead-check-status-card")).toHaveTextContent("Failed");
    expect(document.getElementById("lead-check-status-card")).not.toHaveTextContent("Complete");
    expect(document.getElementById("lead-check-status-card")).not.toHaveTextContent("Lead check is still processing");
    expect(previewButton()).toBeDisabled();

    selectCampaign("recontact");

    expect(previewButton()).not.toBeDisabled();
    expect(confirmButton()).toBeDisabled();
    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("15,203 checked rows");
    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("Eligible after mandatory safety: Preview required");
    expect(document.getElementById("leads-workflow-status-banner")).toHaveTextContent("Checked Recontact source is ready for Preview Dispatch");

    fireEvent.click(previewButton());
    await act(async () => flushMicrotasks());

    expect(previewPosts(boot.fetchMock)).toHaveLength(1);
    const [, request] = previewPosts(boot.fetchMock)[0];
    expect(JSON.parse(request.body)).toMatchObject({
      campaign_type: "recontact_cold",
      dispatch_source_mode: "cleaned",
      output_path: RECONTACT_SOURCE.dispatch_source_path,
    });
  });

  it("restores a persisted cleaned Recontact staged run after a process restart", async () => {
    const boot = await bootController(restartedStagedRecontactStatus());
    root = boot.root;

    expect(document.getElementById("lead-check-status-card")).toHaveTextContent("Complete");
    expect(document.getElementById("leads-control-check-result")).toHaveTextContent("Input 19,271");
    expect(document.getElementById("leads-control-check-result")).toHaveTextContent("Cleaned 15,342");
    expect(document.getElementById("leads-control-check-result")).toHaveTextContent("Rejected 3,929");
    expect(document.getElementById("leads-control-check-result")).toHaveTextContent("Keep 11,221");
    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("11,221 source rows");
    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("15,342 checked rows");
    expect(document.getElementById("leads-dispatch-campaign-type")).toHaveValue("recontact_cold");
    expect(document.getElementById("leads-dispatch-source-mode")).toHaveValue("cleaned");
    expect(document.body).toHaveTextContent("Preview required for the selected Checked Recontact source.");
    expect(previewButton()).not.toBeDisabled();
    expect(confirmButton()).toBeDisabled();
    expect(dispatchMutationPosts(boot.fetchMock)).toHaveLength(0);
    const requestedPaths = boot.fetchMock.mock.calls.map(([url]) => String(url));
    expect(requestedPaths.indexOf("/api/leads/status")).toBeGreaterThanOrEqual(0);
    expect(requestedPaths.indexOf("/api/leads/check-important/active")).toBeGreaterThan(
      requestedPaths.indexOf("/api/leads/status"),
    );
  });

  it("allows Recontact preview while a Fresh check status is processing, without making Fresh ready", async () => {
    const boot = await bootController(leadsStatus({ checkState: "processing" }));
    root = boot.root;

    expect(document.getElementById("lead-check-status-card")).toHaveTextContent("Running");
    expect(previewButton()).toBeDisabled();
    selectCampaign("recontact");
    expect(previewButton()).not.toBeDisabled();
    expect(confirmButton()).toBeDisabled();
  });

  it("keeps valid Fresh independent from a missing or inconsistent Recontact source", async () => {
    const missingRecontact = {
      ...RECONTACT_SOURCE,
      dispatch_source_exists: false,
      dispatch_source_row_count: 0,
      dispatch_eligible_row_count: 0,
      dispatch_block_reason: "Cleaned dispatch source missing: _important/leads.csv",
    };
    const boot = await bootController(leadsStatus({ checkState: "success", recontactSource: missingRecontact }));
    root = boot.root;

    expect(previewButton()).not.toBeDisabled();
    selectCampaign("recontact");
    expect(previewButton()).toBeDisabled();
    expect(previewButton()).toHaveAttribute("title", expect.stringContaining("missing"));

    selectCampaign("fresh");
    expect(previewButton()).not.toBeDisabled();
  });

  it("keeps Fresh ready while rejecting structurally inconsistent Recontact metadata", async () => {
    const inconsistentRecontact = {
      ...RECONTACT_SOURCE,
      dispatch_source_mode: "triaged_keep",
      dispatch_source_name: "Unexpected source",
    };
    const boot = await bootController(leadsStatus({ checkState: "success", recontactSource: inconsistentRecontact }));
    root = boot.root;

    expect(document.getElementById("lead-check-status-card")).toHaveTextContent("Complete");
    expect(previewButton()).not.toBeDisabled();
    selectCampaign("recontact");
    expect(previewButton()).toBeDisabled();
    expect(previewButton()).toHaveAttribute("title", expect.stringContaining("metadata"));
  });

  it("shows a calculated Recontact eligible count only for a current matching preview", async () => {
    const preview = {
      preview_id: "recontact-preview",
      campaign_type: "recontact_cold",
      dispatch_source_mode: "cleaned",
      dispatch_source_path: RECONTACT_SOURCE.dispatch_source_path,
      dispatch_source_exists: true,
      dispatch_source_row_count: 15203,
      dispatch_eligible_row_count: 15203,
      verification_file_mtime: "",
      dispatch_cap: "all",
      total_planned_unique_count: 321,
      total_rows_would_write: 321,
      queue_safety: { safe: true },
    };
    const boot = await bootController(leadsStatus({ checkState: "success", preview, previewCurrent: true }));
    root = boot.root;

    selectCampaign("recontact");
    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("Eligible after mandatory safety: 321");

    selectCampaign("fresh");
    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("Eligible after mandatory safety: Preview required");
    selectCampaign("recontact");
    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("Eligible after mandatory safety: 321");
  });

  it("blocks both source modes when an actual sender is active", async () => {
    const boot = await bootController(leadsStatus({ checkState: "success" }), { activeSender: true });
    root = boot.root;

    expect(previewButton()).toBeDisabled();
    expect(previewButton()).toHaveAttribute("title", expect.stringContaining("Active senders are running"));
    selectCampaign("recontact");
    expect(previewButton()).toBeDisabled();
    expect(previewButton()).toHaveAttribute("title", expect.stringContaining("Active senders are running"));
  });

  it("blocks both source modes while a conflicting dispatch operation is active", async () => {
    const activeDispatch = {
      job_id: "dispatch-job",
      status: "running",
      phase: "previewing",
      campaign_type: "cold",
      dispatch_source_mode: "triaged_keep",
    };
    const boot = await bootController(leadsStatus({ checkState: "success", activeDispatch }));
    root = boot.root;

    expect(previewButton()).toBeDisabled();
    selectCampaign("recontact");
    expect(previewButton()).toBeDisabled();
  });

  it("restores a restarted cleaned Recontact source when its persisted Preview is already current", async () => {
    const status = restartedStagedRecontactStatus();
    const preview = currentRecontactPreview(status);

    status.latest_auto_dispatch_preview = preview;
    status.latest_auto_dispatch_preview_current = true;

    const boot = await bootController(status);
    root = boot.root;

    expect(
      document.getElementById("lead-check-status-card"),
    ).toHaveTextContent("Complete");

    expect(
      document.getElementById("leads-control-check-result"),
    ).toHaveTextContent("Input 19,271");

    expect(
      document.getElementById("leads-control-check-result"),
    ).toHaveTextContent("Cleaned 15,342");

    expect(
      document.getElementById("leads-control-check-result"),
    ).toHaveTextContent("Rejected 3,929");

    expect(
      document.getElementById("leads-control-check-result"),
    ).toHaveTextContent("Keep 11,221");

    expect(
      document.getElementById("leads-dispatch-mode-cards"),
    ).toHaveTextContent("11,221 source rows");

    expect(
      document.getElementById("leads-dispatch-mode-cards"),
    ).toHaveTextContent("15,342 checked rows");

    expect(
      document.getElementById(
        "leads-dispatch-campaign-type",
      ),
    ).toHaveValue("recontact_cold");

    expect(
      document.getElementById(
        "leads-dispatch-source-mode",
      ),
    ).toHaveValue("cleaned");

    expect(document.body).toHaveTextContent(
      "Eligible after mandatory safety: 15,341",
    );

    expect(dispatchMutationPosts(boot.fetchMock)).toHaveLength(0);
  });

  it.each([
    ["server marks the Preview stale", {}, false],
    ["source path differs", { dispatch_source_path: "/synthetic/other/leads.csv" }, true],
    ["source row count differs", { dispatch_source_row_count: 15341 }, true],
    ["campaign differs", { campaign_type: "cold" }, true],
    ["source mode differs", { dispatch_source_mode: "triaged_keep" }, true],
    ["dispatch cap differs", { dispatch_cap: "100" }, true],
  ])("rejects a persisted Preview when %s", async (_label, previewOverrides, backendCurrent) => {
    const status = restartedStagedRecontactStatus();
    status.latest_auto_dispatch_preview = currentRecontactPreview(status, previewOverrides);
    status.latest_auto_dispatch_preview_current = backendCurrent;

    const boot = await bootController(status);
    root = boot.root;

    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("15,342 checked rows");
    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("Eligible after mandatory safety: Preview required");
    expect(confirmButton()).toBeDisabled();
    expect(dispatchMutationPosts(boot.fetchMock)).toHaveLength(0);
  });

  it("fails closed when a required verification fingerprint differs", async () => {
    const status = restartedStagedRecontactStatus();
    status.dispatch_source.verification_required = true;
    status.dispatch_source_options.cleaned.verification_required = true;
    status.latest_auto_dispatch_preview = currentRecontactPreview(status, {
      verification_required: true,
      verification_file_mtime: "2026-08-31T22:30:00+00:00",
    });
    status.latest_auto_dispatch_preview_current = true;

    const boot = await bootController(status);
    root = boot.root;

    expect(document.getElementById("leads-dispatch-mode-cards")).toHaveTextContent("Eligible after mandatory safety: Preview required");
    expect(confirmButton()).toBeDisabled();
    expect(dispatchMutationPosts(boot.fetchMock)).toHaveLength(0);
  });

});
