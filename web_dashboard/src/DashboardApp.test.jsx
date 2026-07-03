import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardApp } from "./main.jsx";

const template = {
  sidebar: {
    brand: '<div class="app-rail-top">Email Automation</div>',
    navigation: '<div class="app-rail-tabs"><button id="ops-tab-btn">Senders</button><button id="leads-tab-btn">Lead Ops</button></div>',
    status: '<div class="app-rail-status"><span id="auth-status-label">Local dev</span></div>',
  },
  senders: {
    commandBar: '<section class="workspace-status-row"><button id="start-btn">Start All</button></section>',
    metrics: '<section class="queue-health-section"><div id="summary-grid"></div></section>',
    progress: '<section class="ops-progress-strip"><span id="ops-progress-summary"></span></section>',
    progressDetails: '<details id="ops-progress-details"></details>',
    profileDetail: '<section class="workspace-primary"><div id="profile-detail"></div></section>',
    history: '<details class="campaign-history-panel"><div id="campaign-run-history"></div></details>',
  },
  leadOps: {
    heading: '<div class="panel-header"><h2 id="leads-command-heading">Prepare Dispatch</h2></div>',
    source: '<section class="leads-control-bar"><select id="leads-important-upload-type"></select></section>',
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
    expect(screen.getByText("Start All")).toBeInTheDocument();
    expect(screen.getByText("Checking dashboard mode...")).toBeInTheDocument();
    expect(screen.getByText(/Mac\/dev is not for live sending/)).toBeInTheDocument();
    expect(document.getElementById("leads-important-dispatch-preview-btn")).toBeInTheDocument();
    expect(document.getElementById("auth-overlay")).toBeInTheDocument();
    expect(document.querySelector('[data-dashboard-ui="react-tailwind-components"]')).toBeInTheDocument();
  });
});
