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
  alertsProgress: document.getElementById("alerts-progress"),
  alertsCaption: document.getElementById("alerts-caption"),
  summaryGrid: document.getElementById("summary-grid"),
  trendsGrid: document.getElementById("trends-grid"),
  webhookHealth: document.getElementById("webhook-health"),
  webhookHealthCaption: document.getElementById("webhook-health-caption"),
  awaitingAging: document.getElementById("awaiting-aging"),
  domainBreakdown: document.getElementById("domain-breakdown"),
  domainBreakdownCaption: document.getElementById("domain-breakdown-caption"),
  overviewGrid: document.getElementById("overview-grid"),
  campaignRunHistory: document.getElementById("campaign-run-history"),
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
  leadsImportantInputPath: document.getElementById("leads-important-input-path"),
  leadsImportantIntakeMode: document.getElementById("leads-important-intake-mode"),
  leadsImportantOutputPath: document.getElementById("leads-important-output-path"),
  leadsImportantRejectedPath: document.getElementById("leads-important-rejected-path"),
  leadsImportantInputText: document.getElementById("leads-important-input-text"),
  leadsImportantPasteNote: document.getElementById("leads-important-paste-note"),
  leadsImportantUploadFile: document.getElementById("leads-important-upload-file"),
  leadsImportantUploadNote: document.getElementById("leads-important-upload-note"),
  leadsImportantUploadCheckBtn: document.getElementById("leads-important-upload-check-btn"),
  leadsImportantCheckBtn: document.getElementById("leads-important-check-btn"),
  leadsImportantCheckMeta: document.getElementById("leads-important-check-meta"),
  leadsImportantCheckResults: document.getElementById("leads-important-check-results"),
  leadsImportantVerifyInputPath: document.getElementById("leads-verify-input-path"),
  leadsImportantVerifyOutputPath: document.getElementById("leads-verify-output-path"),
  leadsImportantVerifyRejectedPath: document.getElementById("leads-verify-rejected-path"),
  leadsImportantVerifyQuarantinePath: document.getElementById("leads-verify-quarantine-path"),
  leadsImportantVerifyBtn: document.getElementById("leads-verify-btn"),
  leadsImportantVerifyStrictBtn: document.getElementById("leads-verify-strict-btn"),
  leadsImportantVerifyStopBtn: document.getElementById("leads-verify-stop-btn"),
  leadsImportantVerifyMeta: document.getElementById("leads-verify-meta"),
  leadsImportantVerifyResults: document.getElementById("leads-verify-results"),
  leadsQuarantineReasonCode: document.getElementById("leads-quarantine-reason-code"),
  leadsQuarantineStage: document.getElementById("leads-quarantine-stage"),
  leadsQuarantineStatus: document.getElementById("leads-quarantine-status"),
  leadsQuarantineSort: document.getElementById("leads-quarantine-sort"),
  leadsQuarantineRefreshBtn: document.getElementById("leads-quarantine-refresh-btn"),
  leadsQuarantineOperatorNote: document.getElementById("leads-quarantine-operator-note"),
  leadsQuarantinePromoteBtn: document.getElementById("leads-quarantine-promote-btn"),
  leadsQuarantineRejectBtn: document.getElementById("leads-quarantine-reject-btn"),
  leadsQuarantineStrictBtn: document.getElementById("leads-quarantine-strict-btn"),
  leadsQuarantineNoteBtn: document.getElementById("leads-quarantine-note-btn"),
  leadsQuarantineMeta: document.getElementById("leads-quarantine-meta"),
  leadsQuarantineResults: document.getElementById("leads-quarantine-results"),
  leadsQuarantineShell: document.querySelector(".leads-review-shell"),
  leadsImportantDispatchSourceMode: document.getElementById("leads-dispatch-source-mode"),
  leadsImportantDispatchCap: document.getElementById("leads-dispatch-cap"),
  leadsImportantDispatchSourceNote: document.getElementById("leads-dispatch-source-note"),
  leadsImportantDispatchPreviewBtn: document.getElementById("leads-important-dispatch-preview-btn"),
  leadsImportantDispatchConfirmBtn: document.getElementById("leads-important-dispatch-confirm-btn"),
  leadsImportantDispatchMeta: document.getElementById("leads-important-dispatch-meta"),
  leadsImportantDispatchResults: document.getElementById("leads-important-dispatch-results"),
  leadsPipelineMeta: document.getElementById("leads-pipeline-meta"),
  leadsOperatorStatusStrip: document.getElementById("leads-operator-status-strip"),
  leadsWorkflowStatusBanner: document.getElementById("leads-workflow-status-banner"),
  leadsActiveAlerts: document.getElementById("leads-active-alerts"),
  leadFunnelSummary: document.getElementById("lead-funnel-summary"),
  leadsRunSafetyCard: document.getElementById("leads-run-safety-card"),
  nextBatchPrepCard: document.getElementById("next-batch-prep-card"),
  leadsPipelineSteps: document.getElementById("leads-pipeline-steps"),
  leadsUploadInput: document.getElementById("leads-upload-input"),
  leadsUploadBtn: document.getElementById("leads-upload-btn"),
  leadsUploadMeta: document.getElementById("leads-upload-meta"),
  leadsEmailColumn: document.getElementById("leads-email-column"),
  leadsFirstNameColumn: document.getElementById("leads-first-name-column"),
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
  authOverlay: document.getElementById("auth-overlay"),
  authOverlayNote: document.getElementById("auth-overlay-note"),
  authForm: document.getElementById("auth-form"),
  authUsername: document.getElementById("auth-username"),
  authPassword: document.getElementById("auth-password"),
  authLoginBtn: document.getElementById("auth-login-btn"),
  authStatusLabel: document.getElementById("auth-status-label"),
  authLogoutBtn: document.getElementById("logout-btn"),
  messageBar: document.getElementById("message-bar"),
};

let socket = null;
let lastSnapshot = null;
let lastLeadsStatus = null;
let lastShardPreview = null;
let lastImportantLeadCheck = null;
let lastImportantLeadCheckJob = null;
let importantLeadCheckJobTimer = null;
let importantLeadCheckJobPollId = "";
let lastImportantVerify = null;
let lastImportantVerifyJob = null;
let importantLeadVerifyJobTimer = null;
let importantLeadVerifyJobPollId = "";
let lastImportantDispatch = null;
let lastImportantDispatchJob = null;
let importantLeadDispatchJobTimer = null;
let importantLeadDispatchJobPollId = "";
let lastImportantDispatchSource = null;
let lastImportantDispatchPreview = null;
let importantLeadDispatchPreviewLoading = false;
let importantLeadDispatchConfirmLoading = false;
let lastImportantDispatchPreviewState = "not_generated";
let lastQuarantineReview = null;
let lastQuarantineReviewLead = null;
let socketReconnectTimer = null;
let socketShouldReconnect = false;
let quarantineInboxOpen = false;
let quarantineToggleBtn = null;
const selectedQuarantineLeadIds = new Set();
const excludedQuarantineLeadIds = new Set();
let allFilteredQuarantineSelected = false;
let quarantinePageSize = 10;
let quarantinePageIndex = 0;
let didHydrate = false;
let selectedProfileName = "";
let senderStatusPanel = null;
let displayTimeZone = "America/Los_Angeles";
let wallboardMode = false;
let activeDashboardTab = "ops";
let authState = {
  authEnabled: true,
  authenticated: false,
  username: "",
};
const profileActionState = new Map();
const IMPORTANT_LEAD_CHECK_JOB_STORAGE_KEY = "emailautomation.activeImportantCheckJobId";
const IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY = "emailautomation.activeImportantVerifyJobId";
const IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY = "emailautomation.activeImportantDispatchJobId";
const VERIFY_MODE_FAST_TRIAGE = "FAST_TRIAGE";
const VERIFY_MODE_MANUAL_AUTHOR_RESEARCH = "MANUAL_AUTHOR_RESEARCH";
const VERIFY_MODE_STRICT_PUBLIC_PROOF = "STRICT_PUBLIC_PROOF";
const QUARANTINE_PAGE_SIZE_OPTIONS = [10, 25, 50, 100];
const VERIFY_FAST_DEFAULT_PATHS = {
  verified_path: "_important/leads_triaged_keep.csv",
  rejected_path: "_important/leads_triaged_reject.csv",
  quarantine_path: "_important/leads_triaged_quarantine.csv",
};
const VERIFY_STRICT_DEFAULT_PATHS = {
  verified_path: "_important/leads_verified.csv",
  rejected_path: "_important/leads_verify_rejected.csv",
  quarantine_path: "_important/leads_quarantine.csv",
};
const LEADS_RUN_SAFETY_COPY = [
  "Check Leads is running.",
  "Current leads.csv has not been published for this run.",
  "Triage output is stale.",
  "Dispatch preview is stale.",
  "Triaged Keep",
  "Dispatch Preview",
  "Confirm Dispatch blocked",
  "Check Leads is running for job",
];
const pendingProfileActions = new Map();
const profilePreviewValidationState = new Map();
const privateJcQueueRepairState = { kind: "", message: "", summary: null };

function currentActivityHours() {
  return els.hoursSelect?.value || "24";
}

function currentTailLines() {
  return els.tailSelect?.value || "12";
}

function setConnectionState(live) {
  els.wsIndicator.className = `dot ${live ? "dot-live" : "dot-off"}`;
  if (live) {
    els.wsLabel.textContent = "Ops socket live";
  } else if (isLeadsTabVisible() && lastLeadsStatus) {
    els.wsLabel.textContent = "Leads local snapshot loaded";
  } else {
    els.wsLabel.textContent = "Ops socket disconnected";
  }
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

function renderAuthUi() {
  const authenticated = Boolean(authState.authenticated);
  if (els.authStatusLabel) {
    setNodeText(
      els.authStatusLabel,
      authenticated
        ? `Signed in as ${authState.username || "admin"}`
        : authState.authEnabled
          ? "Signed out"
          : "Auth not configured",
    );
  }
  if (els.authLogoutBtn) {
    els.authLogoutBtn.disabled = !authenticated;
  }
  if (els.page) {
    els.page.classList.toggle("is-authenticated", authenticated);
  }
}

function showAuthOverlay(message = "") {
  if (els.authOverlay) {
    els.authOverlay.classList.remove("hidden");
    els.authOverlay.setAttribute("aria-hidden", "false");
  }
  if (els.authOverlayNote) {
    setNodeText(
      els.authOverlayNote,
      message || (authState.authEnabled ? "Sign in to unlock dashboard controls." : "Dashboard auth is not configured."),
    );
  }
  if (els.authLoginBtn) {
    els.authLoginBtn.disabled = false;
    setNodeText(els.authLoginBtn, authState.authEnabled ? "Sign in" : "Auth unavailable" );
  }
  if (els.page) {
    els.page.classList.add("is-auth-locked");
  }
}

function hideAuthOverlay() {
  if (els.authOverlay) {
    els.authOverlay.classList.add("hidden");
    els.authOverlay.setAttribute("aria-hidden", "true");
  }
  if (els.page) {
    els.page.classList.remove("is-auth-locked");
  }
}

function setAuthState(nextState = {}) {
  authState = {
    authEnabled: nextState.authEnabled ?? authState.authEnabled,
    authenticated: Boolean(nextState.authenticated),
    username: String(nextState.username || ""),
  };
  renderAuthUi();
  if (authState.authenticated) {
    hideAuthOverlay();
  } else {
    showAuthOverlay(nextState.message || "");
  }
}

async function fetchAuthStatus() {
  const response = await fetch("/api/auth/status", { credentials: "same-origin" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    throw new Error(data.message || data.detail || `Request failed (${response.status}).`);
  }
  setAuthState({
    authEnabled: Boolean(data.auth_enabled),
    authenticated: Boolean(data.authenticated),
    username: data.username || "",
  });
  return data;
}

async function submitAuthLogin() {
  const username = String(els.authUsername?.value || "").trim();
  const password = String(els.authPassword?.value || "");
  if (!username || !password) {
    showMessage("Enter a username and password.", "error");
    return;
  }
  if (els.authLoginBtn) {
    els.authLoginBtn.disabled = true;
    setNodeText(els.authLoginBtn, "Signing in...");
  }
  try {
    const data = await fetchJson("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ username, password }),
    });
    setAuthState({
      authEnabled: Boolean(data.auth_enabled),
      authenticated: Boolean(data.authenticated),
      username: data.username || username,
    });
    showMessage("Signed in.", "success");
    await bootstrapAuthenticatedDashboard();
  } catch (err) {
    setAuthState({ authEnabled: authState.authEnabled, authenticated: false, username: "", message: String(err) });
    showMessage(`Sign in failed: ${err}`, "error");
  } finally {
    if (els.authLoginBtn) {
      els.authLoginBtn.disabled = false;
      setNodeText(els.authLoginBtn, authState.authEnabled ? "Sign in" : "Auth unavailable");
    }
    if (els.authPassword) {
      els.authPassword.value = "";
    }
  }
}

async function submitAuthLogout() {
  try {
    await fetchJson("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
    });
  } catch (err) {
    // Fall through to local state reset even if the server session is already gone.
  }
  stopSocket();
  setAuthState({ authEnabled: authState.authEnabled, authenticated: false, username: "" });
  showMessage("Signed out.", "success");
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
    els.opsView.hidden = leadsActive;
  }

  if (els.leadsView) {
    els.leadsView.classList.toggle("hidden", !leadsActive);
    els.leadsView.hidden = !leadsActive;
  }

  if (els.opsTabBtn) {
    els.opsTabBtn.classList.toggle("is-active", !leadsActive);
    els.opsTabBtn.setAttribute("aria-selected", String(!leadsActive));
    els.opsTabBtn.tabIndex = !leadsActive ? 0 : -1;
  }

  if (els.leadsTabBtn) {
    els.leadsTabBtn.classList.toggle("is-active", leadsActive);
    els.leadsTabBtn.setAttribute("aria-selected", String(leadsActive));
    els.leadsTabBtn.tabIndex = leadsActive ? 0 : -1;
  }
}

function isOpsTabVisible() {
  return activeDashboardTab === "ops" || wallboardMode;
}

function isLeadsTabVisible() {
  return activeDashboardTab === "leads" && !wallboardMode;
}

function markDashboardHydrated() {
  if (!didHydrate && els.page) {
    didHydrate = true;
    requestAnimationFrame(() => {
      els.page.classList.remove("booting");
    });
  }
}

function stopLeadsBackgroundActivity() {
  stopImportantLeadCheckJobPolling();
  stopImportantLeadVerifyJobPolling();
  stopImportantLeadDispatchJobPolling();
  closeQuarantineInbox();
}

function syncTabBackgroundActivity() {
  if (isOpsTabVisible()) {
    void fetchSnapshot();
    connectSocket();
  } else {
    stopSocket();
  }
  if (!isLeadsTabVisible()) {
    stopLeadsBackgroundActivity();
  }
}

function applyLeadsTriageCopy() {
  const verifyPanel = els.leadsImportantVerifyBtn?.closest?.(".leads-step-panel");
  const eyebrow = verifyPanel?.querySelector?.(".panel-header .eyebrow");
  const heading = verifyPanel?.querySelector?.(".panel-header h2");
  const helper = verifyPanel?.querySelector?.(".panel-header .muted");
  if (eyebrow) {
    setNodeText(eyebrow, "Lead Triage");
  }
  if (heading) {
    setNodeText(heading, "Lead Triage");
  }
  if (helper) {
    setNodeText(
      helper,
      "Fast Triage is the default lead gate. Open Quarantine Inbox only when you need manual review.",
    );
  }
}

function setQuarantineInboxOpen(open, { load = false } = {}) {
  quarantineInboxOpen = Boolean(open);
  if (els.leadsQuarantineShell) {
    els.leadsQuarantineShell.hidden = !quarantineInboxOpen;
    els.leadsQuarantineShell.classList.toggle("hidden", !quarantineInboxOpen);
  }
  if (quarantineToggleBtn) {
    quarantineToggleBtn.setAttribute("aria-expanded", String(quarantineInboxOpen));
    setNodeText(quarantineToggleBtn, quarantineInboxOpen ? "Close Quarantine Inbox" : "Open Quarantine Inbox");
  }
  if (!quarantineInboxOpen) {
    clearQuarantineSelection();
    lastQuarantineReview = null;
    lastQuarantineReviewLead = null;
    if (els.leadsQuarantineMeta) {
      setNodeText(els.leadsQuarantineMeta, "Quarantine review is closed.");
    }
    if (els.leadsQuarantineResults) {
      setNodeHtml(els.leadsQuarantineResults, "");
    }
    return;
  }
  if (load) {
    quarantinePageSize = 10;
    quarantinePageIndex = 0;
    void refreshQuarantineReview(false, true);
  }
}

function openQuarantineInbox({ load = true } = {}) {
  setQuarantineInboxOpen(true, { load });
}

function closeQuarantineInbox() {
  setQuarantineInboxOpen(false);
}

function initQuarantineInboxDisclosure() {
  if (!els.leadsQuarantineShell || quarantineToggleBtn) return;
  quarantineToggleBtn = document.createElement("button");
  quarantineToggleBtn.type = "button";
  quarantineToggleBtn.className = "btn btn-secondary";
  quarantineToggleBtn.setAttribute("aria-expanded", "false");
  setNodeText(quarantineToggleBtn, "Open Quarantine Inbox");
  quarantineToggleBtn.addEventListener("click", () => {
    if (quarantineInboxOpen) closeQuarantineInbox();
    else openQuarantineInbox({ load: true });
  });
  els.leadsQuarantineShell.parentNode?.insertBefore(quarantineToggleBtn, els.leadsQuarantineShell);
  closeQuarantineInbox();
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
  syncTabBackgroundActivity();
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
  syncTabBackgroundActivity();
  if (isLeadsTabVisible()) {
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
  const providerRemaining = Number(profile?.provider_cooldown_remaining_seconds ?? 0);
  if (Number.isFinite(providerRemaining) && providerRemaining > 0) return Math.max(0, Math.round(providerRemaining));
  const remaining = Number(profile?.cooldown_remaining_seconds ?? 0);
  if (!Number.isFinite(remaining) || remaining <= 0) return 0;
  return Math.max(0, Math.round(remaining));
}

function profileCooldownDisplay(profile, options = {}) {
  const remaining = profileCooldownRemaining(profile);
  if (remaining > 0) {
    return {
      text: humanizeCooldownRemaining(remaining),
      title: `Cooldown: ${remaining}s remaining`,
      countdown: remaining,
      active: true,
    };
  }
  return {
    text: "Ready",
    title: "No active cooldown",
    countdown: null,
    active: false,
  };
}

function profileLastUpdateText(profile) {
  const remaining = profileCooldownRemaining(profile);
  if ((profile?.runtime_state || "") === "paused" && remaining > 0) {
    return `Paused ${humanizeDurationCompact(remaining)} remaining`;
  }
  if ((profile?.runtime_state || "") === "cooldown" && remaining > 0) {
    return `Cooldown ${remaining}s remaining`;
  }
  return `Last update ${profile?.last_age || "-"}`;
}

function profileLastAgeText(profile) {
  const remaining = profileCooldownRemaining(profile);
  if ((profile?.runtime_state || "") === "paused" && remaining > 0) {
    return `Next safe start in ${humanizeDurationCompact(remaining)}`;
  }
  if ((profile?.runtime_state || "") === "cooldown" && remaining > 0) {
    return `Next send in ${remaining}s`;
  }
  return profile?.last_age ? `Age ${profile.last_age}` : "No recent sender log line";
}

function profileRunSentDisplay(profile) {
  const displayValue = Number(profile?.run_sent_display);
  if (Number.isFinite(displayValue)) return displayValue;
  const canonicalValue = Number(profile?.run_sent);
  if (Number.isFinite(canonicalValue)) return canonicalValue;
  return 0;
}

// Backwards-compatible alias: prefer the UI-only display value when present.
// Use this helper in rendering code when the displayed "Accepted" count
// should reflect server-provided `run_sent_display` (fallback to canonical
// `run_sent` when the display value is absent).
function profileRunSentPrefer(profile) {
  return profileRunSentDisplay(profile);
}

function formatPercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return `${(num * 100).toFixed(1)}%`;
}

function renderSummaryDetails(details = []) {
  if (!Array.isArray(details) || !details.length) return "";
  return `
    <div class="summary-insight-list">
      ${details
        .filter((item) => String(item?.label || "").trim() || String(item?.value ?? "").trim())
        .slice(0, 3)
        .map((item) => `
          <div class="summary-insight-row">
            <span class="summary-insight-label">${escapeHtml(item?.label || "")}</span>
            <span class="summary-insight-value">${escapeHtml(item?.value ?? "")}</span>
          </div>
        `)
        .join("")}
    </div>
  `;
}

function fleetProfileStatus(profile) {
  const state = String(profile?.runtime_state || "").trim();
  const name = formatProfileName(profile?.name || "");
  if (["running", "starting", "sleeping"].includes(state)) {
    return { name, label: "Live", tone: "good" };
  }
  if (["cooldown", "paused"].includes(state)) {
    return { name, label: state === "paused" ? "Paused" : "Cooldown", tone: "warn" };
  }
  return { name, label: "Stopped", tone: "bad" };
}

function renderFleetProfileStrip(profiles = []) {
  if (!Array.isArray(profiles) || !profiles.length) return "";
  return `
    <div class="summary-fleet-matrix">
      ${profiles.map((profile) => {
        const status = fleetProfileStatus(profile);
        return `
          <div class="summary-fleet-row summary-fleet-row-${escapeHtml(status.tone || "neutral")}">
            <span class="summary-fleet-name">${escapeHtml(status.name)}</span>
            <span class="summary-fleet-state">
              <span class="summary-fleet-dot"></span>
              <span>${escapeHtml(status.label)}</span>
            </span>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderSummaryInsightList(items = [], emptyText = "") {
  if (!Array.isArray(items) || !items.length) {
    return emptyText ? `<div class="summary-note">${escapeHtml(emptyText)}</div>` : "";
  }
  return `
    <div class="summary-insight-list">
      ${items.slice(0, 3).map((item) => `
        <div class="summary-insight-row">
          <span class="summary-insight-label">${escapeHtml(item.label || "")}</span>
          <span class="summary-insight-value">${escapeHtml(item.value ?? "")}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function isSummaryTextValue(value) {
  const text = String(value ?? "");
  return /[A-Za-z]/.test(text) || text.length >= 8;
}

function compactSummaryNote(note = "", details = []) {
  const plainNote = String(note || "")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (plainNote) return plainNote;
  if (Array.isArray(details) && details.length) {
    const first = details[0] || {};
    return [String(first.label || "").trim(), String(first.value ?? "").trim()].filter(Boolean).join(" · ");
  }
  return "";
}

function summaryCard(label, value, note = "", details = []) {
  const valueClass = isSummaryTextValue(value) ? "summary-value summary-value-text" : "summary-value";
  const compactNote = compactSummaryNote(note, details);
  return `
    <article class="summary-card summary-card-neutral summary-card-compact fleet-module">
      <div class="summary-head fleet-module-head">
        <div class="summary-label">${label}</div>
        <span class="summary-spark summary-spark-neutral"></span>
      </div>
      <div class="fleet-module-body">
        <div class="${valueClass}">${value}</div>
        <div class="summary-note">${escapeHtml(compactNote)}</div>
      </div>
      <div class="summary-details-slot"></div>
    </article>
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

function setButtonBusy(button, busy, label) {
  if (!button) return;
  button.classList.toggle("is-loading", Boolean(busy));
  button.disabled = Boolean(busy);
  if (label !== undefined) {
    setNodeText(button, label);
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

function safeTimestampMs(value) {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function currentImportantCheckJob(status = lastLeadsStatus) {
  return status?.active_important_check_job || lastImportantLeadCheckJob || null;
}

function importantCheckJobProgress(job) {
  const processed = Number(job?.processed_rows ?? job?.processed ?? 0);
  const total = Number(job?.total_rows ?? job?.total ?? 0);
  const explicitPercent = Number(job?.progress_percent);
  const percent = Number.isFinite(explicitPercent)
    ? Math.min(100, Math.max(0, explicitPercent))
    : (total > 0 ? Math.min(100, Math.max(0, (processed / total) * 100)) : 0);
  return { processed, total, percent };
}

function outputFreshnessLabel(value) {
  if (value === true) return "Fresh";
  if (value === false) return "Stale";
  return "Unknown";
}

function hasCaseInsensitiveField(fields = [], fieldName = "") {
  const expected = String(fieldName || "").trim().toLowerCase();
  return Array.isArray(fields) && fields.some((field) => String(field || "").trim().toLowerCase() === expected);
}

function recipientQueueBookTitleStatus(status = lastLeadsStatus) {
  const queues = [];
  if (status?.jc_queue) {
    queues.push({
      label: "private_jc",
      fields: Array.isArray(status.jc_queue.fieldnames) ? status.jc_queue.fieldnames : [],
    });
  }
  if (Array.isArray(status?.sendgrid_queues)) {
    status.sendgrid_queues.forEach((queue) => {
      queues.push({
        label: queue.profile || queue.name || queue.path || "sendgrid",
        fields: Array.isArray(queue.fieldnames) ? queue.fieldnames : [],
      });
    });
  }
  const missing = queues
    .filter((queue) => !hasCaseInsensitiveField(queue.fields, "BookTitle"))
    .map((queue) => queue.label);
  return { checked: queues.length > 0, missing };
}

function leadsRunSafety(status = lastLeadsStatus, snapshot = lastSnapshot) {
  const backendCurrentSafety = status?.current_send_safety || {};
  const activeCheckJob = currentImportantCheckJob(status);
  const checkRunning = isActiveImportantLeadCheckJob(activeCheckJob);
  const activeSenders = activeSenderProfiles(snapshot);
  const latestCheck = status?.latest_master_check || {};
  const latestTriage = status?.latest_lead_triage || status?.latest_lead_verify || {};
  const latestPreview = status?.latest_auto_dispatch_preview || {};
  const latestCheckTime = safeTimestampMs(latestCheck.generated_at_utc);
  const latestTriageTime = safeTimestampMs(latestTriage.generated_at_utc);
  const previewTime = safeTimestampMs(latestPreview.generated_at_utc || latestPreview.completed_at_utc || latestPreview.created_at_utc);
  const queueUnsafe = Object.prototype.hasOwnProperty.call(backendCurrentSafety, "blocked")
    ? Boolean(backendCurrentSafety.blocked)
    : queueSafetyBlocked(snapshot);
  const bookTitleStatus = recipientQueueBookTitleStatus(status);
  const progress = importantCheckJobProgress(activeCheckJob);

  const leadsFresh = checkRunning ? false : Boolean(latestCheckTime);
  const triageFresh = checkRunning ? false : (latestCheckTime ? latestTriageTime >= latestCheckTime && latestTriageTime > 0 : null);
  const previewFresh = checkRunning
    ? false
    : (latestTriageTime
      ? (previewTime ? previewTime >= latestTriageTime : Boolean(latestPreview.preview_id || latestPreview.preview_path || latestPreview.status))
      : null);

  const reasons = [];
  if (Array.isArray(backendCurrentSafety.reasons) && backendCurrentSafety.reasons.length) {
    reasons.push(...backendCurrentSafety.reasons.map((reason) => String(reason || "")).filter(Boolean));
  }
  if (bookTitleStatus.missing.length) {
    reasons.push(`Recipient queues are missing BookTitle: ${bookTitleStatus.missing.join(", ")}.`);
  }
  if (queueUnsafe) reasons.push(queueSafetyBlockMessage(snapshot) || "Queue safety is unsafe.");

  let statusLabel = "SAFE TO CONTINUE";
  if (queueUnsafe) {
    statusLabel = "BLOCKED";
  }

  const uploadFilename = activeCheckJob?.selected_filename
    || activeCheckJob?.original_uploaded_filename
    || activeCheckJob?.server_received_filename
    || activeCheckJob?.source_label
    || latestCheck.input_label
    || "-";
  const checkJobId = activeCheckJob?.job_id || latestCheck.check_job_id || latestCheck.job_id || "-";

  return {
    statusLabel,
    reasons,
    checkRunning,
    activeSenders,
    queueUnsafe,
    progress,
    uploadFilename,
    checkJobId,
    leadsFresh,
    triageFresh,
    previewFresh,
    bookTitleStatus,
    nextBatchPrep: status?.next_batch_prep || {},
  };
}

function dispatchActionBlockReason() {
  const safety = leadsRunSafety();
  if (safety.checkRunning) {
    return `Check Leads is running for job ${safety.checkJobId}. Wait until leads.csv, triage, and preview are fresh.`;
  }
  if (safety.activeSenders.length) {
    return `Active senders are running: ${safety.activeSenders.map((profile) => `${formatProfileName(profile.name)} (${profile.runtime_state})`).join(", ")}.`;
  }
  return "";
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

function currentDispatchPlanKey() {
  return [
    els.leadsImportantDispatchSourceMode?.value || "triaged_keep",
    els.leadsImportantDispatchCap?.value || "all",
  ].join("|");
}

function dispatchPreviewMatchesCurrentSelection() {
  return Boolean(lastImportantDispatchPreview && lastImportantDispatchPreview._preview_key === currentDispatchPlanKey());
}

function selectedLeadsMapping() {
  return {
    email: els.leadsEmailColumn?.value || "",
    first_name: els.leadsFirstNameColumn?.value || "",
    book_title: els.leadsBookColumn?.value || "",
  };
}

function importantLeadPathsPayload() {
  return {
    intake_mode: els.leadsImportantIntakeMode?.value || "standard",
    input_path: els.leadsImportantInputPath?.value?.trim() || "",
    output_path: els.leadsImportantOutputPath?.value?.trim() || "",
    rejected_path: els.leadsImportantRejectedPath?.value?.trim() || "",
    dispatch_source_mode: els.leadsImportantDispatchSourceMode?.value || "triaged_keep",
    input_text: els.leadsImportantInputText?.value || "",
  };
}

function importantLeadDispatchPayload(includePreviewId = false) {
  const payload = {
    input_path: els.leadsImportantInputPath?.value?.trim() || "",
    output_path: els.leadsImportantOutputPath?.value?.trim() || "",
    rejected_path: els.leadsImportantRejectedPath?.value?.trim() || "",
    dispatch_source_mode: els.leadsImportantDispatchSourceMode?.value || "triaged_keep",
    dispatch_cap: els.leadsImportantDispatchCap?.value || "all",
  };
  if (includePreviewId) {
    payload.preview_id = lastImportantDispatchPreview?.preview_id || "";
  }
  return payload;
}

function importantLeadPastePolicy() {
  const policy = lastLeadsStatus?.check_paste_policy || {};
  return {
    mode: policy.mode || "small_manual_only",
    warningRows: Number(policy.paste_warning_rows || 250),
    maxRows: Number(policy.paste_max_rows || 1000),
    uploadRequiredRows: Number(policy.upload_required_rows || 1000),
    uploadRecommendedRows: Number(policy.upload_recommended_rows || 250),
  };
}

function estimateImportantLeadPasteRows(text) {
  const normalized = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (!normalized) return 0;
  return normalized
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .length;
}

function updateImportantLeadPasteGuardrails() {
  const policy = importantLeadPastePolicy();
  const text = String(els.leadsImportantInputText?.value || "");
  const estimatedRows = estimateImportantLeadPasteRows(text);
  const limit = Math.max(1, policy.maxRows || 1000);
  const warning = Math.max(1, Math.min(policy.warningRows || 250, limit));
  if (!text.trim()) {
    if (els.leadsImportantPasteNote) {
      setNodeText(
        els.leadsImportantPasteNote,
        `Small/manual only. Use Upload CSV for ${limit}+ rows. Paste first, then Check Leads writes the run file and cleans it into Output and Rejected. Use FullName upstream when you have it.`,
      );
    }
    if (els.leadsImportantCheckBtn) {
      els.leadsImportantCheckBtn.disabled = false;
    }
    return;
  }
  if (estimatedRows > limit) {
    if (els.leadsImportantPasteNote) {
      setNodeText(
        els.leadsImportantPasteNote,
        `Paste detected about ${estimatedRows} row(s). Paste intake is limited to ${limit} rows. Use Upload CSV for this batch.`,
      );
    }
    if (els.leadsImportantCheckBtn) {
      els.leadsImportantCheckBtn.disabled = true;
    }
    return;
  }
  if (els.leadsImportantPasteNote) {
    const suffix = estimatedRows >= warning
      ? `Estimated ${estimatedRows} row(s). Upload CSV is recommended above ${warning} rows.`
      : `Estimated ${estimatedRows} row(s). Small/manual only.`;
    setNodeText(
      els.leadsImportantPasteNote,
      `${suffix} Paste first, then Check Leads writes the run file and cleans it into Output and Rejected. Use FullName upstream when you have it.`,
    );
  }
  if (els.leadsImportantCheckBtn) {
    els.leadsImportantCheckBtn.disabled = false;
  }
}

function importantLeadUploadPayload() {
  const formData = new FormData();
  const { file, filename, size, extension } = selectedImportantLeadUploadFile();
  if (file) {
    formData.append("file", file);
  }
  formData.append("client_selected_filename", filename);
  formData.append("client_selected_size_bytes", String(size || 0));
  formData.append("client_selected_extension", extension);
  formData.append("intake_mode", els.leadsImportantIntakeMode?.value || "standard");
  formData.append("output_path", els.leadsImportantOutputPath?.value?.trim() || "");
  formData.append("rejected_path", els.leadsImportantRejectedPath?.value?.trim() || "");
  return { formData, file, filename, size, extension };
}

function humanizeFileSize(bytes) {
  const size = Number(bytes);
  if (!Number.isFinite(size) || size < 0) return "-";
  if (size < 1024) return `${size} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = size / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}

function selectedImportantLeadUploadFile() {
  const file = els.leadsImportantUploadFile?.files?.[0] || null;
  const filename = file?.name ? String(file.name) : "";
  const extension = filename.includes(".") ? filename.slice(filename.lastIndexOf(".")).toLowerCase() : "";
  return {
    file,
    filename,
    size: Number(file?.size || 0),
    extension,
  };
}

function updateImportantLeadUploadNote(extra = "") {
  const { filename, size, extension } = selectedImportantLeadUploadFile();
  const base = filename
    ? `Selected ${filename} (${humanizeFileSize(size)}, ${extension || "no extension"}). Uploads are file-only and never reuse the stored input path.`
    : "Choose a CSV or XLSX file, then click Upload & Check. Uploads are file-only and never reuse the stored input path.";
  if (els.leadsImportantUploadNote) {
    setNodeText(els.leadsImportantUploadNote, extra ? `${base} ${extra}` : base);
  }
  return { filename, size, extension };
}

function importantLeadCheckJobStatus(job) {
  return String(job?.status || job?.stage || "queued").toLowerCase();
}

function isTerminalImportantLeadCheckJob(job) {
  return ["completed", "failed", "canceled", "cancelled"].includes(importantLeadCheckJobStatus(job));
}

function isActiveImportantLeadCheckJob(job) {
  return Boolean(job?.job_id) && !isTerminalImportantLeadCheckJob(job);
}

function readSavedImportantLeadCheckJobId() {
  try {
    return String(localStorage.getItem(IMPORTANT_LEAD_CHECK_JOB_STORAGE_KEY) || "").trim();
  } catch (err) {
    return "";
  }
}

function saveImportantLeadCheckJobId(jobId) {
  const cleanJobId = String(jobId || "").trim();
  if (!cleanJobId) return;
  try {
    localStorage.setItem(IMPORTANT_LEAD_CHECK_JOB_STORAGE_KEY, cleanJobId);
  } catch (err) {
    // localStorage may be unavailable in private or restricted browser contexts.
  }
}

function clearSavedImportantLeadCheckJobId(jobId = "") {
  const cleanJobId = String(jobId || "").trim();
  try {
    const savedJobId = readSavedImportantLeadCheckJobId();
    if (!cleanJobId || !savedJobId || savedJobId === cleanJobId) {
      localStorage.removeItem(IMPORTANT_LEAD_CHECK_JOB_STORAGE_KEY);
    }
  } catch (err) {
    // no-op
  }
}

function readSavedJobId(storageKey) {
  try {
    return String(localStorage.getItem(storageKey) || "").trim();
  } catch (err) {
    return "";
  }
}

function saveJobId(storageKey, jobId) {
  const cleanJobId = String(jobId || "").trim();
  if (!cleanJobId) return;
  try {
    localStorage.setItem(storageKey, cleanJobId);
  } catch (err) {
    // no-op
  }
}

function clearSavedJobId(storageKey, jobId = "") {
  const cleanJobId = String(jobId || "").trim();
  try {
    const savedJobId = readSavedJobId(storageKey);
    if (!cleanJobId || !savedJobId || savedJobId === cleanJobId) {
      localStorage.removeItem(storageKey);
    }
  } catch (err) {
    // no-op
  }
}

function accessibleProgressBar(progressPercent, etaText, label = "Progress") {
  const progress = Math.min(100, Math.max(0, Number(progressPercent) || 0));
  const percentLabel = `${progress.toFixed(progress % 1 ? 1 : 0)}%`;
  const valueText = `${percentLabel}${etaText && etaText !== "n/a" ? `, ETA ${etaText}` : ""}`;
  return `
    <div class="progress-wrap">
      <div class="progress-label">
        <span>${escapeHtml(label)}</span>
        <span>${escapeHtml(percentLabel)}</span>
      </div>
      <div
        class="progress-bar"
        role="progressbar"
        aria-valuenow="${progress.toFixed(1)}"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuetext="${escapeHtml(valueText)}"
      >
        <div class="progress-fill" style="width: ${progress}%;"></div>
      </div>
    </div>
  `;
}

function stopImportantLeadCheckJobPolling() {
  if (importantLeadCheckJobTimer) {
    clearTimeout(importantLeadCheckJobTimer);
    importantLeadCheckJobTimer = null;
  }
  importantLeadCheckJobPollId = "";
}

function renderImportantLeadCheckJob(job) {
  if (!job || !job.job_id) return;
  const status = importantLeadCheckJobStatus(job);
  const label = status === "completed"
    ? "Upload check complete"
    : status === "failed"
      ? "Upload check failed"
      : `Upload check ${status}`;
  const detail = job.message || job.error || job.stage || "";
  lastImportantLeadCheckJob = job;
  const selectedFilename = job.selected_filename || job.original_uploaded_filename || job.source_label || "-";
  const serverFilename = job.server_received_filename || job.original_uploaded_filename || job.source_label || "-";
  if (isActiveImportantLeadCheckJob(job)) {
    saveImportantLeadCheckJobId(job.job_id);
  } else if (isTerminalImportantLeadCheckJob(job)) {
    clearSavedImportantLeadCheckJobId(job.job_id);
  }
  if (els.leadsImportantCheckMeta) {
    setNodeText(
      els.leadsImportantCheckMeta,
      detail ? `${label}: ${detail}` : `${label}.`,
    );
  }
  renderLeadsWorkflowStatusBanner(lastLeadsStatus);
  if (status !== "completed" && status !== "failed" && els.leadsImportantCheckResults) {
    const stage = job.stage || status || "queued";
    const totalRows = Number(job.total_input_rows || 0);
    const processedRows = Number(job.processed_rows || 0);
    const remainingRows = Number(job.remaining_rows || Math.max(0, totalRows - processedRows));
    const explicitProgress = Number(job.progress_percent);
    const progressPercent = Number.isFinite(explicitProgress)
      ? Math.min(100, Math.max(0, explicitProgress))
      : (totalRows > 0 ? Math.min(100, Math.max(0, (processedRows / totalRows) * 100)) : 0);
    const etaSeconds = Number(job.eta_seconds);
    const etaText = Number.isFinite(etaSeconds) && etaSeconds > 0 ? humanizeDurationCompact(etaSeconds) : "n/a";
    const updatedText = job.updated_at_utc ? formatGeneratedAt(job.updated_at_utc) : "-";
    const sheetName = job.current_sheet || job.source_sheet || job.sheet_name || "";
    setNodeHtml(
      els.leadsImportantCheckResults,
      `
        <article class="leads-result-card">
          <h3>Upload Job</h3>
          ${accessibleProgressBar(progressPercent, etaText, "Check progress")}
          <div class="leads-kpis">
            <div class="leads-kpi"><div class="label">Stage</div><div class="value">${escapeHtml(stage)}</div></div>
            <div class="leads-kpi"><div class="label">Rows</div><div class="value">${totalRows}</div></div>
            <div class="leads-kpi"><div class="label">Processed</div><div class="value">${processedRows}</div></div>
            <div class="leads-kpi"><div class="label">Remaining</div><div class="value">${remainingRows}</div></div>
            <div class="leads-kpi"><div class="label">ETA</div><div class="value">${escapeHtml(etaText)}</div></div>
            <div class="leads-kpi"><div class="label">Updated</div><div class="value">${escapeHtml(updatedText)}</div></div>
          </div>
          <div class="pill-row">
            <span class="mini-pill">Job ${escapeHtml(job.job_id || "-")}</span>
            <span class="mini-pill">Mode ${escapeHtml(job.source_mode || "uploaded_file")}</span>
            <span class="mini-pill">Intake mode ${escapeHtml(job.intake_mode_label || (job.intake_mode === VERIFY_MODE_MANUAL_AUTHOR_RESEARCH ? "Manual Author Research" : "Standard"))}</span>
            <span class="mini-pill">Selected ${escapeHtml(selectedFilename)}</span>
            <span class="mini-pill">Server ${escapeHtml(serverFilename)}</span>
            ${sheetName ? `<span class="mini-pill">Sheet ${escapeHtml(sheetName)}</span>` : ""}
          </div>
        </article>
      `,
    );
  }
}

async function pollImportantLeadCheckJob(jobId) {
  if (!jobId) return;
  stopImportantLeadCheckJobPolling();
  importantLeadCheckJobPollId = String(jobId);
  try {
    const data = await fetchJson(`/api/leads/check-important/job/${encodeURIComponent(jobId)}`);
    const job = data.job || {};
    renderImportantLeadCheckJob(job);
    if (job.status === "completed") {
      stopImportantLeadCheckJobPolling();
      clearSavedImportantLeadCheckJobId(job.job_id || jobId);
      lastImportantLeadCheck = job.check || null;
      if (data.status) {
        renderLeadsStatus(data.status || {});
      } else {
        renderImportantLeadCheck(lastImportantLeadCheck);
      }
      showMessage(job.message || "Upload check complete.", "success");
      return;
    }
    if (job.status === "failed" || job.status === "canceled" || job.status === "cancelled") {
      stopImportantLeadCheckJobPolling();
      clearSavedImportantLeadCheckJobId(job.job_id || jobId);
      showMessage(job.error || "Upload check failed.", "error");
      return;
    }
    importantLeadCheckJobTimer = setTimeout(() => pollImportantLeadCheckJob(jobId), 1500);
  } catch (err) {
    if (String(err || "").includes("not found")) {
      clearSavedImportantLeadCheckJobId(jobId);
      stopImportantLeadCheckJobPolling();
      return;
    }
    showMessage(`Upload job poll failed: ${err}`, "error");
    importantLeadCheckJobTimer = setTimeout(() => pollImportantLeadCheckJob(jobId), 2500);
  }
}

function resumeImportantLeadCheckJob(job) {
  if (!isActiveImportantLeadCheckJob(job)) {
    if (isTerminalImportantLeadCheckJob(job)) {
      clearSavedImportantLeadCheckJobId(job?.job_id || "");
    }
    return false;
  }
  renderImportantLeadCheckJob(job);
  const jobId = String(job.job_id || "");
  if (importantLeadCheckJobPollId !== jobId) {
    void pollImportantLeadCheckJob(jobId);
  }
  return true;
}

async function hydrateImportantLeadCheckJobOnLoad() {
  const savedJobId = readSavedImportantLeadCheckJobId();
  if (savedJobId) {
    try {
      const data = await fetchJson(`/api/leads/check-important/job/${encodeURIComponent(savedJobId)}`);
      const job = data.job || null;
      if (resumeImportantLeadCheckJob(job)) return;
      if (job && isTerminalImportantLeadCheckJob(job)) {
        renderImportantLeadCheckJob(job);
        if (job.status === "completed" && job.check) {
          lastImportantLeadCheck = job.check;
          renderImportantLeadCheck(lastImportantLeadCheck);
        }
      }
    } catch (err) {
      clearSavedImportantLeadCheckJobId(savedJobId);
    }
  }
  try {
    const data = await fetchJson("/api/leads/check-important/active");
    resumeImportantLeadCheckJob(data.job || null);
  } catch (err) {
    // Leads status still renders normally if active-job hydration is unavailable.
  }
}

function stopImportantLeadVerifyJobPolling() {
  if (importantLeadVerifyJobTimer) {
    clearTimeout(importantLeadVerifyJobTimer);
    importantLeadVerifyJobTimer = null;
  }
  importantLeadVerifyJobPollId = "";
}

function renderImportantLeadVerifyJob(job) {
  if (!job || !job.job_id) return;
  lastImportantVerifyJob = job;
  const status = importantLeadCheckJobStatus(job);
  const active = isActiveImportantLeadCheckJob(job);
  const mode = String(job.mode || VERIFY_MODE_FAST_TRIAGE).toUpperCase();
  const modeLabel = mode === VERIFY_MODE_STRICT_PUBLIC_PROOF ? "Strict Public Proof" : mode === VERIFY_MODE_MANUAL_AUTHOR_RESEARCH ? "Manual Author Research" : "Fast Triage";
  if (active) {
    saveJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY, job.job_id);
  } else if (isTerminalImportantLeadCheckJob(job)) {
    clearSavedJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY, job.job_id);
  }
  const stage = job.phase || job.stage || status || "queued";
  const totalRows = Number(job.total_rows || job.total_input_rows || 0);
  const processedRows = Number(job.processed_rows || 0);
  const remainingRows = Number(job.remaining_rows || Math.max(0, totalRows - processedRows));
  const progressPercent = Number.isFinite(Number(job.progress_percent))
    ? Math.min(100, Math.max(0, Number(job.progress_percent)))
    : (totalRows > 0 ? Math.min(100, Math.max(0, (processedRows / totalRows) * 100)) : 0);
  const etaSeconds = Number(job.eta_seconds);
  const etaText = Number.isFinite(etaSeconds) && etaSeconds > 0 ? humanizeDurationCompact(etaSeconds) : "n/a";
  const updatedText = job.updated_at_utc ? formatGeneratedAt(job.updated_at_utc) : "-";
  if (els.leadsImportantVerifyMeta) {
    setNodeText(els.leadsImportantVerifyMeta, `Verify job ${status}: ${job.message || job.error || stage}.`);
  }
  if (els.leadsImportantVerifyBtn) {
    setButtonBusy(els.leadsImportantVerifyBtn, active, active ? "Verifying..." : "Fast Triage");
  }
  if (els.leadsImportantVerifyStrictBtn) {
    setButtonBusy(els.leadsImportantVerifyStrictBtn, active, active ? "Verifying..." : "Strict Public Proof");
  }
  if (els.leadsImportantVerifyStopBtn) {
    els.leadsImportantVerifyStopBtn.disabled = !active || Boolean(job.cancel_requested);
    setNodeText(els.leadsImportantVerifyStopBtn, job.cancel_requested ? "Stopping..." : "Stop Verify");
  }
  if (els.leadsImportantVerifyResults && active) {
    setNodeHtml(
      els.leadsImportantVerifyResults,
      `
        <article class="leads-result-card">
          <h3>Verify Job</h3>
          ${accessibleProgressBar(progressPercent, etaText, "Verify progress")}
          <div class="leads-kpis">
            <div class="leads-kpi"><div class="label">Phase</div><div class="value">${escapeHtml(stage)}</div></div>
            <div class="leads-kpi"><div class="label">Mode</div><div class="value">${escapeHtml(modeLabel)}</div></div>
            <div class="leads-kpi"><div class="label">Rows</div><div class="value">${totalRows}</div></div>
            <div class="leads-kpi"><div class="label">Processed</div><div class="value">${processedRows}</div></div>
            <div class="leads-kpi"><div class="label">Remaining</div><div class="value">${remainingRows}</div></div>
            <div class="leads-kpi"><div class="label">ETA</div><div class="value">${escapeHtml(etaText)}</div></div>
            <div class="leads-kpi"><div class="label">Updated</div><div class="value">${escapeHtml(updatedText)}</div></div>
          </div>
          <div class="pill-row">
            <span class="mini-pill">Job ${escapeHtml(job.job_id || "-")}</span>
            <span class="mini-pill">Input ${escapeHtml(job.input_path || "-")}</span>
            <span class="mini-pill">Keep ${escapeHtml(job.verified_path || "-")}</span>
          </div>
        </article>
      `,
    );
  }
  renderLeadsWorkflowStatusBanner(lastLeadsStatus);
}

async function stopImportantLeadVerify() {
  const jobId = String(lastImportantVerifyJob?.job_id || readSavedJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY) || "").trim();
  if (!jobId) {
    showMessage("No active Verify job to stop.", "error");
    return;
  }
  if (els.leadsImportantVerifyStopBtn) {
    els.leadsImportantVerifyStopBtn.disabled = true;
    setNodeText(els.leadsImportantVerifyStopBtn, "Stopping...");
  }
  try {
    const data = await fetchJson(`/api/leads/verify-important/job/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
    });
    if (data.job) {
      renderImportantLeadVerifyJob(data.job);
    }
    showMessage(data.message || "Stop requested for Verify Leads.", "success");
  } catch (err) {
    showMessage(`Stop Verify failed: ${err}`, "error");
    if (els.leadsImportantVerifyStopBtn) {
      els.leadsImportantVerifyStopBtn.disabled = false;
      setNodeText(els.leadsImportantVerifyStopBtn, "Stop Verify");
    }
  }
}

async function pollImportantLeadVerifyJob(jobId) {
  if (!jobId) return;
  stopImportantLeadVerifyJobPolling();
  importantLeadVerifyJobPollId = String(jobId);
  try {
    const data = await fetchJson(`/api/leads/verify-important/job/${encodeURIComponent(jobId)}`);
    const job = data.job || {};
    renderImportantLeadVerifyJob(job);
    if (job.status === "completed") {
      stopImportantLeadVerifyJobPolling();
      clearSavedJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY, job.job_id || jobId);
      lastImportantVerify = job.verify || null;
      if (data.status) renderLeadsStatus(data.status || {});
      else renderImportantLeadVerify(lastImportantVerify);
      showMessage(job.message || "Lead verification complete.", "success");
      return;
    }
    if (job.status === "failed" || job.status === "canceled" || job.status === "cancelled") {
      stopImportantLeadVerifyJobPolling();
      clearSavedJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY, job.job_id || jobId);
      showMessage(job.error || "Lead verification failed.", "error");
      return;
    }
    importantLeadVerifyJobTimer = setTimeout(() => pollImportantLeadVerifyJob(jobId), 1500);
  } catch (err) {
    if (String(err || "").includes("not found")) {
      clearSavedJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY, jobId);
      stopImportantLeadVerifyJobPolling();
      return;
    }
    showMessage(`Verify job poll failed: ${err}`, "error");
    importantLeadVerifyJobTimer = setTimeout(() => pollImportantLeadVerifyJob(jobId), 2500);
  }
}

function resumeImportantLeadVerifyJob(job) {
  if (!isActiveImportantLeadCheckJob(job)) {
    if (isTerminalImportantLeadCheckJob(job)) {
      clearSavedJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY, job?.job_id || "");
    }
    return false;
  }
  renderImportantLeadVerifyJob(job);
  const jobId = String(job.job_id || "");
  if (importantLeadVerifyJobPollId !== jobId) {
    void pollImportantLeadVerifyJob(jobId);
  }
  return true;
}

async function hydrateImportantLeadVerifyJobOnLoad() {
  const savedJobId = readSavedJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY);
  if (savedJobId) {
    try {
      const data = await fetchJson(`/api/leads/verify-important/job/${encodeURIComponent(savedJobId)}`);
      if (resumeImportantLeadVerifyJob(data.job || null)) return;
    } catch (err) {
      clearSavedJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY, savedJobId);
    }
  }
  try {
    const data = await fetchJson("/api/leads/verify-important/active");
    resumeImportantLeadVerifyJob(data.job || null);
  } catch (err) {
    // no-op
  }
}

function stopImportantLeadDispatchJobPolling() {
  if (importantLeadDispatchJobTimer) {
    clearTimeout(importantLeadDispatchJobTimer);
    importantLeadDispatchJobTimer = null;
  }
  importantLeadDispatchJobPollId = "";
}

function renderImportantLeadDispatchJob(job) {
  if (!job || !job.job_id) return;
  lastImportantDispatchJob = job;
  const status = importantLeadCheckJobStatus(job);
  const active = isActiveImportantLeadCheckJob(job);
  if (active) {
    saveJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY, job.job_id);
  } else if (isTerminalImportantLeadCheckJob(job)) {
    clearSavedJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY, job.job_id);
  }
  const stage = job.phase || job.stage || status || "queued";
  const totalRows = Number(job.total_rows || 0);
  const processedRows = Number(job.processed_rows || 0);
  const assignedRows = Number(job.assigned_rows || 0);
  const skippedRows = Number(job.skipped_rows || 0);
  const remainingRows = Number(job.remaining_rows || Math.max(0, totalRows - processedRows));
  const progressPercent = Number.isFinite(Number(job.progress_percent))
    ? Math.min(100, Math.max(0, Number(job.progress_percent)))
    : (totalRows > 0 ? Math.min(100, Math.max(0, (processedRows / totalRows) * 100)) : 0);
  const etaSeconds = Number(job.eta_seconds);
  const etaText = Number.isFinite(etaSeconds) && etaSeconds > 0 ? humanizeDurationCompact(etaSeconds) : "n/a";
  const updatedText = job.updated_at_utc ? formatGeneratedAt(job.updated_at_utc) : "-";
  const mode = job.dispatch_source_mode || "triaged_keep";
  if (els.leadsImportantDispatchMeta) {
    setNodeText(els.leadsImportantDispatchMeta, `Dispatch job ${status}: ${job.message || job.error || stage}.`);
  }
  if (els.leadsImportantDispatchPreviewBtn) {
    setButtonBusy(els.leadsImportantDispatchPreviewBtn, active, "Preview Dispatch");
    setNodeText(els.leadsImportantDispatchPreviewBtn, "Preview Dispatch");
  }
  if (els.leadsImportantDispatchConfirmBtn) {
    setButtonBusy(els.leadsImportantDispatchConfirmBtn, active, active ? "Dispatching..." : "Confirm Dispatch");
    els.leadsImportantDispatchConfirmBtn.disabled = true;
  }
  if (els.leadsImportantDispatchResults && active) {
    setNodeHtml(
      els.leadsImportantDispatchResults,
      `
        <article class="leads-result-card">
          <h3>Dispatch Job</h3>
          ${accessibleProgressBar(progressPercent, etaText, "Dispatch progress")}
          <div class="leads-kpis">
            <div class="leads-kpi"><div class="label">Phase</div><div class="value">${escapeHtml(stage)}</div></div>
            <div class="leads-kpi"><div class="label">Rows</div><div class="value">${totalRows}</div></div>
            <div class="leads-kpi"><div class="label">Assigned</div><div class="value">${assignedRows}</div></div>
            <div class="leads-kpi"><div class="label">Skipped</div><div class="value">${skippedRows}</div></div>
            <div class="leads-kpi"><div class="label">Remaining</div><div class="value">${remainingRows}</div></div>
            <div class="leads-kpi"><div class="label">ETA</div><div class="value">${escapeHtml(etaText)}</div></div>
            <div class="leads-kpi"><div class="label">Updated</div><div class="value">${escapeHtml(updatedText)}</div></div>
          </div>
          <div class="pill-row">
            <span class="mini-pill">Job ${escapeHtml(job.job_id || "-")}</span>
            <span class="mini-pill">Mode ${escapeHtml(mode)}</span>
            <span class="mini-pill">Cap ${escapeHtml(job.dispatch_cap || "all")}</span>
          </div>
        </article>
      `,
    );
  }
  renderLeadsWorkflowStatusBanner(lastLeadsStatus);
}

function renderDispatchConfirmGuard(dispatchSource = {}, preview = null) {
  const sourceBlocked = Boolean(dispatchSource.dispatch_block_reason);
  const activeDispatch = isActiveImportantLeadCheckJob(lastImportantDispatchJob);
  const liveSenderProfiles = activeSenderProfiles();
  const sendersActive = liveSenderProfiles.length > 0;
  const activeCheck = isActiveImportantLeadCheckJob(currentImportantCheckJob());
  const dispatchBlockReason = dispatchActionBlockReason();
  const previewReady = dispatchPreviewMatchesCurrentSelection();
  const previewBlocked = !preview || !previewReady;
  if (els.leadsImportantDispatchPreviewBtn) {
    els.leadsImportantDispatchPreviewBtn.disabled = activeDispatch || sourceBlocked || sendersActive || activeCheck;
    els.leadsImportantDispatchPreviewBtn.title = dispatchBlockReason || "";
  }
  if (els.leadsImportantDispatchConfirmBtn) {
    els.leadsImportantDispatchConfirmBtn.disabled = activeDispatch || sourceBlocked || previewBlocked || sendersActive || activeCheck;
    els.leadsImportantDispatchConfirmBtn.title = dispatchBlockReason || (previewBlocked ? "Run Preview Dispatch for the current source and cap first." : "");
  }
}

async function pollImportantLeadDispatchJob(jobId) {
  if (!jobId) return;
  stopImportantLeadDispatchJobPolling();
  importantLeadDispatchJobPollId = String(jobId);
  try {
    const data = await fetchJson(`/api/leads/dispatch-important/job/${encodeURIComponent(jobId)}`);
    const job = data.job || {};
    renderImportantLeadDispatchJob(job);
    if (job.status === "completed") {
      stopImportantLeadDispatchJobPolling();
      clearSavedJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY, job.job_id || jobId);
      lastImportantDispatchPreview = null;
      lastImportantDispatch = job.dispatch || null;
      if (data.status) renderLeadsStatus(data.status || {});
      else renderImportantDispatch(lastImportantDispatch);
      showMessage(job.message || "Lead dispatch complete.", "success");
      return;
    }
    if (job.status === "failed" || job.status === "canceled" || job.status === "cancelled") {
      stopImportantLeadDispatchJobPolling();
      clearSavedJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY, job.job_id || jobId);
      showMessage(job.error || "Lead dispatch failed.", "error");
      return;
    }
    importantLeadDispatchJobTimer = setTimeout(() => pollImportantLeadDispatchJob(jobId), 1500);
  } catch (err) {
    if (String(err || "").includes("not found")) {
      clearSavedJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY, jobId);
      stopImportantLeadDispatchJobPolling();
      return;
    }
    showMessage(`Dispatch job poll failed: ${err}`, "error");
    importantLeadDispatchJobTimer = setTimeout(() => pollImportantLeadDispatchJob(jobId), 2500);
  }
}

function resumeImportantLeadDispatchJob(job) {
  if (!isActiveImportantLeadCheckJob(job)) {
    if (isTerminalImportantLeadCheckJob(job)) {
      clearSavedJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY, job?.job_id || "");
    }
    return false;
  }
  renderImportantLeadDispatchJob(job);
  const jobId = String(job.job_id || "");
  if (importantLeadDispatchJobPollId !== jobId) {
    void pollImportantLeadDispatchJob(jobId);
  }
  return true;
}

async function hydrateImportantLeadDispatchJobOnLoad() {
  const savedJobId = readSavedJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY);
  if (savedJobId) {
    try {
      const data = await fetchJson(`/api/leads/dispatch-important/job/${encodeURIComponent(savedJobId)}`);
      if (resumeImportantLeadDispatchJob(data.job || null)) return;
    } catch (err) {
      clearSavedJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY, savedJobId);
    }
  }
  try {
    const data = await fetchJson("/api/leads/dispatch-important/active");
    resumeImportantLeadDispatchJob(data.job || null);
  } catch (err) {
    // no-op
  }
}

function syncImportantLeadPathInputs(status) {
  const inputLabel = status?.important_input_label || "_important/leadschecker.csv";
  const outputLabel = status?.important_output_label || "_important/leads.csv";
  const rejectedLabel = status?.important_rejected_label || "_important/leads_rejected.csv";
  if (els.leadsImportantInputPath) els.leadsImportantInputPath.value = inputLabel;
  if (els.leadsImportantOutputPath) els.leadsImportantOutputPath.value = outputLabel;
  if (els.leadsImportantRejectedPath) els.leadsImportantRejectedPath.value = rejectedLabel;
}

function importantLeadVerifyPayload(mode = VERIFY_MODE_FAST_TRIAGE) {
  let normalizedMode = String(mode || VERIFY_MODE_FAST_TRIAGE).toUpperCase() === VERIFY_MODE_STRICT_PUBLIC_PROOF
    ? VERIFY_MODE_STRICT_PUBLIC_PROOF
    : VERIFY_MODE_FAST_TRIAGE;
  if (normalizedMode === VERIFY_MODE_FAST_TRIAGE && (els.leadsImportantIntakeMode?.value || "") === "manual_author_research") {
    normalizedMode = VERIFY_MODE_MANUAL_AUTHOR_RESEARCH;
  }
  const modeDefaults = normalizedMode === VERIFY_MODE_STRICT_PUBLIC_PROOF
    ? VERIFY_STRICT_DEFAULT_PATHS
    : VERIFY_FAST_DEFAULT_PATHS;
  return {
    mode: normalizedMode,
    input_path: els.leadsImportantVerifyInputPath?.value?.trim() || "",
    verified_path: normalizedMode === VERIFY_MODE_STRICT_PUBLIC_PROOF
      ? modeDefaults.verified_path
      : (els.leadsImportantVerifyOutputPath?.value?.trim() || modeDefaults.verified_path),
    rejected_path: normalizedMode === VERIFY_MODE_STRICT_PUBLIC_PROOF
      ? modeDefaults.rejected_path
      : (els.leadsImportantVerifyRejectedPath?.value?.trim() || modeDefaults.rejected_path),
    quarantine_path: normalizedMode === VERIFY_MODE_STRICT_PUBLIC_PROOF
      ? modeDefaults.quarantine_path
      : (els.leadsImportantVerifyQuarantinePath?.value?.trim() || modeDefaults.quarantine_path),
  };
}

function syncImportantVerifyPathInputs(status) {
  const inputLabel = status?.important_triage_input_label || status?.important_verify_input_label || "_important/leads.csv";
  const verifiedLabel = status?.important_triage_keep_label || VERIFY_FAST_DEFAULT_PATHS.verified_path;
  const rejectedLabel = status?.important_triage_rejected_label || VERIFY_FAST_DEFAULT_PATHS.rejected_path;
  const quarantineLabel = status?.important_triage_quarantine_label || VERIFY_FAST_DEFAULT_PATHS.quarantine_path;
  if (els.leadsImportantVerifyInputPath) els.leadsImportantVerifyInputPath.value = inputLabel;
  if (els.leadsImportantVerifyOutputPath) els.leadsImportantVerifyOutputPath.value = verifiedLabel;
  if (els.leadsImportantVerifyRejectedPath) els.leadsImportantVerifyRejectedPath.value = rejectedLabel;
  if (els.leadsImportantVerifyQuarantinePath) els.leadsImportantVerifyQuarantinePath.value = quarantineLabel;
}

function syncImportantDispatchSourceMode(status) {
  const mode = status?.dispatch_source_mode || lastImportantDispatchSource?.dispatch_source_mode || "triaged_keep";
  if (els.leadsImportantDispatchSourceMode) {
    els.leadsImportantDispatchSourceMode.value = mode === "strict_verified" ? "strict_verified" : "triaged_keep";
  }
  if (els.leadsImportantDispatchCap && !els.leadsImportantDispatchCap.value) {
    els.leadsImportantDispatchCap.value = "all";
  }
}

function dispatchSourceForSelectedMode() {
  const status = lastLeadsStatus || {};
  const selectedMode = els.leadsImportantDispatchSourceMode?.value || status.dispatch_source_mode || "triaged_keep";
  const options = status.dispatch_source_options || {};
  const mode = selectedMode === "strict_verified" ? "strict_verified" : "triaged_keep";
  return {
    mode,
    source: options[mode] || status.dispatch_source || {},
  };
}

function quarantineReviewFiltersPayload() {
  return {
    reason_code: String(els.leadsQuarantineReasonCode?.value || "").trim(),
    stage: String(els.leadsQuarantineStage?.value || "").trim(),
    status: String(els.leadsQuarantineStatus?.value || "QUARANTINE").trim() || "QUARANTINE",
    sort: String(els.leadsQuarantineSort?.value || "score_desc").trim() || "score_desc",
  };
}

function quarantineReviewQueryString() {
  const params = new URLSearchParams();
  const payload = quarantineReviewFiltersPayload();
  Object.entries(payload).forEach(([key, value]) => {
    if (value !== "") params.set(key, value);
  });
  const normalizedPageSize = QUARANTINE_PAGE_SIZE_OPTIONS.includes(Number(quarantinePageSize)) ? Number(quarantinePageSize) : 10;
  const normalizedPageIndex = Math.max(0, Number(quarantinePageIndex || 0));
  params.set("limit", String(normalizedPageSize));
  params.set("offset", String(normalizedPageIndex * normalizedPageSize));
  return params.toString();
}

function quarantineCountLabel(value) {
  return Number(value || 0).toLocaleString();
}

function visibleQuarantineLeads(review = lastQuarantineReview) {
  return Array.isArray(review?.leads) ? review.leads : [];
}

function visibleQuarantineLeadIds(review = lastQuarantineReview) {
  return visibleQuarantineLeads(review)
    .map((lead) => String(lead?.lead_id || "").trim())
    .filter(Boolean);
}

function quarantineFilteredCount(review = lastQuarantineReview) {
  return Number(review?.counts?.filtered || visibleQuarantineLeads(review).length || 0);
}

function quarantineRowsPerPage(review = lastQuarantineReview) {
  const value = Number(review?.filters?.limit || quarantinePageSize || 10);
  return QUARANTINE_PAGE_SIZE_OPTIONS.includes(value) ? value : 10;
}

function quarantineCurrentOffset(review = lastQuarantineReview) {
  return Math.max(0, Number(review?.filters?.offset || quarantinePageIndex * quarantineRowsPerPage(review) || 0));
}

function quarantineTotalPages(review = lastQuarantineReview) {
  const filtered = quarantineFilteredCount(review);
  const pageSize = quarantineRowsPerPage(review);
  return Math.max(1, Math.ceil(filtered / Math.max(1, pageSize)));
}

function quarantineCurrentPage(review = lastQuarantineReview) {
  const pageSize = quarantineRowsPerPage(review);
  return Math.min(quarantineTotalPages(review), Math.floor(quarantineCurrentOffset(review) / Math.max(1, pageSize)) + 1);
}

function quarantineVisibleRange(review = lastQuarantineReview) {
  const filtered = quarantineFilteredCount(review);
  if (!filtered) {
    return { start: 0, end: 0 };
  }
  const start = quarantineCurrentOffset(review) + 1;
  const end = Math.min(filtered, quarantineCurrentOffset(review) + visibleQuarantineLeads(review).length);
  return { start, end };
}

function isQuarantineLeadSelected(leadId) {
  const normalizedLeadId = String(leadId || "").trim();
  if (!normalizedLeadId) return false;
  if (allFilteredQuarantineSelected) {
    return !excludedQuarantineLeadIds.has(normalizedLeadId);
  }
  return selectedQuarantineLeadIds.has(normalizedLeadId);
}

function selectedQuarantineLeadCount(review = lastQuarantineReview) {
  if (allFilteredQuarantineSelected) {
    return Math.max(0, quarantineFilteredCount(review) - excludedQuarantineLeadIds.size);
  }
  return selectedQuarantineLeadIds.size;
}

function selectedQuarantineLeadIdsList(review = lastQuarantineReview) {
  if (allFilteredQuarantineSelected) {
    return visibleQuarantineLeadIds(review).filter((leadId) => !excludedQuarantineLeadIds.has(leadId));
  }
  return Array.from(selectedQuarantineLeadIds.values());
}

function clearQuarantineSelection() {
  allFilteredQuarantineSelected = false;
  selectedQuarantineLeadIds.clear();
  excludedQuarantineLeadIds.clear();
}

function quarantineHeaderCheckboxState(review = lastQuarantineReview) {
  const visibleIds = visibleQuarantineLeadIds(review);
  const visibleSelectedCount = visibleIds.filter((leadId) => isQuarantineLeadSelected(leadId)).length;
  return {
    visibleIds,
    visibleSelectedCount,
    visibleCount: visibleIds.length,
    checked: visibleIds.length > 0 && visibleSelectedCount === visibleIds.length,
    indeterminate: visibleSelectedCount > 0 && visibleSelectedCount < visibleIds.length,
  };
}

function focusedQuarantineLeadId(review = lastQuarantineReview) {
  const visibleIds = visibleQuarantineLeadIds(review);
  const currentFocusedLeadId = String(lastQuarantineReviewLead?.lead_id || "").trim();
  if (currentFocusedLeadId && visibleIds.includes(currentFocusedLeadId)) {
    return currentFocusedLeadId;
  }
  return visibleIds[0] || "";
}

function quarantineSelectionSummary(review = lastQuarantineReview) {
  const headerState = quarantineHeaderCheckboxState(review);
  const filteredCount = quarantineFilteredCount(review);
  const selectedCount = selectedQuarantineLeadCount(review);
  const unselectedFilteredCount = Math.max(0, filteredCount - selectedCount);
  return {
    ...headerState,
    filteredCount,
    selectedCount,
    unselectedFilteredCount,
    scopeLabel: allFilteredQuarantineSelected
      ? `Bulk actions apply to all ${quarantineCountLabel(selectedCount)} selected filtered leads.`
      : `Bulk actions apply to ${quarantineCountLabel(selectedCount)} explicitly selected lead${selectedCount === 1 ? "" : "s"}.`,
    pageStatus: headerState.visibleSelectedCount
      ? `${quarantineCountLabel(headerState.visibleSelectedCount)} selected on this page`
      : "No rows selected on this page",
    filteredStatus: `${quarantineCountLabel(filteredCount)} filtered result${filteredCount === 1 ? "" : "s"}`,
  };
}

function applyQuarantineHeaderCheckboxState(review = lastQuarantineReview) {
  const checkbox = els.leadsQuarantineResults?.querySelector?.("[data-quarantine-page-toggle]");
  if (!(checkbox instanceof HTMLInputElement)) return;
  const state = quarantineHeaderCheckboxState(review);
  checkbox.checked = state.checked;
  checkbox.indeterminate = state.indeterminate;
  checkbox.setAttribute("aria-checked", state.indeterminate ? "mixed" : state.checked ? "true" : "false");
}

function updateQuarantineSelectionForVisiblePage(nextChecked, review = lastQuarantineReview) {
  const visibleIds = visibleQuarantineLeadIds(review);
  if (!visibleIds.length) return;
  if (allFilteredQuarantineSelected) {
    visibleIds.forEach((leadId) => {
      if (nextChecked) excludedQuarantineLeadIds.delete(leadId);
      else excludedQuarantineLeadIds.add(leadId);
    });
  } else {
    visibleIds.forEach((leadId) => {
      if (nextChecked) selectedQuarantineLeadIds.add(leadId);
      else selectedQuarantineLeadIds.delete(leadId);
    });
  }
  renderQuarantineReview(lastQuarantineReview);
}

function selectAllFilteredQuarantineLeads() {
  allFilteredQuarantineSelected = true;
  selectedQuarantineLeadIds.clear();
  excludedQuarantineLeadIds.clear();
  renderQuarantineReview(lastQuarantineReview);
}

function setQuarantineRowsPerPage(value) {
  if (!quarantineInboxOpen) return;
  const next = Number(value);
  quarantinePageSize = QUARANTINE_PAGE_SIZE_OPTIONS.includes(next) ? next : 10;
  quarantinePageIndex = 0;
  void refreshQuarantineReview(true, false);
}

function moveQuarantinePage(direction) {
  if (!quarantineInboxOpen) return;
  const totalPages = quarantineTotalPages(lastQuarantineReview);
  quarantinePageIndex = Math.max(0, Math.min(totalPages - 1, quarantinePageIndex + direction));
  void refreshQuarantineReview(true, false);
}

function applyQuarantineFilterOptions(review) {
  const filters = review?.filters || {};
  const reasonOptions = Array.isArray(review?.reason_code_options) ? review.reason_code_options : [];
  const stageOptions = Array.isArray(review?.stage_options) ? review.stage_options : [];
  const statusOptions = Array.isArray(review?.status_options) ? review.status_options : [];
  if (els.leadsQuarantineReasonCode) {
    setNodeHtml(
      els.leadsQuarantineReasonCode,
      [`<option value="">All reason codes</option>`, ...reasonOptions.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)].join(""),
    );
    els.leadsQuarantineReasonCode.value = String(filters.reason_code || "");
  }
  if (els.leadsQuarantineStage) {
    setNodeHtml(
      els.leadsQuarantineStage,
      [`<option value="">All stages</option>`, ...stageOptions.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)].join(""),
    );
    els.leadsQuarantineStage.value = String(filters.stage || "");
  }
  if (els.leadsQuarantineStatus) {
    const normalized = Array.from(new Set(["QUARANTINE", ...statusOptions]));
    setNodeHtml(
      els.leadsQuarantineStatus,
      normalized.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join(""),
    );
    els.leadsQuarantineStatus.value = String(filters.status || "QUARANTINE") || "QUARANTINE";
  }
  if (els.leadsQuarantineSort) {
    els.leadsQuarantineSort.value = String(filters.sort || "score_desc");
  }
}

function renderQuarantineReview(review) {
  lastQuarantineReview = review || lastQuarantineReview;
  const activeReview = lastQuarantineReview || {};
  const leads = Array.isArray(activeReview.leads) ? activeReview.leads : [];
  const counts = activeReview.counts || {};
  const selection = quarantineSelectionSummary(activeReview);
  const pageSize = quarantineRowsPerPage(activeReview);
  const currentPage = quarantineCurrentPage(activeReview);
  const totalPages = quarantineTotalPages(activeReview);
  const range = quarantineVisibleRange(activeReview);
  if (els.leadsQuarantineMeta) {
    setNodeText(
      els.leadsQuarantineMeta,
      `Open quarantine ${quarantineCountLabel(counts.total_quarantined || 0)}. Showing ${range.start ? `${quarantineCountLabel(range.start)}-${quarantineCountLabel(range.end)}` : "0"} of ${quarantineCountLabel(counts.filtered || leads.length || 0)} filtered leads. ${selection.scopeLabel}`,
    );
  }
  applyQuarantineFilterOptions(activeReview);
  if (!leads.length) {
    setNodeHtml(
      els.leadsQuarantineResults,
      `
        <section class="operator-empty-state operator-empty-state-inbox">
          <strong>Inbox is clear.</strong>
          <span>No quarantined leads matched the current filters.</span>
        </section>
      `,
    );
    return;
  }
  const reasonRows = Object.entries(activeReview.reason_code_counts || {}).sort((left, right) => Number(right[1] || 0) - Number(left[1] || 0)).slice(0, 8);
  const recentActions = Array.isArray(activeReview.recent_actions) ? activeReview.recent_actions : [];
  const detail = lastQuarantineReviewLead || null;
  const focusedLeadLabel = detail?.email || leads[0]?.email || "-";
  const selectionSentence = `${quarantineCountLabel(selection.selectedCount)} selected · ${range.start ? `${quarantineCountLabel(range.start)}-${quarantineCountLabel(range.end)}` : "0"} of ${quarantineCountLabel(selection.filteredCount)} shown · Page ${quarantineCountLabel(currentPage)} of ${quarantineCountLabel(totalPages)}`;
  const dominantReasons = reasonRows.length
    ? reasonRows.slice(0, 4).map(([reason, count]) => `${reason} ${Number(count || 0)}`)
    : ["No reason codes"];
  const detailHistoryRows = Array.isArray(detail?.lead_events)
    ? detail.lead_events.slice(-6).reverse().map((event) => ({
      Event: event.event_type || "-",
      "Reason / Note": event.reason_code || event.note || "-",
      When: formatGeneratedAt(event.created_at || ""),
    }))
    : [];
  const recentReviewRows = recentActions.slice(0, 8).map((event) => ({
    Action: event.event_type || "-",
    Lead: event.email || event.full_name || event.lead_id || "-",
    When: formatGeneratedAt(event.created_at || ""),
  }));
  const detailInspectionBlocks = detail?.lead_id
    ? `
      ${renderOperatorTableBlock("Recent Lead History", "Most recent ledger activity for the selected lead.", ["Event", "Reason / Note", "When"], detailHistoryRows, "No lead history yet.")}
      ${renderOperatorTableBlock("Recent Review Actions", "Latest actions for the inspected quarantine context.", ["Action", "Lead", "When"], recentReviewRows, "No recent review actions yet.")}
    `
    : "";
  setNodeHtml(
    els.leadsQuarantineResults,
    `
      <div class="quarantine-shell inbox-shell">
        <section class="quarantine-inbox-panel inbox-panel">
          <div class="quarantine-inbox-sticky inbox-sticky">
            <div class="inbox-toolbar">
              <div class="inbox-toolbar-copy">
                <span class="inbox-title">Quarantine Inbox</span>
                <strong>${escapeHtml(selectionSentence)}</strong>
                <span class="muted">${escapeHtml(selection.scopeLabel)}</span>
              </div>
              <div class="inbox-toolbar-actions">
                <button class="btn btn-secondary btn-sm" type="button" data-quarantine-check-page>Check page</button>
                <button class="btn btn-secondary btn-sm" type="button" data-quarantine-uncheck-page>Uncheck page</button>
                <button class="btn btn-secondary btn-sm" type="button" data-quarantine-select-all-filtered>Select all filtered</button>
                <button class="btn btn-secondary btn-sm" type="button" data-quarantine-clear-selection>Clear</button>
              </div>
            </div>
            <div class="inbox-strip">
              ${renderOperatorPillStrip(dominantReasons, "inbox-pill-strip")}
              <div class="quarantine-pagination-actions inbox-pagination-actions">
                <label class="quarantine-page-size">
                  <span>Rows</span>
                  <select data-quarantine-page-size>
                    ${QUARANTINE_PAGE_SIZE_OPTIONS.map((value) => `<option value="${value}"${value === pageSize ? " selected" : ""}>${value}</option>`).join("")}
                  </select>
                </label>
                <button class="btn btn-secondary btn-sm" type="button" data-quarantine-prev-page ${currentPage <= 1 ? "disabled" : ""}>Prev</button>
                <button class="btn btn-secondary btn-sm" type="button" data-quarantine-next-page ${currentPage >= totalPages ? "disabled" : ""}>Next</button>
              </div>
            </div>
          </div>
          <div class="quarantine-list-shell inbox-list-shell">
            <div class="quarantine-list-head inbox-list-head">
              <div class="quarantine-list-col-select">
                <label class="quarantine-header-checkbox">
                  <input
                    type="checkbox"
                    data-quarantine-page-toggle
                    aria-label="Select all visible quarantine leads"
                    aria-checked="false"
                  />
                  <span>Select</span>
                </label>
              </div>
              <div class="quarantine-list-col-lead">Lead</div>
              <div class="quarantine-list-col-review">Review</div>
              <div class="quarantine-list-col-signals">Signals</div>
              <div class="quarantine-list-col-open">Open</div>
            </div>
            <div class="quarantine-list-scroll">
              ${leads.map((lead) => {
                const leadId = String(lead.lead_id || "");
                const isSelected = isQuarantineLeadSelected(leadId);
                const reasons = Array.isArray(lead.reason_codes) ? lead.reason_codes : [];
                const dominantReason = String(reasons[0] || "No reason code");
                return `
                  <div class="quarantine-list-row inbox-list-row ${isSelected ? "is-selected" : ""}" data-quarantine-row="${escapeHtml(leadId)}">
                    <div class="quarantine-row-select">
                      <input type="checkbox" data-quarantine-select="${escapeHtml(leadId)}" ${isSelected ? "checked" : ""} />
                    </div>
                    <div class="quarantine-row-identity">
                      <strong>${escapeHtml(lead.full_name || lead.first_name || lead.email || "-")}</strong>
                      <span class="quarantine-lead-secondary">${escapeHtml(lead.email || "-")}</span>
                    </div>
                    <div class="quarantine-row-review">
                      <div class="quarantine-pill-row quarantine-pill-row-compact">
                        <span class="quarantine-pill">${escapeHtml(lead.current_status || "-")}</span>
                        <span class="quarantine-pill quarantine-pill-muted">${escapeHtml(lead.current_stage || "-")}</span>
                        <span class="quarantine-pill quarantine-pill-warn">Score ${Number(lead.score || 0).toFixed(1)}</span>
                      </div>
                      <span class="quarantine-lead-secondary">${escapeHtml(dominantReason)}</span>
                    </div>
                    <div class="quarantine-row-signals">
                      ${lead.suppressed
                        ? `<span class="quarantine-pill quarantine-pill-alert">${escapeHtml(lead.suppression_reason || "suppressed")}</span>`
                        : `<span class="quarantine-pill quarantine-pill-muted">Not suppressed</span>`}
                      <span class="quarantine-lead-secondary">Dispatch ${Number(lead.dispatch_summary?.dispatch_count || 0)} · ${escapeHtml(lead.dispatch_summary?.last_outcome || "none")}</span>
                    </div>
                    <div class="quarantine-row-open">
                      <button class="btn btn-secondary btn-sm" type="button" data-quarantine-inspect="${escapeHtml(leadId)}">Inspect</button>
                    </div>
                  </div>
                `;
              }).join("")}
            </div>
          </div>
        </section>

        <aside class="quarantine-inspector inbox-inspector">
          <div class="inspector-head">
            <div>
              <h3>Lead Inspector</h3>
              <p class="quarantine-selection-note">${detail?.lead_id ? `Focused lead: ${escapeHtml(focusedLeadLabel)}` : "Select a lead to inspect history, provenance, and dispatch context."}</p>
            </div>
          </div>
          ${
            detail?.lead_id
              ? `
                ${renderOperatorMetricStrip([
                  { label: "Stage", value: detail.current_stage || "-" },
                  { label: "Status", value: detail.current_status || "-" },
                  { label: "Score", value: Number(detail.score || 0).toFixed(1), tone: "warn" },
                  { label: "Suppression", value: detail.suppressed ? "Suppressed" : "Clear", tone: detail.suppressed ? "warn" : "good" },
                ], "inspector-metrics")}
                ${renderOperatorPillStrip(Array.isArray(detail.reason_codes) && detail.reason_codes.length ? detail.reason_codes : ["No reason codes"], "inspector-reason-strip")}
                <div class="inspector-facts">
                  <section class="inspector-fact">
                    <span class="inspector-fact-label">Source</span>
                    <strong>${escapeHtml(detail.source_provenance?.source_file || "-")}</strong>
                  </section>
                  <section class="inspector-fact">
                    <span class="inspector-fact-label">Row hash</span>
                    <strong>${escapeHtml(detail.source_provenance?.source_row_hash || "-")}</strong>
                  </section>
                  <section class="inspector-fact">
                    <span class="inspector-fact-label">Seen</span>
                    <strong>${escapeHtml(formatGeneratedAt(detail.source_provenance?.last_seen_at || ""))}</strong>
                  </section>
                  <section class="inspector-fact">
                    <span class="inspector-fact-label">Dispatch</span>
                    <strong>${Number(detail.dispatch_summary?.dispatch_count || 0)} · ${escapeHtml(detail.dispatch_summary?.last_outcome || "-")}</strong>
                  </section>
                </div>
                <section class="operator-note-block">
                  <span class="inspector-fact-label">Operator Note</span>
                  <p class="muted">${escapeHtml(detail.operator_note || "No operator note yet.")}</p>
                </section>
                ${detailInspectionBlocks}
              `
              : `
                <section class="operator-empty-state operator-empty-state-inline">
                  <strong>Inspector is waiting.</strong>
                  <span>Select a quarantined lead to inspect history, provenance, suppression state, and dispatch context.</span>
                </section>
              `
          }
        </aside>
      </div>
    `,
  );
  applyQuarantineHeaderCheckboxState(activeReview);
}

async function loadQuarantineReviewLeadDetail(leadId) {
  if (!leadId) return;
  try {
    const data = await fetchJson(`/api/leads/quarantine-review/${encodeURIComponent(leadId)}`);
    lastQuarantineReviewLead = data.lead || null;
    renderQuarantineReview(lastQuarantineReview);
  } catch (err) {
    showMessage(`Quarantine detail failed: ${err}`, "error");
  }
}

async function refreshQuarantineReview(preserveSelection = true, resetPage = false) {
  if (!quarantineInboxOpen) return;
  try {
    if (resetPage) {
      quarantinePageIndex = 0;
    }
    let data = await fetchJson(`/api/leads/quarantine-review?${quarantineReviewQueryString()}`);
    let review = data.review || {};
    if (!Array.isArray(review.leads) || (!review.leads.length && quarantineFilteredCount(review) > 0 && quarantineCurrentOffset(review) > 0)) {
      quarantinePageSize = quarantineRowsPerPage(review);
      quarantinePageIndex = Math.max(0, quarantineTotalPages(review) - 1);
      data = await fetchJson(`/api/leads/quarantine-review?${quarantineReviewQueryString()}`);
      review = data.review || {};
    }
    quarantinePageSize = quarantineRowsPerPage(review);
    quarantinePageIndex = Math.max(0, quarantineCurrentPage(review) - 1);
    if (!preserveSelection) {
      clearQuarantineSelection();
    }
    lastQuarantineReview = review;
    const currentFocusedLeadId = String(lastQuarantineReviewLead?.lead_id || "").trim();
    const visibleIds = visibleQuarantineLeadIds(review);
    if (!currentFocusedLeadId || !visibleIds.includes(currentFocusedLeadId)) {
      lastQuarantineReviewLead = null;
    }
    renderQuarantineReview(lastQuarantineReview);
  } catch (err) {
    showMessage(`Quarantine review load failed: ${err}`, "error");
  }
}

async function runQuarantineReviewAction(action) {
  const selection = quarantineSelectionSummary(lastQuarantineReview);
  if (!selection.selectedCount) {
    showMessage("Select at least one quarantined lead first.", "error");
    return;
  }
  const usingFilteredSelection = allFilteredQuarantineSelected;
  const payload = {
    action,
    operator_note: String(els.leadsQuarantineOperatorNote?.value || "").trim(),
    lead_ids: usingFilteredSelection ? [] : selectedQuarantineLeadIdsList(lastQuarantineReview),
    excluded_lead_ids: usingFilteredSelection ? Array.from(excludedQuarantineLeadIds.values()) : [],
    select_all_filtered: usingFilteredSelection,
    ...quarantineReviewFiltersPayload(),
  };
  try {
    const data = await fetchJson("/api/leads/quarantine-review/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    lastQuarantineReview = data.review || null;
    if (action !== "update_operator_note" && els.leadsQuarantineOperatorNote) {
      els.leadsQuarantineOperatorNote.value = "";
    }
    clearQuarantineSelection();
    showMessage(
      data.message || (usingFilteredSelection ? "Quarantine review action applied to filtered selection." : "Quarantine review action applied to selected rows."),
      "success",
    );
    await refreshQuarantineReview(false);
  } catch (err) {
    showMessage(`Quarantine review action failed: ${err}`, "error");
  }
}

async function fetchJson(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    const message = data.message || data.detail || `Request failed (${response.status}).`;
    if (response.status === 401 || response.status === 403) {
      setAuthState({
        authEnabled: authState.authEnabled,
        authenticated: false,
        username: "",
        message,
      });
    }
    throw new Error(message);
  }
  return data;
}

function renderLeadsMappingOptions(upload) {
  const fieldnames = Array.isArray(upload?.fieldnames) ? upload.fieldnames : [];
  const mapping = upload?.mapping || {};
  const selects = [
    { node: els.leadsEmailColumn, selected: mapping.email || "", allowEmpty: false },
    { node: els.leadsFirstNameColumn, selected: mapping.first_name || "", allowEmpty: true },
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

function renderOperatorMetricStrip(items = [], className = "") {
  const metrics = Array.isArray(items) ? items.filter((item) => item && item.label) : [];
  if (!metrics.length) return "";
  return `
    <div class="operator-metric-strip${className ? ` ${className}` : ""}">
      ${metrics.map((item) => `
        <div class="operator-metric${item.tone ? ` operator-metric-${item.tone}` : ""}">
          <span class="operator-metric-label">${escapeHtml(item.label)}</span>
          <span class="operator-metric-value">${escapeHtml(item.value ?? "-")}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function renderOperatorPillStrip(items = [], className = "") {
  const pills = Array.isArray(items) ? items.filter(Boolean) : [];
  if (!pills.length) return "";
  return `
    <div class="operator-pill-strip${className ? ` ${className}` : ""}">
      ${pills.map((item) => `<span class="operator-pill">${escapeHtml(item)}</span>`).join("")}
    </div>
  `;
}

function renderOperatorTable(headers = [], rows = [], emptyText = "No rows available.", className = "") {
  if (!Array.isArray(headers) || !headers.length || !Array.isArray(rows) || !rows.length) {
    return `<div class="operator-empty">${escapeHtml(emptyText)}</div>`;
  }
  return `
    <div class="table-shell operator-table-shell${className ? ` ${className}` : ""}">
      <table>
        <thead>
          <tr>${headers.map((field) => `<th>${escapeHtml(field)}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>${headers.map((field) => `<td>${escapeHtml(row?.[field] ?? "")}</td>`).join("")}</tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderOperatorTableBlock(title, caption, headers, rows, emptyText = "No rows available.", className = "") {
  const collapsibleTitles = new Set([
    "Clean Output Preview",
    "Keep Queue",
    "Reject Queue",
    "Quarantine Queue",
    "Channel Decisions",
    "Live Queue Comparison",
    "Source Preview",
    "Assigned Preview",
    "Source Snapshot",
    "Already Contacted Evidence",
  ]);
  const isCollapsible = collapsibleTitles.has(String(title || ""));
  if (isCollapsible) {
    return `
      <details class="operator-table-block operator-table-disclosure${className ? ` ${className}` : ""}">
        <summary class="operator-table-head">
          <div>
            <h3>${escapeHtml(title)}</h3>
            ${caption ? `<p class="muted">${escapeHtml(caption)}</p>` : ""}
          </div>
          <span class="mini-pill">Open</span>
        </summary>
        ${renderOperatorTable(headers, rows, emptyText)}
      </details>
    `;
  }
  return `
    <section class="operator-table-block${className ? ` ${className}` : ""}">
      <div class="operator-table-head">
        <div>
          <h3>${escapeHtml(title)}</h3>
          ${caption ? `<p class="muted">${escapeHtml(caption)}</p>` : ""}
        </div>
      </div>
      ${renderOperatorTable(headers, rows, emptyText)}
    </section>
  `;
}

function compactPreviewTable(rows = [], preferredHeaders = [], maxRows = 5, maxColumns = 4) {
  const sourceRows = Array.isArray(rows) ? rows : [];
  const allHeaders = sourceRows.length ? Object.keys(sourceRows[0] || {}) : [];
  const headerByLower = new Map(allHeaders.map((header) => [String(header).toLowerCase(), header]));
  const picked = [];
  preferredHeaders.forEach((candidate) => {
    const header = headerByLower.get(String(candidate || "").toLowerCase());
    if (header && !picked.includes(header)) picked.push(header);
  });
  allHeaders.forEach((header) => {
    if (picked.length < maxColumns && !picked.includes(header)) picked.push(header);
  });
  return {
    headers: picked.slice(0, maxColumns),
    rows: sourceRows.slice(0, maxRows),
  };
}

function renderImportantLeadCheck(result) {
  if (els.leadsImportantCheckMeta) {
    if (result?.generated_at_utc) {
      setNodeText(
        els.leadsImportantCheckMeta,
        `Last check completed. Cleaned ${Number(result.cleaned_rows || 0)} row(s), rejected ${Number((result.input_rows || 0) - (result.cleaned_rows || 0))} row(s).`,
      );
    } else {
      setNodeText(
        els.leadsImportantCheckMeta,
        "Ready. Put email-first leads in _important/leadschecker.csv, then click Check Leads. Keep FullName upstream when you have it.",
      );
    }
  }

  if (!result?.generated_at_utc) {
    setNodeHtml(els.leadsImportantCheckResults, "");
    return;
  }

  const fieldnames = Array.isArray(result.output_fieldnames) ? result.output_fieldnames : [];
  const rows = Array.isArray(result.output_preview_rows) ? result.output_preview_rows : [];
  const reasonRows = Object.entries(result.reason_counts || {}).map(([reason, count]) => ({ Reason: reason, Count: Number(count || 0) }));
  const intakeModeLabel = result.intake_mode === VERIFY_MODE_MANUAL_AUTHOR_RESEARCH ? "Manual Author Research" : (result.intake_mode_label || "Standard");
  setNodeHtml(
    els.leadsImportantCheckResults,
    `
      <div class="operator-result-shell operator-check-shell">
        ${renderOperatorMetricStrip([
          { label: "Intake mode", value: intakeModeLabel },
          { label: "Input", value: Number(result.input_rows || 0) },
          { label: "Cleaned", value: Number(result.cleaned_rows || 0), tone: "good" },
          { label: "Rejected", value: Math.max(0, Number(result.input_rows || 0) - Number(result.cleaned_rows || 0)), tone: "warn" },
          { label: "Review / Quarantine", value: Number(result.quarantine_count || result.review_count || 0), tone: Number(result.quarantine_count || result.review_count || 0) ? "warn" : "" },
          { label: "Safe fixes", value: Number(result.safe_fixes_applied || 0) },
        ])}
        ${renderOperatorMetricStrip([
          { label: "Duplicates", value: Number(result.duplicates_removed || 0) },
          { label: "Invalid", value: Number(result.invalid_removed || 0), tone: "warn" },
          { label: "Suppressed", value: Number(result.suppressed_removed || 0), tone: "warn" },
          { label: "Suspicious", value: Number(result.suspicious_flagged || 0), tone: "warn" },
        ], "operator-secondary-metrics")}
        <div class="operator-result-grid operator-result-grid-wide">
          ${reasonRows.length
            ? renderOperatorTableBlock("Removal Ledger", "What changed during hygiene.", ["Reason", "Count"], reasonRows, "No rows were removed.")
            : `<section class="operator-table-block"><div class="operator-table-head"><div><h3>Removal Ledger</h3><p class="muted">No removal reasons were recorded for this run.</p></div></div></section>`}
          ${renderOperatorTableBlock("Clean Output Preview", "The working rows that move into Verify.", fieldnames, rows, "No checked rows were written.")}
        </div>
        <details class="dispatch-drawer advanced-details">
          <summary>Advanced file details</summary>
          <div class="dispatch-disclosure-body">
            ${renderOperatorPillStrip([
              `Input ${result.input_label || "-"}`,
              `Output ${result.output_label || "-"}`,
              `Rejected ${result.rejected_label || "-"}`,
            ])}
          </div>
        </details>
      </div>
    `,
  );
}

function renderImportantLeadVerify(result) {
  const mode = String(result?.mode || VERIFY_MODE_FAST_TRIAGE).toUpperCase();
  const modeLabel = mode === VERIFY_MODE_STRICT_PUBLIC_PROOF ? "Strict Public Proof" : mode === VERIFY_MODE_MANUAL_AUTHOR_RESEARCH ? "Manual Author Research" : "Fast Triage";
  const isManualAuthorResearch = mode === VERIFY_MODE_MANUAL_AUTHOR_RESEARCH;
  if (els.leadsImportantVerifyMeta) {
    if (result?.generated_at_utc) {
      setNodeText(
        els.leadsImportantVerifyMeta,
        `${modeLabel}: KEEP ${Number(result.keep_count || 0)}, REJECT ${Number(result.reject_count || 0)}, QUARANTINE ${Number(result.quarantine_count || 0)}.`,
      );
    } else {
      setNodeText(
        els.leadsImportantVerifyMeta,
        "Ready. Fast Triage uses local checks only and is the default. Strict Public Proof is slower and optional.",
      );
    }
  }

  if (!result?.generated_at_utc) {
    setNodeHtml(els.leadsImportantVerifyResults, "");
    return;
  }

  const keepRows = Array.isArray(result.keep_preview_rows) ? result.keep_preview_rows : [];
  const rejectRows = Array.isArray(result.reject_preview_rows) ? result.reject_preview_rows : [];
  const quarantineRows = Array.isArray(result.quarantine_preview_rows) ? result.quarantine_preview_rows : [];
  const keepPreview = compactPreviewTable(keepRows, ["Email", "FirstName", "BookTitle", "Title"]);
  const rejectPreview = compactPreviewTable(rejectRows, ["Email", "FirstName", "Reason", "ReasonCode", "Score"]);
  const quarantinePreview = compactPreviewTable(quarantineRows, ["Email", "FirstName", "Reason", "ReasonCode", "Score"]);
  const reasonRows = Object.entries(result.reason_counts || {}).map(([reason, count]) => ({ Reason: reason, Count: Number(count || 0) }));
  setNodeHtml(
    els.leadsImportantVerifyResults,
    `
      <div class="operator-result-shell operator-verify-shell">
        ${renderOperatorMetricStrip([
          { label: "Mode", value: modeLabel },
          { label: "Input", value: Number(result.total_input_rows || 0) },
          { label: "Keep", value: Number(result.keep_count || 0), tone: "good" },
          { label: "Reject", value: Number(result.reject_count || 0), tone: "warn" },
          { label: "Review / Quarantine", value: Number(result.quarantine_count || 0), tone: "warn" },
        ])}
        ${isManualAuthorResearch
          ? `
            <section class="operator-empty-state operator-empty-state-inline">
              <strong>Manual Author Research mode</strong>
              <span>Manual Author Research keeps hard safety blockers strict and sends soft-quality issues to Review/Quarantine.</span>
            </section>
            <section class="operator-empty-state operator-empty-state-inline">
              <strong>Review/Quarantine rows are not dispatched automatically.</strong>
              <span>They must be manually promoted or selected before dispatch.</span>
            </section>
          `
          : ""}
        <div class="operator-result-grid">
          ${reasonRows.length
            ? renderOperatorTableBlock("Reason Ledger", "Local triage evidence for the current pass.", ["Reason", "Count"], reasonRows, "No verification reasons were recorded.")
            : ""}
          ${isManualAuthorResearch
            ? renderOperatorTableBlock(
              "Soft Warnings",
              "Manual Author Research warnings routed to Review/Quarantine.",
              ["Reason", "Count"],
              Object.entries(result.soft_warning_counts || {}).map(([reason, count]) => ({ Reason: reason, Count: Number(count || 0) })),
              "No soft warnings were recorded.",
            )
            : ""}
          ${isManualAuthorResearch
            ? renderOperatorTableBlock(
              "Hard Reject Reasons",
              "Hard safety blockers still rejected.",
              ["Reason", "Count"],
              Object.entries(result.hard_reject_counts || {}).map(([reason, count]) => ({ Reason: reason, Count: Number(count || 0) })),
              "No hard rejects were recorded.",
            )
            : ""}
          ${renderOperatorTableBlock("Keep Queue", `${modeLabel} rows ready to move forward. Showing up to 5 rows.`, keepPreview.headers, keepPreview.rows, "No rows moved to keep.")}
          ${renderOperatorTableBlock("Reject Queue", "Rows that should not proceed. Showing up to 5 rows.", rejectPreview.headers, rejectPreview.rows, "No rows were rejected.")}
          ${renderOperatorTableBlock("Quarantine Queue", "Rows that require operator review. Showing up to 5 rows.", quarantinePreview.headers, quarantinePreview.rows, "No rows were quarantined.")}
        </div>
        <details class="dispatch-drawer advanced-details">
          <summary>Advanced file details</summary>
          <div class="dispatch-disclosure-body">
            ${renderOperatorPillStrip([
              `Intake mode: ${modeLabel}`,
              `Input ${result.input_label || "-"}`,
              `Keep ${result.verified_label || "-"}`,
              `Reject ${result.rejected_label || "-"}`,
              `Quarantine ${result.quarantine_label || "-"}`,
            ])}
          </div>
        </details>
      </div>
    `,
  );
}

function renderImportantDispatch(result) {
  const selectedDispatchSource = dispatchSourceForSelectedMode();
  const dispatchSource = selectedDispatchSource.source || {};
  const dispatchPreview = dispatchPreviewMatchesCurrentSelection() ? lastImportantDispatchPreview : null;
  const liveSenderProfiles = activeSenderProfiles();
  const sendersActive = liveSenderProfiles.length > 0;
  const activeCheckRunning = isActiveImportantLeadCheckJob(currentImportantCheckJob());
  const dispatchBlockReason = dispatchActionBlockReason();
  const liveQueues = Array.isArray(lastLeadsStatus?.sendgrid_queues) ? lastLeadsStatus.sendgrid_queues : [];
  const liveQueueMap = new Map(liveQueues.map((item) => [String(item.name || ""), Number(item.count || 0)]));
  const liveJcCount = Number(lastLeadsStatus?.jc_queue?.count || 0);
  const liveSg1 = Number(liveQueueMap.get("SG1") || 0);
  const liveSg2 = Number(liveQueueMap.get("SG2") || 0);
  const liveSg3 = Number(liveQueueMap.get("SG3") || 0);
  const liveSg4 = Number(liveQueueMap.get("SG4") || 0);
  const liveSg5 = Number(liveQueueMap.get("SG5") || 0);
  const liveSendgridTotal = liveSg1 + liveSg2 + liveSg3 + liveSg4 + liveSg5;
  const lastDispatchGeneratedAt = result?.generated_at_utc ? formatGeneratedAt(result.generated_at_utc) : "-";
  const assignedSendgridTotal = Number(result?.assigned_sg1 || 0)
    + Number(result?.assigned_sg2 || 0)
    + Number(result?.assigned_sg3 || 0)
    + Number(result?.assigned_sg4 || 0)
    + Number(result?.assigned_sg5 || 0);
  const confirmedSg1 = Number(result?.sg1_added || result?.assigned_sg1 || 0);
  const confirmedSg2 = Number(result?.sg2_added || result?.assigned_sg2 || 0);
  const confirmedSg3 = Number(result?.sg3_added || result?.assigned_sg3 || 0);
  const confirmedSg4 = Number(result?.sg4_added || result?.assigned_sg4 || 0);
  const confirmedSg5 = Number(result?.sg5_added || result?.assigned_sg5 || 0);
  const confirmedSendgridTotal = Number(result?.sendgrid_added || result?.added_sendgrid || assignedSendgridTotal || 0);
  const confirmedPrivateJcTotal = Number(result?.private_jc_added || result?.added_astra || 0);
  const sourcePreviewRows = Array.isArray(dispatchSource.dispatch_source_preview_rows) ? dispatchSource.dispatch_source_preview_rows : [];
  const sourceHeaders = Array.isArray(dispatchSource.dispatch_source_headers) ? dispatchSource.dispatch_source_headers : [];
  const sourceName = dispatchSource.dispatch_source_name || result?.dispatch_source_name || dispatchSource.dispatch_source_mode || result?.dispatch_source_mode || "triaged_keep";
  const sourcePath = dispatchSource.dispatch_source_path || result?.dispatch_source_path || "-";
  const preflightAllowed = !sendersActive && !activeCheckRunning;
  const preflightLabel = preflightAllowed ? "Allowed" : "Blocked";
  const activeSenderSummary = liveSenderProfiles.length
    ? liveSenderProfiles.map((profile) => `${formatProfileName(profile.name)} (${profile.runtime_state})`).join(", ")
    : "None";
  const selectedCap = els.leadsImportantDispatchCap?.value || (dispatchPreview?.dispatch_cap ?? "all");
  const previewPrivateJc = Number(dispatchPreview?.rows_to_add_private_jc || 0);
  const previewSg1 = Number(dispatchPreview?.rows_to_add_sendgrid_1 || 0);
  const previewSg2 = Number(dispatchPreview?.rows_to_add_sendgrid_2 || 0);
  const previewSg3 = Number(dispatchPreview?.rows_to_add_sendgrid_3 || 0);
  const previewSg4 = Number(dispatchPreview?.rows_to_add_sendgrid_4 || 0);
  const previewSg5 = Number(dispatchPreview?.rows_to_add_sendgrid_5 || 0);
  const previewSendgrid = previewSg1 + previewSg2 + previewSg3 + previewSg4 + previewSg5;
  const previewSkipped = Number(dispatchPreview?.skipped_both || 0)
    || Number(dispatchPreview?.skipped_already_sent || 0)
    + Number(dispatchPreview?.skipped_already_queued || 0)
    + Number(dispatchPreview?.skipped_suppressed || 0)
    + Number(dispatchPreview?.skipped_invalid_malformed || 0);

  renderDispatchConfirmGuard(dispatchSource, dispatchPreview);
  if (els.leadsImportantDispatchMeta) {
    if (dispatchPreview && !result?.generated_at_utc) {
      setNodeText(
        els.leadsImportantDispatchMeta,
        dispatchBlockReason
          ? `Preview ready. ${escapeHtml(dispatchPreview.dispatch_source_name || dispatchPreview.dispatch_source_mode || "triaged_keep")} with cap ${escapeHtml(dispatchPreview.dispatch_cap_label || dispatchPreview.dispatch_cap || "all")}. Dispatch actions are blocked: ${dispatchBlockReason}`
          : `Preview ready. ${escapeHtml(dispatchPreview.dispatch_source_name || dispatchPreview.dispatch_source_mode || "triaged_keep")} with cap ${escapeHtml(dispatchPreview.dispatch_cap_label || dispatchPreview.dispatch_cap || "all")}. Confirm Dispatch will write exactly this previewed set if nothing changed.`,
      );
    } else if (result?.generated_at_utc) {
      setNodeText(
        els.leadsImportantDispatchMeta,
        `Last dispatch ${lastDispatchGeneratedAt}. Source ${escapeHtml(result.dispatch_source_name || result.dispatch_source_mode || "triaged_keep")}. Astra ${confirmedPrivateJcTotal}, SendGrid ${confirmedSendgridTotal}. Live queue counts are shown separately below.`,
      );
    } else {
      const sourceMode = selectedDispatchSource.mode;
      const idlePath = dispatchSource?.dispatch_source_path || (sourceMode === "strict_verified" ? "_important/leads_verified.csv" : "_important/leads_triaged_keep.csv");
      const idleName = dispatchSource?.dispatch_source_name || (sourceMode === "strict_verified" ? "Strict Public Proof Verified" : "Fast Triage Keep");
      setNodeText(
        els.leadsImportantDispatchMeta,
        dispatchBlockReason
          ? `Dispatch is idle. Source ${idleName}. Preview and confirm are blocked: ${dispatchBlockReason}`
          : `Dispatch is idle. Source ${idleName}. Check the selected source first, then dispatch while all senders are stopped.`,
      );
    }
  }

  if (!result?.generated_at_utc) {
    const previewRows = Array.isArray(dispatchPreview?.assigned_preview_rows) ? dispatchPreview.assigned_preview_rows : [];
    const previewFields = Array.isArray(dispatchPreview?.queue_headers) ? dispatchPreview.queue_headers : [];
    setNodeHtml(
      els.leadsImportantDispatchResults,
      `
        <div class="dispatch-shell dispatch-shell-preview">
          ${renderOperatorMetricStrip([
            { label: "Current preview", value: dispatchPreview ? "Ready" : "Not generated", tone: dispatchPreview ? "good" : "warn" },
            { label: "Eligible", value: Number(dispatchPreview?.dispatch_eligible_row_count || dispatchSource.dispatch_eligible_row_count || 0) },
            { label: "Private JC planned", value: previewPrivateJc },
            { label: "SendGrid planned", value: previewSendgrid },
            { label: "Skipped", value: previewSkipped, tone: previewSkipped ? "warn" : "" },
          ], "dispatch-metrics")}
          <section class="dispatch-runbook">
            <div class="operator-table-head">
              <div>
                <h3>Dispatch Checklist</h3>
                <p class="muted">Intake/check volume is not dispatch approval. Confirm only after this surface is clean.</p>
              </div>
            </div>
            <div class="op-checklist-items dispatch-runbook-items">
              <div class="op-checklist-item ${preflightAllowed ? "is-ready" : "is-blocked"}">
                <div class="op-checklist-step">1</div>
                <div class="op-checklist-copy">
                  <strong>Preflight</strong>
                  <span>${preflightAllowed ? "All senders are stopped and no Check Leads job is running. Dispatch is allowed." : escapeHtml(dispatchBlockReason || `Blocked until active senders stop: ${activeSenderSummary}`)}</span>
                </div>
              </div>
              <div class="op-checklist-item ${dispatchSource.dispatch_source_path ? "is-ready" : "is-warn"}">
                <div class="op-checklist-step">2</div>
                <div class="op-checklist-copy">
                  <strong>Source</strong>
                  <span>${escapeHtml(sourceName)} · ${Number(dispatchSource.dispatch_source_row_count || 0)} rows · ${Number(dispatchSource.dispatch_eligible_row_count || 0)} eligible before cap</span>
                </div>
              </div>
              <div class="op-checklist-item ${dispatchPreview ? "is-ready" : "is-warn"}">
                <div class="op-checklist-step">3</div>
                <div class="op-checklist-copy">
                  <strong>Preview</strong>
                  <span>${dispatchPreview ? `${Number(dispatchPreview.dispatch_selected_row_count || 0)} selected by this cap · ${Number(dispatchPreview.total_rows_would_write || 0)} would write` : "Run Preview Dispatch to compute the exact capped write set."}</span>
                </div>
              </div>
              <div class="op-checklist-item ${dispatchPreview && preflightAllowed ? "is-ready" : "is-warn"}">
                <div class="op-checklist-step">4</div>
                <div class="op-checklist-copy">
                  <strong>Confirm</strong>
                  <span>${dispatchPreview && preflightAllowed ? "Ready to confirm the exact previewed set." : "Confirm stays disabled until preview is current and preflight passes."}</span>
                </div>
              </div>
            </div>
          </section>
          <section class="dispatch-decision-surface">
            <div class="operator-table-head">
              <div>
                <h3>Current preview</h3>
                <p class="muted">The exact write set lives here. Review this before confirm.</p>
              </div>
            </div>
            ${
              dispatchPreview
                ? `
                  ${renderOperatorMetricStrip([
                    { label: "Cap", value: dispatchPreview.dispatch_cap_label || dispatchPreview.dispatch_cap || "all" },
                    { label: "Eligible", value: Number(dispatchPreview.dispatch_eligible_row_count || 0) },
                    { label: "Private JC", value: previewPrivateJc, tone: "good" },
                    { label: "SendGrid", value: previewSendgrid, tone: "good" },
                    { label: "Skipped", value: previewSkipped, tone: previewSkipped ? "warn" : "" },
                  ], "dispatch-selection-strip")}
                  <details class="dispatch-drawer advanced-details">
                    <summary>Advanced dispatch details</summary>
                    <div class="dispatch-disclosure-body">
                      ${renderOperatorPillStrip([
                        `Selected source ${sourceName}`,
                        `Source path ${sourcePath}`,
                        `Cap ${dispatchPreview.dispatch_cap_label || dispatchPreview.dispatch_cap || "all"}`,
                        `Preflight ${preflightLabel}`,
                        `Active senders ${activeSenderSummary}`,
                        `Already sent ${Number(dispatchPreview.skipped_already_sent || 0)}`,
                        `Already queued ${Number(dispatchPreview.skipped_already_queued || 0)}`,
                        `Suppressed ${Number(dispatchPreview.skipped_suppressed || 0)}`,
                        `Invalid ${Number(dispatchPreview.skipped_invalid_malformed || 0)}`,
                        dispatchPreview.preview_path ? `Preview path ${dispatchPreview.preview_path}` : "",
                        dispatchPreview.assigned_preview_archive_path ? `Assigned preview ${dispatchPreview.assigned_preview_archive_path}` : "",
                      ])}
                      ${renderOperatorMetricStrip([
                        { label: "JC", value: previewPrivateJc },
                        { label: "SG1", value: previewSg1 },
                        { label: "SG2", value: previewSg2 },
                        { label: "SG3", value: previewSg3 },
                        { label: "SG4", value: previewSg4 },
                        { label: "SG5", value: previewSg5 },
                      ], "dispatch-allocation-strip")}
                      <div class="operator-result-grid">
                        ${renderOperatorTableBlock("Source Preview", "The eligible source rows behind this run.", sourceHeaders, sourcePreviewRows, "No source preview available yet.")}
                        ${renderOperatorTableBlock("Assigned Preview", "The exact rows that would be written on confirm.", previewFields, previewRows, "No assigned preview rows were produced.")}
                        ${Array.isArray(dispatchPreview.already_contacted_evidence) && dispatchPreview.already_contacted_evidence.length
                          ? renderOperatorTableBlock(
                            "Already Contacted Evidence",
                            "already_contacted is a send-history protection, not a lead-quality rejection.",
                            ["matched_email", "normalized_matched_email", "contact_ledger_source_file", "contacted_at", "channel", "campaign", "subject", "matching_rule"],
                            dispatchPreview.already_contacted_evidence,
                            "No already_contacted evidence was recorded.",
                          )
                          : ""}
                      </div>
                      ${renderOperatorTable(
                        ["Queue", "Current Live"],
                        [
                          { Queue: "Astra / JC", "Current Live": liveJcCount },
                          { Queue: "SG1", "Current Live": liveSg1 },
                          { Queue: "SG2", "Current Live": liveSg2 },
                          { Queue: "SG3", "Current Live": liveSg3 },
                          { Queue: "SG4", "Current Live": liveSg4 },
                          { Queue: "SG5", "Current Live": liveSg5 },
                        ],
                        "No live queue counts available.",
                        "dispatch-live-table",
                      )}
                      <p class="dispatch-support-note">Live queue comparison is advanced-only and does not change the preview.</p>
                    </div>
                  </details>
                `
                : `
                  <section class="operator-empty-state operator-empty-state-inline">
                    <strong>No current dispatch preview generated yet.</strong>
                    <span>No current dispatch preview generated yet. Click Preview Dispatch to calculate queue assignments.</span>
                  </section>
                `
            }
          </section>
        </div>
      `,
    );
    return;
  }

  const previewRows = Array.isArray(result.assigned_preview_rows) ? result.assigned_preview_rows : [];
  const previewFields = Array.isArray(result.queue_headers) ? result.queue_headers : [];
  const confirmedZeroAdd = Number(result.total_rows_would_write || 0) === 0;
  const exclusionReasons = result.exclusion_reason_counts || {};
  const skippedAlreadyContacted = Number(result.skipped_already_contacted || exclusionReasons.already_contacted || 0);
  const skippedAlreadySent = Number(result.skipped_already_sent || exclusionReasons.already_sent || 0);
  const skippedAlreadyQueued = Number(result.skipped_already_queued || exclusionReasons.already_queued || 0);
  const skippedSuppressed = Number(result.skipped_suppressed || result.suppressed_skipped || exclusionReasons.suppressed || 0);
  const skippedInvalid = Number(result.skipped_invalid_malformed || result.invalid_malformed_skipped || exclusionReasons.invalid_source_row || 0);
  const sendgridZeroAddReasonParts = [
    skippedAlreadyContacted ? `${skippedAlreadyContacted} already contacted` : "",
    Number(result.skipped_sendgrid_already_sent || 0) ? `${Number(result.skipped_sendgrid_already_sent || 0)} already sent through SendGrid` : "",
    Number(result.skipped_sendgrid_already_queued || 0) ? `${Number(result.skipped_sendgrid_already_queued || 0)} already queued for SendGrid` : "",
    skippedSuppressed ? `${skippedSuppressed} suppressed` : "",
    skippedInvalid ? `${skippedInvalid} invalid or malformed` : "",
  ].filter(Boolean);
  const sendgridZeroAddExplanation = confirmedSendgridTotal === 0 && Number(result.dispatch_selected_row_count || result.selected_rows || 0) > 0
    ? `SendGrid added 0 rows because the selected rows were excluded before queue write${sendgridZeroAddReasonParts.length ? `: ${sendgridZeroAddReasonParts.join(", ")}.` : "."}`
    : "";
  const alreadyContactedEvidenceRows = Array.isArray(result.already_contacted_evidence) ? result.already_contacted_evidence : [];
  setNodeHtml(
    els.leadsImportantDispatchResults,
    `
      <div class="dispatch-shell dispatch-shell-confirmed">
        ${renderOperatorMetricStrip([
          { label: "Last confirmed dispatch", value: lastDispatchGeneratedAt },
          { label: "Eligible", value: Number(dispatchSource.dispatch_eligible_row_count || result.dispatch_eligible_row_count || 0) },
          { label: "Private JC added", value: confirmedPrivateJcTotal, tone: "good" },
          { label: "SendGrid added", value: confirmedSendgridTotal, tone: "good" },
          { label: "Skipped", value: Number(result.skipped_both || 0), tone: Number(result.skipped_both || 0) ? "warn" : "" },
        ], "dispatch-metrics")}
        <section class="dispatch-decision-surface dispatch-current-preview">
          <div class="operator-table-head">
            <div>
              <h3>Current preview</h3>
              <p class="muted">This is the preview for the currently selected source and cap.</p>
            </div>
          </div>
          ${dispatchPreview
            ? `
              ${renderOperatorMetricStrip([
                { label: "Eligible", value: Number(dispatchPreview.dispatch_eligible_row_count || 0) },
                { label: "Selected", value: Number(dispatchPreview.dispatch_selected_row_count || 0), tone: "good" },
                { label: "Would Write", value: Number(dispatchPreview.total_rows_would_write || 0), tone: "good" },
                { label: "Cap", value: dispatchPreview.dispatch_cap_label || dispatchPreview.dispatch_cap || "all" },
              ], "dispatch-selection-strip")}
            `
            : `
              <section class="operator-empty-state operator-empty-state-inline">
                <strong>No current dispatch preview generated yet.</strong>
                <span>No current dispatch preview generated yet. Click Preview Dispatch to calculate queue assignments.</span>
              </section>
            `}
        </section>
        <section class="dispatch-decision-surface">
          <div class="operator-table-head">
            <div>
              <h3>Last confirmed dispatch — not the current upload</h3>
              <p class="muted">Last confirmed dispatch — not the current upload. Use Current preview above for the active source before confirming again.</p>
            </div>
          </div>
          ${sendgridZeroAddExplanation
            ? `
              <section class="operator-empty-state operator-empty-state-inline">
                <strong>SendGrid added 0 rows.</strong>
                <span>${escapeHtml(sendgridZeroAddExplanation)}</span>
              </section>
            `
            : ""}
          <details class="dispatch-drawer advanced-details">
            <summary>Advanced dispatch details</summary>
            <div class="dispatch-disclosure-body">
              ${renderOperatorPillStrip([
                `Source ${sourceName}`,
                `Path ${sourcePath}`,
                `Backup ${result.backup_dir || "-"}`,
                result.assigned_preview_archive_path ? `Assigned preview ${result.assigned_preview_archive_path}` : "",
                result.confirmed_summary_archive_path ? `Confirmed summary ${result.confirmed_summary_archive_path}` : "",
              ])}
              ${renderOperatorMetricStrip([
                { label: "Source rows", value: Number(dispatchSource.dispatch_source_row_count || result.dispatch_source_row_count || 0) },
                { label: "Suppressed", value: Number(result.suppressed_skipped || 0), tone: "warn" },
                { label: "JC", value: confirmedPrivateJcTotal },
                { label: "SG1", value: confirmedSg1 },
                { label: "SG2", value: confirmedSg2 },
                { label: "SG3", value: confirmedSg3 },
                { label: "SG4", value: confirmedSg4 },
                { label: "SG5", value: confirmedSg5 },
              ], "dispatch-allocation-strip")}
              <div class="operator-result-grid">
                ${sourceHeaders.length && sourcePreviewRows.length
                  ? renderOperatorTableBlock("Source Snapshot", "Source rows used for the last confirmed run.", sourceHeaders, sourcePreviewRows, "No source preview available.")
                  : ""}
                ${renderOperatorTableBlock(
                  "Channel Decisions",
                  "How this dispatch wrote or skipped rows by channel.",
                  ["Channel", "Decision", "Count"],
                  [
                    { Channel: "Astra", Decision: "Added", Count: confirmedPrivateJcTotal },
                    { Channel: "Astra", Decision: "Already Sent", Count: Number(result.skipped_astra_already_sent || 0) },
                    { Channel: "Astra", Decision: "Already Queued", Count: Number(result.skipped_astra_already_queued || 0) },
                    { Channel: "SendGrid", Decision: "Added", Count: confirmedSendgridTotal },
                    { Channel: "SendGrid", Decision: "Already Contacted", Count: skippedAlreadyContacted },
                    { Channel: "SendGrid", Decision: "Already Sent", Count: Number(result.skipped_sendgrid_already_sent || 0) },
                    { Channel: "SendGrid", Decision: "Already Queued", Count: Number(result.skipped_sendgrid_already_queued || 0) },
                    { Channel: "Both", Decision: "Suppressed", Count: skippedSuppressed },
                    { Channel: "Both", Decision: "Invalid / Malformed", Count: skippedInvalid },
                    { Channel: "Both", Decision: "Skipped Both", Count: Number(result.skipped_both || 0) },
                  ],
                  "No channel decisions were recorded.",
                )}
                ${alreadyContactedEvidenceRows.length
                  ? renderOperatorTableBlock(
                    "Already Contacted Evidence",
                    "already_contacted is a send-history protection, not a lead-quality rejection.",
                    ["matched_email", "normalized_matched_email", "contact_ledger_source_file", "contacted_at", "channel", "campaign", "subject", "matching_rule"],
                    alreadyContactedEvidenceRows,
                    "No already_contacted evidence was recorded.",
                  )
                  : ""}
              </div>
              ${renderOperatorTable(
                ["Queue", "Current Live", "At Last Dispatch"],
                [
                  { Queue: "Astra / JC", "Current Live": liveJcCount, "At Last Dispatch": Number(result.final_queue_counts?.jc || 0) },
                  { Queue: "SG1", "Current Live": liveSg1, "At Last Dispatch": Number(result.final_queue_counts?.sg1 || 0) },
                  { Queue: "SG2", "Current Live": liveSg2, "At Last Dispatch": Number(result.final_queue_counts?.sg2 || 0) },
                  { Queue: "SG3", "Current Live": liveSg3, "At Last Dispatch": Number(result.final_queue_counts?.sg3 || 0) },
                  { Queue: "SG4", "Current Live": liveSg4, "At Last Dispatch": Number(result.final_queue_counts?.sg4 || 0) },
                  { Queue: "SG5", "Current Live": liveSg5, "At Last Dispatch": Number(result.final_queue_counts?.sg5 || 0) },
                ],
                "No live queue comparison is available.",
                "dispatch-live-table",
              )}
              <p class="dispatch-support-note">Live queue comparison is advanced-only and may be lower after sending drains files.</p>
              ${
                previewFields.length && previewRows.length
                  ? renderOperatorTable(previewFields, previewRows, "No assigned preview rows were stored for the last dispatch.")
                  : confirmedZeroAdd
                    ? `<section class="operator-empty-state operator-empty-state-inline"><strong>Zero-add dispatch stored.</strong><span>No assigned rows were expected for this confirmed dispatch. Skip reasons were saved with the confirmed summary.</span></section>`
                    : `<section class="operator-empty-state operator-empty-state-inline"><strong>No stored assigned preview.</strong><span>Last dispatch has no stored assigned preview. Re-run Preview Dispatch before confirming again.</span></section>`
              }
            </div>
          </details>
        </section>
      </div>
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

function funnelStageDisplay(stage) {
  const status = String(stage?.status || "pending").toLowerCase();
  if (status === "ready") {
    return {
      text: Number(stage?.row_count || 0).toLocaleString(),
      tone: "good",
      badge: "Fresh",
    };
  }
  if (status === "not_available") {
    return { text: "Not available", tone: "warn", badge: "Missing" };
  }
  return { text: "Pending", tone: "", badge: "Pending" };
}

function funnelPathLabel(stage) {
  const path = String(stage?.path || "").trim();
  if (!path) return "";
  return path.split(/[\\/]/).slice(-2).join("/");
}

function renderFunnelPath(stage) {
  const path = String(stage?.path || "").trim();
  if (!path) return "";
  return `<span class="path-ellipsis" title="${escapeHtml(path)}">${escapeHtml(funnelPathLabel(stage))}</span>`;
}

function renderFunnelCell(stage) {
  const display = funnelStageDisplay(stage || {});
  return `
    <td class="lead-funnel-value">
      <span class="status-pill status-pill-${escapeHtml(display.tone || "pending")}">${escapeHtml(display.text)}</span>
    </td>
  `;
}

function funnelPassThrough(summary) {
  return summary?.pass_through_rate?.status === "ready" && summary?.pass_through_rate?.value !== null
    ? `${Number(summary.pass_through_rate.value || 0).toFixed(1)}%`
    : "Pending";
}

function renderFunnelComparisonRow(label, currentStage, nextStage) {
  return `
    <tr>
      <td class="lead-funnel-stage">${escapeHtml(label)}</td>
      ${renderFunnelCell(currentStage)}
      ${renderFunnelCell(nextStage)}
    </tr>
  `;
}

function renderLeadFunnelSummary(funnel) {
  if (!els.leadFunnelSummary) return;
  const current = funnel?.current_live || {};
  const next = funnel?.next_batch || {};
  const nextRunId = String(next?.run_id || "").trim();
  setNodeHtml(
    els.leadFunnelSummary,
    `
      <div class="lead-funnel-title">
        <div>
          <p class="eyebrow">Lead Funnel Summary</p>
          <h3>Raw leads → cleaned → triaged → eligible</h3>
        </div>
        <span class="mini-pill">${escapeHtml(nextRunId ? `Next ${nextRunId}` : "Counts only")}</span>
      </div>
      <div class="lead-funnel-table-wrap">
        <table class="lead-funnel-table" aria-label="Lead Funnel Summary">
          <colgroup>
            <col class="lead-funnel-stage-col" />
            <col class="lead-funnel-value-col" />
            <col class="lead-funnel-value-col" />
          </colgroup>
          <thead>
            <tr>
              <th>Stage</th>
              <th>Current live</th>
              <th>Next batch</th>
            </tr>
          </thead>
          <tbody>
          ${renderFunnelComparisonRow("Raw input", current.raw_input, next.raw_input)}
          ${renderFunnelComparisonRow("After cleanup", current.cleaned_after_check, next.cleaned_after_check)}
          ${renderFunnelComparisonRow("Check rejected", current.check_rejected, next.check_rejected)}
          ${renderFunnelComparisonRow("Triage keep", current.triage_keep, next.triage_keep)}
          ${renderFunnelComparisonRow("Triage reject", current.triage_reject, next.triage_reject)}
          ${renderFunnelComparisonRow("Triage quarantine", current.triage_quarantine, next.triage_quarantine)}
          ${renderFunnelComparisonRow("Final eligible", current.final_eligible, next.final_eligible)}
          ${renderFunnelComparisonRow("Removed/excluded", current.total_removed_excluded, next.total_removed_excluded)}
          <tr>
            <td class="lead-funnel-stage">Pass-through</td>
            <td class="lead-funnel-value"><span class="status-pill">${escapeHtml(funnelPassThrough(current))}</span></td>
            <td class="lead-funnel-value"><span class="status-pill">${escapeHtml(funnelPassThrough(next))}</span></td>
          </tr>
          </tbody>
        </table>
      </div>
    `,
  );
}

function formatOperatorCount(value) {
  if (value === null || value === undefined || value === "") return "Pending";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toLocaleString() : String(value);
}

function intakeModeLabelFromStatus(status = lastLeadsStatus) {
  const mode = String(
    els.leadsImportantIntakeMode?.value
    || status?.latest_master_check?.intake_mode
    || status?.latest_lead_triage?.intake_mode
    || status?.latest_lead_triage?.mode
    || "standard",
  ).toLowerCase();
  return mode === "manual_author_research" || mode === VERIFY_MODE_MANUAL_AUTHOR_RESEARCH.toLowerCase()
    ? "Manual Author Research"
    : "Standard";
}

function latestDispatchAddedSummary(dispatch = lastImportantDispatch) {
  if (!dispatch?.generated_at_utc) return "Pending";
  const privateAdded = Number(dispatch.private_jc_added || dispatch.added_astra || 0);
  const sendgridAdded = Number(dispatch.sendgrid_added || dispatch.added_sendgrid || 0);
  return `JC ${privateAdded.toLocaleString()} · SG ${sendgridAdded.toLocaleString()}`;
}

function workflowTerminalStatus(job) {
  const status = String(job?.status || "").toLowerCase();
  if (["failed", "error"].includes(status)) return "failed";
  if (["canceled", "cancelled"].includes(status)) return "failed";
  if (status === "completed") return "completed";
  return "";
}

function workflowStepStatus(activeJob, latestResult, pendingLabel = "pending") {
  if (isActiveImportantLeadCheckJob(activeJob)) return "running";
  const terminal = workflowTerminalStatus(activeJob);
  if (terminal) return terminal;
  if (latestResult?.generated_at_utc) return "completed";
  return pendingLabel;
}

function workflowStatusLabel(status) {
  const normalized = String(status || "pending").toLowerCase();
  if (normalized === "not_generated") return "not generated";
  if (normalized === "not_confirmed") return "not confirmed";
  return normalized;
}

function workflowStatusTone(status) {
  const normalized = String(status || "").toLowerCase();
  if (["completed", "ready", "confirmed"].includes(normalized)) return "good";
  if (["running"].includes(normalized)) return "warn";
  if (["failed"].includes(normalized)) return "bad";
  return "pending";
}

function workflowNextStepMessage(checkStatus, triageStatus, previewStatus, confirmStatus) {
  if (checkStatus === "running") return "Check Leads running...";
  if (checkStatus === "failed") return "Check failed. Review the error before continuing.";
  if (checkStatus === "completed" && triageStatus === "pending") return "Check complete. Next step: Run Fast Triage.";
  if (triageStatus === "running") return "Fast Triage running...";
  if (triageStatus === "failed") return "Fast Triage failed. Review the error before previewing dispatch.";
  if (triageStatus === "completed" && previewStatus === "not_generated") return "Fast Triage complete. Next step: Preview Dispatch.";
  if (previewStatus === "running") return "Preview Dispatch running...";
  if (previewStatus === "failed") return "Preview Dispatch failed. Re-run preview after fixing the issue.";
  if (previewStatus === "ready" && confirmStatus !== "confirmed") return "Preview Dispatch ready. Next step: Confirm Dispatch.";
  if (confirmStatus === "confirmed") return "Dispatch confirmed. Queue write summary is shown below.";
  return "Start with Check Leads, then run Fast Triage and Preview Dispatch.";
}

function renderWorkflowStep(label, status, detail = "") {
  const normalized = String(status || "pending").toLowerCase();
  return `
    <div class="workflow-step workflow-step-${escapeHtml(workflowStatusTone(normalized))}">
      <span class="workflow-step-label">${escapeHtml(label)}</span>
      <strong>${escapeHtml(workflowStatusLabel(normalized))}</strong>
      ${detail ? `<span>${escapeHtml(detail)}</span>` : ""}
    </div>
  `;
}

function renderLeadsWorkflowStatusBanner(status = lastLeadsStatus) {
  if (!els.leadsWorkflowStatusBanner) return;
  const activeCheck = currentImportantCheckJob(status);
  const activeVerify = status?.active_important_verify_job || lastImportantVerifyJob || null;
  const activeDispatch = status?.active_important_dispatch_job || lastImportantDispatchJob || null;
  const latestCheck = status?.latest_master_check || lastImportantLeadCheck || {};
  const latestTriage = status?.latest_lead_triage || status?.latest_lead_verify || lastImportantVerify || {};
  const latestDispatch = status?.latest_dispatch || lastImportantDispatch || {};
  const checkStatus = workflowStepStatus(activeCheck, latestCheck);
  const triageStatus = workflowStepStatus(activeVerify, latestTriage);
  const currentPreviewReady = dispatchPreviewMatchesCurrentSelection() && Boolean(lastImportantDispatchPreview?.preview_id);
  const previewStatus = importantLeadDispatchPreviewLoading
    ? "running"
    : currentPreviewReady
      ? "ready"
      : lastImportantDispatchPreviewState === "failed"
        ? "failed"
        : "not_generated";
  const confirmStatus = importantLeadDispatchConfirmLoading || isActiveImportantLeadCheckJob(activeDispatch)
    ? "running"
    : latestDispatch?.generated_at_utc
      ? "confirmed"
      : "not_confirmed";
  const triageCounts = latestTriage?.generated_at_utc
    ? `input ${formatOperatorCount(latestTriage.total_input_rows)} · keep ${formatOperatorCount(latestTriage.keep_count)} · reject ${formatOperatorCount(latestTriage.reject_count)} · review ${formatOperatorCount(latestTriage.quarantine_count)}`
    : "";
  setNodeHtml(
    els.leadsWorkflowStatusBanner,
    `
      <div class="workflow-banner-head">
        <div>
          <p class="eyebrow">Workflow Status</p>
          <strong>${escapeHtml(workflowNextStepMessage(checkStatus, triageStatus, previewStatus, confirmStatus))}</strong>
        </div>
      </div>
      <div class="workflow-step-grid">
        ${renderWorkflowStep("Last check", checkStatus)}
        ${renderWorkflowStep("Last triage", triageStatus, triageCounts)}
        ${renderWorkflowStep("Preview dispatch", previewStatus)}
        ${renderWorkflowStep("Confirm dispatch", confirmStatus)}
      </div>
    `,
  );
}

function renderLeadsOperatorStatusStrip(status = lastLeadsStatus) {
  if (!els.leadsOperatorStatusStrip) return;
  const safety = leadsRunSafety(status);
  const latestCheck = status?.latest_master_check || {};
  const latestTriage = status?.latest_lead_triage || status?.latest_lead_verify || {};
  const blocker = safety.queueUnsafe
    ? (safety.reasons[0] || "Recipient queue unsafe.")
    : (safety.checkRunning ? "Next batch check is running." : "None");
  const triageSummary = latestTriage?.generated_at_utc
    ? `Keep ${formatOperatorCount(latestTriage.keep_count)} · Review ${formatOperatorCount(latestTriage.quarantine_count)} · Reject ${formatOperatorCount(latestTriage.reject_count)}`
    : "Pending";
  setNodeHtml(
    els.leadsOperatorStatusStrip,
    `
      ${renderOperatorMetricStrip([
        { label: "Intake mode", value: intakeModeLabelFromStatus(status) },
        { label: "Last check", value: latestCheck?.generated_at_utc ? formatOperatorCount(latestCheck.cleaned_rows || latestCheck.output_rows || latestCheck.input_rows) : "Pending" },
        { label: "Last triage", value: triageSummary },
        { label: "Last dispatch", value: latestDispatchAddedSummary(status?.latest_dispatch || lastImportantDispatch) },
        { label: "Current blocker", value: blocker, tone: safety.queueUnsafe ? "warn" : "good" },
      ], "operator-status-metrics")}
    `,
  );
}

function renderLeadsActiveAlerts(status = lastLeadsStatus, snapshot = lastSnapshot) {
  if (!els.leadsActiveAlerts) return;
  const safety = leadsRunSafety(status, snapshot);
  const cards = [];
  if (safety.queueUnsafe) {
    cards.push({
      severity: "bad",
      title: "Current live queue blocked",
      message: safety.reasons[0] || "Recipient queue unsafe. Rebuild queues from the current campaign source before starting.",
      blocks: true,
    });
  }
  const currentSafety = status?.current_send_safety || {};
  if (currentSafety.sendgrid_status && currentSafety.private_status && currentSafety.sendgrid_status !== currentSafety.private_status) {
    cards.push({
      severity: currentSafety.private_status === "READY" ? "warn" : "bad",
      title: `${currentSafety.sendgrid_status === "READY" ? "SendGrid ready" : "SendGrid blocked"}; ${currentSafety.private_status === "READY" ? "Private JC ready" : "Private JC blocked"}`,
      message: "Provider-specific queue safety controls individual Start buttons. Start All still requires every provider to be safe.",
      blocks: currentSafety.private_status !== "READY" || currentSafety.sendgrid_status !== "READY",
    });
  }
  (Array.isArray(snapshot?.alerts) ? snapshot.alerts : []).forEach((alert) => {
    cards.push({
      severity: alert?.severity || "warn",
      title: alert?.title || "Alert",
      message: alert?.message || "",
      blocks: Boolean(alert?.blocks_sending),
    });
  });
  if (!cards.length) {
    cards.push({
      severity: "good",
      title: "No active lead safety alerts",
      message: "Current lead safety checks do not show a blocking alert.",
      blocks: false,
    });
  }
  setNodeHtml(
    els.leadsActiveAlerts,
    cards.slice(0, 6).map((card) => `
      <article class="leads-alert-card leads-alert-card-${escapeHtml(card.severity || "warn")}">
        <div>
          <strong>${escapeHtml(card.title)}</strong>
          <p>${escapeHtml(card.message || "No details provided.")}</p>
        </div>
        <span class="mini-pill">${card.blocks ? "Blocking" : "Info"}</span>
      </article>
    `).join(""),
  );
}

function renderLeadsRunSafety(status = lastLeadsStatus) {
  if (!els.leadsRunSafetyCard) return;
  const safety = leadsRunSafety(status);
  const tone = safety.statusLabel === "SAFE TO CONTINUE" ? "safe-to-continue" : safety.statusLabel.toLowerCase().replace(/\s+/g, "-");
  const progress = safety.progress || {};
  const progressText = progress.total > 0
    ? `${progress.processed} / ${progress.total} (${progress.percent.toFixed(1)}%)`
    : "n/a";
  const reasons = safety.reasons.length
    ? safety.reasons
    : ["Live recipient queues are approved for current sending."];
  const currentSafetyTitle = safety.queueUnsafe ? "Current live queue blocked" : "Current live queue ready";
  const currentSafetyScope = "Current approved live queues only";
  setNodeHtml(
    els.leadsRunSafetyCard,
    `
      <div class="leads-run-safety-head">
        <div>
          <p class="eyebrow">Current Run Safety</p>
          <h3>${escapeHtml(currentSafetyTitle)}</h3>
          <strong>${escapeHtml(safety.statusLabel)}</strong>
        </div>
        <span class="mini-pill">${escapeHtml(currentSafetyScope)}</span>
      </div>
      <div class="leads-run-safety-body">
        <div class="leads-run-safety-reasons">
          ${reasons.map((reason) => `<div>${escapeHtml(reason)}</div>`).join("")}
        </div>
        ${renderOperatorMetricStrip([
          { label: "Live Queue", value: safety.queueUnsafe ? "Blocked" : "Ready", tone: safety.queueUnsafe ? "warn" : "good" },
          { label: "SendGrid", value: status?.current_send_safety?.sendgrid_status || "-", tone: status?.current_send_safety?.sendgrid_status === "READY" ? "good" : "warn" },
          { label: "Private JC", value: status?.current_send_safety?.private_status || "-", tone: status?.current_send_safety?.private_status === "READY" ? "good" : "warn" },
          { label: "Active Check", value: safety.checkRunning ? "Running" : "Idle", tone: safety.checkRunning ? "warn" : "good" },
        ], "leads-run-safety-metrics")}
      </div>
    `,
  );
  els.leadsRunSafetyCard.className = `leads-run-safety-card leads-run-safety-card-${tone}`;

  if (els.nextBatchPrepCard) {
    const prep = safety.nextBatchPrep || {};
    const prepStatus = String(prep.status || (safety.checkRunning ? "WAIT" : "NOT READY"));
    const prepTone = prepStatus === "SAFE TO PROMOTE"
      ? "safe-to-continue"
      : prepStatus === "NOT READY"
        ? "wait"
        : prepStatus.toLowerCase().replace(/\s+/g, "-");
    const prepReasons = Array.isArray(prep.reasons) && prep.reasons.length
      ? prep.reasons
      : [safety.checkRunning ? "Check Leads is running for the next batch." : "No staged next-batch blocker is visible."];
    const prepTitle = prepStatus === "SAFE TO PROMOTE"
      ? "Staged next batch safe to promote"
      : prepStatus === "WAIT"
        ? "Staged next batch running"
        : "Staged next batch not ready";
    setNodeHtml(
      els.nextBatchPrepCard,
      `
        <div class="leads-run-safety-head">
          <div>
            <p class="eyebrow">Next Batch Prep Status</p>
            <h3>${escapeHtml(prepTitle)}</h3>
            <strong>${escapeHtml(prepStatus)}</strong>
          </div>
          <span class="mini-pill">${escapeHtml(prep.blocks_current_send === false ? "Staged lane only" : "Prep lane")}</span>
        </div>
        <div class="leads-run-safety-body">
          <div class="leads-run-safety-reasons">
            ${prepReasons.map((reason) => `<div>${escapeHtml(reason)}</div>`).join("")}
          </div>
          ${renderOperatorMetricStrip([
            { label: "Check Job", value: safety.checkJobId },
            { label: "Progress", value: progressText },
            { label: "Staged leads.csv", value: outputFreshnessLabel(safety.leadsFresh), tone: safety.leadsFresh === false ? "warn" : safety.leadsFresh === true ? "good" : "" },
            { label: "Staged Triage", value: outputFreshnessLabel(safety.triageFresh), tone: safety.triageFresh === false ? "warn" : safety.triageFresh === true ? "good" : "" },
            { label: "Staged Preview", value: outputFreshnessLabel(safety.previewFresh), tone: safety.previewFresh === false ? "warn" : safety.previewFresh === true ? "good" : "" },
          ], "leads-run-safety-metrics")}
        </div>
      `,
    );
    els.nextBatchPrepCard.className = `leads-run-safety-card leads-run-safety-card-${prepTone}`;
  }
}

function renderLeadsStatus(status) {
  lastLeadsStatus = status || lastLeadsStatus;
  if (isLeadsTabVisible()) {
    setConnectionState(false);
    if (els.toolbarGeneratedAt) {
      setNodeText(els.toolbarGeneratedAt, "Leads local snapshot loaded");
    }
  }
  const activeCheckJob = lastLeadsStatus?.active_important_check_job || null;
  const activeVerifyJob = lastLeadsStatus?.active_important_verify_job || null;
  const activeDispatchJob = lastLeadsStatus?.active_important_dispatch_job || null;
  const shouldResumeLeadJobs = isLeadsTabVisible();
  syncImportantLeadPathInputs(lastLeadsStatus);
  syncImportantVerifyPathInputs(lastLeadsStatus);
  syncImportantDispatchSourceMode(lastLeadsStatus);
  updateImportantLeadPasteGuardrails();
  lastImportantLeadCheck = lastLeadsStatus?.latest_master_check || lastImportantLeadCheck;
  lastImportantVerify = lastLeadsStatus?.latest_lead_triage || lastLeadsStatus?.latest_lead_verify || lastImportantVerify;
  lastImportantDispatch = lastLeadsStatus?.latest_dispatch || lastImportantDispatch;
  lastImportantDispatchSource = lastLeadsStatus?.dispatch_source || lastImportantDispatchSource;
  if (shouldResumeLeadJobs && !resumeImportantLeadCheckJob(activeCheckJob)) {
    renderImportantLeadCheck(lastImportantLeadCheck);
  } else if (!shouldResumeLeadJobs) {
    renderImportantLeadCheck(lastImportantLeadCheck);
  }
  if (shouldResumeLeadJobs && !resumeImportantLeadVerifyJob(activeVerifyJob)) {
    renderImportantLeadVerify(lastImportantVerify);
  } else if (!shouldResumeLeadJobs) {
    renderImportantLeadVerify(lastImportantVerify);
  }
  if (shouldResumeLeadJobs && !resumeImportantLeadDispatchJob(activeDispatchJob)) {
    renderImportantDispatch(lastImportantDispatch);
  } else if (!shouldResumeLeadJobs) {
    renderImportantDispatch(lastImportantDispatch);
  }

  const latestUpload = lastLeadsStatus?.latest_upload || null;
  const latestCleaned = lastLeadsStatus?.latest_cleaned || null;
  const latestShardReport = lastLeadsStatus?.latest_shard_report_summary || lastLeadsStatus?.latest_shard_report || null;
  renderLeadsMappingOptions(latestUpload);
  renderLeadsPreview(latestUpload);
  renderLeadsCleanResults(latestCleaned);
  renderLeadsShardResults(previewMatchesCurrentSelection() ? lastShardPreview : latestShardReport);
  renderLeadsWorkflowStatusBanner(lastLeadsStatus);
  renderLeadFunnelSummary(lastLeadsStatus?.lead_funnel || {});
  renderLeadsOperatorStatusStrip(lastLeadsStatus);
  renderLeadsRunSafety(lastLeadsStatus);
  renderLeadsPipeline(lastLeadsStatus?.pipeline || {});
  renderLeadsActiveAlerts(lastLeadsStatus, lastSnapshot);

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

function pipelineStateLabel(state) {
  const normalized = String(state || "").toLowerCase();
  if (normalized === "stale") return "STALE";
  if (normalized === "done") return "Ready";
  if (normalized === "active") return "Running";
  if (normalized === "warn") return "Review";
  return "Waiting";
}

function renderLeadsPipeline(pipeline) {
  const steps = Array.isArray(pipeline?.steps) ? pipeline.steps : [];
  const safety = leadsRunSafety();
  const staleKeys = new Set();
  if (safety.checkRunning || safety.triageFresh === false) {
    ["triage", "quarantine", "preview", "dispatch"].forEach((key) => staleKeys.add(key));
  } else if (safety.previewFresh === false) {
    ["preview", "dispatch"].forEach((key) => staleKeys.add(key));
  }
  if (els.leadsPipelineMeta) {
    const checkedRows = Number(pipeline?.checked_rows || 0);
    const triageKeepRows = Number(pipeline?.triaged_keep_rows || 0);
    const quarantineRows = Number(pipeline?.quarantine_rows || 0);
    const providedTriageRejectRows = Number(
      pipeline?.triaged_reject_rows
      || pipeline?.triaged_rejected_rows
      || pipeline?.triage_reject_rows
      || pipeline?.rejected_rows
      || 0,
    );
    const triageRejectRows = providedTriageRejectRows || Math.max(0, checkedRows - triageKeepRows - quarantineRows);
    const nextStep = pipeline?.next_step
      ? steps.find((step) => String(step.key || "") === String(pipeline.next_step || ""))
      : null;
    const archivePath = String(pipeline?.latest_pre_dispatch_archive_path || "");
    const summary = [
      nextStep ? `Next: ${nextStep.label || nextStep.key}` : "No active lead run",
      `Checked ${checkedRows}`,
      `Triage keep ${triageKeepRows}`,
      `Triage reject ${triageRejectRows}`,
      `Quarantine ${quarantineRows}`,
      `Eligible ${Number(pipeline?.dispatch_eligible_rows || 0)}`,
      archivePath ? `Archive ${archivePath.split(/[\\/]/).pop()}` : "",
    ].filter(Boolean).join(" | ");
    setNodeText(els.leadsPipelineMeta, summary);
  }
  if (!els.leadsPipelineSteps) return;
  setNodeHtml(
    els.leadsPipelineSteps,
    steps.length
      ? steps.map((step, index) => {
          const state = String(step.state || "waiting").toLowerCase();
          const key = String(step.key || "");
          const isStale = staleKeys.has(key) && state !== "active";
          const displayState = isStale ? "stale" : state;
          const note = isStale
            ? `${step.note || ""} Stale: newer Check Leads output is not ready for this stage.`
            : (step.note || "");
          return `
            <article class="leads-pipeline-step leads-pipeline-step-${escapeHtml(displayState)}">
              <div class="leads-pipeline-index">${index + 1}</div>
              <div class="leads-pipeline-copy">
                <div class="leads-pipeline-title">
                  <strong>${escapeHtml(step.label || step.key || "-")}</strong>
                  <span class="mini-pill">${escapeHtml(pipelineStateLabel(displayState))}</span>
                </div>
                <div class="muted">${escapeHtml(note)}</div>
              </div>
              <div class="leads-pipeline-count">${Number(step.count || 0)}</div>
            </article>
          `;
        }).join("")
      : `<p class="muted">Pipeline status will appear after the first leads status refresh.</p>`,
  );
}

async function fetchLeadsStatus() {
  try {
    const data = await fetchJson("/api/leads/status");
    renderLeadsStatus(data.status || {});
    markDashboardHydrated();
  } catch (err) {
    if (activeDashboardTab === "leads") {
      showMessage(`Leads status failed: ${err}`, "error");
    }
  }
}

async function runImportantLeadCheck() {
  updateImportantLeadPasteGuardrails();
  if (els.leadsImportantCheckBtn?.disabled) {
    showMessage(`Textarea paste is limited to ${importantLeadPastePolicy().maxRows || 1000} rows. Use Upload CSV for larger batches.`, "error");
    return;
  }
  if (els.leadsImportantCheckBtn) {
    setButtonBusy(els.leadsImportantCheckBtn, true, "Checking...");
  }
  try {
    const data = await fetchJson("/api/leads/check-important", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(importantLeadPathsPayload()),
    });
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
      setButtonBusy(els.leadsImportantCheckBtn, false, "Check Leads");
    }
  }
}

async function runImportantLeadUploadCheck() {
  const { formData, file, filename, size, extension } = importantLeadUploadPayload();
  if (!file) {
    showMessage("Choose a CSV or XLSX file before uploading.", "error");
    return;
  }
  if (extension && ![".csv", ".xlsx"].includes(extension)) {
    updateImportantLeadUploadNote(`Only .csv and .xlsx uploads are supported. Selected ${extension}.`);
    showMessage("Upload checks only accept .csv or .xlsx files.", "error");
    return;
  }
  if (els.leadsImportantUploadCheckBtn) {
    setButtonBusy(els.leadsImportantUploadCheckBtn, true, "Uploading...");
  }
  updateImportantLeadUploadNote(`Submitting ${filename} (${humanizeFileSize(size)}, ${extension || "no extension"}).`);
  try {
    const data = await fetchJson("/api/leads/check-important/upload", {
      method: "POST",
      body: formData,
    });
    if (data.job?.job_id) {
      renderImportantLeadCheckJob(data.job);
      void pollImportantLeadCheckJob(data.job.job_id);
      const serverFilename = data.job.server_received_filename || data.job.original_uploaded_filename || data.job.source_label || "-";
      const mismatch = filename && serverFilename && filename !== serverFilename;
      updateImportantLeadUploadNote(
        mismatch
          ? `Server received ${serverFilename}. Filename mismatch detected.`
          : `Server received ${serverFilename}. Job ${data.job.job_id}.`,
      );
      if (mismatch) {
        showMessage(`Upload filename mismatch: selected ${filename}, server received ${serverFilename}.`, "error");
        return;
      }
    } else if (data.check) {
      lastImportantLeadCheck = data.check || null;
      if (data.status) {
        renderLeadsStatus(data.status || {});
      } else {
        renderImportantLeadCheck(lastImportantLeadCheck);
      }
    }
    if (els.leadsImportantUploadFile) {
      els.leadsImportantUploadFile.value = "";
    }
    showMessage(data.message || "Uploaded file queued.", "success");
  } catch (err) {
    showMessage(`Upload lead check failed: ${err}`, "error");
  } finally {
    if (els.leadsImportantUploadCheckBtn) {
      setButtonBusy(els.leadsImportantUploadCheckBtn, false, "Upload & Check");
    }
  }
}

async function runImportantLeadVerify(mode = VERIFY_MODE_FAST_TRIAGE) {
  let normalizedMode = String(mode || VERIFY_MODE_FAST_TRIAGE).toUpperCase() === VERIFY_MODE_STRICT_PUBLIC_PROOF
    ? VERIFY_MODE_STRICT_PUBLIC_PROOF
    : VERIFY_MODE_FAST_TRIAGE;
  if (normalizedMode === VERIFY_MODE_FAST_TRIAGE && (els.leadsImportantIntakeMode?.value || "") === "manual_author_research") {
    normalizedMode = VERIFY_MODE_MANUAL_AUTHOR_RESEARCH;
  }
  const activeLabel = normalizedMode === VERIFY_MODE_STRICT_PUBLIC_PROOF ? "Strict verifying..." : "Triaging...";
  renderLeadsWorkflowStatusBanner(lastLeadsStatus);
  if (els.leadsImportantVerifyBtn) {
    setButtonBusy(els.leadsImportantVerifyBtn, true, activeLabel);
  }
  if (els.leadsImportantVerifyStrictBtn) {
    setButtonBusy(els.leadsImportantVerifyStrictBtn, true, activeLabel);
  }
  try {
    const data = await fetchJson("/api/leads/verify-important", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(importantLeadVerifyPayload(normalizedMode)),
    });
    if (data.job?.job_id) {
      renderImportantLeadVerifyJob(data.job);
      void pollImportantLeadVerifyJob(data.job.job_id);
      showMessage(data.message || "Lead verification queued.", "success");
    } else {
      lastImportantVerify = data.verify || null;
      if (data.status) {
        renderLeadsStatus(data.status || {});
      } else {
        renderImportantLeadVerify(lastImportantVerify);
      }
      showMessage(data.message || "Lead verification complete.", "success");
    }
  } catch (err) {
    showMessage(`Lead verification failed: ${err}`, "error");
  } finally {
    if (els.leadsImportantVerifyBtn) {
      const activeVerify = isActiveImportantLeadCheckJob(lastImportantVerifyJob);
      setButtonBusy(els.leadsImportantVerifyBtn, activeVerify, activeVerify ? "Verifying..." : "Fast Triage");
    }
    if (els.leadsImportantVerifyStrictBtn) {
      const activeVerify = isActiveImportantLeadCheckJob(lastImportantVerifyJob);
      setButtonBusy(els.leadsImportantVerifyStrictBtn, activeVerify, activeVerify ? "Verifying..." : "Strict Public Proof");
    }
    if (els.leadsImportantVerifyStopBtn) {
      const activeVerify = isActiveImportantLeadCheckJob(lastImportantVerifyJob);
      els.leadsImportantVerifyStopBtn.disabled = !activeVerify || Boolean(lastImportantVerifyJob?.cancel_requested);
      setNodeText(els.leadsImportantVerifyStopBtn, lastImportantVerifyJob?.cancel_requested ? "Stopping..." : "Stop Verify");
    }
  }
}

async function previewImportantLeadDispatch() {
  const blockReason = dispatchActionBlockReason();
  if (blockReason) {
    renderImportantDispatch(lastImportantDispatch);
    showMessage(`Dispatch preview blocked: ${blockReason}`, "error");
    return;
  }
  if (activeSenderProfiles().length) {
    renderImportantDispatch(lastImportantDispatch);
    showMessage(`Dispatch blocked: stop active senders first. Active: ${activeSenderProfiles().map((profile) => formatProfileName(profile.name)).join(", ")}`, "error");
    return;
  }
  if (els.leadsImportantDispatchPreviewBtn) {
    importantLeadDispatchPreviewLoading = true;
    lastImportantDispatchPreviewState = "running";
    setButtonBusy(els.leadsImportantDispatchPreviewBtn, true, "Previewing...");
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
  }
  try {
    const data = await fetchJson("/api/leads/dispatch-important/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(importantLeadDispatchPayload(false)),
    });
    if (data.preview?.preview_id) {
      lastImportantDispatchPreview = {
        ...(data.preview || {}),
        _preview_key: currentDispatchPlanKey(),
      };
      lastImportantDispatchPreviewState = "ready";
      if (data.status) {
        renderLeadsStatus(data.status || {});
      } else {
        renderImportantDispatch(lastImportantDispatch);
      }
      showMessage(data.message || "Dispatch preview ready.", "success");
    } else {
      showMessage("Dispatch preview did not return a preview id.", "error");
    }
  } catch (err) {
    lastImportantDispatchPreviewState = "failed";
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
    showMessage(`Dispatch preview failed: ${err}`, "error");
  } finally {
    importantLeadDispatchPreviewLoading = false;
    if (els.leadsImportantDispatchPreviewBtn) {
      const activeDispatch = isActiveImportantLeadCheckJob(lastImportantDispatchJob);
      setButtonBusy(els.leadsImportantDispatchPreviewBtn, activeDispatch, "Preview Dispatch");
      renderDispatchConfirmGuard(dispatchSourceForSelectedMode().source || {}, dispatchPreviewMatchesCurrentSelection() ? lastImportantDispatchPreview : null);
    }
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
  }
}

async function confirmImportantLeadDispatch() {
  const blockReason = dispatchActionBlockReason();
  if (blockReason) {
    renderImportantDispatch(lastImportantDispatch);
    showMessage(`Confirm Dispatch blocked: ${blockReason}`, "error");
    return;
  }
  if (activeSenderProfiles().length) {
    renderImportantDispatch(lastImportantDispatch);
    showMessage(`Dispatch blocked: stop active senders first. Active: ${activeSenderProfiles().map((profile) => formatProfileName(profile.name)).join(", ")}`, "error");
    return;
  }
  if (!dispatchPreviewMatchesCurrentSelection() || !lastImportantDispatchPreview?.preview_id) {
    showMessage("Run Preview Dispatch first for the current source and cap.", "error");
    return;
  }
  if (els.leadsImportantDispatchConfirmBtn) {
    importantLeadDispatchConfirmLoading = true;
    setButtonBusy(els.leadsImportantDispatchConfirmBtn, true, "Dispatching...");
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
  }
  try {
    const data = await fetchJson("/api/leads/dispatch-important/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(importantLeadDispatchPayload(true)),
    });
    if (data.job?.job_id) {
      renderImportantLeadDispatchJob(data.job);
      void pollImportantLeadDispatchJob(data.job.job_id);
      showMessage(data.message || "Lead dispatch queued.", "success");
    } else {
      showMessage("Dispatch confirm did not return a job.", "error");
    }
  } catch (err) {
    showMessage(`Lead dispatch failed: ${err}`, "error");
  } finally {
    importantLeadDispatchConfirmLoading = false;
    if (els.leadsImportantDispatchConfirmBtn) {
      const activeDispatch = isActiveImportantLeadCheckJob(lastImportantDispatchJob);
      setButtonBusy(els.leadsImportantDispatchConfirmBtn, activeDispatch, activeDispatch ? "Dispatching..." : "Confirm Dispatch");
      renderDispatchConfirmGuard(dispatchSourceForSelectedMode().source || {}, dispatchPreviewMatchesCurrentSelection() ? lastImportantDispatchPreview : null);
    }
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
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

function humanizeDurationCompact(totalSeconds) {
  const seconds = Number(totalSeconds);
  if (!Number.isFinite(seconds) || seconds <= 0) return "due";
  if (seconds < 60) return `${Math.max(1, Math.ceil(seconds))}s`;
  const totalMinutes = Math.ceil(seconds / 60);
  if (totalMinutes < 60) return `${totalMinutes}m`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (!minutes) return `${hours}h`;
  return `${hours}h ${minutes}m`;
}

function humanizeDurationClock(totalSeconds) {
  const seconds = Number(totalSeconds);
  if (!Number.isFinite(seconds) || seconds <= 0) return "0s";
  const whole = Math.ceil(seconds);
  const minutes = Math.floor(whole / 60);
  const remainder = whole % 60;
  if (minutes <= 0) return `${remainder}s`;
  return `${minutes}m ${remainder}s`;
}

function privateBounceTone(guard = {}) {
  const status = String(guard?.status || "idle");
  if (status === "watching") return "good";
  if (status === "cooldown" || (guard?.sync_stale && guard?.profile_active)) return "warn";
  if (status === "error") return "bad";
  return "neutral";
}

function renderDetailPrivateBounceGuard(profile, guard = {}, automation = {}) {
  if (!profile || profile.name !== "private_jc") return "";
  const tone = privateBounceTone(guard);
  const lastSyncText = guard?.last_sync_utc ? formatGeneratedAt(guard.last_sync_utc) : "Never";
  const cooldownText = guard?.cooldown_until_utc
    ? formatGeneratedAt(guard.cooldown_until_utc)
    : (guard?.cooldown_active ? humanizeCooldownRemaining(guard?.cooldown_remaining_seconds || 0) : "Off");
  const recovery = automation?.private_jc_recovery || {};
  const daily = automation?.private_jc_daily || {};
  const recoveryText = recovery?.active
    ? `${recovery?.target_local_clock || recovery?.target_local_label || "-"}`
    : "Not armed";
  const recoveryCaption = recovery?.active
    ? `${humanizeDurationCompact(recovery?.remaining_seconds || 0)} remaining`
    : (recovery?.note || "No one-shot recovery timer");
  const dailyText = daily?.enabled
    ? `${daily?.local_time || "-"} daily`
    : "Off";
  const dailyCaption = daily?.enabled
    ? `Next ${daily?.next_run_local_label || daily?.next_run_local_clock || "-"}`
    : "Automatic daily start disabled";
  const lastSuppressed = Array.isArray(guard?.last_suppressed_addresses) ? guard.last_suppressed_addresses : [];
  const events = Array.isArray(guard?.events) ? guard.events.slice(0, 3) : [];

  return `
    <section class="detail-section detail-guard-panel detail-guard-panel-${escapeHtml(tone)}">
      <div class="detail-section-head">
        <strong>JC Bounce Guard</strong>
        <span class="mini-pill">${escapeHtml(guard?.status_label || "Idle")}</span>
      </div>
      <p class="detail-guard-note">${escapeHtml(guard?.status_note || "Automatic private bounce sync, suppression, and clustered-bounce cooldown protection.")}</p>

      <div class="detail-guard-grid">
        <article class="detail-guard-stat">
          <div class="detail-guard-label">Last Sync</div>
          <div class="detail-guard-value">${escapeHtml(lastSyncText)}</div>
        </article>
        <article class="detail-guard-stat">
          <div class="detail-guard-label">Suppressed This Sync</div>
          <div class="detail-guard-value">${Number(guard?.last_added_suppressed || 0).toLocaleString()}</div>
        </article>
        <article class="detail-guard-stat">
          <div class="detail-guard-label">Recent Bounce Window</div>
          <div class="detail-guard-value">${Number(guard?.recent_bounces_window || 0)}/${Number(guard?.bounce_threshold || 0)} in ${Number(guard?.window_minutes || 0)}m</div>
        </article>
        <article class="detail-guard-stat">
          <div class="detail-guard-label">Cooldown</div>
          <div class="detail-guard-value">${escapeHtml(cooldownText)}</div>
        </article>
        <article class="detail-guard-stat">
          <div class="detail-guard-label">Recovery Start</div>
          <div class="detail-guard-value">${escapeHtml(recoveryText)}</div>
          <div class="detail-guard-caption">${escapeHtml(recoveryCaption)}</div>
        </article>
        <article class="detail-guard-stat">
          <div class="detail-guard-label">Daily Auto Start</div>
          <div class="detail-guard-value">${escapeHtml(dailyText)}</div>
          <div class="detail-guard-caption">${escapeHtml(dailyCaption)}</div>
        </article>
      </div>

      <div class="detail-guard-stack">
        <div>
          <div class="detail-guard-subhead">Last Suppressed Addresses</div>
          <div class="pill-row">
            ${lastSuppressed.length
              ? lastSuppressed.slice(0, 6).map((email) => `<span class="mini-pill">${escapeHtml(email)}</span>`).join("")
              : `<span class="mini-pill">No new addresses</span>`}
          </div>
        </div>
        <div>
          <div class="detail-guard-subhead">Recent Guard Events</div>
          ${events.length
            ? `
              <div class="detail-guard-events">
                ${events.map((event) => `
                  <article class="detail-guard-event detail-guard-event-${escapeHtml(String(event?.severity || "info"))}">
                    <div class="detail-guard-event-head">
                      <strong>${escapeHtml(event?.title || "Event")}</strong>
                      <span class="muted">${escapeHtml(event?.occurred_at_utc ? formatGeneratedAt(event.occurred_at_utc) : "-")}</span>
                    </div>
                    <p>${escapeHtml(event?.message || "")}</p>
                  </article>
                `).join("")}
              </div>
            `
            : `<p class="muted">No private bounce guard events yet.</p>`}
        </div>
      </div>
    </section>
  `;
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
  const total_awaiting_outcome = Number(summary.total_awaiting_outcome || 0);
  const alerts = Array.isArray(snapshot.alerts) ? snapshot.alerts : [];
  const profiles = Array.isArray(snapshot.profiles) ? snapshot.profiles : [];
  const fleetOrder = ["private_jc", "sendgrid_annette", "sendgrid_jordan", "sendgrid_jodi", "sendgrid_alison", "sendgrid_fiorela"];
  const fleetProfiles = fleetOrder
    .map((name) => profiles.find((profile) => profile.name === name))
    .filter(Boolean);
  const cards = [
    {
      key: "pending_total",
      label: "Pending Total",
      value: Number(summary.total_pending || 0).toLocaleString(),
      note: `Astra ${Number(summary.astra_pending || 0).toLocaleString()} · SendGrid ${Number(summary.sendgrid_pending || 0).toLocaleString()}`,
      tone: Number(summary.total_pending || 0) > 0 ? "warn" : "neutral",
    },
    {
      key: "active_senders",
      label: "Senders",
      value: summary.active_profiles,
      note: `${profiles.length || fleetProfiles.length} profiles · ${fleetProfiles.map((profile) => fleetProfileStatus(profile).label).join(" / ") || "No status"}`,
      tone: Number(summary.active_profiles || 0) > 0 ? "good" : "neutral",
    },
    {
      key: "alerts",
      label: "Critical Alerts",
      value: summary.active_alerts || alerts.length || 0,
      note: Number(summary.active_alerts || alerts.length || 0) > 0
        ? `Needs review · awaiting ${total_awaiting_outcome.toLocaleString()}`
        : "Clear",
      tone: Number(summary.active_alerts || alerts.length || 0) > 0 ? "bad" : "good",
    },
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
        details: node.querySelector(".summary-details-slot"),
        spark: node.querySelector(".summary-spark"),
      };
      return node;
    },
    (node, card) => {
      const refs = node._refs;
      node.className = `summary-card summary-card-${card.tone || "neutral"} summary-card-${card.key || "metric"}`;
      if (refs.spark) refs.spark.className = `summary-spark summary-spark-${card.tone || "neutral"}`;
      setNodeText(refs.label, card.label);
      setNodeText(refs.value, card.value);
      setNodeText(refs.note, card.note);
      refs.value.classList.toggle("summary-value-text", isSummaryTextValue(card.value));
      setNodeHtml(refs.details, card.detailsHtml || renderSummaryDetails(card.details || []));
    },
  );
}

function ensureSenderStatusPanel() {
  if (senderStatusPanel?.isConnected) return senderStatusPanel;
  const anchor = els.summaryGrid?.closest(".queue-health-section") || els.summaryGrid;
  if (!anchor?.parentNode) return null;
  senderStatusPanel = elementFromHTML(`
    <section class="sender-status-panel panel-shell">
      <div class="ops-strip-head sender-status-head">
        <div>
          <p class="eyebrow">Sender Status</p>
          <p class="muted">Current queue, activity, and profile controls</p>
        </div>
      </div>
      <div class="sender-status-table-wrap">
        <table class="sender-status-table">
          <thead>
            <tr>
              <th>Sender</th>
              <th>Status</th>
              <th>Pending</th>
              <th>Accepted</th>
              <th>Awaiting</th>
              <th>Last Activity</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </section>
  `);
  anchor.insertAdjacentElement("afterend", senderStatusPanel);
  return senderStatusPanel;
}

function senderStatusBadge(profile) {
  if (profileTelemetryChannel(profile) === "sendgrid" && profile?.sendgrid_hourly_cap_waiting) {
    return { label: "Waiting · hourly cap", tone: "warn" };
  }
  if (queueSafetyBlockedForProfile(profile)) {
    return { label: "Blocked", tone: "bad" };
  }
  const runtimeState = String(profile?.runtime_state || "").trim();
  if (["running", "starting", "sleeping"].includes(runtimeState)) return { label: "Live", tone: "good" };
  if (["cooldown", "paused"].includes(runtimeState)) return { label: runtimeState === "paused" ? "Paused" : "Cooldown", tone: "warn" };
  if (runtimeState === "stalled") return { label: "Stalled", tone: "warn" };
  if (canStartProfile(profile, lastSnapshot)) return { label: "Ready", tone: "neutral" };
  return { label: "Stopped", tone: "bad" };
}

function renderSenderStatusConsole(snapshot, selectedProfile) {
  const panel = ensureSenderStatusPanel();
  if (!panel) return;
  const tbody = panel.querySelector("tbody");
  const profiles = Array.isArray(snapshot?.profiles) ? snapshot.profiles : [];
  if (!profiles.length) {
    setNodeHtml(tbody, `<tr><td colspan="7" class="sender-status-empty muted">No sender profiles available.</td></tr>`);
    return;
  }
  setNodeHtml(
    tbody,
    profiles.map((profile) => {
      const status = senderStatusBadge(profile);
      const pendingAction = pendingProfileActions.get(profile.name) || "";
      const stopAvailable = canStopProfile(profile);
      const startAvailable = canStartProfile(profile, snapshot);
      const action = stopAvailable ? "stop" : "start";
      const actionLabelText = pendingAction
        ? actionLabel(pendingAction)
        : stopAvailable ? "Stop" : "Start";
      const actionDisabled = Boolean(pendingAction) || (!stopAvailable && !startAvailable);
      const lastActivity = profile.last_timestamp
        ? `${profile.last_timestamp}${profile.last_email ? ` · ${truncateMiddle(profile.last_email, 34)}` : ""}`
        : profileLastAgeText(profile);
      return `
        <tr class="${selectedProfile?.name === profile.name ? "is-selected" : ""}" data-profile="${escapeHtml(profile.name || "")}">
          <td>
            <button class="sender-status-name-btn" type="button" data-profile="${escapeHtml(profile.name || "")}">
              ${escapeHtml(formatProfileName(profile.name))}
            </button>
          </td>
          <td><span class="sender-status-pill sender-status-pill-${escapeHtml(status.tone)}">${escapeHtml(status.label)}</span></td>
          <td>${Number(profile.pending_count || 0).toLocaleString()}</td>
          <td>${Number(profileRunSentDisplay(profile) || 0).toLocaleString()}</td>
          <td>${Number(profile.awaiting_outcome || 0).toLocaleString()}</td>
          <td class="sender-status-activity" title="${escapeHtml(profile.last_email || profile.last_timestamp || "")}">${escapeHtml(lastActivity)}</td>
          <td>
            <button
              class="btn ${action === "stop" ? "btn-danger" : "btn-secondary"} btn-sm sender-status-action-btn"
              type="button"
              data-profile="${escapeHtml(profile.name || "")}"
              data-action="${escapeHtml(action)}"
              ${actionDisabled ? "disabled" : ""}
            >${escapeHtml(actionLabelText)}</button>
          </td>
        </tr>
      `;
    }).join(""),
  );
}

function createAlertCardNode() {
  const node = elementFromHTML(`
    <article class="alert-card alert-card-compact alert-row alert-warn">
      <div class="alert-row-state">
        <span class="alert-pill"></span>
      </div>
      <div class="alert-row-body">
        <div class="alert-row-main">
          <h3></h3>
          <p class="alert-message"></p>
        </div>
      </div>
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
  const blocksSending = Boolean(alert?.blocks_sending);
  const alertProfile = String(alert?.profile || alert?.profile_name || "").trim();
  const alertMessage = String(alert?.message || "").trim();
  const messageWithProfile = alertProfile
    ? `${alertMessage}${alertMessage ? " " : ""}Profile: ${formatProfileName(alertProfile)}.`
    : alertMessage;
  node.className = `alert-card alert-card-compact alert-row alert-${severity}`;
  refs.pill.className = `alert-pill alert-pill-${severity}`;
  setNodeText(
    refs.pill,
    severity === "ok"
      ? "Healthy"
      : blocksSending
        ? "Blocks Start"
        : "Non-blocking",
  );
  setNodeText(refs.title, alert?.title || "Alert");
  setNodeText(refs.message, messageWithProfile);
}

function summarizeAlertProgress(snapshot) {
  const totals = {
    sendgrid: { key: "sendgrid", label: "SendGrid", sent: 0, active: 0, cap: 0, hourly: snapshot?.sendgrid_hourly_cap || null },
    private: { key: "private", label: "Private Email", sent: 0, active: 0, cap: 0 },
  };

  const activeStates = new Set(["running", "starting", "sleeping", "cooldown", "paused"]);
  const profiles = Array.isArray(snapshot?.profiles) ? snapshot.profiles : [];

  profiles.forEach((profile) => {
    const channel = profileTelemetryChannel(profile);
    if (!totals[channel]) return;

    totals[channel].sent += profileRunSentDisplay(profile);
    totals[channel].cap += Number(profile?.max_total || 0);

    if (activeStates.has(String(profile?.runtime_state || ""))) {
      totals[channel].active += 1;
    }
  });

  return Object.values(totals);
}

function renderAlertsProgress(snapshot) {
  if (!els.alertsProgress) return;
  const items = summarizeAlertProgress(snapshot);
  const windowLabel = `${Number(snapshot?.activity_hours || 24)}h window`;
  const controls = snapshot?.controls || {};
  const automation = snapshot?.automation || {};
  const sendTarget = Number(controls.send_target_total || controls.send_cap_total || controls.send_cap_per_profile || 0);
  const availableSenders = Number(controls.available_sendgrid_sender_count || controls.available_sender_count || 0);
  const targetWindowHours = Number(controls.send_target_window_hours || 18);
  const perProfileTarget = Number(controls.send_target_per_profile || 0)
    || Math.ceil(sendTarget / Math.max(1, availableSenders || 5));
  const sendgridDailyTime = automation?.sendgrid_daily?.enabled
    ? automation.sendgrid_daily.local_time
    : null;
  const renderSendGridMeta = (item) => {
    if (item.key !== "sendgrid") return "";
    return `
      <span class="alerts-progress-meta alerts-progress-plan">Target window: ${Number(sendTarget || 0).toLocaleString()} emails · 6 PM to 12 PM (${Number(targetWindowHours || 18)}h)</span>
      <span class="alerts-progress-meta alerts-progress-plan">Per-profile plan: ~${Number(perProfileTarget || 0).toLocaleString()} across ${Number(availableSenders || 0).toLocaleString()} SG</span>
      <span class="alerts-progress-meta alerts-progress-plan">Daily cap: ${sendgridDailyTime ? `SG ${escapeHtml(sendgridDailyTime)}` : "manual"}</span>
    `;
  };
  setNodeHtml(
    els.alertsProgress,
    `
      <div class="alerts-progress-list">
        ${items.map((item) => `
          <article class="alerts-progress-item alerts-progress-row alerts-progress-item-${item.key} ${item.active > 0 ? "is-running" : "is-stopped"}">
            <div class="alerts-progress-main">
              <div class="alerts-progress-label-row">
                <span class="alerts-progress-dot"></span>
                <span class="alerts-progress-label">${escapeHtml(item.label)}</span>
              </div>
              <div class="alerts-progress-value-row">
                <span class="alerts-progress-value">${Number(item.sent || 0).toLocaleString()}</span>
                <span class="alerts-progress-unit muted">sent</span>
              </div>
            </div>
            <span class="alerts-progress-state alerts-progress-state-${item.active > 0 ? "running" : "stopped"}">
              ${item.active > 0 ? "RUNNING" : "STOPPED"} · ${Number(item.active || 0).toLocaleString()} active
            </span>
            ${item.key === "sendgrid" ? renderSendGridMeta(item) : `
              <span class="alerts-progress-meta muted">${item.cap ? `Cap ${Number(item.cap).toLocaleString()}` : "Cap ∞"} · ${escapeHtml(windowLabel)}</span>
            `}
          </article>
        `).join("")}
      </div>
    `,
  );
}

function renderAlerts(snapshot) {
  if (!els.alertsGrid) return;
  const activeAlerts = Array.isArray(snapshot.alerts) ? snapshot.alerts : [];
  const visibleAlerts = activeAlerts.slice(0, 2);
  const hiddenAlertCount = Math.max(0, activeAlerts.length - visibleAlerts.length);
  const cards = activeAlerts.length
    ? [
        ...visibleAlerts,
        ...(hiddenAlertCount > 0
          ? [{
              key: "alerts-overflow",
              severity: "ok",
              title: "More alerts",
              message: `+${hiddenAlertCount} more alert${hiddenAlertCount === 1 ? "" : "s"}`,
            }]
          : []),
      ]
    : [{ key: "ok", severity: "ok", title: "Thresholds clear", message: "Current metrics are below configured limits." }];
  syncKeyedChildren(
    els.alertsGrid,
    cards,
    (alert, index) => alert.key || `${alert.severity}-${alert.title || index}`,
    () => createAlertCardNode(),
    (node, alert) => updateAlertCardNode(node, alert),
  );
  if (els.alertsCaption) {
    const blockingCount = activeAlerts.filter((alert) => Boolean(alert?.blocks_sending)).length;
    const nonBlockingCount = Math.max(0, activeAlerts.length - blockingCount);
    setNodeText(
      els.alertsCaption,
      activeAlerts.length
        ? `${activeAlerts.length} active now · ${blockingCount} blocking · ${nonBlockingCount} non-blocking`
        : "All thresholds clear",
    );
  }
  renderAlertsProgress(snapshot);
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
  const sendgridSafety = snapshot?.sendgrid_queue_safety || {};
  const privateSafety = snapshot?.private_queue_safety || {};
  const providerSplit = sendgridReadyPrivateBlocked(snapshot);
  const state = providerSplit ? "yellow" : (snapshot.health?.state || "yellow");
  const message = providerSplit
    ? "SendGrid ready; Private JC blocked."
    : (snapshot.health?.message || "No status available.");
  els.healthBanner.className = `health-banner health-${state}`;
  els.healthBanner.textContent = message;
}

function sendgridReadyPrivateBlocked(snapshot = lastSnapshot) {
  const sendgridSafety = snapshot?.sendgrid_queue_safety || {};
  const privateSafety = snapshot?.private_queue_safety || {};
  return sendgridSafety.safe === true && privateSafety.safe === false;
}

const SENDGRID_METRIC_DISCLAIMER_COPY = "SendGrid delivery status only. Delivered means accepted by the recipient server, not confirmed inbox placement. Non-bounced emails may still land in spam or be filtered. Astra/private JC sends are tracked separately and are not included in SendGrid totals.";

function sendgridBounceRateFromSummary(summary = {}) {
  const bounced = Number(summary.bounce || 0);
  const processed = Number(summary.processed || 0);
  if (!Number.isFinite(bounced) || !Number.isFinite(processed) || processed <= 0) return null;
  return bounced / processed;
}

function sendgridBounceRateAlert(summary = {}) {
  const bounceRate = sendgridBounceRateFromSummary(summary);
  if (bounceRate == null) return null;
  if (bounceRate > 0.25) {
    return {
      tone: "bad",
      message: "SendGrid dispatch unsafe. Bounce rate is critically high.",
    };
  }
  if (bounceRate > 0.10) {
    return {
      tone: "warn",
      message: "High SendGrid bounce rate detected. Pause SendGrid dispatch until recipient queues are cleaned.",
    };
  }
  return null;
}

function renderSendGridMetricDisclaimer(summary = {}) {
  const alert = sendgridBounceRateAlert(summary);
  return `
    <div class="sendgrid-metric-disclaimer ${alert ? `sendgrid-metric-disclaimer-${escapeHtml(alert.tone)}` : ""}">
      <span>${SENDGRID_METRIC_DISCLAIMER_COPY}</span>
      ${alert ? `<strong class="sendgrid-metric-disclaimer-alert">${escapeHtml(alert.message)}</strong>` : ""}
    </div>
  `;
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
  if ((profile.health_tone || "") === "bad" || (summary.failed || 0) > 0) return "bad";
  if ((profile.health_label || "") === "Healthy" && ["starting", "running", "cooldown", "sleeping"].includes(profile.runtime_state || "")) return "good";
  return "idle";
}

function overviewGlowState(profile) {
  return ["starting", "running", "cooldown", "sleeping"].includes(profile?.runtime_state || "")
    ? "running"
    : "stopped";
}

function profileActivityState(profile) {
  const runtimeState = String(profile?.runtime_state || "").trim();
  if (["starting", "running", "cooldown", "sleeping"].includes(runtimeState)) {
    return { label: "Running", tone: "good" };
  }
  if (runtimeState === "paused") {
    return { label: "Paused", tone: "paused" };
  }
  if (runtimeState === "stalled") {
    return { label: "Stalled", tone: "warn" };
  }
  return { label: "Stopped", tone: "bad" };
}

function overviewStateIndicator(profile) {
  const runtimeState = String(profile?.runtime_state || "").trim();
  if (["running", "starting", "sleeping"].includes(runtimeState)) {
    return { label: "Live", tone: "good" };
  }
  if (["cooldown", "paused"].includes(runtimeState)) {
    return { label: runtimeState === "paused" ? "Paused" : "Cooldown", tone: "warn" };
  }
  if (runtimeState === "stalled") {
    return { label: "Stalled", tone: "warn" };
  }
  return { label: "Stopped", tone: "bad" };
}

function messageReadinessTone(status) {
  const normalized = String(status || "").trim().toUpperCase().replace(/\s+/g, "-");
  if (normalized === "PASS") return "pass";
  if (normalized === "FAIL") return "fail";
  if (normalized === "STALE") return "stale";
  return "not-run";
}

function yesNo(value) {
  return value ? "Yes" : "No";
}

function formatReadinessTime(value) {
  return value ? formatGeneratedAt(value) : "-";
}

function renderMessageReadiness(profile) {
  const readiness = profile?.message_readiness || {};
  const profileName = String(profile?.name || "");
  const previewState = profilePreviewValidationState.get(profileName) || {};
  const previewRunning = previewState.kind === "loading";
  const blockedByQueueSafety = queueSafetyBlockedForProfile(profile);
  const actionDisabled = previewRunning || isProfileActive(profile) || blockedByQueueSafety;
  const actionTitle = previewRunning
    ? "Preview + validation is running."
    : isProfileActive(profile)
      ? "Stop this sender before generating a preview."
      : blockedByQueueSafety
        ? queueSafetyBlockMessageForProfile(profile)
        : "Render the current queue without sending, then validate the preview.";
  const status = String(readiness.status || "NOT RUN").trim().toUpperCase() || "NOT RUN";
  const tone = messageReadinessTone(status);
  const items = [
    ["Rows", Number(readiness.recipient_row_count || 0).toLocaleString()],
    ["BookTitle column", yesNo(readiness.book_title_column_present)],
    ["BookTitle rows", Number(readiness.rows_with_book_title || 0).toLocaleString()],
    ["Fallback rows", Number(readiness.fallback_row_count || 0).toLocaleString()],
    ["Invalid emails", Number(readiness.invalid_email_count || 0).toLocaleString()],
    ["Duplicate emails", Number(readiness.duplicate_email_count || 0).toLocaleString()],
    ["Preview CSV", yesNo(readiness.preview_csv_exists)],
    ["Validation", readiness.preview_validation_status || "NOT RUN"],
    ["Preview time", formatReadinessTime(readiness.last_preview_generated_utc)],
    ["Validation time", formatReadinessTime(readiness.last_validation_time_utc)],
    ["Expected mode", readiness.pitch_mode_expected || "-"],
    ["Actual mode", readiness.actual_profile_mode || "-"],
  ];
  const reasons = Array.isArray(readiness.reasons) ? readiness.reasons.filter(Boolean).slice(0, 2) : [];
  return `
    <section class="message-readiness message-readiness-${escapeHtml(tone)}">
      <div class="message-readiness-head">
        <span>Message Readiness</span>
        <strong>${escapeHtml(status)}</strong>
      </div>
      <div class="message-readiness-actions">
        <button
          class="btn btn-secondary btn-sm preview-validate-profile-btn"
          type="button"
          data-profile="${escapeHtml(profileName)}"
          ${actionDisabled ? "disabled" : ""}
          title="${escapeHtml(actionTitle)}"
        >${escapeHtml(previewRunning ? "Running..." : "Run Preview + Validate")}</button>
      </div>
      <div class="message-readiness-grid">
        ${items.map(([label, value]) => `
          <div class="message-readiness-item">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
          </div>
        `).join("")}
      </div>
      ${previewState.message ? `<p class="message-readiness-feedback message-readiness-feedback-${escapeHtml(previewState.kind || "info")}">${escapeHtml(previewState.message)}</p>` : ""}
      ${reasons.length ? `<p class="message-readiness-reason">${escapeHtml(reasons.join(" "))}</p>` : ""}
    </section>
  `;
}

function createOverviewCardNode() {
  const node = elementFromHTML(`
    <article class="overview-card overview-row overview-idle" data-profile="">
      <div class="overview-row-main">
        <div class="overview-name-row">
          <div class="overview-title-block">
            <h3></h3>
            <span class="overview-warning-text muted"></span>
          </div>
          <span class="overview-state-line">
            <span class="overview-state-dot overview-state-dot-neutral"></span>
            <span class="overview-state-text"></span>
          </span>
          <span class="overview-badges">
            <span class="overview-badge overview-provider-badge hidden"></span>
            <span class="overview-badge overview-cooldown-badge hidden"></span>
          </span>
        </div>
      </div>
      <div class="overview-metrics overview-stats"></div>
      <div class="overview-message-readiness"></div>
    </article>
  `);
  node._refs = {
    title: node.querySelector("h3"),
    stateLine: node.querySelector(".overview-state-line"),
    stateDot: node.querySelector(".overview-state-dot"),
    stateText: node.querySelector(".overview-state-text"),
    stats: node.querySelector(".overview-stats"),
    messageReadiness: node.querySelector(".overview-message-readiness"),
    warningText: node.querySelector(".overview-warning-text"),
    providerBadge: node.querySelector(".overview-provider-badge"),
    cooldownBadge: node.querySelector(".overview-cooldown-badge"),
  };
  return node;
}

function strongestProfileWarning(profile) {
  const failed = Number(profile?.webhook?.summary?.failed || 0);
  const awaiting = Number(profile?.awaiting_outcome || 0);
  const errors = Number(profile?.run_errors || 0);
  const pending = Number(profile?.pending_count || 0);
  const reasonCode = String(profile?.reason_code || "").trim() || "READY";
  const reasonNote = String(profile?.reason_note || profile?.health_note || "").trim() || "No dominant sender issue is active right now.";
  const healthLabel = String(profile?.health_label || "").trim() || "Healthy";
  const healthTone = String(profile?.health_tone || "").trim() || "neutral";
  const readiness = String(profile?.readiness_label || "").trim() || "Ready";
  const telemetry = String(profile?.telemetry_quality_label || "").trim();
  if (profile?.tmux_dead || (profile?.runtime_state || "") === "error") {
    return { tone: "bad", label: reasonCode, message: reasonNote || profile?.runtime_note || "Sender process is not healthy." };
  }
  if (failed > 0) {
    return { tone: "bad", label: "Failures", message: `${failed} delivery failure${failed === 1 ? "" : "s"} in the selected window.` };
  }
  if (healthLabel !== "Healthy" || readiness !== "Ready") {
    const extra = [];
    if (readiness && readiness !== "Ready") extra.push(readiness);
    if (telemetry && (readiness === "Telemetry Degraded" || healthLabel === "Watch")) extra.push(`Confidence ${telemetry}`);
    return {
      tone: healthTone === "bad" ? "bad" : healthTone === "warn" || healthTone === "paused" ? "warn" : "neutral",
      label: reasonCode,
      message: `${reasonNote}${extra.length ? ` (${extra.join(" • ")})` : ""}`,
    };
  }
  if (pending > 0 && !isProfileActive(profile)) {
    return { tone: "neutral", label: "Ready", message: `${pending} queued recipient${pending === 1 ? "" : "s"} ready when this sender starts.` };
  }
  if (awaiting > 0) {
    return { tone: "warn", label: "Awaiting", message: `${awaiting} accepted recipient${awaiting === 1 ? "" : "s"} still awaiting final outcome.` };
  }
  if (errors > 0) {
    return { tone: "neutral", label: reasonCode, message: reasonNote };
  }
  return { tone: "neutral", label: "Clear", message: "No immediate warning on this sender." };
}

function updateOverviewCardNode(node, profile, selectedProfile) {
  const refs = node._refs || {
    title: node.querySelector("h3"),
    stateLine: node.querySelector(".overview-state-line"),
    stateDot: node.querySelector(".overview-state-dot"),
    stateText: node.querySelector(".overview-state-text"),
    stats: node.querySelector(".overview-stats"),
    warningText: node.querySelector(".overview-warning-text"),
  };
  node._refs = refs;
  const tone = overviewTone(profile);
  const isSelected = selectedProfile && selectedProfile.name === profile.name;
  const warning = strongestProfileWarning(profile);
  const stateIndicator = overviewStateIndicator(profile);
  const stats = [
    { key: "pending", label: "Pending", value: Number(profile.pending_count || 0).toLocaleString() },
    { key: "accepted", label: "Accepted", value: profileRunSentDisplay(profile).toLocaleString() },
  ];

  node.dataset.profile = profile.name || "";
  const runtimeClass = stateIndicator.tone === "good" ? "overview-runtime-running" : stateIndicator.tone === "bad" ? "overview-runtime-stopped" : "overview-runtime-paused";
  node.className = `overview-card overview-${tone} ${runtimeClass}${isSelected ? " is-selected" : ""}`;
  setNodeText(refs.title, formatProfileName(profile.name));
  refs.stateLine.className = `overview-state-line overview-state-line-${stateIndicator.tone || "neutral"}`;
  refs.stateDot.className = `overview-state-dot overview-state-dot-${stateIndicator.tone || "neutral"}`;
  setNodeText(refs.stateText, stateIndicator.label || "Stopped");

  // Cooldown / provider badges (compact)
  try {
    const profileRemaining = Number(profile?.cooldown_remaining_seconds || 0);
    const providerRemaining = Number(profile?.provider_cooldown_remaining_seconds || 0);
    // store numeric values on refs for the live ticker to use
    if (refs.cooldownBadge) refs.cooldownBadge._remaining = profileRemaining;
    if (refs.providerBadge) refs.providerBadge._remaining = providerRemaining;

    if (refs.providerBadge) {
      if (providerRemaining > 0) {
        refs.providerBadge.classList.remove("hidden");
        refs.providerBadge.textContent = `P: ${humanizeCooldownRemaining(providerRemaining)}`;
        refs.providerBadge.title = `Provider cooldown: ${providerRemaining}s remaining`;
      } else {
        refs.providerBadge.classList.add("hidden");
        refs.providerBadge.textContent = "";
        refs.providerBadge.title = "";
      }
    }

    if (refs.cooldownBadge) {
      const cooldownDisplay = profileCooldownDisplay(profile, { compact: true });
      refs.cooldownBadge._remaining = typeof cooldownDisplay.countdown === "number" ? cooldownDisplay.countdown : null;
      if (cooldownDisplay.active) {
        refs.cooldownBadge.classList.remove("hidden");
        refs.cooldownBadge.textContent = `C: ${cooldownDisplay.text}`;
        refs.cooldownBadge.title = cooldownDisplay.title;
      } else {
        refs.cooldownBadge.classList.add("hidden");
        refs.cooldownBadge.textContent = "";
        refs.cooldownBadge.title = "";
      }
    }
  } catch (e) {
    // non-fatal: protect overview rendering
    console.error("Error updating cooldown badges", e);
  }

  syncKeyedChildren(
    refs.stats,
    stats,
    (stat) => stat.key,
    () => createOverviewStatNode(),
    (statNode, stat) => updateOverviewStatNode(statNode, stat.label, stat.value),
  );
  setNodeHtml(refs.messageReadiness, renderMessageReadiness(profile));
  const warningText = warning.tone === "neutral"
    ? String(profile.health_note || profile.reason_note || "").trim()
    : `${warning.label || "Watch"}: ${warning.message || ""}`;
  setNodeText(refs.warningText, warningText || "No immediate warning.");
  refs.warningText.classList.toggle("muted", warning.tone === "neutral");
  refs.warningText.classList.toggle("overview-warning-inline-bad", warning.tone === "bad");
  refs.warningText.classList.toggle("overview-warning-inline-warn", warning.tone === "warn");
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

function campaignHistoryEventLabel(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function campaignHistoryReason(record) {
  const reasons = Array.isArray(record?.blocked_reasons) ? record.blocked_reasons.filter(Boolean) : [];
  if (reasons.length) return String(reasons[0]);
  if (record?.validation_status) return String(record.validation_status);
  if (record?.queue_safety_status) return `Queue ${record.queue_safety_status}`;
  return "-";
}

function renderCampaignRunHistory(snapshot) {
  if (!els.campaignRunHistory) return;
  const records = Array.isArray(snapshot?.campaign_run_history) ? snapshot.campaign_run_history.slice(0, 25) : [];
  if (!records.length) {
    setNodeHtml(els.campaignRunHistory, `<p class="muted">No campaign run history yet.</p>`);
    return;
  }
  setNodeHtml(
    els.campaignRunHistory,
    `
      <div class="table-shell campaign-history-table">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Event</th>
              <th>Profile</th>
              <th>Readiness</th>
              <th>Validation</th>
              <th>Rows</th>
              <th>Sent</th>
              <th>Result / Reason</th>
            </tr>
          </thead>
          <tbody>
            ${records.map((record) => `
              <tr>
                <td>${escapeHtml(formatReadinessTime(record.timestamp))}</td>
                <td>${escapeHtml(campaignHistoryEventLabel(record.event_type))}</td>
                <td>${escapeHtml(record.profile || "-")}</td>
                <td>${escapeHtml(record.message_readiness_status || "-")}</td>
                <td>${escapeHtml(record.validation_status || "-")}</td>
                <td>${Number(record.recipient_row_count || 0).toLocaleString()}</td>
                <td>${Number(record.sent_count || 0).toLocaleString()}</td>
                <td>${escapeHtml(campaignHistoryReason(record))}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `,
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

// Live ticker for overview cooldown/provider badges
let _cooldownBadgeTickerId = null;
function startCooldownBadgeTicker() {
  if (_cooldownBadgeTickerId) return;
  _cooldownBadgeTickerId = setInterval(() => {
    try {
      if (!els.overviewGrid) return;
      for (const card of Array.from(els.overviewGrid.children || [])) {
        const refs = card._refs || {};
        // provider badge
        if (refs.providerBadge && typeof refs.providerBadge._remaining === "number") {
          if (refs.providerBadge._remaining > 0) {
            refs.providerBadge._remaining = Math.max(0, refs.providerBadge._remaining - 1);
            refs.providerBadge.textContent = `P: ${humanizeCooldownRemaining(refs.providerBadge._remaining)}`;
            refs.providerBadge.title = `Provider cooldown: ${refs.providerBadge._remaining}s remaining`;
            refs.providerBadge.classList.remove("hidden");
          } else {
            refs.providerBadge.classList.add("hidden");
          }
        }
        // profile cooldown badge
        if (refs.cooldownBadge && typeof refs.cooldownBadge._remaining === "number") {
          if (refs.cooldownBadge._remaining > 0) {
            refs.cooldownBadge._remaining = Math.max(0, refs.cooldownBadge._remaining - 1);
            refs.cooldownBadge.textContent = `C: ${humanizeCooldownRemaining(refs.cooldownBadge._remaining)}`;
            refs.cooldownBadge.title = `Cooldown: ${refs.cooldownBadge._remaining}s remaining`;
            refs.cooldownBadge.classList.remove("hidden");
          } else {
            refs.cooldownBadge.classList.add("hidden");
          }
        }
      }
    } catch (e) {
      console.error("Cooldown badge ticker error", e);
    }
  }, 1000);
}

// Start the ticker immediately so badges feel live between snapshots
startCooldownBadgeTicker();

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

function queueSafetyBlocked(snapshot = lastSnapshot) {
  const queueSafety = snapshot?.queue_safety || {};
  return queueSafety && queueSafety.safe === false;
}

function queueSafetyBlockMessage(snapshot = lastSnapshot) {
  const queueSafety = snapshot?.queue_safety || {};
  return String(queueSafety.message || "Recipient queue unsafe. Rebuild queues from the current campaign source before starting.").trim();
}

function providerQueueSafetyForProfile(profile, snapshot = lastSnapshot) {
  const channel = profileTelemetryChannel(profile);
  if (channel === "sendgrid") return snapshot?.sendgrid_queue_safety || {};
  if (channel === "private") return snapshot?.private_queue_safety || {};
  return snapshot?.queue_safety || {};
}

function queueSafetyBlockedForProfile(profile, snapshot = lastSnapshot) {
  const queueSafety = providerQueueSafetyForProfile(profile, snapshot);
  return queueSafety && queueSafety.safe === false;
}

function queueSafetyBlockMessageForProfile(profile, snapshot = lastSnapshot) {
  const queueSafety = providerQueueSafetyForProfile(profile, snapshot);
  return String(queueSafety.message || "Recipient queue unsafe. Rebuild this provider queue from the current campaign source before starting.").trim();
}

function canStartProfile(profile, snapshot = lastSnapshot) {
  return !queueSafetyBlockedForProfile(profile, snapshot) && !isProfileActive(profile) && !Boolean(profile?.restart_blocked);
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

function renderPrivateJcQueueRepair(profile, snapshot = lastSnapshot) {
  if (!profile || profile.name !== "private_jc") return "";
  const queueSafety = snapshot?.private_queue_safety || {};
  if (queueSafety.safe !== false) return "";
  const summary = privateJcQueueRepairState.summary || {};
  const feedback = privateJcQueueRepairState.message
    ? `<div class="private-jc-repair-feedback private-jc-repair-feedback-${escapeHtml(privateJcQueueRepairState.kind || "info")}">${escapeHtml(privateJcQueueRepairState.message)}</div>`
    : "";
  const summaryRows = privateJcQueueRepairState.summary ? `
    <div class="private-jc-repair-summary">
      <span>Unsafe rows archived <strong>${Number(summary.unsafe_queue_rows_archived || 0).toLocaleString()}</strong></span>
      <span>Reject-overlap rows removed <strong>${Number(summary.reject_overlap_rows_removed || 0).toLocaleString()}</strong></span>
      <span>Outside-source rows removed <strong>${Number(summary.outside_source_rows_removed || 0).toLocaleString()}</strong></span>
      <span>Rebuilt queue rows <strong>${Number(summary.rebuilt_queue_rows || 0).toLocaleString()}</strong></span>
      <span class="private-jc-repair-backup" title="${escapeHtml(summary.backup_path || "")}">Backup <strong>${escapeHtml(truncateMiddle(summary.backup_path || "-", 72))}</strong></span>
    </div>
  ` : "";
  const active = isProfileActive(profile);
  const loading = privateJcQueueRepairState.kind === "loading";
  const reasonBits = [
    Number(queueSafety.overlap_with_triaged_reject || 0) ? `${Number(queueSafety.overlap_with_triaged_reject || 0).toLocaleString()} reject overlap` : "",
    Number(queueSafety.outside_intended_source_count || 0) ? `${Number(queueSafety.outside_intended_source_count || 0).toLocaleString()} outside approved source` : "",
    Number(queueSafety.outside_checked_output_count || 0) ? `${Number(queueSafety.outside_checked_output_count || 0).toLocaleString()} outside checked output` : "",
  ].filter(Boolean);
  return `
    <section class="private-jc-repair-panel">
      <div class="private-jc-repair-head">
        <div>
          <strong>Repair Private JC Queue</strong>
          <p>Private JC queue is blocked because the live queue contains recipients that overlap rejected leads or are outside the current approved source.</p>
          ${reasonBits.length ? `<p class="muted">${escapeHtml(reasonBits.join(" · "))}</p>` : ""}
        </div>
        <button
          class="btn btn-secondary btn-sm repair-private-jc-queue-btn"
          type="button"
          ${active || loading ? "disabled" : ""}
          title="${escapeHtml(active ? "Stop Private JC before repairing its queue." : "Archive the unsafe JC queue and rebuild from the latest confirmed dispatch preview.")}"
        >${escapeHtml(loading ? "Repairing..." : "Repair Private JC Queue")}</button>
      </div>
      <p class="private-jc-repair-note">Repair archives the current JC queue, clears the unsafe live file, and rebuilds JC recipients only from the current approved dispatch source. It does not start JC.</p>
      ${feedback}
      ${summaryRows}
    </section>
  `;
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
  const automation = snapshot.automation || {};
  const sendTarget = Number(controls.send_target_total || controls.send_cap_total || controls.send_cap_per_profile || 0);
  const profiles = Array.isArray(snapshot.profiles) ? snapshot.profiles : [];
  const hasActiveSender = profiles.some((profile) => isProfileActive(profile))
    || Number(controls.active_sendgrid_sender_count || 0) > 0
    || Number(controls.active_profile_count || controls.active_profiles || 0) > 0;
  const blockedByQueueSafety = queueSafetyBlocked(snapshot);
  const splitQueueSafety = sendgridReadyPrivateBlocked(snapshot);
  const queueSafetyMessage = splitQueueSafety
    ? "SendGrid ready; Private JC blocked."
    : queueSafetyBlockMessage(snapshot);
  if (els.sendCapInput && document.activeElement !== els.sendCapInput && sendTarget > 0) {
    els.sendCapInput.value = String(sendTarget);
  }
  if (els.startBtn) {
    els.startBtn.disabled = hasActiveSender || blockedByQueueSafety;
    els.startBtn.classList.toggle("btn-start-muted", hasActiveSender || blockedByQueueSafety);
    els.startBtn.title = blockedByQueueSafety
      ? queueSafetyMessage
      : hasActiveSender
      ? "Some senders are already running. Use per-sender controls or Stop All first."
      : "Start all available senders.";
    els.startBtn.setAttribute("aria-describedby", (hasActiveSender || blockedByQueueSafety) ? "send-cap-note" : "");
  }
  if (els.stopBtn) {
    els.stopBtn.classList.toggle("btn-danger-active", hasActiveSender);
  }
  if (els.sendCapNote) {
    const lines = [];
    if (hasActiveSender) {
      lines.push("Some senders are already running. Use per-sender controls or Stop All first.");
    }
    if (blockedByQueueSafety) {
      lines.push(queueSafetyMessage);
    }
    const scheduleBits = [];
    if (automation?.private_jc_daily?.enabled) {
      scheduleBits.push(`JC daily ${automation.private_jc_daily.local_time}`);
    }
    if (automation?.private_jc_recovery?.active) {
      scheduleBits.push(`JC recovery ${automation.private_jc_recovery.target_local_clock} (${humanizeDurationCompact(automation.private_jc_recovery.remaining_seconds || 0)})`);
    }
    if (scheduleBits.length) {
      lines.push(scheduleBits.join(" | "));
    }
    if (!lines.length) {
      lines.push("Choose a send target, then Start All.");
    }
    setNodeHtml(
      els.sendCapNote,
      lines.map((line, index) => `
        <span class="toolbar-note-line${index ? " toolbar-note-line-secondary" : ""}">${escapeHtml(line)}</span>
      `).join(""),
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
  renderSenderStatusConsole(lastSnapshot, selected);
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
  if (["starting", "running", "cooldown", "sleeping", "finished", "scheduled-stop", "paused", "stalled", "error", "dead"].includes(state)) {
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

function profileTelemetryChannel(profile) {
  const name = String(profile?.name || "").toLowerCase();
  const csv = String(profile?.csv_path || "").toLowerCase();
  const log = String(profile?.log_path || "").toLowerCase();
  if (name.startsWith("sendgrid_") || csv.includes("sendgrid") || log.includes("sendgrid")) return "sendgrid";
  if (name.startsWith("private_") || csv.includes("private") || log.includes("private")) return "private";
  if (name.startsWith("gmail_") || csv.includes("gmail") || log.includes("gmail")) return "gmail";
  return "other";
}

function renderDiagnosticRows(items = []) {
  return `
    <div class="diagnostic-row-list">
      ${items.map((item) => `
        <div class="diagnostic-row">
          <span class="diagnostic-key">${escapeHtml(item.label || "-")}</span>
          <span class="diagnostic-value"${item.title ? ` title="${escapeHtml(item.title)}"` : ""}>${escapeHtml(item.value ?? "-")}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function renderDetailPrimaryWarning(profile) {
  const warning = strongestProfileWarning(profile);
  if (!warning || warning.tone === "neutral") return "";
  return `
    <div class="detail-primary-warning detail-primary-warning-${escapeHtml(warning.tone || "warn")}">
      <span class="detail-primary-warning-label">${escapeHtml(warning.label || "Warning")}</span>
      <span>${escapeHtml(warning.message || "")}</span>
    </div>
  `;
}

function renderLiveDelivery(profile, hours) {
  const channel = profileTelemetryChannel(profile);
  if (channel !== "sendgrid") {
    const cooldownSeconds = Number(profile.cooldown_remaining_seconds || 0);
    const headLabel = channel === "private" ? "Private Mailbox" : "Sender Mailbox";
    const headNote = channel === "private"
      ? "SMTP delivery plus mailbox bounce handling for this sender"
      : "Direct sender telemetry for this mailbox";
    const lastActivityValue = profile.last_timestamp
      ? `${profile.last_timestamp}${profile.last_email ? ` • ${truncateMiddle(profile.last_email, 52)}` : ""}`
      : "No recent sender log activity";
    const rows = [
      { label: "Sent Today", value: Number(profile.sent_today || 0).toLocaleString() },
      { label: "Errors Today", value: Number(profile.errors_today || 0).toLocaleString() },
      { label: "Skipped Today", value: Number(profile.skipped_today || 0).toLocaleString() },
      { label: "Cooldown", value: cooldownSeconds > 0 ? humanizeCooldownRemaining(cooldownSeconds) : "Ready" },
      { label: "Last Status", value: senderLogStatusLabel(profile.last_status || "-") },
      { label: "Last Recipient", value: truncateMiddle(profile.last_email || "-", 52), title: String(profile.last_email || "-") },
      { label: "Last Activity", value: lastActivityValue, title: `${profile.last_timestamp || ""} ${profile.last_email || ""}`.trim() },
    ];
    return `
      <section class="live-delivery detail-inspector-section">
        <div class="live-delivery-head">
          <strong>${headLabel}</strong>
          <span class="muted">${headNote}</span>
        </div>
        ${renderDiagnosticRows(rows)}
        <div class="live-delivery-note">
          <span>No SendGrid webhook telemetry for this sender.</span>
          <span>Delivery feedback comes from SMTP responses, sender logs, and mailbox bounce handling.</span>
        </div>
      </section>
    `;
  }

  const webhook = profile.webhook || { summary: {}, latest_event: {}, total: 0 };
  const summary = webhook.summary || {};
  const latest = webhook.latest_event || {};
  const mapped24h = Number(webhook.mapped_events_24h || webhook.total || 0);
  const unmapped24h = Number(webhook.unmapped_events_24h || 0);
  const lastWebhookText = webhook.last_received_at || (webhook.last_received_iso ? formatGeneratedAt(webhook.last_received_iso) : "No webhook yet");
  const latestText = latest.time
    ? `${statusLabel(latest.status)} at ${formatGeneratedAt(latest.time)}${latest.email ? ` • ${truncateMiddle(latest.email, 40)}` : ""}`
    : `No mapped webhook events in the last ${hours}h`;
  const rows = [
    { label: `Mapped ${hours}h`, value: mapped24h },
    { label: `Unmapped ${hours}h`, value: unmapped24h },
    { label: "Processed", value: summary.processed || 0 },
    { label: "Delivered", value: summary.delivered || 0 },
    { label: "Deferred", value: summary.deferred || 0 },
    { label: "Bounced", value: summary.bounce || 0 },
    { label: "Dropped", value: summary.dropped || 0 },
    { label: "Awaiting", value: profile.awaiting_outcome || 0 },
    { label: "Last Webhook", value: lastWebhookText },
    { label: "Latest Event", value: latestText, title: latest.email || "" },
  ];
  const failureBits = [];
  if (summary.bounce) failureBits.push(`Bounced ${summary.bounce}`);
  if (summary.blocked) failureBits.push(`Blocked ${summary.blocked}`);
  if (summary.dropped) failureBits.push(`Dropped ${summary.dropped}`);
  if (summary.spamreport) failureBits.push(`Spam ${summary.spamreport}`);
  if (summary.unsubscribe) failureBits.push(`Unsubscribed ${summary.unsubscribe}`);

  return `
    <section class="live-delivery detail-inspector-section">
      <div class="live-delivery-head">
        <strong>Live SendGrid</strong>
        <span class="muted">Compact delivery state for ${hours}h</span>
      </div>
      ${renderDiagnosticRows(rows)}
      ${renderSendGridMetricDisclaimer(summary)}
      <div class="live-delivery-note">
        <span>${failureBits.length ? failureBits.join(" | ") : "No bounce, block, drop, or spam events in the selected window."}</span>
      </div>
    </section>
  `;
}

function renderWebhookSummary(profile, snapshot = {}) {
  const channel = profileTelemetryChannel(profile);
  const guard = snapshot.private_bounce_guard || {};
  if (channel !== "sendgrid") {
    const guardLabel = profile.name === "private_jc" ? (guard.status_label || "Idle") : "N/A";
    const cooldownText = profile.name === "private_jc"
      ? (guard.cooldown_active
        ? (guard.cooldown_until_utc ? formatGeneratedAt(guard.cooldown_until_utc) : humanizeCooldownRemaining(guard.cooldown_remaining_seconds || 0))
        : "Off")
      : "Off";
    const rows = [
      { label: "Last Status", value: senderLogStatusLabel(profile.last_status || "-") },
      { label: "Errors Today", value: Number(profile.errors_today || 0) },
      { label: "Sent Today", value: Number(profile.sent_today || 0) },
      { label: "Guard", value: guardLabel },
      { label: "Cooldown", value: cooldownText },
    ];
    return `
      <section class="webhook-panel detail-inspector-section">
        <div class="webhook-head">
          <strong>Mailbox Feedback</strong>
          <span class="muted">No webhook event stream for this sender</span>
        </div>
        ${renderDiagnosticRows(rows)}
        <p class="muted">
          Private delivery confirmation comes from SMTP responses, sender logs, and bounce mail processing rather than SendGrid webhooks.
        </p>
      </section>
    `;
  }

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

  const visibleRecent = (Array.isArray(webhook.recent) ? webhook.recent : []).slice(0, MAX_VISIBLE_WEBHOOK_ROWS);
  const recent = visibleRecent.map((row) => `
    <tr>
      <td>${escapeHtml(formatGeneratedAt(row.time || ""))}</td>
      <td>${escapeHtml(statusLabel(row.status || ""))}</td>
      <td>${escapeHtml(row.email || "")}</td>
      <td>${escapeHtml(row.reason || "-")}</td>
    </tr>
  `).join("");

  return `
    <section class="webhook-panel detail-inspector-section">
      <div class="webhook-head">
        <strong>Webhook Events</strong>
        <span class="muted">${webhook.last_received_at ? `Last received ${webhook.last_received_at}` : `Total ${webhook.total || 0}`}</span>
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
  const accepted = profileRunSentDisplay(profile);
  const awaiting = Number(profile.awaiting_outcome || 0);
  const errors = Number(profile.run_errors || 0);
  const readiness = String(profile.readiness_label || "").trim() || "Ready";
  const reasonNote = String(profile.reason_note || profile.health_note || "").trim();
  const runIssueState = String(profile.run_issue_state || "").trim() || "none";
  const reasonCode = String(profile.reason_code || "").trim() || "READY";
  if ((profile?.runtime_state || "") === "paused") {
    return `${readiness}. ${reasonNote || profile?.restart_block_reason || "Provider cooldown is active before the next safe restart."}`;
  }
  if (isProfileActive(profile)) {
    const base = `${accepted} accepted, ${awaiting} awaiting outcome, and ${pending} still pending in this queue.`;
    if ((profile.health_label || "") === "Healthy") return base;
    return `${base} ${reasonNote}`;
  }
  if (accepted || errors || Number(profile.run_skipped || 0)) {
    const base = `${accepted} accepted in this run and ${pending} still pending in the queue.`;
    if (runIssueState === "recovered") {
      if (reasonCode && reasonCode !== "READY") {
        return `${base} Recovered from an earlier run issue; current watch reason: ${reasonCode}. ${reasonNote || ""}`.trim();
      }
      return `${base} Recovered from an earlier run issue.`.trim();
    }
    if (errors > 0) {
      return `${base} Active sender failure needs review. ${reasonNote || ""}`.trim();
    }
    return `${base} ${reasonNote || ""}`.trim();
  }
  return `${pending} pending in this queue. ${reasonNote || "Start this sender when you want it live."}`;
}

function sendgridFleetTarget(snapshot) {
  const controls = snapshot?.controls || {};
  const target = Number(controls.send_target_total || controls.send_cap_total || 0);
  return Number.isFinite(target) && target > 0 ? target : 0;
}

function sendgridProfileTarget(snapshot) {
  const controls = snapshot?.controls || {};
  const explicitTarget = Number(controls.send_target_per_profile || 0);
  if (Number.isFinite(explicitTarget) && explicitTarget > 0) return explicitTarget;
  const fleetTarget = sendgridFleetTarget(snapshot);
  const senderCount = Number(controls.available_sendgrid_sender_count || controls.available_sender_count || 0);
  return fleetTarget > 0 ? Math.ceil(fleetTarget / Math.max(1, senderCount || 5)) : 0;
}

function buildProfileActionNote(profile, snapshot = lastSnapshot) {
  const channel = profileTelemetryChannel(profile);
  if (channel === "sendgrid") {
    const fleetTarget = sendgridFleetTarget(snapshot);
    const profileTarget = sendgridProfileTarget(snapshot);
    const targetCopy = profileTarget > 0
      ? `~${Number(profileTarget).toLocaleString()} profile target from fleet cap ${Number(fleetTarget || 0).toLocaleString()}`
      : `fleet cap ${Number(fleetTarget || profile.max_total || 0).toLocaleString()}`;
    if (profile?.restart_blocked) {
      return profile?.restart_block_reason || "Start is blocked until the provider cooldown window ends.";
    }
    if (canStopProfile(profile)) {
      return `Profile is active. Dashboard start cap is shared across active SendGrid profiles (${targetCopy}). Stop pauses only this sender.`;
    }
    if ((profile.runtime_state || "") === "finished") {
      return `This sender reached its current target or exhausted the queue. Dashboard start cap is shared across active SendGrid profiles (${targetCopy}).`;
    }
    return `Queue is idle. Start runs only this sender using the shared SendGrid launch target (${targetCopy}).`;
  }
  if (profile?.restart_blocked) {
    return profile?.restart_block_reason || "Start is blocked until the provider cooldown window ends.";
  }
  if (canStopProfile(profile)) {
    return `Profile is active. Dashboard start cap is ${profile.max_total || "∞"} for new launches. Stop pauses only this sender.`;
  }
  if ((profile.runtime_state || "") === "finished") {
    return `This sender reached its current cap or exhausted the queue. Dashboard start cap is ${profile.max_total || "∞"}.`;
  }
  return `Queue is idle. Start runs only this sender using a dashboard cap of ${profile.max_total || "∞"}.`;
}

function truncateMiddle(value, maxLength = 56) {
  const text = String(value || "");
  if (!text || text.length <= maxLength) return text || "-";
  const head = Math.max(12, Math.floor((maxLength - 1) * 0.65));
  const tail = Math.max(8, maxLength - head - 1);
  return `${text.slice(0, head)}…${text.slice(-tail)}`;
}

function renderDetailCoreRuntime(profile) {
  const lastActivity = profile.last_timestamp
    ? `${profile.last_timestamp}${profile.last_email ? ` • ${truncateMiddle(profile.last_email, 44)}` : ""}`
    : "No recent sender log line";
  const acceptedCount = profileRunSentDisplay(profile);
  const cooldownDisplay = profileCooldownDisplay(profile);
  const items = [
    { label: "Pending", value: profile.pending_count, tone: Number(profile.pending_count || 0) > 0 ? "warn" : "neutral" },
    { label: "Accepted", value: acceptedCount, tone: acceptedCount > 0 ? "good" : "neutral" },
    Number(profile.awaiting_outcome || 0) > 0
      ? { label: "Awaiting", value: profile.awaiting_outcome || 0, tone: "warn" }
      : null,
    cooldownDisplay.active
      ? { label: "Cooldown", value: cooldownDisplay.text, tone: "warn" }
      : null,
  ].filter(Boolean);
  return `
    <div class="detail-core-grid">
      ${items.map((item) => `
        <div class="detail-core-item detail-core-item-${escapeHtml(item.tone || "neutral")}">
          <span class="detail-core-label">${escapeHtml(item.label)}</span>
          <span class="detail-core-value">${escapeHtml(item.value)}</span>
        </div>
      `).join("")}
    </div>
    <div class="detail-core-activity">
      <div class="detail-compact-row">
        <span class="detail-compact-label">Readiness</span>
        <span class="detail-compact-value">${escapeHtml(profile.readiness_label || "Ready")}</span>
      </div>
      <div class="detail-compact-row">
        <span class="detail-compact-label">Last activity</span>
        <span class="detail-compact-value" title="${escapeHtml(profile.last_email || profile.last_timestamp || "")}">${escapeHtml(lastActivity)}</span>
      </div>
    </div>
  `;
}

function profileHasPaneTail(profile) {
  const text = String(profile?.tmux_tail || "").trim();
  return Boolean(text) && text !== "(no pane output)";
}

function paneTailLineCount(text) {
  const normalized = String(text || "").trim();
  if (!normalized) return 0;
  return normalized.split(/\r?\n/).length;
}

const MAX_VISIBLE_PANE_TAIL_LINES = 10;
const MAX_VISIBLE_WEBHOOK_ROWS = 8;

function tailLines(text, limit = MAX_VISIBLE_PANE_TAIL_LINES) {
  const normalized = String(text || "").trimEnd();
  if (!normalized) return "";
  return normalized.split(/\r?\n/).slice(-Math.max(1, Number(limit) || 1)).join("\n");
}

function isDisclosureOpen(node) {
  return Boolean(node && !node.classList.contains("hidden") && node.open);
}

function clearNodeHtml(node) {
  if (node && node.innerHTML) node.innerHTML = "";
}

function createProfileDetailNode() {
  const node = elementFromHTML(`
    <article class="detail-card">
      <div class="detail-command-bar">
        <div class="detail-head">
          <div>
            <h3></h3>
            <div class="detail-subline">
              <span class="detail-state-line">
                <span class="detail-state-dot detail-state-dot-neutral"></span>
                <span class="detail-state-text"></span>
              </span>
            </div>
            <p class="detail-kicker muted"></p>
          </div>
        </div>
        <section class="detail-action-card detail-command-actions">
          <div class="detail-action-head">
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
      <div class="detail-private-jc-repair-slot"></div>

      <section class="detail-section detail-message-readiness-section">
        <div class="detail-message-readiness-slot"></div>
      </section>

      <section class="detail-section detail-core-section">
        <div class="detail-section-head">
          <strong>Core Runtime</strong>
          <span class="muted detail-progress-note"></span>
        </div>
        <div class="detail-primary-warning-slot"></div>
        <div class="detail-core-runtime"></div>
        <div class="detail-core-meta">
          <div class="detail-core-meta-row">
            <span class="detail-compact-label">Runtime</span>
            <span class="detail-compact-value detail-runtime-note"></span>
          </div>
          <div class="detail-core-meta-row">
            <span class="detail-compact-label">Session</span>
            <span class="detail-compact-value detail-pane-label"></span>
          </div>
        </div>
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

      <details class="detail-disclosure detail-advanced-disclosure heavy-panel">
        <summary>
          <span class="detail-summary-copy">
            <span class="detail-summary-title">Advanced Sender Diagnostics</span>
            <span class="muted detail-summary-note">Mailbox, delivery, queue, guard, and runtime details</span>
          </span>
          <span class="muted detail-summary-meta">Open diagnostics</span>
        </summary>

        <details class="detail-disclosure detail-live-disclosure heavy-panel">
          <summary>
            <span class="detail-summary-copy">
              <span class="detail-summary-title">Mailbox Detail</span>
              <span class="muted detail-summary-note">Live counters and mailbox-specific feedback</span>
            </span>
            <span class="muted detail-summary-meta detail-live-summary-meta"></span>
          </summary>
          <div class="detail-live-slot"></div>
        </details>

        <details class="detail-disclosure detail-webhook-disclosure heavy-panel">
          <summary>
            <span class="detail-summary-copy">
              <span class="detail-summary-title">Delivery / Webhook Detail</span>
              <span class="muted detail-summary-note">Delivery funnel, events, and webhook evidence</span>
            </span>
            <span class="muted detail-summary-meta detail-webhook-summary-meta"></span>
          </summary>
          <div class="detail-webhook-slot"></div>
        </details>

        <details class="detail-disclosure detail-queue-disclosure heavy-panel">
          <summary>
            <span class="detail-summary-copy">
              <span class="detail-summary-title">Queue Context</span>
              <span class="muted detail-summary-note">Files, pacing, and tmux pane</span>
            </span>
            <span class="muted detail-summary-meta detail-queue-summary-meta"></span>
          </summary>
          <div class="profile-meta detail-meta"></div>
        </details>

        <details class="detail-disclosure detail-guard-disclosure heavy-panel">
          <summary>
            <span class="detail-summary-copy">
              <span class="detail-summary-title">Bounce Guard Detail</span>
              <span class="muted detail-summary-note">Suppression sync and recovery safeguards</span>
            </span>
            <span class="muted detail-summary-meta detail-guard-summary-meta"></span>
          </summary>
          <div class="detail-guard-slot"></div>
        </details>

        <details class="detail-pane detail-runtime-output heavy-panel">
          <summary>
            <span class="detail-summary-copy">
              <span class="detail-summary-title">Pane Tail / Runtime Output</span>
              <span class="muted detail-summary-note">Live pane tail from the tmux sender process</span>
            </span>
            <span class="muted detail-summary-meta detail-runtime-summary-meta"></span>
          </summary>
          <pre></pre>
        </details>
      </details>
    </article>
  `);
  node._refs = {
    title: node.querySelector("h3"),
    stateLine: node.querySelector(".detail-state-line"),
    stateDot: node.querySelector(".detail-state-dot"),
    stateText: node.querySelector(".detail-state-text"),
    kicker: node.querySelector(".detail-kicker"),
    paneLabel: node.querySelector(".detail-pane-label"),
    runtimeNote: node.querySelector(".detail-runtime-note"),
    lastUpdate: node.querySelector(".detail-last-update"),
    actionNote: node.querySelector(".detail-action-note"),
    startButton: node.querySelector(".start-profile-btn"),
    stopButton: node.querySelector(".stop-profile-btn"),
    feedback: node.querySelector(".detail-feedback-slot"),
    privateJcRepair: node.querySelector(".detail-private-jc-repair-slot"),
    messageReadiness: node.querySelector(".detail-message-readiness-slot"),
    primaryWarning: node.querySelector(".detail-primary-warning-slot"),
    coreRuntime: node.querySelector(".detail-core-runtime"),
    advancedDisclosure: node.querySelector(".detail-advanced-disclosure"),
    live: node.querySelector(".detail-live-slot"),
    liveDisclosure: node.querySelector(".detail-live-disclosure"),
    liveSummaryMeta: node.querySelector(".detail-live-summary-meta"),
    guard: node.querySelector(".detail-guard-slot"),
    guardDisclosure: node.querySelector(".detail-guard-disclosure"),
    guardSummaryMeta: node.querySelector(".detail-guard-summary-meta"),
    progressNote: node.querySelector(".detail-progress-note"),
    progressValue: node.querySelector(".detail-progress-value"),
    progressFill: node.querySelector(".progress-fill"),
    webhook: node.querySelector(".detail-webhook-slot"),
    webhookDisclosure: node.querySelector(".detail-webhook-disclosure"),
    webhookSummaryMeta: node.querySelector(".detail-webhook-summary-meta"),
    queueDisclosure: node.querySelector(".detail-queue-disclosure"),
    queueSummaryMeta: node.querySelector(".detail-queue-summary-meta"),
    meta: node.querySelector(".detail-meta"),
    runtimeDisclosure: node.querySelector(".detail-runtime-output"),
    runtimeSummaryMeta: node.querySelector(".detail-runtime-summary-meta"),
    paneTail: node.querySelector(".detail-runtime-output pre"),
  };
  const closeAdvancedDiagnostics = () => {
    [
      node._refs.liveDisclosure,
      node._refs.webhookDisclosure,
      node._refs.queueDisclosure,
      node._refs.guardDisclosure,
      node._refs.runtimeDisclosure,
    ].forEach((disclosure) => {
      if (!disclosure) return;
      disclosure.open = false;
      clearDisclosureContent(disclosure);
    });
  };
  const clearDisclosureContent = (disclosure) => {
    if (disclosure === node._refs.liveDisclosure) clearNodeHtml(node._refs.live);
    if (disclosure === node._refs.webhookDisclosure) clearNodeHtml(node._refs.webhook);
    if (disclosure === node._refs.queueDisclosure) clearNodeHtml(node._refs.meta);
    if (disclosure === node._refs.guardDisclosure) clearNodeHtml(node._refs.guard);
    if (disclosure === node._refs.runtimeDisclosure) setNodeText(node._refs.paneTail, "");
  };
  if (node._refs.advancedDisclosure) {
    node._refs.advancedDisclosure.addEventListener("toggle", () => {
      if (!node._refs.advancedDisclosure.open) closeAdvancedDiagnostics();
    });
  }
  [
    node._refs.liveDisclosure,
    node._refs.webhookDisclosure,
    node._refs.queueDisclosure,
    node._refs.guardDisclosure,
    node._refs.runtimeDisclosure,
  ].forEach((disclosure) => {
    if (!disclosure) return;
    disclosure.addEventListener("toggle", () => {
      if (disclosure.open) rerenderCurrentSelection();
      else clearDisclosureContent(disclosure);
    });
  });
  return node;
}

function updateProfileDetailNode(node, snapshot, profile) {
  const refs = node._refs || {
    title: node.querySelector("h3"),
    stateLine: node.querySelector(".detail-state-line"),
    stateDot: node.querySelector(".detail-state-dot"),
    stateText: node.querySelector(".detail-state-text"),
    kicker: node.querySelector(".detail-kicker"),
    paneLabel: node.querySelector(".detail-pane-label"),
    runtimeNote: node.querySelector(".detail-runtime-note"),
    lastUpdate: node.querySelector(".detail-last-update"),
    actionNote: node.querySelector(".detail-action-note"),
    startButton: node.querySelector(".start-profile-btn"),
    stopButton: node.querySelector(".stop-profile-btn"),
    feedback: node.querySelector(".detail-feedback-slot"),
    privateJcRepair: node.querySelector(".detail-private-jc-repair-slot"),
    messageReadiness: node.querySelector(".detail-message-readiness-slot"),
    primaryWarning: node.querySelector(".detail-primary-warning-slot"),
    coreRuntime: node.querySelector(".detail-core-runtime"),
    advancedDisclosure: node.querySelector(".detail-advanced-disclosure"),
    live: node.querySelector(".detail-live-slot"),
    liveDisclosure: node.querySelector(".detail-live-disclosure"),
    liveSummaryMeta: node.querySelector(".detail-live-summary-meta"),
    guard: node.querySelector(".detail-guard-slot"),
    guardDisclosure: node.querySelector(".detail-guard-disclosure"),
    guardSummaryMeta: node.querySelector(".detail-guard-summary-meta"),
    progressNote: node.querySelector(".detail-progress-note"),
    progressValue: node.querySelector(".detail-progress-value"),
    progressFill: node.querySelector(".progress-fill"),
    webhook: node.querySelector(".detail-webhook-slot"),
    webhookDisclosure: node.querySelector(".detail-webhook-disclosure"),
    webhookSummaryMeta: node.querySelector(".detail-webhook-summary-meta"),
    queueDisclosure: node.querySelector(".detail-queue-disclosure"),
    queueSummaryMeta: node.querySelector(".detail-queue-summary-meta"),
    meta: node.querySelector(".detail-meta"),
    runtimeDisclosure: node.querySelector(".detail-runtime-output"),
    runtimeSummaryMeta: node.querySelector(".detail-runtime-summary-meta"),
    paneTail: node.querySelector(".detail-runtime-output pre"),
  };
  node._refs = refs;

  const activity = profileActivityState(profile);
  const runtimeClass = `detail-runtime-${activity.tone || "neutral"}`;
  const pendingAction = pendingProfileActions.get(profile.name) || "";
  const startDisabled = Boolean(pendingAction) || !canStartProfile(profile, snapshot);
  const stopDisabled = Boolean(pendingAction) || !canStopProfile(profile);
  const effectiveSpacing = Number(profile.effective_spacing_seconds || 0);
  const effectivePace = Number(profile.effective_pace_per_hour || 0);
  const paceDisplay = effectiveSpacing > 0 ? `${effectiveSpacing}s${effectivePace > 0 ? ` (~${effectivePace}/h)` : ""}` : "-";
  const maxTotalRaw = Number(profile.max_total || 0);
  const acceptedRaw = profileRunSentDisplay(profile);
  const channel = profileTelemetryChannel(profile);
  const isSendGridProfile = channel === "sendgrid";
  const fleetTargetRaw = isSendGridProfile ? sendgridFleetTarget(snapshot) : 0;
  const profileTargetRaw = isSendGridProfile ? sendgridProfileTarget(snapshot) : 0;
  const progressDenominator = isSendGridProfile ? (profileTargetRaw || maxTotalRaw) : maxTotalRaw;
  const progress = progressDenominator > 0 ? Math.max(0, Math.min(100, (acceptedRaw / progressDenominator) * 100)) : 0;
  const showProgress = isProfileActive(profile) || acceptedRaw > 0;
  const showSession = Boolean(profile.pane_index || profile.tmux_command);
  const webhook = profile.webhook || {};
  const webhookSummary = webhook.summary || {};
  const webhookRecent = Array.isArray(webhook.recent) ? webhook.recent : [];
  const webhookCounts = webhook.counts || {};
  const hasPaneTail = profileHasPaneTail(profile);
  const paneTailText = hasPaneTail ? tailLines(profile.tmux_tail, MAX_VISIBLE_PANE_TAIL_LINES) : "(no pane output)";
  const paneTailLines = hasPaneTail ? paneTailLineCount(paneTailText) : 0;
  const guard = snapshot.private_bounce_guard || {};
  const hasWebhookDetail = channel !== "sendgrid"
    ? Boolean(profile.last_status || profile.last_timestamp || Number(profile.sent_today || 0) || Number(profile.errors_today || 0))
    : Boolean(
      webhook.last_received_at ||
      webhook.last_received_iso ||
      Number(webhook.total || 0) ||
      webhookRecent.length ||
      Object.keys(webhookCounts).length ||
      Object.values(webhookSummary).some((value) => Number(value || 0) > 0) ||
      Number(profile.awaiting_outcome || 0) > 0,
    );
  const liveSummary = channel === "sendgrid"
    ? `Delivered ${Number(webhookSummary.delivered || 0)} • Awaiting ${Number(profile.awaiting_outcome || 0)}`
    : `Sent ${Number(profile.sent_today || 0)} • Errors ${Number(profile.errors_today || 0)}`;
  const webhookSummaryText = channel === "sendgrid"
    ? (hasWebhookDetail ? `Recent ${webhookRecent.length} • Total ${Number(webhook.total || 0)}` : "No webhook telemetry")
    : "SMTP responses • sender log";
  const queueSummary = `Pace ${paceDisplay} • Pane ${profile.pane_index || "-"}`;
  const guardSummary = profile.name === "private_jc"
    ? `${guard.status_label || "Idle"} • Cooldown ${guard.cooldown_active ? humanizeCooldownRemaining(guard.cooldown_remaining_seconds || 0) : "Off"}`
    : "";
  const runtimeSummary = hasPaneTail ? `${paneTailLines} line${paneTailLines === 1 ? "" : "s"}` : "No pane output";
  const metaBoxes = [
    { label: "Effective Pace", value: paceDisplay },
    { label: "Queue File", value: profile.csv_path },
    { label: "Sender Log", value: profile.log_path },
    { label: "Configured Cap", value: profile.configured_max_total || "∞" },
    { label: "Dashboard Start Cap", value: profile.max_total || "∞" },
    { label: "Session Pane", value: `${profile.pane_index} / ${profile.tmux_command || "-"}` },
  ];

  node.className = `detail-card ${runtimeClass}`;
  node.dataset.profile = profile.name || "";
  setNodeText(refs.title, formatProfileName(profile.name));
  refs.stateLine.className = `detail-state-line detail-state-line-${activity.tone || "neutral"}`;
  refs.stateDot.className = `detail-state-dot detail-state-dot-${activity.tone || "neutral"}`;
  setNodeText(refs.stateText, profile.runtime_label || activity.label || "Stopped");
  setNodeText(refs.kicker, buildDetailKicker(profile));
  setNodeText(refs.paneLabel, `Pane ${profile.pane_index} / ${profile.tmux_command || "-"}`);
  setNodeText(refs.runtimeNote, profile.runtime_note || "Pane is idle.");
  setNodeText(refs.lastUpdate, profileLastUpdateText(profile));
  const profileQueueBlocked = queueSafetyBlockedForProfile(profile, snapshot);
  setNodeText(
    refs.actionNote,
    profileQueueBlocked
      ? `NOT READY / BLOCKED: ${queueSafetyBlockMessageForProfile(profile, snapshot)}`
      : (isProfileActive(profile) || profile?.restart_blocked || (profile.runtime_state || "") === "finished") ? buildProfileActionNote(profile, snapshot) : "",
  );

  refs.startButton.dataset.profile = profile.name || "";
  refs.startButton.disabled = startDisabled;
  setNodeText(refs.startButton, pendingAction === "start" ? "Starting..." : "Start");

  refs.stopButton.dataset.profile = profile.name || "";
  refs.stopButton.disabled = stopDisabled;
  setNodeText(refs.stopButton, pendingAction === "stop" ? "Stopping..." : "Stop");

  setNodeHtml(refs.feedback, renderProfileActionFeedback(profile));
  setNodeHtml(refs.privateJcRepair, renderPrivateJcQueueRepair(profile, snapshot));
  setNodeHtml(refs.messageReadiness, renderMessageReadiness(profile));
  setNodeHtml(refs.primaryWarning, renderDetailPrimaryWarning(profile));
  setNodeHtml(refs.coreRuntime, renderDetailCoreRuntime(profile));

  setNodeText(refs.liveSummaryMeta, liveSummary);
  if (refs.liveDisclosure) {
    const showLive = true;
    refs.liveDisclosure.classList.toggle("hidden", !showLive);
    if (!showLive) refs.liveDisclosure.open = false;
    if (isDisclosureOpen(refs.liveDisclosure)) setNodeHtml(refs.live, renderLiveDelivery(profile, snapshot.activity_hours));
    else clearNodeHtml(refs.live);
  }
  if (refs.guardDisclosure) {
    const showGuard = Boolean(profile.name === "private_jc");
    setNodeText(refs.guardSummaryMeta, showGuard ? guardSummary : "");
    refs.guardDisclosure.classList.toggle("hidden", !showGuard);
    if (!showGuard) refs.guardDisclosure.open = false;
    if (isDisclosureOpen(refs.guardDisclosure)) {
      setNodeHtml(refs.guard, renderDetailPrivateBounceGuard(profile, snapshot.private_bounce_guard || {}, snapshot.automation || {}));
    } else {
      clearNodeHtml(refs.guard);
    }
  }
  setNodeText(
    refs.progressNote,
    showProgress
      ? isSendGridProfile
        ? `Dashboard start cap is shared across active SendGrid profiles. Fleet cap ${fleetTargetRaw ? Number(fleetTargetRaw).toLocaleString() : "∞"}${profileTargetRaw ? ` · ~${Number(profileTargetRaw).toLocaleString()} profile target` : ""}. Base profile cap ${profile.configured_max_total || "∞"}.`
        : `Dashboard start cap ${profile.max_total || "∞"} accepted recipient${Number(profile.max_total || 0) === 1 ? "" : "s"}. Base profile cap ${profile.configured_max_total || "∞"}.`
      : "",
  );
  setNodeText(
    refs.progressValue,
    isSendGridProfile
      ? profileTargetRaw
        ? `${Number(acceptedRaw).toLocaleString()} / ~${Number(profileTargetRaw).toLocaleString()} profile target`
        : `${Number(acceptedRaw).toLocaleString()} sent · fleet cap ${fleetTargetRaw ? Number(fleetTargetRaw).toLocaleString() : "∞"}`
      : `${Number(acceptedRaw).toLocaleString()}/${profile.max_total || "∞"}`,
  );
  refs.progressFill.style.width = `${progress}%`;
  refs.progressFill.closest(".progress-wrap")?.classList.toggle("hidden", !showProgress);
  refs.paneLabel.closest(".detail-core-meta-row")?.classList.toggle("hidden", !showSession);
  refs.runtimeNote.closest(".detail-core-meta-row")?.classList.toggle("hidden", !showProgress);
  setNodeText(refs.webhookSummaryMeta, webhookSummaryText);
  if (refs.webhookDisclosure) {
    refs.webhookDisclosure.classList.toggle("hidden", !hasWebhookDetail);
    if (!hasWebhookDetail) refs.webhookDisclosure.open = false;
    if (isDisclosureOpen(refs.webhookDisclosure)) setNodeHtml(refs.webhook, renderWebhookSummary(profile, snapshot));
    else clearNodeHtml(refs.webhook);
  }
  setNodeText(refs.queueSummaryMeta, queueSummary);
  if (refs.queueDisclosure) {
    if (isDisclosureOpen(refs.queueDisclosure)) {
      setNodeHtml(
        refs.meta,
        metaBoxes.map((item) => `
          <div class="detail-meta-row">
            <div class="detail-meta-label">${escapeHtml(item.label)}</div>
            <code class="detail-meta-value">${escapeHtml(item.value || "-")}</code>
          </div>
        `).join(""),
      );
    } else {
      clearNodeHtml(refs.meta);
    }
  }
  setNodeText(refs.runtimeSummaryMeta, runtimeSummary);
  if (refs.runtimeDisclosure) {
    refs.runtimeDisclosure.classList.toggle("hidden", !hasPaneTail);
    if (!hasPaneTail) refs.runtimeDisclosure.open = false;
  }
  if (isDisclosureOpen(refs.runtimeDisclosure)) setNodeText(refs.paneTail, paneTailText);
  else setNodeText(refs.paneTail, "");
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
  renderSenderStatusConsole(snapshot, selectedProfile);
  renderTrends(snapshot);
  renderWebhookHealth(snapshot);
  renderAwaitingAging(snapshot, selectedProfile);
  renderDomainBreakdown(snapshot);
  renderOverview(snapshot, selectedProfile);
  renderCampaignRunHistory(snapshot);
  renderSignals(snapshot);
  renderFailures(snapshot);
  renderDetailSwitcher(snapshot, selectedProfile);
  renderProfileDetail(snapshot, selectedProfile);
  renderShardWriteGuard();
  if (isActiveImportantLeadCheckJob(lastImportantDispatchJob)) {
    renderImportantLeadDispatchJob(lastImportantDispatchJob);
  } else {
    renderImportantDispatch(lastImportantDispatch);
  }
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
  renderSenderStatusConsole(lastSnapshot, selected);
  renderDetailSwitcher(lastSnapshot, selected);
  renderProfileDetail(lastSnapshot, selected);
}

async function runProfilePreviewValidation(profileName) {
  const profile = String(profileName || "").trim();
  if (!profile) return;
  profilePreviewValidationState.set(profile, { kind: "loading", message: "Generating preview and validating..." });
  rerenderCurrentSelection();
  try {
    const data = await fetchJson(`/api/profiles/${encodeURIComponent(profile)}/preview-validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const result = data.result || {};
    const passed = result.validation_status === "PASS" || result.validation_passed === true;
    const reasonText = Array.isArray(result.validation_reasons) && result.validation_reasons.length
      ? ` Top reason: ${result.validation_reasons[0]}.`
      : "";
    profilePreviewValidationState.set(profile, {
      kind: passed ? "success" : "error",
      message: `${passed ? "Preview validation passed" : "Preview validation failed"} (${Number(result.preview_row_count || 0).toLocaleString()} row(s)).${reasonText}`,
    });
    if (data.snapshot) {
      renderSnapshot(data.snapshot);
    } else {
      await fetchSnapshot();
    }
    showMessage(data.message || (passed ? "Preview validation passed." : "Preview validation failed."), passed ? "success" : "error");
  } catch (err) {
    profilePreviewValidationState.set(profile, { kind: "error", message: `Preview validation failed: ${err}` });
    rerenderCurrentSelection();
    showMessage(`Preview validation failed: ${err}`, "error");
  }
}

async function repairPrivateJcQueue() {
  privateJcQueueRepairState.kind = "loading";
  privateJcQueueRepairState.message = "Repairing Private JC queue...";
  privateJcQueueRepairState.summary = null;
  rerenderCurrentSelection();
  try {
    const data = await fetchJson("/api/profiles/private_jc/repair-queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    privateJcQueueRepairState.kind = data.ok ? "success" : "error";
    privateJcQueueRepairState.message = data.message || (data.ok ? "Private JC queue repaired." : "Private JC queue repair failed.");
    privateJcQueueRepairState.summary = data.summary || null;
    if (data.snapshot) renderSnapshot(data.snapshot);
    else await fetchSnapshot();
    showMessage(privateJcQueueRepairState.message, data.ok ? "success" : "error");
  } catch (err) {
    privateJcQueueRepairState.kind = "error";
    privateJcQueueRepairState.message = `Private JC queue repair failed: ${err}`;
    privateJcQueueRepairState.summary = null;
    rerenderCurrentSelection();
    showMessage(privateJcQueueRepairState.message, "error");
  }
}

function handleOverviewClick(event) {
  if (wallboardMode) return;
  const previewButton = event.target.closest(".preview-validate-profile-btn[data-profile]");
  if (previewButton && els.overviewGrid.contains(previewButton)) {
    if (previewButton.disabled) return;
    void runProfilePreviewValidation(previewButton.getAttribute("data-profile") || "");
    return;
  }
  const card = event.target.closest(".overview-card[data-profile]");
  if (!card || !els.overviewGrid.contains(card)) return;
  selectProfileByName(card.getAttribute("data-profile") || "");
}

async function handleProfileDetailClick(event) {
  const repairPrivateJcButton = event.target.closest(".repair-private-jc-queue-btn");
  if (repairPrivateJcButton && els.profileDetail.contains(repairPrivateJcButton)) {
    if (repairPrivateJcButton.disabled) return;
    await repairPrivateJcQueue();
    return;
  }

  const previewButton = event.target.closest(".preview-validate-profile-btn[data-profile]");
  if (previewButton && els.profileDetail.contains(previewButton)) {
    if (previewButton.disabled) return;
    void runProfilePreviewValidation(previewButton.getAttribute("data-profile") || "");
    return;
  }

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

async function handleSenderStatusClick(event) {
  const actionButton = event.target.closest(".sender-status-action-btn[data-profile][data-action]");
  if (actionButton && senderStatusPanel?.contains(actionButton)) {
    if (actionButton.disabled) return;
    const profile = actionButton.getAttribute("data-profile") || "";
    const action = actionButton.getAttribute("data-action") || "";
    if (!profile || !["start", "stop"].includes(action)) return;
    await postAction(`/api/${action}/${profile}`, { profileName: profile, action });
    return;
  }
  const profileButton = event.target.closest(".sender-status-name-btn[data-profile]");
  if (profileButton && senderStatusPanel?.contains(profileButton)) {
    selectProfileByName(profileButton.getAttribute("data-profile") || "");
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
    const blockReasons = Array.isArray(data.blocked_reasons) ? data.blocked_reasons : Array.isArray(data.reasons) ? data.reasons : [];
    const message = data.message
      || (blockReasons.length ? `NOT READY / BLOCKED: ${blockReasons.join(" ")}` : "")
      || data.detail
      || (ok ? "Action complete." : `Request failed (${response.status}).`);
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
  if (![5000, 10000].includes(rawValue)) {
    showMessage("Choose a SendGrid target of 5,000 or 10,000.", "error");
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
      setNodeText(els.sendCapSaveBtn, "Save");
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

function connectSocket(forceReconnect = false) {
  if (!authState.authenticated) {
    stopSocket();
    return;
  }
  if (!isOpsTabVisible()) {
    stopSocket();
    return;
  }
  socketShouldReconnect = true;
  if (socket && !forceReconnect && socket.readyState !== WebSocket.CLOSING && socket.readyState !== WebSocket.CLOSED) {
    return;
  }
  if (socketReconnectTimer) {
    clearTimeout(socketReconnectTimer);
    socketReconnectTimer = null;
  }
  if (socket) {
    socketShouldReconnect = false;
    socket.close();
    socket = null;
  }
  socketShouldReconnect = true;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const hours = encodeURIComponent(currentActivityHours());
  const tail = encodeURIComponent(currentTailLines());
  const nextSocket = new WebSocket(`${protocol}://${location.host}/ws?hours=${hours}&tail_lines=${tail}`);
  socket = nextSocket;

  nextSocket.addEventListener("open", () => {
    setConnectionState(true);
  });

  nextSocket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    renderSnapshot(payload);
  });

  nextSocket.addEventListener("close", () => {
    setConnectionState(false);
    if (socket === nextSocket) {
      socket = null;
    }
    if (socketShouldReconnect && authState.authenticated && isOpsTabVisible()) {
      socketReconnectTimer = setTimeout(connectSocket, 1500);
    }
  });

  nextSocket.addEventListener("error", () => {
    setConnectionState(false);
    if (socket === nextSocket) {
      socket.close();
    }
  });
}

function stopSocket() {
  socketShouldReconnect = false;
  if (socketReconnectTimer) {
    clearTimeout(socketReconnectTimer);
    socketReconnectTimer = null;
  }
  if (socket) {
    try {
      socket.close();
    } catch (err) {
      // no-op
    }
    socket = null;
  }
  setConnectionState(false);
}

async function bootstrapAuthenticatedDashboard() {
  if (isLeadsTabVisible()) {
    await fetchLeadsStatus();
    stopSocket();
    return;
  }
  await fetchSnapshot();
  connectSocket();
}

async function bootstrapDashboard() {
  try {
    const auth = await fetchAuthStatus();
    if (auth.authenticated) {
      await bootstrapAuthenticatedDashboard();
    } else {
      stopSocket();
      renderAuthUi();
      showAuthOverlay(auth.auth_enabled ? "Sign in to unlock dashboard controls." : "Dashboard auth is not configured.");
    }
  } catch (err) {
    stopSocket();
    setAuthState({
      authEnabled: authState.authEnabled,
      authenticated: false,
      username: "",
      message: String(err),
    });
  }
}

if (els.refreshBtn) els.refreshBtn.addEventListener("click", () => fetchSnapshot());
if (els.sendCapSaveBtn) els.sendCapSaveBtn.addEventListener("click", () => saveSendCap());
if (els.wallboardBtn) els.wallboardBtn.addEventListener("click", () => toggleWallboardMode());
if (els.startBtn) els.startBtn.addEventListener("click", () => postAction("/api/start"));
if (els.stopBtn) els.stopBtn.addEventListener("click", () => postAction("/api/stop"));
if (els.archiveBtn) els.archiveBtn.addEventListener("click", () => postAction("/api/archive-reset-logs"));
if (els.opsTabBtn) els.opsTabBtn.addEventListener("click", () => setDashboardTab("ops"));
if (els.leadsTabBtn) els.leadsTabBtn.addEventListener("click", () => setDashboardTab("leads"));
if (els.leadsImportantUploadCheckBtn) els.leadsImportantUploadCheckBtn.addEventListener("click", () => runImportantLeadUploadCheck());
if (els.leadsImportantCheckBtn) els.leadsImportantCheckBtn.addEventListener("click", () => runImportantLeadCheck());
if (els.leadsImportantIntakeMode) els.leadsImportantIntakeMode.addEventListener("change", () => renderLeadsOperatorStatusStrip(lastLeadsStatus || {}));
if (els.leadsImportantVerifyBtn) els.leadsImportantVerifyBtn.addEventListener("click", () => runImportantLeadVerify(VERIFY_MODE_FAST_TRIAGE));
if (els.leadsImportantVerifyStrictBtn) els.leadsImportantVerifyStrictBtn.addEventListener("click", () => runImportantLeadVerify(VERIFY_MODE_STRICT_PUBLIC_PROOF));
if (els.leadsImportantVerifyStopBtn) els.leadsImportantVerifyStopBtn.addEventListener("click", () => stopImportantLeadVerify());
if (els.leadsImportantDispatchPreviewBtn) els.leadsImportantDispatchPreviewBtn.addEventListener("click", () => previewImportantLeadDispatch());
if (els.leadsImportantDispatchConfirmBtn) els.leadsImportantDispatchConfirmBtn.addEventListener("click", () => confirmImportantLeadDispatch());
if (els.leadsImportantInputText) {
  els.leadsImportantInputText.addEventListener("input", () => updateImportantLeadPasteGuardrails());
  els.leadsImportantInputText.addEventListener("change", () => updateImportantLeadPasteGuardrails());
}
if (els.leadsImportantUploadFile) {
  els.leadsImportantUploadFile.addEventListener("change", () => updateImportantLeadUploadNote());
}
if (els.leadsImportantDispatchSourceMode) {
  els.leadsImportantDispatchSourceMode.addEventListener("change", () => renderImportantDispatch(lastImportantDispatch));
}
if (els.leadsImportantDispatchCap) {
  els.leadsImportantDispatchCap.addEventListener("change", () => renderImportantDispatch(lastImportantDispatch));
}
if (els.leadsUploadBtn) els.leadsUploadBtn.addEventListener("click", () => uploadLeadsFile());
if (els.leadsCleanBtn) els.leadsCleanBtn.addEventListener("click", () => runLeadClean());
if (els.leadsPreviewBtn) els.leadsPreviewBtn.addEventListener("click", () => previewLeadShard());
if (els.leadsShardBtn) els.leadsShardBtn.addEventListener("click", () => runLeadShard());
if (els.leadsRefreshBtn) els.leadsRefreshBtn.addEventListener("click", () => fetchLeadsStatus());
if (els.leadsQuarantineRefreshBtn) els.leadsQuarantineRefreshBtn.addEventListener("click", () => {
  if (!quarantineInboxOpen) openQuarantineInbox({ load: false });
  refreshQuarantineReview(false, false);
});
if (els.leadsQuarantinePromoteBtn) els.leadsQuarantinePromoteBtn.addEventListener("click", () => runQuarantineReviewAction("promote_dispatch_ready"));
if (els.leadsQuarantineRejectBtn) els.leadsQuarantineRejectBtn.addEventListener("click", () => runQuarantineReviewAction("reject_permanently"));
if (els.leadsQuarantineStrictBtn) els.leadsQuarantineStrictBtn.addEventListener("click", () => runQuarantineReviewAction("send_to_strict_verify"));
if (els.leadsQuarantineNoteBtn) els.leadsQuarantineNoteBtn.addEventListener("click", () => runQuarantineReviewAction("update_operator_note"));
if (els.leadsQuarantineReasonCode) els.leadsQuarantineReasonCode.addEventListener("change", () => refreshQuarantineReview(false, true));
if (els.leadsQuarantineStage) els.leadsQuarantineStage.addEventListener("change", () => refreshQuarantineReview(false, true));
if (els.leadsQuarantineStatus) els.leadsQuarantineStatus.addEventListener("change", () => refreshQuarantineReview(false, true));
if (els.leadsQuarantineSort) els.leadsQuarantineSort.addEventListener("change", () => refreshQuarantineReview(false, true));
if (els.leadsQuarantineResults) {
  els.leadsQuarantineResults.addEventListener("click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    if (target?.closest?.("[data-quarantine-select]")) {
      return;
    }
    if (target?.closest?.("[data-quarantine-check-page]")) {
      updateQuarantineSelectionForVisiblePage(true, lastQuarantineReview);
      return;
    }
    if (target?.closest?.("[data-quarantine-uncheck-page]")) {
      updateQuarantineSelectionForVisiblePage(false, lastQuarantineReview);
      return;
    }
    if (target?.closest?.("[data-quarantine-select-all-filtered]")) {
      selectAllFilteredQuarantineLeads();
      return;
    }
    if (target?.closest?.("[data-quarantine-clear-selection]")) {
      clearQuarantineSelection();
      renderQuarantineReview(lastQuarantineReview);
      return;
    }
    if (target?.closest?.("[data-quarantine-prev-page]")) {
      moveQuarantinePage(-1);
      return;
    }
    if (target?.closest?.("[data-quarantine-next-page]")) {
      moveQuarantinePage(1);
      return;
    }
    const inspectButton = target?.closest?.("[data-quarantine-inspect]");
    if (inspectButton) {
      const leadId = String(inspectButton.getAttribute("data-quarantine-inspect") || "");
      if (leadId) {
        void loadQuarantineReviewLeadDetail(leadId);
      }
      return;
    }
    const row = target?.closest?.("[data-quarantine-row]");
    if (row) {
      const leadId = String(row.getAttribute("data-quarantine-row") || "");
      if (leadId) {
        void loadQuarantineReviewLeadDetail(leadId);
      }
    }
  });
  els.leadsQuarantineResults.addEventListener("change", (event) => {
    const inputTarget = event.target instanceof HTMLInputElement ? event.target : null;
    const selectTarget = event.target instanceof HTMLSelectElement ? event.target : null;
    if (selectTarget?.hasAttribute("data-quarantine-page-size")) {
      setQuarantineRowsPerPage(selectTarget.value);
      return;
    }
    const target = inputTarget;
    if (!target) return;
    if (target.hasAttribute("data-quarantine-page-toggle")) {
      updateQuarantineSelectionForVisiblePage(Boolean(target.checked), lastQuarantineReview);
      return;
    }
    const leadId = String(target.getAttribute("data-quarantine-select") || "");
    if (!leadId) return;
    if (allFilteredQuarantineSelected) {
      if (target.checked) excludedQuarantineLeadIds.delete(leadId);
      else excludedQuarantineLeadIds.add(leadId);
    } else if (target.checked) {
      selectedQuarantineLeadIds.add(leadId);
    } else {
      selectedQuarantineLeadIds.delete(leadId);
    }
    renderQuarantineReview(lastQuarantineReview);
  });
}
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
if (els.hoursSelect) els.hoursSelect.addEventListener("change", () => connectSocket(true));
if (els.tailSelect) els.tailSelect.addEventListener("change", () => connectSocket(true));
if (els.opsView) els.opsView.addEventListener("click", handleSenderStatusClick);
if (els.overviewGrid) els.overviewGrid.addEventListener("click", handleOverviewClick);
if (els.profileDetail) els.profileDetail.addEventListener("click", handleProfileDetailClick);
if (els.detailProfileSelect) {
  els.detailProfileSelect.addEventListener("change", (event) => {
    selectProfileByName(event.target.value);
  });
}
if (els.detailPrevBtn) els.detailPrevBtn.addEventListener("click", () => shiftSelectedProfile(-1));
if (els.detailNextBtn) els.detailNextBtn.addEventListener("click", () => shiftSelectedProfile(1));
if (els.authForm) {
  els.authForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void submitAuthLogin();
  });
}
if (els.authLogoutBtn) els.authLogoutBtn.addEventListener("click", () => submitAuthLogout());

wallboardMode = readWallboardModeFromLocation();
activeDashboardTab = readDashboardTabFromLocation();
applyWallboardMode();
applyDashboardTab();
applyLeadsTriageCopy();
initQuarantineInboxDisclosure();
renderImportantLeadCheck(lastImportantLeadCheck);
renderImportantLeadVerify(lastImportantVerify);
renderImportantDispatch(lastImportantDispatch);
renderAuthUi();
showAuthOverlay("Loading authentication status...");
bootstrapDashboard();
