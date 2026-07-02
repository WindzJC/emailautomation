import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardApp } from "./main.jsx";

const template = {
  header: '<aside class="app-rail"><span id="auth-status-label">Local dev</span></aside>',
  senders: '<section id="ops-view"><button id="start-btn">Start All</button><div id="summary-grid"></div></section>',
  leadOps: '<section id="leads-view" hidden><button id="leads-important-dispatch-preview-btn">Preview Dispatch</button></section>',
  auth: '<div id="auth-overlay" hidden></div>',
};

describe("DashboardApp", () => {
  it("mounts sender and Lead Ops controller contracts", () => {
    render(<DashboardApp template={template} />);
    expect(screen.getByText("Start All")).toBeInTheDocument();
    expect(document.getElementById("leads-important-dispatch-preview-btn")).toBeInTheDocument();
    expect(document.getElementById("auth-overlay")).toBeInTheDocument();
  });
});
