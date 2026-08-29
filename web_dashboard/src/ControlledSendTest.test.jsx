import fs from "node:fs";
import path from "node:path";

import React from "react";
import { act, cleanup, fireEvent } from "@testing-library/react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardApp } from "./main.jsx";

const INDEX_HTML = fs.readFileSync(path.resolve(process.cwd(), "web_dashboard/index.html"), "utf8");
const SNAPSHOT = {
  generated_at: "2026-08-29T00:00:00Z",
  activity_hours: 24,
  profiles: [],
  summary: { total_pending: 0 },
  controls: {},
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

function response(data, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(data) };
}

function deferred() {
  let resolve;
  const promise = new Promise((next) => { resolve = next; });
  return { promise, resolve };
}

async function flush(turns = 8) {
  for (let index = 0; index < turns; index += 1) await Promise.resolve();
}

async function boot(controlledHandler) {
  const parsed = new DOMParser().parseFromString(INDEX_HTML, "text/html");
  document.head.innerHTML = parsed.head.innerHTML;
  document.body.innerHTML = parsed.body.innerHTML;
  window.history.replaceState({}, "", "/?tab=ops");
  const fetchMock = vi.fn((url, options = {}) => {
    const pathname = String(url);
    if (pathname === "/api/auth/status") return Promise.resolve(response({ ok: true, authenticated: true, auth_enabled: false, auth_disabled: true }));
    if (pathname.startsWith("/api/snapshot")) return Promise.resolve(response(SNAPSHOT));
    if (pathname === "/api/sendgrid/controlled-test") return controlledHandler(pathname, options);
    return Promise.resolve(response({ ok: true }));
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const root = createRoot(document.getElementById("dashboard-root"));
  await act(async () => { root.render(<DashboardApp />); await flush(); });
  vi.resetModules();
  await act(async () => { await import("../app.js"); await flush(); });
  return { root, fetchMock };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.head.innerHTML = "";
  document.body.innerHTML = "";
});

describe("Controlled Send Test", () => {
  it("renders only approved identities and updates the server-locked From preview", async () => {
    const { root } = await boot(() => Promise.resolve(response({ ok: true })));
    const select = document.getElementById("controlled-send-test-profile");
    expect(document.getElementById("controlled-send-test-recipient")).toHaveTextContent("astraprouctionsbyjc@gmail.com");
    expect([...select.options].map((option) => [option.value, option.dataset.fromEmail])).toEqual([
      ["sendgrid_alison", "alisonaguiar@bnmarketing.info"],
      ["sendgrid_jodi", "jodihorowitz@bnmarketing.info"],
      ["sendgrid_jordan", "jordankendrick@bnmarketing.info"],
    ]);
    fireEvent.change(select, { target: { value: "sendgrid_jordan" } });
    expect(document.getElementById("controlled-send-test-from")).toHaveTextContent("jordankendrick@bnmarketing.info");
    await act(async () => root.unmount());
  });

  it("submits exactly one profile-only request and locks rapid repeated interaction", async () => {
    const pending = deferred();
    const { root, fetchMock } = await boot(() => pending.promise);
    const button = document.getElementById("controlled-send-test-btn");
    fireEvent.click(button);
    expect(window.confirm).toHaveBeenCalledTimes(1);
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Sending...");
    expect(document.getElementById("controlled-send-test-profile")).toBeDisabled();
    fireEvent.click(button);
    const posts = fetchMock.mock.calls.filter(([url]) => String(url) === "/api/sendgrid/controlled-test");
    expect(posts).toHaveLength(1);
    expect(posts[0][1]).toEqual({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender_profile: "sendgrid_alison" }),
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith("/api/start/"))).toBe(false);
    await act(async () => {
      pending.resolve(response({
        ok: true,
        message: "Accepted.",
        result: {
          sender: "Alison",
          from_email: "alisonaguiar@bnmarketing.info",
          recipient: "astraprouctionsbyjc@gmail.com",
          provider_message_id: "provider-1",
          submitted_at_utc: "2026-08-29T00:00:00Z",
        },
      }));
      await flush();
    });
    expect(document.getElementById("controlled-send-test-status")).toHaveTextContent("Alison accepted");
    expect(document.getElementById("controlled-send-test-status")).toHaveTextContent("provider-1");
    expect(button).not.toBeDisabled();
    expect(button).toHaveTextContent("Send 1 Controlled Test");
    await act(async () => root.unmount());
  });

  it("cancellation emits no controlled request", async () => {
    const { root, fetchMock } = await boot(() => Promise.resolve(response({ ok: true })));
    window.confirm.mockReturnValue(false);
    fireEvent.click(document.getElementById("controlled-send-test-btn"));
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === "/api/sendgrid/controlled-test")).toHaveLength(0);
    expect(document.getElementById("controlled-send-test-status")).toHaveTextContent("cancelled");
    await act(async () => root.unmount());
  });

  it("surfaces structured failure and returns controls to a usable non-pending state", async () => {
    const { root, fetchMock } = await boot(() => Promise.resolve(response({
      ok: false,
      blocked: true,
      error: "recipient_blocked",
      message: "Controlled test recipient is suppressed.",
      auto_started: false,
    }, 409)));
    fireEvent.click(document.getElementById("controlled-send-test-btn"));
    await act(async () => { await flush(); });
    expect(document.getElementById("controlled-send-test-status")).toHaveTextContent("suppressed");
    expect(document.getElementById("controlled-send-test-btn")).not.toBeDisabled();
    expect(document.getElementById("controlled-send-test-profile")).not.toBeDisabled();
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === "/api/sendgrid/controlled-test")).toHaveLength(1);
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith("/api/start/"))).toBe(false);
    await act(async () => root.unmount());
  });
});
