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

function baseFetchMock(startHandler) {
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
    if (pathName.startsWith("/api/start/")) {
      return startHandler(pathName, options);
    }
    return Promise.resolve(jsonResponse({ ok: true }));
  });
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
    const fetchMock = baseFetchMock(() => Promise.resolve(jsonResponse({
      ok: false,
      blocked: true,
      message: "Synthetic Start refused.",
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
      "Synthetic Start refused.",
    );
    expect(document.querySelector(".profile-action-feedback.error")).toHaveTextContent(
      "Synthetic Start refused.",
    );
  });
});
