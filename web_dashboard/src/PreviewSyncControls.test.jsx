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

function messageReadiness(overrides = {}) {
  return {
    status: "STALE",
    preview_sync_required: true,
    recipient_row_count: 974,
    preview_row_count: 1030,
    validated_preview_row_count: 1030,
    failed_preview_row_count: 0,
    generated_row_count_matches_queue: false,
    validated_row_count_matches_queue: false,
    generated_email_set_matches_queue: false,
    validated_email_set_matches_queue: false,
    generated_fingerprint_matches_queue: false,
    validated_fingerprint_matches_queue: false,
    book_title_column_present: true,
    preview_csv_exists: true,
    preview_validation_status: "PASS",
    pitch_mode_expected: "astra_visual",
    actual_profile_mode: "astra_visual",
    reasons: ["Preview row count does not match recipient queue row count."],
    ...overrides,
  };
}

function snapshot({ readiness = messageReadiness(), blocked = false } = {}) {
  return {
    generated_at: "2026-08-22T00:00:00Z",
    display_timezone: "UTC",
    activity_hours: 24,
    profiles: [{
      name: "private_jc",
      pending_count: 974,
      runtime_state: "stopped",
      runtime_label: "Stopped",
      readiness_label: blocked ? "Blocked" : "Ready",
      readiness_tone: blocked ? "bad" : "good",
      message_readiness: readiness,
      max_total: 100,
      configured_max_total: 100,
    }],
    summary: { total_pending: 974 },
    controls: { send_target_total: 5000 },
    automation: {},
    alerts: [],
    queue_safety: { safe: !blocked },
    private_queue_safety: {
      safe: !blocked,
      message: blocked ? "Independent queue safety failure." : "Queue safety passed.",
    },
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
  for (let index = 0; index < turns; index += 1) await Promise.resolve();
}

async function bootController(fetchMock) {
  installDashboardDocument();
  window.history.replaceState({}, "", "/?tab=ops");
  vi.stubGlobal("fetch", fetchMock);
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

function fetchMockFor(initialSnapshot, syncHandler = null) {
  return vi.fn((url, options = {}) => {
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
    if (requestPath.startsWith("/api/snapshot")) {
      return Promise.resolve(jsonResponse(initialSnapshot));
    }
    if (requestPath === "/api/profiles/private_jc/preview-validate") {
      return syncHandler(requestPath, options);
    }
    return Promise.resolve(jsonResponse({ ok: true }));
  });
}

function syncButton() {
  return document.querySelector(
    '#profile-detail .preview-validate-profile-btn[data-profile="private_jc"]',
  );
}

describe("safe preview synchronization controls", () => {
  let root;

  afterEach(async () => {
    if (root) {
      await act(async () => root.unmount());
      root = null;
    }
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    document.head.innerHTML = "";
    document.body.innerHTML = "";
  });

  it("shows SYNC REQUIRED with non-PII alignment details and serializes rapid clicks", async () => {
    const pending = deferredResponse();
    const staleSnapshot = snapshot();
    const fetchMock = fetchMockFor(staleSnapshot, () => pending.promise);
    root = await bootController(fetchMock);

    expect(document.getElementById("profile-detail")).toHaveTextContent("SYNC REQUIRED");
    expect(document.getElementById("profile-detail")).toHaveTextContent(/Queue rows\s+974/);
    expect(document.getElementById("profile-detail")).toHaveTextContent(/Generated preview\s+1,030/);
    expect(document.getElementById("profile-detail")).toHaveTextContent(/Validated preview\s+1,030/);
    expect(document.getElementById("profile-detail")).toHaveTextContent(/Email sets\s+Mismatch/);
    expect(document.getElementById("profile-detail")).toHaveTextContent(/Fingerprints\s+Mismatch/);
    expect(syncButton()).toHaveTextContent("Regenerate & Validate Preview");

    fireEvent.click(syncButton());
    fireEvent.click(syncButton());

    expect(syncButton()).toHaveTextContent("Synchronizing...");
    expect(syncButton()).toBeDisabled();
    const syncPosts = fetchMock.mock.calls.filter(([url, options = {}]) => (
      String(url) === "/api/profiles/private_jc/preview-validate" && options.method === "POST"
    ));
    expect(syncPosts).toHaveLength(1);

    const currentSnapshot = snapshot({
      readiness: messageReadiness({
        status: "PASS",
        preview_sync_required: false,
        preview_row_count: 974,
        validated_preview_row_count: 974,
        generated_row_count_matches_queue: true,
        validated_row_count_matches_queue: true,
        generated_email_set_matches_queue: true,
        validated_email_set_matches_queue: true,
        generated_fingerprint_matches_queue: true,
        validated_fingerprint_matches_queue: true,
        reasons: [],
      }),
    });
    await act(async () => {
      pending.resolve(jsonResponse({
        ok: true,
        message: "Preview synchronized and validated. Sender was not started.",
        result: { validation_passed: true, preview_row_count: 974 },
        snapshot: currentSnapshot,
      }));
      await flushMicrotasks(12);
    });

    expect(document.getElementById("profile-detail")).not.toHaveTextContent("SYNC REQUIRED");
    expect(document.getElementById("profile-detail")).toHaveTextContent("PASS");
    expect(syncPosts).toHaveLength(1);
  });

  it("does not classify a matching preview as SYNC REQUIRED", async () => {
    const current = snapshot({
      readiness: messageReadiness({
        status: "PASS",
        preview_sync_required: false,
        preview_row_count: 974,
        validated_preview_row_count: 974,
        generated_row_count_matches_queue: true,
        validated_row_count_matches_queue: true,
        generated_email_set_matches_queue: true,
        validated_email_set_matches_queue: true,
        generated_fingerprint_matches_queue: true,
        validated_fingerprint_matches_queue: true,
        reasons: [],
      }),
    });
    root = await bootController(fetchMockFor(current, () => Promise.resolve(jsonResponse({ ok: true }))));

    expect(document.getElementById("profile-detail")).not.toHaveTextContent("SYNC REQUIRED");
    expect(document.getElementById("profile-detail")).toHaveTextContent("PASS");
  });

  it("surfaces a failed synchronization and restores the non-pending control", async () => {
    const fetchMock = fetchMockFor(snapshot(), () => Promise.resolve(jsonResponse({
      ok: false,
      error: "validation_failed",
      message: "Preview generated but validation failed.",
    }, 422)));
    root = await bootController(fetchMock);

    fireEvent.click(syncButton());
    await act(async () => flushMicrotasks(12));

    const syncPosts = fetchMock.mock.calls.filter(([url, options = {}]) => (
      String(url) === "/api/profiles/private_jc/preview-validate" && options.method === "POST"
    ));
    expect(syncPosts).toHaveLength(1);
    expect(syncButton()).toHaveTextContent("Regenerate & Validate Preview");
    expect(syncButton()).not.toBeDisabled();
    expect(document.getElementById("profile-detail")).toHaveTextContent(
      "Preview synchronization failed: Error: Preview generated but validation failed.",
    );
    expect(document.getElementById("message-bar")).toHaveTextContent(
      "Preview synchronization failed: Error: Preview generated but validation failed.",
    );
  });

  it("retains BLOCKED when an independent queue-safety failure also exists", async () => {
    root = await bootController(fetchMockFor(snapshot({ blocked: true }), () => Promise.resolve(jsonResponse({ ok: true }))));

    expect(document.querySelector(".sender-status-table tbody tr")).toHaveTextContent("Blocked");
    expect(document.getElementById("profile-detail")).not.toHaveTextContent("SYNC REQUIRED");
    expect(syncButton()).toBeDisabled();
  });
});
