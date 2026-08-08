import React, { useEffect } from "react";
import { createRoot } from "react-dom/client";
import parse from "html-react-parser";
import "./tailwind.css";

function LegacyNode({ html }) {
  return parse(html);
}

export function StatusPill({ children, tone = "neutral" }) {
  return <span className={`react-status-pill react-status-pill-${tone}`}>{children}</span>;
}

export function Sidebar({ brand, navigation, status }) {
  return (
    <aside className="app-rail react-sidebar" aria-label="Primary navigation">
      <div className="react-sidebar-brand">
        <span className="react-brand-mark" aria-hidden="true">EA</span>
        <LegacyNode html={brand} />
      </div>
      <nav className="react-sidebar-nav" aria-label="Workspace">
        <p className="react-sidebar-label">Workspace</p>
        <LegacyNode html={navigation} />
      </nav>
      <div className="react-sidebar-context">
        <p className="react-sidebar-label">Environment</p>
        <LegacyNode html={status} />
      </div>
    </aside>
  );
}

export function PageHeading({ eyebrow, title, description, aside = null }) {
  return (
    <header className="react-page-heading">
      <div>
        <p className="react-kicker">{eyebrow}</p>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {aside}
    </header>
  );
}

export function CommandBar({ html }) {
  return (
    <div className="react-command-bar">
      <p className="react-command-label">Run controls</p>
      <LegacyNode html={html} />
    </div>
  );
}

export function MetricCard({ children }) {
  return (
    <section className="react-metric-region" aria-label="Current run summary">
      <header className="react-section-heading">
        <div>
          <p className="react-section-label">Current run</p>
          <span>Queue and delivery state</span>
        </div>
        <span className="react-section-state">Live snapshot</span>
      </header>
      {children}
    </section>
  );
}

export function SenderTable({ progress, details }) {
  return (
    <section className="react-sender-console" aria-label="Sender operations">
      <LegacyNode html={progress} />
      <LegacyNode html={details} />
    </section>
  );
}

export function EmptyState({ title, description }) {
  return (
    <div className="react-empty-state">
      <span aria-hidden="true" />
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

export function EnvironmentBanner() {
  return (
    <section id="dashboard-environment-banner" className="react-environment-banner react-environment-banner-checking" aria-label="Dashboard environment and sender safety">
      <div className="react-environment-primary">
        <span className="react-environment-dot" aria-hidden="true" />
        <div>
          <p>Environment &amp; sender safety</p>
          <strong id="dashboard-environment-mode">Checking dashboard mode...</strong>
        </div>
      </div>
      <div className="react-environment-flags">
        <span id="dashboard-auth-mode">Auth: checking</span>
        <span id="dashboard-auto-start-mode">Auto-start: checking</span>
      </div>
      <p id="dashboard-environment-note">Manual Start/Resume can launch real workers and consume queues.</p>
    </section>
  );
}

export function SendersDashboard({ view }) {
  return (
    <section id="ops-view" className="dashboard-view workspace-view react-workspace react-senders-page" role="tabpanel" aria-labelledby="ops-tab-btn">
      <PageHeading
        eyebrow="Delivery operations"
        title="Sender command center"
        description="Monitor queues, delivery state, and the next safe action."
        aside={<StatusPill tone="live">Live operations</StatusPill>}
      />
      <CommandBar html={view.commandBar} />
      <MetricCard><LegacyNode html={view.metrics} /></MetricCard>
      <SenderTable progress={view.progress} details={view.progressDetails} />
      <section className="react-supporting-panels">
        <LegacyNode html={view.profileDetail} />
        <LegacyNode html={view.history} />
      </section>
    </section>
  );
}

export function LeadStepper({ status, steps }) {
  return (
    <>
      <LegacyNode html={status} />
      <div className="react-stepper-shell">
        <p className="react-section-label">
          <span className="react-cold-copy">Dispatch workflow</span>
          <span className="react-warm-copy">Warm outreach workflow</span>
        </p>
        <LegacyNode html={steps} />
      </div>
    </>
  );
}

export function SourcePanel({ html }) {
  return <LegacyNode html={html} />;
}

export function CommandRail({ left, right }) {
  return (
    <div className="leads-command-main react-lead-workspace">
      <LegacyNode html={left} />
      <div className="react-command-rail-shell">
        <LegacyNode html={right} />
      </div>
    </div>
  );
}

export function WarmResearchPanel({ children }) {
  return <div className="react-warm-surface">{children}</div>;
}

export function LeadOpsDashboard({ view }) {
  return (
    <section id="leads-view" className="dashboard-view workspace-view leads-workspace react-workspace react-leads-page hidden" role="tabpanel" aria-labelledby="leads-tab-btn" hidden>
      <PageHeading
        eyebrow="Lead operations"
        title={(
          <>
            <span className="react-cold-copy">Prepare the next campaign</span>
            <span className="react-warm-copy">Warm research workspace</span>
          </>
        )}
        description={(
          <>
            <span className="react-cold-copy">Check source quality, choose a campaign, preview the write set, then confirm.</span>
            <span className="react-warm-copy">Turn qualified research into reviewed, explicitly confirmed outreach.</span>
          </>
        )}
        aside={<StatusPill tone="safe">Safety gated</StatusPill>}
      />
      <nav id="leads-workflow-nav" className="leads-workflow-nav" aria-label="Lead Ops workflows">
        <a href="/?tab=leads&amp;workflow=cold" data-leads-workflow="cold">Cold Campaigns</a>
        <a href="/?tab=leads&amp;workflow=warm" data-leads-workflow="warm">Warm Outreach</a>
      </nav>
      <section className="leads-command-center operator-workflow-section react-lead-canvas">
        <LegacyNode html={view.heading} />
        <WarmResearchPanel><SourcePanel html={view.source} /></WarmResearchPanel>
        <LeadStepper status={view.workflowStatus} steps={view.workflowSteps} />
        <CommandRail left={view.commandLeft} right={view.commandRight} />
        <LegacyNode html={view.diagnostics} />
      </section>
    </section>
  );
}

export function AppShell({ template }) {
  return (
    <div className="page booting react-dashboard min-h-screen bg-canvas text-ink" data-dashboard-ui="react-tailwind-components">
      <div className="app-shell react-app-shell">
        <Sidebar {...template.sidebar} />
        <main className="app-main react-main">
          <EnvironmentBanner />
          <SendersDashboard view={template.senders} />
          <LeadOpsDashboard view={template.leadOps} />
        </main>
      </div>
    </div>
  );
}

function DashboardControllerBridge() {
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "/static/app.js?v=snapshot-polling-20260803a";
    script.dataset.dashboardController = "true";
    document.body.append(script);
    return () => script.remove();
  }, []);
  return null;
}

function outer(root, selector) {
  const node = root.querySelector(selector);
  if (!node) throw new Error(`Dashboard template is missing ${selector}.`);
  return node.outerHTML;
}

function readDashboardTemplate() {
  const template = document.getElementById("dashboard-template");
  if (!(template instanceof HTMLTemplateElement)) throw new Error("Dashboard template is missing.");
  const content = template.content.cloneNode(true);
  const header = content.querySelector(".app-rail");
  const senders = content.querySelector("#ops-view");
  const leadOps = content.querySelector("#leads-view");
  const command = leadOps?.querySelector(".leads-command-center");
  const commandMain = command?.querySelector(".leads-command-main");
  if (!header || !senders || !leadOps || !command || !commandMain) throw new Error("Dashboard template is incomplete.");

  return {
    sidebar: {
      brand: outer(header, ".app-rail-top"),
      navigation: outer(header, ".app-rail-tabs"),
      status: outer(header, ".app-rail-status"),
    },
    senders: {
      commandBar: outer(senders, ".workspace-status-row"),
      metrics: outer(senders, ".queue-health-section"),
      progress: outer(senders, ".ops-progress-strip"),
      progressDetails: outer(senders, "#ops-progress-details"),
      profileDetail: outer(senders, ".workspace-primary"),
      history: outer(senders, ".campaign-history-panel"),
    },
    leadOps: {
      heading: outer(command, ":scope > .panel-header"),
      source: outer(command, ":scope > .leads-control-bar"),
      workflowStatus: outer(command, ":scope > .leads-workflow-status-banner"),
      workflowSteps: outer(command, ":scope > .leads-workflow-task-list"),
      commandLeft: outer(commandMain, ":scope > .leads-command-column-left"),
      commandRight: outer(commandMain, ":scope > .leads-command-column-right"),
      diagnostics: outer(command, ":scope > .leads-advanced-diagnostics"),
    },
    auth: outer(content, "#auth-overlay"),
  };
}

export function DashboardApp({ template = readDashboardTemplate() }) {
  return (
    <>
      <AppShell template={template} />
      <LegacyNode html={template.auth} />
      <DashboardControllerBridge />
    </>
  );
}

const root = document.getElementById("dashboard-root");
if (root) createRoot(root).render(<DashboardApp />);
