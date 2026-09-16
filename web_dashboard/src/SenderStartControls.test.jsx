import fs from "node:fs";
import path from "node:path";

import React from "react";
import { act, cleanup, fireEvent } from "@testing-library/react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardApp, SenderStartControls } from "./main.jsx";

const INDEX_HTML = fs.readFileSync(
  path.resolve(process.cwd(), "web_dashboard/index.html"),
  "utf8",
);

const READY_SNAPSHOT = {
  generated_at: "2026-08-13T00:00:00Z",
  display_timezone: "UTC",
  activity_hours: 24,
  profiles: [
    {
      name: "private_jc",
      pending_count: 1,
      runtime_state: "stopped",
      runtime_label: "Stopped",
      max_total: 100,
      configured_max_total: 100,
      message_readiness_status: "PASS",
    },
  ],
  summary: { total_pending: 1 },
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

function jsonResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(data),
  };
}

function deferredResponse() {
  let resolve;
  const promise = new Promise((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

function installDashboardDocument() {
  const parsed = new DOMParser().parseFromString(INDEX_HTML, "text/html");
  document.head.innerHTML = parsed.head.innerHTML;
  document.body.innerHTML = parsed.body.innerHTML;
}

async function flushMicrotasks(turns = 8) {
  for (let index = 0; index < turns; index += 1) {
    await Promise.resolve();
  }
}

async function bootController(fetchMock, tab = "senders") {
  if (tab === "start-ready") {
    document.body.innerHTML = '<button id="refresh-btn" type="button">Refresh</button><div id="dashboard-root"></div>';
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const rootNode = document.getElementById("dashboard-root");
    const root = createRoot(rootNode);
    await act(async () => {
      root.render(<SenderStartControls />);
      await flushMicrotasks();
    });
    return root;
  }
  installDashboardDocument();
  window.history.replaceState({}, "", `/?tab=${tab}`);
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(window, "confirm").mockReturnValue(true);

  const rootNode = document.getElementById("dashboard-root");
  const root = createRoot(rootNode);
  await act(async () => {
    root.render(<DashboardApp />);
    await flushMicrotasks();
  });

  vi.resetModules();
  await act(async () => {
    await import("../app.js");
    await flushMicrotasks();
  });

  return root;
}

function startCalls(fetchMock) {
  return fetchMock.mock.calls.filter(([url]) => String(url).startsWith("/api/start/"));
}

function baseFetchMock(startHandler, startReadyHandler = null) {
  return vi.fn((url, options = {}) => {
    const pathName = String(url);
    if (pathName === "/api/auth/status") {
      return Promise.resolve(jsonResponse({
        ok: true,
        authenticated: true,
        auth_enabled: false,
        auth_disabled: true,
        dashboard_mode: "local_dev",
        machine_id: "mac",
        authorized_machine: "mac",
        authority_status: "active",
        authority_generation: 1,
        production_authorized: true,
        live_actions_enabled: true,
      }));
    }
    if (pathName.startsWith("/api/snapshot")) {
      return Promise.resolve(jsonResponse(READY_SNAPSHOT));
    }
    if (pathName === "/api/start-ready" || pathName.startsWith("/api/start-ready/status/")) {
      return startReadyHandler
        ? startReadyHandler(pathName, options)
        : Promise.resolve(jsonResponse({ ok: true, ready_profiles: [], skipped_profiles: [] }));
    }
    if (pathName.startsWith("/api/start/")) {
      return startHandler(pathName, options);
    }
    return Promise.resolve(jsonResponse({ ok: true }));
  });
}

function startReadyButton() {
  return document.getElementById("start-ready-btn");
}

function startReadyPosts(fetchMock) {
  return fetchMock.mock.calls.filter(([url, options = {}]) => (
    String(url) === "/api/start-ready" && options.method === "POST"
  ));
}

function senderRowStartButton() {
  return document.querySelector(
    '.sender-status-action-btn[data-profile="private_jc"][data-action="start"]',
  );
}

function profileDetailStartButton() {
  return document.querySelector(
    '#profile-detail .start-profile-btn[data-profile="private_jc"]',
  );
}

describe("individual sender Start controls", () => {
  let root;

  it("disables Start in the UI when the backend reports manual live actions off", async () => {
    const fetchMock = vi.fn((url, options = {}) => {
      const pathName = String(url);
      if (pathName === "/api/auth/status") {
        return Promise.resolve(jsonResponse({
          ok: true,
          authenticated: true,
          auth_enabled: false,
          auth_disabled: true,
          dashboard_mode: "local_dev",
        machine_id: "mac",
        authorized_machine: "mac",
        authority_status: "active",
        authority_generation: 1,
        production_authorized: true,
          auto_start_allowed: false,
          live_actions_enabled: false,
        }));
      }
      if (pathName.startsWith("/api/snapshot")) {
        return Promise.resolve(jsonResponse(READY_SNAPSHOT));
      }
      if (pathName.startsWith("/api/start/")) {
        throw new Error("Start endpoint must not be called while manual actions are disabled");
      }
      return Promise.resolve(jsonResponse({ ok: true }));
    });

    root = await bootController(fetchMock, "ops");

    const startButton = senderRowStartButton();
    expect(startButton).not.toBeNull();
    expect(startButton).toBeDisabled();
    expect(startButton).toHaveTextContent("Manual actions disabled");
    expect(startButton.title).toContain("Automatic startup remains off");
    expect(document.querySelector(".summary-card-next_action .summary-value")).toHaveTextContent("Manual actions disabled");
    expect(startCalls(fetchMock)).toHaveLength(0);
  });


  it("keeps a standby machine read-only even when live actions are enabled", async () => {
    const fetchMock = vi.fn((url, options = {}) => {
      const pathName = String(url);
      if (pathName === "/api/auth/status") {
        return Promise.resolve(jsonResponse({
          ok: true,
          authenticated: true,
          auth_enabled: false,
          auth_disabled: true,
          dashboard_mode: "local_dev",
          auto_start_allowed: false,
          live_actions_enabled: true,
          machine_id: "mac",
          authorized_machine: "windows-wsl",
          authority_status: "active",
          authority_generation: 2,
          production_authorized: false,
        }));
      }
      if (pathName.startsWith("/api/snapshot")) {
        return Promise.resolve(jsonResponse(READY_SNAPSHOT));
      }
      if (pathName.startsWith("/api/start/")) {
        throw new Error("Start endpoint must not be called from a standby host");
      }
      return Promise.resolve(jsonResponse({ ok: true }));
    });

    root = await bootController(fetchMock, "ops");

    const startButton = senderRowStartButton();
    expect(startButton).not.toBeNull();
    expect(startButton).toBeDisabled();
    expect(startButton).toHaveTextContent("Machine not authorized");
    expect(startButton.title).toContain("WINDOWS / WSL holds runtime authority");
    expect(document.querySelector(".summary-card-next_action .summary-value")).toHaveTextContent("Standby host");
    expect(startCalls(fetchMock)).toHaveLength(0);
  });

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(async () => {
    if (root) {
      await act(async () => root.unmount());
      root = null;
    }
    cleanup();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    document.head.innerHTML = "";
    document.body.innerHTML = "";
  });

  it.each([
    { event_stale: true, awaiting_outcome: 0, state: "healthy", warning: false, feed: "STALE" },
    { event_stale: true, awaiting_outcome: 3, state: "stale", warning: true, feed: "STALE" },
    { event_stale: false, awaiting_outcome: 0, state: "healthy", warning: false, feed: "CURRENT" },
    { event_stale: true, awaiting_outcome: 0, state: "no_events", warning: false, feed: "NO EVENTS" },
  ])("renders $feed independently of Complete and backlog=$awaiting_outcome", async (health) => {
    const latest = health.state === "no_events" ? "" : "2026-08-12T12:00:00Z";
    const fallback = baseFetchMock(() => { throw new Error("Unexpected Start"); });
    const fetchMock = vi.fn((url, options = {}) => {
      if (String(url).startsWith("/api/snapshot")) {
        return Promise.resolve(jsonResponse({
          ...READY_SNAPSHOT,
          sendgrid_outcome_health: {
            ...health,
            latest_sendgrid_event_timestamp: latest,
            warning_text: health.warning ? "SendGrid outcome feed is stale." : "",
            webhook_route_exists: true,
            sendgrid_event_public_key_configured: true,
            sendgrid_webhook_receiver_url_configured: true,
          },
        }));
      }
      return fallback(url, options);
    });
    root = await bootController(fetchMock, "ops");

    const card = document.querySelector(".summary-card-sendgrid");
    const feed = card.querySelector(".sendgrid-outcome-health");
    expect(card.querySelector(".summary-value").textContent).toBe("Complete");
    expect(feed.textContent).toContain(`Event feed: ${health.feed}`);
    expect(feed.textContent.includes("No outcomes currently awaiting")).toBe(health.awaiting_outcome === 0);
    expect(feed.querySelector("strong") !== null).toBe(health.warning);
    expect(feed.textContent).toContain("Latest outcome event:");
    expect(feed.textContent).toContain(latest ? "2026" : "No SendGrid events");
    expect(document.querySelector(".summary-card-alerts .summary-value").textContent).toBe("0 warnings");
    expect(fetchMock.mock.calls.every(([, options = {}]) => !options.method || options.method === "GET")).toBe(true);
  });

  it("keeps Private JC card sent count cold-only while progress shows compact private total", async () => {
    const fetchMock = vi.fn((url, options = {}) => {
      if (String(url).startsWith("/api/snapshot")) {
        return Promise.resolve(jsonResponse({
          ...READY_SNAPSHOT,
          profiles: [
            {
              name: "private_jc",
              pending_count: 1615,
              runtime_state: "stopped",
              run_sent_display: 4929,
              max_total: 2000,
              message_readiness_status: "PASS",
            },
            { name: "private_jc_warm", pending_count: 0, runtime_state: "stopped", run_sent_display: 33 },
            { name: "sendgrid_alison", pending_count: 0, runtime_state: "stopped", run_sent_display: 50387 },
          ],
          warm_private_jc_status: { sent_count: 33 },
          summary: {
            total_pending: 1615,
            astra_pending: 1615,
            sendgrid_pending: 0,
            active_alerts: 0,
            total_awaiting_outcome: 0,
          },
          alerts: [],
        }));
      }
      return baseFetchMock(() => { throw new Error("Unexpected Start"); })(url, options);
    });
    root = await bootController(fetchMock, "ops");

    const privateCard = document.querySelector(".summary-card-private_jc");
    expect(privateCard).toHaveTextContent("JC Cold");
    expect(privateCard.querySelector(".summary-value")).toHaveTextContent("1,615 pending");
    expect(privateCard.querySelector(".summary-note")).toHaveTextContent("Ready · 4,929 sent");
    expect(privateCard.querySelector(".summary-note")).not.toHaveTextContent("4,962");
    expect(privateCard).toHaveTextContent("Private Email total: 4,962");
    expect(privateCard).toHaveTextContent("JC cold: 4,929");
    expect(privateCard).toHaveTextContent("Warm JC: 33");

    const progress = document.getElementById("ops-progress-summary");
    const progressItems = [...progress.querySelectorAll(".ops-progress-summary-item")];
    expect(progressItems).toHaveLength(3);
    expect(progressItems[0]).toHaveTextContent("SendGrid");
    expect(progressItems[0]).toHaveTextContent("Complete · 50,387 sent");
    expect(progressItems[1]).toHaveTextContent("Private Email");
    expect(progressItems[1]).toHaveTextContent("4,962 sent · JC 4,929 · Warm 33");
    expect(progressItems[2]).toHaveTextContent("Alerts");
    expect(progressItems[2]).toHaveTextContent("0 blocking · 0 warning · 0 awaiting");
    expect(document.getElementById("ops-progress-details-toggle")).toHaveTextContent("View details");
  });

  it("posts the sender-row Start exactly once and locks duplicate interaction while pending", async () => {
    const pending = deferredResponse();
    const fetchMock = baseFetchMock(() => pending.promise);
    root = await bootController(fetchMock);

    const startButton = senderRowStartButton();
    expect(startButton).toBeInTheDocument();
    expect(startButton).toHaveTextContent("Start");

    fireEvent.click(startButton);

    const pendingButton = senderRowStartButton();
    expect(window.confirm).toHaveBeenCalledTimes(1);
    expect(pendingButton).toHaveTextContent("Starting...");
    expect(pendingButton).toBeDisabled();
    expect(startCalls(fetchMock)).toEqual([
      ["/api/start/private_jc", { method: "POST" }],
    ]);

    fireEvent.click(pendingButton);
    expect(window.confirm).toHaveBeenCalledTimes(1);
    expect(startCalls(fetchMock)).toHaveLength(1);

    await act(async () => {
      pending.resolve(jsonResponse({
        ok: true,
        message: "Synthetic Start accepted.",
        snapshot: READY_SNAPSHOT,
      }));
      await flushMicrotasks();
    });

    expect(senderRowStartButton()).toHaveTextContent("Start");
    expect(senderRowStartButton()).not.toBeDisabled();
    expect(startCalls(fetchMock)).toHaveLength(1);
  });

  it("posts the Profile Detail Start exactly once", async () => {
    const pending = deferredResponse();
    const fetchMock = baseFetchMock(() => pending.promise);
    root = await bootController(fetchMock);

    const startButton = profileDetailStartButton();
    expect(startButton).toBeInTheDocument();
    expect(startButton).toHaveTextContent("Start");

    fireEvent.click(startButton);

    expect(profileDetailStartButton()).toHaveTextContent("Starting...");
    expect(profileDetailStartButton()).toBeDisabled();
    expect(startCalls(fetchMock)).toEqual([
      ["/api/start/private_jc", { method: "POST" }],
    ]);

    await act(async () => {
      pending.resolve(jsonResponse({
        ok: true,
        message: "Synthetic Start accepted.",
        snapshot: READY_SNAPSHOT,
      }));
      await flushMicrotasks();
    });

    expect(profileDetailStartButton()).toHaveTextContent("Start");
    expect(startCalls(fetchMock)).toHaveLength(1);
  });

  it("does not POST when the operator cancels the confirmation", async () => {
    const fetchMock = baseFetchMock(() => {
      throw new Error("Start fetch must not run after cancellation.");
    });
    root = await bootController(fetchMock);
    window.confirm.mockReturnValue(false);

    fireEvent.click(senderRowStartButton());
    await act(async () => flushMicrotasks());

    expect(window.confirm).toHaveBeenCalledTimes(1);
    expect(startCalls(fetchMock)).toHaveLength(0);
    expect(senderRowStartButton()).toHaveTextContent("Start");
    expect(document.getElementById("message-bar")).toHaveTextContent(
      "Manual Start/Resume cancelled. No sender workers were started.",
    );
  });

  it("clears pending state after a failed Start response without retrying", async () => {
    const backendFailure = "REFUSED: astra-sender@private_jc.service ExecCondition rejected startup; state=inactive substate=dead result=exec-condition exec_condition_status=1.";
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({
      ok: false,
      blocked: true,
      message: backendFailure,
    }, 409)));
    root = await bootController(fetchMock);

    fireEvent.click(senderRowStartButton());
    await act(async () => flushMicrotasks(12));

    expect(startCalls(fetchMock)).toEqual([
      ["/api/start/private_jc", { method: "POST" }],
    ]);
    expect(senderRowStartButton()).toHaveTextContent("Start");
    expect(senderRowStartButton()).not.toBeDisabled();
    expect(document.getElementById("message-bar")).toHaveTextContent(
      backendFailure,
    );
    expect(document.querySelector(".profile-action-feedback.error")).toHaveTextContent(
      backendFailure,
    );
  });
});

describe("Start Ready Senders controls", () => {
  let root;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(async () => {
    if (root) {
      await act(async () => root.unmount());
      root = null;
    }
    cleanup();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    document.head.innerHTML = "";
    document.body.innerHTML = "";
  });

  const plan = {
    ok: true,
    ready_count: 2,
    ready_profiles: [
      { profile: "private_jc", label: "JC", status: "READY", pending_count: 8, reason: "Ready to start." },
      { profile: "sendgrid_annette", label: "Annette", status: "READY", pending_count: 12, reason: "Ready to start." },
    ],
    skipped_profiles: [
      { profile: "private_jc_warm", label: "Warm Outreach", status: "SKIPPED", pending_count: 0, reason: "Empty queue (SAFE_IDLE_EMPTY_QUEUE)." },
    ],
  };

  it("loads the authoritative plan before exposing inline confirmation", async () => {
    const handler = (pathName, options) => {
      return Promise.resolve(jsonResponse(plan));
    };
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({ ok: true })), handler);
    root = await bootController(fetchMock, "start-ready");

    expect(startReadyButton()).toHaveTextContent("Start Ready Senders");
    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(16));

    expect(fetchMock.mock.calls.filter(([url, options = {}]) => (
      String(url) === "/api/start-ready" && !options.method
    ))).toHaveLength(1);
    expect(startReadyPosts(fetchMock)).toHaveLength(0);
    expect(window.confirm).not.toHaveBeenCalled();
    expect(startReadyButton()).toHaveTextContent("Confirm Start 2 Senders");
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent(
      "READYJC8 pending · Ready to start.",
    );
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent(
      "SKIPPEDWarm Outreach0 pending · Empty queue (SAFE_IDLE_EMPTY_QUEUE).",
    );
    expect(startReadyButton()).not.toBeDisabled();
  });

  it("cancel submits zero Start transactions", async () => {
    const fetchMock = baseFetchMock(
      () => Promise.resolve(jsonResponse({ ok: true })),
      () => Promise.resolve(jsonResponse(plan)),
    );
    root = await bootController(fetchMock, "start-ready");

    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));
    fireEvent.click(document.querySelector(".react-start-ready-control .btn-secondary"));
    await act(async () => flushMicrotasks());

    expect(startReadyPosts(fetchMock)).toHaveLength(0);
    expect(startReadyButton()).not.toBeDisabled();
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent(
      "Start Ready Senders cancelled. No Start request was submitted.",
    );
  });

  it("locks rapid duplicate clicks while readiness is pending", async () => {
    const pending = deferredResponse();
    const fetchMock = baseFetchMock(
      () => Promise.resolve(jsonResponse({ ok: true })),
      () => pending.promise,
    );
    root = await bootController(fetchMock, "start-ready");

    fireEvent.click(startReadyButton());
    fireEvent.click(startReadyButton());

    expect(startReadyButton()).toBeDisabled();
    expect(startReadyButton()).toHaveTextContent("Checking readiness...");
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === "/api/start-ready")).toHaveLength(1);

    await act(async () => {
      pending.resolve(jsonResponse({ ok: true, ready_profiles: [], skipped_profiles: plan.skipped_profiles }));
      await flushMicrotasks();
    });
    expect(startReadyButton()).toBeDisabled();
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent("No pending sender work");
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent("SAFE_IDLE_EMPTY_QUEUE");
    expect(startReadyButton()).not.toHaveTextContent("Confirm Start");
    expect(startReadyPosts(fetchMock)).toHaveLength(0);
  });

  it("can refresh an empty plan into a positive plan without posting automatically", async () => {
    let responsePlan = { ok: true, ready_profiles: [], skipped_profiles: plan.skipped_profiles };
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({ ok: true })),
      () => Promise.resolve(jsonResponse(responsePlan)));
    root = await bootController(fetchMock, "start-ready");
    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(16));
    expect(startReadyButton()).toBeDisabled();
    fireEvent.click(startReadyButton());
    expect(startReadyPosts(fetchMock)).toHaveLength(0);
    responsePlan = plan;
    fireEvent.click([...document.querySelectorAll("button")].find((button) => button.textContent === "Refresh readiness"));
    await act(async () => flushMicrotasks(16));
    expect(startReadyButton()).not.toBeDisabled();
    expect(startReadyButton()).toHaveTextContent("Confirm Start 2 Senders");
    expect(startReadyPosts(fetchMock)).toHaveLength(0);
  });

  it("submits exactly one POST across rapid repeated confirmation activations and rerenders", async () => {
    const pendingPost = deferredResponse();
    const handler = (pathName, options) => {
      if (pathName === "/api/start-ready" && options.method === "POST") {
        return pendingPost.promise;
      }
      return Promise.resolve(jsonResponse(plan));
    };
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({ ok: true })), handler);
    root = await bootController(fetchMock, "start-ready");

    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));
    fireEvent.click(startReadyButton());
    fireEvent.click(startReadyButton());
    fireEvent.keyDown(startReadyButton(), { key: "Enter", code: "Enter" });

    expect(startReadyButton()).toBeDisabled();
    expect(startReadyPosts(fetchMock)).toHaveLength(1);

    await act(async () => {
      root.render(<SenderStartControls />);
      await flushMicrotasks();
    });
    fireEvent.click(startReadyButton());
    expect(startReadyPosts(fetchMock)).toHaveLength(1);

    await act(async () => {
      pendingPost.resolve(jsonResponse({
        ok: true,
        job: { job_id: "job-double", status: "FAILED", results: [], message: "Stopped safely." },
      }, 202));
      await flushMicrotasks(12);
    });
    expect(startReadyPosts(fetchMock)).toHaveLength(1);
  });

  it("treats a network-ambiguous POST as non-retryable", async () => {
    const handler = (pathName, options) => {
      if (pathName === "/api/start-ready" && options.method === "POST") {
        return Promise.reject(new Error("synthetic connection loss"));
      }
      return Promise.resolve(jsonResponse(plan));
    };
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({ ok: true })), handler);
    root = await bootController(fetchMock, "start-ready");

    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));
    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));

    expect(startReadyPosts(fetchMock)).toHaveLength(1);
    expect(startReadyButton()).toBeDisabled();
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent(
      "Do not retry. Inspect the Start Ready job and sender runtime state.",
    );
    fireEvent.click(startReadyButton());
    expect(startReadyPosts(fetchMock)).toHaveLength(1);
  });

  it("captures the 202 job id, polls with GET, continues RUNNING, and stops on COMPLETE", async () => {
    let statusCalls = 0;
    const handler = (pathName, options) => {
      if (pathName === "/api/start-ready" && options.method === "POST") {
        return Promise.resolve(jsonResponse({
          ok: true,
          job: { job_id: "job-202", status: "PLANNING", results: [], message: "Accepted." },
        }, 202));
      }
      if (pathName === "/api/start-ready/status/job-202") {
        statusCalls += 1;
        return Promise.resolve(jsonResponse({
          ok: true,
          job: statusCalls === 1
            ? {
              job_id: "job-202",
              status: "RUNNING",
              results: [{ profile: "private_jc", label: "JC", status: "STARTING", pending_count: 8, reason: "Activating." }],
            }
            : {
              job_id: "job-202",
              status: "COMPLETE",
              message: "Complete.",
              results: [
                { profile: "private_jc", label: "JC", status: "STARTED", pending_count: 8, reason: "Started." },
                { profile: "sendgrid_annette", label: "Annette", status: "REFUSED", pending_count: 12, reason: "Refused." },
                { profile: "sendgrid_jodi", label: "Jodi", status: "FAILED", pending_count: 7, reason: "Failed." },
                { profile: "sendgrid_jordan", label: "Jordan", status: "SKIPPED", pending_count: 6, reason: "Skipped." },
              ],
            },
        }));
      }
      return Promise.resolve(jsonResponse(plan));
    };
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({ ok: true })), handler);
    root = await bootController(fetchMock, "start-ready");

    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));
    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(16));

    expect(statusCalls).toBe(1);
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent("STARTINGJC");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(750);
      await flushMicrotasks(12);
    });
    expect(statusCalls).toBe(2);
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent("STARTEDJC");
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent("REFUSEDAnnette");
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent("FAILEDJodi");
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent("SKIPPEDJordan");
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === "/api/start-ready/status/job-202").every(([, options = {}]) => !options.method || options.method === "GET")).toBe(true);
    await act(async () => vi.advanceTimersByTimeAsync(3000));
    expect(statusCalls).toBe(2);
  });

  it("stops polling on FAILED", async () => {
    let statusCalls = 0;
    const handler = (pathName, options) => {
      if (pathName === "/api/start-ready" && options.method === "POST") {
        return Promise.resolve(jsonResponse({ ok: true, job: { job_id: "job-failed", status: "PLANNING" } }, 202));
      }
      if (pathName === "/api/start-ready/status/job-failed") {
        statusCalls += 1;
        return Promise.resolve(jsonResponse({
          ok: true,
          job: { job_id: "job-failed", status: "FAILED", results: [{ profile: "private_jc", label: "JC", status: "FAILED", reason: "Failed safely." }] },
        }));
      }
      return Promise.resolve(jsonResponse(plan));
    };
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({ ok: true })), handler);
    root = await bootController(fetchMock, "start-ready");

    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));
    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(16));
    await act(async () => vi.advanceTimersByTimeAsync(3000));

    expect(statusCalls).toBe(1);
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent("FAILEDJC");
  });

  it("handles an active-job 409 without another POST", async () => {
    const pendingStatus = deferredResponse();
    const handler = (pathName, options) => {
      if (pathName === "/api/start-ready" && options.method === "POST") {
        return Promise.resolve(jsonResponse({
          ok: false,
          message: "Start Ready Senders is already running.",
          job: { job_id: "job-active", status: "RUNNING", results: [] },
        }, 409));
      }
      if (pathName === "/api/start-ready/status/job-active") return pendingStatus.promise;
      return Promise.resolve(jsonResponse(plan));
    };
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({ ok: true })), handler);
    root = await bootController(fetchMock, "start-ready");

    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));
    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));

    expect(startReadyPosts(fetchMock)).toHaveLength(1);
    expect(startReadyButton()).toBeDisabled();
    expect(document.getElementById("react-start-ready-status")).toHaveTextContent(
      "Start Ready Senders is already running.",
    );
    fireEvent.click(startReadyButton());
    expect(startReadyPosts(fetchMock)).toHaveLength(1);

    await act(async () => {
      pendingStatus.resolve(jsonResponse({ ok: true, job: { job_id: "job-active", status: "COMPLETE", results: [] } }));
      await flushMicrotasks(12);
    });
  });

  it("cleans a nonterminal polling timer on unmount", async () => {
    let statusCalls = 0;
    const handler = (pathName, options) => {
      if (pathName === "/api/start-ready" && options.method === "POST") {
        return Promise.resolve(jsonResponse({ ok: true, job: { job_id: "job-unmount", status: "PLANNING" } }, 202));
      }
      if (pathName === "/api/start-ready/status/job-unmount") {
        statusCalls += 1;
        return Promise.resolve(jsonResponse({ ok: true, job: { job_id: "job-unmount", status: "RUNNING", results: [] } }));
      }
      return Promise.resolve(jsonResponse(plan));
    };
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({ ok: true })), handler);
    root = await bootController(fetchMock, "start-ready");

    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));
    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(16));
    expect(statusCalls).toBe(1);

    await act(async () => root.unmount());
    root = null;
    await act(async () => vi.advanceTimersByTimeAsync(3000));
    expect(statusCalls).toBe(1);
  });
});
