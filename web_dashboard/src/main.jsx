import React, { useEffect, useRef, useState } from "react";
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

const START_READY_TERMINAL_STATES = new Set(["COMPLETE", "FAILED"]);

function defaultFetch(...args) {
  return fetch(...args);
}

function defaultDashboardRefresh() {
  const refreshButton = document.getElementById("refresh-btn");
  if (refreshButton instanceof HTMLButtonElement && !refreshButton.disabled) {
    refreshButton.click();
  }
}

function startReadyItems(payload = {}) {
  const results = Array.isArray(payload.results) ? payload.results : [];
  if (results.length) return results;
  const ready = Array.isArray(payload.ready_profiles) ? payload.ready_profiles : [];
  const skipped = Array.isArray(payload.skipped_profiles) ? payload.skipped_profiles : [];
  return [...ready, ...skipped];
}

function activeStartReadyJob(payload = {}) {
  return payload.job || payload.active_job || null;
}

export function SenderStartControls({
  fetchImpl = defaultFetch,
  onDashboardRefresh = defaultDashboardRefresh,
  pollIntervalMs = 750,
}) {
  const [phase, setPhase] = useState("idle");
  const [payload, setPayload] = useState(null);
  const [message, setMessage] = useState("");
  const [jobId, setJobId] = useState("");
  const planInFlightRef = useRef(false);
  const postInFlightRef = useRef(false);
  const postAttemptedRef = useRef(false);
  const pollTimerRef = useRef(null);

  useEffect(() => {
    if (phase !== "polling" || !jobId) return undefined;
    let cancelled = false;

    const poll = async () => {
      try {
        const response = await fetchImpl(
          `/api/start-ready/status/${encodeURIComponent(jobId)}`,
        );
        const data = await response.json().catch(() => ({}));
        if (cancelled) return;
        if (!response.ok || data.ok === false || !data.job) {
          setMessage(data.message || `Start Ready status failed (${response.status}). Do not retry Start; inspect job and runtime state.`);
          setPhase("status_error");
          return;
        }
        const job = data.job;
        setPayload(job);
        const status = String(job.status || "").toUpperCase();
        setMessage(job.message || "Start Ready Senders is running.");
        if (START_READY_TERMINAL_STATES.has(status)) {
          setPhase("terminal");
          onDashboardRefresh();
          return;
        }
        pollTimerRef.current = window.setTimeout(poll, pollIntervalMs);
      } catch (error) {
        if (cancelled) return;
        setMessage(`Start Ready status is unavailable: ${error}. Do not retry Start; inspect job and runtime state.`);
        setPhase("status_error");
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [fetchImpl, jobId, onDashboardRefresh, phase, pollIntervalMs]);

  const beginPollingActiveJob = (data, fallbackMessage) => {
    const job = activeStartReadyJob(data);
    setPayload(job || data);
    setMessage(data.message || job?.message || fallbackMessage);
    postAttemptedRef.current = true;
    const activeJobId = String(job?.job_id || "").trim();
    if (activeJobId) {
      setJobId(activeJobId);
      setPhase("polling");
    } else {
      setPhase("conflict");
    }
  };

  const loadPlan = async () => {
    if (planInFlightRef.current || postInFlightRef.current || ["posting", "polling", "ambiguous", "conflict", "status_error"].includes(phase)) return;
    planInFlightRef.current = true;
    postAttemptedRef.current = false;
    setPhase("planning");
    setMessage("");
    try {
      const response = await fetchImpl("/api/start-ready");
      const data = await response.json().catch(() => ({}));
      if (response.status === 409) {
        beginPollingActiveJob(data, "A Start Ready job is already active. No new Start request was submitted.");
        return;
      }
      if (!response.ok || data.ok === false) {
        setPayload(data);
        setMessage(data.message || `Readiness request failed (${response.status}).`);
        setPhase("error");
        return;
      }
      setPayload(data);
      const ready = Array.isArray(data.ready_profiles) ? data.ready_profiles : [];
      if (!ready.length) {
        setMessage("No pending sender work. Review the skipped-profile reasons below.");
        setPhase("empty");
        return;
      }
      setMessage(data.message || "Review the authoritative plan, then confirm the single Start Ready transaction.");
      setPhase("confirm");
    } catch (error) {
      setMessage(`Unable to load Start Ready readiness: ${error}`);
      setPhase("error");
    } finally {
      planInFlightRef.current = false;
    }
  };

  const confirmStart = async () => {
    if (phase !== "confirm" || postInFlightRef.current || postAttemptedRef.current) return;
    postInFlightRef.current = true;
    postAttemptedRef.current = true;
    setPhase("posting");
    setMessage("Submitting one Start Ready transaction...");
    let response;
    let data;
    try {
      response = await fetchImpl("/api/start-ready", { method: "POST" });
      data = await response.json().catch(() => ({}));
    } catch (error) {
      setMessage(`Start request outcome is unknown: ${error}. Do not retry. Inspect the Start Ready job and sender runtime state.`);
      setPhase("ambiguous");
      postInFlightRef.current = false;
      return;
    }
    postInFlightRef.current = false;
    if (response.status === 409) {
      beginPollingActiveJob(data, "A Start Ready job is already active. The Start request will not be retried.");
      return;
    }
    if (response.status !== 202 || !response.ok || data.ok === false || !data.job?.job_id) {
      setPayload(data.job || data);
      setMessage(data.message || `Start request failed (${response.status}). No automatic retry was attempted.`);
      setPhase("error");
      return;
    }
    setPayload(data.job);
    setJobId(String(data.job.job_id));
    setMessage(data.job.message || "Start Ready job accepted.");
    setPhase("polling");
  };

  const cancelConfirmation = () => {
    if (phase !== "confirm" || postInFlightRef.current) return;
    setPhase("idle");
    setMessage("Start Ready Senders cancelled. No Start request was submitted.");
  };

  const readyCount = Array.isArray(payload?.ready_profiles)
    ? payload.ready_profiles.length
    : Number(payload?.ready_count || 0);
  const disabled = ["empty", "planning", "posting", "polling", "ambiguous", "conflict", "status_error"].includes(phase);
  const primaryLabel = phase === "planning"
    ? "Checking readiness..."
    : phase === "confirm"
      ? `Confirm Start ${readyCount} Senders`
      : phase === "posting"
        ? "Submitting Start Ready..."
        : phase === "polling"
          ? "Start Ready in progress..."
          : phase === "ambiguous"
            ? "Start outcome unknown"
            : phase === "conflict"
              ? "Start Ready already active"
              : phase === "status_error"
                ? "Inspect active Start Ready job"
                : "Start Ready Senders";
  const items = startReadyItems(payload || {});

  return (
    <div className="react-start-ready-control">
      <button
        id="start-ready-btn"
        className="btn btn-primary"
        type="button"
        disabled={disabled}
        onClick={phase === "confirm" ? confirmStart : loadPlan}
      >
        {primaryLabel}
      </button>
      {phase === "confirm" ? (
        <button className="btn btn-secondary" type="button" onClick={cancelConfirmation}>
          Cancel
        </button>
      ) : null}
      {phase === "empty" ? (
        <button className="btn btn-secondary" type="button" onClick={loadPlan}>
          Refresh readiness
        </button>
      ) : null}
      {(payload || message) ? (
        <section id="react-start-ready-status" className="start-ready-status react-start-ready-status" aria-live="polite">
          <div className="start-ready-head">
            <strong>{phase === "confirm" ? "Start Ready Senders review" : "Start Ready Senders"}</strong>
            {message ? <span>{message}</span> : null}
          </div>
          {items.length ? (
            <ul className="start-ready-list">
              {items.map((item, index) => {
                const status = String(item?.status || "SKIPPED").toUpperCase();
                const label = item?.label || item?.profile || "Sender";
                const pending = Number(item?.pending_count || 0).toLocaleString();
                return (
                  <li className={`start-ready-item status-${status.toLowerCase()}`} key={`${item?.profile || label}-${index}`}>
                    <span className="start-ready-item-state">{status}</span>
                    <strong>{label}</strong>
                    <span>{pending} pending{item?.reason ? ` · ${item.reason}` : ""}</span>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

export function CommandBar({ html }) {
  const controls = parse(html, {
    replace(node) {
      if (node?.attribs?.id === "start-ready-btn") {
        return <SenderStartControls />;
      }
      if (node?.attribs?.id === "start-ready-status") {
        return <React.Fragment />;
      }
      return undefined;
    },
  });
  return (
    <section className="react-command-bar react-global-controls" aria-label="Global sender controls">
      <div className="react-section-heading">
        <div>
          <p className="react-section-label">Current live operations</p>
          <span>Safety-gated fleet controls</span>
        </div>
        <span className="react-section-state">Secondary controls</span>
      </div>
      {controls}
    </section>
  );
}

export function FleetSummary({ children }) {
  return (
    <section className="react-metric-region react-fleet-summary" aria-label="Fleet operations summary">
      {children}
    </section>
  );
}

export function SenderTable() {
  return (
    <section className="react-sender-console" aria-label="Sender operations">
      <div className="sender-status-mount" aria-hidden="true" />
    </section>
  );
}

export function CompactProgress({ progress }) {
  return (
    <section className="react-senders-progress" aria-label="Run progress and alerts summary">
      <LegacyNode html={progress} />
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

export function ValidationTools({ html }) {
  return (
    <details className="react-validation-tools">
      <summary>
        <span>Validation Tools</span>
        <span>Controlled sender tests — no production recipient queues</span>
      </summary>
      <div className="react-validation-tools-body">
        <LegacyNode html={html} />
      </div>
    </details>
  );
}

export function OverviewDashboard({ view }) {
  return (
    <section id="overview-view" className="dashboard-view workspace-view react-workspace react-overview-page" role="tabpanel" aria-labelledby="overview-tab-btn">
      <PageHeading
        eyebrow="Operations"
        title="Overview"
        description="Current queue health, live runtime, and the next authorized action."
        aside={<StatusPill tone="live">Live operations</StatusPill>}
      />
      <FleetSummary>
        <LegacyNode html={view.metrics} />
      </FleetSummary>
      <div className="react-overview-live-grid">
        <CommandBar html={view.commandBar} />
        <CompactProgress progress={view.progress} />
      </div>
      <section className="react-overview-next-action panel-shell" aria-label="Next action guidance">
        <p className="react-section-label">Next action</p>
        <strong>Start a qualified sender only when authorized.</strong>
        <span>Readiness means a sender is qualified to start. Runtime shows whether it is currently running or stopped.</span>
      </section>
    </section>
  );
}

export function SendersDashboard({ view }) {
  return (
    <section id="senders-view" className="dashboard-view workspace-view react-workspace react-senders-page hidden" role="tabpanel" aria-labelledby="senders-tab-btn" hidden>
      <PageHeading
        eyebrow="Delivery authority"
        title="Senders"
        description="Sender rows show runtime separately from readiness. READY means qualified to start; STOPPED means runtime inactive."
        aside={<StatusPill tone="live">Row controls</StatusPill>}
      />
      <SenderTable />
      <section className="react-supporting-panels react-sender-detail-panels">
        <LegacyNode html={view.profileDetail} />
      </section>
    </section>
  );
}

export function HistoryDashboard({ view }) {
  return (
    <section id="history-view" className="dashboard-view workspace-view react-workspace react-history-page hidden" role="tabpanel" aria-labelledby="history-tab-btn" hidden>
      <PageHeading
        eyebrow="Records"
        title="History"
        description="Recent campaign runs, previews, validations, and start activity."
      />
      <LegacyNode html={view.history} />
    </section>
  );
}

export function DiagnosticsDashboard({ view }) {
  return (
    <section id="diagnostics-view" className="dashboard-view workspace-view react-workspace react-diagnostics-page hidden" role="tabpanel" aria-labelledby="diagnostics-tab-btn" hidden>
      <PageHeading
        eyebrow="System"
        title="Diagnostics"
        description="Expanded alerts, run progress, environment safety, and controlled sender validation."
      />
      <LegacyNode html={view.progressDetails} />
      {view.controlledTest ? <ValidationTools html={view.controlledTest} /> : null}
      <section className="react-diagnostics-note panel-shell">
        <p className="react-section-label">Sender diagnostics</p>
        <strong>Profile Detail remains available on Senders.</strong>
        <span>Use the selected sender detail panel for focused delivery flow and advanced diagnostics.</span>
      </section>
    </section>
  );
}

export function LeadStepper({ status, steps }) {
  return (
    <section className="operator-stepper" aria-label="Current workflow progress">
      <div className="react-stepper-shell react-workflow-status-rail react-cold-copy">
        <LegacyNode html={steps} />
      </div>
      <LegacyNode html={status} />

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
    <section id="leads-view" className="dashboard-view workspace-view leads-workspace react-workspace react-leads-page hidden" role="tabpanel" aria-labelledby="campaigns-tab-btn" hidden>
      <PageHeading
        eyebrow="Campaigns"
        title={(
          <>
            <span className="react-cold-copy">Cold Campaigns</span>
            <span className="react-warm-copy">Warm Outreach</span>
          </>
        )}
        description={(
          <>
            <span className="react-cold-copy">Current live queue is separate from the next staged campaign workflow.</span>
            <span className="react-warm-copy">Upload a qualified warm batch, validate each lead, review the evidence and personalization, preview the exact email, then explicitly confirm.</span>
          </>
        )}
        aside={<StatusPill tone="safe">Safety gated</StatusPill>}
      />
      <nav id="leads-workflow-nav" className="leads-workflow-nav" aria-label="Lead Ops workflows">
        <a href="/?tab=campaigns&amp;workflow=cold" data-leads-workflow="cold">Cold Campaigns</a>
        <a href="/?tab=campaigns&amp;workflow=warm" data-leads-workflow="warm">Warm Outreach</a>
      </nav>
      <section className="react-current-staged-legend panel-shell" aria-label="Current and staged campaign state">
        <div>
          <p className="react-section-label">Current / live</p>
          <strong>Confirmed queues and running senders</strong>
          <span>Finish the current live queue before confirming a new JC dispatch.</span>
        </div>
        <div>
          <p className="react-section-label">Next / staged</p>
          <strong>Upload, validate, preview, confirm</strong>
          <span>These gates prepare the next campaign without changing live runtime.</span>
        </div>
      </section>
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
          <OverviewDashboard view={template.senders} />
          <LeadOpsDashboard view={template.leadOps} />
          <SendersDashboard view={template.senders} />
          <HistoryDashboard view={template.senders} />
          <DiagnosticsDashboard view={template.senders} />
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
      controlledTest: Array.from(
        senders.querySelectorAll(".controlled-send-test-card"),
      ).map((node) => node.outerHTML).join(""),
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
