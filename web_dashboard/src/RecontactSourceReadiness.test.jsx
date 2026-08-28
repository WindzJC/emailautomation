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
    const boot = await bootController(leadsStatus({ checkState: "success", preview }));
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
});
