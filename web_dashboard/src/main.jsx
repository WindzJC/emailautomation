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
    <header className="app-rail react-sidebar" aria-label="Primary navigation">
      <div className="react-sidebar-brand">
        <span className="react-brand-mark" aria-hidden="true">Astra</span>
        <LegacyNode html={brand} />
      </div>
      <nav className="react-sidebar-nav" aria-label="Workspace">
        <LegacyNode html={navigation} />
      </nav>
      <div className="react-sidebar-context">
        <LegacyNode html={status} />
        <EnvironmentBanner />
      </div>
    </header>
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
    <section className="react-command-bar react-global-controls" aria-label="Global sender controls">
      <div className="react-section-heading">
        <div>
          <p className="react-section-label">Global controls</p>
          <span>Start, stop, and refresh controls</span>
        </div>
        <span className="react-section-state">No bulk start</span>
      </div>
      <LegacyNode html={html} />
    </section>
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

export function SenderTable({ progress, details, controls }) {
  return (
    <section className="react-sender-console" aria-label="Sender operations">
      <LegacyNode html={progress} />
      <LegacyNode html={details} />
      <CommandBar html={controls} />
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
        eyebrow="Campaign delivery"
        title="Sender operations"
        description="Review queue health, then start only the sender you intend to run."
        aside={<StatusPill tone="live">Live operations</StatusPill>}
      />

      <MetricCard>
        <LegacyNode html={view.metrics} />
      </MetricCard>

      <SenderTable
        progress={view.progress}
        details={view.progressDetails}
        controls={view.commandBar}
      />

      {view.controlledTest ? <LegacyNode html={view.controlledTest} /> : null}

      <section className="react-supporting-panels">
        <LegacyNode html={view.profileDetail} />
        <LegacyNode html={view.history} />
      </section>
    </section>
  );
}

export function LeadStepper({ status, steps }) {
  return (
    <section className="operator-stepper" aria-label="Current workflow progress">
      <LegacyNode html={status} />
      <div className="react-stepper-shell react-legacy-stepper">
        <LegacyNode html={steps} />
      </div>
      <ol className="operator-flow-line react-cold-copy" aria-label="Cold workflow steps">
        <li><span>1</span><strong>Source</strong></li>
        <li><span>2</span><strong>Campaign</strong></li>
        <li><span>3</span><strong>Preview</strong></li>
        <li><span>4</span><strong>Confirm</strong></li>
      </ol>

      <ol className="operator-flow-line react-warm-copy" aria-label="Warm Outreach workflow steps">
        <li><span>1</span><strong>Upload Batch</strong></li>
        <li><span>2</span><strong>Validate</strong></li>
        <li><span>3</span><strong>Review</strong></li>
        <li><span>4</span><strong>Preview Email</strong></li>
        <li><span>5</span><strong>Confirm</strong></li>
      </ol>
    </section>
  );
}

export function SourcePanel({ html }) {
  return (
    <section className="operator-step operator-step-source">
      <header className="operator-step-heading">
        <h3>
          <span className="react-cold-copy">Source</span>
          <span className="react-warm-copy">Upload Batch</span>
        </h3>
      </header>
      <LegacyNode html={html} />
    </section>
  );
}

export function CommandRail({ left, right }) {
  return (
    <div className="leads-command-main react-lead-workspace">
      <section className="operator-step operator-step-campaign">
        <header className="operator-step-heading">
          <span className="operator-step-number react-cold-copy">2</span>
          <span className="operator-step-number react-warm-copy">3</span>
          <div>
            <p className="operator-step-kicker">
              <span className="react-cold-copy">Choose the write set</span>
              <span className="react-warm-copy">Review current output</span>
            </p>
            <h3>
              <span className="react-cold-copy">Campaign</span>
              <span className="react-warm-copy">Review</span>
            </h3>
          </div>
        </header>
        <LegacyNode html={left} />
      </section>
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
  useEffect(() => {
    const root = document.getElementById("leads-view");
    if (!root) return undefined;
    const revealCampaignChoices = () => {
      root.querySelectorAll("details.dispatch-secondary-modes").forEach((details) => {
        details.open = true;
      });
    };
    revealCampaignChoices();
    const observer = new MutationObserver(revealCampaignChoices);
    observer.observe(root, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  return (
    <section id="leads-view" className="dashboard-view workspace-view leads-workspace react-workspace react-leads-page hidden" role="tabpanel" aria-labelledby="leads-tab-btn" hidden>
      <PageHeading
        eyebrow="Lead operations"
        title={(
          <>
            <span className="react-cold-copy">Prepare the next campaign</span>
            <span className="react-warm-copy">Warm Outreach</span>
          </>
        )}
        description={(
          <>
            <span className="react-cold-copy">Check source quality, choose a campaign, preview the write set, then confirm.</span>
            <span className="react-warm-copy">Upload a qualified warm batch, validate each lead, review the evidence and personalization, preview the exact email, then explicitly confirm.</span>
          </>
        )}
        aside={<StatusPill tone="safe">Safety gated</StatusPill>}
      />
      <nav id="leads-workflow-nav" className="leads-workflow-nav" aria-label="Lead Ops workflows">
        <a href="/?tab=leads&amp;workflow=cold" data-leads-workflow="cold">Cold Campaigns</a>
        <a href="/?tab=leads&amp;workflow=warm" data-leads-workflow="warm">Warm Outreach</a>
      </nav>
      <section className="leads-command-center operator-workflow-section react-lead-canvas">
        <div className="react-legacy-command-heading"><LegacyNode html={view.heading} /></div>
        <LeadStepper status={view.workflowStatus} steps={view.workflowSteps} />
        <WarmResearchPanel><SourcePanel html={view.source} /></WarmResearchPanel>
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
    script.src = __LEGACY_APP_ASSET_URL__;
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
      controlledTest: outer(senders, ".controlled-send-test-card"),
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
