import React from "react";
import fs from "node:fs";
import path from "node:path";
import { act, cleanup, render, screen } from "@testing-library/react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardApp } from "./main.jsx";

const template = {
  sidebar: {
    brand: '<div class="app-rail-top">Email Automation</div>',
    navigation: '<div class="app-rail-tabs"><button id="ops-tab-btn">Senders</button><button id="leads-tab-btn">Lead Ops</button></div>',
    status: '<div class="app-rail-status"><span id="auth-status-label">Local dev</span></div>',
  },
  senders: {
    commandBar: '<section class="workspace-status-row"><button id="refresh-btn">Refresh</button></section>',
    metrics: '<section class="queue-health-section"><div id="summary-grid"></div></section>',
    progress: '<section class="ops-progress-strip"><span id="ops-progress-summary"></span></section>',
    progressDetails: '<details id="ops-progress-details"></details>',
    profileDetail: '<section class="workspace-primary"><div id="profile-detail"></div></section>',
    history: '<details class="campaign-history-panel"><div id="campaign-run-history"></div></details>',
  },
  leadOps: {
    heading: '<div class="panel-header"><h2 id="leads-command-heading">Prepare Dispatch</h2></div>',
    source: '<section class="leads-control-bar"><input id="leads-important-upload-type" type="hidden" value="cold" /></section>',
    workflowStatus: '<div id="leads-workflow-status-banner" class="leads-workflow-status-banner"></div>',
    workflowSteps: '<div id="leads-workflow-task-list" class="leads-workflow-task-list"></div>',
    commandLeft: '<div class="leads-command-column-left"><div id="leads-current-run-panel"></div></div>',
    commandRight: '<div id="leads-dispatch-command-column" class="leads-command-column-right"><button id="leads-important-dispatch-preview-btn">Preview Dispatch</button></div>',
    diagnostics: '<details class="leads-advanced-diagnostics"></details>',
  },
  auth: '<div id="auth-overlay" hidden></div>',
};

describe("DashboardApp", () => {
  it("mounts sender and Lead Ops controller contracts", () => {
    render(<DashboardApp template={template} />);
    expect(screen.queryByText("Start All")).not.toBeInTheDocument();
    expect(screen.getByText("Refresh")).toBeInTheDocument();
    expect(screen.getByText("Checking dashboard mode...")).toBeInTheDocument();
    expect(screen.getByText("Manual Start/Resume can launch real workers and consume queues.")).toBeInTheDocument();
    expect(screen.getByText("Current run")).toBeInTheDocument();
    expect(screen.getByText("Queue and delivery state")).toBeInTheDocument();
    expect(document.getElementById("leads-important-dispatch-preview-btn")).toBeInTheDocument();
    expect(document.querySelector('[data-leads-workflow="cold"]')).toHaveAttribute("href", "/?tab=leads&workflow=cold");
    expect(document.querySelector('[data-leads-workflow="warm"]')).toHaveAttribute("href", "/?tab=leads&workflow=warm");
    expect(screen.getAllByText("Warm Outreach").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Upload Batch").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Validate").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Review").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Preview Email").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Confirm").length).toBeGreaterThan(0);
    expect(document.querySelector('select#leads-important-upload-type')).not.toBeInTheDocument();
    expect(document.getElementById("auth-overlay")).toBeInTheDocument();
    expect(document.querySelector('[data-dashboard-ui="react-tailwind-components"]')).toBeInTheDocument();
  });
});

describe("Warm Outreach controller layout", () => {
  let root;

  afterEach(async () => {
    if (root) await act(async () => root.unmount());
    root = null;
    cleanup();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    document.head.innerHTML = "";
    document.body.innerHTML = "";
  });

  async function boot({ checked = false, drafts = 0, historical = false } = {}) {
    vi.useFakeTimers();
    const html = fs.readFileSync(path.resolve(process.cwd(), "web_dashboard/index.html"), "utf8");
    const parsed = new DOMParser().parseFromString(html, "text/html");
    document.head.innerHTML = parsed.head.innerHTML;
    document.body.innerHTML = parsed.body.innerHTML;
    window.history.replaceState({}, "", "/?tab=leads&workflow=warm");
    const status = {
      current_warm_check_job_id: checked ? "fixture-check" : "",
      current_warm_check: checked ? {
        upload_type: "warm_research", current_upload_valid: true,
        current_job_id: "fixture-check", generated_at_utc: "2026-09-01T00:00:00Z",
        warm_email_ready_rows: 7, warm_email_preview_rows: drafts,
      } : {},
      lead_ops_progress_by_workflow: { warm_research: checked ? {
        job_id: "fixture-check", selected_upload_type: "warm_research", phase: "ready_for_preview",
        input_exists: true, job_record_exists: true, output_exists: true, rejected_exists: true,
        latest_master_check_matches_current_run: true,
      } : {} },
      warm_private_jc_status: historical ? {
        confirmed: true, queued_remaining_count: 9, sent_count: 50, running: false,
      } : {},
    };
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (options.method && options.method !== "GET") throw new Error("Unexpected mutation");
      let payload = { ok: true };
      if (String(url) === "/api/auth/status") payload = { ok: true, authenticated: true, auth_disabled: true, dashboard_mode: "local_dev" };
      if (String(url).startsWith("/api/snapshot")) payload = {
        profiles: [], summary: {}, controls: {}, automation: {}, alerts: [],
        queue_safety: { safe: true }, domain_breakdown: [], campaign_run_history: [], latest_failures: [],
      };
      if (String(url) === "/api/leads/status") payload = { ok: true, status };
      return { ok: true, status: 200, json: async () => payload };
    });
    vi.stubGlobal("fetch", fetchMock);
    root = createRoot(document.getElementById("dashboard-root"));
    await act(async () => { root.render(<DashboardApp />); });
    vi.resetModules();
    await act(async () => {
      await import("../app.js");
      for (let i = 0; i < 15; i += 1) await Promise.resolve();
    });
    return fetchMock;
  }

  it.each([false, true])("consolidates unchecked state without letting history=%s unlock actions", async (historical) => {
    const fetchMock = await boot({ historical });
    expect(document.getElementById("leads-command-heading")).toHaveTextContent("Warm Outreach");
    const panel = document.getElementById("leads-current-run-panel");
    expect(panel).toHaveTextContent("No warm batch loaded");
    expect(panel).toHaveTextContent("Upload a CSV or XLSX to begin validation");
    expect(panel).toHaveTextContent("Upload & Check");
    for (const label of ["Upload Batch", "Validate", "Review", "Preview Email", "Confirm"]) {
      expect(document.querySelector(".react-warm-copy")?.closest("#leads-view") || document.body).toHaveTextContent(label);
    }
    expect(panel.querySelector(".warm-locked-stages")).toHaveTextContent("Waiting for upload");
    for (const label of ["Locked until validation", "Locked until review", "Locked until preview"]) expect(panel).toHaveTextContent(label);
    expect(panel.querySelector(".warm-review-panel")).not.toBeVisible();
    expect(panel.querySelector(".warm-private-action-panel")).not.toBeVisible();
    expect(panel.querySelector(".warm-operations-details")).not.toHaveAttribute("open");
    for (const selector of ['[data-warm-review-action="load"]', '[data-leads-next-action="generate_warm_preview"]', '[data-leads-next-action="confirm_warm_private_jc"]', '[data-leads-next-action="start_warm_private_jc"]']) {
      expect(panel.querySelector(selector)).toBeDisabled();
    }
    expect(fetchMock.mock.calls.every(([, options = {}]) => !options.method || options.method === "GET")).toBe(true);
  });

  it.each([0, 7])("preserves checked review/preview and draft-count=%s confirmation gates", async (drafts) => {
    const fetchMock = await boot({ checked: true, drafts });
    const panel = document.getElementById("leads-current-run-panel");
    expect(panel).toHaveTextContent("Ready for review");
    expect(document.getElementById("leads-control-check-result")).toHaveTextContent("Email ready 7");
    expect(panel.querySelector(".warm-locked-stages")).toBeNull();
    expect(panel.querySelector('[data-warm-review-action="load"]')).toBeEnabled();
    expect(panel.querySelector('[data-leads-next-action="generate_warm_preview"]')).toBeEnabled();
    const confirm = panel.querySelector('[data-leads-next-action="confirm_warm_private_jc"]');
    if (drafts) expect(confirm).toBeEnabled(); else expect(confirm).toBeDisabled();
    expect(panel.querySelector('[data-leads-next-action="start_warm_private_jc"]')).toBeDisabled();
    expect(fetchMock.mock.calls.every(([, options = {}]) => !options.method || options.method === "GET")).toBe(true);
  });
});
