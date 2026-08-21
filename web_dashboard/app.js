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
  opsProgressSummary: document.getElementById("ops-progress-summary"),
  opsProgressDetails: document.getElementById("ops-progress-details"),
  opsProgressDetailsToggle: document.getElementById("ops-progress-details-toggle"),
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
  startReadyBtn: document.getElementById("start-ready-btn"),
  startReadyStatus: document.getElementById("start-ready-status"),
  stopBtn: document.getElementById("stop-btn"),
  archiveBtn: document.getElementById("archive-btn"),
  leadsImportantInputPath: document.getElementById("leads-important-input-path"),
  leadsImportantIntakeMode: document.getElementById("leads-important-intake-mode"),
  leadsImportantOutputPath: document.getElementById("leads-important-output-path"),
  leadsImportantRejectedPath: document.getElementById("leads-important-rejected-path"),
  leadsImportantInputText: document.getElementById("leads-important-input-text"),
  leadsImportantPasteNote: document.getElementById("leads-important-paste-note"),
  leadsImportantUploadFile: document.getElementById("leads-important-upload-file"),
  leadsImportantUploadType: document.getElementById("leads-important-upload-type"),
  leadsImportantUploadNote: document.getElementById("leads-important-upload-note"),
  leadsImportantUploadCheckBtn: document.getElementById("leads-important-upload-check-btn"),
  leadsImportantCheckBtn: document.getElementById("leads-important-check-btn"),
  leadsImportantCheckMeta: document.getElementById("leads-important-check-meta"),
  leadCheckStatusCard: document.getElementById("lead-check-status-card"),
  leadsControlCheckResult: document.getElementById("leads-control-check-result"),
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
  leadsImportantDispatchCampaignType: document.getElementById("leads-dispatch-campaign-type"),
  leadsImportantDispatchSourceNote: document.getElementById("leads-dispatch-source-note"),
  leadsDispatchModeCards: document.getElementById("leads-dispatch-mode-cards"),
  leadsRecommendedNextAction: document.getElementById("leads-recommended-next-action"),
  leadsRecontactOverrideWrap: document.getElementById("leads-recontact-override-wrap"),
  leadsRecontactRecencyOverride: document.getElementById("leads-recontact-recency-override"),
  leadsDispatchSection: document.querySelector(".leads-dispatch-section"),
  leadsDispatchCurrentQueueNote: document.getElementById("leads-dispatch-current-queue-note"),
  leadsImportantDispatchPreviewBtn: document.getElementById("leads-important-dispatch-preview-btn"),
  leadsImportantDispatchPreviewTopBtn: document.getElementById("leads-important-dispatch-preview-top-btn"),
  leadsImportantDispatchConfirmBtn: document.getElementById("leads-important-dispatch-confirm-btn"),
  leadsImportantDispatchMeta: document.getElementById("leads-important-dispatch-meta"),
  leadsImportantDispatchResults: document.getElementById("leads-important-dispatch-results"),
  leadsCurrentQueueNote: document.getElementById("leads-current-queue-note"),
  leadsPipelineMeta: document.getElementById("leads-pipeline-meta"),
  leadsCommandHeading: document.getElementById("leads-command-heading"),
  leadsDispatchCommandColumn: document.getElementById("leads-dispatch-command-column"),
  leadsWorkflowTaskList: document.getElementById("leads-workflow-task-list"),
  leadsCurrentRunPanel: document.getElementById("leads-current-run-panel"),
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
  environmentBanner: document.getElementById("dashboard-environment-banner"),
  environmentMode: document.getElementById("dashboard-environment-mode"),
  environmentAuthMode: document.getElementById("dashboard-auth-mode"),
  environmentAutoStartMode: document.getElementById("dashboard-auto-start-mode"),
  environmentNote: document.getElementById("dashboard-environment-note"),
  messageBar: document.getElementById("message-bar"),
};

let snapshotPollTimer = null;
let snapshotPollGeneration = 0;
let lastSnapshot = null;
let lastLeadsStatus = null;
let lastShardPreview = null;
let lastImportantLeadCheck = null;
let warmDraftPreviewLoading = false;
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
let saferRecontactPoolLoading = false;
let importantLeadDispatchConfirmLoading = false;
let lastImportantDispatchPreviewState = "not_generated";
let lastImportantDispatchPreviewFeedback = null;
let lastImportantDispatchConfirmFeedback = null;
let lastSaferRecontactSummary = null;
let lastSaferRecontactFeedback = null;
let lastQuarantineReview = null;
let lastQuarantineReviewLead = null;
let quarantineInboxOpen = false;
let quarantineToggleBtn = null;
const selectedQuarantineLeadIds = new Set();
const excludedQuarantineLeadIds = new Set();
let allFilteredQuarantineSelected = false;
let quarantinePageSize = 10;
let quarantinePageIndex = 0;
let didHydrate = false;
let socketLive = false;
let snapshotFallbackHealthy = false;
let selectedProfileName = "";
let senderStatusPanel = null;
let warmSenderLeadStatusRequested = false;
let displayTimeZone = "America/Los_Angeles";
let wallboardMode = false;
let startReadyBusy = false;
let startReadyJobId = "";
let startReadyPollTimer = null;
let activeDashboardTab = "ops";
let activeLeadWorkflow = "cold";
const tabPanelMounts = {
  initialized: false,
  opsAnchor: null,
  leadsAnchor: null,
};
let authState = {
  authEnabled: true,
  authDisabled: false,
  authenticated: false,
  username: "",
  dashboardMode: "live",
  autoStartAllowed: false,
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
const LEAD_OPS_PROGRESS_STALE_WARNING =
  "Lead Ops progress appears stale. The job may have stopped or the dashboard may need inspection.";
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
  socketLive = Boolean(live);
  els.wsIndicator.className = `dot ${live ? "dot-live" : "dot-off"}`;
  if (live) {
    els.wsLabel.textContent = "Connected";
  } else if (isLeadsTabVisible() && lastLeadsStatus) {
    els.wsLabel.textContent = "Live status";
  } else if (snapshotFallbackHealthy && lastSnapshot) {
    els.wsLabel.textContent = "Connected";
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
  const authEnabled = Boolean(authState.authEnabled);
  const authDisabled = Boolean(authState.authDisabled);
  if (els.authStatusLabel) {
    setNodeText(
      els.authStatusLabel,
      authDisabled
        ? "Local dev"
        : authenticated
        ? `Signed in as ${authState.username || "admin"}`
        : authEnabled
          ? "Signed out"
          : "Auth not configured",
    );
  }
  if (els.authLogoutBtn) {
    els.authLogoutBtn.disabled = authDisabled || !authenticated;
    els.authLogoutBtn.classList.toggle("hidden", authDisabled);
    els.authLogoutBtn.setAttribute("aria-hidden", authDisabled ? "true" : "false");
  }
  if (els.page) {
    els.page.classList.toggle("is-authenticated", authenticated);
    els.page.classList.toggle("is-auth-disabled", authDisabled || !authEnabled);
  }
  renderEnvironmentStatus();
}

function renderEnvironmentStatus(overrides = {}) {
  const dashboardMode = String(overrides.dashboardMode ?? authState.dashboardMode ?? "live");
  const localDev = dashboardMode === "local_dev";
  const authEnabled = Boolean(overrides.authEnabled ?? authState.authEnabled);
  const authDisabled = Boolean(overrides.authDisabled ?? authState.authDisabled);
  const autoStartAllowed = Boolean(overrides.autoStartAllowed ?? authState.autoStartAllowed);
  if (els.environmentBanner) {
    els.environmentBanner.className = `react-environment-banner react-environment-banner-${localDev ? "local" : "live"}`;
  }
  setNodeText(els.environmentMode, localDev ? "Local / dev mode" : "Live mode");
  setNodeText(els.environmentAuthMode, authDisabled ? "Auth disabled" : authEnabled ? "Auth enabled" : "Auth not configured");
  setNodeText(els.environmentAutoStartMode, autoStartAllowed ? "Auto-start enabled" : "Auto-start disabled");
  setNodeText(
    els.environmentNote,
    "Manual Start/Resume can launch real workers and consume queues.",
  );
}

function showAuthOverlay(message = "") {
  if (authState.authDisabled || !authState.authEnabled || authState.authenticated) {
    if (els.page) els.page.classList.add("is-authenticated");
    if (els.authOverlay) els.authOverlay.hidden = true;
    if (els.authPanel) els.authPanel.hidden = true;
    if (els.authForm) els.authForm.hidden = true;
    if (els.authMessage) setNodeText(els.authMessage, "");
    return;
  }
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
  const authDisabled = nextState.authDisabled ?? authState.authDisabled;
  const authEnabled = authDisabled ? false : (nextState.authEnabled ?? authState.authEnabled);
  authState = {
    authEnabled,
    authDisabled,
    authenticated: authDisabled || !authEnabled || Boolean(nextState.authenticated),
    username: String(nextState.username || ""),
    dashboardMode: String(nextState.dashboardMode ?? authState.dashboardMode ?? "live"),
    autoStartAllowed: Boolean(nextState.autoStartAllowed ?? authState.autoStartAllowed),
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
    authDisabled: Boolean(data.auth_disabled),
    authenticated: Boolean(data.authenticated) || data.auth_enabled === false,
    username: data.username || "",
    dashboardMode: data.dashboard_mode || (data.auth_disabled ? "local_dev" : "live"),
    autoStartAllowed: Boolean(data.auto_start_allowed),
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
      authDisabled: Boolean(data.auth_disabled),
      authenticated: Boolean(data.authenticated) || data.auth_enabled === false,
      username: data.username || username,
      dashboardMode: data.dashboard_mode || (data.auth_disabled ? "local_dev" : "live"),
      autoStartAllowed: Boolean(data.auto_start_allowed),
    });
    showMessage(data.auth_disabled ? "Local dev auth disabled." : "Signed in.", "success");
    await bootstrapAuthenticatedDashboard();
  } catch (err) {
    setAuthState({ authEnabled: authState.authEnabled, authDisabled: authState.authDisabled, authenticated: false, username: "", message: String(err) });
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
  if (authState.authDisabled) {
    setAuthState({ authEnabled: false, authDisabled: true, authenticated: true, username: "admin" });
    showMessage("Local dev auth disabled.", "success");
    return;
  }
  stopSocket();
  setAuthState({ authEnabled: authState.authEnabled, authDisabled: false, authenticated: false, username: "" });
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

function readLeadWorkflowFromLocation() {
  const params = new URLSearchParams(window.location.search);
  return params.get("workflow") === "warm" ? "warm" : "cold";
}

function leadWorkflowUploadType(workflow = activeLeadWorkflow) {
  return workflow === "warm" ? "warm_research" : "cold";
}

function leadWorkflowFromUploadType(uploadType = "cold") {
  return String(uploadType || "").trim().toLowerCase() === "warm_research" ? "warm" : "cold";
}

function syncLocationState(historyMode = "replace") {
  const url = new URL(window.location.href);
  if (wallboardMode) {
    url.searchParams.set("view", "wallboard");
  } else {
    url.searchParams.delete("view");
  }
  if (activeDashboardTab === "leads" && !wallboardMode) {
    url.searchParams.set("tab", "leads");
    url.searchParams.set("workflow", activeLeadWorkflow);
  } else {
    url.searchParams.delete("tab");
    url.searchParams.delete("workflow");
  }
  const historyMethod = historyMode === "push" ? "pushState" : "replaceState";
  window.history[historyMethod]({}, "", url);
}

function insertAfterAnchor(anchor, node) {
  if (!anchor || !node || !anchor.parentNode) return;
  if (node.parentNode === anchor.parentNode && node.previousSibling === anchor) return;
  anchor.parentNode.insertBefore(node, anchor.nextSibling);
}

function ensureTabPanelMountAnchors() {
  if (tabPanelMounts.initialized) return;
  if (els.opsView?.parentNode) {
    tabPanelMounts.opsAnchor = document.createComment("ops-view-mount");
    els.opsView.parentNode.insertBefore(tabPanelMounts.opsAnchor, els.opsView);
  }
  if (els.leadsView?.parentNode) {
    tabPanelMounts.leadsAnchor = document.createComment("leads-view-mount");
    els.leadsView.parentNode.insertBefore(tabPanelMounts.leadsAnchor, els.leadsView);
  }
  tabPanelMounts.initialized = true;
}

function mountExclusiveDashboardPanel(leadsActive) {
  ensureTabPanelMountAnchors();
  if (leadsActive) {
    if (els.opsView?.isConnected) els.opsView.remove();
    insertAfterAnchor(tabPanelMounts.leadsAnchor, els.leadsView);
  } else {
    if (els.leadsView?.isConnected) els.leadsView.remove();
    insertAfterAnchor(tabPanelMounts.opsAnchor, els.opsView);
  }
}

function applyDashboardTab() {
  const leadsActive = activeDashboardTab === "leads" && !wallboardMode;
  mountExclusiveDashboardPanel(leadsActive);

  if (els.opsTabBtn) setNodeText(els.opsTabBtn, "Senders");
  if (els.leadsTabBtn) setNodeText(els.leadsTabBtn, "Lead Ops");

  if (els.opsView) {
    els.opsView.classList.toggle("hidden", leadsActive);
    els.opsView.hidden = leadsActive;
    els.opsView.setAttribute("aria-hidden", String(leadsActive));
    if (leadsActive) els.opsView.setAttribute("inert", "");
    else els.opsView.removeAttribute("inert");
  }

  if (els.leadsView) {
    els.leadsView.classList.toggle("hidden", !leadsActive);
    els.leadsView.hidden = !leadsActive;
    els.leadsView.setAttribute("aria-hidden", String(!leadsActive));
    if (!leadsActive) els.leadsView.setAttribute("inert", "");
    else els.leadsView.removeAttribute("inert");
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

  if (leadsActive) {
    initQuarantineInboxDisclosure();
    applyLeadWorkflowPage();
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

function applyLeadWorkflowPage() {
  const warmActive = activeLeadWorkflow === "warm";
  if (els.leadsImportantUploadType) {
    els.leadsImportantUploadType.value = leadWorkflowUploadType();
  }
  document.querySelectorAll("[data-leads-workflow]").forEach((link) => {
    const selected = link.getAttribute("data-leads-workflow") === activeLeadWorkflow;
    link.classList.toggle("is-active", selected);
    if (selected) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  if (els.leadsView) {
    els.leadsView.dataset.leadWorkflow = activeLeadWorkflow;
  }
  if (quarantineToggleBtn) {
    quarantineToggleBtn.hidden = warmActive;
  }
  if (warmActive) {
    closeQuarantineInbox();
  }
  applyWarmResearchLayoutState(warmActive);
  updateImportantLeadUploadNote(
    warmActive
      ? "Warm Outreach keeps validation, draft preparation, and explicit confirmation separate from cold dispatch."
      : "Cold Campaigns uses the existing check, triage, preview, and confirm workflow.",
  );
}

function setLeadWorkflow(nextWorkflow, { historyMode = "push" } = {}) {
  const next = nextWorkflow === "warm" ? "warm" : "cold";
  const changed = next !== activeLeadWorkflow;
  if (changed) {
    stopLeadsBackgroundActivity();
    if (els.leadsImportantUploadFile) {
      els.leadsImportantUploadFile.value = "";
    }
    activeLeadWorkflow = next;
    lastImportantLeadCheckJob = null;
    lastImportantVerifyJob = null;
    lastImportantDispatchJob = null;
  }
  activeDashboardTab = "leads";
  wallboardMode = false;
  applyDashboardTab();
  syncLocationState(historyMode);
  syncTabBackgroundActivity();
  renderLeadsStatus(lastLeadsStatus || {});
  if (changed || !lastLeadsStatus) {
    void fetchLeadsStatus();
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

function formatWarmActivity(timestamp, email = "") {
  if (!timestamp) return "No activity yet";
  const dt = new Date(timestamp);
  if (Number.isNaN(dt.getTime())) return email ? `${timestamp} · ${email}` : timestamp;
  const stamp = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(dt).replace(",", "");
  return `${stamp} UTC${email ? ` · ${email}` : ""}`;
}

function formatProfileName(value) {
  if (String(value || "") === "private_jc_warm") return "Warm Outreach";
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

function profilePendingCount(profile) {
  const value = Number(profile?.pending_count ?? profile?.pending ?? 0);
  return Number.isFinite(value) ? Math.max(0, value) : 0;
}

function queueSafetyCount(queueSafety, key) {
  const value = Number(queueSafety?.[key] ?? 0);
  return Number.isFinite(value) ? Math.max(0, value) : 0;
}

function queueSafetyVerifiedSubset(queueSafety) {
  if (!queueSafety || typeof queueSafety !== "object") return false;
  return Boolean(queueSafety.partial_consumption_verified)
    || (
      queueSafety.safe === true
      && queueSafetyCount(queueSafety, "expected_preview_unique_emails") > 0
      && queueSafetyCount(queueSafety, "missing_from_preview_expected_count") > 0
      && queueSafetyCount(queueSafety, "unaccounted_missing_from_preview_expected_count") === 0
      && queueSafetyCount(queueSafety, "extra_vs_preview_expected_count") === 0
      && queueSafetyCount(queueSafety, "live_already_sent_overlap_count") === 0
    );
}

function queueSafetyComplete(queueSafety) {
  if (!queueSafety || typeof queueSafety !== "object") return false;
  const expected = queueSafetyCount(queueSafety, "expected_preview_unique_emails");
  if (expected <= 0) return false;
  return queueSafety.safe === true
    && queueSafetyCount(queueSafety, "live_preview_unique_emails") === 0
    && queueSafetyCount(queueSafety, "accounted_missing_from_preview_expected_count") >= expected
    && queueSafetyCount(queueSafety, "unaccounted_missing_from_preview_expected_count") === 0
    && queueSafetyCount(queueSafety, "extra_vs_preview_expected_count") === 0
    && queueSafetyCount(queueSafety, "live_already_sent_overlap_count") === 0;
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

function activeSenderStateNames(snapshot = lastSnapshot) {
  const activeStates = ["starting", "running", "cooldown", "sleeping"];
  const stateMaps = [
    snapshot?.active_sender_states,
    snapshot?.active_states,
    snapshot?.sender_active_states,
  ].filter((value) => value && typeof value === "object" && !Array.isArray(value));
  return stateMaps.flatMap((states) => Object.entries(states)
    .filter(([, state]) => activeStates.includes(String(state || "").toLowerCase()))
    .map(([name]) => String(name || "").trim())
    .filter(Boolean));
}

function activeSenderProcessCount(snapshot = lastSnapshot) {
  const processLists = [
    snapshot?.active_sender_processes,
    snapshot?.sender_processes,
    snapshot?.running_sender_processes,
  ].filter(Array.isArray);
  return processLists.reduce((sum, processes) => sum + processes.length, 0);
}

function liveRecipientQueueCounts(status = lastLeadsStatus) {
  const privatePending = Number(status?.jc_queue?.count || 0);
  const sendgridPending = liveSendGridQueueTotal(status);
  return {
    privatePending,
    sendgridPending,
    total: privatePending + sendgridPending,
  };
}

function hasActualLiveQueueActivity(status = lastLeadsStatus, snapshot = lastSnapshot) {
  const counts = liveRecipientQueueCounts(status);
  return counts.total > 0
    || activeSenderProfiles(snapshot).length > 0
    || activeSenderStateNames(snapshot).length > 0
    || activeSenderProcessCount(snapshot) > 0;
}

function safeTimestampMs(value) {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function selectedLeadUploadType() {
  return leadWorkflowUploadType();
}

function reportUploadType(report = {}) {
  return String(report?.upload_type || report?.check?.upload_type || "cold").trim().toLowerCase() === "warm_research" ? "warm_research" : "cold";
}

function uploadTypeLabel(uploadType = selectedLeadUploadType()) {
  return uploadType === "warm_research" ? "Warm Research" : "Cold Leads";
}

function reportMatchesUploadType(report = {}, uploadType = selectedLeadUploadType()) {
  if (!report || typeof report !== "object") return false;
  return reportUploadType(report) === uploadType;
}

function currentImportantCheckJob(status = lastLeadsStatus, uploadType = selectedLeadUploadType()) {
  const workflowJobs = status?.active_important_check_jobs;
  const serverJob = workflowJobs && typeof workflowJobs === "object"
    ? workflowJobs[uploadType]
    : status?.active_important_check_job;
  return [serverJob, lastImportantLeadCheckJob]
    .find((job) => reportMatchesUploadType(job, uploadType)) || null;
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
      count: Number(status.jc_queue.count || 0),
    });
  }
  if (Array.isArray(status?.sendgrid_queues)) {
    status.sendgrid_queues.forEach((queue) => {
      queues.push({
        label: queue.profile || queue.name || queue.path || "sendgrid",
        fields: Array.isArray(queue.fieldnames) ? queue.fieldnames : [],
        count: Number(queue.count || 0),
      });
    });
  }
  const missing = queues
    .filter((queue) => Number(queue.count || 0) > 0 && !hasCaseInsensitiveField(queue.fields, "BookTitle"))
    .map((queue) => queue.label);
  return { checked: queues.length > 0, missing };
}

function leadsRunSafety(status = lastLeadsStatus, snapshot = lastSnapshot) {
  const backendCurrentSafety = status?.current_send_safety || {};
  const activeCheckJob = currentImportantCheckJob(status);
  const leadCheck = currentLeadCheckStatus(status);
  const checkRunning = leadCheckWorkflowStatus(leadCheck) === "running";
  const activeSenders = activeSenderProfiles(snapshot);
  const latestCheck = selectedLeadCheckReport(status);
  const latestTriage = selectedLeadTriageReport(status, leadCheck);
  const latestPreview = selectedLeadUploadType() === "cold" ? (status?.latest_auto_dispatch_preview || {}) : {};
  const latestCheckTime = safeTimestampMs(latestCheck.generated_at_utc);
  const latestTriageTime = safeTimestampMs(latestTriage.generated_at_utc);
  const previewTime = safeTimestampMs(latestPreview.generated_at_utc || latestPreview.completed_at_utc || latestPreview.created_at_utc);
  const backendQueueUnsafe = Object.prototype.hasOwnProperty.call(backendCurrentSafety, "blocked")
    ? Boolean(backendCurrentSafety.blocked)
    : queueSafetyBlocked(snapshot);
  const hasLiveActivity = hasActualLiveQueueActivity(status, snapshot);
  const backendReasons = Array.isArray(backendCurrentSafety.reasons)
    ? backendCurrentSafety.reasons.map((reason) => String(reason || "")).filter(Boolean)
    : [];
  const sourceWarningOnly = backendQueueUnsafe && (
    sourceComparisonOnlySafety(backendCurrentSafety)
    || backendReasons.every((reason) => isSourceComparisonSafetyReason(reason))
  );
  const queueUnsafe = backendQueueUnsafe && hasLiveActivity && !sourceWarningOnly;
  const queueWarnings = backendQueueUnsafe && !queueUnsafe ? backendReasons : [];
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
  if (queueUnsafe && backendReasons.length) {
    reasons.push(...backendReasons);
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
    queueWarnings,
    hasLiveActivity,
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

function currentLeadOpsProgress(status = lastLeadsStatus, uploadType = selectedLeadUploadType()) {
  const workflowProgress = status?.lead_ops_progress_by_workflow;
  const progress = workflowProgress && typeof workflowProgress === "object"
    ? workflowProgress[uploadType]
    : status?.lead_ops_progress;
  if (!progress || typeof progress !== "object") return {};
  const selectedType = String(progress.selected_upload_type || "cold").toLowerCase();
  const expectedType = uploadType === "warm_research" ? "warm_research" : "cold";
  if (selectedType && selectedType !== expectedType) return {};
  if (!String(progress.job_id || "").trim()) return {};
  return progress;
}

function leadOpsProgressCopy(phase) {
  const normalized = String(phase || "").toLowerCase();
  const copy = {
    upload_received: "Upload received",
    checking: "Checking leads",
    triaging: "Fast triage",
    ready_for_preview: "Ready for preview",
    previewing: "Previewing dispatch",
    preview_complete: "Preview complete",
    confirming: "Confirming dispatch",
    confirm_complete: "Confirm complete",
    failed: "Failed",
    stale: "Stale",
  };
  return copy[normalized] || "Upload received";
}

function leadOpsProgressAsCheckStatus(progress = {}) {
  const phase = String(progress.phase || progress.status || "upload_received").toLowerCase();
  const label = leadOpsProgressCopy(phase);
  const rowCounts = progress.row_counts && typeof progress.row_counts === "object" ? progress.row_counts : {};
  const progressRows = Number(progress.processed_rows || 0);
  const completedCheckPhase = ["ready_for_preview", "previewing", "preview_complete"].includes(phase);
  const cleanedRows = Number(rowCounts.cleaned_rows ?? progress.cleaned_rows ?? (completedCheckPhase ? progressRows : 0));
  const rejectedRows = Number(rowCounts.rejected_rows ?? progress.rejected_rows ?? 0);
  const outputExists = Object.prototype.hasOwnProperty.call(progress, "output_exists")
    ? Boolean(progress.output_exists)
    : Boolean(progress.output_path);
  const rejectedExists = Object.prototype.hasOwnProperty.call(progress, "rejected_exists")
    ? Boolean(progress.rejected_exists)
    : Boolean(progress.rejected_path);
  const failed = ["failed", "stale"].includes(phase);
  const processing = ["upload_received", "checking", "triaging", "previewing", "confirming"].includes(phase);
  const previewReady = ["ready_for_preview", "preview_complete"].includes(phase) && cleanedRows > 0 && outputExists && rejectedExists;
  const state = failed ? phase : previewReady ? "success" : processing ? "processing" : "not_ready";
  const guidance = failed
    ? "Do not preview. Re-upload a clean lead CSV and run Upload & Check again."
      : phase === "ready_for_preview"
      ? "Success: review counts, then Preview Dispatch."
      : phase === "preview_complete"
        ? "Preview complete: review safety before Confirm."
        : phase === "confirm_complete"
          ? "Confirm complete."
        : "Processing: wait.";
  return {
    state,
    label,
    message: String(progress.current_message || label),
    guidance,
    preview_ready: previewReady,
    preview_state: previewReady ? "ready" : "not_ready",
    preview_label: previewReady ? "Ready for preview" : "Not ready for preview",
    preview_block_reason: previewReady ? "" : failed ? "Check failed or stale: no cleaned/rejected output files were produced." : "Lead check is still processing.",
    cleaned_rows: cleanedRows,
    rejected_rows: rejectedRows,
    output_exists: outputExists,
    rejected_exists: rejectedExists,
    latest_master_check_matches_current_run: Boolean(progress.latest_master_check_matches_current_run ?? previewReady),
    generated_at_utc: progress.completed_at_utc || "",
    upload_received_at_utc: progress.started_at_utc || "",
    updated_at_utc: progress.updated_at_utc || "",
    stale_age_seconds: progress.stale_age_seconds,
    current_run_id: progress.current_run_id || "",
    check_job_id: progress.job_id || "",
    job_id: progress.job_id || "",
    input_path: progress.input_path || "",
    selected_filename: pathDisplayName(progress.input_path || ""),
    progress_percent: progress.percent,
    processed_rows: progress.processed_rows,
    total_rows: progress.total_rows,
    elapsed_seconds: progress.elapsed_seconds,
    eta_seconds: progress.eta_seconds,
    stale_warning: progress.stale_warning,
    stale_reason: progress.stale_reason || "",
    last_successful_step: progress.last_successful_step || "",
    retry_safe: progress.retry_safe,
    reupload_required: progress.reupload_required,
    input_exists: progress.input_exists,
    job_record_exists: progress.job_record_exists,
    phase,
    current_message: progress.current_message || label,
    error_summary: progress.error_summary || "",
    confirm_ready: false,
    tone: failed ? "bad" : processing ? "active" : previewReady ? "good" : "wait",
    lead_ops_progress: progress,
  };
}

function currentLeadCheckStatus(status = lastLeadsStatus) {
  const uploadType = selectedLeadUploadType();
  const progress = currentLeadOpsProgress(status, uploadType);
  if (progress?.job_id) {
    const progressPhase = String(progress.phase || progress.status || "").toLowerCase();
    if (["confirming", "confirm_complete"].includes(progressPhase) && status?.lead_check_status) {
      return {
        ...status.lead_check_status,
        lead_ops_progress: progress,
        phase: progressPhase,
        current_message: progress.current_message || leadOpsProgressCopy(progressPhase),
      };
    }
    const progressStatus = leadOpsProgressAsCheckStatus(progress);
    if (progressStatus.state !== "success" || !status?.lead_check_status?.preview_ready) {
      return progressStatus;
    }
  }
  const check = status?.lead_check_status;
  if (uploadType === "cold" && check && typeof check === "object") {
    const selectedReport = selectedLeadCheckReport(status, uploadType);
    const warmReport = status?.latest_warm_check;
    if (!selectedReport?.generated_at_utc && warmReport?.generated_at_utc) {
      return selectedModeLeadCheckStatus(status, uploadType);
    }
    return check;
  }
  return selectedModeLeadCheckStatus(status, uploadType);
}

function selectedLeadCheckReport(status = lastLeadsStatus, uploadType = selectedLeadUploadType()) {
  const report = uploadType === "warm_research" ? status?.current_warm_check : status?.latest_master_check;
  if (report?.generated_at_utc && reportMatchesUploadType(report, uploadType)) return report;
  return {};
}

function selectedLeadTriageReport(status = lastLeadsStatus, check = currentLeadCheckStatus(status)) {
  if (selectedLeadUploadType() === "warm_research") return {};
  if (leadCheckWorkflowStatus(check) !== "completed") return {};
  const triage = status?.latest_lead_triage || status?.latest_lead_verify || {};
  const selectedCheck = selectedLeadCheckReport(status);
  const checkTime = safeTimestampMs(selectedCheck.generated_at_utc);
  const triageTime = safeTimestampMs(triage.generated_at_utc);
  if (checkTime && (!triageTime || triageTime < checkTime)) return {};
  return triage;
}

function selectedModeLeadCheckStatus(status = lastLeadsStatus, uploadType = selectedLeadUploadType()) {
  const selectedReport = selectedLeadCheckReport(status, uploadType);
  const activeJob = currentImportantCheckJob(status, uploadType);
  const otherReport = uploadType === "warm_research" ? status?.latest_master_check : status?.latest_warm_check;
  if (selectedReport?.generated_at_utc) {
    const cleanedRows = Number(selectedReport.cleaned_rows || selectedReport.output_rows || selectedReport.warm_email_ready_rows || 0);
    const rejectedRows = Number(selectedReport.rejected_rows || selectedReport.warm_rejected_rows || Math.max(0, Number(selectedReport.input_rows || 0) - cleanedRows) || 0);
    return {
      state: cleanedRows > 0 ? "success" : "not_ready",
      label: cleanedRows > 0 ? "Success — ready for Preview Dispatch" : "Not ready for preview",
      message: cleanedRows > 0 ? `${uploadTypeLabel(uploadType)} check is current for the selected upload type.` : `${uploadTypeLabel(uploadType)} check has no valid rows.`,
      guidance: cleanedRows > 0 ? "Success: review counts, then Preview Dispatch." : "Not ready for preview: re-upload clean source.",
      preview_ready: cleanedRows > 0 && uploadType === "cold",
      preview_state: cleanedRows > 0 && uploadType === "cold" ? "ready" : "not_ready",
      preview_label: cleanedRows > 0 && uploadType === "cold" ? "Ready for preview" : "Not ready for preview",
      preview_block_reason: uploadType === "warm_research" ? "Warm Research does not use Cold Dispatch Preview." : "",
      cleaned_rows: cleanedRows,
      rejected_rows: rejectedRows,
      output_exists: true,
      rejected_exists: true,
      latest_master_check_matches_current_run: true,
      generated_at_utc: selectedReport.generated_at_utc,
      current_run_id: selectedReport.current_run_id || selectedReport.run_id || selectedReport.check_run_id || "",
      input_path: selectedReport.input_path || selectedReport.source_path || "",
      check_job_id: selectedReport.check_job_id || selectedReport.job_id || "",
      confirm_ready: false,
      tone: cleanedRows > 0 ? "good" : "warn",
    };
  }
  if (activeJob?.job_id) {
    const terminal = isTerminalImportantLeadCheckJob(activeJob);
    const failed = ["failed", "canceled", "cancelled"].includes(importantLeadCheckJobStatus(activeJob));
    const state = failed || terminal ? "stale" : "processing";
    const selectedFilename = activeJob.selected_filename || activeJob.original_uploaded_filename || activeJob.server_received_filename || activeJob.source_label || "";
    return {
      state,
      label: state === "processing" ? "Checking…" : "Failed/Stale — check did not produce outputs",
      message: state === "processing" ? "Waiting for check output files." : "No completed check output is available for this job.",
      guidance: state === "processing" ? "Processing: wait. This may take a moment." : "Do not preview. Re-upload a clean lead CSV and run Upload & Check again.",
      preview_ready: false,
      preview_state: "not_ready",
      preview_label: "Not ready for preview",
      preview_block_reason: state === "processing" ? "Lead check is still processing." : "Check failed or stale: no cleaned/rejected output files were produced.",
      cleaned_rows: 0,
      rejected_rows: 0,
      output_exists: false,
      rejected_exists: false,
      latest_master_check_matches_current_run: false,
      check_job_id: activeJob.job_id,
      current_run_id: activeJob.current_run_id || activeJob.run_id || activeJob.check_run_id || "",
      input_path: activeJob.input_path || activeJob.source_path || activeJob.server_path || "",
      selected_filename: selectedFilename,
      updated_at_utc: activeJob.updated_at_utc || activeJob.started_at_utc || activeJob.created_at_utc || "",
      progress_percent: activeJob.progress_percent,
      confirm_ready: false,
      tone: state === "processing" ? "active" : "bad",
    };
  }
  if (otherReport?.generated_at_utc) {
    return {
      state: "mismatch",
      label: "Check state mismatch",
      message: "Latest check result does not match the selected upload type.",
      guidance: "Do not preview. Rerun Upload & Check for the selected upload type.",
      preview_ready: false,
      preview_state: "not_ready",
      preview_label: "Not ready for preview",
      preview_block_reason: "Check state mismatch: rerun Upload & Check for the selected upload type.",
      cleaned_rows: 0,
      rejected_rows: 0,
      output_exists: false,
      rejected_exists: false,
      latest_master_check_matches_current_run: false,
      confirm_ready: false,
      tone: "warn",
    };
  }
  return {
    state: "not_started",
    label: "Not started",
    message: `${uploadTypeLabel(uploadType)} check has not started.`,
    guidance: "Not ready for preview: run Upload & Check for the selected upload type.",
    preview_ready: false,
    preview_state: "not_ready",
    preview_label: "Not ready for preview",
    preview_block_reason: "No current check is ready for the selected upload type.",
    cleaned_rows: 0,
    rejected_rows: 0,
    output_exists: false,
    rejected_exists: false,
    latest_master_check_matches_current_run: false,
    confirm_ready: false,
    tone: "wait",
  };
}

function leadCheckWorkflowStatus(check = currentLeadCheckStatus()) {
  const state = String(check?.state || "").toLowerCase();
  if (state === "success") return "completed";
  if (state === "processing" || state === "upload_received") return "running";
  if (["failed", "stale", "mismatch"].includes(state)) return "failed";
  return "pending";
}

function leadCheckBlocksPreview(check = currentLeadCheckStatus()) {
  if (!check || !check.state) return "";
  if (check.preview_ready === true || String(check.preview_state || "").toLowerCase() === "ready") return "";
  return String(check.preview_block_reason || check.message || "Lead check is not ready for preview.");
}

function leadCheckStatusTone(check = currentLeadCheckStatus()) {
  const tone = String(check?.tone || "").toLowerCase();
  if (["good", "bad", "warn", "active", "wait"].includes(tone)) return tone;
  const state = String(check?.state || "").toLowerCase();
  if (state === "success") return "good";
  if (["failed", "stale"].includes(state)) return "bad";
  if (state === "mismatch" || state === "not_ready") return "warn";
  if (state === "processing" || state === "upload_received") return "active";
  return "wait";
}

function renderLeadCheckStatusCard(status = lastLeadsStatus) {
  if (!els.leadCheckStatusCard) return;
  const check = currentLeadCheckStatus(status);
  const state = String(check.state || "not_started");
  const tone = leadCheckStatusTone(check);
  const label = check.label || "Not started";
  const message = check.message || "No upload/check output is ready yet.";
  const guidance = check.guidance || "Not ready for preview: upload a lead CSV and run Upload & Check.";
  const uploadTime = check.upload_received_at_utc || check.upload_received_at ? formatGeneratedAt(check.upload_received_at_utc || check.upload_received_at) : "Not recorded";
  const generatedTime = check.generated_at_utc ? formatGeneratedAt(check.generated_at_utc) : "Not generated";
  const staleSeconds = Number(check.stale_age_seconds ?? check.stale_seconds);
  const staleCopy = Number.isFinite(staleSeconds) && staleSeconds >= 0 ? humanizeDurationCompact(staleSeconds) : "";
  const cleanedRows = Number(check.cleaned_rows || 0);
  const rejectedRows = Number(check.rejected_rows || 0);
  const previewLabel = check.preview_label || (check.preview_ready ? "Ready for preview" : "Not ready for preview");
  const outputStatus = check.output_exists ? "exists" : "missing";
  const rejectedStatus = check.rejected_exists ? "exists" : "missing";
  const matchStatus = check.latest_master_check_matches_current_run ? "yes" : "no";
  const jobId = check.check_job_id || check.job_id || "-";
  const currentRunId = check.current_run_id || check.run_id || "-";
  const selectedFile = check.selected_filename || pathDisplayName(check.input_path || check.current_input_path || check.input_label || "");
  const progress = check.lead_ops_progress || currentLeadOpsProgress(status);
  const progressValue = Number(check.progress_percent ?? progress?.percent);
  const hasProgressPercent = Object.prototype.hasOwnProperty.call(progress || {}, "percent") && Number.isFinite(progressValue);
  const safeProgressPercent = hasProgressPercent ? Math.min(100, Math.max(0, progressValue)) : 0;
  const progressPhase = String(progress?.phase || check.phase || state || "").toLowerCase();
  const progressPhaseLabel = leadOpsProgressCopy(progressPhase);
  const processedRows = Number(check.processed_rows ?? progress?.processed_rows);
  const totalRows = Number(check.total_rows ?? progress?.total_rows);
  const progressRowsCopy = Number.isFinite(processedRows) && Number.isFinite(totalRows) && totalRows > 0
    ? `${processedRows.toLocaleString()} / ${totalRows.toLocaleString()} rows`
    : "";
  const progressUpdated = progress?.updated_at_utc || check.updated_at_utc || "";
  const elapsedSeconds = Number(check.elapsed_seconds ?? progress?.elapsed_seconds);
  const etaSeconds = Number(check.eta_seconds ?? progress?.eta_seconds);
  const elapsedCopy = Number.isFinite(elapsedSeconds) && elapsedSeconds >= 0 ? humanizeDurationCompact(elapsedSeconds) : "";
  const etaCopy = Number.isFinite(etaSeconds) && etaSeconds > 0 ? humanizeDurationCompact(etaSeconds) : "";
  const staleWarning = String(
    check.stale_warning || progress?.stale_warning || (progressPhase === "stale" ? LEAD_OPS_PROGRESS_STALE_WARNING : ""),
  ).trim();
  const progressMessage = String(check.current_message || progress?.current_message || "").trim();
  const progressError = String(check.error_summary || progress?.error_summary || "").trim();
  const lastSuccessfulStep = String(check.last_successful_step || progress?.last_successful_step || "").trim();
  const reuploadRequired = check.reupload_required ?? progress?.reupload_required;
  const hasProgressJob = Boolean(progress?.job_id || check.job_id || check.check_job_id);
  const processing = ["processing", "upload_received", "checking", "running", "queued"].includes(state.toLowerCase());
  const processingStrip = processing
    ? `
      <div class="lead-check-processing-strip" role="status">
        <span>${hasProgressPercent ? `${safeProgressPercent.toFixed(0)}%` : "Checking source…"}</span>
        <strong>${hasProgressPercent ? escapeHtml(progressPhaseLabel) : "Waiting for output files…"}</strong>
        <em>This may take a moment.</em>
      </div>
    `
    : "";
  const progressModule = hasProgressJob
    ? `
      <div class="lead-ops-progress-module lead-ops-progress-${escapeHtml(progressPhase || "idle")}" role="status">
        <div class="lead-ops-progress-head">
          <div>
            <span>Lead Ops progress</span>
            <strong>${escapeHtml(progressPhaseLabel)}</strong>
          </div>
          ${hasProgressPercent ? `<b><span>Percent complete</span>${safeProgressPercent.toFixed(0)}%</b>` : `<b>Active</b>`}
        </div>
        ${hasProgressPercent ? `
          <div class="lead-ops-progress-track" role="progressbar" aria-label="${escapeHtml(progressPhaseLabel)} progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${safeProgressPercent.toFixed(0)}">
            <i style="width:${safeProgressPercent}%"></i>
          </div>
        ` : ""}
        <div class="lead-ops-progress-meta">
          ${progressRowsCopy ? `<span>${escapeHtml(progressRowsCopy)}</span>` : ""}
          <span title="${escapeHtml(jobId)}">Job ${escapeHtml(jobId)}</span>
          ${progressUpdated ? `<span>Updated ${escapeHtml(formatGeneratedAt(progressUpdated))}</span>` : ""}
          ${elapsedCopy ? `<span>Elapsed ${escapeHtml(elapsedCopy)}</span>` : ""}
          ${etaCopy ? `<span>ETA ${escapeHtml(etaCopy)}</span>` : ""}
          ${selectedFile ? `<span title="${escapeHtml(selectedFile)}">${escapeHtml(selectedFile)}</span>` : ""}
        </div>
        ${staleWarning ? `<div class="lead-ops-progress-warning">${escapeHtml(staleWarning)}</div>` : ""}
        ${progressMessage ? `<p>${escapeHtml(progressMessage)}</p>` : ""}
        ${progressError && progressError !== progressMessage ? `<p class="lead-ops-progress-error">${escapeHtml(progressError)}</p>` : ""}
      </div>
    `
    : "";
  els.leadCheckStatusCard.className = `lead-check-status-card lead-check-status-card-${tone}`;
  setNodeHtml(
    els.leadCheckStatusCard,
    `
      <div class="lead-check-status-head">
        <div>
          <p class="eyebrow">Lead Check Status</p>
          <strong>${escapeHtml(label)}</strong>
          <span>${escapeHtml(message)}</span>
        </div>
        <span class="mini-pill">${escapeHtml(previewLabel)}</span>
      </div>
      ${processingStrip}
      ${progressModule}
      <div class="lead-check-guidance lead-check-guidance-${escapeHtml(state)}">${escapeHtml(guidance)}</div>
      <details class="lead-check-details">
        <summary>Check details</summary>
        <div class="lead-check-status-grid">
          <div><span>Selected file</span><strong title="${escapeHtml(selectedFile || "-")}">${escapeHtml(selectedFile || "-")}</strong></div>
          <div><span>Current job</span><strong title="${escapeHtml(jobId)}">${escapeHtml(jobId)}</strong></div>
          <div><span>Current run</span><strong title="${escapeHtml(currentRunId)}">${escapeHtml(currentRunId)}</strong></div>
          <div><span>leads.csv</span><strong>${escapeHtml(outputStatus)}</strong></div>
          <div><span>leads_rejected.csv</span><strong>${escapeHtml(rejectedStatus)}</strong></div>
          <div><span>Latest matches current upload</span><strong>${escapeHtml(matchStatus)}</strong></div>
          <div><span>Cleaned rows</span><strong>${cleanedRows.toLocaleString()}</strong></div>
          <div><span>Rejected rows</span><strong>${rejectedRows.toLocaleString()}</strong></div>
          <div><span>Upload received</span><strong>${escapeHtml(uploadTime)}</strong></div>
          <div><span>Check generated</span><strong>${escapeHtml(generatedTime)}</strong></div>
          ${staleCopy ? `<div><span>Stale age</span><strong>${escapeHtml(staleCopy)}</strong></div>` : ""}
          ${lastSuccessfulStep ? `<div><span>Last successful step</span><strong>${escapeHtml(lastSuccessfulStep)}</strong></div>` : ""}
          ${typeof reuploadRequired === "boolean" ? `<div><span>Re-upload required</span><strong>${reuploadRequired ? "yes" : "no"}</strong></div>` : ""}
        </div>
      </details>
    `,
  );
}

function dispatchActionBlockReason() {
  const safety = leadsRunSafety();
  const checkBlock = leadCheckBlocksPreview();
  if (checkBlock) return checkBlock;
  if (safety.checkRunning) {
    return `Check Leads is running for job ${safety.checkJobId}. Wait until leads.csv, triage, and preview are fresh.`;
  }
  if (safety.activeSenders.length) {
    return `Active senders are running: ${safety.activeSenders.map((profile) => `${formatProfileName(profile.name)} (${profile.runtime_state})`).join(", ")}.`;
  }
  return "";
}

function dispatchPreviewActionBlockReason() {
  return dispatchActionBlockReason();
}

function dispatchPreviewBlockReason(dispatchSource = {}) {
  const actionBlock = dispatchPreviewActionBlockReason();
  if (actionBlock) return actionBlock;
  if (dispatchSource.dispatch_block_reason) return String(dispatchSource.dispatch_block_reason);
  if (!dispatchSource.dispatch_source_path) return "No triage keep source is selected or the source is missing.";
  const sourceMode = String(dispatchSource.dispatch_source_mode || "").toLowerCase();
  const sourceName = String(dispatchSource.dispatch_source_name || "").toLowerCase();
  const triageSourceSelected = sourceMode === "triaged_keep" || sourceName.includes("triage");
  if (dispatchSource.dispatch_source_exists === false) {
    return triageSourceSelected
      ? "Triage not ready: leads_triaged_keep.csv is missing. Run Fast Triage after Check Leads completes."
      : "Selected dispatch source is missing. Retry after the source is generated.";
  }
  if (Number(dispatchSource.dispatch_source_row_count || 0) <= 0) {
    return triageSourceSelected
      ? "Triage not ready: leads_triaged_keep.csv has no Keep rows. Review/Quarantine rows are not dispatched automatically."
      : "Dispatch source is empty. Retry after the source has accepted rows.";
  }
  if (Number(dispatchSource.dispatch_eligible_row_count || 0) <= 0) {
    return "No eligible rows are available for preview. Rows may already be contacted, already sent, suppressed, invalid, or excluded.";
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

function selectedImportantDispatchCampaignType() {
  return els.leadsImportantDispatchCampaignType?.value || "cold";
}

function selectedImportantDispatchSourceMode(campaignType = selectedImportantDispatchCampaignType()) {
  if (campaignType === "recontact_cold") return "cleaned";
  const selectedMode = els.leadsImportantDispatchSourceMode?.value || "triaged_keep";
  if (selectedMode === "strict_verified") return "strict_verified";
  if (selectedMode === "cleaned") return "cleaned";
  return "triaged_keep";
}

function syncImportantDispatchCampaignSource() {
  const sourceSelect = els.leadsImportantDispatchSourceMode;
  if (!sourceSelect) return;
  if (selectedImportantDispatchCampaignType() === "recontact_cold") {
    sourceSelect.value = "cleaned";
    sourceSelect.disabled = true;
    sourceSelect.title = "Recontact previews from the checked upload output.";
    return;
  }
  sourceSelect.disabled = false;
  sourceSelect.title = "";
  if (sourceSelect.value === "cleaned") sourceSelect.value = "triaged_keep";
}

function currentDispatchPlanKey() {
  const selected = dispatchSourceForSelectedMode();
  const source = selected.source || {};
  return [
    selectedImportantDispatchSourceMode(),
    String(source.dispatch_source_path || ""),
    String(source.dispatch_source_exists ?? ""),
    String(source.dispatch_source_row_count ?? ""),
    String(source.dispatch_eligible_row_count ?? ""),
    String(source.verification_file_mtime || ""),
    els.leadsImportantDispatchCap?.value || "all",
    selectedImportantDispatchCampaignType(),
  ].join("|");
}

function dispatchPreviewMatchesCurrentSelection() {
  return Boolean(lastImportantDispatchPreview && lastImportantDispatchPreview._preview_key === currentDispatchPlanKey());
}

function persistedImportantDispatchPreviewKey(preview) {
  if (!preview?.preview_id) return "";
  return [
    String(preview.dispatch_source_mode || ""),
    String(preview.dispatch_source_path || ""),
    String(preview.dispatch_source_exists ?? ""),
    String(preview.dispatch_source_row_count ?? ""),
    String(preview.dispatch_eligible_row_count ?? ""),
    String(preview.verification_file_mtime || ""),
    String(preview.dispatch_cap || "all"),
    String(preview.campaign_type || "cold"),
  ].join("|");
}

function hydrateImportantDispatchPreviewFromStatus(status = lastLeadsStatus) {
  if (selectedLeadUploadType() !== "cold") return false;

  const preview = status?.latest_auto_dispatch_preview || null;
  const persistedKey = persistedImportantDispatchPreviewKey(preview);
  const currentKey = currentDispatchPlanKey();

  if (!persistedKey) {
    lastImportantDispatchPreview = null;
    return false;
  }

  lastImportantDispatchPreview = { ...(preview || {}), _preview_key: persistedKey };
  if (persistedKey !== currentKey) return false;

  lastImportantDispatchPreviewState = "ready";
  lastImportantDispatchPreviewFeedback = {
    state: "ready",
    message: "Preview ready.",
  };
  return true;
}

function dispatchSummaryMatchesCurrentSource(dispatch = lastImportantDispatch) {
  if (!dispatch?.generated_at_utc) return false;
  const selected = dispatchSourceForSelectedMode();
  const selectedPath = String(selected?.source?.dispatch_source_path || "").trim();
  const dispatchPath = String(dispatch.dispatch_source_path || "").trim();
  return Boolean(selectedPath && dispatchPath && selectedPath === dispatchPath);
}

function currentDispatchConfirmed(dispatch = lastImportantDispatch) {
  return Boolean(dispatch?.generated_at_utc && dispatchSummaryMatchesCurrentSource(dispatch));
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
    dispatch_source_mode: selectedImportantDispatchSourceMode(),
    input_text: els.leadsImportantInputText?.value || "",
  };
}

function importantLeadDispatchPayload(includePreviewId = false) {
  const campaignType = selectedImportantDispatchCampaignType();
  const payload = {
    input_path: els.leadsImportantInputPath?.value?.trim() || "",
    output_path: els.leadsImportantOutputPath?.value?.trim() || "",
    rejected_path: els.leadsImportantRejectedPath?.value?.trim() || "",
    dispatch_source_mode: selectedImportantDispatchSourceMode(campaignType),
    dispatch_cap: els.leadsImportantDispatchCap?.value || "all",
    campaign_type: campaignType,
    recontact_recency_override: Boolean(els.leadsRecontactRecencyOverride?.checked),
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
  formData.append("upload_type", selectedLeadUploadType());
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

function importantLeadCheckStorageKey(uploadType = selectedLeadUploadType()) {
  return `${IMPORTANT_LEAD_CHECK_JOB_STORAGE_KEY}.${leadWorkflowFromUploadType(uploadType)}`;
}

function readSavedImportantLeadCheckJobId(uploadType = selectedLeadUploadType()) {
  try {
    return String(localStorage.getItem(importantLeadCheckStorageKey(uploadType)) || "").trim();
  } catch (err) {
    return "";
  }
}

function saveImportantLeadCheckJobId(jobId, uploadType = selectedLeadUploadType()) {
  const cleanJobId = String(jobId || "").trim();
  if (!cleanJobId) return;
  try {
    localStorage.setItem(importantLeadCheckStorageKey(uploadType), cleanJobId);
  } catch (err) {
    // localStorage may be unavailable in private or restricted browser contexts.
  }
}

function clearSavedImportantLeadCheckJobId(jobId = "", uploadType = selectedLeadUploadType()) {
  const cleanJobId = String(jobId || "").trim();
  try {
    const storageKey = importantLeadCheckStorageKey(uploadType);
    const savedJobId = readSavedImportantLeadCheckJobId(uploadType);
    if (!cleanJobId || !savedJobId || savedJobId === cleanJobId) {
      localStorage.removeItem(storageKey);
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
  const jobUploadType = reportUploadType(job);
  if (jobUploadType !== selectedLeadUploadType()) {
    if (isActiveImportantLeadCheckJob(job)) {
      saveImportantLeadCheckJobId(job.job_id, jobUploadType);
    }
    return;
  }
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
    saveImportantLeadCheckJobId(job.job_id, jobUploadType);
  } else if (isTerminalImportantLeadCheckJob(job)) {
    clearSavedImportantLeadCheckJobId(job.job_id, jobUploadType);
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
            <span class="mini-pill">Upload type ${escapeHtml(job.upload_type_label || (job.upload_type === "warm_research" ? "Warm Research" : "Cold Leads"))}</span>
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

async function pollImportantLeadCheckJob(jobId, expectedUploadType = selectedLeadUploadType()) {
  if (!jobId) return;
  stopImportantLeadCheckJobPolling();
  importantLeadCheckJobPollId = String(jobId);
  try {
    const data = await fetchJson(`/api/leads/check-important/job/${encodeURIComponent(jobId)}`);
    const job = data.job || {};
    renderImportantLeadCheckJob(job);
    if (job.status === "completed") {
      stopImportantLeadCheckJobPolling();
      const jobUploadType = reportUploadType(job);
      clearSavedImportantLeadCheckJobId(job.job_id || jobId, jobUploadType);
      if (jobUploadType !== selectedLeadUploadType()) {
        return;
      }
      lastImportantLeadCheck = job.check || null;
      if (data.status) {
        renderLeadsStatus(data.status || {});
      }
      if (job.upload_type === "warm_research") {
        renderImportantLeadCheck(lastImportantLeadCheck);
      } else if (!data.status) {
        renderImportantLeadCheck(lastImportantLeadCheck);
      }
      showMessage(job.message || "Upload check complete.", "success");
      return;
    }
    if (job.status === "failed" || job.status === "canceled" || job.status === "cancelled") {
      stopImportantLeadCheckJobPolling();
      clearSavedImportantLeadCheckJobId(job.job_id || jobId, reportUploadType(job));
      showMessage(job.error || "Upload check failed.", "error");
      return;
    }
    importantLeadCheckJobTimer = setTimeout(() => pollImportantLeadCheckJob(jobId, expectedUploadType), 1500);
  } catch (err) {
    if (String(err || "").includes("not found")) {
      clearSavedImportantLeadCheckJobId(jobId, expectedUploadType);
      stopImportantLeadCheckJobPolling();
      return;
    }
    showMessage(`Upload job poll failed: ${err}`, "error");
    importantLeadCheckJobTimer = setTimeout(() => pollImportantLeadCheckJob(jobId, expectedUploadType), 2500);
  }
}

function resumeImportantLeadCheckJob(job) {
  if (job?.job_id && !reportMatchesUploadType(job, selectedLeadUploadType())) {
    return false;
  }
  if (!isActiveImportantLeadCheckJob(job)) {
    if (isTerminalImportantLeadCheckJob(job)) {
      clearSavedImportantLeadCheckJobId(job?.job_id || "");
    }
    return false;
  }
  renderImportantLeadCheckJob(job);
  const jobId = String(job.job_id || "");
  if (importantLeadCheckJobPollId !== jobId) {
    void pollImportantLeadCheckJob(jobId, reportUploadType(job));
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
    setButtonBusy(els.leadsImportantDispatchConfirmBtn, active, active ? "Dispatching..." : importantDispatchConfirmButtonLabel());
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
  const warmUploadSelected = warmResearchUploadMode();
  const sourceBlocked = Boolean(dispatchSource.dispatch_block_reason);
  const activeDispatch = isActiveImportantLeadCheckJob(lastImportantDispatchJob);
  const previewBlockReason = dispatchPreviewBlockReason(dispatchSource);
  const previewReady = dispatchPreviewMatchesCurrentSelection();
  const previewBlocked = !preview || !previewReady;
  const safety = dispatchConfirmSafetyState(dispatchSource, preview);
  const previewButtons = [els.leadsImportantDispatchPreviewBtn, els.leadsImportantDispatchPreviewTopBtn].filter(Boolean);
  if (previewButtons.length) {
    const previewBusy = Boolean((importantLeadDispatchPreviewLoading && !previewReady) || activeDispatch);
    previewButtons.forEach((button) => {
      button.disabled = previewBusy || Boolean(previewBlockReason) || warmUploadSelected;
      button.title = warmUploadSelected
        ? "Warm Research uses its own draft, confirmation, and Private JC lane. Cold Dispatch Preview is disabled."
        : (previewBlockReason || "");
      if (!previewBusy) {
        const retryState = lastImportantDispatchPreviewFeedback?.state === "failed" && previewBlocked;
        setNodeText(button, previewBlockReason ? "Preview locked" : retryState ? "Retry Preview Dispatch" : "Preview Dispatch");
      }
      button.classList.toggle(
        "is-next-action",
        previewBlocked && !button.disabled,
      );
      button.classList.toggle("is-locked", Boolean(button.disabled || previewBlockReason || warmUploadSelected));
    });
  }
  if (els.leadsImportantDispatchConfirmBtn) {
    const confirmBusy = Boolean(importantLeadDispatchConfirmLoading || activeDispatch);
    els.leadsImportantDispatchConfirmBtn.disabled = confirmBusy || Boolean(previewBlockReason) || !safety.ready || warmUploadSelected;
    els.leadsImportantDispatchConfirmBtn.title = safety.buttonTitle || previewBlockReason || (previewBlocked ? "Run Preview Dispatch for the current source and cap first." : "");
    if (!confirmBusy) {
      els.leadsImportantDispatchConfirmBtn.classList.remove("is-loading");
      const retryConfirm = lastImportantDispatchConfirmFeedback?.state === "failed" && !previewBlocked;
      setNodeText(
        els.leadsImportantDispatchConfirmBtn,
        retryConfirm
          ? "Retry Confirm Dispatch"
          : safety.buttonLabel,
      );
    }
    els.leadsImportantDispatchConfirmBtn.classList.toggle("is-locked", Boolean(els.leadsImportantDispatchConfirmBtn.disabled));
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
      lastImportantDispatchConfirmFeedback = { state: "ready", message: job.message || "Lead dispatch complete." };
      if (data.status) renderLeadsStatus(data.status || {});
      else renderImportantDispatch(lastImportantDispatch);
      showMessage(job.message || "Lead dispatch complete.", "success");
      return;
    }
    if (job.status === "failed" || job.status === "canceled" || job.status === "cancelled") {
      stopImportantLeadDispatchJobPolling();
      clearSavedJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY, job.job_id || jobId);
      lastImportantDispatchConfirmFeedback = { state: "failed", message: job.error || "Lead dispatch failed." };
      renderImportantDispatch(lastImportantDispatch);
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
    els.leadsImportantDispatchSourceMode.value = mode === "strict_verified" ? "strict_verified" : mode === "cleaned" ? "cleaned" : "triaged_keep";
  }
  if (els.leadsImportantDispatchCap && !els.leadsImportantDispatchCap.value) {
    els.leadsImportantDispatchCap.value = "all";
  }
  syncImportantDispatchCampaignSource();
}

function dispatchSourceForSelectedMode() {
  const status = lastLeadsStatus || {};
  const selectedMode = selectedImportantDispatchSourceMode();
  const options = status.dispatch_source_options || {};
  const mode = selectedMode === "strict_verified" ? "strict_verified" : selectedMode === "cleaned" ? "cleaned" : "triaged_keep";
  return {
    mode,
    source: options[mode] || status.dispatch_source || {},
  };
}

function selectedDispatchSourceLabel() {
  const source = arguments.length > 0 ? arguments[0] : null;
  const preview = arguments.length > 1 ? arguments[1] : null;
  if (isCurrentSaferRecontactSource(source, preview)) return "Safer Recontact Pool";
  const select = els.leadsImportantDispatchSourceMode;
  if (select?.selectedOptions?.length) {
    return String(select.selectedOptions[0].textContent || "").trim() || "Selected source";
  }
  const selected = dispatchSourceForSelectedMode();
  return selected.source?.dispatch_source_name || selected.mode || "Selected source";
}

function dispatchCampaignTypeLabel(value = selectedImportantDispatchCampaignType()) {
  if (isCurrentSaferRecontactSource(null, lastImportantDispatchPreview)) return "Safer Recontact Pool";
  return value === "recontact_cold"
    ? "Recontact — allows prior contacts"
    : "Fresh Cold — excludes prior contacts";
}

function dispatchSourceFriendlyLabel(mode = selectedImportantDispatchSourceMode(), source = null, preview = null) {
  if (isCurrentSaferRecontactSource(source, preview)) return "Safer Recontact Pool";
  if (mode === "cleaned") return "Recontact Pool / Checked Output";
  if (mode === "strict_verified") return "Strict Public Proof";
  return "Fresh Cold Keep";
}

const SAFER_RECONTACT_SOURCE_FILENAME = "leads_safer_recontact_not_seen_active_history.csv";

function normalizeComparableSourcePath(value) {
  return String(value || "").trim().replace(/\\/g, "/").replace(/\/+/g, "/").toLowerCase();
}

function sourcePathMatchesSaferRecontact(value) {
  const normalized = normalizeComparableSourcePath(value);
  if (!normalized) return false;
  if (normalized.includes(SAFER_RECONTACT_SOURCE_FILENAME)) return true;
  const summaryPath = normalizeComparableSourcePath(lastSaferRecontactSummary?.output_path || "");
  return Boolean(summaryPath && normalized === summaryPath);
}

function isSaferRecontactSource(payload = null) {
  if (!payload || typeof payload !== "object") return false;
  const sourceMode = String(payload.dispatch_source_mode || payload.source_mode || payload.dispatch_source_kind || "").trim().toLowerCase();
  if (["safer_recontact", "safer_recontact_pool"].includes(sourceMode)) return true;
  return [
    payload.dispatch_source_path,
    payload.source_path,
    payload.output_path,
    payload.dispatch_source_label,
    payload.source_label,
  ].some(sourcePathMatchesSaferRecontact);
}

function isCurrentSaferRecontactSource(source = null, preview = null) {
  if (isSaferRecontactSource(preview) || isSaferRecontactSource(source)) return true;
  if (dispatchPreviewMatchesCurrentSelection() && isSaferRecontactSource(lastImportantDispatchPreview)) return true;
  return selectedSaferRecontactPoolIsActive();
}

function dispatchSourceDisplayName(source = null, preview = null) {
  if (isCurrentSaferRecontactSource(source, preview)) return "Safer Recontact Pool";
  return source?.dispatch_source_name || preview?.dispatch_source_name || dispatchSourceFriendlyLabel(selectedImportantDispatchSourceMode(), source, preview);
}

function dispatchSourceDetailLabel(source = null, preview = null) {
  if (isCurrentSaferRecontactSource(source, preview)) return "Safer recontact CSV — not found in active history";
  return dispatchSourceDisplayName(source, preview);
}

function recontactRecencySummary(preview = lastImportantDispatchPreview) {
  const raw = preview?.recontact_recency && typeof preview.recontact_recency === "object"
    ? preview.recontact_recency
    : {};
  const plannedUnique = Number(raw.planned_unique ?? preview?.recontact_planned_unique ?? preview?.total_planned_unique_count ?? 0);
  const found = Number(raw.found_in_active_history ?? preview?.recontact_found_in_active_history ?? 0);
  const seenThisMonth = Number(raw.seen_this_month ?? preview?.recontact_seen_this_month ?? 0);
  const notFound = Number(raw.not_found_in_active_history ?? preview?.recontact_not_found_in_active_history ?? Math.max(0, plannedUnique - found));
  const foundRatio = plannedUnique > 0 ? found / plannedUnique : 0;
  const seenThisMonthRatio = plannedUnique > 0 ? seenThisMonth / plannedUnique : 0;
  const notFoundRatio = plannedUnique > 0 ? notFound / plannedUnique : 0;
  let riskLevel = String(raw.risk_level || preview?.recontact_recency_risk_level || "").trim().toLowerCase();
  if (!riskLevel) {
    riskLevel = foundRatio >= 0.3 || seenThisMonthRatio >= 0.15
      ? "red"
      : foundRatio >= 0.1 || seenThisMonthRatio >= 0.05
        ? "yellow"
        : "green";
  }
  const highRisk = Boolean(raw.high_risk ?? preview?.recontact_recency_high_risk) || riskLevel === "red";
  return {
    plannedUnique,
    found,
    seenThisMonth,
    notFound,
    foundRatio,
    seenThisMonthRatio,
    notFoundRatio,
    riskLevel,
    highRisk,
    warning: String(raw.warning || preview?.recontact_recency_warning || (highRisk ? "Not recommended: most leads were contacted recently." : "")),
  };
}

function percentLabel(ratio) {
  const value = Number(ratio || 0) * 100;
  return `${value.toFixed(1)}%`;
}

function isRecontactPreview(preview) {
  return String(preview?.campaign_type || "").trim() === "recontact_cold";
}

function latestRecontactPreviewContext(preview = lastImportantDispatchPreview) {
  return isRecontactPreview(preview) ? preview : null;
}

function recontactRecencyOverrideRequired(preview = lastImportantDispatchPreview) {
  if (!preview || selectedImportantDispatchCampaignType() !== "recontact_cold") return false;
  if (!dispatchPreviewMatchesCurrentSelection()) return false;
  if (selectedSaferRecontactPoolIsActive() && Number(lastSaferRecontactSummary?.safer_found_in_active_history || 0) === 0) return false;
  return recontactRecencySummary(preview).highRisk && !Boolean(els.leadsRecontactRecencyOverride?.checked);
}

function saferRecontactSummaryContext() {
  const summary = lastSaferRecontactSummary && typeof lastSaferRecontactSummary === "object"
    ? lastSaferRecontactSummary
    : {};
  const plannedUnique = Number(summary.planned_unique || 0);
  const found = Number(summary.found_in_active_history || 0);
  const seenThisMonth = Number(summary.seen_this_month || 0);
  const notFound = Number(summary.not_found_in_active_history ?? summary.safer_rows_written ?? 0);
  const foundRatio = plannedUnique > 0 ? found / plannedUnique : Number(summary.found_in_active_history_pct || 0) / 100;
  const seenThisMonthRatio = plannedUnique > 0 ? seenThisMonth / plannedUnique : Number(summary.seen_this_month_pct || 0) / 100;
  const notFoundRatio = plannedUnique > 0 ? notFound / plannedUnique : Number(summary.not_found_in_active_history_pct || 0) / 100;
  const riskLevel = String(summary.risk_level || "").trim().toLowerCase();
  return {
    plannedUnique,
    found,
    seenThisMonth,
    notFound,
    foundRatio,
    seenThisMonthRatio,
    notFoundRatio,
    highRisk: riskLevel === "red" || foundRatio >= 0.5 || seenThisMonthRatio >= 0.5,
    riskLevel: riskLevel ? riskLevel.toUpperCase() : "",
    hasSummary: plannedUnique > 0 || Boolean(summary.output_path),
    outputPath: String(summary.output_path || "").trim(),
  };
}

function recontactDecisionContext(preview = lastImportantDispatchPreview) {
  const recontactPreview = latestRecontactPreviewContext(preview);
  if (recontactPreview) return recontactRecencySummary(recontactPreview);
  return saferRecontactSummaryContext();
}

function importantDispatchConfirmButtonLabel() {
  return selectedQueueConfirmLabel(lastImportantDispatchPreview, dispatchSourceForSelectedMode().source || {});
}

function selectedSaferRecontactPoolIsActive() {
  const saferPath = String(lastSaferRecontactSummary?.output_path || "").trim();
  const selectedOutput = String(els.leadsImportantOutputPath?.value || "").trim();
  return Boolean(
    selectedImportantDispatchCampaignType() === "recontact_cold"
    && (
      (saferPath && selectedOutput && normalizeComparableSourcePath(saferPath) === normalizeComparableSourcePath(selectedOutput))
      || sourcePathMatchesSaferRecontact(selectedOutput)
    ),
  );
}

function liveRecipientQueueTotal(status = lastLeadsStatus) {
  return Number(status?.jc_queue?.count || 0) + liveSendGridQueueTotal(status);
}

function dispatchPreviewRouteSummary(preview = null, dispatchSource = {}) {
  const shardCounts = preview?.sendgrid_shard_planned_counts && typeof preview.sendgrid_shard_planned_counts === "object"
    ? preview.sendgrid_shard_planned_counts
    : {};
  const sg1 = Number(preview?.rows_to_add_sendgrid_1 ?? shardCounts.sendgrid_1 ?? 0);
  const sg2 = Number(preview?.rows_to_add_sendgrid_2 ?? shardCounts.sendgrid_2 ?? 0);
  const sg3 = Number(preview?.rows_to_add_sendgrid_3 ?? shardCounts.sendgrid_3 ?? 0);
  const sg4 = Number(preview?.rows_to_add_sendgrid_4 ?? shardCounts.sendgrid_4 ?? 0);
  const sg5 = Number(preview?.rows_to_add_sendgrid_5 ?? shardCounts.sendgrid_5 ?? 0);
  const sendgridTotal = Number(preview?.rows_to_add_sendgrid ?? preview?.sendgrid_planned_count ?? (sg1 + sg2 + sg3 + sg4 + sg5) ?? 0);
  const privateJc = Number(preview?.rows_to_add_private_jc ?? preview?.private_jc_planned_count ?? 0);
  const selectedRows = Number(preview?.dispatch_selected_row_count ?? preview?.selected_rows ?? dispatchSource.dispatch_source_row_count ?? 0);
  const uniquePlanned = Number(preview?.total_planned_unique_count ?? preview?.total_rows_would_write ?? privateJc + sendgridTotal ?? 0);
  const skippedReasons = preview?.exclusion_reason_counts && typeof preview.exclusion_reason_counts === "object"
    ? preview.exclusion_reason_counts
    : {};
  const skippedAlreadyContacted = Number(preview?.skipped_already_contacted ?? skippedReasons.already_contacted ?? 0);
  const skippedAlreadySent = Number(preview?.skipped_already_sent ?? skippedReasons.already_sent ?? 0);
  const skippedAlreadyQueued = Number(preview?.skipped_already_queued ?? skippedReasons.already_queued ?? 0);
  const skippedSuppressed = Number(preview?.skipped_suppressed ?? preview?.suppressed_skipped ?? skippedReasons.suppressed ?? 0);
  const skippedInvalid = Number(preview?.skipped_invalid_malformed ?? preview?.invalid_malformed_skipped ?? skippedReasons.invalid_source_row ?? 0);
  const skippedBoth = Number(preview?.skipped_both ?? 0);
  const skippedRows = Number(preview?.skipped_rows ?? 0);
  const skippedFiltered = skippedRows || skippedBoth || (skippedAlreadyContacted + skippedAlreadySent + skippedAlreadyQueued + skippedSuppressed + skippedInvalid);
  const skippedReasonTotal = Object.values(skippedReasons).reduce((sum, value) => sum + Number(value || 0), 0);
  const skippedMathMismatch = Boolean(preview && skippedRows !== skippedReasonTotal);
  const duplicatePlanned = Number(preview?.duplicate_planned_email_count ?? 0);
  const sentLogOverlap = Number(preview?.planned_authoritative_sent_overlap_count ?? preview?.planned_sent_log_overlap_count ?? 0);
  const sendgridZeroReason = String(preview?.sendgrid_zero_reason || "").trim();
  const shardsSlash = `${sg1} / ${sg2} / ${sg3} / ${sg4} / ${sg5}`;
  const shardsLabel = `SG1 ${sg1} · SG2 ${sg2} · SG3 ${sg3} · SG4 ${sg4} · SG5 ${sg5}`;
  const sourceRows = Number(preview?.dispatch_source_row_count ?? dispatchSource.dispatch_source_row_count ?? selectedRows ?? 0);
  const historyRemoved = skippedAlreadyContacted + skippedAlreadySent;
  return {
    privateJc,
    sg1,
    sg2,
    sg3,
    sg4,
    sg5,
    sendgridTotal,
    uniquePlanned,
    selectedRows,
    sourceRows,
    eligibleRows: Number(preview?.dispatch_eligible_row_count ?? dispatchSource.dispatch_eligible_row_count ?? 0),
    skippedAlreadyContacted,
    skippedAlreadySent,
    skippedAlreadyQueued,
    skippedSuppressed,
    skippedInvalid,
    historyRemoved,
    skippedBoth,
    skippedRows,
    skippedFiltered,
    skippedReasonTotal,
    skippedMathMismatch,
    duplicatePlanned,
    sentLogOverlap,
    sendgridZeroReason,
    shardsSlash,
    shardsLabel,
    hasMissingSendgridZeroReason: Boolean(preview && uniquePlanned > 0 && sendgridTotal === 0 && !sendgridZeroReason),
  };
}

function selectedQueueLabel(preview = lastImportantDispatchPreview, dispatchSource = {}) {
  if (isCurrentSaferRecontactSource(dispatchSource, preview)) return "Safer Recontact";
  if (String(preview?.campaign_type || selectedImportantDispatchCampaignType()) === "recontact_cold") return "Full Recontact";
  return "Fresh Cold";
}

function selectedQueueConfirmLabel(preview = lastImportantDispatchPreview, dispatchSource = {}) {
  const label = selectedQueueLabel(preview, dispatchSource);
  if (label === "Safer Recontact") return "Confirm Safer Recontact Queue";
  if (label === "Full Recontact") return "Confirm Full Recontact Queue";
  return "Confirm Fresh Cold Queue";
}

function sendgridOutcomeHealthSummaryHtml(snapshot = lastSnapshot) {
  const health = snapshot?.sendgrid_outcome_health || {};
  if (!health || typeof health !== "object") return "";
  const route = health.webhook_route_exists ? "Route yes" : "Route no";
  const key = health.sendgrid_event_public_key_configured ? "Public key yes" : "Public key no";
  const receiver = health.sendgrid_webhook_receiver_url_configured ? "Receiver URL yes" : "Receiver URL no";
  const latest = health.latest_sendgrid_event_timestamp
    ? formatGeneratedAt(health.latest_sendgrid_event_timestamp)
    : "No SendGrid events";
  const warning = health.warning_text || (health.warning ? (health.message || SENDGRID_OUTCOME_STALE_WARNING) : "");
  return `
    <div class="summary-small-note sendgrid-outcome-health sendgrid-outcome-health-${escapeHtml(health.state || "unknown")}">
      <span>${escapeHtml(route)} · ${escapeHtml(key)} · ${escapeHtml(receiver)}</span>
      <span>Latest outcome event: ${escapeHtml(latest)}</span>
      ${warning ? `<strong>${escapeHtml(warning)}</strong>` : ""}
    </div>
  `;
}

const REQUIRED_DISPATCH_FIELDS = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"];
const SENDGRID_OUTCOME_STALE_WARNING = "SendGrid outcome feed is stale. Emails may have been accepted by SendGrid, but delivery/bounce/spam outcomes are not currently being received.";

function previewPlannedRows(preview = null) {
  const queues = preview?.plan_rows_by_queue && typeof preview.plan_rows_by_queue === "object"
    ? preview.plan_rows_by_queue
    : {};
  return Object.values(queues).flatMap((rows) => (Array.isArray(rows) ? rows : []));
}

function previewMissingRequiredDispatchFields(preview = null) {
  return previewPlannedRows(preview).some((row) => (
    !row
    || typeof row !== "object"
    || REQUIRED_DISPATCH_FIELDS.some((field) => !String(row[field] || "").trim())
  ));
}

function dispatchConfirmSafetyState(dispatchSource = {}, preview = null) {
  const summary = dispatchPreviewRouteSummary(preview, dispatchSource);
  const previewCurrent = Boolean(preview && dispatchPreviewMatchesCurrentSelection());
  const activeDispatch = isActiveImportantLeadCheckJob(lastImportantDispatchJob);
  const sendersActive = activeSenderProfiles().length > 0;
  const activeCheck = isActiveImportantLeadCheckJob(currentImportantCheckJob());
  const sourceBlocked = Boolean(dispatchSource.dispatch_block_reason);
  const sourceBlockReason = dispatchPreviewBlockReason(dispatchSource);
  const liveQueuesNotEmpty = liveRecipientQueueTotal() > 0;
  const recencyOverrideRequired = recontactRecencyOverrideRequired(preview);
  const malformedPreview = Boolean(preview) && (
    !String(preview.campaign_type || "").trim()
    || !String(preview.dispatch_source_mode || "").trim()
  );
  const queueSafety = preview?.queue_safety && typeof preview.queue_safety === "object" ? preview.queue_safety : null;
  const hasQueueSafety = Object.prototype.hasOwnProperty.call(preview || {}, "queue_safety") && queueSafety !== null;
  const missingRequiredDispatchFields = previewMissingRequiredDispatchFields(preview);
  const derivedQueueSafety = Boolean(
    preview
    && previewCurrent
    && !sendersActive
    && !liveQueuesNotEmpty
    && summary.duplicatePlanned === 0
    && summary.sentLogOverlap === 0
    && !missingRequiredDispatchFields
  );
  const queueSafetyBlockedByPreview = Boolean(preview) && (
    (hasQueueSafety && queueSafety.safe !== true)
    || (!hasQueueSafety && !derivedQueueSafety)
  );
  if (!preview) {
    return {
      state: "idle",
      tone: "neutral",
      ready: false,
      title: "Needs preview",
      message: sourceBlockReason || "Run Preview Dispatch for the selected source before confirming anything.",
      buttonLabel: "Confirm locked — review preview",
      buttonTitle: sourceBlockReason || "Run Preview Dispatch first.",
    };
  }
  if (!previewCurrent) {
    return {
      state: "stale",
      tone: "warn",
      ready: false,
      title: "Review required",
      message: "Preview stale or inconsistent. Re-run Preview Dispatch for the selected source and cap.",
      buttonLabel: "Confirm locked — rerun preview",
      buttonTitle: "The stored preview does not match the current source, cap, or campaign.",
    };
  }
  if (activeDispatch || sendersActive || activeCheck || sourceBlocked || liveQueuesNotEmpty || summary.duplicatePlanned > 0 || summary.sentLogOverlap > 0 || summary.skippedMathMismatch || summary.hasMissingSendgridZeroReason || malformedPreview || missingRequiredDispatchFields || queueSafetyBlockedByPreview || recencyOverrideRequired) {
    const reason = activeDispatch
      ? "Dispatch job is already running."
      : sendersActive
        ? "A sender is active. Stop senders before confirming a queue write."
        : activeCheck
          ? "Check Leads is running."
          : liveQueuesNotEmpty
            ? "Recipient queues are not empty."
            : summary.duplicatePlanned > 0
              ? `Duplicate planned emails: ${summary.duplicatePlanned.toLocaleString()}.`
              : summary.sentLogOverlap > 0
                ? `Planned recipients overlap authoritative sent/contact logs: ${summary.sentLogOverlap.toLocaleString()}.`
                : summary.skippedMathMismatch
                  ? `Skipped rows ${summary.skippedRows.toLocaleString()} do not match skipped reasons ${summary.skippedReasonTotal.toLocaleString()}.`
                  : summary.hasMissingSendgridZeroReason
                    ? "SendGrid planned is 0 and no SendGrid zero reason was provided."
                    : malformedPreview
                      ? "Preview is missing campaign or source metadata."
                      : missingRequiredDispatchFields
                        ? "Preview has planned rows missing required dispatch fields."
                        : queueSafetyBlockedByPreview
                          ? (hasQueueSafety ? "Preview queue safety is unsafe." : "Preview queue safety is unknown.")
                          : recencyOverrideRequired
                            ? "Full recontact has high recent-contact overlap and requires explicit override."
                            : sourceBlockReason || String(dispatchSource.dispatch_block_reason || "Selected source is blocked.");
    return {
      state: "blocked",
      tone: "bad",
      ready: false,
      title: "Review required",
      message: reason,
      buttonLabel: "Confirm locked — review preview",
      buttonTitle: reason,
    };
  }
  const queueLabel = selectedQueueLabel(preview, dispatchSource);
  const title = queueLabel === "Fresh Cold"
    ? "Ready to confirm Fresh Cold queue"
    : queueLabel === "Safer Recontact"
      ? "Ready to confirm Safer Recontact queue"
      : "Ready to confirm Full Recontact queue";
  const message = `${summary.uniquePlanned.toLocaleString()} unique leads will be queued: ${summary.privateJc.toLocaleString()} Private JC and ${summary.sendgridTotal.toLocaleString()} SendGrid. SendGrid shards: ${summary.shardsSlash}. Duplicate planned emails: ${summary.duplicatePlanned.toLocaleString()}.`;
  return {
    state: "ready",
    tone: "good",
    ready: true,
    title,
    message,
    buttonLabel: selectedQueueConfirmLabel(preview, dispatchSource),
    buttonTitle: "",
  };
}

function dispatchSourceOptionForMode(mode) {
  const options = lastLeadsStatus?.dispatch_source_options || {};
  const normalized = mode === "cleaned" ? "cleaned" : mode === "strict_verified" ? "strict_verified" : "triaged_keep";
  return options[normalized] || {};
}

function renderDispatchModeCards(preview = null) {
  if (!els.leadsDispatchModeCards) return;
  const selectedCampaign = selectedImportantDispatchCampaignType();
  const recontactPreview = latestRecontactPreviewContext(preview || lastImportantDispatchPreview);
  const activeSaferPreview = isCurrentSaferRecontactSource(null, preview || lastImportantDispatchPreview);
  const freshSource = dispatchSourceOptionForMode("triaged_keep");
  const recontactSource = dispatchSourceOptionForMode("cleaned");
  const freshCount = Number(freshSource.dispatch_eligible_row_count || freshSource.dispatch_source_row_count || 0);
  const validPreview = Boolean(preview && dispatchPreviewMatchesCurrentSelection());
  const validColdPreview = validPreview && selectedCampaign === "cold";
  const routeSummary = dispatchPreviewRouteSummary(validPreview ? preview : null, freshSource);
  const coldPlanned = validColdPreview ? routeSummary.uniquePlanned : 0;
  const coldSafety = dispatchConfirmSafetyState(freshSource, validColdPreview ? preview : null);
  const fullRecency = recontactPreview && !activeSaferPreview ? recontactRecencySummary(recontactPreview) : saferRecontactSummaryContext();
  const recontactCount = Number(fullRecency.plannedUnique || lastSaferRecontactSummary?.planned_unique || recontactSource.dispatch_eligible_row_count || recontactSource.dispatch_source_row_count || 0);
  const recency = fullRecency;
  const recentHistoryLabel = recency.plannedUnique
    ? `${recency.found.toLocaleString()} / ${recency.plannedUnique.toLocaleString()} (${percentLabel(recency.foundRatio)}) active history · ${recency.seenThisMonth.toLocaleString()} / ${recency.plannedUnique.toLocaleString()} (${percentLabel(recency.seenThisMonthRatio)}) seen this month`
    : "Run preview to calculate recent-history overlap";
  const freshMetric = validColdPreview
    ? `${coldPlanned.toLocaleString()} cold-safe lead${coldPlanned === 1 ? "" : "s"} after history filtering`
    : `${freshCount.toLocaleString()} source row${freshCount === 1 ? "" : "s"}`;
  const freshAdvice = validColdPreview && coldPlanned <= 2
    ? "Only 2 cold-safe leads found — import new fresh leads."
    : validColdPreview
      ? `${routeSummary.privateJc.toLocaleString()} Private JC / ${routeSummary.sendgridTotal.toLocaleString()} SendGrid. ${coldSafety.ready ? "Ready" : "Review"}`
      : "Preview required for actual sendable count.";
  const recontactAdvice = recency.highRisk
    ? `Not recommended — ${percentLabel(recency.foundRatio)} already in active history.`
    : "Use only when recontacting prior SendGrid/local history is intentional.";
  const recontactRiskLabel = recency.highRisk ? "RED risk. " : "";
  const saferCount = Number(lastSaferRecontactSummary?.safer_rows_written ?? recency.notFound ?? 0);
  const saferPlanned = Number(lastSaferRecontactSummary?.planned_unique ?? recency.plannedUnique ?? 0);
  const saferPercent = saferPlanned > 0 ? percentLabel(saferCount / saferPlanned) : percentLabel(recency.notFoundRatio);
  const saferActive = activeSaferPreview || selectedSaferRecontactPoolIsActive();
  const saferCreated = Boolean(lastSaferRecontactSummary?.output_path);
  const saferCreationCount = Number(saferCount || recency.notFound || 0);
  const saferCreationLabel = saferCreationCount
    ? `Create ${saferCreationCount.toLocaleString()} Safer Recontact Leads`
    : "Create Safer Recontact Leads";
  const saferButtonLabel = saferRecontactPoolLoading
    ? "Creating..."
    : saferActive
      ? "Safer Pool Selected"
      : saferCreated
        ? "Use Safer Pool"
        : saferCreationLabel;
  const saferMetric = saferCreated
    ? `${saferCount.toLocaleString()} / ${saferPlanned.toLocaleString()} (${escapeHtml(saferPercent)}) safer leads created`
    : `${saferCount.toLocaleString()} / ${Math.max(saferPlanned, recency.plannedUnique).toLocaleString()} (${escapeHtml(saferPercent)}) safer candidates`;
  const saferFeedback = lastSaferRecontactFeedback?.message
    ? `<small class="dispatch-mode-feedback dispatch-mode-feedback-${escapeHtml(lastSaferRecontactFeedback.state || "warn")}">${escapeHtml(lastSaferRecontactFeedback.message)}</small>`
    : "";
  setNodeHtml(
    els.leadsDispatchModeCards,
    `
      <button class="dispatch-mode-card ${selectedCampaign === "cold" ? "is-selected" : ""}" type="button" data-dispatch-mode-card="fresh">
        <span class="label">Fresh Cold Campaign</span>
        <strong>Fresh Cold Keep</strong>
        <span>Excludes prior contacts/sends.</span>
        <b>${escapeHtml(freshMetric)}</b>
        <small>${escapeHtml(freshAdvice)}</small>
        ${validColdPreview ? `<em>${escapeHtml(coldSafety.ready ? "Ready" : "Review")}</em>` : ""}
      </button>
      <details class="dispatch-secondary-modes" ${selectedCampaign === "recontact_cold" || saferActive ? "open" : ""}>
        <summary>Recontact options</summary>
        <div class="dispatch-secondary-mode-grid">
          <button class="dispatch-mode-card ${selectedCampaign === "recontact_cold" && !activeSaferPreview ? "is-selected" : ""} ${recency.highRisk ? "is-warn" : ""}" type="button" data-dispatch-mode-card="recontact">
            <span class="label">Recontact Campaign</span>
            <strong>Full Recontact Pool / Checked Output</strong>
            <span>May include prior contacts/sends.</span>
            <b>${recontactCount.toLocaleString()} total planned</b>
            <small>${escapeHtml(recentHistoryLabel)}. ${escapeHtml(recontactRiskLabel)}${escapeHtml(recontactAdvice)}</small>
          </button>
          <button class="dispatch-mode-card dispatch-mode-card-action ${saferActive ? "is-selected" : lastSaferRecontactSummary?.output_path ? "is-ready" : ""}" type="button" data-dispatch-mode-card="safer-recontact" ${saferActive ? "disabled" : ""}>
            <span class="label">Safer Recontact Campaign</span>
            ${saferActive ? `<span class="mini-pill">Selected</span>` : ""}
            <strong>Safer Recontact Pool</strong>
            <span>Only planned recontact leads not found in active history.</span>
            <b>${saferMetric}</b>
            <small>${saferActive ? "Selected source: Safer recontact CSV — not found in active history." : lastSaferRecontactSummary?.output_path ? `Created separately: ${lastSaferRecontactSummary.output_path}` : "Recommended over full recontact when recent-contact risk is high."}</small>
            ${saferFeedback}
            <em>${escapeHtml(saferButtonLabel)}</em>
          </button>
        </div>
      </details>
    `,
  );
}

function dispatchStatusBannerModel(dispatchSource = {}, preview = null) {
  const routeSummary = dispatchPreviewRouteSummary(preview, dispatchSource);
  const duplicateCount = Number(preview?.duplicate_planned_email_count || 0);
  const sourceMismatch = Boolean(lastImportantDispatchPreview?.preview_id && !preview);
  const saferPreview = isCurrentSaferRecontactSource(dispatchSource, preview);
  const malformedPreview = Boolean(preview) && (
    !String(preview.campaign_type || "").trim()
    || !String(preview.dispatch_source_mode || "").trim()
    || duplicateCount > 0
    || routeSummary.sentLogOverlap > 0
    || routeSummary.skippedMathMismatch
  );
  const activeSenders = activeSenderProfiles().length > 0;
  const sourceBlocked = Boolean(dispatchSource.dispatch_block_reason);
  if (activeSenders || malformedPreview || sourceBlocked || sourceMismatch) {
    return {
      tone: "bad",
      title: "Blocked",
      message: activeSenders
        ? "Active sender is running. Stop senders before preparing a dispatch."
        : malformedPreview
          ? "Preview is malformed, overlaps sent history, has duplicate planned emails, or has inconsistent skipped math. Re-run Preview Dispatch."
          : sourceMismatch
            ? "Preview source or cap is stale. Re-run Preview Dispatch for the selected source."
            : String(dispatchSource.dispatch_block_reason || "Selected source is blocked."),
    };
  }
  const recency = recontactRecencySummary(preview);
  if (preview && selectedImportantDispatchCampaignType() === "recontact_cold" && recency.highRisk && !saferPreview) {
    return {
      tone: "bad",
      title: "Do not confirm",
      message: `Do not confirm full recontact — ${percentLabel(recency.foundRatio)} were already in active history and ${percentLabel(recency.seenThisMonthRatio)} were seen this month. Use the ${recency.notFound.toLocaleString()} safer leads or import a new fresh pool.`,
    };
  }
  if (preview && liveRecipientQueueTotal() === 0) {
    return {
      tone: "good",
      title: "Preview calculated",
      message: saferPreview
        ? "Safer recontact CSV — not found in active history. Confirm is available when the selected preview is current."
        : routeSummary.historyRemoved
          ? `History filter excluded ${routeSummary.historyRemoved.toLocaleString()} already-sent/contacted rows. ${routeSummary.uniquePlanned.toLocaleString()} cold-safe leads remain.`
          : "Queues are empty. Confirm is available when the selected preview is current.",
    };
  }
  return {
    tone: "warn",
    title: "Preview needed",
    message: "Run Preview Dispatch for the selected mode before confirming anything.",
  };
}

function renderDispatchStatusBanner(dispatchSource = {}, preview = null) {
  const banner = dispatchStatusBannerModel(dispatchSource, preview);
  return `
    <section class="dispatch-status-banner dispatch-status-banner-${escapeHtml(banner.tone)}">
      <strong>${escapeHtml(banner.title)}</strong>
      <span>${escapeHtml(banner.message)}</span>
    </section>
  `;
}

function renderRecommendedNextAction(dispatchSource = {}, preview = null) {
  void dispatchSource;
  void preview;
  if (els.leadsRecommendedNextAction) {
    setNodeText(els.leadsRecommendedNextAction, "");
    els.leadsRecommendedNextAction.hidden = true;
  }
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
    const error = new Error(message);
    error.payload = data;
    error.status = response.status;
    if (response.status === 401 || response.status === 403) {
      setAuthState({
        authEnabled: authState.authEnabled,
        authenticated: false,
        username: "",
        message,
      });
    }
    throw error;
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
          ${item.note ? `<span class="operator-metric-note">${escapeHtml(item.note)}</span>` : ""}
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
  const isWarmResearch = result?.upload_type === "warm_research" || warmResearchUploadMode();
  if (els.leadsImportantCheckMeta) {
    if (result?.generated_at_utc) {
      setNodeText(
        els.leadsImportantCheckMeta,
        isWarmResearch
          ? "Warm upload checked. Generate drafts before explicit Warm Private JC confirmation."
          : `Last check completed. Cleaned ${Number(result.cleaned_rows || 0)} row(s), rejected ${Number((result.input_rows || 0) - (result.cleaned_rows || 0))} row(s).`,
      );
    } else {
      setNodeText(
        els.leadsImportantCheckMeta,
        isWarmResearch
          ? "Choose a Warm Research CSV/XLSX file, then click Upload & Check. Cold dispatch remains disabled."
          : "Choose the source file for this Cold campaign, then run Upload & Check.",
      );
    }
  }

  if (!result?.generated_at_utc) {
    setNodeHtml(els.leadsImportantCheckResults, "");
    return;
  }

  if (isWarmResearch) {
    const reasonRows = Object.entries(result.reason_counts || {}).map(([reason, count]) => ({ Reason: reason, Count: Number(count || 0) }));
    setNodeHtml(
      els.leadsImportantCheckResults,
      `
        <div class="operator-result-shell operator-check-shell warm-check-results">
          <section class="operator-empty-state operator-empty-state-inline warm-check-message">
            <strong>Warm upload checked.</strong>
            <span>Warm sending requires draft preview and explicit Warm Private JC confirmation.</span>
          </section>
          ${renderOperatorMetricStrip([
            { label: "Input", value: Number(result.input_rows || 0) },
            { label: "Warm email ready", value: Number(result.warm_email_ready_rows || 0), tone: "good" },
            { label: "Contact forms", value: Number(result.warm_contact_form_rows || 0) },
            { label: "Rejected", value: Number(result.warm_rejected_rows || 0), tone: "warn" },
            { label: "Already contacted", value: Number(result.already_contacted_rows || 0), tone: "warn" },
          ])}
          ${reasonRows.length
            ? renderOperatorTableBlock("Warm rejection reasons", "Rejected warm rows remain outside all sender queues.", ["Reason", "Count"], reasonRows, "No warm rows were rejected.")
            : ""}
          <details class="dispatch-drawer advanced-details">
            <summary>Warm output files</summary>
            <div class="dispatch-disclosure-body">
              ${renderOperatorPillStrip([
                `Email ready ${result.email_ready_label || "-"}`,
                `Contact forms ${result.contact_form_review_label || "-"}`,
                `Rejected ${result.rejected_label || "-"}`,
              ])}
            </div>
          </details>
        </div>
      `,
    );
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
          ...(isManualAuthorResearch
            ? [
              { label: "Keep with fallback", value: Number(result.keep_with_fallback_rows || 0), tone: Number(result.keep_with_fallback_rows || 0) ? "warn" : "" },
            ]
            : []),
          { label: "Reject", value: Number(result.reject_count || 0), tone: "warn" },
          { label: "Review / Quarantine", value: Number(result.quarantine_count || 0), tone: "warn" },
        ])}
        ${isManualAuthorResearch
          ? `
            <section class="operator-empty-state operator-empty-state-inline">
              <strong>Manual Author Research mode</strong>
              <span>Manual Author Research mode keeps rows with valid AuthorName and AuthorEmail when no hard safety blocker exists. Rows missing BookTitle are kept only when the selected template has a safe fallback subject/body. Missing proof/enrichment fields are warnings, not dispatch blockers.</span>
            </section>
            <section class="operator-empty-state operator-empty-state-inline">
              <strong>Review/Quarantine rows are not dispatched automatically.</strong>
              <span>They must be manually promoted or selected before dispatch.</span>
            </section>
          `
          : ""}
        <details class="dispatch-drawer advanced-details lead-triage-details-drawer">
          <summary>Reason ledger and queues</summary>
          <div class="operator-result-grid">
            ${reasonRows.length
              ? renderOperatorTableBlock("Reason Ledger", "Local triage evidence for the current pass.", ["Reason", "Count"], reasonRows, "No verification reasons were recorded.")
              : ""}
            ${isManualAuthorResearch
              ? renderOperatorTableBlock(
                "Soft Warnings",
                "Soft warnings that did not block Keep.",
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
        </details>
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

function dispatchSkipReasonSummary(payload = {}) {
  const reasons = payload.exclusion_reason_counts || {};
  return [
    Number(payload.skipped_already_queued || reasons.already_queued || 0)
      ? `${Number(payload.skipped_already_queued || reasons.already_queued || 0)} already queued`
      : "",
    Number(payload.skipped_already_sent || reasons.already_sent || 0)
      ? `${Number(payload.skipped_already_sent || reasons.already_sent || 0)} already sent`
      : "",
    Number(payload.skipped_already_contacted || reasons.already_contacted || 0)
      ? `${Number(payload.skipped_already_contacted || reasons.already_contacted || 0)} already contacted`
      : "",
    Number(payload.skipped_suppressed || payload.suppressed_skipped || reasons.suppressed || 0)
      ? `${Number(payload.skipped_suppressed || payload.suppressed_skipped || reasons.suppressed || 0)} suppressed`
      : "",
    Number(payload.skipped_invalid_malformed || payload.invalid_malformed_skipped || reasons.invalid_source_row || 0)
      ? `${Number(payload.skipped_invalid_malformed || payload.invalid_malformed_skipped || reasons.invalid_source_row || 0)} invalid or malformed`
      : "",
  ].filter(Boolean).join(", ");
}

function warmResearchUploadMode() {
  return activeLeadWorkflow === "warm";
}

function currentWarmResearchReport(status = lastLeadsStatus) {
  const statusReport = status?.current_warm_check;
  if (statusReport?.upload_type === "warm_research" && statusReport?.current_upload_valid === true) return statusReport;
  return {};
}

function previousWarmResearchReport(status = lastLeadsStatus) {
  const report = status?.previous_warm_check || status?.latest_warm_check;
  if (report?.upload_type !== "warm_research" || !report?.generated_at_utc) return {};
  const current = currentWarmResearchReport(status);
  const currentJobId = String(status?.current_warm_check_job_id || current?.current_job_id || "");
  const historicalJobId = String(report?.current_job_id || report?.check_job_id || report?.job_id || "");
  if (current?.generated_at_utc === report.generated_at_utc && (!historicalJobId || historicalJobId === currentJobId)) return {};
  return report;
}

function currentWarmWorkflowState(status = lastLeadsStatus) {
  const report = currentWarmResearchReport(status);
  const progress = currentLeadOpsProgress(status, "warm_research");
  const phase = String(progress?.phase || progress?.status || "").toLowerCase();
  const progressJobId = String(progress?.job_id || "");
  const currentJobId = String(status?.current_warm_check_job_id || report?.current_job_id || "");
  const invalidPhase = ["failed", "stale", "canceled", "cancelled"].includes(phase);
  const missingCurrentArtifacts = (
    progress?.input_exists !== true
    || progress?.job_record_exists !== true
    || progress?.output_exists !== true
    || progress?.rejected_exists !== true
    || progress?.latest_master_check_matches_current_run !== true
  );
  const valid = Boolean(
    report?.generated_at_utc
    && report?.current_upload_valid === true
    && progressJobId
    && currentJobId === progressJobId
    && !invalidPhase
    && progress?.reupload_required !== true
    && !missingCurrentArtifacts
  );
  const hasCurrentAttempt = Boolean(progressJobId);
  const reuploadRequired = hasCurrentAttempt && !valid && (
    invalidPhase
    || progress?.reupload_required === true
    || missingCurrentArtifacts
  );
  return {
    valid,
    reuploadRequired,
    report: valid ? report : {},
    historicalReport: previousWarmResearchReport(status),
    progress,
  };
}

function currentWarmPrivateJcStatus(status = lastLeadsStatus, snapshot = lastSnapshot) {
  return status?.warm_private_jc_status
    || snapshot?.warm_private_jc_status
    || status?.warm_private_jc_lane
    || snapshot?.warm_private_jc_lane
    || {};
}

function applyWarmResearchLayoutState(active = warmResearchUploadMode()) {
  const leadsView = document.getElementById("leads-view");
  const appShell = leadsView?.closest(".app-shell");
  const controlBar = document.querySelector("#leads-view .leads-control-bar");
  const commandLeft = document.querySelector("#leads-view .leads-command-column-left");
  const commandCenter = document.querySelector("#leads-view .leads-command-center");
  leadsView?.classList.toggle("warm-research-mode", active);
  appShell?.classList.toggle("warm-research-shell", active);
  if (els.leadsCommandHeading) setNodeText(els.leadsCommandHeading, active ? "Check Warm Research" : "Prepare Dispatch");
  if (els.leadsPipelineMeta) {
    setNodeText(
      els.leadsPipelineMeta,
      active
        ? "Validate warm research, generate drafts, then explicitly confirm the separate Warm Private JC lane."
        : "Current source, preview, and queue confirmation in one place.",
    );
  }
  const campaignPanel = document.querySelector("#leads-view .leads-campaign-command");
  const workflowTaskContainer = els.leadsWorkflowTaskList?.closest(".react-stepper-shell")
    || els.leadsWorkflowTaskList;
  if (campaignPanel) campaignPanel.hidden = active;
  if (active && controlBar && els.leadsCurrentRunPanel?.parentElement !== controlBar) {
    controlBar.appendChild(els.leadsCurrentRunPanel);
  } else if (!active && commandLeft && els.leadsCurrentRunPanel?.parentElement !== commandLeft) {
    commandLeft.insertBefore(els.leadsCurrentRunPanel, campaignPanel || commandLeft.firstChild);
  }
  const workflowAnchorsShareParent = commandCenter
    && workflowTaskContainer?.parentElement === commandCenter
    && els.leadsWorkflowStatusBanner?.parentElement === commandCenter;
  if (active && workflowAnchorsShareParent) {
    commandCenter.insertBefore(workflowTaskContainer, els.leadsWorkflowStatusBanner);
  } else if (!active && workflowAnchorsShareParent) {
    commandCenter.insertBefore(els.leadsWorkflowStatusBanner, workflowTaskContainer);
  }
  if (els.leadsDispatchCommandColumn) els.leadsDispatchCommandColumn.hidden = active;
  const advancedDiagnostics = document.querySelector("#leads-view .leads-advanced-diagnostics");
  if (advancedDiagnostics) advancedDiagnostics.hidden = active;
  if (els.leadsImportantCheckBtn) els.leadsImportantCheckBtn.hidden = active;
  if (els.leadsImportantDispatchPreviewTopBtn) {
    els.leadsImportantDispatchPreviewTopBtn.hidden = active;
    if (active) els.leadsImportantDispatchPreviewTopBtn.disabled = true;
  }
}

function warmResearchMetricMarkup(report = {}) {
  return renderOperatorMetricStrip([
    { label: "Warm Email Ready", value: Number(report.warm_email_ready_rows || 0), tone: "good" },
    { label: "Contact forms", value: Number(report.warm_contact_form_rows || 0) },
    { label: "Rejected", value: Number(report.warm_rejected_rows || 0), tone: "warn" },
    { label: "Already contacted", value: Number(report.already_contacted_rows || 0), tone: Number(report.already_contacted_rows || 0) ? "warn" : "" },
    { label: "Suppressed", value: Number(report.suppressed_removed || 0), tone: Number(report.suppressed_removed || 0) ? "warn" : "" },
    { label: "Draft previews", value: Number(report.warm_email_preview_rows || 0), tone: Number(report.warm_email_preview_rows || 0) ? "good" : "" },
  ]);
}

function renderImportantDispatch(result) {
  if (warmResearchUploadMode()) {
    applyWarmResearchLayoutState(true);
    renderDispatchConfirmGuard({}, null);
    return;
  }
  applyWarmResearchLayoutState(false);
  const selectedDispatchSource = dispatchSourceForSelectedMode();
  const dispatchSource = selectedDispatchSource.source || {};
  const dispatchPreview = dispatchPreviewMatchesCurrentSelection() ? lastImportantDispatchPreview : null;
  const liveSenderProfiles = activeSenderProfiles();
  const sendersActive = liveSenderProfiles.length > 0;
  const liveDispatch = currentLiveDispatchState(lastLeadsStatus);
  const currentJcQueuePending = Number(liveDispatch.privatePending || 0) > 0;
  const sourceLabel = selectedDispatchSourceLabel(dispatchSource, dispatchPreview);
  const displaySourceName = dispatchSourceDisplayName(dispatchSource, dispatchPreview || result);
  const displaySourceDetail = dispatchSourceDetailLabel(dispatchSource, dispatchPreview || result);
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
  const sourceName = displaySourceName || dispatchSource.dispatch_source_name || result?.dispatch_source_name || dispatchSource.dispatch_source_mode || result?.dispatch_source_mode || "triaged_keep";
  const sourcePath = dispatchSource.dispatch_source_path || result?.dispatch_source_path || "-";
  const preflightAllowed = !sendersActive && !activeCheckRunning;
  const preflightLabel = preflightAllowed ? "Allowed" : "Blocked";
  const activeSenderSummary = liveSenderProfiles.length
    ? liveSenderProfiles.map((profile) => `${formatProfileName(profile.name)} (${profile.runtime_state})`).join(", ")
    : "None";
  const selectedCap = els.leadsImportantDispatchCap?.value || (dispatchPreview?.dispatch_cap ?? "all");
  const stalePreviewMismatch = !dispatchPreview && Boolean(lastImportantDispatchPreview?.preview_id);
  const previewFeedbackState = !dispatchPreview ? String(lastImportantDispatchPreviewFeedback?.state || "") : "";
  const previewFeedbackMessage = !dispatchPreview ? String(lastImportantDispatchPreviewFeedback?.message || "") : "";
  const noPreviewTitle = dispatchBlockReason
    ? "Preview locked."
    : previewFeedbackState === "blocked"
    ? "Preview blocked."
    : previewFeedbackState === "failed"
      ? "Preview failed. Retry Preview Dispatch."
      : stalePreviewMismatch
        ? "Preview/source/cap mismatch. Retry Preview Dispatch."
        : "No preview yet.";
  const noPreviewMessage = dispatchBlockReason
    || previewFeedbackMessage
    || (stalePreviewMismatch
      ? "The stored preview does not match the selected source or cap. Click Preview Dispatch to calculate queue assignments."
      : "Locked until Check/Triage completes.");
  const previewPrivateJc = Number(dispatchPreview?.rows_to_add_private_jc || 0);
  const previewSg1 = Number(dispatchPreview?.rows_to_add_sendgrid_1 || 0);
  const previewSg2 = Number(dispatchPreview?.rows_to_add_sendgrid_2 || 0);
  const previewSg3 = Number(dispatchPreview?.rows_to_add_sendgrid_3 || 0);
  const previewSg4 = Number(dispatchPreview?.rows_to_add_sendgrid_4 || 0);
  const previewSg5 = Number(dispatchPreview?.rows_to_add_sendgrid_5 || 0);
  const previewSendgrid = previewSg1 + previewSg2 + previewSg3 + previewSg4 + previewSg5;
  const sendgridShardBreakdown = `SG1 ${previewSg1} · SG2 ${previewSg2} · SG3 ${previewSg3} · SG4 ${previewSg4} · SG5 ${previewSg5}`;
  const sendgridZeroReason = String(dispatchPreview?.sendgrid_zero_reason || "").trim();
  const previewUniquePlanned = Number(dispatchPreview?.total_planned_unique_count || dispatchPreview?.total_rows_would_write || 0);
  const previewSkipped = Number(dispatchPreview?.skipped_both || 0)
    || Number(dispatchPreview?.skipped_already_sent || 0)
    + Number(dispatchPreview?.skipped_already_queued || 0)
    + Number(dispatchPreview?.skipped_suppressed || 0)
    + Number(dispatchPreview?.skipped_invalid_malformed || 0);
  const previewRouteSummary = dispatchPreviewRouteSummary(dispatchPreview, dispatchSource);
  const confirmSafety = dispatchConfirmSafetyState(dispatchSource, dispatchPreview);
  const previewZeroAdd = Boolean(dispatchPreview) && Number(dispatchPreview?.total_rows_would_write || 0) === 0;
  const previewZeroAddReasons = dispatchSkipReasonSummary(dispatchPreview || {});
  const confirmFeedbackState = String(lastImportantDispatchConfirmFeedback?.state || "");
  const confirmFeedbackMessage = String(lastImportantDispatchConfirmFeedback?.message || "");
  const confirmFeedbackTitle = confirmFeedbackState === "blocked"
    ? "Confirm Dispatch blocked."
    : confirmFeedbackState === "failed"
      ? "Confirm Dispatch failed. Retry Confirm Dispatch."
      : confirmFeedbackState === "queued" || confirmFeedbackState === "running"
        ? "Confirm Dispatch running."
        : "";

  renderDispatchConfirmGuard(dispatchSource, dispatchPreview);
  renderDispatchModeCards(dispatchPreview);
  renderRecommendedNextAction(dispatchSource, dispatchPreview);
  if (els.leadsDispatchSection) {
    els.leadsDispatchSection.classList.toggle("leads-dispatch-section-deferred", currentJcQueuePending);
  }
  if (els.leadsRecontactOverrideWrap) {
    const showOverride = Boolean(dispatchPreview && selectedImportantDispatchCampaignType() === "recontact_cold" && recontactRecencySummary(dispatchPreview).highRisk);
    els.leadsRecontactOverrideWrap.hidden = !showOverride;
  }
  if (els.leadsDispatchCurrentQueueNote) {
    els.leadsDispatchCurrentQueueNote.hidden = !currentJcQueuePending || Boolean(dispatchPreview);
    setNodeText(
      els.leadsDispatchCurrentQueueNote,
      currentJcQueuePending
        ? "Private JC has an unfinished recipient queue. Finish the current queue before confirming a new dispatch."
        : "",
    );
  }
  if (els.leadsImportantDispatchMeta) {
    if (dispatchPreview && !result?.generated_at_utc) {
      setNodeText(
        els.leadsImportantDispatchMeta,
        dispatchBlockReason
          ? `Preview ready. ${escapeHtml(displaySourceName)} with cap ${escapeHtml(dispatchPreview.dispatch_cap_label || dispatchPreview.dispatch_cap || "all")}. Dispatch actions are blocked: ${dispatchBlockReason}`
          : `Preview ready. ${escapeHtml(displaySourceName)} with cap ${escapeHtml(dispatchPreview.dispatch_cap_label || dispatchPreview.dispatch_cap || "all")}. Confirm Dispatch will write exactly this previewed set if nothing changed.`,
      );
    } else if (result?.generated_at_utc) {
      setNodeText(
        els.leadsImportantDispatchMeta,
        `Last dispatch ${lastDispatchGeneratedAt}. Source ${escapeHtml(result.dispatch_source_name || result.dispatch_source_mode || "triaged_keep")}. Astra ${confirmedPrivateJcTotal}, SendGrid ${confirmedSendgridTotal}. Live queue counts are shown separately below.`,
      );
    } else {
      const sourceMode = selectedDispatchSource.mode;
      const idlePath = dispatchSource?.dispatch_source_path || (sourceMode === "strict_verified" ? "_important/leads_verified.csv" : "_important/leads_triaged_keep.csv");
      const idleName = dispatchSourceDisplayName(dispatchSource, null) || dispatchSource?.dispatch_source_name || dispatchSourceFriendlyLabel(sourceMode, dispatchSource, null);
      setNodeText(
        els.leadsImportantDispatchMeta,
        dispatchBlockReason
          ? `Dispatch is idle. Source ${idleName}.`
          : `Dispatch is idle. Source ${idleName}. Check the selected source first, then dispatch while all senders are stopped.`,
      );
    }
  }

  if (!result?.generated_at_utc) {
    const previewRows = Array.isArray(dispatchPreview?.assigned_preview_rows) ? dispatchPreview.assigned_preview_rows : [];
    const previewFields = Array.isArray(dispatchPreview?.queue_headers) ? dispatchPreview.queue_headers : [];
    const previewMetricsMarkup = dispatchPreview
      ? renderOperatorMetricStrip([
        { label: "Writable", value: previewRouteSummary.uniquePlanned },
        { label: "Private JC", value: previewRouteSummary.privateJc },
        {
          label: "SendGrid",
          value: previewRouteSummary.sendgridTotal,
          tone: previewRouteSummary.sendgridTotal ? "good" : (previewRouteSummary.sendgridZeroReason ? "warn" : "bad"),
        },
      ], "dispatch-metrics dispatch-preview-metrics dispatch-preview-metrics-primary")
      : "";
    setNodeHtml(
      els.leadsImportantDispatchResults,
      `
        <div class="dispatch-shell dispatch-shell-preview">
          <section class="dispatch-preview-card">
            <div class="operator-table-head">
              <div>
                <p class="muted">Preview is read-only and writes no queues.</p>
              </div>
              <span class="mini-pill mini-pill-${escapeHtml(confirmSafety.tone === "good" ? "good" : confirmSafety.tone === "bad" ? "bad" : "warn")}">${escapeHtml(dispatchPreview ? (confirmSafety.ready ? "Ready to confirm" : "Review required") : "Preview needed")}</span>
            </div>
            <section class="dispatch-status-banner dispatch-status-banner-${escapeHtml(confirmSafety.tone === "neutral" ? "warn" : confirmSafety.tone)}">
              <strong>${escapeHtml(confirmSafety.title)}</strong>
              <span>${escapeHtml(dispatchPreview ? confirmSafety.message : noPreviewMessage)}</span>
            </section>
            ${previewMetricsMarkup}
            ${dispatchPreview ? `
              <details class="dispatch-preview-details">
                <summary>Preview details</summary>
                ${renderOperatorMetricStrip([
                  { label: "SendGrid shards", value: previewRouteSummary.shardsSlash },
                  { label: "Unique", value: previewRouteSummary.uniquePlanned },
                  { label: "Duplicates", value: previewRouteSummary.duplicatePlanned, tone: previewRouteSummary.duplicatePlanned ? "bad" : "good" },
                  { label: "Already contacted", value: previewRouteSummary.skippedAlreadyContacted, tone: previewRouteSummary.skippedAlreadyContacted ? "warn" : "" },
                  { label: "Already sent", value: previewRouteSummary.skippedAlreadySent, tone: previewRouteSummary.skippedAlreadySent ? "warn" : "" },
                  { label: "Suppressed", value: previewRouteSummary.skippedSuppressed, tone: previewRouteSummary.skippedSuppressed ? "bad" : "" },
                  { label: "Invalid", value: previewRouteSummary.skippedInvalid, tone: previewRouteSummary.skippedInvalid ? "bad" : "" },
                  { label: "Skipped", value: previewRouteSummary.skippedFiltered, tone: previewRouteSummary.skippedFiltered ? "warn" : "" },
                  { label: "Sent-log overlap", value: previewRouteSummary.sentLogOverlap, tone: previewRouteSummary.sentLogOverlap ? "bad" : "good" },
                  { label: "Skipped math", value: previewRouteSummary.skippedMathMismatch ? "Mismatch" : "Valid", tone: previewRouteSummary.skippedMathMismatch ? "bad" : "good" },
                ], "dispatch-metrics dispatch-preview-technical-metrics")}
                <div class="dispatch-skip-breakdown">
                  <span>Already contacted: <strong>${previewRouteSummary.skippedAlreadyContacted.toLocaleString()}</strong></span>
                  <span>Already sent: <strong>${previewRouteSummary.skippedAlreadySent.toLocaleString()}</strong></span>
                  <span>Already queued: <strong>${previewRouteSummary.skippedAlreadyQueued.toLocaleString()}</strong></span>
                  <span>Suppressed: <strong>${previewRouteSummary.skippedSuppressed.toLocaleString()}</strong></span>
                  <span>Invalid: <strong>${previewRouteSummary.skippedInvalid.toLocaleString()}</strong></span>
                  <span>Skipped rows: <strong>${previewRouteSummary.skippedRows.toLocaleString()}</strong></span>
                  <span>Skipped reasons: <strong>${previewRouteSummary.skippedReasonTotal.toLocaleString()}</strong></span>
                  <span>Sent-log overlap: <strong>${previewRouteSummary.sentLogOverlap.toLocaleString()}</strong></span>
                </div>
                ${previewRouteSummary.skippedAlreadyContacted || previewRouteSummary.skippedAlreadySent
                  ? `<section class="dispatch-skip-explainer">
                      <h4>Why only ${previewRouteSummary.uniquePlanned.toLocaleString()}?</h4>
                      <p>History filter excluded ${previewRouteSummary.historyRemoved.toLocaleString()} already-sent/contacted rows. ${previewRouteSummary.uniquePlanned.toLocaleString()} cold-safe leads remain. Skipped reason: already_sent ${previewRouteSummary.skippedAlreadySent.toLocaleString()}.</p>
                    </section>`
                  : ""}
              </details>
            ` : ""}
          </section>
          ${confirmFeedbackTitle
            ? `<section class="operator-empty-state operator-empty-state-inline dispatch-confirm-feedback dispatch-confirm-feedback-${escapeHtml(confirmFeedbackState)}"><strong>${escapeHtml(confirmFeedbackTitle)}</strong><span>${escapeHtml(confirmFeedbackMessage)}</span></section>`
            : ""}
          ${previewZeroAdd
            ? `<section class="operator-empty-state operator-empty-state-inline"><strong>No queue rows will be written.</strong><span>Nothing to confirm for queue writes because all eligible rows were already queued/skipped${previewZeroAddReasons ? `: ${escapeHtml(previewZeroAddReasons)}.` : "."}</span></section>`
            : ""}
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
          {
            label: "Eligible for selected source",
            value: Number(dispatchSource.dispatch_eligible_row_count || result.dispatch_eligible_row_count || 0),
            note: `Source: ${sourceLabel}`,
          },
          { label: "Private JC added", value: confirmedPrivateJcTotal, tone: "good" },
          { label: "SendGrid added", value: confirmedSendgridTotal, tone: "good" },
          { label: "Skipped", value: Number(result.skipped_both || 0), tone: Number(result.skipped_both || 0) ? "warn" : "" },
        ], "dispatch-metrics")}
        ${confirmFeedbackTitle
          ? `<section class="operator-empty-state operator-empty-state-inline dispatch-confirm-feedback dispatch-confirm-feedback-${escapeHtml(confirmFeedbackState)}"><strong>${escapeHtml(confirmFeedbackTitle)}</strong><span>${escapeHtml(confirmFeedbackMessage)}</span></section>`
          : ""}
        <section class="dispatch-decision-surface dispatch-current-preview">
          <div class="operator-table-head">
            <div>
              <h3>Selected preview</h3>
              <p class="muted">This is the preview for the currently selected source and cap.</p>
            </div>
          </div>
          ${dispatchPreview
            ? `
              ${renderOperatorMetricStrip([
                { label: "Eligible for selected source", value: Number(dispatchPreview.dispatch_eligible_row_count || 0), note: `Source: ${sourceLabel}` },
                { label: "Selected", value: Number(dispatchPreview.dispatch_selected_row_count || 0), tone: "good" },
                { label: "Would Write", value: Number(dispatchPreview.total_rows_would_write || 0), tone: "good" },
                { label: "Cap", value: dispatchPreview.dispatch_cap_label || dispatchPreview.dispatch_cap || "all" },
              ], "dispatch-selection-strip")}
            `
            : `
              <section class="operator-empty-state operator-empty-state-inline dispatch-next-step-banner${previewFeedbackState ? ` dispatch-next-step-${escapeHtml(previewFeedbackState)}` : ""}">
                <strong>${escapeHtml(noPreviewTitle)}</strong>
                <span>${escapeHtml(noPreviewMessage)}</span>
              </section>
            `}
        </section>
        ${sendgridZeroAddExplanation
          ? `<section class="operator-empty-state operator-empty-state-inline">
              <strong>SendGrid added 0 rows.</strong>
              <span>${escapeHtml(sendgridZeroAddExplanation)}</span>
            </section>`
          : ""}
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
              <th>Historical/canonical files</th>
              <th>Current staged run</th>
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
    status?.latest_master_check?.intake_mode
    || status?.latest_lead_triage?.intake_mode
    || status?.latest_lead_triage?.mode
    || els.leadsImportantIntakeMode?.value
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
  if (triageStatus === "completed" && previewStatus === "not_generated") return "Fast Triage complete. Preview Dispatch is ready.";
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

function currentRunWorkflowState(status = lastLeadsStatus) {
  const activeCheck = currentImportantCheckJob(status);
  const activeVerify = status?.active_important_verify_job || lastImportantVerifyJob || null;
  const activeDispatch = status?.active_important_dispatch_job || lastImportantDispatchJob || null;
  const leadCheck = currentLeadCheckStatus(status);
  const latestCheck = selectedLeadCheckReport(status);
  const latestTriage = selectedLeadTriageReport(status, leadCheck);
  const latestDispatch = status?.latest_dispatch || lastImportantDispatch || {};
  const checkStatus = leadCheck.state ? leadCheckWorkflowStatus(leadCheck) : workflowStepStatus(activeCheck, latestCheck);
  const triageStatus = checkStatus === "completed" ? workflowStepStatus(activeVerify, latestTriage) : "pending";
  const currentPreviewReady = checkStatus === "completed" && triageStatus === "completed" && dispatchPreviewMatchesCurrentSelection() && Boolean(lastImportantDispatchPreview?.preview_id);
  const previewStatus = currentPreviewReady
      ? "ready"
      : importantLeadDispatchPreviewLoading
        ? "running"
        : lastImportantDispatchPreviewState === "failed"
          ? "failed"
          : "not_generated";
  const confirmStatus = importantLeadDispatchConfirmLoading || isActiveImportantLeadCheckJob(activeDispatch)
    ? "running"
    : latestDispatch?.generated_at_utc
      ? "confirmed"
      : "not_confirmed";
  return {
    activeCheck,
    activeVerify,
    activeDispatch,
    latestCheck,
    latestTriage,
    latestDispatch,
    checkStatus,
    triageStatus,
    previewStatus,
    confirmStatus,
    currentPreviewReady,
  };
}

function currentRunPreviewBlockMessage(dispatchSource = {}, state = currentRunWorkflowState()) {
  if (state.checkStatus === "running") return "Preview blocked: Check Leads is still running";
  if (state.checkStatus === "failed") return "Preview blocked: current check is not ready";
  if (state.checkStatus !== "completed") return "Preview blocked: Upload & Check is required for the selected upload type";
  if (state.triageStatus === "running") return "Preview blocked: Fast Triage has not completed";
  if (state.triageStatus !== "completed") return "Preview blocked: Fast Triage has not completed";
  const rawReason = String(dispatchSource.dispatch_block_reason || dispatchPreviewBlockReason(dispatchSource) || "").trim();
  if (!rawReason) return "";
  const normalized = rawReason.toLowerCase();
  if (normalized.includes("current staged fast triage keep is empty") || normalized.includes("has no keep rows")) {
    return "Preview blocked: current staged keep is empty";
  }
  if (normalized.includes("missing") || normalized.includes("not available")) {
    return "Preview blocked: source file missing";
  }
  if (normalized.includes("no eligible")) {
    return "Preview blocked: no eligible rows are available";
  }
  return `Preview blocked: ${rawReason.replace(/^Preview blocked:\s*/i, "")}`;
}

function currentRunNextAction(state, dispatchSource = {}) {
  const previewBlock = currentRunPreviewBlockMessage(dispatchSource, state);
  if (state.checkStatus === "running") return { label: "Check Leads running", action: "", disabled: true };
  if (state.checkStatus !== "completed") return { label: "Upload & Check", action: "upload_check", disabled: false };
  if (state.triageStatus === "running") return { label: "Fast Triage running", action: "", disabled: true };
  if (state.triageStatus !== "completed") return { label: "Fast Triage", action: "fast_triage", disabled: false };
  if (state.previewStatus === "ready") {
    const confirmBlocked = dispatchActionBlockReason();
    return {
      label: "Confirm Dispatch",
      action: "confirm_dispatch",
      disabled: Boolean(confirmBlocked || importantLeadDispatchConfirmLoading),
      blocker: confirmBlocked,
    };
  }
  return {
    label: "Preview Dispatch",
    action: "preview_dispatch",
    disabled: Boolean(previewBlock || importantLeadDispatchPreviewLoading),
    blocker: previewBlock,
  };
}

function renderCurrentRunStatusStrip(state) {
  return `
    <div class="current-run-step-strip" aria-label="Current run workflow">
      ${renderWorkflowStep("Check Leads", state.checkStatus)}
      ${renderWorkflowStep("Fast Triage", state.triageStatus)}
      ${renderWorkflowStep("Preview Dispatch", state.previewStatus)}
      ${renderWorkflowStep("Confirm Dispatch", state.confirmStatus)}
    </div>
  `;
}

function liveSendGridQueueTotal(status = lastLeadsStatus) {
  return Array.isArray(status?.sendgrid_queues)
    ? status.sendgrid_queues.reduce((sum, queue) => sum + Number(queue.count || 0), 0)
    : 0;
}

function confirmedDispatchQueueState(status = lastLeadsStatus) {
  const latestDispatch = status?.latest_dispatch || lastImportantDispatch || {};
  const privateAdded = Number(latestDispatch.private_jc_added || latestDispatch.added_astra || 0);
  const sendgridAdded = Number(latestDispatch.sendgrid_added || latestDispatch.added_sendgrid || 0);
  const skipped = Number(latestDispatch.skipped_both || 0);
  const livePrivate = Number(status?.jc_queue?.count || 0);
  const liveSendgrid = liveSendGridQueueTotal(status);
  const totalQueued = privateAdded + sendgridAdded;
  const liveMatches = Boolean(latestDispatch?.generated_at_utc)
    && totalQueued > 0
    && livePrivate === privateAdded
    && liveSendgrid === sendgridAdded;
  return {
    confirmed: Boolean(latestDispatch?.generated_at_utc),
    liveMatches,
    privateAdded,
    sendgridAdded,
    skipped,
    livePrivate,
    liveSendgrid,
    totalQueued,
    sourcePath: latestDispatch.dispatch_source_path || latestDispatch.source_path || "",
  };
}

function pathDisplayName(path) {
  const text = String(path || "").trim();
  if (!text) return "-";
  return text.split(/[\\/]/).pop() || text;
}

function currentLiveDispatchState(status = lastLeadsStatus) {
  const activeSnapshot = status?.active_campaign_snapshot || {};
  const confirmedDispatch = status?.latest_confirmed_dispatch || status?.latest_dispatch || lastImportantDispatch || {};
  const privatePending = Number(status?.jc_queue?.count || 0);
  const sendgridPending = liveSendGridQueueTotal(status);
  const privateAdded = Number(confirmedDispatch.private_jc_added || confirmedDispatch.added_astra || 0);
  const sendgridAdded = Number(confirmedDispatch.sendgrid_added || confirmedDispatch.added_sendgrid || 0);
  const sourcePath = String(activeSnapshot.intended_source_path || confirmedDispatch.dispatch_source_path || confirmedDispatch.source_path || "").trim();
  const sourceRows = Number(activeSnapshot.intended_source_row_count || confirmedDispatch.dispatch_source_row_count || confirmedDispatch.source_rows || 0);
  const campaignType = String(activeSnapshot.campaign_type || confirmedDispatch.campaign_type || "cold").trim() || "cold";
  const hasLiveQueue = privatePending + sendgridPending > 0;
  const hasConfirmedDispatch = Boolean(confirmedDispatch?.generated_at_utc || confirmedDispatch?.confirmed_at_utc || confirmedDispatch?.confirmed_at);
  return {
    active: hasLiveQueue || hasConfirmedDispatch,
    hasLiveQueue,
    campaignType,
    sourcePath,
    sourceRows,
    privatePending,
    sendgridPending,
    privateAdded,
    sendgridAdded,
    sendgridStatus: sendgridPending > 0 ? `SendGrid pending ${sendgridPending.toLocaleString()}` : "SendGrid complete",
    privateStatus: privatePending > 0 ? `Private JC pending ${privatePending.toLocaleString()}` : "Private JC complete",
    nextAction: privatePending > 0 && sendgridPending <= 0
      ? "Start JC from Dashboard"
      : privatePending + sendgridPending > 0
        ? "Start remaining sender(s) from Dashboard"
        : "No live queue action",
  };
}

function dispatchSourceComparisonWarning(status = lastLeadsStatus) {
  const live = currentLiveDispatchState(status);
  if (!live.active || !live.sourceRows) return "";
  const selectedSource = dispatchSourceForSelectedMode().source || {};
  const selectedRows = Number(selectedSource.dispatch_eligible_row_count || selectedSource.dispatch_source_row_count || 0);
  const selectedCampaign = selectedImportantDispatchCampaignType();
  if (selectedCampaign === "recontact_cold" && selectedRows > live.sourceRows) {
    return `Selected source has ${selectedRows.toLocaleString()} rows, which is broader than the confirmed safe source (${live.sourceRows.toLocaleString()} rows).`;
  }
  return "";
}

function queueSafetyReasonLabel(reason) {
  const normalized = String(reason || "").trim();
  if (normalized === "OUTSIDE_CHECKED_OUTPUT") return "Live queues differ from the selected checked output.";
  if (normalized === "OUTSIDE_INTENDED_SOURCE") return "Live queues differ from the selected intended source.";
  if (normalized === "TRIAGED_REJECT_OVERLAP") return "Live queues overlap triaged reject rows.";
  if (normalized === "INTENDED_SOURCE_OVERLAPS_REJECT") return "Selected intended source overlaps triaged reject rows.";
  return normalized || "Recipient queue unsafe.";
}

function queueSafetySourceContext(currentSafety = {}) {
  const report = currentSafety.queue_safety || currentSafety.combined_queue_safety || {};
  const checked = report.checked_path || "";
  const intended = report.intended_source_path || report.triaged_keep_path || "";
  const pieces = [];
  if (checked) pieces.push(`Checked: ${pathDisplayName(checked)}`);
  if (intended) pieces.push(`Intended: ${pathDisplayName(intended)}`);
  return pieces.join(" · ");
}

function sourceComparisonOnlySafety(currentSafety = {}) {
  const reasons = Array.isArray(currentSafety.reasons) ? currentSafety.reasons : [];
  if (!reasons.length) return false;
  return reasons.every((reason) => ["OUTSIDE_CHECKED_OUTPUT", "OUTSIDE_INTENDED_SOURCE"].includes(String(reason || "").trim()));
}

function isSourceComparisonSafetyReason(reason) {
  const normalized = String(reason || "").trim();
  return ["OUTSIDE_CHECKED_OUTPUT", "OUTSIDE_INTENDED_SOURCE"].includes(normalized);
}

function inactiveSendgridBookTitleOnly(currentSafety = {}, status = lastLeadsStatus) {
  const missing = Array.isArray(currentSafety.missing_booktitle_queues)
    ? currentSafety.missing_booktitle_queues.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  if (!missing.length) return false;
  if (liveSendGridQueueTotal(status) > 0) return false;
  if (String(currentSafety.private_status || "").toUpperCase() !== "READY") return false;
  return missing.every((queue) => {
    const normalized = queue.toLowerCase();
    return normalized.startsWith("sg") || normalized.includes("sendgrid");
  });
}

function isInactiveSendgridBookTitleReason(reason, currentSafety = {}, status = lastLeadsStatus) {
  const normalized = String(reason || "").toLowerCase();
  return normalized.includes("missing booktitle") && inactiveSendgridBookTitleOnly(currentSafety, status);
}

function newDispatchOnlySafetyWarning(currentSafety = {}, status = lastLeadsStatus) {
  if (!Boolean(currentSafety?.blocked)) return false;
  const live = currentLiveDispatchState(status);
  if (!live.active && !sourceComparisonOnlySafety(currentSafety)) return false;
  if (live.privatePending > 0 && String(currentSafety.private_status || "").toUpperCase() !== "READY") return false;
  const reasons = Array.isArray(currentSafety.reasons) ? currentSafety.reasons : [];
  if (!reasons.length) return false;
  return reasons.every((reason) => (
    isSourceComparisonSafetyReason(reason)
    || isInactiveSendgridBookTitleReason(reason, currentSafety, status)
  ));
}

function newDispatchWarningMessage(reasonText, context = "") {
  const scope = "This warning applies to preparing a new dispatch. It does not block the already confirmed current live dispatch.";
  const detail = `${reasonText || ""}${context ? ` ${context}.` : ""}`.trim();
  return detail ? `${scope} ${detail}` : scope;
}

function alertLooksLikeNewDispatchSourceWarning(alert = {}, currentSafety = {}, status = lastLeadsStatus) {
  const text = `${alert?.title || ""} ${alert?.message || ""}`.toLowerCase();
  const looksLikeSourceWarning = (
    text.includes("selected checked output")
    || text.includes("selected intended source")
    || text.includes("outside checked")
    || text.includes("outside intended")
    || text.includes("differ from the selected")
  );
  if (!looksLikeSourceWarning) return false;
  if (!hasActualLiveQueueActivity(status, lastSnapshot)) return true;
  if (!currentLiveDispatchState(status).active) return false;
  if (String(currentSafety.private_status || "").toUpperCase() !== "READY") return false;
  return true;
}

function renderLeadsCurrentQueueNote(status = lastLeadsStatus) {
  if (!els.leadsCurrentQueueNote) return;
  void status;
  setNodeText(els.leadsCurrentQueueNote, "");
  els.leadsCurrentQueueNote.hidden = true;
}

function privateJcAuthIssueMessage(snapshot = lastSnapshot) {
  const alerts = Array.isArray(snapshot?.alerts) ? snapshot.alerts : [];
  const match = alerts.find((alert) => {
    const text = `${alert?.title || ""} ${alert?.message || ""}`.toLowerCase();
    return text.includes("private") && text.includes("bounce") && (text.includes("auth") || text.includes("token") || text.includes("credential"));
  });
  return match ? "Private JC auth issue — affects JC/private bounce sync only" : "";
}

function renderLeadsCurrentRunPanel(status = lastLeadsStatus) {
  if (!els.leadsCurrentRunPanel) return;
  if (warmResearchUploadMode()) {
    const workflow = currentWarmWorkflowState(status);
    const report = workflow.report;
    const checked = workflow.valid;
    const lane = currentWarmPrivateJcStatus(status, lastSnapshot);
    const warmRunning = Boolean(lane.running);
    const laneConfirmed = Boolean(lane.confirmed);
    const warmConfirmed = checked && Boolean(report.warm_private_jc_confirmed);
    const warmRemaining = Number(lane.queued_remaining_count ?? lane.remaining ?? 0);
    const warmSent = Number(lane.sent_count ?? 0);
    const draftCount = Number(report.warm_email_preview_rows || 0);
    const warmCap = Number(lane.cap ?? 0);
    const warmOriginal = Number(lane.ready_original_count ?? lane.original_count ?? draftCount ?? 0);
    const warmStateHeadline = workflow.reuploadRequired
      ? "Current Warm Outreach · Re-upload required"
      : checked
        ? "Current Warm Outreach · Ready for review"
        : "Current Warm Outreach · Upload required";
    const warmTimeline = Array.isArray(lane.timeline) ? lane.timeline : [];
    const warmStartAction = warmRunning ? "stop_warm_private_jc" : "start_warm_private_jc";
    const warmStartLabel = warmRunning
      ? "Stop Warm Private JC"
      : warmRemaining > 0 && warmConfirmed && laneConfirmed
          ? warmSent > 0 ? "Resume Warm Private JC" : "Start Warm Private JC"
          : "No Current Warm Queue";
    const warmStartDisabled = !warmRunning && (!checked || !warmConfirmed || !laneConfirmed || warmRemaining <= 0);
    if (els.leadsControlCheckResult) {
      setNodeHtml(
        els.leadsControlCheckResult,
        checked
          ? [
            ["Email ready", report.warm_email_ready_rows],
            ["Contact forms", report.warm_contact_form_rows],
            ["Rejected", report.warm_rejected_rows],
            ["Already contacted", report.already_contacted_rows],
            ["Suppressed", report.suppressed_removed],
          ].map(([label, value]) => `<span>${escapeHtml(label)} <strong>${Number(value || 0).toLocaleString()}</strong></span>`).join("")
          : workflow.reuploadRequired
            ? "<span>Re-upload required. Current Warm Outreach counts are cleared until a new upload completes.</span>"
            : "<span>No current Warm Research upload checked yet</span>",
      );
    }
    setNodeHtml(
      els.leadsCurrentRunPanel,
      `
        <article class="current-run-card current-source-summary-card ${checked ? "current-run-card-ready" : "current-run-card-wait"}">
          <div class="current-run-head">
            <div>
              <p class="eyebrow">Warm Private JC</p>
              <h3>${escapeHtml(warmStateHeadline)}</h3>
              <p class="current-run-subtitle warm-status-summary">${checked ? "Current upload outputs are valid." : "Historical sender activity below does not unlock this upload workflow."}</p>
            </div>
            <div class="warm-command-badges">
              <span class="mini-pill">Explicit confirmation</span>
              ${warmCap > 0 ? `<span class="mini-pill">Cap ${warmCap.toLocaleString()}</span>` : ""}
            </div>
          </div>
          <section class="warm-private-action-panel">
            <div class="warm-panel-heading">
              <div>
                <p class="eyebrow">Warm actions</p>
                <strong>Preview, confirm, then start</strong>
              </div>
            </div>
            <div class="leads-action-slot warm-action-stack">
              <button class="btn btn-secondary" type="button" data-leads-next-action="generate_warm_preview" ${!checked || warmDraftPreviewLoading ? "disabled" : ""}>${warmDraftPreviewLoading ? "Generating..." : "Generate Warm Draft Preview"}</button>
              <button class="btn btn-primary" type="button" data-leads-next-action="confirm_warm_private_jc" ${!checked || draftCount <= 0 || warmConfirmed ? "disabled" : ""}>${warmConfirmed ? "Warm Private JC Confirmed" : "Confirm Warm Private JC"}</button>
              <button class="btn ${warmRunning ? "btn-danger" : "btn-primary"}" type="button" data-leads-next-action="${escapeHtml(warmStartAction)}" ${warmStartDisabled ? "disabled" : ""}>${escapeHtml(warmStartLabel)}</button>
            </div>
            ${lane.blocked ? `<div class="warm-live-warning"><strong>Blocked: no eligible warm rows</strong><span>${escapeHtml(lane.last_worker_reason || "queue_exhausted_no_eligible_rows")}</span></div>` : ""}
            <div class="warm-live-summary" aria-label="Warm sender status">
              <span>Sent <strong>${warmSent.toLocaleString()}</strong></span>
              <span>Remaining <strong>${warmRemaining.toLocaleString()}</strong></span>
              <span>Running <strong>${warmRunning ? "Yes" : "No"}</strong></span>
            </div>
            <details class="warm-operations-details">
              <summary>Warm sender details</summary>
              <section class="warm-private-lane-group">
                <div class="warm-panel-heading">
                  <p class="eyebrow">${checked ? "Warm Private JC Sender History" : "Previous Warm Outreach Run"}</p>
                  <span class="mini-pill">Historical / live lane</span>
                </div>
                <p class="muted">This sender history is separate from the current upload workflow and cannot unlock preview, confirmation, or Start.</p>
                <div class="current-run-metrics warm-lane-metrics">
                  <div><span>Ready / Original</span><strong>${warmOriginal.toLocaleString()}</strong></div>
                  <div><span>Confirmed</span><strong>${laneConfirmed ? "Yes" : "No"}</strong></div>
                  <div><span>Running</span><strong>${warmRunning ? "Yes" : "No"}</strong></div>
                  <div><span>Sent</span><strong>${warmSent.toLocaleString()}</strong></div>
                  <div><span>Remaining</span><strong>${warmRemaining.toLocaleString()}</strong></div>
                  <div><span>Cap</span><strong>${warmCap > 0 ? warmCap.toLocaleString() : "-"}</strong></div>
                </div>
                <div class="warm-live-details">
                  <span><strong>Last sent</strong>${escapeHtml(formatWarmActivity(lane.last_sent_timestamp))}${lane.last_sent_email ? ` · <a href="mailto:${escapeHtml(lane.last_sent_email)}">${escapeHtml(lane.last_sent_email)}</a>` : ""}</span>
                  <span><strong>Next queued</strong>${escapeHtml(lane.next_queued_email || "None")}</span>
                </div>
              </section>
              <section class="warm-run-timeline">
                <div class="warm-panel-heading"><p class="eyebrow">Warm run timeline</p><span class="mini-pill">Live files</span></div>
                <div class="warm-timeline-list">
                  ${warmTimeline.length ? warmTimeline.map((event) => `
                    <div class="warm-timeline-event">
                      <strong>${escapeHtml(event.type || "EVENT")}</strong>
                      <span>${escapeHtml(event.email || event.reason || "Warm worker event")}</span>
                      <time>${escapeHtml(formatWarmActivity(event.timestamp || ""))}</time>
                    </div>
                  `).join("") : `<span class="muted">No warm run events yet.</span>`}
                </div>
              </section>
            </details>
          </section>
        </article>
      `,
    );
    return;
  }
  const state = currentRunWorkflowState(status);
  const checkReadyForCounts = state.checkStatus === "completed";
  const dispatchSource = checkReadyForCounts ? (dispatchSourceForSelectedMode().source || {}) : {};
  const latestCheck = state.latestCheck || {};
  const latestTriage = state.latestTriage || {};
  const pipeline = status?.pipeline || {};
  const keepRows = checkReadyForCounts ? Number(latestTriage.keep_count || latestTriage.kept_rows || dispatchSource.dispatch_eligible_row_count || 0) : 0;
  const rejectRows = checkReadyForCounts ? Number(latestTriage.reject_count || latestTriage.rejected_count || 0) : 0;
  const quarantineRows = checkReadyForCounts ? Number(latestTriage.quarantine_count || latestTriage.review_count || 0) : 0;
  const inputRows = checkReadyForCounts ? Number(latestCheck.input_rows || pipeline.input_rows || 0) : 0;
  const cleanedRows = checkReadyForCounts ? Number(latestCheck.cleaned_rows || latestCheck.output_rows || pipeline.cleaned_rows || 0) : 0;
  const rejectedRows = checkReadyForCounts ? Number(latestCheck.rejected_rows || latestCheck.reject_count || latestCheck.removed_rows || pipeline.rejected_rows || 0) : 0;
  const sourceRows = Number(dispatchSource.dispatch_eligible_row_count || dispatchSource.dispatch_source_row_count || 0);
  const checkedEligibleRows = checkReadyForCounts ? Number(
    pipeline.dispatch_eligible_rows
    || latestCheck.dispatch_eligible_rows
    || latestCheck.eligible_rows
    || latestCheck.cleaned_rows
    || latestCheck.output_rows
    || sourceRows
    || 0,
  ) : 0;
  const lastCheckCopy = state.checkStatus === "running"
    ? `<span class="leads-check-waiting">Waiting for check output.</span>`
    : state.checkStatus === "failed"
      ? `<span class="leads-check-failed">Check failed or stale.</span>`
      : "No completed check yet.";
  if (els.leadsControlCheckResult) {
    setNodeHtml(
      els.leadsControlCheckResult,
      cleanedRows || rejectedRows || inputRows
        ? [
          ["Input", inputRows],
          ["Cleaned", cleanedRows],
          ["Rejected", rejectedRows],
          ["Keep", keepRows],
          ["Reject", rejectRows],
          ["Quarantine", quarantineRows],
        ].map(([label, value]) => `<span>${escapeHtml(label)} <strong>${Number(value || 0).toLocaleString()}</strong></span>`).join("")
        : `<span>${lastCheckCopy}</span>`,
    );
  }
  const processingReady = state.checkStatus === "completed" && state.triageStatus === "completed";
  const currentBlocker = state.checkStatus === "failed"
    ? "Check Leads failed."
    : state.triageStatus === "failed"
      ? "Fast Triage failed."
      : state.checkStatus === "running"
        ? "Check Leads is running."
        : state.triageStatus === "running"
          ? "Fast Triage is running."
          : "";
  const authIssue = privateJcAuthIssueMessage(lastSnapshot);
  setNodeHtml(
    els.leadsCurrentRunPanel,
    `
      <article class="current-run-card current-source-summary-card ${processingReady ? "current-run-card-ready" : "current-run-card-wait"}">
        <div class="current-run-head">
          <div>
            <p class="eyebrow">Source Summary</p>
            <h3>${processingReady ? "Source ready for preview" : "Source not ready"}</h3>
            <p class="current-run-subtitle">${checkReadyForCounts ? "Counts below describe the current checked and triaged source only." : "Source rows 0 · Not ready for preview until Upload & Check completes."}</p>
          </div>
          <span class="mini-pill">${processingReady ? "Ready" : "Waiting"}</span>
        </div>
        <div class="current-run-metrics">
          <div><span>Input</span><strong>${inputRows.toLocaleString()}</strong></div>
          <div><span>Cleaned</span><strong>${cleanedRows.toLocaleString()}</strong></div>
          <div><span>Rejected</span><strong>${rejectedRows.toLocaleString()}</strong></div>
          <div><span>Keep</span><strong>${keepRows.toLocaleString()}</strong></div>
          <div><span>Dispatch eligible</span><strong>${checkedEligibleRows.toLocaleString()}</strong></div>
        </div>
        ${checkReadyForCounts ? `
          <details class="current-run-details">
            <summary>Triage details</summary>
            <div class="current-run-detail-grid">
              <span>Triage reject <strong>${rejectRows.toLocaleString()}</strong></span>
              <span>Quarantine <strong>${quarantineRows.toLocaleString()}</strong></span>
            </div>
          </details>
        ` : ""}
        ${checkReadyForCounts ? "" : `<div class="operator-empty-state operator-empty-state-inline source-summary-empty"><strong>Source rows 0</strong><span>Upload and check the selected source before previewing dispatch.</span></div>`}
        ${authIssue ? `<div class="current-run-auth-warning">${escapeHtml(authIssue)}</div>` : ""}
        ${currentBlocker ? `<div class="current-run-summary-line current-run-blocker"><span>${escapeHtml(currentBlocker)}</span></div>` : ""}
      </article>
    `,
  );
}

function renderLeadsWorkflowTaskList(status = lastLeadsStatus) {
  if (!els.leadsWorkflowTaskList) return;
  if (warmResearchUploadMode()) {
    const workflow = currentWarmWorkflowState(status);
    const report = workflow.report;
    const activeJob = currentImportantCheckJob(status);
    const running = isActiveImportantLeadCheckJob(activeJob) && activeJob?.upload_type === "warm_research";
    const checked = workflow.valid;
    const draftReady = checked && Number(report.warm_email_preview_rows || 0) > 0;
    const currentConfirmed = checked && Boolean(report.warm_private_jc_confirmed);
    const tasks = [
      {
        step: "Upload Warm Research",
        status: running ? "Waiting" : checked ? "Complete" : workflow.reuploadRequired ? "Re-upload Required" : "Available",
        detail: checked ? `${Number(report.input_rows || 0).toLocaleString()} rows checked` : workflow.reuploadRequired ? "The current job is stale or its required files are unavailable." : "Choose a CSV/XLSX file and click Upload & Check.",
        tone: running ? "warn" : checked ? "good" : workflow.reuploadRequired ? "bad" : "neutral",
      },
      {
        step: "Review Split Outputs",
        status: checked ? "Available" : "Locked",
        detail: checked
          ? `${Number(report.warm_email_ready_rows || 0).toLocaleString()} email ready · ${Number(report.warm_contact_form_rows || 0).toLocaleString()} contact forms`
          : "Locked until a valid current Warm Research upload completes.",
        tone: checked ? "good" : "neutral",
      },
      {
        step: "Generate Draft Preview",
        status: draftReady ? "Complete" : checked ? "Available" : "Locked",
        detail: draftReady
          ? `${Number(report.warm_email_preview_rows || 0).toLocaleString()} preview-only drafts generated`
          : checked ? "Creates warm_email_preview.csv without writing sender queues." : "Locked until current split outputs are valid.",
        tone: draftReady ? "good" : checked ? "warn" : "neutral",
      },
      {
        step: "Warm Private JC",
        status: currentConfirmed ? "Complete" : draftReady ? "Required" : "Locked",
        detail: checked ? "Uses the separate Warm Private JC queue and never routes through SendGrid." : "Locked until the current upload has a valid draft preview.",
        tone: currentConfirmed ? "good" : "neutral",
      },
    ];
    setNodeHtml(
      els.leadsWorkflowTaskList,
      `
        <div class="workflow-tracker-head"><p class="eyebrow">Warm Research Workflow</p></div>
        <ol class="workflow-tracker-row warm-workflow-tracker" aria-label="Warm Research check workflow">
          ${tasks.map((task, index) => `
            <li class="workflow-track-step workflow-track-step-${escapeHtml(task.tone)}">
              <span class="workflow-track-number">${index + 1}</span>
              <span class="workflow-track-copy"><strong>${escapeHtml(task.step)}</strong><em>${escapeHtml(task.status)}</em><small>${escapeHtml(task.detail)}</small></span>
            </li>
          `).join("")}
        </ol>
      `,
    );
    return;
  }
  const state = currentRunWorkflowState(status);
  const latestCheck = state.latestCheck || {};
  const latestTriage = state.latestTriage || {};
  const dispatchSource = dispatchSourceForSelectedMode().source || {};
  const checkRows = Number(latestCheck.cleaned_rows || latestCheck.output_rows || latestCheck.input_rows || 0);
  const checkRejected = Number(latestCheck.rejected_rows || latestCheck.reject_count || latestCheck.removed_rows || 0);
  const keepRows = Number(latestTriage.keep_count || latestTriage.kept_rows || dispatchSource.dispatch_source_row_count || 0);
  const rejectRows = Number(latestTriage.reject_count || latestTriage.rejected_count || 0);
  const quarantineRows = Number(latestTriage.quarantine_count || latestTriage.review_count || 0);
  const selectedCampaign = selectedImportantDispatchCampaignType();
  const previewCurrent = Boolean(lastImportantDispatchPreview && dispatchPreviewMatchesCurrentSelection());
  const selectedSource = selectedDispatchSourceLabel(dispatchSource, previewCurrent ? lastImportantDispatchPreview : null);
  const confirmReady = dispatchConfirmSafetyState(dispatchSource, previewCurrent ? lastImportantDispatchPreview : null).ready;
  const hasUpload = Boolean(state.activeCheck?.job_id || latestCheck?.generated_at_utc);
  const checkFailed = state.checkStatus === "failed";
  const triageLocked = state.checkStatus !== "completed";
  const previewBlocked = currentRunPreviewBlockMessage(dispatchSource, state);
  const tasks = [
    {
      step: "Source",
      status: hasUpload ? "Complete" : "Waiting",
      detail: hasUpload ? "A source is staged for the selected upload type." : "Choose a CSV/XLSX source.",
      tone: hasUpload ? "good" : "neutral",
    },
    {
      step: "Check",
      status: state.checkStatus === "completed" ? "Complete" : checkFailed ? "Failed/Stale" : state.checkStatus === "running" ? "Running" : "Waiting",
      detail: checkRows ? `${checkRows.toLocaleString()} cleaned, ${checkRejected.toLocaleString()} rejected` : state.checkStatus === "running" ? "Waiting for leads.csv and leads_rejected.csv." : "Run Upload & Check.",
      tone: state.checkStatus === "completed" ? "good" : checkFailed ? "bad" : state.checkStatus === "running" ? "warn" : "neutral",
    },
    {
      step: "Triage",
      status: state.triageStatus === "completed" ? "Complete" : triageLocked ? "Locked" : state.triageStatus === "running" ? "Running" : "Waiting",
      detail: keepRows ? `${keepRows.toLocaleString()} keep, ${rejectRows.toLocaleString()} reject, ${quarantineRows.toLocaleString()} quarantine` : triageLocked ? "Locked until check completes." : "Run Fast Triage after Check.",
      tone: state.triageStatus === "completed" ? "good" : state.triageStatus === "running" ? "warn" : "neutral",
    },
    {
      step: "Preview",
      status: previewCurrent ? "Complete" : previewBlocked ? "Locked" : "Ready",
      detail: previewCurrent ? "Preview matches selected source and cap." : previewBlocked || `${selectedSource}. ${selectedCampaign === "cold" ? "Fresh Cold" : "Recontact"} mode ready to preview.`,
      tone: previewCurrent ? "good" : previewBlocked ? "neutral" : "warn",
    },
    {
      step: "Confirm",
      status: confirmReady ? "Ready" : "Locked",
      detail: "Confirm writes queues only after preview passes.",
      tone: confirmReady ? "good" : "neutral",
    },
  ];
  setNodeHtml(
    els.leadsWorkflowTaskList,
    `
      <div class="workflow-tracker-head">
        <p class="eyebrow">Workflow Tracker</p>
        <span>${escapeHtml(isCurrentSaferRecontactSource(dispatchSource, previewCurrent ? lastImportantDispatchPreview : null) ? "Safer Recontact" : selectedCampaign === "cold" ? "Fresh Cold" : "Recontact")}</span>
      </div>
      <ol class="workflow-tracker-row" aria-label="Lead dispatch workflow">
        ${tasks.map((task, index) => `
          <li class="workflow-track-step workflow-track-step-${escapeHtml(task.tone)}">
            <span class="workflow-track-number">${index + 1}</span>
            <span class="workflow-track-copy">
              <strong>${escapeHtml(task.step)}</strong>
              <em>${escapeHtml(task.status)}</em>
              <small>${escapeHtml(task.detail)}</small>
            </span>
          </li>
        `).join("")}
      </ol>
    `,
  );
}

function renderLeadsWorkflowStatusBanner(status = lastLeadsStatus) {
  if (!els.leadsWorkflowStatusBanner) return;
  if (warmResearchUploadMode()) {
    const workflow = currentWarmWorkflowState(status);
    const report = workflow.report;
    const historicalReport = workflow.historicalReport;
    setNodeHtml(
      els.leadsWorkflowStatusBanner,
      `
        <div class="warm-post-command-grid">
          <section class="warm-research-output-group">
            <div class="warm-panel-heading">
              <div>
                <p class="eyebrow">Current workflow outputs</p>
                <strong>${workflow.reuploadRequired ? "Re-upload required" : "Warm Research Outputs"}</strong>
              </div>
              ${workflow.valid && Number(report.warm_email_preview_rows || 0) > 0 ? `<span class="mini-pill">Draft preview ready</span>` : ""}
            </div>
            ${warmResearchMetricMarkup(report)}
            ${workflow.valid ? "" : `<p class="muted">Current metrics are cleared and actions remain locked until a valid current upload completes.</p>`}
            ${historicalReport?.generated_at_utc ? `
              <details class="previous-warm-run">
                <summary>Previous Warm Outreach Run</summary>
                <p class="muted">Historical results — not current workflow state</p>
                ${warmResearchMetricMarkup(historicalReport)}
              </details>
            ` : ""}
          </section>
          <aside class="warm-safety-card">
            <p class="eyebrow">Safety Rules</p>
            <div class="warm-safety-rules">
              <span>Cold dispatch disabled for Warm Research</span>
              <span>Explicit confirmation required</span>
              <span>Warm Outreach uses individual sender controls</span>
              <span>Warm confirmation stays separate</span>
            </div>
          </aside>
        </div>
      `,
    );
    return;
  }
  const state = currentRunWorkflowState(status);
  const dispatchSource = dispatchSourceForSelectedMode().source || {};
  const dispatchPreview = dispatchPreviewMatchesCurrentSelection() ? lastImportantDispatchPreview : null;
  const dispatchSummary = dispatchPreviewRouteSummary(dispatchPreview, dispatchSource);
  const confirmedQueue = confirmedDispatchQueueState(status);
  const stagedRunWarning = confirmedQueue.liveMatches && currentRunPreviewBlockMessage(dispatchSource, state)
    ? "New staged run not ready — previous dispatch is queued."
    : "";
  const headline = dispatchSummary.sentLogOverlap > 0
    ? `BLOCKED — Planned recipients overlap authoritative sent/contact logs: ${dispatchSummary.sentLogOverlap.toLocaleString()}.`
    : dispatchSummary.skippedMathMismatch
      ? `BLOCKED — Skipped rows ${dispatchSummary.skippedRows.toLocaleString()} do not match skipped reasons ${dispatchSummary.skippedReasonTotal.toLocaleString()}.`
      : dispatchSummary.historyRemoved && state.previewStatus === "completed"
        ? `SAFE — History filter excluded ${dispatchSummary.historyRemoved.toLocaleString()} already-sent/contacted rows. ${dispatchSummary.uniquePlanned.toLocaleString()} cold-safe leads remain.`
        : state.triageStatus === "completed" && state.previewStatus !== "completed"
      ? "READY — Preview Dispatch required before Confirm."
      : workflowNextStepMessage(state.checkStatus, state.triageStatus, state.previewStatus, state.confirmStatus);
  setNodeHtml(
    els.leadsWorkflowStatusBanner,
    `
      <div class="workflow-banner-inline">
        <span class="eyebrow">Current step</span>
        <strong>${escapeHtml(headline)}</strong>
      </div>
      ${stagedRunWarning ? `<div class="workflow-staged-warning">${escapeHtml(stagedRunWarning)}</div>` : ""}
    `,
  );
}

function renderLeadsOperatorStatusStrip(status = lastLeadsStatus) {
  if (!els.leadsOperatorStatusStrip) return;
  const safety = leadsRunSafety(status);
  const leadCheck = currentLeadCheckStatus(status);
  const latestCheck = selectedLeadCheckReport(status);
  const latestTriage = selectedLeadTriageReport(status, leadCheck);
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
    const currentSafety = status?.current_send_safety || {};
    const newDispatchOnly = sourceComparisonOnlySafety(currentSafety) || newDispatchOnlySafetyWarning(currentSafety, status);
    const context = queueSafetySourceContext(currentSafety);
    const reasonText = (Array.isArray(currentSafety.reasons) && currentSafety.reasons.length
      ? currentSafety.reasons.map(queueSafetyReasonLabel).join(" ")
      : safety.reasons[0] || "Recipient queue unsafe.");
    cards.push({
      severity: newDispatchOnly ? "warn" : "bad",
      title: newDispatchOnly ? "New dispatch source warning" : "Current live queue blocked",
      message: newDispatchOnly ? newDispatchWarningMessage(reasonText, context) : `${reasonText}${context ? ` ${context}.` : ""}`,
      blocks: !newDispatchOnly,
    });
  } else if (Array.isArray(safety.queueWarnings) && safety.queueWarnings.length) {
    const currentSafety = status?.current_send_safety || {};
    const context = queueSafetySourceContext(currentSafety);
    const reasonText = safety.queueWarnings.map(queueSafetyReasonLabel).join(" ");
    const sourceWarning = safety.queueWarnings.every((reason) => isSourceComparisonSafetyReason(reason));
    cards.push({
      severity: "warn",
      title: sourceWarning ? "New dispatch source warning" : "Inactive live queue warning",
      message: sourceWarning
        ? newDispatchWarningMessage(reasonText, context)
        : `No live queue is active, so this does not block Preview Dispatch. ${reasonText}${context ? ` ${context}.` : ""}`.trim(),
      blocks: false,
    });
  } else if (currentLiveDispatchState(status).hasLiveQueue) {
    cards.push({
      severity: "good",
      title: "Current live dispatch: Ready",
      message: "The already confirmed current live dispatch does not show a blocking start alert.",
      blocks: false,
    });
  }
  const currentSafety = status?.current_send_safety || {};
  if (currentSafety.sendgrid_status && currentSafety.private_status && currentSafety.sendgrid_status !== currentSafety.private_status) {
    cards.push({
      severity: currentSafety.private_status === "READY" ? "warn" : "bad",
      title: `${currentSafety.sendgrid_status === "READY" ? "SendGrid ready" : "SendGrid blocked"}; ${currentSafety.private_status === "READY" ? "Private JC ready" : "Private JC blocked"}`,
      message: "Provider-specific queue safety controls each individual Start button.",
      blocks: currentSafety.private_status !== "READY" || currentSafety.sendgrid_status !== "READY",
    });
  }
  (Array.isArray(snapshot?.alerts) ? snapshot.alerts : []).forEach((alert) => {
    const alertText = `${alert?.title || ""} ${alert?.message || ""}`.toLowerCase();
    const sendgridPending = Array.isArray(status?.sendgrid_queues)
      ? status.sendgrid_queues.reduce((sum, queue) => sum + Number(queue.count || 0), 0)
      : 0;
    if (alertText.includes("booktitle") && sendgridPending <= 0 && !Boolean(alert?.blocks_sending)) {
      return;
    }
    const alertNewDispatchOnly = alertLooksLikeNewDispatchSourceWarning(alert, currentSafety, status);
    cards.push({
      severity: alertNewDispatchOnly ? "warn" : (alert?.severity || "warn"),
      title: alertNewDispatchOnly ? "New dispatch source warning" : (alert?.title || "Alert"),
      message: alertNewDispatchOnly ? newDispatchWarningMessage(alert?.message || "") : (alert?.message || ""),
      blocks: alertNewDispatchOnly ? false : Boolean(alert?.blocks_sending),
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
  const blockingCount = cards.filter((card) => Boolean(card.blocks)).length;
  const warningCount = cards.filter((card) => !card.blocks && String(card.severity || "").toLowerCase() === "warn").length;
  const infoCount = Math.max(0, cards.length - blockingCount - warningCount);
  const leadCard = cards.find((card) => Boolean(card.blocks))
    || cards.find((card) => String(card.severity || "").toLowerCase() === "warn")
    || cards[0];
  setNodeHtml(
    els.leadsActiveAlerts,
    `
      <div class="leads-alert-summary-row leads-alert-summary-${blockingCount ? "bad" : warningCount ? "warn" : "good"}">
        <div>
          <strong>${warningCount.toLocaleString()} warning${warningCount === 1 ? "" : "s"}</strong>
          <span>${blockingCount.toLocaleString()} blocking · ${infoCount.toLocaleString()} info</span>
        </div>
        <p>${escapeHtml(leadCard?.title || "No active lead safety alerts")}</p>
      </div>
      <details class="leads-collapsible advanced-details leads-alert-details">
        <summary>Safety messages</summary>
        <div class="leads-alert-detail-list">
          ${cards.slice(0, 6).map((card) => `
            <article class="leads-alert-card leads-alert-card-${escapeHtml(card.severity || "warn")}">
              <div>
                <strong>${escapeHtml(card.title)}</strong>
                <p>${escapeHtml(card.message || "No details provided.")}</p>
              </div>
              <span class="mini-pill">${card.blocks ? "Blocking" : String(card.severity || "").toLowerCase() === "warn" ? "Warning" : "Info"}</span>
            </article>
          `).join("")}
        </div>
      </details>
    `,
  );
}

function renderLeadsRunSafety(status = lastLeadsStatus) {
  if (!els.leadsRunSafetyCard) return;
  const safety = leadsRunSafety(status);
  const progress = safety.progress || {};
  const progressText = progress.total > 0
    ? `${progress.processed} / ${progress.total} (${progress.percent.toFixed(1)}%)`
    : "n/a";
  const reasons = safety.reasons.length
    ? safety.reasons
    : (Array.isArray(safety.queueWarnings) && safety.queueWarnings.length
      ? safety.queueWarnings
      : ["Live recipient queues are approved for current sending."]);
  const currentSafety = status?.current_send_safety || {};
  const warningOnly = !safety.queueUnsafe && Array.isArray(safety.queueWarnings) && safety.queueWarnings.length > 0;
  const sourceWarningOnly = warningOnly && safety.queueWarnings.every((reason) => isSourceComparisonSafetyReason(reason));
  const newDispatchOnly = warningOnly || sourceComparisonOnlySafety(currentSafety) || newDispatchOnlySafetyWarning(currentSafety, status);
  const displayStatusLabel = (safety.queueUnsafe && newDispatchOnly) || warningOnly ? "WARNING" : safety.statusLabel;
  const tone = displayStatusLabel === "SAFE TO CONTINUE" ? "safe-to-continue" : displayStatusLabel.toLowerCase().replace(/\s+/g, "-");
  const currentSafetyTitle = safety.queueUnsafe
    ? (newDispatchOnly ? "New dispatch source warning" : "Current live queue blocked")
    : (warningOnly ? (sourceWarningOnly ? "New dispatch source warning" : "Inactive live queue warning") : "Current live queue ready");
  const currentSafetyScope = "Current approved live queues only";
  const sourceContext = queueSafetySourceContext(currentSafety);
  const liveQueueDisplay = safety.queueUnsafe && !newDispatchOnly ? "Blocked" : "Ready";
  setNodeHtml(
    els.leadsRunSafetyCard,
    `
      <div class="leads-run-safety-head">
        <div>
          <p class="eyebrow">Current Run Safety</p>
          <h3>${escapeHtml(currentSafetyTitle)}</h3>
          <strong>${escapeHtml(displayStatusLabel)}</strong>
        </div>
        <span class="mini-pill">${escapeHtml(currentSafetyScope)}</span>
      </div>
      <div class="leads-run-safety-body">
        <div class="leads-run-safety-reasons">
          ${reasons.map((reason) => `<div>${escapeHtml(queueSafetyReasonLabel(reason))}</div>`).join("")}
          ${sourceContext ? `<div>${escapeHtml(sourceContext)}</div>` : ""}
        </div>
        ${renderOperatorMetricStrip([
          { label: "Live Queue", value: liveQueueDisplay, tone: liveQueueDisplay === "Ready" ? "good" : "warn" },
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
      setNodeText(els.toolbarGeneratedAt, "Local snapshot");
    }
  }
  const selectedCheckIsRunning = leadCheckWorkflowStatus(currentLeadCheckStatus(lastLeadsStatus)) === "running";
  const activeCheckJob = selectedCheckIsRunning ? currentImportantCheckJob(lastLeadsStatus) : null;
  if (!selectedCheckIsRunning) {
    stopImportantLeadCheckJobPolling();
  }
  const coldWorkflow = selectedLeadUploadType() === "cold";
  const activeVerifyJob = coldWorkflow ? (lastLeadsStatus?.active_important_verify_job || null) : null;
  const activeDispatchJob = coldWorkflow ? (lastLeadsStatus?.active_important_dispatch_job || null) : null;
  const shouldResumeLeadJobs = isLeadsTabVisible();
  syncImportantLeadPathInputs(lastLeadsStatus);
  syncImportantVerifyPathInputs(lastLeadsStatus);
  syncImportantDispatchSourceMode(lastLeadsStatus);
  updateImportantLeadPasteGuardrails();
  const warmUploadSelected = warmResearchUploadMode();
  applyWarmResearchLayoutState(warmUploadSelected);
  lastImportantLeadCheck = selectedLeadCheckReport(lastLeadsStatus);
  lastImportantVerify = selectedLeadTriageReport(lastLeadsStatus);
  lastImportantDispatch = warmUploadSelected ? {} : (lastLeadsStatus?.latest_dispatch || {});
  lastImportantDispatchSource = lastLeadsStatus?.dispatch_source || lastImportantDispatchSource;
  if (lastLeadsStatus?.safer_recontact_source_summary && typeof lastLeadsStatus.safer_recontact_source_summary === "object") {
    lastSaferRecontactSummary = lastLeadsStatus.safer_recontact_source_summary;
  }
  hydrateImportantDispatchPreviewFromStatus(lastLeadsStatus);
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
  renderLeadCheckStatusCard(lastLeadsStatus);
  renderLeadsWorkflowTaskList(lastLeadsStatus);
  renderLeadsCurrentRunPanel(lastLeadsStatus);
  renderLeadsCurrentQueueNote(lastLeadsStatus);
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
      `Eligible in checked output ${Number(pipeline?.dispatch_eligible_rows || 0)}`,
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
  const uploadTypeLabel = warmResearchUploadMode() ? "Warm Research" : "Cold Leads";
  updateImportantLeadUploadNote(`Submitting ${filename} as ${uploadTypeLabel} (${humanizeFileSize(size)}, ${extension || "no extension"}).`);
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

async function generateWarmDraftPreview() {
  if (!warmResearchUploadMode()) {
    showMessage("Select Warm Research before generating a warm draft preview.", "error");
    return;
  }
  warmDraftPreviewLoading = true;
  renderLeadsCurrentRunPanel(lastLeadsStatus);
  try {
    const data = await fetchJson("/api/leads/check-important/warm-preview", { method: "POST" });
    lastImportantLeadCheck = data.warm_check || lastImportantLeadCheck;
    if (data.status) {
      renderLeadsStatus(data.status);
    } else {
      renderLeadsCurrentRunPanel(lastLeadsStatus);
      renderLeadsWorkflowTaskList(lastLeadsStatus);
      renderLeadsWorkflowStatusBanner(lastLeadsStatus);
    }
    showMessage(data.message || "Warm draft preview generated.", "success");
  } catch (err) {
    showMessage(`Warm draft preview failed: ${err}`, "error");
  } finally {
    warmDraftPreviewLoading = false;
    renderLeadsCurrentRunPanel(lastLeadsStatus);
  }
}

async function confirmWarmPrivateJc() {
  if (!warmResearchUploadMode()) {
    showMessage("Select Warm Research before confirming Warm Private JC.", "error");
    return;
  }
  try {
    const data = await fetchJson("/api/leads/check-important/warm-confirm", { method: "POST" });
    lastImportantLeadCheck = data.warm_check || lastImportantLeadCheck;
    if (data.status) renderLeadsStatus(data.status);
    showMessage(data.message || "Warm Private JC confirmed.", "success");
    await fetchSnapshot();
  } catch (err) {
    showMessage(`Warm Private JC confirmation failed: ${err}`, "error");
  }
}

async function startWarmPrivateJc() {
  if (!warmResearchUploadMode()) {
    showMessage("Select Warm Research before starting Warm Private JC.", "error");
    return;
  }
  await postAction("/api/start/private_jc_warm", { profileName: "private_jc_warm", action: "start" });
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

function previewDispatchBlockedFeedback(payload = {}, fallbackMessage = "") {
  const errorCode = String(payload?.error || "").trim();
  const rawMessage = String(payload?.message || fallbackMessage || "Preview Dispatch was blocked.").trim();
  const retryAction = String(payload?.retry_action || "").trim();
  const sourcePath = String(payload?.source_path || payload?.dispatch_source_path || "").trim();
  const messageParts = [];
  if (errorCode === "triage_not_ready" || rawMessage.toLowerCase().includes("current staged fast triage keep is empty")) {
    messageParts.push("Current staged Fast Triage Keep is empty.");
    messageParts.push("Run Check Leads / Fast Triage first.");
  } else if (rawMessage) {
    messageParts.push(rawMessage);
  }
  if (retryAction) {
    messageParts.push(`Retry action: ${retryAction}`);
  }
  if (sourcePath) {
    messageParts.push(`Source path: ${sourcePath}`);
  }
  return {
    state: "blocked",
    message: messageParts.join(" "),
    error: errorCode,
    source_path: sourcePath,
    retry_action: retryAction,
  };
}

async function pollImportantLeadDispatchPreviewJob(jobId) {
  if (!jobId) return;

  try {
    const data = await fetchJson(
      `/api/leads/check-important/job/${encodeURIComponent(jobId)}`,
    );
    const job = data.job || {};
    const previewStatus = String(
      job.auto_dispatch_preview_status || "",
    ).toLowerCase();

    if (data.status) {
      renderLeadsStatus(data.status || {});
    }

    if (previewStatus === "completed") {
      const preview =
        job.auto_dispatch_preview
        || data.status?.latest_auto_dispatch_preview
        || {};

      importantLeadDispatchPreviewLoading = false;

      if (preview?.preview_id) {
        lastImportantDispatchPreview = {
          ...(preview || {}),
          _preview_key: currentDispatchPlanKey(),
        };
        lastImportantDispatchPreviewState = "ready";
        lastImportantDispatchPreviewFeedback = {
          state: "ready",
          message: "Preview ready.",
        };
        renderImportantDispatch(lastImportantDispatch);
        renderLeadsWorkflowStatusBanner(lastLeadsStatus);
        showMessage("Dispatch preview ready.", "success");
      } else {
        lastImportantDispatchPreviewState = "failed";
        lastImportantDispatchPreviewFeedback = {
          state: "failed",
          message: "Preview completed but the saved preview could not be loaded.",
        };
        renderImportantDispatch(lastImportantDispatch);
        renderLeadsWorkflowStatusBanner(lastLeadsStatus);
        showMessage(
          "Preview completed but the saved preview could not be loaded.",
          "error",
        );
      }

      [
        els.leadsImportantDispatchPreviewBtn,
        els.leadsImportantDispatchPreviewTopBtn,
      ].filter(Boolean).forEach((button) => {
        setButtonBusy(button, false, "Preview Dispatch");
      });

      return;
    }

    if (previewStatus === "failed") {
      importantLeadDispatchPreviewLoading = false;
      lastImportantDispatchPreviewState = "failed";
      lastImportantDispatchPreviewFeedback = {
        state: "failed",
        message:
          job.auto_dispatch_preview_error
          || "Preview Dispatch failed.",
      };

      renderImportantDispatch(lastImportantDispatch);
      renderLeadsWorkflowStatusBanner(lastLeadsStatus);

      [
        els.leadsImportantDispatchPreviewBtn,
        els.leadsImportantDispatchPreviewTopBtn,
      ].filter(Boolean).forEach((button) => {
        setButtonBusy(button, false, "Preview Dispatch");
      });

      showMessage(lastImportantDispatchPreviewFeedback.message, "error");
      return;
    }

    importantLeadDispatchPreviewLoading = true;
    lastImportantDispatchPreviewState = "running";
    lastImportantDispatchPreviewFeedback = {
      state: "running",
      message: "Preview Dispatch is running.",
    };

    renderImportantDispatch(lastImportantDispatch);
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);

    setTimeout(
      () => pollImportantLeadDispatchPreviewJob(jobId),
      1500,
    );
  } catch (err) {
    lastImportantDispatchPreviewState = "running";
    lastImportantDispatchPreviewFeedback = {
      state: "running",
      message: `Preview status check retrying: ${String(err || "")}`,
    };

    setTimeout(
      () => pollImportantLeadDispatchPreviewJob(jobId),
      2500,
    );
  }
}


async function previewImportantLeadDispatch() {
  if (warmResearchUploadMode()) {
    showMessage("Warm Research does not use Cold Dispatch Preview. Generate drafts and confirm Warm Private JC instead.", "error");
    return;
  }
  const selectedDispatchSource = dispatchSourceForSelectedMode();
  const blockReason = dispatchPreviewBlockReason(selectedDispatchSource.source || {});
  if (blockReason) {
    lastImportantDispatchPreviewFeedback = { state: "blocked", message: blockReason };
    lastImportantDispatchPreviewState = "blocked";
    renderImportantDispatch(lastImportantDispatch);
    showMessage(`Dispatch preview blocked: ${blockReason}`, "error");
    return;
  }
  if (activeSenderProfiles().length) {
    const activeReason = `Active senders are running: ${activeSenderProfiles().map((profile) => formatProfileName(profile.name)).join(", ")}.`;
    lastImportantDispatchPreviewFeedback = { state: "blocked", message: activeReason };
    lastImportantDispatchPreviewState = "blocked";
    renderImportantDispatch(lastImportantDispatch);
    showMessage(`Dispatch blocked: stop active senders first. Active: ${activeSenderProfiles().map((profile) => formatProfileName(profile.name)).join(", ")}`, "error");
    return;
  }
  if (els.leadsImportantDispatchPreviewBtn) {
    importantLeadDispatchPreviewLoading = true;
    lastImportantDispatchPreviewState = "running";
    lastImportantDispatchPreviewFeedback = { state: "running", message: "Preview Dispatch is running." };
    [els.leadsImportantDispatchPreviewBtn, els.leadsImportantDispatchPreviewTopBtn].filter(Boolean).forEach((button) => {
      setButtonBusy(button, true, "Previewing...");
    });
    renderImportantDispatch(lastImportantDispatch);
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
    showMessage("Preview Dispatch request started.", "success");
  }
  try {
    const data = await fetchJson("/api/leads/dispatch-important/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(importantLeadDispatchPayload(false)),
    });
    if (data.accepted && data.job?.job_id) {
      lastImportantDispatchPreviewState = "running";
      lastImportantDispatchPreviewFeedback = {
        state: "running",
        message: data.message || "Preview Dispatch is running.",
      };

      if (data.status) {
        renderLeadsStatus(data.status || {});
      }

      renderImportantDispatch(lastImportantDispatch);
      renderLeadsWorkflowStatusBanner(lastLeadsStatus);
      showMessage(data.message || "Preview Dispatch started.", "success");

      void pollImportantLeadDispatchPreviewJob(data.job.job_id);
      return;
    }

    if (data.preview?.preview_id) {
      lastImportantDispatchPreview = {
        ...(data.preview || {}),
        _preview_key: currentDispatchPlanKey(),
      };
      lastImportantDispatchPreviewState = "ready";
      lastImportantDispatchPreviewFeedback = { state: "ready", message: "Preview ready." };
      if (data.status) {
        renderLeadsStatus(data.status || {});
      } else {
        renderImportantDispatch(lastImportantDispatch);
      }
      showMessage(data.message || "Dispatch preview ready.", "success");
    } else {
      lastImportantDispatchPreviewState = "failed";
      lastImportantDispatchPreviewFeedback = { state: "failed", message: "Preview did not save. Please retry." };
      renderImportantDispatch(lastImportantDispatch);
      showMessage("Preview did not save. Please retry.", "error");
    }
  } catch (err) {
    const payload = err?.payload || {};
    const blocked = Boolean(payload?.blocked) || Boolean(payload?.error);
    lastImportantDispatchPreviewState = blocked ? "blocked" : "failed";
    lastImportantDispatchPreviewFeedback = blocked
      ? previewDispatchBlockedFeedback(payload, String(err || "Preview Dispatch was blocked."))
      : { state: "failed", message: `Preview Dispatch API failure: ${String(err || "Preview Dispatch failed.")}` };
    renderImportantDispatch(lastImportantDispatch);
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
    showMessage(
      blocked
        ? `Dispatch preview blocked: ${lastImportantDispatchPreviewFeedback.message}`
        : lastImportantDispatchPreviewFeedback.message,
      "error",
    );
  } finally {
    const previewStillRunning =
      lastImportantDispatchPreviewState === "running";

    importantLeadDispatchPreviewLoading = previewStillRunning;

    if (els.leadsImportantDispatchPreviewBtn) {
      const activeDispatch =
        isActiveImportantLeadCheckJob(lastImportantDispatchJob);
      const previewBusy = previewStillRunning || activeDispatch;

      [
        els.leadsImportantDispatchPreviewBtn,
        els.leadsImportantDispatchPreviewTopBtn,
      ].filter(Boolean).forEach((button) => {
        setButtonBusy(
          button,
          previewBusy,
          previewStillRunning ? "Previewing..." : "Preview Dispatch",
        );
      });
      renderDispatchConfirmGuard(dispatchSourceForSelectedMode().source || {}, dispatchPreviewMatchesCurrentSelection() ? lastImportantDispatchPreview : null);
    }
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
  }
}

async function confirmImportantLeadDispatch() {
  const blockReason = dispatchActionBlockReason();
  if (blockReason) {
    lastImportantDispatchConfirmFeedback = { state: "blocked", message: blockReason };
    renderImportantDispatch(lastImportantDispatch);
    showMessage(`Confirm Dispatch blocked: ${blockReason}`, "error");
    return;
  }
  if (activeSenderProfiles().length) {
    const message = `Dispatch blocked: stop active senders first. Active: ${activeSenderProfiles().map((profile) => formatProfileName(profile.name)).join(", ")}`;
    lastImportantDispatchConfirmFeedback = { state: "blocked", message };
    renderImportantDispatch(lastImportantDispatch);
    showMessage(message, "error");
    return;
  }
  if (!dispatchPreviewMatchesCurrentSelection() || !lastImportantDispatchPreview?.preview_id) {
    lastImportantDispatchConfirmFeedback = { state: "blocked", message: "Run Preview Dispatch first for the current source and cap." };
    renderImportantDispatch(lastImportantDispatch);
    showMessage("Run Preview Dispatch first for the current source and cap.", "error");
    return;
  }
  if (recontactRecencyOverrideRequired(lastImportantDispatchPreview)) {
    const message = "Recontact preview has high recent-contact overlap. Confirm requires explicit override.";
    lastImportantDispatchConfirmFeedback = { state: "blocked", message };
    renderImportantDispatch(lastImportantDispatch);
    showMessage(message, "error");
    return;
  }
  if (els.leadsImportantDispatchConfirmBtn) {
    importantLeadDispatchConfirmLoading = true;
    lastImportantDispatchConfirmFeedback = { state: "running", message: "Confirm Dispatch is running." };
    setButtonBusy(els.leadsImportantDispatchConfirmBtn, true, "Dispatching...");
    renderImportantDispatch(lastImportantDispatch);
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
  }
  try {
    const data = await fetchJson("/api/leads/dispatch-important/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(importantLeadDispatchPayload(true)),
    });
    if (data.job?.job_id) {
      lastImportantDispatchConfirmFeedback = { state: "queued", message: data.message || "Lead dispatch queued." };
      renderImportantLeadDispatchJob(data.job);
      void pollImportantLeadDispatchJob(data.job.job_id);
      showMessage(data.message || "Lead dispatch queued.", "success");
    } else {
      lastImportantDispatchConfirmFeedback = { state: "failed", message: "Dispatch confirm did not return a job." };
      renderImportantDispatch(lastImportantDispatch);
      showMessage("Dispatch confirm did not return a job.", "error");
    }
  } catch (err) {
    lastImportantDispatchConfirmFeedback = { state: "failed", message: String(err || "Lead dispatch failed.") };
    renderImportantDispatch(lastImportantDispatch);
    showMessage(`Lead dispatch failed: ${err}`, "error");
  } finally {
    importantLeadDispatchConfirmLoading = false;
    if (els.leadsImportantDispatchConfirmBtn) {
      const activeDispatch = isActiveImportantLeadCheckJob(lastImportantDispatchJob);
      setButtonBusy(els.leadsImportantDispatchConfirmBtn, activeDispatch, activeDispatch ? "Dispatching..." : importantDispatchConfirmButtonLabel());
      renderDispatchConfirmGuard(dispatchSourceForSelectedMode().source || {}, dispatchPreviewMatchesCurrentSelection() ? lastImportantDispatchPreview : null);
    }
    renderLeadsWorkflowStatusBanner(lastLeadsStatus);
  }
}

async function createSaferRecontactPool() {
  const preview = latestRecontactPreviewContext(lastImportantDispatchPreview);
  if (!preview?.preview_id) {
    lastSaferRecontactFeedback = { state: "bad", message: "Run a Recontact preview before creating safer leads." };
    renderImportantDispatch(lastImportantDispatch);
    showMessage("Run a current Recontact preview before creating a safer pool.", "error");
    return;
  }
  saferRecontactPoolLoading = true;
  lastSaferRecontactFeedback = { state: "running", message: "Creating safer recontact leads..." };
  renderImportantDispatch(lastImportantDispatch);
  try {
    const data = await fetchJson("/api/leads/dispatch-important/safer-recontact-pool", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...importantLeadDispatchPayload(false),
        preview_id: preview.preview_id,
        campaign_type: "recontact_cold",
        dispatch_source_mode: "cleaned",
      }),
    });
    lastSaferRecontactSummary = data.summary || null;
    lastSaferRecontactFeedback = {
      state: "good",
      message: `${Number(lastSaferRecontactSummary?.safer_rows_written || 0).toLocaleString()} safer recontact leads created.`,
    };
    renderImportantDispatch(lastImportantDispatch);
    showMessage(data.message || "Safer recontact pool created.", "success");
  } catch (err) {
    lastSaferRecontactFeedback = { state: "bad", message: `Create safer recontact leads failed: ${String(err || "Unknown error")}` };
    renderImportantDispatch(lastImportantDispatch);
    showMessage(`Safer recontact pool failed: ${err}`, "error");
  } finally {
    saferRecontactPoolLoading = false;
    renderImportantDispatch(lastImportantDispatch);
  }
}

function useSaferRecontactPoolAsSelectedSource() {
  const saferPath = String(lastSaferRecontactSummary?.output_path || "").trim();
  if (!saferPath) {
    void createSaferRecontactPool();
    return;
  }
  if (els.leadsImportantDispatchCampaignType) els.leadsImportantDispatchCampaignType.value = "recontact_cold";
  if (els.leadsImportantDispatchSourceMode) els.leadsImportantDispatchSourceMode.value = "cleaned";
  if (els.leadsImportantOutputPath) els.leadsImportantOutputPath.value = saferPath;
  if (els.leadsRecontactRecencyOverride) els.leadsRecontactRecencyOverride.checked = false;
  lastImportantDispatchPreview = null;
  lastImportantDispatchPreviewState = "not_generated";
  lastImportantDispatchPreviewFeedback = {
    state: "ready",
    message: "Safer recontact pool selected. Run Preview Dispatch to calculate queue assignments.",
  };
  syncImportantDispatchCampaignSource();
  renderImportantDispatch(lastImportantDispatch);
  showMessage("Safer recontact pool selected. Run Preview Dispatch before confirming.", "success");
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
  const total_awaiting_outcome = Number(summary?.total_awaiting_outcome || 0);
  const alerts = Array.isArray(snapshot.alerts) ? snapshot.alerts : [];
  const profiles = Array.isArray(snapshot.profiles) ? snapshot.profiles : [];
  const sendgridProfiles = profiles.filter((profile) => profileTelemetryChannel(profile) === "sendgrid");
  const privateProfile = profiles.find((profile) => profile.name === "private_jc")
    || profiles.find((profile) => profileTelemetryChannel(profile) === "private");
  const activeStates = new Set(["starting", "running", "sleeping", "cooldown", "paused"]);
  const sendgridRunning = sendgridProfiles.filter((profile) => activeStates.has(String(profile?.runtime_state || ""))).length;
  const alertIsInfo = (alert) => ["ok", "info"].includes(String(alert?.severity || "").trim().toLowerCase())
    || String(alert?.blocking_label || "").trim().toLowerCase() === "info";
  const alertGroups = {
    blocking: alerts.filter((alert) => Boolean(alert?.blocks_sending)),
    warning: alerts.filter((alert) => !Boolean(alert?.blocks_sending) && !alertIsInfo(alert)),
    info: alerts.filter((alert) => !Boolean(alert?.blocks_sending) && alertIsInfo(alert)),
  };
  const blockingAlerts = alertGroups.blocking.length;
  const warningAlerts = alertGroups.warning.length;
  const infoAlerts = alertGroups.info.length;
  const progressTotals = summarizeAlertProgress(snapshot).reduce((acc, item) => {
    acc[item.key] = item;
    return acc;
  }, {});
  const controls = snapshot?.controls || {};
  const automation = snapshot?.automation || {};
  const targetWindowHours = Number(controls.send_target_window_hours || 18);
  const sendgridDailyTime = automation?.sendgrid_daily?.enabled
    ? automation.sendgrid_daily.local_time
    : null;
  const privateWindowHours = Number(snapshot?.activity_hours || 24);
  const sendgridPending = Number(summary?.sendgrid_pending || 0);
  const privatePending = privateProfile ? profilePendingCount(privateProfile) : Number(summary.astra_pending || 0);
  const totalPending = Number(summary?.total_pending || (sendgridPending + privatePending) || 0);
  const privateStatus = privateProfile ? senderStatusBadge(privateProfile).label : "Stopped";
  const privateRunning = privateProfile && isProfileActive(privateProfile);
  const privateQueueSafety = privateProfile ? providerQueueSafetyForProfile(privateProfile, snapshot) : {};
  const privateVerifiedPartial = privateProfile && queueSafetyVerifiedSubset(privateQueueSafety);
  const sendgridProgress = progressTotals.sendgrid || { sent: 0, active: 0, cap: 0 };
  const privateProgress = progressTotals.private || { sent: 0, active: 0, cap: 0 };
  const privateSent = privateEmailSentBreakdown(snapshot);
  const firstVisibleAlert = alertGroups.blocking[0] || alertGroups.warning[0] || alertGroups.info[0] || null;
  const firstAlertTitle = firstVisibleAlert?.title || "No active alerts";
  const nextAction = (() => {
    if (privateRunning) {
      return {
        value: "Monitor Private JC",
        note: `${privatePending.toLocaleString()} remaining`,
        tone: "good",
        detail: "Private JC is running. Remaining recipients are verified against the confirmed preview.",
      };
    }
    if (blockingAlerts > 0) {
      return {
        value: "Review alerts",
        note: `${blockingAlerts} blocking alert${blockingAlerts === 1 ? "" : "s"}`,
        tone: "bad",
        detail: "Resolve blocking alerts before starting senders.",
      };
    }
    if (privatePending > 0 && privateVerifiedPartial && privateProfile && canStartProfile(privateProfile, snapshot)) {
      return {
        value: "Resume Private JC",
        note: `${privatePending.toLocaleString()} remaining`,
        tone: "good",
        detail: "Queue partially consumed — remaining recipients verified safe.",
      };
    }
    if (privatePending > 0 && privateProfile && canStartProfile(privateProfile, snapshot)) {
      return {
        value: "Start JC",
        note: sendgridPending > 0 ? "Private JC ready" : "SendGrid complete · Private JC ready",
        tone: "good",
        detail: "Use the Private JC sender row below.",
      };
    }
    if (sendgridPending > 0 && sendgridRunning === 0) {
      return {
        value: "Start SendGrid",
        note: `${sendgridProfiles.length || 5} profiles available`,
        tone: "warn",
        detail: "Use the SendGrid sender rows below.",
      };
    }
    if (totalPending > 0) {
      return {
        value: "Monitor",
        note: `${totalPending.toLocaleString()} pending`,
        tone: "neutral",
        detail: "Sender rows below show the active control state.",
      };
    }
    return {
      value: "Run complete",
      note: "No pending queues",
      tone: "good",
      detail: "No sender action is needed.",
    };
  })();
  const alertDetailsHtml = `
    <div class="summary-alert-counts" aria-label="Alert summary">
      <span>Blocking: ${blockingAlerts.toLocaleString()}</span>
      <span>Warning: ${warningAlerts.toLocaleString()}</span>
      <span>Info: ${infoAlerts.toLocaleString()}</span>
    </div>
    <details class="summary-inline-details">
      <summary>${escapeHtml(firstAlertTitle)}${alerts.length > 1 ? " · View all" : ""}</summary>
      <div class="summary-inline-list">
        ${(alerts.length ? alerts : [{ title: "No active alerts", message: "All thresholds clear." }]).slice(0, 5).map((alert) => `
          <div class="summary-inline-row">
            <strong>${escapeHtml(alert?.title || "Alert")}</strong>
            <span>${escapeHtml(alert?.message || "No details provided.")}</span>
          </div>
        `).join("")}
      </div>
    </details>
  `;
  const cards = [
    {
      key: "private_jc",
      label: "Private JC",
      value: `${privatePending.toLocaleString()} pending`,
      note: `${privateStatus} · ${Number(privateProgress.sent || 0).toLocaleString()} sent`,
      tone: privatePending > 0 ? "warn" : "neutral",
      detailsHtml: `
        <div class="summary-private-breakdown">
          <strong>Private Email total: ${privateSent.total.toLocaleString()}</strong>
          <span>JC cold: ${privateSent.cold.toLocaleString()}</span>
          <span>Warm JC: ${privateSent.warm.toLocaleString()}</span>
        </div>
        <div class="summary-small-note">Cap ${privateProgress.cap ? Number(privateProgress.cap).toLocaleString() : "∞"} · ${privateWindowHours.toLocaleString()}h window</div>
      `,
    },
    {
      key: "total_pending",
      label: "Total Pending",
      value: totalPending.toLocaleString(),
      note: `Astra ${privatePending.toLocaleString()} · SendGrid ${sendgridPending.toLocaleString()}`,
      tone: totalPending > 0 ? "warn" : "neutral",
    },
    {
      key: "sendgrid",
      label: "SendGrid",
      value: sendgridPending > 0 ? `${sendgridPending.toLocaleString()} pending` : "Complete",
      note: `${sendgridPending.toLocaleString()} pending · ${Number(sendgridProgress.sent || 0).toLocaleString()} sent`,
      tone: sendgridRunning > 0 ? "good" : sendgridPending > 0 ? "warn" : "neutral",
      detailsHtml: `
        <div class="summary-small-note">Daily ${escapeHtml(sendgridDailyTime || "manual")} · ${targetWindowHours.toLocaleString()}h window</div>
        ${sendgridOutcomeHealthSummaryHtml(snapshot)}
      `,
    },
    {
      key: "alerts",
      label: "Alerts",
      value: `${warningAlerts.toLocaleString()} warning${warningAlerts === 1 ? "" : "s"}`,
      note: Number(summary.active_alerts || alerts.length || 0) > 0
        ? `${blockingAlerts} blocking · awaiting ${total_awaiting_outcome.toLocaleString()}`
        : "Clear",
      tone: blockingAlerts > 0 ? "bad" : Number(summary.active_alerts || alerts.length || 0) > 0 ? "warn" : "good",
      detailsHtml: `<div class="summary-small-note">${infoAlerts.toLocaleString()} info · ${alerts.length.toLocaleString()} total</div>`,
    },
    {
      key: "next_action",
      label: "Next Action",
      value: nextAction.value,
      note: nextAction.value === "Start JC" ? "Use JC sender row below" : nextAction.note,
      tone: nextAction.tone,
      detailsHtml: `<div class="summary-small-note">${escapeHtml(nextAction.detail)}</div>`,
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
  const opsRoot = els.opsView;
  const anchor = opsRoot?.querySelector(".ops-progress-strip")
    || opsRoot?.querySelector(".workspace-metric-details")
    || els.summaryGrid?.closest(".queue-health-section")
    || els.summaryGrid;
  if (!anchor?.parentNode) return null;

  const panels = Array.from(opsRoot?.querySelectorAll(".sender-status-panel") || []);
  senderStatusPanel = panels.shift() || null;
  panels.forEach((panel) => panel.remove());

  if (senderStatusPanel) {
    senderStatusPanel.id = "senders-table-panel";
    if (senderStatusPanel.previousElementSibling !== anchor) {
      anchor.insertAdjacentElement("afterend", senderStatusPanel);
    }
    return senderStatusPanel;
  }

  senderStatusPanel = elementFromHTML(`
    <section id="senders-table-panel" class="sender-status-panel panel-shell">
      <div class="ops-strip-head sender-status-head">
        <div>
          <p class="eyebrow">Senders</p>
          <p class="muted">Queues, activity, controls</p>
        </div>
      </div>
      <div class="sender-status-table-wrap">
        <table class="sender-status-table">
          <thead>
            <tr>
              <th>Sender</th>
              <th>State</th>
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

function syncProgressDetailsToggle() {
  if (!els.opsProgressDetailsToggle || !els.opsProgressDetails) return;
  const open = Boolean(els.opsProgressDetails.open);
  setNodeText(els.opsProgressDetailsToggle, open ? "Close details" : "View details");
  els.opsProgressDetailsToggle.setAttribute("aria-expanded", open ? "true" : "false");
}

function warmDraftPreviewCount(snapshot = lastSnapshot) {
  const report = lastLeadsStatus?.latest_warm_check
    || snapshot?.latest_warm_check
    || (lastImportantLeadCheck?.upload_type === "warm_research" ? lastImportantLeadCheck : {});
  const value = Number(report?.warm_email_preview_rows || 0);
  return Number.isFinite(value) ? Math.max(0, value) : 0;
}

function warmSenderDisplayState(profile, snapshot = lastSnapshot) {
  const lane = currentWarmPrivateJcStatus(lastLeadsStatus, snapshot);
  const label = String(lane.state || "No queue");
  const tone = label === "Blocked" ? "bad" : ["Running", "Ready", "Complete"].includes(label) ? "good" : label === "Partial" || label === "Not confirmed" ? "warn" : "neutral";
  return { label, tone };
}

function senderStatusBadge(profile) {
  const runtimeState = String(profile?.runtime_state || "").trim();
  const pendingCount = profilePendingCount(profile);
  const queueSafety = providerQueueSafetyForProfile(profile);
  if (profile?.name === "private_jc_warm") return warmSenderDisplayState(profile, lastSnapshot);
  if (["running", "starting", "sleeping"].includes(runtimeState)) return { label: "Running", tone: "good" };
  if (["cooldown", "paused"].includes(runtimeState)) return { label: runtimeState === "paused" ? "Paused" : "Cooldown", tone: "warn" };
  if (runtimeState === "stalled") return { label: "Stalled", tone: "warn" };
  if (pendingCount <= 0 && (profileTelemetryChannel(profile) === "sendgrid" || queueSafetyComplete(queueSafety))) {
    return { label: "Complete", tone: "good" };
  }
  if (profileTelemetryChannel(profile) === "sendgrid" && profile?.sendgrid_hourly_cap_waiting) {
    return { label: "Waiting · hourly cap", tone: "warn" };
  }
  if (queueSafetyBlockedForProfile(profile)) {
    return { label: "Blocked", tone: "bad" };
  }
  if (profilePreviewSyncRequired(profile) && !profileHasIndependentBlocker(profile)) {
    return { label: "Sync Required", tone: "warn" };
  }
  if (pendingCount > 0 && queueSafetyVerifiedSubset(queueSafety)) return { label: "Resume", tone: "good" };
  if (canStartProfile(profile, lastSnapshot)) return { label: "Ready", tone: "good" };
  if (pendingCount <= 0) return { label: "Complete", tone: "good" };
  return { label: "Stopped", tone: "bad" };
}

function renderSenderStatusConsole(snapshot, selectedProfile) {
  const panel = ensureSenderStatusPanel();
  if (!panel) return;
  const tbody = panel.querySelector("tbody");
  const profiles = Array.isArray(snapshot?.profiles)
    ? snapshot.profiles.filter((profile, index, allProfiles) => (
      allProfiles.findIndex((candidate) => candidate?.name === profile?.name) === index
    ))
    : [];
  if (!profiles.length) {
    setNodeHtml(tbody, `<tr><td colspan="7" class="sender-status-empty muted">No sender profiles available.</td></tr>`);
    return;
  }
  setNodeHtml(
    tbody,
    profiles.map((profile) => {
      const warmProfile = profile?.name === "private_jc_warm";
      const warmStatus = currentWarmPrivateJcStatus(lastLeadsStatus, snapshot);
      const status = senderStatusBadge(profile);
      const pendingAction = pendingProfileActions.get(profile.name) || "";
      const stopAvailable = warmProfile ? Boolean(warmStatus.running) : canStopProfile(profile);
      const startAvailable = canStartProfile(profile, snapshot);
      const pendingCount = warmProfile
        ? Number(warmStatus.queued_remaining_count ?? warmStatus.remaining ?? 0)
        : profilePendingCount(profile);
      const acceptedCount = warmProfile
        ? Number(warmStatus.sent_count ?? 0)
        : Number(profileRunSentDisplay(profile) || 0);
      const warmHasDraftPreview = warmDraftPreviewCount(snapshot) > 0;
      const warmCanOpenLeadOps = warmProfile
        && status.label !== "Complete"
        && (pendingCount > 0 || warmHasDraftPreview || ["Partial", "Blocked", "Ready", "Not confirmed"].includes(status.label));
      const noPendingQueue = !stopAvailable && pendingCount <= 0;
      const action = stopAvailable
        ? "stop"
        : warmProfile
          ? warmCanOpenLeadOps ? "open_lead_ops" : "no_queue"
          : "start";
      const actionLabelText = pendingAction
        ? actionLabel(pendingAction)
        : action === "stop" ? "Stop" : action === "open_lead_ops" ? status.label === "Partial" ? "Resume in Lead Ops" : "Open Lead Ops" : status.label === "Complete" ? "Complete" : action === "no_queue" || noPendingQueue ? "No queue" : "Start";
      const actionDisabled = Boolean(pendingAction)
        || action === "no_queue"
        || (!warmProfile && noPendingQueue)
        || (!warmProfile && !stopAvailable && !startAvailable);
      const warmMax = Number(profile?.max_total ?? profile?.configured_max_total ?? profile?.max_messages_per_run ?? 0);
      const warmMetadata = warmProfile
        ? `<span class="sender-status-profile-meta">Private JC sender · same limits as JC · ${warmMax > 0 ? `max ${warmMax.toLocaleString()}` : "no run cap"}</span>`
        : "";
      const lastActivity = warmProfile && warmStatus.last_sent_timestamp
        ? formatWarmActivity(warmStatus.last_sent_timestamp, warmStatus.last_sent_email)
        : warmProfile
        ? "No activity yet"
        : profile.last_timestamp
        ? `${profile.last_timestamp}${profile.last_email ? ` · ${truncateMiddle(profile.last_email, 34)}` : ""}`
        : profileLastAgeText(profile);
      return `
        <tr class="${[
          selectedProfile?.name === profile.name ? "is-selected" : "",
          (warmProfile ? Boolean(warmStatus.running) : isProfileActive(profile)) ? "is-live" : "",
          pendingCount <= 0 ? "is-complete" : "",
          warmProfile ? "is-warm-jc" : "",
        ].filter(Boolean).join(" ")}" data-profile="${escapeHtml(profile.name || "")}">
          <td>
            <div class="sender-status-identity">
              <button class="sender-status-name-btn" type="button" data-profile="${escapeHtml(profile.name || "")}">
                ${escapeHtml(formatProfileName(profile.name))}
              </button>
              ${warmMetadata}
            </div>
          </td>
          <td><span class="sender-status-pill sender-status-pill-${escapeHtml(status.tone)}">${escapeHtml(status.label)}</span></td>
          <td>${pendingCount.toLocaleString()}</td>
          <td>${acceptedCount.toLocaleString()}</td>
          <td>${Number(profile.awaiting_outcome || 0).toLocaleString()}</td>
          <td class="sender-status-activity" title="${escapeHtml(profile.last_email || profile.last_timestamp || "")}">${escapeHtml(lastActivity)}</td>
          <td>
            <button
              class="btn ${action === "stop" ? "btn-danger" : "btn-secondary"} btn-sm sender-status-action-btn"
              type="button"
              data-profile="${escapeHtml(profile.name || "")}"
              data-action="${escapeHtml(action)}"
              title="${warmProfile && action === "open_lead_ops" ? "Warm confirmation and start controls are available in Lead Ops only." : action === "no_queue" || noPendingQueue ? "No pending leads." : ""}"
              ${actionDisabled ? "disabled" : ""}
            >${escapeHtml(actionLabelText)}</button>
          </td>
        </tr>
      `;
    }).join(""),
  );
}

async function hydrateWarmSenderLeadStatus() {
  if (warmSenderLeadStatusRequested) return;
  warmSenderLeadStatusRequested = true;
  try {
    const data = await fetchJson("/api/leads/status");
    lastLeadsStatus = data.status || lastLeadsStatus;
    if (lastSnapshot) renderSenderStatusConsole(lastSnapshot, resolveSelectedProfile(lastSnapshot));
  } catch (_err) {
    // Sender rows remain usable from the live snapshot if lead status is unavailable.
  }
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

function privateEmailSentBreakdown(snapshot = lastSnapshot) {
  const profiles = Array.isArray(snapshot?.profiles) ? snapshot.profiles : [];
  const coldProfile = profiles.find((profile) => profile?.name === "private_jc") || {};
  const warmStatus = currentWarmPrivateJcStatus(lastLeadsStatus, snapshot);
  const warmProfile = profiles.find((profile) => profile?.name === "private_jc_warm") || {};
  const cold = Number(profileRunSentDisplay(coldProfile) || 0);
  const warm = Number(warmStatus.sent_count ?? profileRunSentDisplay(warmProfile) ?? 0);
  return { cold, warm, total: cold + warm };
}

function renderProgressSummaryStrip(snapshot) {
  if (!els.opsProgressSummary) return;
  const profiles = Array.isArray(snapshot?.profiles) ? snapshot.profiles : [];
  const items = summarizeAlertProgress(snapshot).reduce((acc, item) => {
    acc[item.key] = item;
    return acc;
  }, {});
  const summary = snapshot?.summary || {};
  const alerts = Array.isArray(snapshot?.alerts) ? snapshot.alerts : [];
  const blockingAlerts = alerts.filter((alert) => Boolean(alert?.blocks_sending)).length;
  const warningAlerts = alerts.filter((alert) => {
    const severity = String(alert?.severity || "").trim().toLowerCase();
    const label = String(alert?.blocking_label || "").trim().toLowerCase();
    return !Boolean(alert?.blocks_sending) && !["ok", "info"].includes(severity) && label !== "info";
  }).length;
  const sendgridPending = Number(summary?.sendgrid_pending || 0);
  const sendgridStatus = Number(items.sendgrid?.active || 0) > 0
    ? `${Number(items.sendgrid?.active || 0).toLocaleString()} active`
    : sendgridPending > 0
      ? `${sendgridPending.toLocaleString()} pending`
      : "complete";
  const privateProfile = profiles.find((profile) => profile.name === "private_jc")
    || profiles.find((profile) => profileTelemetryChannel(profile) === "private");
  const privateStatus = privateProfile ? senderStatusBadge(privateProfile).label.toLowerCase() : "stopped";
  const privateSent = privateEmailSentBreakdown(snapshot);
  const progressItems = [
    {
      label: "SendGrid",
      value: `${sendgridStatus} · ${Number(items.sendgrid?.sent || 0).toLocaleString()} sent`,
    },
    {
      label: "Private Email",
      value: `Private Email total: ${privateSent.total.toLocaleString()} · JC cold: ${privateSent.cold.toLocaleString()} · Warm JC: ${privateSent.warm.toLocaleString()} · ${privateStatus}`,
    },
    {
      label: "Alerts",
      value: `${blockingAlerts.toLocaleString()} blocking · ${warningAlerts.toLocaleString()} warning`,
    },
    {
      label: "Awaiting outcomes",
      value: Number(summary?.total_awaiting_outcome || 0).toLocaleString(),
    },
  ];
  setNodeHtml(
    els.opsProgressSummary,
    progressItems.map((item) => `
      <span class="ops-progress-summary-item">
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.value)}</span>
      </span>
    `).join(""),
  );
  syncProgressDetailsToggle();
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
      <span class="alerts-progress-meta alerts-progress-plan">Target ${Number(sendTarget || 0).toLocaleString()} · ~${Number(perProfileTarget || 0).toLocaleString()}/profile</span>
      <span class="alerts-progress-meta alerts-progress-plan">Daily ${sendgridDailyTime ? escapeHtml(sendgridDailyTime) : "manual"} · ${Number(targetWindowHours || 18)}h window</span>
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
  renderProgressSummaryStrip(snapshot);
  const activeAlerts = Array.isArray(snapshot.alerts) ? snapshot.alerts : [];
  const groups = [
    {
      key: "blocking",
      title: "Blocking",
      badge: "Blocked",
      tone: "bad",
      alerts: activeAlerts.filter((alert) => Boolean(alert?.blocks_sending)),
      empty: "No blocking alerts.",
    },
    {
      key: "warning",
      title: "Warning",
      badge: "Warning",
      tone: "warn",
      alerts: activeAlerts.filter((alert) => !Boolean(alert?.blocks_sending) && String(alert?.severity || "warn") !== "ok"),
      empty: "No warnings.",
    },
    {
      key: "info",
      title: "Info",
      badge: "Info",
      tone: "neutral",
      alerts: activeAlerts.filter((alert) => !Boolean(alert?.blocks_sending) && String(alert?.severity || "warn") === "ok"),
      empty: "No informational alerts.",
    },
  ];
  setNodeHtml(
    els.alertsGrid,
    groups.map((group) => {
      const visible = group.alerts.slice(0, group.key === "blocking" ? 2 : 1);
      const overflow = Math.max(0, group.alerts.length - visible.length);
      const overflowAlerts = group.alerts.slice(visible.length);
      const renderAlertRow = (alert) => {
        const alertProfile = String(alert?.profile || alert?.profile_name || "").trim();
        const alertMessage = String(alert?.message || "").trim();
        const messageWithProfile = alertProfile
          ? `${alertMessage}${alertMessage ? " " : ""}Profile: ${formatProfileName(alertProfile)}.`
          : alertMessage;
        return `
          <article class="alert-card alert-card-compact alert-row alert-${escapeHtml(alert?.severity || group.tone)}">
            <div class="alert-row-main">
              <h3>${escapeHtml(alert?.title || "Alert")}</h3>
              <p class="alert-message">${escapeHtml(messageWithProfile || "No details provided.")}</p>
            </div>
          </article>
        `;
      };
      return `
        <section class="alert-group alert-group-${escapeHtml(group.key)}">
          <div class="alert-group-head">
            <strong>${escapeHtml(group.title)}</strong>
            <span class="alert-pill alert-pill-${escapeHtml(group.tone)}">${escapeHtml(group.badge)} · ${group.alerts.length}</span>
          </div>
          <div class="alert-group-body">
            ${visible.length
              ? visible.map(renderAlertRow).join("")
              : `<p class="muted alert-empty">${escapeHtml(group.empty)}</p>`}
            ${overflow > 0 ? `
              <details class="alert-overflow-details">
                <summary>View all (${overflow} more)</summary>
                <div class="alert-overflow-list">${overflowAlerts.map(renderAlertRow).join("")}</div>
              </details>
            ` : ""}
          </div>
        </section>
      `;
    }).join(""),
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
  if (runtimeState === "cooldown") {
    return { label: "Cooldown", tone: "warn" };
  }
  if (["starting", "running", "sleeping"].includes(runtimeState)) {
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

function profileDisplayStatus(profile) {
  const runtimeState = String(profile?.runtime_state || "").trim();
  if (runtimeState === "cooldown") return { label: "Cooldown", tone: "warn" };
  if (["starting", "running", "sleeping"].includes(runtimeState)) return { label: "Running", tone: "good" };
  if (profilePreviewSyncRequired(profile) && !profileHasIndependentBlocker(profile)) {
    return { label: "Sync Required", tone: "warn" };
  }
  const readiness = String(profile?.readiness_label || "").trim();
  if (readiness && readiness !== "Ready") return { label: readiness, tone: profile?.readiness_tone || "bad" };
  return { label: profile?.runtime_label || "Stopped", tone: "bad" };
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

function profilePreviewSyncRequired(profile) {
  return Boolean(profile?.message_readiness?.preview_sync_required);
}

function profileHasIndependentBlocker(profile, snapshot = lastSnapshot) {
  const readinessLabel = String(profile?.readiness_label || "").trim().toLowerCase();
  const readinessTone = String(profile?.readiness_tone || "").trim().toLowerCase();
  const messageStatus = String(profile?.message_readiness?.status || "").trim().toUpperCase();
  return queueSafetyBlockedForProfile(profile, snapshot)
    || readinessTone === "bad"
    || ["blocked", "not ready"].includes(readinessLabel)
    || messageStatus === "FAIL";
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
  const syncRequired = Boolean(readiness.preview_sync_required) && !profileHasIndependentBlocker(profile);
  const displayStatus = syncRequired ? "SYNC REQUIRED" : status;
  const tone = messageReadinessTone(syncRequired ? "STALE" : status);
  const emailSetsMatch = Boolean(
    readiness.generated_email_set_matches_queue
    && readiness.validated_email_set_matches_queue
  );
  const fingerprintsMatch = Boolean(
    readiness.generated_fingerprint_matches_queue
    && readiness.validated_fingerprint_matches_queue
  );
  const items = [
    ["Queue rows", Number(readiness.recipient_row_count || 0).toLocaleString()],
    ["Generated preview", Number(readiness.preview_row_count || 0).toLocaleString()],
    ["Validated preview", Number(readiness.validated_preview_row_count || 0).toLocaleString()],
    ["Failed preview rows", Number(readiness.failed_preview_row_count || 0).toLocaleString()],
    ["Email sets", emailSetsMatch ? "Match" : "Mismatch"],
    ["Fingerprints", fingerprintsMatch ? "Match" : "Mismatch"],
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
        <strong>${escapeHtml(displayStatus)}</strong>
      </div>
      <div class="message-readiness-actions">
        <button
          class="btn btn-secondary btn-sm preview-validate-profile-btn"
          type="button"
          data-profile="${escapeHtml(profileName)}"
          ${actionDisabled ? "disabled" : ""}
          title="${escapeHtml(actionTitle)}"
        >${escapeHtml(previewRunning ? "Synchronizing..." : "Regenerate & Validate Preview")}</button>
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
      ${syncRequired ? `<p class="message-readiness-reason">Preview artifacts are stale relative to the current queue.</p>` : ""}
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
  if (isProfileActive(profile)) {
    if (failed > 0) {
      return { tone: "bad", label: "Failures", message: `${failed} delivery failure${failed === 1 ? "" : "s"} in the selected window.` };
    }
    if (awaiting > 0) {
      return { tone: "warn", label: "Awaiting", message: `${awaiting} accepted recipient${awaiting === 1 ? "" : "s"} still awaiting final outcome.` };
    }
    return { tone: "neutral", label: "Active", message: profile?.runtime_note || "Sender is active." };
  }
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
  return String(queueSafety.message || "Recipient queue needs review before starting.").trim();
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
  return String(queueSafety.message || "Recipient queue needs review before starting this sender.").trim();
}

function canStartProfile(profile, snapshot = lastSnapshot) {
  if (profile?.name === "private_jc_warm") {
    const lane = snapshot?.warm_private_jc_lane || {};
    return profilePendingCount(profile) > 0
      && Boolean(lane.confirmed)
      && Boolean(lane.ready)
      && !isProfileActive(profile)
      && !Boolean(profile?.restart_blocked);
  }
  return profilePendingCount(profile) > 0
    && !queueSafetyBlockedForProfile(profile, snapshot)
    && !profilePreviewSyncRequired(profile)
    && !isProfileActive(profile)
    && !Boolean(profile?.restart_blocked);
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
  const summaryPending = Number(snapshot?.summary?.total_pending);
  const totalPending = Number.isFinite(summaryPending)
    ? Math.max(0, summaryPending)
    : profiles.reduce((sum, profile) => sum + Math.max(0, profilePendingCount(profile)), 0);
  const runComplete = totalPending <= 0;
  const blockedByQueueSafety = queueSafetyBlocked(snapshot);
  const splitQueueSafety = sendgridReadyPrivateBlocked(snapshot);
  const queueSafetyMessage = splitQueueSafety
    ? "SendGrid ready; Private JC blocked."
    : queueSafetyBlockMessage(snapshot);
  if (els.sendCapInput && document.activeElement !== els.sendCapInput && sendTarget > 0) {
    els.sendCapInput.value = String(sendTarget);
  }
  if (els.stopBtn) {
    els.stopBtn.classList.toggle("btn-danger-active", hasActiveSender);
  }
  if (els.sendCapNote) {
    const lines = [];
    if (runComplete) {
      lines.push("Run complete. No pending queues.");
    } else if (hasActiveSender) {
      lines.push("Some senders are already running. Use per-sender controls or Stop All first.");
    }
    const hasBlockingAlert = Array.isArray(snapshot?.alerts)
      && snapshot.alerts.some((alert) => Boolean(alert?.blocks_sending));
    if (blockedByQueueSafety && hasBlockingAlert) {
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
      lines.push("Choose a sender, then use its individual Start button.");
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
  const displayStatus = profileDisplayStatus(profile);
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
        <span class="detail-compact-value">${escapeHtml(displayStatus.label || "Stopped")}</span>
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
  const pendingCount = Number(profile.pending_count || 0);
  const noPendingQueue = !canStopProfile(profile) && pendingCount <= 0;
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
    isProfileActive(profile) || profile?.restart_blocked || (profile.runtime_state || "") === "finished"
      ? buildProfileActionNote(profile, snapshot)
      : profileQueueBlocked
        ? `NOT READY / BLOCKED: ${queueSafetyBlockMessageForProfile(profile, snapshot)}`
        : "",
  );

  refs.startButton.dataset.profile = profile.name || "";
  refs.startButton.disabled = startDisabled;
  refs.startButton.title = noPendingQueue ? "Start unavailable — no pending leads." : "";
  setNodeText(refs.startButton, pendingAction === "start" ? "Starting..." : noPendingQueue ? "No queue" : "Start");

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
  const snapshotAutoStart = snapshot?.automation?.auto_start_allowed;
  renderEnvironmentStatus(
    typeof snapshotAutoStart === "boolean" ? { autoStartAllowed: snapshotAutoStart } : {},
  );
  displayTimeZone = snapshot.display_timezone || displayTimeZone;
  const selectedProfile = resolveSelectedProfile(snapshot);
  renderControls(snapshot);
  renderHealth(snapshot);
  renderAlerts(snapshot);
  renderSummary(snapshot);
  renderSenderStatusConsole(snapshot, selectedProfile);
  if ((snapshot?.profiles || []).some((profile) => profile?.name === "private_jc_warm")) {
    void hydrateWarmSenderLeadStatus();
  }
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
  try {
    const response = await fetch(
      `/api/snapshot?hours=${encodeURIComponent(hours)}&tail_lines=${encodeURIComponent(tail)}`,
      { credentials: "same-origin" },
    );
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || data.detail || `Request failed (${response.status}).`);
    }
    snapshotFallbackHealthy = response.ok;
    renderSnapshot(data);
    if (!socketLive) setConnectionState(false);
  } catch (err) {
    snapshotFallbackHealthy = false;
    setConnectionState(false);
    throw err;
  }
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
  if (profilePreviewValidationState.get(profile)?.kind === "loading") return;
  profilePreviewValidationState.set(profile, { kind: "loading", message: "Regenerating and validating the current preview..." });
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
      message: `${passed ? "Preview synchronized and validated" : "Preview synchronization failed"} (${Number(result.preview_row_count || 0).toLocaleString()} row(s)).${reasonText}`,
    });
    if (data.snapshot) {
      renderSnapshot(data.snapshot);
    } else {
      await fetchSnapshot();
    }
    showMessage(data.message || (passed ? "Preview synchronized and validated." : "Preview synchronization failed."), passed ? "success" : "error");
  } catch (err) {
    profilePreviewValidationState.set(profile, { kind: "error", message: `Preview synchronization failed: ${err}` });
    rerenderCurrentSelection();
    showMessage(`Preview synchronization failed: ${err}`, "error");
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
    if (profile === "private_jc_warm" && action === "open_lead_ops") {
      setLeadWorkflow("warm");
      return;
    }
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
  const manualSenderStart = path.startsWith("/api/start/");
  if (manualSenderStart && !window.confirm(
    "LIVE SENDER ACTION\n\n"
    + "This starts or resumes real sender workers and can consume pending queue rows. "
    + "Use only on the live Windows/WSL machine. Dashboard auto-start may be disabled, "
    + "but this manual Start/Resume action still works.\n\nContinue?",
  )) {
    showMessage("Manual Start/Resume cancelled. No sender workers were started.", "info");
    return;
  }
  try {
    if (profileName && action) {
      pendingProfileActions.set(profileName, action);
      setProfileActionFeedback(profileName, "info", action === "start" ? "Starting or resuming real sender worker..." : "Stopping profile...");
      rerenderCurrentSelection();
    } else if (manualSenderStart) {
      showMessage("Starting or resuming real sender workers on the live machine...", "info");
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

function renderStartReadyStatus(payload = {}, title = "Start Ready Senders") {
  if (!els.startReadyStatus) return;
  const ready = Array.isArray(payload.ready_profiles) ? payload.ready_profiles : [];
  const skipped = Array.isArray(payload.skipped_profiles) ? payload.skipped_profiles : [];
  const results = Array.isArray(payload.results) ? payload.results : [];
  const items = results.length ? results : [...ready, ...skipped];
  const message = String(payload.message || "").trim();
  const rows = items.map((item) => {
    const status = String(item?.status || "SKIPPED").toUpperCase();
    const label = escapeHtml(item?.label || item?.profile || "Sender");
    const reason = escapeHtml(item?.reason || "");
    const pending = Number(item?.pending_count || 0);
    return `<li class="start-ready-item status-${status.toLowerCase()}">`
      + `<span class="start-ready-item-state">${escapeHtml(status)}</span>`
      + `<strong>${label}</strong>`
      + `<span>${pending.toLocaleString()} pending${reason ? ` · ${reason}` : ""}</span>`
      + "</li>";
  }).join("");
  els.startReadyStatus.innerHTML = `
    <div class="start-ready-head">
      <strong>${escapeHtml(title)}</strong>
      ${message ? `<span>${escapeHtml(message)}</span>` : ""}
    </div>
    ${rows ? `<ul class="start-ready-list">${rows}</ul>` : ""}
  `;
  els.startReadyStatus.classList.remove("hidden");
}

function resetStartReadyButton() {
  startReadyBusy = false;
  startReadyJobId = "";
  if (startReadyPollTimer) clearTimeout(startReadyPollTimer);
  startReadyPollTimer = null;
  if (els.startReadyBtn) {
    els.startReadyBtn.disabled = false;
    els.startReadyBtn.textContent = "Start Ready Senders";
  }
}

async function pollStartReadyJob(jobId) {
  if (!startReadyBusy || jobId !== startReadyJobId) return;
  try {
    const response = await fetch(`/api/start-ready/status/${encodeURIComponent(jobId)}`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false || !data.job) {
      throw new Error(data.message || `Status request failed (${response.status}).`);
    }
    const job = data.job;
    renderStartReadyStatus(job, "Start Ready Senders progress");
    if (["COMPLETE", "FAILED"].includes(String(job.status || "").toUpperCase())) {
      const failed = String(job.status || "").toUpperCase() === "FAILED";
      resetStartReadyButton();
      showMessage(job.message || "Start Ready Senders finished.", failed ? "error" : "success");
      await fetchSnapshot();
      return;
    }
    startReadyPollTimer = setTimeout(() => void pollStartReadyJob(jobId), 750);
  } catch (err) {
    resetStartReadyButton();
    showMessage(`Start Ready Senders status failed: ${err}`, "error");
  }
}

async function startReadySenders() {
  if (startReadyBusy) return;
  startReadyBusy = true;
  if (els.startReadyBtn) {
    els.startReadyBtn.disabled = true;
    els.startReadyBtn.textContent = "Checking readiness...";
  }
  try {
    const planResponse = await fetch("/api/start-ready");
    const plan = await planResponse.json().catch(() => ({}));
    if (!planResponse.ok || plan.ok === false) {
      throw new Error(plan.message || `Readiness request failed (${planResponse.status}).`);
    }
    renderStartReadyStatus(plan, "Start Ready Senders review");
    const ready = Array.isArray(plan.ready_profiles) ? plan.ready_profiles : [];
    if (!ready.length) {
      resetStartReadyButton();
      showMessage("No operational production senders are currently ready.", "info");
      return;
    }
    const readyLines = ready.map((item) => `✓ ${item.label || item.profile} (${Number(item.pending_count || 0).toLocaleString()} pending)`);
    const skipped = Array.isArray(plan.skipped_profiles) ? plan.skipped_profiles : [];
    const skippedLines = skipped.map((item) => `- ${item.label || item.profile}: ${item.reason || "Not ready"}`);
    const confirmed = window.confirm(
      `LIVE SENDER ACTION\n\nStart ${ready.length} ready operational sender(s), sequentially?\n\n`
      + readyLines.join("\n")
      + (skippedLines.length ? `\n\nSkipped:\n${skippedLines.join("\n")}` : "")
      + "\n\nThe server will recompute every sender's safety immediately before Start. "
      + "No retries will be attempted, and the sequence cannot be cancelled after confirmation.",
    );
    if (!confirmed) {
      resetStartReadyButton();
      showMessage("Start Ready Senders cancelled. No Start request was submitted.", "info");
      return;
    }
    if (els.startReadyBtn) els.startReadyBtn.textContent = "Starting ready senders...";
    const response = await fetch("/api/start-ready", { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false || !data.job?.job_id) {
      throw new Error(data.message || `Start request failed (${response.status}).`);
    }
    startReadyJobId = String(data.job.job_id);
    renderStartReadyStatus(data.job, "Start Ready Senders progress");
    await pollStartReadyJob(startReadyJobId);
  } catch (err) {
    resetStartReadyButton();
    showMessage(`Start Ready Senders failed: ${err}`, "error");
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
  if (!authState.authenticated && authState.authEnabled) {
    stopSocket();
    return;
  }
  if (!isOpsTabVisible()) {
    stopSocket();
    return;
  }
  if (snapshotPollTimer && !forceReconnect) {
    return;
  }
  if (snapshotPollTimer) {
    clearTimeout(snapshotPollTimer);
    snapshotPollTimer = null;
  }

  const generation = ++snapshotPollGeneration;
  const poll = async () => {
    if (
      generation !== snapshotPollGeneration
      || (!authState.authenticated && authState.authEnabled)
      || !isOpsTabVisible()
    ) {
      setConnectionState(false);
      return;
    }

    try {
      await fetchSnapshot();
    } catch (err) {
      // The connection indicator is updated by fetchSnapshot.
    }

    if (
      generation !== snapshotPollGeneration
      || (!authState.authenticated && authState.authEnabled)
      || !isOpsTabVisible()
    ) {
      setConnectionState(false);
      return;
    }

    snapshotPollTimer = setTimeout(poll, 10000);
  };

  // Load sender data immediately, then continue polling every 10 seconds.
  void poll();
}

function stopSocket() {
  snapshotPollGeneration += 1;
  if (snapshotPollTimer) {
    clearTimeout(snapshotPollTimer);
    snapshotPollTimer = null;
  }
  setConnectionState(false);
}

async function bootstrapAuthenticatedDashboard() {
  document.querySelectorAll(".profile-detail-panel[open], .campaign-history-panel[open]").forEach((node) => {
    node.removeAttribute("open");
  });
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
    if (auth.authenticated || auth.auth_enabled === false) {
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
      authDisabled: authState.authDisabled,
      authenticated: false,
      username: "",
      message: String(err),
    });
  }
}

if (els.refreshBtn) els.refreshBtn.addEventListener("click", () => fetchSnapshot());
if (els.startReadyBtn) els.startReadyBtn.addEventListener("click", () => startReadySenders());
if (els.sendCapSaveBtn) els.sendCapSaveBtn.addEventListener("click", () => saveSendCap());
if (els.wallboardBtn) els.wallboardBtn.addEventListener("click", () => toggleWallboardMode());
if (els.stopBtn) els.stopBtn.addEventListener("click", () => postAction("/api/stop"));
if (els.archiveBtn) els.archiveBtn.addEventListener("click", () => postAction("/api/archive-reset-logs"));
if (els.opsProgressDetailsToggle && els.opsProgressDetails) {
  els.opsProgressDetailsToggle.addEventListener("click", () => {
    els.opsProgressDetails.open = !els.opsProgressDetails.open;
    syncProgressDetailsToggle();
  });
}
if (els.opsProgressDetails) {
  els.opsProgressDetails.addEventListener("toggle", () => syncProgressDetailsToggle());
}
if (els.opsTabBtn) els.opsTabBtn.addEventListener("click", () => setDashboardTab("ops"));
if (els.leadsTabBtn) els.leadsTabBtn.addEventListener("click", () => setDashboardTab("leads"));
document.querySelectorAll("[data-leads-workflow]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    setLeadWorkflow(link.getAttribute("data-leads-workflow") || "cold");
  });
});
if (els.leadsCurrentRunPanel) {
  els.leadsCurrentRunPanel.addEventListener("click", (event) => {
    const button = event.target.closest("[data-leads-next-action]");
    if (!button || button.disabled) return;
    const action = String(button.dataset.leadsNextAction || "");
    if (action === "upload_check") void runImportantLeadUploadCheck();
    if (action === "generate_warm_preview") void generateWarmDraftPreview();
    if (action === "confirm_warm_private_jc") void confirmWarmPrivateJc();
    if (action === "start_warm_private_jc") void startWarmPrivateJc();
    if (action === "stop_warm_private_jc") void postAction("/api/stop/private_jc_warm", { profileName: "private_jc_warm", action: "stop" });
    if (action === "fast_triage") void runImportantLeadVerify(VERIFY_MODE_FAST_TRIAGE);
    if (action === "preview_dispatch") void previewImportantLeadDispatch();
    if (action === "confirm_dispatch") void confirmImportantLeadDispatch();
    if (action === "create_safer_recontact") void createSaferRecontactPool();
    if (action === "use_safer_recontact") useSaferRecontactPoolAsSelectedSource();
    if (action === "select_fresh_cold") {
      if (els.leadsImportantDispatchCampaignType) els.leadsImportantDispatchCampaignType.value = "cold";
      if (els.leadsImportantDispatchSourceMode) els.leadsImportantDispatchSourceMode.value = "triaged_keep";
      if (els.leadsRecontactRecencyOverride) els.leadsRecontactRecencyOverride.checked = false;
      syncImportantDispatchCampaignSource();
      hydrateImportantDispatchPreviewFromStatus(lastLeadsStatus);
      renderImportantDispatch(lastImportantDispatch);
    }
  });
}
if (els.leadsRecommendedNextAction) {
  els.leadsRecommendedNextAction.addEventListener("click", (event) => {
    const button = event.target.closest("[data-leads-next-action]");
    if (!button || button.disabled) return;
    const action = String(button.dataset.leadsNextAction || "");
    if (action === "upload_check") void runImportantLeadUploadCheck();
    if (action === "preview_dispatch") void previewImportantLeadDispatch();
    if (action === "confirm_dispatch") void confirmImportantLeadDispatch();
    if (action === "create_safer_recontact") void createSaferRecontactPool();
    if (action === "use_safer_recontact") useSaferRecontactPoolAsSelectedSource();
    if (action === "select_fresh_cold") {
      if (els.leadsImportantDispatchCampaignType) els.leadsImportantDispatchCampaignType.value = "cold";
      if (els.leadsImportantDispatchSourceMode) els.leadsImportantDispatchSourceMode.value = "triaged_keep";
      if (els.leadsRecontactRecencyOverride) els.leadsRecontactRecencyOverride.checked = false;
      syncImportantDispatchCampaignSource();
      hydrateImportantDispatchPreviewFromStatus(lastLeadsStatus);
      renderImportantDispatch(lastImportantDispatch);
    }
  });
}
if (els.leadsImportantUploadCheckBtn) els.leadsImportantUploadCheckBtn.addEventListener("click", () => runImportantLeadUploadCheck());
if (els.leadsImportantCheckBtn) els.leadsImportantCheckBtn.addEventListener("click", () => runImportantLeadCheck());
if (els.leadsImportantIntakeMode) els.leadsImportantIntakeMode.addEventListener("change", () => renderLeadsOperatorStatusStrip(lastLeadsStatus || {}));
if (els.leadsImportantVerifyBtn) els.leadsImportantVerifyBtn.addEventListener("click", () => runImportantLeadVerify(VERIFY_MODE_FAST_TRIAGE));
if (els.leadsImportantVerifyStrictBtn) els.leadsImportantVerifyStrictBtn.addEventListener("click", () => runImportantLeadVerify(VERIFY_MODE_STRICT_PUBLIC_PROOF));
if (els.leadsImportantVerifyStopBtn) els.leadsImportantVerifyStopBtn.addEventListener("click", () => stopImportantLeadVerify());
if (els.leadsImportantDispatchPreviewBtn) els.leadsImportantDispatchPreviewBtn.addEventListener("click", () => previewImportantLeadDispatch());
if (els.leadsImportantDispatchPreviewTopBtn) els.leadsImportantDispatchPreviewTopBtn.addEventListener("click", () => previewImportantLeadDispatch());
if (els.leadsImportantDispatchConfirmBtn) els.leadsImportantDispatchConfirmBtn.addEventListener("click", () => confirmImportantLeadDispatch());
if (els.leadsDispatchModeCards) {
  els.leadsDispatchModeCards.addEventListener("click", (event) => {
    const card = event.target.closest("[data-dispatch-mode-card]");
    if (!card) return;
    const mode = String(card.dataset.dispatchModeCard || "");
    if (mode === "safer-recontact") {
      if (lastSaferRecontactSummary?.output_path) {
        useSaferRecontactPoolAsSelectedSource();
      } else {
        void createSaferRecontactPool();
      }
      return;
    }
    if (mode === "recontact") {
      if (els.leadsImportantDispatchCampaignType) els.leadsImportantDispatchCampaignType.value = "recontact_cold";
      if (els.leadsImportantDispatchSourceMode) els.leadsImportantDispatchSourceMode.value = "cleaned";
    } else {
      if (els.leadsImportantDispatchCampaignType) els.leadsImportantDispatchCampaignType.value = "cold";
      if (els.leadsImportantDispatchSourceMode) els.leadsImportantDispatchSourceMode.value = "triaged_keep";
      if (els.leadsRecontactRecencyOverride) els.leadsRecontactRecencyOverride.checked = false;
    }
    syncImportantDispatchCampaignSource();
    hydrateImportantDispatchPreviewFromStatus(lastLeadsStatus);
    renderImportantDispatch(lastImportantDispatch);
  });
}
if (els.leadsRecontactRecencyOverride) {
  els.leadsRecontactRecencyOverride.addEventListener("change", () => renderImportantDispatch(lastImportantDispatch));
}
if (els.leadsImportantInputText) {
  els.leadsImportantInputText.addEventListener("input", () => updateImportantLeadPasteGuardrails());
  els.leadsImportantInputText.addEventListener("change", () => updateImportantLeadPasteGuardrails());
}
if (els.leadsImportantUploadFile) {
  els.leadsImportantUploadFile.addEventListener("change", () => updateImportantLeadUploadNote());
}
if (els.leadsImportantDispatchSourceMode) {
  els.leadsImportantDispatchSourceMode.addEventListener("change", () => {
    hydrateImportantDispatchPreviewFromStatus(lastLeadsStatus);
    renderImportantDispatch(lastImportantDispatch);
  });
}
if (els.leadsImportantDispatchCap) {
  els.leadsImportantDispatchCap.addEventListener("change", () => {
    hydrateImportantDispatchPreviewFromStatus(lastLeadsStatus);
    renderImportantDispatch(lastImportantDispatch);
  });
}
if (els.leadsImportantDispatchCampaignType) {
  els.leadsImportantDispatchCampaignType.addEventListener("change", () => {
    syncImportantDispatchCampaignSource();
    hydrateImportantDispatchPreviewFromStatus(lastLeadsStatus);
    renderImportantDispatch(lastImportantDispatch);
  });
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

window.addEventListener("popstate", () => {
  wallboardMode = readWallboardModeFromLocation();
  activeDashboardTab = readDashboardTabFromLocation();
  activeLeadWorkflow = readLeadWorkflowFromLocation();
  applyWallboardMode();
  applyLeadWorkflowPage();
  syncTabBackgroundActivity();
  if (isLeadsTabVisible()) {
    void fetchLeadsStatus();
  }
});

wallboardMode = readWallboardModeFromLocation();
activeDashboardTab = readDashboardTabFromLocation();
activeLeadWorkflow = readLeadWorkflowFromLocation();
applyWallboardMode();
applyDashboardTab();
applyLeadWorkflowPage();
applyLeadsTriageCopy();
initQuarantineInboxDisclosure();
renderImportantLeadCheck(lastImportantLeadCheck);
renderImportantLeadVerify(lastImportantVerify);
renderImportantDispatch(lastImportantDispatch);
renderAuthUi();
// Local mode: do not show the auth overlay while auth status loads.
bootstrapDashboard();
