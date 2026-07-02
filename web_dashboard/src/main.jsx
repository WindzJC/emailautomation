import React, { useEffect } from "react";
import { createRoot } from "react-dom/client";
import "./tailwind.css";

function StaticSurface({ html }) {
  return <div className="contents" dangerouslySetInnerHTML={{ __html: html }} />;
}

function AppHeader({ html }) {
  return <StaticSurface html={html} />;
}

function SendersDashboard({ html }) {
  return <StaticSurface html={html} />;
}

function LeadOpsDashboard({ html }) {
  return <StaticSurface html={html} />;
}

function AuthOverlay({ html }) {
  return <StaticSurface html={html} />;
}

function DashboardControllerBridge() {
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "/static/app.js?v=react-shell-20260702";
    script.dataset.dashboardController = "true";
    document.body.append(script);
    return () => script.remove();
  }, []);
  return null;
}

function readDashboardTemplate() {
  const template = document.getElementById("dashboard-template");
  if (!(template instanceof HTMLTemplateElement)) {
    throw new Error("Dashboard template is missing.");
  }

  const content = template.content.cloneNode(true);
  const header = content.querySelector(".app-rail");
  const senders = content.querySelector("#ops-view");
  const leadOps = content.querySelector("#leads-view");
  const auth = content.querySelector("#auth-overlay");
  if (!header || !senders || !leadOps || !auth) {
    throw new Error("Dashboard template is incomplete.");
  }

  return {
    header: header.outerHTML,
    senders: senders.outerHTML,
    leadOps: leadOps.outerHTML,
    auth: auth.outerHTML,
  };
}

export function DashboardApp({ template = readDashboardTemplate() }) {
  return (
    <>
      <div
        className="page booting react-dashboard min-h-screen bg-canvas text-ink"
        data-dashboard-ui="react-tailwind"
      >
        <div className="app-shell">
          <AppHeader html={template.header} />
          <main className="app-main">
            <SendersDashboard html={template.senders} />
            <LeadOpsDashboard html={template.leadOps} />
          </main>
        </div>
      </div>
      <AuthOverlay html={template.auth} />
      <DashboardControllerBridge />
    </>
  );
}

const root = document.getElementById("dashboard-root");
if (root) createRoot(root).render(<DashboardApp />);
