import React from "react";
import fs from "node:fs";
import path from "node:path";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardApp } from "./main.jsx";

const template = {
  sidebar: {
    brand: '<div class="app-rail-top">Email Automation</div>',
    navigation: `<div class="app-rail-tabs">
      <button id="overview-tab-btn" aria-controls="overview-view">Overview</button>
      <button id="campaigns-tab-btn" aria-controls="leads-view">Campaigns</button>
      <button id="senders-tab-btn" aria-controls="senders-view">Senders</button>
      <button id="history-tab-btn" aria-controls="history-view">History</button>
      <button id="diagnostics-tab-btn" aria-controls="diagnostics-view">Diagnostics</button>
    </div>`,
    status: '<div class="app-rail-status"><span id="auth-status-label">Local dev</span></div>',
  },
  senders: {
    commandBar: '<section class="workspace-status-row"><button id="start-ready-btn">Start Ready Senders</button><button id="stop-btn">Stop All</button><button id="refresh-btn">Refresh</button></section>',
    metrics: '<section class="queue-health-section"><div id="summary-grid"></div></section>',
    progress: '<section class="ops-progress-strip"><span id="ops-progress-summary"></span></section>',
    progressDetails: '<details id="ops-progress-details"></details>',
    controlledTest: '<section class="controlled-send-test-card"><button id="controlled-send-test-btn">Controlled test</button></section><section class="controlled-send-test-card"><button id="controlled-send-test-jc-btn">JC controlled test</button></section><section class="controlled-send-test-card"><button id="controlled-send-test-all-btn">All sender controlled test</button></section>',
    profileDetail: '<section class="workspace-primary"><div id="profile-detail"></div></section>',
    history: '<details class="campaign-history-panel"><div id="campaign-run-history"></div></details>',
  },
  leadOps: {
    heading: '<div class="panel-header"><h2 id="leads-command-heading">Prepare Dispatch</h2></div>',
    source: '<section class="leads-control-bar"><input id="leads-important-upload-type" type="hidden" value="cold" /><input id="leads-important-upload-file" type="file" /><span id="leads-important-upload-note"></span><button id="leads-important-upload-check-btn">Upload &amp; Check</button></section>',
    workflowStatus: '<div id="leads-workflow-status-banner" class="leads-workflow-status-banner"></div>',
    workflowSteps: '<div id="leads-workflow-task-list" class="leads-workflow-task-list"></div>',
    commandLeft: '<div class="leads-command-column-left"><div id="leads-current-run-panel"></div><select data-fresh-cold-route></select><select data-recontact-route></select></div>',
    commandRight: '<div id="leads-dispatch-command-column" class="leads-command-column-right"><button id="leads-important-dispatch-preview-btn">Preview Dispatch</button><button id="leads-important-dispatch-confirm-btn">Confirm Dispatch</button></div>',
    diagnostics: '<details class="leads-advanced-diagnostics"></details>',
  },
  auth: '<div id="auth-overlay" hidden></div>',
};

describe("DashboardApp", () => {
  afterEach(() => cleanup());

  it("mounts sender and Lead Ops controller contracts", () => {
    render(<DashboardApp template={template} />);
    expect(screen.queryByText("Start All")).not.toBeInTheDocument();
    expect(screen.getByText("Refresh")).toBeInTheDocument();
    expect(screen.getByText("Checking dashboard mode...")).toBeInTheDocument();
    expect(screen.getByText("Manual Start/Resume can launch real workers and consume queues.")).toBeInTheDocument();
    expect(document.querySelector('[aria-label="Fleet operations summary"] #summary-grid')).toBeInTheDocument();
    expect(document.getElementById("leads-important-dispatch-preview-btn")).toBeInTheDocument();
    expect(document.querySelector('[data-leads-workflow="cold"]')).toHaveAttribute("href", "/?tab=campaigns&workflow=cold");
    expect(document.querySelector('[data-leads-workflow="warm"]')).toHaveAttribute("href", "/?tab=campaigns&workflow=warm");
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

  it("shows canonical dashboard destinations", () => {
    render(<DashboardApp template={template} />);
    const navigation = document.querySelector(".react-sidebar-nav");
    const labels = ["Overview", "Campaigns", "Senders", "History", "Diagnostics"];
    expect(Array.from(navigation.querySelectorAll("button"), (button) => button.textContent.trim())).toEqual(labels);
    for (const label of labels) {
      expect(screen.getAllByText(label, { selector: ".react-sidebar-nav button" })).toHaveLength(1);
    }
    expect(document.getElementById("overview-tab-btn")).toHaveAttribute("aria-controls", "overview-view");
    expect(document.getElementById("campaigns-tab-btn")).toHaveAttribute("aria-controls", "leads-view");
    expect(document.getElementById("senders-tab-btn")).toHaveAttribute("aria-controls", "senders-view");
    expect(document.getElementById("history-tab-btn")).toHaveAttribute("aria-controls", "history-view");
    expect(document.getElementById("diagnostics-tab-btn")).toHaveAttribute("aria-controls", "diagnostics-view");
    expect(document.getElementById("overview-view")).toBeInTheDocument();
    expect(document.getElementById("leads-view")).toBeInTheDocument();
    expect(document.getElementById("senders-view")).toBeInTheDocument();
    expect(document.getElementById("history-view")).toBeInTheDocument();
    expect(document.getElementById("diagnostics-view")).toBeInTheDocument();
    for (const label of ["Leads", "Sending", "Suppressions", "Recovery", "Activity", "Settings", "Replies"]) {
      expect(screen.queryByText(label, { selector: ".react-sidebar-nav button" })).not.toBeInTheDocument();
    }
  });

  it("separates overview, sender, history, and diagnostics regions without duplicate IDs", () => {
    render(<DashboardApp template={template} />);
    const overview = document.getElementById("overview-view");
    const senders = document.getElementById("senders-view");
    const diagnostics = document.getElementById("diagnostics-view");
    const history = document.getElementById("history-view");
    expect(document.getElementById("ops-view")).not.toBeInTheDocument();
    expect(overview).toHaveTextContent("Overview");
    expect(overview.querySelector('[aria-label="Fleet operations summary"] #summary-grid')).toBeInTheDocument();
    expect(overview.querySelector("#start-ready-btn")).toBeInTheDocument();
    expect(overview.querySelector("#stop-btn")).toBeInTheDocument();
    expect(senders).toHaveTextContent("Senders");
    expect(senders.querySelector("#summary-grid")).not.toBeInTheDocument();
    expect(senders.querySelector("#start-ready-btn")).not.toBeInTheDocument();
    expect(senders.querySelector(".sender-status-mount")).toBeInTheDocument();
    expect(senders.querySelector("#profile-detail")).toBeInTheDocument();
    expect(history.querySelector("#campaign-run-history")).toBeInTheDocument();
    const validationTools = diagnostics.querySelector("details.react-validation-tools");
    expect(validationTools).not.toHaveAttribute("open");
    expect(validationTools).toHaveTextContent("Validation Tools");
    expect(validationTools).toHaveTextContent("no production recipient queues");
    expect(validationTools.querySelectorAll(".controlled-send-test-card")).toHaveLength(3);
    expect(diagnostics.querySelector("#ops-progress-details")).toBeInTheDocument();
    for (const id of [
      "start-ready-btn",
      "stop-btn",
      "leads-important-dispatch-preview-btn",
      "leads-important-dispatch-confirm-btn",
      "leads-important-upload-type",
      "leads-important-upload-file",
      "leads-important-upload-note",
      "leads-important-upload-check-btn",
    ]) {
      expect(document.querySelectorAll(`#${id}`)).toHaveLength(1);
    }
    expect(document.querySelectorAll("[data-fresh-cold-route]")).toHaveLength(1);
    expect(document.querySelectorAll("[data-recontact-route]")).toHaveLength(1);
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

  async function boot({ checked = false, drafts = 0, historical = false, running = false, previewPolicyCurrent = Boolean(drafts) } = {}) {
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
        warm_copy_policy_version_required: "warm_diagnosis_gate_v1",
        warm_email_preview_policy_version: previewPolicyCurrent && drafts ? "warm_diagnosis_gate_v1" : "legacy",
        warm_preview_policy_current: Boolean(previewPolicyCurrent && drafts),
      } : {},
      lead_ops_progress_by_workflow: { warm_research: checked ? {
        job_id: "fixture-check", selected_upload_type: "warm_research", phase: "ready_for_preview",
        input_exists: true, job_record_exists: true, output_exists: true, rejected_exists: true,
        latest_master_check_matches_current_run: true,
      } : {} },
      warm_private_jc_status: historical || running ? {
        confirmed: true, queued_remaining_count: 9, sent_count: 50, running,
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
    expect(document.querySelector(".react-lead-workspace")).not.toBeVisible();
    expect(document.querySelector(".leads-control-bar")).toContainElement(panel);
    for (const selector of ['[data-warm-review-action="load"]', '[data-leads-next-action="generate_warm_preview"]', '[data-leads-next-action="confirm_warm_private_jc"]', '[data-leads-next-action="start_warm_private_jc"]']) {
      expect(panel.querySelector(selector)).toBeDisabled();
    }
    expect(fetchMock.mock.calls.every(([, options = {}]) => !options.method || options.method === "GET")).toBe(true);
  });

  it.each([0, 7])("preserves checked review/preview and draft-count=%s confirmation gates", async (drafts) => {
    const fetchMock = await boot({ checked: true, drafts });
    const panel = document.getElementById("leads-current-run-panel");
    expect(panel).toHaveTextContent("Ready for review");
    expect(document.querySelector(".react-lead-workspace")).toBeVisible();
    expect(document.getElementById("leads-control-check-result")).toHaveTextContent("Email ready 7");
    expect(panel.querySelector(".warm-locked-stages")).toBeNull();
    expect(panel.querySelector('[data-warm-review-action="load"]')).toBeEnabled();
    expect(panel.querySelector('[data-leads-next-action="generate_warm_preview"]')).toBeEnabled();
    const confirm = panel.querySelector('[data-leads-next-action="confirm_warm_private_jc"]');
    if (drafts) expect(confirm).toBeEnabled(); else expect(confirm).toBeDisabled();
    expect(panel.querySelector('[data-leads-next-action="start_warm_private_jc"]')).toBeDisabled();
    expect(fetchMock.mock.calls.every(([, options = {}]) => !options.method || options.method === "GET")).toBe(true);
  });

  it("keeps legacy warm preview visibly stale and confirmation disabled", async () => {
    const fetchMock = await boot({ checked: true, drafts: 7, previewPolicyCurrent: false });
    const panel = document.getElementById("leads-current-run-panel");
    expect(panel).toHaveTextContent("Preview policy stale");
    expect(panel.querySelector('[data-leads-next-action="confirm_warm_private_jc"]')).toBeDisabled();
    expect(fetchMock.mock.calls.every(([, options = {}]) => !options.method || options.method === "GET")).toBe(true);
  });

  it("keeps Stop accessible for a running sender with an unchecked upload", async () => {
    const fetchMock = await boot({ running: true });
    const panel = document.getElementById("leads-current-run-panel");
    const stop = panel.querySelector('[data-leads-next-action="stop_warm_private_jc"]');
    expect(stop).toBeVisible();
    expect(stop).toBeEnabled();
    expect(stop).toHaveTextContent("Stop Warm Private JC");
    expect(panel.querySelector(".warm-live-summary")).toBeVisible();
    expect(panel.querySelector(".warm-live-summary")).toHaveClass("warm-live-summary-running");
    expect(panel.querySelector(".warm-live-summary")).toHaveTextContent("Running Yes");
    expect(document.querySelector(".react-lead-workspace")).not.toBeVisible();
    for (const selector of ['[data-warm-review-action="load"]', '[data-leads-next-action="generate_warm_preview"]', '[data-leads-next-action="confirm_warm_private_jc"]']) {
      expect(panel.querySelector(selector)).toBeDisabled();
    }
    expect(panel.querySelector('[data-leads-next-action="start_warm_private_jc"]')).toBeNull();
    expect(fetchMock.mock.calls.every(([, options = {}]) => !options.method || options.method === "GET")).toBe(true);
  });

  it("keeps Leads and Senders navigation while resolving legacy ops links to Senders", async () => {
    const fetchMock = await boot();
    const expectedLabels = ["Overview", "Campaigns", "Senders", "History", "Diagnostics"];
    expect(Array.from(document.querySelectorAll(".react-sidebar-nav button"), (button) => button.textContent.trim())).toEqual(expectedLabels);

    fireEvent.click(document.getElementById("senders-tab-btn"));
    await act(async () => { for (let i = 0; i < 5; i += 1) await Promise.resolve(); });
    expect(window.location.search).toContain("tab=senders");
    expect(document.getElementById("senders-view")).toBeInTheDocument();
    expect(document.getElementById("leads-view")).toHaveAttribute("hidden");

    fireEvent.click(document.getElementById("campaigns-tab-btn"));
    await act(async () => { for (let i = 0; i < 5; i += 1) await Promise.resolve(); });
    expect(window.location.search).toContain("tab=campaigns");
    expect(document.getElementById("leads-view")).toBeInTheDocument();
    expect(document.getElementById("senders-view")).toHaveAttribute("hidden");

    fireEvent.click(document.getElementById("senders-tab-btn"));
    await act(async () => { for (let i = 0; i < 5; i += 1) await Promise.resolve(); });
    expect(window.location.search).toContain("tab=senders");
    const senders = document.getElementById("senders-view");
    expect(senders).toBeInTheDocument();
    expect(document.getElementById("leads-view")).toHaveAttribute("hidden");
    expect(document.querySelectorAll("#senders-table-panel")).toHaveLength(1);
    expect(senders.querySelector("#senders-table-panel")).toBeInTheDocument();
    expect(document.querySelectorAll("#start-ready-btn")).toHaveLength(1);
    expect(document.querySelectorAll("#stop-btn")).toHaveLength(1);
    expect(Array.from(senders.querySelectorAll(".controlled-send-test-card"))).toHaveLength(0);

    fireEvent.click(document.getElementById("diagnostics-tab-btn"));
    await act(async () => { for (let i = 0; i < 5; i += 1) await Promise.resolve(); });
    expect(window.location.search).toContain("tab=diagnostics");
    expect(document.querySelectorAll("#controlled-send-test-btn")).toHaveLength(1);
    expect(document.querySelectorAll("#controlled-send-test-jc-btn")).toHaveLength(1);
    expect(document.querySelectorAll("#controlled-send-test-all-btn")).toHaveLength(1);

    fireEvent.click(document.getElementById("overview-tab-btn"));
    await act(async () => { for (let i = 0; i < 5; i += 1) await Promise.resolve(); });
    expect(window.location.search).toContain("tab=overview");
    expect(document.querySelectorAll("#start-ready-btn")).toHaveLength(1);
    expect(document.querySelectorAll("#stop-btn")).toHaveLength(1);

    window.history.replaceState({}, "", "/?tab=ops");
    window.dispatchEvent(new PopStateEvent("popstate"));
    await act(async () => { for (let i = 0; i < 5; i += 1) await Promise.resolve(); });
    expect(document.getElementById("senders-view")).toBeInTheDocument();
    expect(document.getElementById("ops-view")).not.toBeInTheDocument();

    window.history.replaceState({}, "", "/?tab=leads&workflow=warm");
    window.dispatchEvent(new PopStateEvent("popstate"));
    await act(async () => { for (let i = 0; i < 5; i += 1) await Promise.resolve(); });
    expect(window.location.search).toContain("tab=leads");
    expect(document.getElementById("leads-view")).toBeInTheDocument();
    expect(document.getElementById("senders-view")).toHaveAttribute("hidden");
    expect(fetchMock.mock.calls.every(([, options = {}]) => !options.method || options.method === "GET")).toBe(true);
  });
});
