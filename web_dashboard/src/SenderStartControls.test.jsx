import fs from "node:fs";
import path from "node:path";

import React from "react";
import { act, cleanup, fireEvent } from "@testing-library/react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardApp } from "./main.jsx";

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

async function bootController(fetchMock) {
  installDashboardDocument();
  window.history.replaceState({}, "", "/?tab=ops");
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

  it("shows the plan, requires explicit confirmation, and submits one bulk transaction", async () => {
    const handler = (pathName, options) => {
      if (pathName === "/api/start-ready" && options.method === "POST") {
        return Promise.resolve(jsonResponse({
          ok: true,
          status: "PLANNING",
          job: { job_id: "job-1", status: "PLANNING", results: [], message: "Recomputing." },
        }, 202));
      }
      if (pathName === "/api/start-ready/status/job-1") {
        return Promise.resolve(jsonResponse({
          ok: true,
          job: {
            job_id: "job-1",
            status: "COMPLETE",
            message: "Completed without retries.",
            results: [
              { profile: "private_jc", label: "JC", status: "STARTED", pending_count: 8, reason: "Started." },
              { profile: "sendgrid_annette", label: "Annette", status: "STARTING", pending_count: 12, reason: "Activating." },
              ...plan.skipped_profiles,
            ],
          },
        }));
      }
      return Promise.resolve(jsonResponse(plan));
    };
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({ ok: true })), handler);
    root = await bootController(fetchMock);

    expect(startReadyButton()).toHaveTextContent("Start Ready Senders");
    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(16));

    expect(window.confirm).toHaveBeenCalledTimes(1);
    expect(window.confirm.mock.calls[0][0]).toContain("Start 2 ready operational sender(s), sequentially?");
    expect(window.confirm.mock.calls[0][0]).toContain("Warm Outreach: Empty queue (SAFE_IDLE_EMPTY_QUEUE).");
    expect(window.confirm.mock.calls[0][0]).not.toContain("sendgrid_controlled_test");
    expect(startReadyPosts(fetchMock)).toHaveLength(1);
    expect(document.getElementById("start-ready-status")).toHaveTextContent("STARTEDJC8 pending · Started.");
    expect(document.getElementById("start-ready-status")).toHaveTextContent("STARTINGAnnette12 pending · Activating.");
    expect(startReadyButton()).not.toBeDisabled();
  });

  it("cancellation submits zero Start transactions and leaves the dashboard usable", async () => {
    const fetchMock = baseFetchMock(
      () => Promise.resolve(jsonResponse({ ok: true })),
      () => Promise.resolve(jsonResponse(plan)),
    );
    root = await bootController(fetchMock);
    window.confirm.mockReturnValue(false);

    fireEvent.click(startReadyButton());
    await act(async () => flushMicrotasks(12));

    expect(startReadyPosts(fetchMock)).toHaveLength(0);
    expect(startReadyButton()).not.toBeDisabled();
    expect(document.getElementById("message-bar")).toHaveTextContent(
      "Start Ready Senders cancelled. No Start request was submitted.",
    );
    fireEvent.click(document.getElementById("refresh-btn"));
    await act(async () => flushMicrotasks());
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith("/api/snapshot")).length).toBeGreaterThan(1);
  });

  it("locks rapid duplicate clicks while readiness is pending", async () => {
    const pending = deferredResponse();
    const fetchMock = baseFetchMock(
      () => Promise.resolve(jsonResponse({ ok: true })),
      () => pending.promise,
    );
    root = await bootController(fetchMock);

    fireEvent.click(startReadyButton());
    fireEvent.click(startReadyButton());

    expect(startReadyButton()).toBeDisabled();
    expect(startReadyButton()).toHaveTextContent("Checking readiness...");
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === "/api/start-ready")).toHaveLength(1);

    await act(async () => {
      pending.resolve(jsonResponse({ ok: true, ready_profiles: [], skipped_profiles: plan.skipped_profiles }));
      await flushMicrotasks();
    });
    expect(startReadyButton()).not.toBeDisabled();
    expect(startReadyPosts(fetchMock)).toHaveLength(0);
  });
});
