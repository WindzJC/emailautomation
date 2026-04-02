const els = {
  page: document.querySelector(".page"),
  opsView: document.getElementById("ops-view"),
  leadsView: document.getElementById("leads-view"),
  opsTabBtn: document.getElementById("ops-tab-btn"),
  leadsTabBtn: document.getElementById("leads-tab-btn"),
  wsIndicator: document.getElementById("ws-indicator"),
  wsLabel: document.getElementById("ws-label"),
  healthBanner: document.getElementById("health-banner"),
  alertsGrid: document.getElementById("alerts-grid"),
  alertsCaption: document.getElementById("alerts-caption"),
  summaryGrid: document.getElementById("summary-grid"),
  privateBounceCaption: document.getElementById("private-bounce-caption"),
  privateBounceStatus: document.getElementById("private-bounce-status"),
  privateBounceEvents: document.getElementById("private-bounce-events"),
  trendsGrid: document.getElementById("trends-grid"),
  webhookHealth: document.getElementById("webhook-health"),
  webhookHealthCaption: document.getElementById("webhook-health-caption"),
  awaitingAging: document.getElementById("awaiting-aging"),
  domainBreakdown: document.getElementById("domain-breakdown"),
  domainBreakdownCaption: document.getElementById("domain-breakdown-caption"),
  overviewGrid: document.getElementById("overview-grid"),
  runStatusList: document.getElementById("run-status-list"),
  telemetryNotesList: document.getElementById("telemetry-notes-list"),
  latestFailures: document.getElementById("latest-failures"),
  detailCaption: document.getElementById("detail-caption"),
  detailProfileSelect: document.getElementById("detail-profile-select"),
  detailPrevBtn: document.getElementById("detail-prev-btn"),
  detailNextBtn: document.getElementById("detail-next-btn"),
  profileDetail: document.getElementById("profile-detail"),
  generatedAt: document.getElementById("generated-at"),
  toolbarGeneratedAt: document.getElementById("toolbar-generated-at"),
  hoursSelect: document.getElementById("hours-select"),
  tailSelect: document.getElementById("tail-select"),
  sendCapInput: document.getElementById("send-cap-input"),
  sendCapNote: document.getElementById("send-cap-note"),
  sendCapSaveBtn: document.getElementById("send-cap-save-btn"),
  refreshBtn: document.getElementById("refresh-btn"),
  wallboardBtn: document.getElementById("wallboard-btn"),
  startBtn: document.getElementById("start-btn"),
  stopBtn: document.getElementById("stop-btn"),
  archiveBtn: document.getElementById("archive-btn"),
  leadsImportantCheckBtn: document.getElementById("leads-important-check-btn"),
  leadsImportantCheckMeta: document.getElementById("leads-important-check-meta"),
  leadsImportantCheckResults: document.getElementById("leads-important-check-results"),
  leadsImportantDispatchBtn: document.getElementById("leads-important-dispatch-btn"),
  leadsImportantDispatchMeta: document.getElementById("leads-important-dispatch-meta"),
  leadsImportantDispatchResults: document.getElementById("leads-important-dispatch-results"),
  leadsUploadInput: document.getElementById("leads-upload-input"),
  leadsUploadBtn: document.getElementById("leads-upload-btn"),
  leadsUploadMeta: document.getElementById("leads-upload-meta"),
  leadsEmailColumn: document.getElementById("leads-email-column"),
  leadsAuthorColumn: document.getElementById("leads-author-column"),
  leadsBookColumn: document.getElementById("leads-book-column"),
  leadsUploadPreview: document.getElementById("leads-upload-preview"),
  cleanRemoveInvalid: document.getElementById("clean-remove-invalid"),
  cleanDedupe: document.getElementById("clean-dedupe"),
  cleanRemoveSuppressed: document.getElementById("clean-remove-suppressed"),
  cleanDropRole: document.getElementById("clean-drop-role"),
  cleanExcludeDomains: document.getElementById("clean-exclude-domains"),
  leadsCleanBtn: document.getElementById("leads-clean-btn"),
  leadsCleanMeta: document.getElementById("leads-clean-meta"),
  leadsCleanResults: document.getElementById("leads-clean-results"),
  leadsShardCount: document.getElementById("leads-shard-count"),
  leadsShardStrategy: document.getElementById("leads-shard-strategy"),
  leadsPreviewBtn: document.getElementById("leads-preview-btn"),
  leadsShardBtn: document.getElementById("leads-shard-btn"),
  leadsShardConfirm: document.getElementById("leads-shard-confirm"),
  leadsShardGuard: document.getElementById("leads-shard-guard"),
  leadsShardMeta: document.getElementById("leads-shard-meta"),
  leadsShardResults: document.getElementById("leads-shard-results"),
  leadsRefreshBtn: document.getElementById("leads-refresh-btn"),
  leadsStatusMeta: document.getElementById("leads-status-meta"),
  leadsStatusGrid: document.getElementById("leads-status-grid"),
  messageBar: document.getElementById("message-bar"),
};

let socket = null;
let lastSnapshot = null;
let lastLeadsStatus = null;
let lastShardPreview = null;
let lastImportantLeadCheck = null;
let lastImportantDispatch = null;
let didHydrate = false;
let selectedProfileName = "";
let displayTimeZone = "America/Los_Angeles";
let wallboardMode = false;
let activeDashboardTab = "ops";
const profileActionState = new Map();
const pendingProfileActions = new Map();

function currentActivityHours() {
  return els.hoursSelect?.value || "24";
}

function currentTailLines() {
  return els.tailSelect?.value || "12";
}

function setConnectionState(live) {
  els.wsIndicator.className = `dot ${live ? "dot-live" : "dot-off"}`;
  els.wsLabel.textContent = live ? "Live" : "Disconnected";
}

function showMessage(message, kind = "success") {
  if (!message) {
    els.messageBar.className = "message-bar hidden";
    els.messageBar.textContent = "";
    return;
  }
  els.messageBar.className = `message-bar ${kind}`;
  els.messageBar.textContent = message;
  setTimeout(() => {
    if (els.messageBar.textContent === message) {
      showMessage("");
    }
  }, 5000);
}

function readWallboardModeFromLocation() {
  const params = new URLSearchParams(window.location.search);
  return params.get("view") === "wallboard";
}

function readDashboardTabFromLocation() {
  const params = new URLSearchParams(window.location.search);
  return params.get("tab") === "leads" ? "leads" : "ops";
}

function syncLocationState() {
  const url = new URL(window.location.href);
  if (wallboardMode) {
    url.searchParams.set("view", "wallboard");
  } else {
    url.searchParams.delete("view");
  }
  if (activeDashboardTab === "leads" && !wallboardMode) {
    url.searchParams.set("tab", "leads");
  } else {
    url.searchParams.delete("tab");
  }
  window.history.replaceState({}, "", url);
}

function applyDashboardTab() {
  const leadsActive = activeDashboardTab === "leads" && !wallboardMode;
  if (els.opsView) {
    els.opsView.classList.toggle("hidden", leadsActive);
  }
  if (els.leadsView) {
    els.leadsView.classList.toggle("hidden", !leadsActive);
  }
  if (els.opsTabBtn) {
    els.opsTabBtn.classList.toggle("is-active", !leadsActive);
    els.opsTabBtn.setAttribute("aria-pressed", String(!leadsActive));
  }
  if (els.leadsTabBtn) {
    els.leadsTabBtn.classList.toggle("is-active", leadsActive);
    els.leadsTabBtn.setAttribute("aria-pressed", String(leadsActive));
  }
}

function applyWallboardMode() {
  if (els.page) {
    els.page.classList.toggle("wallboard-mode", wallboardMode);
  }
  if (els.wallboardBtn) {
    els.wallboardBtn.setAttribute("aria-pressed", String(wallboardMode));
    setNodeText(els.wallboardBtn, wallboardMode ? "Exit Wallboard" : "Wallboard");
  }
  if (wallboardMode) {
    activeDashboardTab = "ops";
  }
  applyDashboardTab();
  document.title = wallboardMode ? "Email Automation Wallboard" : "Email Automation Live Dashboard";
}

function setWallboardMode(nextMode) {
  wallboardMode = Boolean(nextMode);
  applyWallboardMode();
  syncLocationState();
}

function toggleWallboardMode() {
  setWallboardMode(!wallboardMode);
}

function setDashboardTab(nextTab) {
  activeDashboardTab = nextTab === "leads" ? "leads" : "ops";
  if (wallboardMode && activeDashboardTab === "leads") {
    wallboardMode = false;
    applyWallboardMode();
  } else {
    applyDashboardTab();
  }
  syncLocationState();
  if (activeDashboardTab === "leads") {
    fetchLeadsStatus();
  }
}

function formatGeneratedAt(value) {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  const stamp = new Intl.DateTimeFormat("sv-SE", {
    timeZone: displayTimeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(dt).replace(",", "");
  const zone = new Intl.DateTimeFormat("en-US", {
    timeZone: displayTimeZone,
    timeZoneName: "short",
  }).formatToParts(dt).find((part) => part.type === "timeZoneName")?.value || "";
  return zone ? `${stamp} ${zone}` : stamp;
}

function formatProfileName(value) {
  const raw = String(value || "")
    .replace(/^sendgrid_/, "")
    .replace(/^private_/, "")
    .replaceAll("_", " ")
    .trim();
  if (!raw) return "-";
  return raw
    .split(/\s+/)
    .map((part) => {
      if (!part) return "";
      if (part.toLowerCase() === "jc") return "JC";
      return part.charAt(0).toUpperCase() + part.slice(1);
    })
    .join(" ");
}

function isManualOnlyProfile(profile) {
  return String(profile?.name || "") === "private_jc";
}

function senderLogStatusLabel(status) {
  const labels = {
    SENT: "Accepted",
    SKIP: "Skipped",
    DRYRUN: "Dry Run",
    INVALID: "Invalid",
    ERROR: "Error",
    DAILY_CAP_REACHED: "Daily Cap Reached",
  };
  return labels[String(status || "").trim()] || (status || "-");
}

function profileCooldownRemaining(profile) {
  const remaining = Number(profile?.cooldown_remaining_seconds ?? 0);
  if (!Number.isFinite(remaining) || remaining <= 0) return 0;
  return Math.max(0, Math.round(remaining));
}

function profileAgeText(profile) {
  const remaining = profileCooldownRemaining(profile);
  if ((profile?.runtime_state || "") === "cooldown" && remaining > 0) {
    return `${remaining}s left`;
  }
  return profile?.last_age || "-";
}

function profileLastUpdateText(profile) {
  const remaining = profileCooldownRemaining(profile);
  if ((profile?.runtime_state || "") === "cooldown" && remaining > 0) {
    return `Cooldown ${remaining}s remaining`;
  }
  return `Last update ${profile?.last_age || "-"}`;
}

function profileLastAgeText(profile) {
  const remaining = profileCooldownRemaining(profile);
  if ((profile?.runtime_state || "") === "cooldown" && remaining > 0) {
    return `Next send in ${remaining}s`;
  }
  return profile?.last_age ? `Age ${profile.last_age}` : "No recent sender log line";
}

function formatPercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return `${(num * 100).toFixed(1)}%`;
}

function renderSummaryDetails(details = []) {
  if (!Array.isArray(details) || !details.length) return "";
  return `
    <div class="summary-details">
      ${details.map((item) => `
        <div class="summary-detail">
          <span class="summary-detail-label">${escapeHtml(item.label || "")}</span>
          <span class="summary-detail-value">${escapeHtml(item.value ?? "")}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function isSummaryTextValue(value) {
  const text = String(value ?? "");
  return /[A-Za-z]/.test(text) || text.length >= 8;
}

function summaryCard(label, value, note = "", details = []) {
  const valueClass = isSummaryTextValue(value) ? "summary-value summary-value-text" : "summary-value";
  return `
    <div class="summary-card summary-card-neutral">
      <div class="summary-head">
        <div class="summary-label">${label}</div>
        <span class="summary-spark summary-spark-neutral"></span>
      </div>
      <div class="${valueClass}">${value}</div>
      <div class="summary-note">${note}</div>
      ${renderSummaryDetails(details)}
    </div>
  `;
}

function elementFromHTML(html) {
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

function setNodeText(node, value) {
  if (!node) return;
  const next = String(value ?? "");
  if (node.textContent !== next) {
    node.textContent = next;
  }
}

function setNodeHtml(node, html) {
  if (!node) return;
  if (node.innerHTML !== html) {
    node.innerHTML = html;
  }
}

function parseDomainList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function activeSenderProfiles(snapshot = lastSnapshot) {
  return Array.isArray(snapshot?.profiles)
    ? snapshot.profiles.filter((profile) => ["starting", "running", "cooldown", "sleeping"].includes(profile?.runtime_state || ""))
    : [];
}

function currentShardPlanKey() {
  return [
    lastLeadsStatus?.latest_cleaned?.filename || "",
    String(els.leadsShardCount?.value || ""),
    els.leadsShardStrategy?.value || "domain_balanced",
  ].join("|");
}

function previewMatchesCurrentSelection() {
  return Boolean(lastShardPreview && lastShardPreview._preview_key === currentShardPlanKey());
}

function selectedLeadsMapping() {
  return {
    email: els.leadsEmailColumn?.value || "",
    author_name: els.leadsAuthorColumn?.value || "",
    book_title: els.leadsBookColumn?.value || "",
  };
}

async function fetchJson(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    const message = data.message || data.detail || `Request failed (${response.status}).`;
    throw new Error(message);
  }
  return data;
}

function renderLeadsMappingOptions(upload) {
  const fieldnames = Array.isArray(upload?.fieldnames) ? upload.fieldnames : [];
  const mapping = upload?.mapping || {};
  const selects = [
    { node: els.leadsEmailColumn, selected: mapping.email || "", allowEmpty: false },
    { node: els.leadsAuthorColumn, selected: mapping.author_name || "", allowEmpty: true },
    { node: els.leadsBookColumn, selected: mapping.book_title || "", allowEmpty: true },
  ];
  selects.forEach(({ node, selected, allowEmpty }) => {
    if (!node) return;
    const options = [];
    if (allowEmpty) {
      options.push(`<option value="">Not mapped</option>`);
    } else {
      options.push(`<option value="">Select column</option>`);
    }
    fieldnames.forEach((fieldname) => {
      options.push(
        `<option value="${escapeHtml(fieldname)}"${fieldname === selected ? " selected" : ""}>${escapeHtml(fieldname)}</option>`,
      );
    });
    setNodeHtml(node, options.join(""));
    if (selected && fieldnames.includes(selected)) {
      node.value = selected;
    }
  });
}

function renderLeadsPreview(upload) {
  const fieldnames = Array.isArray(upload?.fieldnames) ? upload.fieldnames : [];
  const rows = Array.isArray(upload?.preview_rows) ? upload.preview_rows : [];
  if (!fieldnames.length || !rows.length) {
    setNodeHtml(els.leadsUploadPreview, `<p class="muted">Upload a CSV to inspect the first ${25} rows here.</p>`);
    return;
  }
  setNodeHtml(
    els.leadsUploadPreview,
    `
      <table>
        <thead>
          <tr>${fieldnames.map((fieldname) => `<th>${escapeHtml(fieldname)}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>${fieldnames.map((fieldname) => `<td>${escapeHtml(row[fieldname] || "")}</td>`).join("")}</tr>
          `).join("")}
        </tbody>
      </table>
    `,
  );
}

function renderLeadsCleanResults(cleaned) {
  if (!cleaned) {
    setNodeHtml(els.leadsCleanResults, `<p class="muted">Clean results will appear here after the first run.</p>`);
    return;
  }
  const reasonCounts = cleaned.reason_counts || {};
  const removedDomains = cleaned.removed_domains_top || [];
  setNodeHtml(
    els.leadsCleanResults,
    `
      <article class="leads-result-card">
        <h3>Clean Report</h3>
        <div class="leads-kpis">
          <div class="leads-kpi"><div class="label">Input</div><div class="value">${Number(cleaned.input_rows || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Kept</div><div class="value">${Number(cleaned.output_rows || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Removed</div><div class="value">${Number(cleaned.removed_rows || 0)}</div></div>
        </div>
        <div class="table-shell">
          <table>
            <thead>
              <tr><th>Reason</th><th>Count</th></tr>
            </thead>
            <tbody>
              ${Object.keys(reasonCounts).length
                ? Object.entries(reasonCounts).map(([reason, count]) => `<tr><td>${escapeHtml(reason)}</td><td>${Number(count || 0)}</td></tr>`).join("")
                : `<tr><td>No removals</td><td>0</td></tr>`}
            </tbody>
          </table>
        </div>
        <div class="pill-row">
          ${(removedDomains.length ? removedDomains : []).map((item) => `<span class="mini-pill">${escapeHtml(item.domain)} ${Number(item.count || 0)}</span>`).join("") || `<span class="mini-pill">No removed domains</span>`}
        </div>
      </article>
    `,
  );
}

function renderImportantLeadCheck(result) {
  if (els.leadsImportantCheckMeta) {
    if (result?.generated_at_utc) {
      setNodeText(
        els.leadsImportantCheckMeta,
        `${result.input_label} checked into ${result.output_label}. Cleaned ${Number(result.cleaned_rows || 0)} row(s), rejected ${Number((result.input_rows || 0) - (result.cleaned_rows || 0))} row(s).`,
      );
    } else {
      setNodeText(
        els.leadsImportantCheckMeta,
        "Ready. Put raw leads in _important/leadschecker.csv, then click Check Leads.",
      );
    }
  }

  if (!result?.generated_at_utc) {
    setNodeHtml(
      els.leadsImportantCheckResults,
      `<p class="muted">Simple path: raw leads go in <strong>_important/leadschecker.csv</strong>, checked output lands in <strong>_important/leads.csv</strong>, and rejected rows land in <strong>_important/leads_rejected.csv</strong>.</p>`,
    );
    return;
  }

  const fieldnames = Array.isArray(result.output_fieldnames) ? result.output_fieldnames : [];
  const rows = Array.isArray(result.output_preview_rows) ? result.output_preview_rows : [];
  setNodeHtml(
    els.leadsImportantCheckResults,
    `
      <article class="leads-result-card">
        <h3>Check Result</h3>
        <div class="leads-kpis">
          <div class="leads-kpi"><div class="label">Input</div><div class="value">${Number(result.input_rows || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Cleaned</div><div class="value">${Number(result.cleaned_rows || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Duplicates</div><div class="value">${Number(result.duplicates_removed || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Invalid</div><div class="value">${Number(result.invalid_removed || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Suppressed</div><div class="value">${Number(result.suppressed_removed || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Suspicious</div><div class="value">${Number(result.suspicious_flagged || 0)}</div></div>
        </div>
        <div class="pill-row">
          <span class="mini-pill">Input ${escapeHtml(result.input_label || "-")}</span>
          <span class="mini-pill">Output ${escapeHtml(result.output_label || "-")}</span>
          <span class="mini-pill">Rejected ${escapeHtml(result.rejected_label || "-")}</span>
          <span class="mini-pill">Safe Fixes ${Number(result.safe_fixes_applied || 0)}</span>
        </div>
        ${
          Object.keys(result.reason_counts || {}).length
            ? `
              <div class="table-shell">
                <table>
                  <thead>
                    <tr><th>Reason</th><th>Count</th></tr>
                  </thead>
                  <tbody>
                    ${Object.entries(result.reason_counts || {}).map(([reason, count]) => `
                      <tr><td>${escapeHtml(reason)}</td><td>${Number(count || 0)}</td></tr>
                    `).join("")}
                  </tbody>
                </table>
              </div>
            `
            : ""
        }
        ${
          fieldnames.length && rows.length
            ? `
              <div class="table-shell">
                <table>
                  <thead>
                    <tr>${fieldnames.map((fieldname) => `<th>${escapeHtml(fieldname)}</th>`).join("")}</tr>
                  </thead>
                  <tbody>
                    ${rows.map((row) => `
                      <tr>${fieldnames.map((fieldname) => `<td>${escapeHtml(row[fieldname] || "")}</td>`).join("")}</tr>
                    `).join("")}
                  </tbody>
                </table>
              </div>
            `
            : `<p class="muted">No checked rows were written.</p>`
        }
      </article>
    `,
  );
}

function renderImportantDispatch(result) {
  const assignedSendgridTotal = Number(result?.assigned_sg1 || 0)
    + Number(result?.assigned_sg2 || 0)
    + Number(result?.assigned_sg3 || 0)
    + Number(result?.assigned_sg4 || 0)
    + Number(result?.assigned_sg5 || 0);
  if (els.leadsImportantDispatchMeta) {
    if (result?.generated_at_utc) {
      setNodeText(
        els.leadsImportantDispatchMeta,
        `Dispatched from ${result.master_label}. Astra ${Number(result.added_astra || 0)}, SendGrid ${assignedSendgridTotal}. Backup ${result.backup_dir || "-"}.`,
      );
    } else {
      setNodeText(
        els.leadsImportantDispatchMeta,
        "Dispatch is idle. Check the master file first, then dispatch while all senders are stopped.",
      );
    }
  }

  if (!result?.generated_at_utc) {
    setNodeHtml(
      els.leadsImportantDispatchResults,
      `<p class="muted">Dispatch reads <strong>_important/leads.csv</strong>, checks Astra and SendGrid separately, then adds each eligible lead to Astra, one SendGrid shard, or both.</p>`,
    );
    return;
  }

  const previewRows = Array.isArray(result.assigned_preview_rows) ? result.assigned_preview_rows : [];
  const previewFields = Array.isArray(result.queue_headers) ? result.queue_headers : [];
  setNodeHtml(
    els.leadsImportantDispatchResults,
    `
      <article class="leads-result-card">
        <h3>Dispatch Result</h3>
        <div class="leads-kpis">
          <div class="leads-kpi"><div class="label">Master Read</div><div class="value">${Number(result.master_read || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Added Astra</div><div class="value">${Number(result.added_astra || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Added SendGrid</div><div class="value">${Number(result.added_sendgrid || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Suppressed</div><div class="value">${Number(result.suppressed_skipped || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Skipped Both</div><div class="value">${Number(result.skipped_both || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Master Duplicates</div><div class="value">${Number(result.duplicate_master_skipped || 0)}</div></div>
        </div>
        <div class="table-shell">
          <table>
            <thead>
              <tr><th>Channel</th><th>Decision</th><th>Count</th></tr>
            </thead>
            <tbody>
              <tr><td>Astra</td><td>Added</td><td>${Number(result.added_astra || 0)}</td></tr>
              <tr><td>Astra</td><td>Already Sent</td><td>${Number(result.skipped_astra_already_sent || 0)}</td></tr>
              <tr><td>Astra</td><td>Already Queued</td><td>${Number(result.skipped_astra_already_queued || 0)}</td></tr>
              <tr><td>SendGrid</td><td>Added</td><td>${Number(result.added_sendgrid || 0)}</td></tr>
              <tr><td>SendGrid</td><td>Already Sent</td><td>${Number(result.skipped_sendgrid_already_sent || 0)}</td></tr>
              <tr><td>SendGrid</td><td>Already Queued</td><td>${Number(result.skipped_sendgrid_already_queued || 0)}</td></tr>
              <tr><td>Both</td><td>Skipped Both</td><td>${Number(result.skipped_both || 0)}</td></tr>
            </tbody>
          </table>
        </div>
        <div class="table-shell">
          <table>
            <thead>
              <tr><th>Queue</th><th>Assigned</th><th>Final Queue</th></tr>
            </thead>
            <tbody>
              <tr><td>Astra / JC</td><td>${Number(result.added_astra || 0)}</td><td>${Number(result.final_queue_counts?.jc || 0)}</td></tr>
              <tr><td>SG1</td><td>${Number(result.assigned_sg1 || 0)}</td><td>${Number(result.final_queue_counts?.sg1 || 0)}</td></tr>
              <tr><td>SG2</td><td>${Number(result.assigned_sg2 || 0)}</td><td>${Number(result.final_queue_counts?.sg2 || 0)}</td></tr>
              <tr><td>SG3</td><td>${Number(result.assigned_sg3 || 0)}</td><td>${Number(result.final_queue_counts?.sg3 || 0)}</td></tr>
              <tr><td>SG4</td><td>${Number(result.assigned_sg4 || 0)}</td><td>${Number(result.final_queue_counts?.sg4 || 0)}</td></tr>
              <tr><td>SG5</td><td>${Number(result.assigned_sg5 || 0)}</td><td>${Number(result.final_queue_counts?.sg5 || 0)}</td></tr>
            </tbody>
          </table>
        </div>
        <div class="pill-row">
          <span class="mini-pill">Astra + SendGrid allowed</span>
          <span class="mini-pill">Exactly one SG shard per lead</span>
          <span class="mini-pill">Backup ${escapeHtml(result.backup_dir || "-")}</span>
        </div>
        ${
          previewFields.length && previewRows.length
            ? `
              <div class="table-shell">
                <table>
                  <thead>
                    <tr>${previewFields.map((field) => `<th>${escapeHtml(field)}</th>`).join("")}</tr>
                  </thead>
                  <tbody>
                    ${previewRows.map((row) => `
                      <tr>${previewFields.map((field) => `<td>${escapeHtml(row[field] || "")}</td>`).join("")}</tr>
                    `).join("")}
                  </tbody>
                </table>
              </div>
            `
            : ""
        }
      </article>
    `,
  );
}

function renderLeadsShardResults(report) {
  if (!report) {
    setNodeHtml(els.leadsShardResults, `<p class="muted">Run Preview to inspect shard counts and domain mix before the first write.</p>`);
    return;
  }
  const shards = Array.isArray(report.per_shard) ? report.per_shard : [];
  const cleanSummary = report.clean_summary || {};
  const modeLabel = report.preview_only ? "Shard Preview" : "Shard Report";
  setNodeHtml(
    els.leadsShardResults,
    `
      <article class="leads-result-card">
        <h3>${modeLabel}</h3>
        <div class="leads-kpis">
          <div class="leads-kpi"><div class="label">Shards</div><div class="value">${Number(report.shard_count || shards.length || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Rows</div><div class="value">${Number(report.total_rows || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Canaries</div><div class="value">${Number(report.canary_rows_injected || 0)}</div></div>
          <div class="leads-kpi"><div class="label">Cleaned Rows</div><div class="value">${Number(cleanSummary.output_rows || report.input_rows || 0)}</div></div>
        </div>
        <div class="pill-row">
          <span class="mini-pill">Strategy ${escapeHtml(report.strategy || "domain_balanced")}</span>
          <span class="mini-pill">Canary ${report.canary_present ? "protected" : "missing"}</span>
          ${report.backup_dir ? `<span class="mini-pill">Backup ${escapeHtml(report.backup_dir)}</span>` : `<span class="mini-pill">Preview only</span>`}
        </div>
        <div class="table-shell">
          <table>
            <thead>
              <tr><th>Shard</th><th>Current</th><th>Planned</th><th>Delta</th><th>Top Domains</th></tr>
            </thead>
            <tbody>
              ${shards.map((item) => `
                <tr>
                  <td>${escapeHtml(item.name || "-")}</td>
                  <td>${Number(item.current_count || 0)}</td>
                  <td>${Number(item.count || 0)}</td>
                  <td>${Number(item.delta || 0) >= 0 ? "+" : ""}${Number(item.delta || 0)}</td>
                  <td>${(item.top_domains || []).map((domain) => `${escapeHtml(domain.domain)} ${Number(domain.count || 0)}`).join(", ") || "-"}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </article>
    `,
  );
}

function renderShardWriteGuard() {
  const activeProfiles = activeSenderProfiles(lastSnapshot);
  const previewReady = previewMatchesCurrentSelection();
  const confirmReady = String(els.leadsShardConfirm?.value || "").trim().toUpperCase() === "SHARD";
  const cleanedFilename = lastLeadsStatus?.latest_cleaned?.filename || "";
  const canPreview = Boolean(cleanedFilename);
  const canWrite = canPreview && !activeProfiles.length && previewReady && confirmReady;

  if (els.leadsPreviewBtn) {
    els.leadsPreviewBtn.disabled = !canPreview;
  }
  if (els.leadsShardBtn) {
    els.leadsShardBtn.disabled = !canWrite;
  }
  if (els.leadsShardGuard) {
    let message = "Run Preview first. Write is blocked while any sender is active.";
    if (!cleanedFilename) {
      message = "Run Clean first so there is a cleaned lead file to preview and write.";
    } else if (activeProfiles.length) {
      message = `Write blocked. Active senders: ${activeProfiles.map((profile) => `${formatProfileName(profile.name)} (${profile.runtime_state})`).join(", ")}.`;
    } else if (!previewReady) {
      message = "Run Preview for the current shard count and strategy before writing.";
    } else if (!confirmReady) {
      message = "Preview is ready. Type SHARD to enable Write Shards.";
    } else {
      message = "Ready to overwrite shard files with the current preview plan.";
    }
    setNodeText(els.leadsShardGuard, message);
  }
}

function renderLeadsStatus(status) {
  lastLeadsStatus = status || lastLeadsStatus;
  lastImportantLeadCheck = lastLeadsStatus?.latest_master_check || lastImportantLeadCheck;
  lastImportantDispatch = lastLeadsStatus?.latest_dispatch || lastImportantDispatch;
  renderImportantLeadCheck(lastImportantLeadCheck);
  renderImportantDispatch(lastImportantDispatch);

  const latestUpload = lastLeadsStatus?.latest_upload || null;
  const latestCleaned = lastLeadsStatus?.latest_cleaned || null;
  const latestShardReport = lastLeadsStatus?.latest_shard_report_summary || lastLeadsStatus?.latest_shard_report || null;
  renderLeadsMappingOptions(latestUpload);
  renderLeadsPreview(latestUpload);
  renderLeadsCleanResults(latestCleaned);
  renderLeadsShardResults(previewMatchesCurrentSelection() ? lastShardPreview : latestShardReport);

  if (els.leadsUploadMeta) {
    if (latestUpload?.saved_filename) {
      setNodeText(
        els.leadsUploadMeta,
        `${latestUpload.original_filename || latestUpload.saved_filename} saved as ${latestUpload.saved_filename}. ${Number(latestUpload.row_count || 0)} row(s).${latestUpload.mapping_required ? " Select the email column before cleaning." : ""}`,
      );
    } else {
      setNodeText(els.leadsUploadMeta, "No upload yet.");
    }
  }

  if (els.leadsCleanMeta) {
    if (latestCleaned?.filename) {
      setNodeText(
        els.leadsCleanMeta,
        `${latestCleaned.filename} from ${latestCleaned.source_original_filename || latestCleaned.source_upload_filename || "latest upload"} kept ${Number(latestCleaned.output_rows || 0)} row(s) and removed ${Number(latestCleaned.removed_rows || 0)}.`,
      );
    } else {
      setNodeText(els.leadsCleanMeta, "No clean report yet.");
    }
  }

  if (els.leadsShardMeta) {
    if (previewMatchesCurrentSelection() && lastShardPreview) {
      setNodeText(
        els.leadsShardMeta,
        `Preview ready for ${lastShardPreview.source_cleaned_filename || "cleaned leads"} using ${lastShardPreview.strategy || "domain_balanced"}. Review counts, then type SHARD to write.`,
      );
    } else if (lastLeadsStatus?.latest_shard_report?.report_path) {
      const shardMeta = lastLeadsStatus.latest_shard_report;
      setNodeText(
        els.leadsShardMeta,
        `Latest shard write used ${shardMeta.source_cleaned_filename || "unknown clean file"} with ${shardMeta.strategy || "domain_balanced"}. Backup: ${shardMeta.backup_dir || "-"}.`,
      );
    } else if (latestCleaned?.filename) {
      setNodeText(els.leadsShardMeta, `Ready to shard ${latestCleaned.filename}.`);
    } else {
      setNodeText(els.leadsShardMeta, "No shard write yet.");
    }
  }

  if (els.leadsStatusMeta) {
    const updatedAt = lastLeadsStatus?.last_updated_utc ? formatGeneratedAt(lastLeadsStatus.last_updated_utc) : "-";
    setNodeText(
      els.leadsStatusMeta,
      `Current shard total ${Number(lastLeadsStatus?.total_rows || 0)}. Last shard file update ${updatedAt}.`,
    );
  }

  const shards = Array.isArray(lastLeadsStatus?.current_shards) ? lastLeadsStatus.current_shards : [];
  setNodeHtml(
    els.leadsStatusGrid,
    shards.length
      ? shards.map((item) => `
          <article class="leads-status-card">
            <h3>${escapeHtml(item.name || "-")}</h3>
            <div class="leads-kpis">
              <div class="leads-kpi"><div class="label">Rows</div><div class="value">${Number(item.count || 0)}</div></div>
              <div class="leads-kpi"><div class="label">Updated</div><div class="value">${escapeHtml(item.last_updated_utc ? formatGeneratedAt(item.last_updated_utc) : "-")}</div></div>
            </div>
            <div class="pill-row">
              ${(item.top_domains || []).map((domain) => `<span class="mini-pill">${escapeHtml(domain.domain)} ${Number(domain.count || 0)}</span>`).join("") || `<span class="mini-pill">No domains yet</span>`}
            </div>
            <div class="muted">${escapeHtml(item.path || "-")}</div>
          </article>
        `).join("")
      : `<p class="muted">No shard files detected yet.</p>`,
  );
  renderShardWriteGuard();
}

async function fetchLeadsStatus() {
  try {
    const data = await fetchJson("/api/leads/status");
    renderLeadsStatus(data.status || {});
  } catch (err) {
    if (activeDashboardTab === "leads") {
      showMessage(`Leads status failed: ${err}`, "error");
    }
  }
}

async function runImportantLeadCheck() {
  if (els.leadsImportantCheckBtn) {
    els.leadsImportantCheckBtn.disabled = true;
    setNodeText(els.leadsImportantCheckBtn, "Checking...");
  }
  try {
    const data = await fetchJson("/api/leads/check-important", { method: "POST" });
    lastImportantLeadCheck = data.check || null;
    if (data.status) {
      renderLeadsStatus(data.status || {});
    } else {
      renderImportantLeadCheck(lastImportantLeadCheck);
    }
    showMessage(data.message || "Quick lead check complete.", "success");
  } catch (err) {
    showMessage(`Quick lead check failed: ${err}`, "error");
  } finally {
    if (els.leadsImportantCheckBtn) {
      els.leadsImportantCheckBtn.disabled = false;
      setNodeText(els.leadsImportantCheckBtn, "Check Leads");
    }
  }
}

async function runImportantLeadDispatch() {
  if (els.leadsImportantDispatchBtn) {
    els.leadsImportantDispatchBtn.disabled = true;
    setNodeText(els.leadsImportantDispatchBtn, "Dispatching...");
  }
  try {
    const data = await fetchJson("/api/leads/dispatch-important", {
      method: "POST",
    });
    lastImportantDispatch = data.dispatch || null;
    renderImportantLeadCheck(lastImportantLeadCheck);
    if (data.status) {
      renderLeadsStatus(data.status || {});
    } else {
      renderImportantDispatch(lastImportantDispatch);
    }
    if (data.snapshot) {
      renderSnapshot(data.snapshot);
    }
    showMessage(data.message || "Lead dispatch complete.", "success");
  } catch (err) {
    showMessage(`Lead dispatch failed: ${err}`, "error");
  } finally {
    if (els.leadsImportantDispatchBtn) {
      els.leadsImportantDispatchBtn.disabled = false;
      setNodeText(els.leadsImportantDispatchBtn, "Dispatch Leads");
    }
  }
}

function syncKeyedChildren(container, items, keyFn, createFn, updateFn) {
  if (!container) return;
  const existing = new Map(
    Array.from(container.children)
      .map((node) => [node.dataset.key || "", node])
      .filter(([key]) => key),
  );
  const used = new Set();
  items.forEach((item, index) => {
    const key = keyFn(item, index);
    let node = existing.get(key);
    if (!node) {
      node = createFn(item, key);
      node.dataset.key = key;
    }
    updateFn(node, item, index);
    const current = container.children[index];
    if (current !== node) {
      container.insertBefore(node, current || null);
    }
    used.add(key);
  });
  existing.forEach((node, key) => {
    if (!used.has(key)) node.remove();
  });
}

function createLiveMetricNode() {
  const node = elementFromHTML(`
    <div class="live-metric live-neutral">
      <div class="label"></div>
      <div class="value"></div>
    </div>
  `);
  node._refs = {
    label: node.querySelector(".label"),
    value: node.querySelector(".value"),
  };
  return node;
}

function updateLiveMetricNode(node, label, value, tone = "neutral") {
  const refs = node._refs || {
    label: node.querySelector(".label"),
    value: node.querySelector(".value"),
  };
  node._refs = refs;
  node.className = `live-metric live-${tone}`;
  setNodeText(refs.label, label);
  setNodeText(refs.value, value);
}

function createMetricNode() {
  const node = elementFromHTML(`
    <div class="metric">
      <div class="label"></div>
      <div class="value"></div>
    </div>
  `);
  node._refs = {
    label: node.querySelector(".label"),
    value: node.querySelector(".value"),
  };
  return node;
}

function updateMetricNode(node, label, value) {
  const refs = node._refs || {
    label: node.querySelector(".label"),
    value: node.querySelector(".value"),
  };
  node._refs = refs;
  setNodeText(refs.label, label);
  setNodeText(refs.value, value);
}

function createOverviewStatNode() {
  const node = elementFromHTML(`
    <div class="overview-stat">
      <span class="label"></span>
      <span class="value"></span>
    </div>
  `);
  node._refs = {
    label: node.querySelector(".label"),
    value: node.querySelector(".value"),
  };
  return node;
}

function updateOverviewStatNode(node, label, value) {
  const refs = node._refs || {
    label: node.querySelector(".label"),
    value: node.querySelector(".value"),
  };
  node._refs = refs;
  setNodeText(refs.label, label);
  setNodeText(refs.value, value);
}

function createOverviewChipNode() {
  const node = elementFromHTML(`<span class="overview-chip"></span>`);
  node._refs = { value: node };
  return node;
}

function updateOverviewChipNode(node, value) {
  setNodeText(node._refs?.value || node, value);
}

function humanizeSecondsAge(totalSeconds) {
  const seconds = Number(totalSeconds);
  if (!Number.isFinite(seconds) || seconds < 0) return "-";
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function humanizeCooldownRemaining(totalSeconds) {
  const seconds = Number(totalSeconds);
  if (!Number.isFinite(seconds) || seconds <= 0) return "Off";
  if (seconds < 60) return `${Math.max(1, Math.ceil(seconds))}s left`;
  const minutes = Math.ceil(seconds / 60);
  if (minutes < 60) return `${minutes}m left`;
  const hours = Math.ceil(minutes / 60);
  return `${hours}h left`;
}

function privateBounceSummaryCard(guard = {}) {
  const status = String(guard?.status || "idle");
  let tone = "neutral";
  if (status === "watching") tone = "good";
  else if (status === "cooldown" || (guard?.sync_stale && guard?.profile_active)) tone = "warn";
  else if (status === "error") tone = "bad";

  const lastSync = guard?.last_sync_utc
    ? (guard?.last_sync_age_seconds == null ? "Just now" : humanizeSecondsAge(guard.last_sync_age_seconds))
    : "Never";

  const cooldownDetail = guard?.cooldown_active
    ? { label: "Until", value: guard?.cooldown_until_utc ? formatGeneratedAt(guard.cooldown_until_utc) : humanizeCooldownRemaining(guard?.cooldown_remaining_seconds || 0) }
    : { label: "Cooldown", value: "Off" };

  return {
    key: "private_bounce_guard",
    label: "JC Bounce Guard",
    value: guard?.status_label || "Idle",
    note: guard?.status_note || "Automatic private bounce sync, suppressions, and cooldown protection.",
    tone,
    details: [
      { label: "Last Sync", value: lastSync },
      { label: "Suppressed", value: Number(guard?.last_added_suppressed || 0).toLocaleString() },
      { label: "Recent", value: `${Number(guard?.recent_bounces_window || 0)}/${Number(guard?.bounce_threshold || 0)} in ${Number(guard?.window_minutes || 0)}m` },
      cooldownDetail,
    ],
  };
}

function privateBounceTone(guard = {}) {
  const status = String(guard?.status || "idle");
  if (status === "watching") return "good";
  if (status === "cooldown" || (guard?.sync_stale && guard?.profile_active)) return "warn";
  if (status === "error") return "bad";
  return "neutral";
}

function renderPrivateBounceGuard(snapshot) {
  const guard = snapshot.private_bounce_guard || {};
  if (!els.privateBounceStatus || !els.privateBounceEvents) return;
  const tone = privateBounceTone(guard);
  const lastSyncText = guard?.last_sync_utc ? formatGeneratedAt(guard.last_sync_utc) : "Never";
  const cooldownUntilText = guard?.cooldown_until_utc ? formatGeneratedAt(guard.cooldown_until_utc) : "Not cooling down";
  const lastSuppressed = Array.isArray(guard?.last_suppressed_addresses) ? guard.last_suppressed_addresses : [];
  const recentPreview = Array.isArray(guard?.recent_bounce_preview) ? guard.recent_bounce_preview : [];
  if (els.privateBounceCaption) {
    const suffix = guard?.last_sync_utc ? `Last sync ${lastSyncText}.` : "No successful private bounce sync yet.";
    setNodeText(els.privateBounceCaption, `${guard?.status_note || "Automatic private bounce sync, suppression, and clustered-bounce cooldown protection."} ${suffix}`);
  }
  setNodeHtml(
    els.privateBounceStatus,
    `
      <article class="bounce-guard-card bounce-guard-card-${tone}">
        <div class="bounce-guard-kicker">Status</div>
        <div class="bounce-guard-value">${escapeHtml(guard?.status_label || "Idle")}</div>
        <p class="bounce-guard-note">${escapeHtml(guard?.status_note || "Automatic private bounce sync, suppression, and cooldown protection.")}</p>
      </article>
      <article class="bounce-guard-card">
        <div class="bounce-guard-kicker">Last Sync</div>
        <div class="bounce-guard-inline">${escapeHtml(lastSyncText)}</div>
        <p class="bounce-guard-note">Scanned ${Number(guard?.last_scanned_messages || 0)} message(s), matched ${Number(guard?.last_matched_messages || 0)} bounce(s).</p>
      </article>
      <article class="bounce-guard-card">
        <div class="bounce-guard-kicker">Last Suppression</div>
        <div class="bounce-guard-inline">${Number(guard?.last_added_suppressed || 0)} added</div>
        <div class="pill-row">
          ${lastSuppressed.length ? lastSuppressed.slice(0, 5).map((email) => `<span class="mini-pill">${escapeHtml(email)}</span>`).join("") : `<span class="mini-pill">No new addresses</span>`}
        </div>
      </article>
      <article class="bounce-guard-card">
        <div class="bounce-guard-kicker">Cooldown</div>
        <div class="bounce-guard-inline">${escapeHtml(cooldownUntilText)}</div>
        <p class="bounce-guard-note">Recent bounces ${Number(guard?.recent_bounces_window || 0)}/${Number(guard?.bounce_threshold || 0)} in ${Number(guard?.window_minutes || 0)} minute(s).</p>
        ${recentPreview.length ? `<div class="pill-row">${recentPreview.slice(0, 5).map((email) => `<span class="mini-pill">${escapeHtml(email)}</span>`).join("")}</div>` : ""}
      </article>
    `,
  );

  const events = Array.isArray(guard?.events) ? guard.events : [];
  setNodeHtml(
    els.privateBounceEvents,
    events.length
      ? `
        <div class="bounce-guard-events-list">
          ${events.slice(0, 10).map((event) => {
            const severity = String(event?.severity || "info");
            const addresses = Array.isArray(event?.addresses) ? event.addresses.filter(Boolean) : [];
            const cooldownUntil = event?.cooldown_until_utc ? formatGeneratedAt(event.cooldown_until_utc) : "";
            return `
              <article class="bounce-guard-event bounce-guard-event-${escapeHtml(severity)}">
                <div class="bounce-guard-event-head">
                  <div>
                    <h3>${escapeHtml(event?.title || "Event")}</h3>
                    <p class="muted">${escapeHtml(event?.occurred_at_utc ? formatGeneratedAt(event.occurred_at_utc) : "-")}</p>
                  </div>
                  <span class="mini-pill">${escapeHtml(String(event?.event_type || "event").replaceAll("_", " "))}</span>
                </div>
                <p class="bounce-guard-event-message">${escapeHtml(event?.message || "")}</p>
                ${cooldownUntil ? `<p class="bounce-guard-event-meta">Cooldown until ${escapeHtml(cooldownUntil)}</p>` : ""}
                ${addresses.length ? `<div class="pill-row">${addresses.slice(0, 6).map((email) => `<span class="mini-pill">${escapeHtml(email)}</span>`).join("")}</div>` : ""}
              </article>
            `;
          }).join("")}
        </div>
      `
      : `<p class="muted">No private bounce guard events yet.</p>`,
  );
}

function createSelectOptionNode() {
  return document.createElement("option");
}

function updateSelectOptionNode(node, value, label) {
  if (node.value !== value) {
    node.value = value;
  }
  setNodeText(node, label);
}

function renderSummary(snapshot) {
  const summary = snapshot.summary;
  const cards = [
    { key: "session", label: "Session", value: snapshot.session_label.toUpperCase(), note: "tmux session state" },
    { key: "active_profiles", label: "Active Profiles", value: summary.active_profiles, note: "currently sending" },
    {
      key: "pending",
      label: "Pending",
      value: summary.total_pending,
      note: "queued recipients across Astra + SendGrid",
      details: [
        { label: "Astra", value: Number(summary.astra_pending || 0).toLocaleString() },
        { label: "SendGrid", value: Number(summary.sendgrid_pending || 0).toLocaleString() },
      ],
    },
    privateBounceSummaryCard(snapshot.private_bounce_guard || {}),
    { key: "accepted", label: "Accepted", value: summary.total_run_sent, note: "API accepted this run" },
    { key: "alerts", label: "Alerts", value: summary.active_alerts || 0, note: "needs attention" },
    { key: "api_errors", label: "API Errors", value: summary.total_run_errors, note: "sender-side issues" },
  ];
  syncKeyedChildren(
    els.summaryGrid,
    cards,
    (card) => card.key,
    (card) => {
      const node = elementFromHTML(summaryCard(card.label, card.value, card.note, card.details || []));
      node._refs = {
        label: node.querySelector(".summary-label"),
        value: node.querySelector(".summary-value"),
        note: node.querySelector(".summary-note"),
        details: node.querySelector(".summary-details"),
        spark: node.querySelector(".summary-spark"),
      };
      return node;
    },
    (node, card) => {
      const refs = node._refs;
      node.className = `summary-card summary-card-${card.tone || "neutral"}`;
      if (refs.spark) refs.spark.className = `summary-spark summary-spark-${card.tone || "neutral"}`;
      setNodeText(refs.label, card.label);
      setNodeText(refs.value, card.value);
      setNodeText(refs.note, card.note);
      refs.value.classList.toggle("summary-value-text", isSummaryTextValue(card.value));
      setNodeHtml(refs.details, renderSummaryDetails(card.details || []));
    },
  );
}

function createAlertCardNode() {
  const node = elementFromHTML(`
    <article class="alert-card alert-warn">
      <div class="alert-head">
        <span class="alert-pill"></span>
        <h3></h3>
      </div>
      <p class="alert-message"></p>
    </article>
  `);
  node._refs = {
    pill: node.querySelector(".alert-pill"),
    title: node.querySelector("h3"),
    message: node.querySelector(".alert-message"),
  };
  return node;
}

function updateAlertCardNode(node, alert) {
  const refs = node._refs || {
    pill: node.querySelector(".alert-pill"),
    title: node.querySelector("h3"),
    message: node.querySelector(".alert-message"),
  };
  node._refs = refs;
  const severity = alert?.severity || "warn";
  node.className = `alert-card alert-${severity}`;
  refs.pill.className = `alert-pill alert-pill-${severity}`;
  setNodeText(refs.pill, severity === "critical" ? "Critical" : severity === "ok" ? "Healthy" : "Watch");
  setNodeText(refs.title, alert?.title || "Alert");
  setNodeText(refs.message, alert?.message || "");
}

function renderAlerts(snapshot) {
  if (!els.alertsGrid) return;
  const activeAlerts = Array.isArray(snapshot.alerts) ? snapshot.alerts : [];
  const cards = activeAlerts.length
    ? activeAlerts
    : [{ key: "ok", severity: "ok", title: "No active threshold alerts", message: "Current metrics are below the configured alert thresholds." }];
  syncKeyedChildren(
    els.alertsGrid,
    cards,
    (alert, index) => alert.key || `${alert.severity}-${alert.title || index}`,
    () => createAlertCardNode(),
    (node, alert) => updateAlertCardNode(node, alert),
  );
  if (els.alertsCaption) {
    setNodeText(
      els.alertsCaption,
      activeAlerts.length
        ? `${activeAlerts.length} threshold alert${activeAlerts.length === 1 ? "" : "s"} active.`
        : "Operational thresholds for failures, backlog, webhook intake, and attribution.",
    );
  }
}

function sparklineSvg(points, tone = "neutral") {
  const values = Array.isArray(points) && points.length ? points.map((value) => Number(value) || 0) : [0];
  const width = 164;
  const height = 44;
  const pad = 4;
  const maxValue = Math.max(...values, 1);
  const step = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0;
  const coordinates = values.map((value, index) => {
    const x = pad + step * index;
    const y = height - pad - ((value / maxValue) * (height - pad * 2));
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  const areaPoints = [`${pad},${height - pad}`, ...coordinates, `${width - pad},${height - pad}`].join(" ");
  const toneClass = `sparkline-${tone}`;
  return `
    <svg class="sparkline ${toneClass}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <polyline class="sparkline-area" points="${areaPoints}"></polyline>
      <polyline class="sparkline-line" points="${coordinates.join(" ")}"></polyline>
      <circle class="sparkline-dot" cx="${coordinates[coordinates.length - 1].split(",")[0]}" cy="${coordinates[coordinates.length - 1].split(",")[1]}" r="2.8"></circle>
    </svg>
  `;
}

function trendTone(metricKey) {
  if (metricKey === "failures") return "bad";
  if (metricKey === "accepted") return "accent";
  if (metricKey === "delivered" || metricKey === "opened") return "good";
  return "neutral";
}

function createTrendCardNode() {
  const node = elementFromHTML(`
    <article class="trend-card">
      <div class="trend-head">
        <div>
          <div class="trend-label"></div>
          <div class="trend-caption"></div>
        </div>
      </div>
      <div class="trend-window trend-window-24h"></div>
      <div class="trend-window trend-window-7d"></div>
    </article>
  `);
  node._refs = {
    label: node.querySelector(".trend-label"),
    caption: node.querySelector(".trend-caption"),
    trend24h: node.querySelector(".trend-window-24h"),
    trend7d: node.querySelector(".trend-window-7d"),
  };
  return node;
}

function renderTrendWindow(windowLabel, metric, tone, bucketSuffix) {
  const points = metric?.points || [];
  const total = metric?.total || 0;
  const latest = points.length ? points[points.length - 1] : 0;
  return `
    <div class="trend-meta">
      <span>${windowLabel}</span>
      <strong>${total}</strong>
      <span class="muted">latest ${latest}/${bucketSuffix}</span>
    </div>
    ${sparklineSvg(points, tone)}
  `;
}

function updateTrendCardNode(node, item, trends) {
  const refs = node._refs || {
    label: node.querySelector(".trend-label"),
    caption: node.querySelector(".trend-caption"),
    trend24h: node.querySelector(".trend-window-24h"),
    trend7d: node.querySelector(".trend-window-7d"),
  };
  node._refs = refs;
  const trend24h = trends?.["24h"]?.metrics?.[item.key] || {};
  const trend7d = trends?.["7d"]?.metrics?.[item.key] || {};
  const tone = trendTone(item.key);
  setNodeText(refs.label, item.label);
  setNodeText(refs.caption, item.caption);
  setNodeHtml(refs.trend24h, renderTrendWindow("24h", trend24h, tone, "hour"));
  setNodeHtml(refs.trend7d, renderTrendWindow("7d", trend7d, tone, "day"));
}

function renderTrends(snapshot) {
  if (!els.trendsGrid) return;
  const trendItems = [
    { key: "accepted", label: "Accepted", caption: "sender log handoff" },
    { key: "delivered", label: "Delivered", caption: "SendGrid confirmed" },
    { key: "failures", label: "Failures", caption: "bounce, block, drop, spam" },
    { key: "opened", label: "Opened", caption: "tracking pixel fired" },
  ];
  const trends = snapshot.trends || {};
  syncKeyedChildren(
    els.trendsGrid,
    trendItems,
    (item) => item.key,
    () => createTrendCardNode(),
    (node, item) => updateTrendCardNode(node, item, trends),
  );
}

function renderHealth(snapshot) {
  if (!els.healthBanner) return;
  const state = snapshot.health?.state || "yellow";
  const message = snapshot.health?.message || "No status available.";
  els.healthBanner.className = `health-banner health-${state}`;
  els.healthBanner.textContent = message;
}

function resolveSelectedProfile(snapshot) {
  const profiles = snapshot.profiles || [];
  if (!profiles.length) return null;
  const existing = profiles.find((profile) => profile.name === selectedProfileName);
  if (existing) return existing;
  const preferred =
    profiles.find((profile) => profile.tmux_running) ||
    profiles.find((profile) => profile.tmux_dead) ||
    profiles.find((profile) => (profile.webhook?.summary?.failed || 0) > 0) ||
    profiles[0];
  selectedProfileName = preferred.name;
  return preferred;
}

function overviewTone(profile) {
  const webhook = profile.webhook || {};
  const summary = webhook.summary || {};
  if (profile.tmux_dead || profile.runtime_state === "error" || profile.run_errors > 0 || (summary.failed || 0) > 0) return "bad";
  if (["starting", "running", "cooldown", "sleeping"].includes(profile.runtime_state || "")) return "good";
  return "idle";
}

function overviewGlowState(profile) {
  return ["starting", "running", "cooldown", "sleeping"].includes(profile?.runtime_state || "")
    ? "running"
    : "stopped";
}

function createOverviewCardNode() {
  const node = elementFromHTML(`
    <article class="overview-card overview-idle" data-profile="">
      <div class="overview-head">
        <div>
          <h3></h3>
          <div class="overview-subline">
            <span class="badge stopped"></span>
            <span class="overview-chip overview-chip-manual hidden"></span>
            <span class="overview-age"></span>
          </div>
        </div>
        <div class="overview-signal">
          <span class="overview-dot overview-dot-idle"></span>
        </div>
      </div>

      <div class="overview-stats"></div>

      <div class="overview-track">
        <div class="overview-track-row">
          <span>Run progress</span>
          <span class="overview-progress-value"></span>
        </div>
        <div class="overview-bar">
          <div class="overview-fill"></div>
        </div>
      </div>

      <div class="overview-footer"></div>

      <div class="overview-sent">
        <span class="overview-sent-label">Last accepted</span>
        <span class="overview-sent-value"></span>
      </div>

      <div class="overview-latest"></div>
    </article>
  `);
  node._refs = {
    title: node.querySelector("h3"),
    badge: node.querySelector(".badge"),
    manualTag: node.querySelector(".overview-chip-manual"),
    age: node.querySelector(".overview-age"),
    dot: node.querySelector(".overview-dot"),
    stats: node.querySelector(".overview-stats"),
    progressValue: node.querySelector(".overview-progress-value"),
    progressFill: node.querySelector(".overview-fill"),
    footer: node.querySelector(".overview-footer"),
    sentValue: node.querySelector(".overview-sent-value"),
    latest: node.querySelector(".overview-latest"),
  };
  return node;
}

function updateOverviewCardNode(node, profile, selectedProfile) {
  const refs = node._refs || {
    title: node.querySelector("h3"),
    badge: node.querySelector(".badge"),
    manualTag: node.querySelector(".overview-chip-manual"),
    age: node.querySelector(".overview-age"),
    dot: node.querySelector(".overview-dot"),
    stats: node.querySelector(".overview-stats"),
    progressValue: node.querySelector(".overview-progress-value"),
    progressFill: node.querySelector(".overview-fill"),
    footer: node.querySelector(".overview-footer"),
    sentValue: node.querySelector(".overview-sent-value"),
    latest: node.querySelector(".overview-latest"),
  };
  node._refs = refs;
  const webhook = profile.webhook || {};
  const live = webhook.summary || {};
  const tone = overviewTone(profile);
  const glowState = overviewGlowState(profile);
  const statusClass = profileStatusClass(profile);
  const isSelected = selectedProfile && selectedProfile.name === profile.name;
  const latestEvent = webhook.latest_event || {};
  const stateFallback = ["starting", "cooldown", "sleeping", "finished", "scheduled_stop", "error"].includes(profile.runtime_state || "")
    ? profile.runtime_note
    : "";
  const latestLabel = latestEvent.time
    ? `${statusLabel(latestEvent.status || "")} at ${formatGeneratedAt(latestEvent.time)}`
    : stateFallback || `${senderLogStatusLabel(profile.last_status || "No recent activity")}${profile.last_timestamp ? ` at ${profile.last_timestamp}` : ""}`;
  const sentLabel = profile.last_status === "SENT"
    ? `${profile.last_email || "-"}`
    : (profile.last_email || "No recent accepted record");
  const progress = profile.max_total > 0 ? Math.min(100, Math.round((profile.run_sent / profile.max_total) * 100)) : 0;
  const stats = [
    { key: "pending", label: "Pending", value: profile.pending_count },
    { key: "accepted", label: "Accepted", value: profile.run_sent },
    { key: "delivered", label: "Delivered", value: live.delivered || 0 },
    { key: "failures", label: "Failures", value: live.failed || 0 },
  ];
  const chips = [
    { key: "opened", value: `Opened ${live.open_unique || live.open || 0}` },
    { key: "clicked", value: `Clicked ${live.click_unique || live.click || 0}` },
    { key: "awaiting", value: `Awaiting ${profile.awaiting_outcome || 0}` },
    { key: "mapped", value: `Mapped ${webhook.total || 0}` },
  ];

  node.dataset.profile = profile.name || "";
  node.className = `overview-card overview-${tone} overview-glow-${glowState}${isSelected ? " is-selected" : ""}`;
  setNodeText(refs.title, formatProfileName(profile.name));
  refs.badge.className = `badge ${statusClass}`;
  setNodeText(refs.badge, profile.runtime_label || "Stopped");
  refs.manualTag.className = `overview-chip overview-chip-manual${isManualOnlyProfile(profile) ? "" : " hidden"}`;
  setNodeText(refs.manualTag, isManualOnlyProfile(profile) ? "Manual Start Only" : "");
  setNodeText(refs.age, profileAgeText(profile));
  refs.dot.className = `overview-dot overview-dot-${glowState}`;

  syncKeyedChildren(
    refs.stats,
    stats,
    (stat) => stat.key,
    () => createOverviewStatNode(),
    (statNode, stat) => updateOverviewStatNode(statNode, stat.label, stat.value),
  );

  setNodeText(refs.progressValue, `${profile.run_sent}/${profile.max_total || "∞"}`);
  refs.progressFill.style.width = `${progress}%`;

  syncKeyedChildren(
    refs.footer,
    chips,
    (chip) => chip.key,
    () => createOverviewChipNode(),
    (chipNode, chip) => updateOverviewChipNode(chipNode, chip.value),
  );

  setNodeText(refs.sentValue, sentLabel);
  setNodeText(refs.latest, latestLabel || "-");
}

function renderOverview(snapshot, selectedProfile) {
  const profiles = snapshot.profiles || [];
  syncKeyedChildren(
    els.overviewGrid,
    profiles,
    (profile) => profile.name,
    () => createOverviewCardNode(),
    (node, profile) => updateOverviewCardNode(node, profile, selectedProfile),
  );
}

function renderWebhookHealth(snapshot) {
  if (!els.webhookHealth) return;
  const health = snapshot.webhook_health || {};
  const metrics = [
    { key: "signature", label: "Signature", value: health.signature_verification ? "Verified" : "Off", tone: health.signature_verification ? "good" : "warn" },
    { key: "events_5m", label: "Events 5m", value: health.events_5m || 0, tone: (health.events_5m || 0) > 0 ? "good" : "neutral" },
    { key: "events_1h", label: "Events 1h", value: health.events_1h || 0, tone: (health.events_1h || 0) > 0 ? "good" : "neutral" },
    {
      key: "bounce_classified",
      label: "Bounces w/ class",
      value: health.bounces_with_bounce_classification || 0,
      tone: (health.bounces_with_bounce_classification || 0) > 0 ? "good" : "neutral",
    },
    {
      key: "bounce_missing_class",
      label: "Bounces missing class",
      value: health.bounces_missing_bounce_classification || 0,
      tone: (health.bounces_missing_bounce_classification || 0) > 0 ? "warn" : "good",
    },
    { key: "duplicates", label: "Duplicate webhooks (ignored)", value: health.duplicate_hits_selected_window || 0, tone: (health.duplicate_hits_selected_window || 0) > 0 ? "warn" : "good" },
    { key: "unmapped", label: "Unmapped", value: health.unmapped_selected_window || 0, tone: (health.unmapped_selected_window || 0) > 0 ? "warn" : "good" },
  ];
  syncKeyedChildren(
    els.webhookHealth,
    metrics,
    (metric) => metric.key,
    () => createLiveMetricNode(),
    (node, metric) => updateLiveMetricNode(node, metric.label, metric.value, metric.tone),
  );
  const lastReceived = health.last_received_at
    ? `Last webhook ${health.last_received_at} (${health.last_received_age || "-"})`
    : "No webhook events recorded yet.";
  if (els.webhookHealthCaption) {
    els.webhookHealthCaption.textContent = `${lastReceived} | Window ${health.selected_window_hours || snapshot.activity_hours}h`;
  }
}

function renderAwaitingAging(snapshot, selectedProfile) {
  if (!els.awaitingAging) return;
  const labels = snapshot.awaiting_age_buckets?.labels || {};
  const total = snapshot.awaiting_age_buckets?.total || {};
  const selected = selectedProfile?.awaiting_age_buckets || {};
  const clusters = [
    { key: "fleet", label: "Fleet", values: total },
    { key: "selected", label: selectedProfile ? formatProfileName(selectedProfile.name) : "Selected", values: selectedProfile ? selected : {} },
  ];
  setNodeHtml(
    els.awaitingAging,
    clusters.map((cluster) => `
      <section class="awaiting-cluster">
        <div class="awaiting-cluster-head">
          <strong>${escapeHtml(cluster.label)}</strong>
          <span class="muted">Accepted without final outcome</span>
        </div>
        <div class="awaiting-cluster-grid">
          ${Object.entries(labels).map(([key, label]) => `
            <div class="awaiting-box">
              <div class="label">${escapeHtml(label)}</div>
              <div class="value">${Number(cluster.values?.[key] || 0)}</div>
            </div>
          `).join("")}
        </div>
      </section>
    `).join(""),
  );
}

function renderDomainBreakdown(snapshot) {
  if (!els.domainBreakdown) return;
  const rows = Array.isArray(snapshot.domain_breakdown) ? snapshot.domain_breakdown : [];
  if (!rows.length) {
    setNodeHtml(els.domainBreakdown, `<p class="muted">No domain activity recorded in the selected window.</p>`);
    if (els.domainBreakdownCaption) {
      setNodeText(els.domainBreakdownCaption, `Top recipient domains in the selected ${snapshot.activity_hours}h window.`);
    }
    return;
  }
  setNodeHtml(
    els.domainBreakdown,
    `
      <table class="domain-table">
        <thead>
          <tr>
            <th>Domain</th>
            <th>Accepted</th>
            <th>Delivered</th>
            <th>Deferred</th>
            <th>Failures</th>
            <th>Opened U/T</th>
            <th>Clicked U/T</th>
            <th>Bounce Rate</th>
            <th>Delivered Rate</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escapeHtml(row.domain || "-")}</td>
              <td>${Number(row.accepted || 0)}</td>
              <td>${Number(row.delivered || 0)}</td>
              <td>${Number(row.deferred || 0)}</td>
              <td>${Number(row.failures || 0)}</td>
              <td>${Number(row.open_unique || 0)} / ${Number(row.open_total || 0)}</td>
              <td>${Number(row.click_unique || 0)} / ${Number(row.click_total || 0)}</td>
              <td>${row.bounce_rate == null ? "-" : formatPercent(row.bounce_rate)}</td>
              <td>${row.delivered_rate == null ? "-" : formatPercent(row.delivered_rate)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `,
  );
  if (els.domainBreakdownCaption) {
    setNodeText(els.domainBreakdownCaption, `Top recipient domains in the selected ${snapshot.activity_hours}h window.`);
  }
}

function isProfileActive(profile) {
  return ["starting", "running", "cooldown", "sleeping"].includes(profile?.runtime_state || "");
}

function canStartProfile(profile) {
  return !isProfileActive(profile);
}

function canStopProfile(profile) {
  return isProfileActive(profile);
}

function actionLabel(action) {
  if (action === "start") return "Starting...";
  if (action === "stop") return "Stopping...";
  return "";
}

function setProfileActionFeedback(profileName, kind, message) {
  if (!profileName) return;
  profileActionState.set(profileName, { kind, message, updatedAt: Date.now() });
}

function renderProfileActionFeedback(profile) {
  const feedback = profileActionState.get(profile.name);
  if (!feedback?.message) return "";
  return `<div class="profile-action-feedback ${feedback.kind}">${escapeHtml(feedback.message)}</div>`;
}

function renderSignals(snapshot) {
  const runStatus = snapshot.run_status_items || snapshot.attention_items || [];
  const telemetryNotes = snapshot.telemetry_notes || [];
  if (els.runStatusList) {
    syncKeyedChildren(
      els.runStatusList,
      runStatus,
      (item) => item,
      () => document.createElement("li"),
      (node, item) => setNodeText(node, item),
    );
  }
  if (els.telemetryNotesList) {
    syncKeyedChildren(
      els.telemetryNotesList,
      telemetryNotes,
      (item) => item,
      () => document.createElement("li"),
      (node, item) => setNodeText(node, item),
    );
  }
  const updatedLabel = `Updated ${formatGeneratedAt(snapshot.generated_at)}`;
  if (els.generatedAt) {
    els.generatedAt.textContent = updatedLabel;
  }
  if (els.toolbarGeneratedAt) {
    els.toolbarGeneratedAt.textContent = updatedLabel;
  }
}

function renderControls(snapshot) {
  const controls = snapshot.controls || {};
  const sendCap = Number(controls.send_cap_per_profile || 0);
  if (els.sendCapInput && document.activeElement !== els.sendCapInput && sendCap > 0) {
    els.sendCapInput.value = String(sendCap);
  }
  if (els.sendCapNote) {
    const activeSenders = Number(controls.active_sender_count || 0);
    const activeFleetTotal = Number(controls.fleet_total_for_active_senders || 0);
    const startAllTotal = Number(controls.estimated_total_if_start_all || 0);
    setNodeText(
      els.sendCapNote,
      `Per sender ${sendCap || 0}. Active senders ${activeSenders}, current fleet target ${activeFleetTotal || 0}. Start All target about ${startAllTotal}.`,
    );
  }
}

function renderDetailSwitcher(snapshot, selectedProfile) {
  const profiles = snapshot.profiles || [];
  const selectedName = selectedProfile?.name || "";
  const selectFocused = document.activeElement === els.detailProfileSelect;
  syncKeyedChildren(
    els.detailProfileSelect,
    profiles,
    (profile) => profile.name,
    () => createSelectOptionNode(),
    (node, profile) => updateSelectOptionNode(node, profile.name || "", formatProfileName(profile.name)),
  );
  if (!selectFocused && els.detailProfileSelect.value !== selectedName) {
    els.detailProfileSelect.value = selectedName;
  }

  const selectedIndex = profiles.findIndex((profile) => profile.name === selectedName);
  const hasProfiles = profiles.length > 0;
  els.detailProfileSelect.disabled = !hasProfiles;
  els.detailPrevBtn.disabled = !hasProfiles || selectedIndex <= 0;
  els.detailNextBtn.disabled = !hasProfiles || selectedIndex < 0 || selectedIndex >= profiles.length - 1;
}

function selectProfileByName(profileName) {
  if (!lastSnapshot) return;
  const profiles = lastSnapshot.profiles || [];
  const next = profiles.find((profile) => profile.name === profileName);
  if (!next) return;
  selectedProfileName = next.name;
  const selected = resolveSelectedProfile(lastSnapshot);
  renderOverview(lastSnapshot, selected);
  renderDetailSwitcher(lastSnapshot, selected);
  renderProfileDetail(lastSnapshot, selected);
}

function shiftSelectedProfile(direction) {
  if (!lastSnapshot) return;
  const profiles = lastSnapshot.profiles || [];
  if (!profiles.length) return;
  const currentIndex = profiles.findIndex((profile) => profile.name === selectedProfileName);
  const anchorIndex = currentIndex >= 0 ? currentIndex : 0;
  const nextIndex = Math.max(0, Math.min(profiles.length - 1, anchorIndex + direction));
  if (nextIndex === anchorIndex && currentIndex >= 0) return;
  selectProfileByName(profiles[nextIndex].name);
}

function renderFailures(snapshot) {
  if (!els.latestFailures) return;
  const failures = snapshot.latest_failures || [];
  if (!failures.length) {
    setNodeHtml(els.latestFailures, `<p class="muted">No recent failure events in the selected window.</p>`);
    return;
  }
  setNodeHtml(els.latestFailures, `
    <table class="failures-table">
      <thead>
        <tr>
          <th>Time</th>
          <th>Profile</th>
          <th>Status</th>
          <th>Email</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>
        ${failures.map((row) => `
          <tr>
            <td>${escapeHtml(formatGeneratedAt(row.time || ""))}</td>
            <td>${escapeHtml(formatProfileName(row.profile || ""))}</td>
            <td>${escapeHtml(statusLabel(row.status || ""))}</td>
            <td>${escapeHtml(row.email || "")}</td>
            <td>${escapeHtml(row.reason || "-")}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `);
}

function profileStatusClass(profile) {
  const state = String(profile.runtime_state || "").trim().replaceAll("_", "-");
  if (!state) return "stopped";
  if (["starting", "running", "cooldown", "sleeping", "finished", "scheduled-stop", "error", "dead"].includes(state)) {
    return state;
  }
  return "stopped";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function statusLabel(status) {
  const labels = {
    processed: "Processed",
    delivered: "Delivered",
    open: "Opened",
    click: "Clicked",
    deferred: "Deferred",
    bounce: "Bounced",
    blocked: "Blocked",
    dropped: "Dropped",
    spamreport: "Spam Report",
    unsubscribe: "Unsubscribed",
    group_unsubscribe: "Group Unsubscribe",
  };
  return labels[status] || status || "-";
}

function liveMetric(label, value, tone = "neutral") {
  return `
    <div class="live-metric live-${tone}">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
    </div>
  `;
}

function renderDeliveryFunnel(profile, hours) {
  const summary = profile.webhook?.summary || {};
  const accepted = profile.accepted_recent || 0;
  const stages = [
    { label: "Accepted", value: accepted, note: "handed to SendGrid" },
    { label: "Processed", value: summary.processed || 0, note: "entered pipeline" },
    { label: "Delivered", value: summary.delivered || 0, note: "confirmed delivered" },
    { label: "Opened (uniq)", value: summary.open_unique || 0, note: "distinct tracked opens" },
    { label: "Clicked (uniq)", value: summary.click_unique || 0, note: "distinct tracked clicks" },
  ];
  const sideStats = [
    { label: "Awaiting", value: profile.awaiting_outcome || 0, tone: (profile.awaiting_outcome || 0) > 0 ? "warn" : "neutral" },
    { label: "Failures", value: summary.failed || 0, tone: (summary.failed || 0) > 0 ? "bad" : "neutral" },
    { label: "Mapped", value: profile.webhook?.total || 0, tone: "good" },
  ];
  return `
    <section class="funnel-panel">
      <div class="funnel-head">
        <strong>Delivery Funnel</strong>
        <span class="muted">Accepted recipients in ${hours}h, excluding shared canary sends</span>
      </div>
      <div class="funnel-grid">
        ${stages.map((stage) => `
          <div class="funnel-stage">
            <div class="funnel-label">${stage.label}</div>
            <div class="funnel-value">${stage.value}</div>
            <div class="funnel-note">${stage.note}</div>
          </div>
        `).join("")}
      </div>
      <div class="funnel-meta">
        ${sideStats.map((stat) => `<span class="event-chip chip-${stat.tone}">${stat.label}: ${stat.value}</span>`).join("")}
      </div>
    </section>
  `;
}

function renderLiveDelivery(profile, hours) {
  const webhook = profile.webhook || { summary: {}, latest_event: {}, total: 0 };
  const summary = webhook.summary || {};
  const latest = webhook.latest_event || {};
  const failureBits = [];
  if (summary.bounce) failureBits.push(`Bounced ${summary.bounce}`);
  if (summary.blocked) failureBits.push(`Blocked ${summary.blocked}`);
  if (summary.dropped) failureBits.push(`Dropped ${summary.dropped}`);
  if (summary.spamreport) failureBits.push(`Spam ${summary.spamreport}`);
  if (summary.unsubscribe) failureBits.push(`Unsubscribed ${summary.unsubscribe}`);

  let latestText = `No mapped webhook events in the last ${hours}h.`;
  if (latest.time) {
    latestText = `Last webhook: ${statusLabel(latest.status)} at ${formatGeneratedAt(latest.time)}${latest.email ? ` for ${latest.email}` : ""}`;
  }

  return `
    <section class="live-delivery">
      <div class="live-delivery-head">
        <strong>Live SendGrid</strong>
        <span class="muted">${webhook.total || 0} mapped event${(webhook.total || 0) === 1 ? "" : "s"} in ${hours}h</span>
      </div>
      <div class="live-metrics-grid">
        ${liveMetric("Delivered", summary.delivered || 0, "good")}
        ${liveMetric("Opened (uniq)", summary.open_unique || 0, "good")}
        ${liveMetric("Opened (all)", summary.open || 0, "good")}
        ${liveMetric("Clicked (uniq)", summary.click_unique || 0, "good")}
        ${liveMetric("Clicked (all)", summary.click || 0, "good")}
        ${liveMetric("Deferred", summary.deferred || 0, summary.deferred ? "warn" : "neutral")}
        ${liveMetric("Failures", summary.failed || 0, summary.failed ? "bad" : "neutral")}
      </div>
      ${renderDeliveryFunnel(profile, hours)}
      <div class="live-delivery-note">
        <span>${failureBits.length ? failureBits.join(" | ") : "No bounce, block, drop, or spam events in the selected window."}</span>
        <span>Awaiting outcome: ${profile.awaiting_outcome || 0} accepted recipient(s) in ${hours}h.</span>
        <span>${latestText}</span>
      </div>
    </section>
  `;
}

function renderWebhookSummary(profile) {
  const webhook = profile.webhook || { counts: {}, recent: [], total: 0 };
  const counts = webhook.counts || {};
  const hasFailures = Number(webhook?.summary?.failed || 0) > 0;
  const hasRecent = Array.isArray(webhook.recent) && webhook.recent.length > 0;
  const shouldOpen = hasFailures || hasRecent;
  const chips = Object.entries(counts).map(([status, count]) => {
    const lower = status.toLowerCase();
    let cls = "chip-neutral";
    if (["delivered", "processed", "open", "click"].includes(lower)) cls = "chip-good";
    if (["deferred"].includes(lower)) cls = "chip-warn";
    if (["bounce", "blocked", "dropped", "spamreport", "unsubscribe", "group_unsubscribe"].includes(lower)) cls = "chip-bad";
    return `<span class="event-chip ${cls}">${escapeHtml(statusLabel(lower))}: ${count}</span>`;
  }).join("");

  const recent = (webhook.recent || []).map((row) => `
    <tr>
      <td>${escapeHtml(formatGeneratedAt(row.time || ""))}</td>
      <td>${escapeHtml(statusLabel(row.status || ""))}</td>
      <td>${escapeHtml(row.email || "")}</td>
      <td>${escapeHtml(row.reason || "-")}</td>
    </tr>
  `).join("");

  return `
    <section class="webhook-panel">
      <div class="webhook-head">
        <strong>Webhook Events</strong>
        <span class="muted">Total ${webhook.total || 0}</span>
      </div>
      <details class="webhook-details-panel"${shouldOpen ? " open" : ""}>
        <summary>
          <span>Recent webhook events</span>
          <span class="muted">${hasRecent ? `${webhook.recent.length} recent` : "Expand for details"}</span>
        </summary>
        <div class="event-chip-row">
          ${chips || `<span class="muted">No mapped webhook events yet.</span>`}
        </div>
        ${recent ? `
          <div class="webhook-details">
            <table class="webhook-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Status</th>
                  <th>Email</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>${recent}</tbody>
            </table>
          </div>
        ` : `<p class="muted">No mapped webhook events yet for this profile.</p>`}
      </details>
    </section>
  `;
}

function buildDetailKicker(profile) {
  const pending = Number(profile.pending_count || 0);
  const accepted = Number(profile.run_sent || 0);
  const awaiting = Number(profile.awaiting_outcome || 0);
  const errors = Number(profile.run_errors || 0);
  if (isProfileActive(profile)) {
    return `${accepted} accepted, ${awaiting} awaiting outcome, and ${pending} still pending in this queue.`;
  }
  if (accepted || errors || Number(profile.run_skipped || 0)) {
    return `${accepted} accepted in this run, ${errors} API errors, and ${pending} still pending in the queue.`;
  }
  return `${pending} pending in this queue. Start this sender when you want it live.`;
}

function buildProfileActionNote(profile) {
  if (canStopProfile(profile)) {
    return `Profile is active. Dashboard start cap is ${profile.max_total || "∞"} for new launches. Stop pauses only this sender.`;
  }
  if ((profile.runtime_state || "") === "finished") {
    return `This sender reached its current cap or exhausted the queue. Dashboard start cap is ${profile.max_total || "∞"}.`;
  }
  return `Queue is idle. Start runs only this sender using a dashboard cap of ${profile.max_total || "∞"}.`;
}

function createProfileDetailNode() {
  const node = elementFromHTML(`
    <article class="detail-card">
      <div class="detail-head">
        <div>
          <p class="eyebrow">Focused Detail</p>
          <h3></h3>
          <p class="detail-kicker muted"></p>
        </div>
        <section class="detail-action-card">
          <div class="detail-action-head">
            <span class="badge stopped"></span>
            <span class="muted detail-last-update"></span>
          </div>
          <div class="profile-actions">
            <button class="btn btn-secondary start-profile-btn" type="button"></button>
            <button class="btn btn-danger stop-profile-btn" type="button"></button>
          </div>
          <div class="detail-action-note muted"></div>
        </section>
      </div>
      <div class="detail-feedback-slot"></div>

      <div class="detail-layout">
        <div class="detail-main">
          <section class="detail-section">
            <div class="detail-section-head">
              <strong>Run Snapshot</strong>
              <span class="muted detail-progress-note"></span>
            </div>
            <div class="metrics detail-metrics"></div>
            <div class="progress-wrap">
              <div class="progress-label">
                <span>Run progress</span>
                <span class="detail-progress-value"></span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill"></div>
              </div>
            </div>
          </section>

          <div class="detail-live-slot"></div>
          <div class="detail-webhook-slot"></div>
        </div>

        <aside class="detail-side">
          <section class="detail-status-card">
            <div class="detail-side-head">
              <strong>Runtime</strong>
              <span class="muted detail-pane-label"></span>
            </div>
            <div class="detail-status-copy detail-runtime-note"></div>
          </section>

          <section class="detail-status-card">
            <div class="detail-side-head">
              <strong>Latest Sender Activity</strong>
              <span class="muted detail-last-age"></span>
            </div>
            <div class="last-line"></div>
          </section>

          <section class="detail-side-card">
            <div class="detail-side-head">
              <strong>Queue Context</strong>
              <span class="muted">Files and tmux pane</span>
            </div>
            <div class="profile-meta detail-meta"></div>
          </section>

          <details class="detail-pane detail-side-card">
            <summary>Pane tail</summary>
            <pre></pre>
          </details>
        </aside>
      </div>
    </article>
  `);
  node._refs = {
    title: node.querySelector("h3"),
    kicker: node.querySelector(".detail-kicker"),
    badge: node.querySelector(".badge"),
    paneLabel: node.querySelector(".detail-pane-label"),
    runtimeNote: node.querySelector(".detail-runtime-note"),
    lastUpdate: node.querySelector(".detail-last-update"),
    lastAge: node.querySelector(".detail-last-age"),
    actionNote: node.querySelector(".detail-action-note"),
    startButton: node.querySelector(".start-profile-btn"),
    stopButton: node.querySelector(".stop-profile-btn"),
    feedback: node.querySelector(".detail-feedback-slot"),
    metrics: node.querySelector(".detail-metrics"),
    live: node.querySelector(".detail-live-slot"),
    progressNote: node.querySelector(".detail-progress-note"),
    progressValue: node.querySelector(".detail-progress-value"),
    progressFill: node.querySelector(".progress-fill"),
    webhook: node.querySelector(".detail-webhook-slot"),
    meta: node.querySelector(".detail-meta"),
    lastLine: node.querySelector(".last-line"),
    paneTail: node.querySelector(".detail-pane pre"),
  };
  return node;
}

function updateProfileDetailNode(node, snapshot, profile) {
  const refs = node._refs || {
    title: node.querySelector("h3"),
    kicker: node.querySelector(".detail-kicker"),
    badge: node.querySelector(".badge"),
    paneLabel: node.querySelector(".detail-pane-label"),
    runtimeNote: node.querySelector(".detail-runtime-note"),
    lastUpdate: node.querySelector(".detail-last-update"),
    lastAge: node.querySelector(".detail-last-age"),
    actionNote: node.querySelector(".detail-action-note"),
    startButton: node.querySelector(".start-profile-btn"),
    stopButton: node.querySelector(".stop-profile-btn"),
    feedback: node.querySelector(".detail-feedback-slot"),
    metrics: node.querySelector(".detail-metrics"),
    live: node.querySelector(".detail-live-slot"),
    progressNote: node.querySelector(".detail-progress-note"),
    progressValue: node.querySelector(".detail-progress-value"),
    progressFill: node.querySelector(".progress-fill"),
    webhook: node.querySelector(".detail-webhook-slot"),
    meta: node.querySelector(".detail-meta"),
    lastLine: node.querySelector(".last-line"),
    paneTail: node.querySelector(".detail-pane pre"),
  };
  node._refs = refs;

  const statusClass = profileStatusClass(profile);
  const progress = profile.max_total > 0 ? Math.min(100, Math.round((profile.run_sent / profile.max_total) * 100)) : 0;
  const pendingAction = pendingProfileActions.get(profile.name) || "";
  const startDisabled = Boolean(pendingAction) || !canStartProfile(profile);
  const stopDisabled = Boolean(pendingAction) || !canStopProfile(profile);
  const metrics = [
    { key: "pending", label: "Pending", value: profile.pending_count },
    { key: "accepted", label: "Accepted", value: profile.run_sent },
    { key: "awaiting", label: "Awaiting Outcome", value: profile.awaiting_outcome || 0 },
    { key: "errors", label: "API Errors", value: profile.run_errors },
    { key: "skipped", label: "Skipped", value: profile.run_skipped },
  ];
  const metaBoxes = [
    { label: "Queue File", value: profile.csv_path },
    { label: "Sender Log", value: profile.log_path },
    { label: "Configured Cap", value: profile.configured_max_total || "∞" },
    { label: "Dashboard Start Cap", value: profile.max_total || "∞" },
    { label: "Session Pane", value: `${profile.pane_index} / ${profile.tmux_command || "-"}` },
  ];

  node.dataset.profile = profile.name || "";
  setNodeText(refs.title, formatProfileName(profile.name));
  setNodeText(refs.kicker, buildDetailKicker(profile));
  refs.badge.className = `badge ${statusClass}`;
  setNodeText(refs.badge, profile.runtime_label || "Stopped");
  setNodeText(refs.paneLabel, `Pane ${profile.pane_index} / ${profile.tmux_command || "-"}`);
  setNodeText(refs.runtimeNote, profile.runtime_note || "Pane is idle.");
  setNodeText(refs.lastUpdate, profileLastUpdateText(profile));
  setNodeText(refs.lastAge, profileLastAgeText(profile));
  setNodeText(refs.actionNote, buildProfileActionNote(profile));

  refs.startButton.dataset.profile = profile.name || "";
  refs.startButton.disabled = startDisabled;
  setNodeText(refs.startButton, pendingAction === "start" ? "Starting..." : "Start");

  refs.stopButton.dataset.profile = profile.name || "";
  refs.stopButton.disabled = stopDisabled;
  setNodeText(refs.stopButton, pendingAction === "stop" ? "Stopping..." : "Stop");

  setNodeHtml(refs.feedback, renderProfileActionFeedback(profile));

  syncKeyedChildren(
    refs.metrics,
    metrics,
    (metric) => metric.key,
    () => createMetricNode(),
    (metricNode, metric) => updateMetricNode(metricNode, metric.label, metric.value),
  );

  setNodeHtml(refs.live, renderLiveDelivery(profile, snapshot.activity_hours));
  setNodeText(
    refs.progressNote,
    `Dashboard start cap ${profile.max_total || "∞"} accepted recipient${Number(profile.max_total || 0) === 1 ? "" : "s"}. Base profile cap ${profile.configured_max_total || "∞"}.`,
  );
  setNodeText(refs.progressValue, `${profile.run_sent}/${profile.max_total || "∞"}`);
  refs.progressFill.style.width = `${progress}%`;
  setNodeHtml(refs.webhook, renderWebhookSummary(profile));
  setNodeHtml(
    refs.meta,
    metaBoxes.map((item) => `
      <div class="detail-meta-row">
        <div class="detail-meta-label">${escapeHtml(item.label)}</div>
        <code class="detail-meta-value">${escapeHtml(item.value || "-")}</code>
      </div>
    `).join(""),
  );
  setNodeHtml(
    refs.lastLine,
    `
      <div class="detail-activity-list">
        <div class="detail-activity-row">
          <span class="detail-activity-key">Status</span>
          <span>${escapeHtml(senderLogStatusLabel(profile.last_status || "-"))}</span>
        </div>
        <div class="detail-activity-row">
          <span class="detail-activity-key">Recipient</span>
          <span>${escapeHtml(profile.last_email || "-")}</span>
        </div>
        <div class="detail-activity-row">
          <span class="detail-activity-key">Logged</span>
          <span>${escapeHtml(profile.last_timestamp || "-")}</span>
        </div>
        ${profile.run_started_at ? `
          <div class="detail-activity-row">
            <span class="detail-activity-key">Run anchor</span>
            <span>${escapeHtml(profile.run_started_at)}</span>
          </div>
        ` : ""}
        ${profile.last_info ? `
          <div class="detail-activity-row detail-activity-row-info">
            <span class="detail-activity-key">Info</span>
            <code>${escapeHtml(profile.last_info)}</code>
          </div>
        ` : ""}
      </div>
    `,
  );
  setNodeText(refs.paneTail, profile.tmux_tail || "(no pane output)");
}

function renderProfileDetail(snapshot, profile) {
  if (!profile) {
    els.detailCaption.textContent = "No sender profiles available.";
    setNodeHtml(els.profileDetail, `<p class="muted">No profile detail available.</p>`);
    return;
  }
  els.detailCaption.textContent = `Selected sender: ${formatProfileName(profile.name)}`;
  let detailCard = els.profileDetail.querySelector(".detail-card");
  if (!detailCard) {
    detailCard = createProfileDetailNode();
    els.profileDetail.replaceChildren(detailCard);
  }
  updateProfileDetailNode(detailCard, snapshot, profile);
}

function renderSnapshot(snapshot) {
  lastSnapshot = snapshot;
  displayTimeZone = snapshot.display_timezone || displayTimeZone;
  const selectedProfile = resolveSelectedProfile(snapshot);
  renderControls(snapshot);
  renderHealth(snapshot);
  renderAlerts(snapshot);
  renderSummary(snapshot);
  renderPrivateBounceGuard(snapshot);
  renderTrends(snapshot);
  renderWebhookHealth(snapshot);
  renderAwaitingAging(snapshot, selectedProfile);
  renderDomainBreakdown(snapshot);
  renderOverview(snapshot, selectedProfile);
  renderSignals(snapshot);
  renderFailures(snapshot);
  renderDetailSwitcher(snapshot, selectedProfile);
  renderProfileDetail(snapshot, selectedProfile);
  renderShardWriteGuard();
  if (!didHydrate && els.page) {
    didHydrate = true;
    requestAnimationFrame(() => {
      els.page.classList.remove("booting");
    });
  }
}

async function fetchSnapshot() {
  const hours = currentActivityHours();
  const tail = currentTailLines();
  const response = await fetch(`/api/snapshot?hours=${encodeURIComponent(hours)}&tail_lines=${encodeURIComponent(tail)}`);
  const data = await response.json();
  renderSnapshot(data);
}

function rerenderCurrentSelection() {
  if (!lastSnapshot) return;
  const selected = resolveSelectedProfile(lastSnapshot);
  renderOverview(lastSnapshot, selected);
  renderDetailSwitcher(lastSnapshot, selected);
  renderProfileDetail(lastSnapshot, selected);
}

function handleOverviewClick(event) {
  if (wallboardMode) return;
  const card = event.target.closest(".overview-card[data-profile]");
  if (!card || !els.overviewGrid.contains(card)) return;
  selectProfileByName(card.getAttribute("data-profile") || "");
}

async function handleProfileDetailClick(event) {
  const startButton = event.target.closest(".start-profile-btn[data-profile]");
  if (startButton && els.profileDetail.contains(startButton)) {
    if (startButton.disabled) return;
    const profile = startButton.getAttribute("data-profile") || "";
    await postAction(`/api/start/${profile}`, { profileName: profile, action: "start" });
    return;
  }

  const stopButton = event.target.closest(".stop-profile-btn[data-profile]");
  if (stopButton && els.profileDetail.contains(stopButton)) {
    if (stopButton.disabled) return;
    const profile = stopButton.getAttribute("data-profile") || "";
    await postAction(`/api/stop/${profile}`, { profileName: profile, action: "stop" });
  }
}

async function postAction(path, options = {}) {
  const { profileName = "", action = "", body = null } = options;
  try {
    if (profileName && action) {
      pendingProfileActions.set(profileName, action);
      setProfileActionFeedback(profileName, "info", action === "start" ? "Starting profile..." : "Stopping profile...");
      rerenderCurrentSelection();
    }
    const fetchOptions = { method: "POST" };
    if (body !== null) {
      fetchOptions.headers = { "Content-Type": "application/json" };
      fetchOptions.body = JSON.stringify(body);
    }
    const response = await fetch(path, fetchOptions);
    const data = await response.json().catch(() => ({}));
    const ok = response.ok && (data.ok !== false);
    const message = data.message || data.detail || (ok ? "Action complete." : `Request failed (${response.status}).`);
    if (profileName) {
      pendingProfileActions.delete(profileName);
      setProfileActionFeedback(profileName, ok ? "success" : "error", message);
    }
    showMessage(message, ok ? "success" : "error");
    if (data.snapshot) {
      renderSnapshot(data.snapshot);
    } else {
      await fetchSnapshot();
    }
  } catch (err) {
    if (profileName) {
      pendingProfileActions.delete(profileName);
      setProfileActionFeedback(profileName, "error", `Request failed: ${err}`);
      rerenderCurrentSelection();
    }
    showMessage(`Request failed: ${err}`, "error");
  }
}

async function saveSendCap() {
  const rawValue = Number(els.sendCapInput?.value || 0);
  if (!Number.isInteger(rawValue) || rawValue < 1) {
    showMessage("Enter a whole number of at least 1 for the dashboard send cap.", "error");
    return;
  }
  if (els.sendCapSaveBtn) {
    els.sendCapSaveBtn.disabled = true;
    setNodeText(els.sendCapSaveBtn, "Saving...");
  }
  try {
    await postAction("/api/settings/send-cap", { body: { send_cap_per_profile: rawValue } });
  } finally {
    if (els.sendCapSaveBtn) {
      els.sendCapSaveBtn.disabled = false;
      setNodeText(els.sendCapSaveBtn, "Save Cap");
    }
  }
}

async function uploadLeadsFile() {
  const file = els.leadsUploadInput?.files?.[0];
  if (!file) {
    showMessage("Choose a CSV file before uploading.", "error");
    return;
  }
  lastShardPreview = null;
  const formData = new FormData();
  formData.append("file", file);
  if (els.leadsUploadBtn) {
    els.leadsUploadBtn.disabled = true;
    setNodeText(els.leadsUploadBtn, "Uploading...");
  }
  try {
    const data = await fetchJson("/api/leads/upload", {
      method: "POST",
      body: formData,
    });
    renderLeadsStatus(data.status || {});
    showMessage(data.message || "Upload complete.", "success");
  } catch (err) {
    showMessage(`Lead upload failed: ${err}`, "error");
  } finally {
    if (els.leadsUploadBtn) {
      els.leadsUploadBtn.disabled = false;
      setNodeText(els.leadsUploadBtn, "Upload CSV");
    }
  }
}

async function runLeadClean() {
  const uploadFilename = lastLeadsStatus?.latest_upload?.saved_filename || "";
  if (!uploadFilename) {
    showMessage("Upload a leads CSV before running clean.", "error");
    return;
  }
  lastShardPreview = null;
  if (els.leadsCleanBtn) {
    els.leadsCleanBtn.disabled = true;
    setNodeText(els.leadsCleanBtn, "Cleaning...");
  }
  try {
    const data = await fetchJson("/api/leads/clean", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        upload_filename: uploadFilename,
        mapping: selectedLeadsMapping(),
        remove_invalid_emails: Boolean(els.cleanRemoveInvalid?.checked),
        dedupe_by_email: Boolean(els.cleanDedupe?.checked),
        remove_suppressed: Boolean(els.cleanRemoveSuppressed?.checked),
        drop_role_emails: Boolean(els.cleanDropRole?.checked),
        exclude_domains: parseDomainList(els.cleanExcludeDomains?.value || ""),
      }),
    });
    renderLeadsStatus(data.status || {});
    showMessage(data.message || "Lead clean complete.", "success");
  } catch (err) {
    showMessage(`Lead clean failed: ${err}`, "error");
  } finally {
    if (els.leadsCleanBtn) {
      els.leadsCleanBtn.disabled = false;
      setNodeText(els.leadsCleanBtn, "Run Clean");
    }
  }
}

async function previewLeadShard() {
  const cleanedFilename = lastLeadsStatus?.latest_cleaned?.filename || "";
  if (!cleanedFilename) {
    showMessage("Run clean first so there is a cleaned file to preview.", "error");
    return;
  }
  const shardCount = Number(els.leadsShardCount?.value || 0);
  if (!Number.isInteger(shardCount) || shardCount < 1) {
    showMessage("Enter a valid shard count.", "error");
    return;
  }
  if (els.leadsPreviewBtn) {
    els.leadsPreviewBtn.disabled = true;
    setNodeText(els.leadsPreviewBtn, "Previewing...");
  }
  try {
    const data = await fetchJson("/api/leads/shard/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cleaned_filename: cleanedFilename,
        shard_count: shardCount,
        strategy: els.leadsShardStrategy?.value || "domain_balanced",
      }),
    });
    lastShardPreview = {
      ...(data.preview || {}),
      _preview_key: currentShardPlanKey(),
    };
    renderLeadsStatus(data.status || {});
    showMessage(data.message || "Preview ready.", "success");
  } catch (err) {
    lastShardPreview = null;
    renderShardWriteGuard();
    showMessage(`Shard preview failed: ${err}`, "error");
  } finally {
    if (els.leadsPreviewBtn) {
      els.leadsPreviewBtn.disabled = false;
      setNodeText(els.leadsPreviewBtn, "Preview Shards");
    }
  }
}

async function runLeadShard() {
  const cleanedFilename = lastLeadsStatus?.latest_cleaned?.filename || "";
  if (!cleanedFilename) {
    showMessage("Run clean first so there is a cleaned file to shard.", "error");
    return;
  }
  if (!previewMatchesCurrentSelection()) {
    showMessage("Run Preview for the current shard settings before writing.", "error");
    return;
  }
  if (String(els.leadsShardConfirm?.value || "").trim().toUpperCase() !== "SHARD") {
    showMessage("Type SHARD to confirm the overwrite.", "error");
    return;
  }
  if (activeSenderProfiles().length) {
    showMessage("Stop all senders before overwriting shards.", "error");
    renderShardWriteGuard();
    return;
  }
  const shardCount = Number(els.leadsShardCount?.value || 0);
  if (!Number.isInteger(shardCount) || shardCount < 1) {
    showMessage("Enter a valid shard count.", "error");
    return;
  }
  if (els.leadsShardBtn) {
    els.leadsShardBtn.disabled = true;
    setNodeText(els.leadsShardBtn, "Writing...");
  }
  try {
    const data = await fetchJson("/api/leads/shard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cleaned_filename: cleanedFilename,
        shard_count: shardCount,
        strategy: els.leadsShardStrategy?.value || "domain_balanced",
      }),
    });
    lastShardPreview = null;
    if (els.leadsShardConfirm) {
      els.leadsShardConfirm.value = "";
    }
    renderLeadsStatus(data.status || {});
    if (data.snapshot) {
      renderSnapshot(data.snapshot);
    } else {
      await fetchSnapshot();
    }
    showMessage(data.message || "Shards updated.", "success");
  } catch (err) {
    renderShardWriteGuard();
    showMessage(`Shard write failed: ${err}`, "error");
  } finally {
    if (els.leadsShardBtn) {
      setNodeText(els.leadsShardBtn, "Write Shards");
    }
    renderShardWriteGuard();
  }
}

function connectSocket() {
  if (socket) {
    socket.close();
  }
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const hours = encodeURIComponent(currentActivityHours());
  const tail = encodeURIComponent(currentTailLines());
  socket = new WebSocket(`${protocol}://${location.host}/ws?hours=${hours}&tail_lines=${tail}`);

  socket.addEventListener("open", () => {
    setConnectionState(true);
  });

  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    renderSnapshot(payload);
  });

  socket.addEventListener("close", () => {
    setConnectionState(false);
    setTimeout(connectSocket, 1500);
  });

  socket.addEventListener("error", () => {
    setConnectionState(false);
    socket.close();
  });
}

if (els.refreshBtn) els.refreshBtn.addEventListener("click", () => fetchSnapshot());
if (els.sendCapSaveBtn) els.sendCapSaveBtn.addEventListener("click", () => saveSendCap());
if (els.wallboardBtn) els.wallboardBtn.addEventListener("click", () => toggleWallboardMode());
if (els.startBtn) els.startBtn.addEventListener("click", () => postAction("/api/start"));
if (els.stopBtn) els.stopBtn.addEventListener("click", () => postAction("/api/stop"));
if (els.archiveBtn) els.archiveBtn.addEventListener("click", () => postAction("/api/archive-reset-logs"));
if (els.opsTabBtn) els.opsTabBtn.addEventListener("click", () => setDashboardTab("ops"));
if (els.leadsTabBtn) els.leadsTabBtn.addEventListener("click", () => setDashboardTab("leads"));
if (els.leadsImportantCheckBtn) els.leadsImportantCheckBtn.addEventListener("click", () => runImportantLeadCheck());
if (els.leadsImportantDispatchBtn) els.leadsImportantDispatchBtn.addEventListener("click", () => runImportantLeadDispatch());
if (els.leadsUploadBtn) els.leadsUploadBtn.addEventListener("click", () => uploadLeadsFile());
if (els.leadsCleanBtn) els.leadsCleanBtn.addEventListener("click", () => runLeadClean());
if (els.leadsPreviewBtn) els.leadsPreviewBtn.addEventListener("click", () => previewLeadShard());
if (els.leadsShardBtn) els.leadsShardBtn.addEventListener("click", () => runLeadShard());
if (els.leadsRefreshBtn) els.leadsRefreshBtn.addEventListener("click", () => fetchLeadsStatus());
if (els.leadsShardConfirm) {
  els.leadsShardConfirm.addEventListener("input", () => renderShardWriteGuard());
  els.leadsShardConfirm.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !els.leadsShardBtn?.disabled) {
      event.preventDefault();
      runLeadShard();
    }
  });
}
if (els.leadsShardCount) els.leadsShardCount.addEventListener("change", () => renderLeadsStatus(lastLeadsStatus || {}));
if (els.leadsShardStrategy) els.leadsShardStrategy.addEventListener("change", () => renderLeadsStatus(lastLeadsStatus || {}));
if (els.sendCapInput) {
  els.sendCapInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      saveSendCap();
    }
  });
}
if (els.hoursSelect) els.hoursSelect.addEventListener("change", () => connectSocket());
if (els.tailSelect) els.tailSelect.addEventListener("change", () => connectSocket());
if (els.overviewGrid) els.overviewGrid.addEventListener("click", handleOverviewClick);
if (els.profileDetail) els.profileDetail.addEventListener("click", handleProfileDetailClick);
if (els.detailProfileSelect) {
  els.detailProfileSelect.addEventListener("change", (event) => {
    selectProfileByName(event.target.value);
  });
}
if (els.detailPrevBtn) els.detailPrevBtn.addEventListener("click", () => shiftSelectedProfile(-1));
if (els.detailNextBtn) els.detailNextBtn.addEventListener("click", () => shiftSelectedProfile(1));

wallboardMode = readWallboardModeFromLocation();
activeDashboardTab = readDashboardTabFromLocation();
applyWallboardMode();
applyDashboardTab();
renderImportantLeadCheck(lastImportantLeadCheck);
renderImportantDispatch(lastImportantDispatch);
Promise.allSettled([fetchSnapshot(), fetchLeadsStatus()]).finally(() => connectSocket());
