from __future__ import annotations

from pathlib import Path
import re
import unittest

import settings


APP_JS = Path(__file__).resolve().parents[1] / "web_dashboard" / "app.js"
INDEX_HTML = Path(__file__).resolve().parents[1] / "web_dashboard" / "index.html"
STYLES_CSS = Path(__file__).resolve().parents[1] / "web_dashboard" / "styles.css"
TAILWIND_CSS = Path(__file__).resolve().parents[1] / "web_dashboard" / "src" / "tailwind.css"
LIVE_DASHBOARD_PY = Path(__file__).resolve().parents[1] / "live_dashboard.py"
REACT_MAIN = Path(__file__).resolve().parents[1] / "web_dashboard" / "src" / "main.jsx"


class WebDashboardAppTests(unittest.TestCase):
    def test_lead_ops_routes_are_separate_and_upload_type_is_not_user_selectable(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        react_source = REACT_MAIN.read_text(encoding="utf-8")
        backend_source = LIVE_DASHBOARD_PY.read_text(encoding="utf-8")

        for expected in [
            'href="/?tab=leads&amp;workflow=cold"',
            'data-leads-workflow="cold"',
            "Cold Campaigns",
            'href="/?tab=leads&amp;workflow=warm"',
            'data-leads-workflow="warm"',
            "Warm Outreach",
        ]:
            self.assertIn(expected, react_source)
        self.assertIn('params.get("workflow") === "warm" ? "warm" : "cold"', source)
        self.assertIn('url.searchParams.set("workflow", activeLeadWorkflow)', source)
        self.assertIn('window.addEventListener("popstate"', source)
        self.assertIn('const historyMethod = historyMode === "push" ? "pushState" : "replaceState"', source)
        self.assertIn('<input id="leads-important-upload-type" type="hidden" value="cold" />', html)
        self.assertNotIn('<select id="leads-important-upload-type"', html)
        self.assertNotIn("Upload type</span>", html)
        self.assertIn('formData.append("upload_type", selectedLeadUploadType())', source)
        self.assertIn("lead_ops_progress_by_workflow", backend_source)
        self.assertIn("active_important_check_jobs", backend_source)
        self.assertIn("importantLeadCheckStorageKey", source)
        self.assertIn('${IMPORTANT_LEAD_CHECK_JOB_STORAGE_KEY}.${leadWorkflowFromUploadType(uploadType)}', source)

    def test_check_job_refresh_hydration_uses_local_storage_pointer_and_backend_source(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("emailautomation.activeImportantCheckJobId", source)
        self.assertIn("hydrateImportantLeadCheckJobOnLoad", source)
        self.assertIn("/api/leads/check-important/active", source)
        self.assertIn("resumeImportantLeadCheckJob", source)
        self.assertIn("bootstrapAuthenticatedDashboard", source)

    def test_verify_and_dispatch_refresh_hydration_use_local_storage_and_backend_source(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "emailautomation.activeImportantVerifyJobId",
            "emailautomation.activeImportantDispatchJobId",
            "hydrateImportantLeadVerifyJobOnLoad",
            "hydrateImportantLeadDispatchJobOnLoad",
            "/api/leads/verify-important/active",
            "/api/leads/dispatch-important/active",
            "resumeImportantLeadVerifyJob",
            "resumeImportantLeadDispatchJob",
            "pollImportantLeadVerifyJob",
            "pollImportantLeadDispatchJob",
        ]:
            self.assertIn(expected, source)

    def test_check_job_card_renders_live_progress_fields_after_reload(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for field in [
            "progress_percent",
            "eta_seconds",
            "processed_rows",
            "remaining_rows",
            "updated_at_utc",
            "current_sheet",
            "source_sheet",
            "progress-fill",
        ]:
            self.assertIn(field, source)

    def test_stale_lead_check_card_surfaces_reason_and_reupload_requirement(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "stale_reason",
            "last_successful_step",
            "reupload_required",
            "lead-ops-progress-error",
            "Last successful step",
            "Re-upload required",
        ]:
            self.assertIn(expected, source)

    def test_stale_warm_current_state_clears_metrics_and_locks_actions(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        state_start = source.index("function currentWarmWorkflowState")
        state_end = source.index("function currentWarmPrivateJcStatus", state_start)
        state_body = source[state_start:state_end]
        panel_start = source.index("function renderLeadsCurrentRunPanel")
        panel_end = source.index("function renderLeadsWorkflowTaskList", panel_start)
        panel_body = source[panel_start:panel_end]
        tracker_start = source.index("function renderLeadsWorkflowTaskList")
        tracker_end = source.index("function renderLeadsWorkflowStatusBanner", tracker_start)
        tracker_body = source[tracker_start:tracker_end]
        banner_start = tracker_end
        banner_end = source.index("function renderLeadsOperatorStatusStrip", banner_start)
        banner_body = source[banner_start:banner_end]

        for expected in [
            '"stale"',
            "progress?.reupload_required === true",
            "progress?.job_record_exists !== true",
            "progress?.output_exists !== true",
            "progress?.rejected_exists !== true",
            "progress?.latest_master_check_matches_current_run !== true",
            "report: valid ? report : {}",
            "historicalReport: previousWarmResearchReport(status)",
        ]:
            self.assertIn(expected, state_body)
        for expected in [
            "Current Warm Outreach · Re-upload required",
            "No Current Warm Queue",
            "!checked || draftCount <= 0 || warmConfirmed",
            "!checked || !warmConfirmed || !laneConfirmed || warmRemaining <= 0",
            "Historical sender activity below does not unlock this upload workflow.",
            "Previous Warm Outreach Run",
        ]:
            self.assertIn(expected, panel_body)
        for expected in [
            'workflow.reuploadRequired ? "Re-upload Required"',
            'status: checked ? "Available" : "Locked"',
            'status: draftReady ? "Complete" : checked ? "Available" : "Locked"',
            'status: currentConfirmed ? "Complete" : draftReady ? "Required" : "Locked"',
        ]:
            self.assertIn(expected, tracker_body)
        self.assertIn("Previous Warm Outreach Run", banner_body)
        self.assertIn("Historical results — not current workflow state", banner_body)
        self.assertIn("workflow.valid && Number(report.warm_email_preview_rows || 0) > 0", banner_body)

    def test_cold_workflow_tracker_ends_at_confirm_without_changing_queue_safety(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        tracker_start = source.index("function renderLeadsWorkflowTaskList")
        tracker_end = source.index("function renderLeadsWorkflowStatusBanner", tracker_start)
        tracker_body = source[tracker_start:tracker_end]

        for step in ['step: "Source"', 'step: "Check"', 'step: "Triage"', 'step: "Preview"', 'step: "Confirm"']:
            self.assertIn(step, tracker_body)
        self.assertNotIn('step: "Start"', tracker_body)
        self.assertNotIn("const liveQueueExists = liveRecipientQueueTotal(status) > 0", tracker_body)
        self.assertIn("function confirmedDispatchQueueState", source)

    def test_cold_and_warm_current_reports_remain_workflow_scoped(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn(
            'const report = uploadType === "warm_research" ? status?.current_warm_check : status?.latest_master_check',
            source,
        )
        self.assertIn('const progress = currentLeadOpsProgress(status, "warm_research")', source)
        self.assertIn("current_warm_check_job_id", source)
        self.assertIn("previous_warm_check", source)

    def test_warm_layout_moves_the_stepper_shell_only_when_anchors_share_a_parent(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn('closest(".react-stepper-shell")', source)
        self.assertIn("workflowAnchorsShareParent", source)
        self.assertIn("workflowTaskContainer?.parentElement === commandCenter", source)
        self.assertIn("leadsWorkflowStatusBanner?.parentElement === commandCenter", source)
        self.assertNotIn(
            "commandCenter.insertBefore(els.leadsWorkflowTaskList, els.leadsWorkflowStatusBanner)",
            source,
        )

    def test_terminal_check_job_clears_saved_job_pointer(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("clearSavedImportantLeadCheckJobId", source)
        self.assertIn("completed", source)
        self.assertIn("failed", source)
        self.assertIn("canceled", source)

    def test_verify_and_dispatch_cards_render_accessible_progress_and_clear_terminal_jobs(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "renderImportantLeadVerifyJob",
            "renderImportantLeadDispatchJob",
            "role=\"progressbar\"",
            "aria-valuenow",
            "aria-valuemin=\"0\"",
            "aria-valuemax=\"100\"",
            "aria-valuetext",
            "clearSavedJobId(IMPORTANT_LEAD_VERIFY_JOB_STORAGE_KEY",
            "clearSavedJobId(IMPORTANT_LEAD_DISPATCH_JOB_STORAGE_KEY",
            "assigned_rows",
            "skipped_rows",
            "dispatch_source_mode",
        ]:
            self.assertIn(expected, source)

    def test_dispatch_preview_and_confirm_flow_tracks_cap_and_preview_state(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "previewImportantLeadDispatch",
            "pollImportantLeadDispatchPreviewJob",
            "data.accepted && data.job?.job_id",
            "job.auto_dispatch_preview_status",
            "/api/leads/check-important/job/",
            "Preview Dispatch is running.",
            "confirmImportantLeadDispatch",
            "dispatchPreviewMatchesCurrentSelection",
            "currentDispatchPlanKey",
            "leadsImportantDispatchCap",
            "leadsImportantDispatchCampaignType",
            "selectedImportantDispatchCampaignType",
            "selectedImportantDispatchSourceMode",
            "syncImportantDispatchCampaignSource",
            "recontact_cold",
            "cleaned",
            "/api/leads/dispatch-important/preview",
            "/api/leads/dispatch-important/confirm",
            "Dispatch blocked: stop active senders first",
            "Confirm Dispatch blocked",
            "activeSenderSummary",
            "dispatchPreviewActionBlockReason",
            "dispatchPreviewBlockReason",
            "dispatchSummaryMatchesCurrentSource",
            "currentDispatchConfirmed",
            "leadsImportantDispatchPreviewTopBtn",
            "button.disabled = previewBusy",
            "Preview did not save. Please retry.",
            "Retry Preview Dispatch",
            "lastImportantDispatchPreviewFeedback",
            "lastImportantDispatchConfirmFeedback",
            "Retry Confirm Dispatch",
            "Confirm Dispatch failed. Retry Confirm Dispatch.",
            "Confirm Dispatch is running.",
            "sendgrid_profile_planned_counts",
            "sendgrid_profile_labels",
            "sendgrid_profile_order",
            "sendgrid_zero_reason",
            "SendGrid",
            "SendGrid profiles",
            "total_planned_unique_count",
            "Unique",
            "Duplicates",
            "Skipped",
            "Already contacted",
            "Already sent",
            "Sent-log overlap",
            "Skipped math",
            "Why only",
            "History filter excluded",
            "cold-safe leads remain",
            "planned_authoritative_sent_overlap_count",
            "skippedMathMismatch",
            "dispatchPreviewRouteSummary",
            "dispatchConfirmSafetyState",
            "Ready to confirm Fresh Cold queue",
            "Confirm locked — review preview",
            "Confirm locked — rerun preview",
            "importantDispatchConfirmButtonLabel",
            "dispatchSourceDisplayName",
            "dispatchSourceDetailLabel",
            "dispatch_source_kind",
            "Fresh Cold Campaign",
            "Recontact Existing Leads",
            "Checked Recontact Pool",
            "Previously contacted",
            "Seen this month",
            "Eligible after mandatory safety",
            "history_policy_version",
            "prior_success_policy",
            "source row",
            "Preview required for actual sendable count.",
            "cold-safe lead",
            "Confirm Recontact Queue",
            "Confirm Fresh Cold Queue",
            "Confirm locked — review preview",
        ]:
            self.assertIn(expected, source)
        for removed_active_workflow in [
            'data-dispatch-mode-card="safer_recontact"',
            'data-dispatch-mode-card="full_recontact"',
            "recontact_recency_override:",
        ]:
            self.assertNotIn(removed_active_workflow, source)
        self.assertIn("previewStatus = currentPreviewReady", source)
        self.assertLess(source.index("previewStatus = currentPreviewReady"), source.index("importantLeadDispatchPreviewLoading", source.index("previewStatus = currentPreviewReady")))
        self.assertNotIn("sendable</b>", source)
        html = INDEX_HTML.read_text(encoding="utf-8")
        for expected in [
            "leads-command-center",
            "leads-dispatch-mode-cards",
            "leads-dispatch-campaign-type",
            "<option value=\"cold\">Fresh Cold — excludes prior contacts</option>",
            "<option value=\"recontact_cold\">Recontact Existing Leads — allows prior successful contact</option>",
            "<option value=\"triaged_keep\">Fresh Cold Keep</option>",
            "<option value=\"cleaned\">Checked Recontact Pool</option>",
        ]:
            self.assertIn(expected, html)
        self.assertNotIn("leads-recontact-recency-override", html)

        styles = STYLES_CSS.read_text(encoding="utf-8")
        for expected in [
            ".leads-command-center",
            ".leads-command-section",
            ".dispatch-mode-card",
            ".dispatch-status-banner",
            ".dispatch-technical-select",
            ".recontact-override",
        ]:
            self.assertIn(expected, styles)

    def test_lead_check_status_card_and_preview_lock_states_are_rendered(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        backend = LIVE_DASHBOARD_PY.read_text(encoding="utf-8")
        markup = INDEX_HTML.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for expected in [
            "lead-check-status-card",
            "Lead Check Status",
            "Not ready for preview",
        ]:
            self.assertIn(expected, markup)

        for expected in [
            "lead_check_status",
            "renderLeadCheckStatusCard",
            "currentLeadCheckStatus",
            "currentLeadOpsProgress",
            "leadOpsProgressCopy",
            "lead_ops_progress",
            "Lead Ops progress",
            "Checking leads",
            "Fast triage",
            "Previewing dispatch",
            "Preview complete",
            "Confirming dispatch",
            "Confirm complete",
            "Percent complete",
            "role=\"progressbar\"",
            "Elapsed",
            "ETA",
            "Lead Ops progress appears stale. The job may have stopped or the dashboard may need inspection.",
            "leadCheckBlocksPreview",
            "leadCheckWorkflowStatus",
            "Ready for preview",
            "Not ready for preview",
            "Preview queue safety is unknown.",
            "button.disabled = previewBusy || Boolean(previewBlockReason) || warmUploadSelected",
            "els.leadsImportantDispatchConfirmBtn.disabled = confirmBusy || Boolean(previewBlockReason)",
        ]:
            self.assertIn(expected, source)

        for expected in [
            "Processing / checking",
            "Success — ready for Preview Dispatch",
            "Failed/Stale — check did not produce outputs",
            "Do not preview. Re-upload a clean lead CSV and run Upload & Check again.",
            "Check failed or stale",
            "No cleaned/rejected output files were produced.",
            "Check state mismatch",
            "Latest check result does not match the current upload.",
            "latest_master_check_matches_current_run",
            "lead_ops_progress",
            "lead_ops_progress_",
            "Ready for preview",
            "Previewing dispatch",
            "Confirming dispatch",
            "Confirm complete",
            "LEAD_OPS_PROGRESS_STALE_SECONDS = 120",
            "Lead Ops progress appears stale. The job may have stopped or the dashboard may need inspection.",
            "preview_ready",
        ]:
            self.assertIn(expected, backend)

        for expected in [
            ".lead-check-status-card",
            ".lead-check-status-card-good",
            ".lead-check-status-card-bad",
            ".lead-check-status-card-warn",
            ".lead-check-status-grid",
            ".lead-check-guidance",
            ".lead-ops-progress-module",
            ".lead-ops-progress-track",
            ".lead-ops-progress-warning",
        ]:
            self.assertIn(expected, styles)

    def test_lead_check_dispatch_preview_and_queue_statuses_are_distinct(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn('const label = previewReady ? "Complete" : failed ? "Failed" : progressLabel;', source)
        self.assertIn('const failed = ["failed", "stale"].includes(phase) || (completedCheckPhase && !previewReady);', source)
        self.assertIn('message: completedCheckPhase ? "Lead check complete."', source)
        self.assertIn('previewStatus = currentPreviewReady', source)
        self.assertIn('lastImportantDispatchPreviewState = "not_generated"', source)
        self.assertIn('lastImportantDispatchPreviewState = "ready"', source)
        self.assertIn('currentDispatchConfirmed', source)
        self.assertIn('Confirm Recontact Queue', source)
        self.assertNotIn('message: completedCheckPhase ? "Preview complete."', source)

    def test_recontact_readiness_is_scoped_to_checked_source_not_fresh_check(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        readiness_start = source.index("function selectedDispatchSourceReadiness")
        readiness_end = source.index("function dispatchActionBlockReason", readiness_start)
        readiness = source[readiness_start:readiness_end]

        self.assertIn('normalizedCampaign === "recontact_cold" ? "cleaned"', readiness)
        self.assertIn('if (normalizedCampaign === "cold")', readiness)
        self.assertIn("leadCheckBlocksPreview(currentLeadCheckStatus(status))", readiness)
        self.assertIn("dispatchSource.dispatch_source_exists !== true", readiness)
        self.assertIn("base.row_count <= 0", readiness)
        self.assertIn("base.eligible_row_count <= 0", readiness)
        self.assertNotIn('normalizedCampaign === "recontact_cold"\n    && leadCheckBlocksPreview', readiness)

        payload_start = source.index("function importantLeadDispatchPayload")
        payload_end = source.index("async function previewImportantLeadDispatch", payload_start)
        payload = source[payload_start:payload_end]
        self.assertIn('output_path: campaignType === "recontact_cold"', payload)
        self.assertIn("? selectedSourcePath", payload)

        cards_start = source.index("function renderDispatchModeCards")
        cards_end = source.index("function renderImportantDispatch", cards_start)
        cards = source[cards_start:cards_end]
        self.assertIn('String(preview.campaign_type || "") === "recontact_cold"', cards)
        self.assertIn('"Preview required"', cards)

    def test_lead_ops_campaign_intake_polish_and_locked_states_are_rendered(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        markup = INDEX_HTML.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for expected in [
            "Campaign Intake",
            "Upload Source",
            "Check Result",
            "No completed check yet.",
            "Next source action",
            "Preview cap",
            "Use <strong>all</strong> or enter a number.",
        ]:
            self.assertIn(expected, markup)

        for expected in [
            'label: state === "processing" ? "Checking…" : "Failed/Stale — check did not produce outputs"',
            "Waiting for check output files.",
            "Checking source…",
            "Waiting for output files…",
            "This may take a moment.",
            "Selected file",
            "Current job",
            "Current run",
            "Waiting for check output.",
            "Check failed or stale.",
            "Source rows 0",
            "Preview locked",
            "button.classList.toggle(\"is-locked\"",
            "Locked until Check/Triage completes.",
            "step: \"Source\"",
            "step: \"Check\"",
            "step: \"Triage\"",
            "step: \"Preview\"",
            "step: \"Confirm\"",
        ]:
            self.assertIn(expected, source)
        self.assertNotIn('state === "processing" ? "Processing / checking" : "Not started"', source)

        for expected in [
            "Lead Ops campaign-intake polish",
            "grid-template-areas: \"source result status\" \"source result actions\"",
            ".lead-check-processing-strip",
            ".leads-check-waiting",
            ".source-summary-empty",
            ".btn.is-locked",
        ]:
            self.assertIn(expected, styles)

    def test_dispatch_preview_renders_backend_blocked_response(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "function previewDispatchBlockedFeedback",
            "errorCode === \"triage_not_ready\"",
            "Current staged Fast Triage Keep is empty.",
            "Run Check Leads / Fast Triage first.",
            "Retry action:",
            "Source path:",
            "err?.payload",
            "Boolean(payload?.blocked) || Boolean(payload?.error)",
            "Preview Dispatch request started.",
            "Preview Dispatch API failure:",
            "Dispatch preview blocked:",
        ]:
            self.assertIn(expected, source)

        fetch_start = source.index("async function fetchJson")
        fetch_end = source.index("function renderLeadsMappingOptions", fetch_start)
        fetch_body = source[fetch_start:fetch_end]
        self.assertIn("error.payload = data;", fetch_body)
        self.assertIn("error.status = response.status;", fetch_body)

        preview_start = source.index("async function previewImportantLeadDispatch")
        preview_end = source.index("async function confirmImportantLeadDispatch", preview_start)
        preview_body = source[preview_start:preview_end]
        self.assertIn("previewDispatchBlockedFeedback(payload", preview_body)
        self.assertIn("lastImportantDispatchPreviewState = blocked ? \"blocked\" : \"failed\";", preview_body)
        self.assertIn("renderImportantDispatch(lastImportantDispatch);", preview_body)
        self.assertNotIn("confirmImportantLeadDispatch(", preview_body)

    def test_dispatch_preview_source_state_is_authoritative_for_selected_eligibility(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        backend = LIVE_DASHBOARD_PY.read_text(encoding="utf-8")

        plan_start = source.index("function currentDispatchPlanKey")
        plan_end = source.index("function dispatchPreviewMatchesCurrentSelection", plan_start)
        plan_body = source[plan_start:plan_end]
        for expected in [
            "dispatchSourceForSelectedMode()",
            "source.dispatch_source_path",
            "source.dispatch_source_exists",
            "source.dispatch_source_row_count",
            "source.dispatch_eligible_row_count",
            "source.verification_file_mtime",
            "els.leadsImportantDispatchCap",
            "selectedImportantDispatchCampaignType()",
        ]:
            self.assertIn(expected, plan_body)
        self.assertLess(plan_body.index("source.dispatch_source_path"), plan_body.index("els.leadsImportantDispatchCap"))

        persisted_start = source.index("function persistedImportantDispatchPreviewKey")
        persisted_end = source.index("function hydrateImportantDispatchPreviewFromStatus", persisted_start)
        persisted_body = source[persisted_start:persisted_end]
        self.assertIn("preview.dispatch_source_exists", persisted_body)
        self.assertIn("preview.dispatch_cap", persisted_body)
        self.assertIn("preview.campaign_type", persisted_body)

        hydrate_start = persisted_end
        hydrate_end = source.index("function dispatchSummaryMatchesCurrentSource", hydrate_start)
        hydrate_body = source[hydrate_start:hydrate_end]
        self.assertIn("if (!persistedKey)", hydrate_body)
        self.assertIn("lastImportantDispatchPreview = null", hydrate_body)
        self.assertLess(
            hydrate_body.index("lastImportantDispatchPreview = {"),
            hydrate_body.index("persistedKey !== currentKey"),
        )
        self.assertIn("persistedKey !== currentKey", hydrate_body)
        self.assertNotIn("persistedKey == currentKey", hydrate_body)

        render_start = source.index("function renderImportantDispatch")
        render_end = source.index("function renderLeadsShardResults", render_start)
        render_body = source[render_start:render_end]
        self.assertIn("dispatchPreviewRouteSummary(dispatchPreview, dispatchSource)", render_body)
        self.assertIn("Writable", render_body)
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("Dispatch Preview", html)

        funnel_start = source.index("function renderLeadFunnelSummary")
        funnel_end = source.index("function formatOperatorCount", funnel_start)
        funnel_body = source[funnel_start:funnel_end]
        self.assertIn("Historical/canonical files", funnel_body)
        self.assertIn("Current staged run", funnel_body)

        count_start = backend.index("def _csv_count_from_status_label")
        count_end = backend.index("def _csv_funnel_stage", count_start)
        count_body = backend[count_start:count_end]
        self.assertIn("return 0", count_body)
        self.assertLess(count_body.index("return 0"), count_body.index("path = default_path"))

        verify_start = backend.index("def verify_important_leads")
        verify_end = backend.index("@app.get(\"/api/leads/verify-important/job", verify_start)
        verify_body = backend[verify_start:verify_end]
        self.assertIn("if mode != TRIAGE_MODE_STRICT:", verify_body)
        self.assertIn("payload.verified_path if payload else current_keep", verify_body)
        self.assertIn("payload.rejected_path if payload else current_paths[\"rejected_path\"]", verify_body)
        self.assertIn("payload.quarantine_path if payload else current_paths[\"quarantine_path\"]", verify_body)
        self.assertIn("important_leads_triage_paths=_important_triage_path_labels_for_state", verify_body)

    def test_intake_mode_label_prefers_current_status_over_selector(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        match = re.search(r"function intakeModeLabelFromStatus[\s\S]+?\)\.toLowerCase\(\);", source)
        self.assertIsNotNone(match)
        body = match.group(0)
        self.assertLess(body.index("status?.latest_master_check?.intake_mode"), body.index("els.leadsImportantIntakeMode?.value"))

    def test_snapshot_fallback_status_is_not_scary_disconnected(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "let socketLive = false;",
            "let snapshotFallbackHealthy = false;",
            'els.wsLabel.textContent = "Connected"',
            'els.wsLabel.textContent = "Live status"',
            "snapshotFallbackHealthy = response.ok;",
            "if (!socketLive) setConnectionState(false);",
        ]:
            self.assertIn(expected, source)
        start = source.index("function setConnectionState(live)")
        end = source.index("function showMessage", start)
        body = source[start:end]
        self.assertLess(body.index('"Connected"'), body.index("Ops socket disconnected"))

    def test_leads_run_safety_card_reports_wait_blocked_freshness_and_stale_pipeline(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        markup = INDEX_HTML.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for expected in [
            "leads-run-safety-card",
            "Current Run Safety",
            "WAIT",
            "leads-current-run-panel",
            "Advanced diagnostics",
        ]:
            self.assertIn(expected, markup)

        for expected in [
            "function leadsRunSafety",
            "lead-funnel-table-wrap",
            "<table class=\"lead-funnel-table\"",
            "<col class=\"lead-funnel-stage-col\"",
            "<col class=\"lead-funnel-value-col\"",
            "<th>Stage</th>",
            "<th>Historical/canonical files</th>",
            "<th>Current staged run</th>",
            "<tr>",
            "<td class=\"lead-funnel-stage\">",
            "<td class=\"lead-funnel-value\">",
            "status-pill",
            "SAFE TO CONTINUE",
            "BLOCKED",
            "Check Leads is running.",
            "Current leads.csv has not been published for this run.",
            "Triage output is stale.",
            "Dispatch preview is stale.",
            "Recipient queues are missing BookTitle",
            "leads.csv",
            "Triaged Keep",
            "Dispatch Preview",
            "STALE",
            "Confirm Dispatch blocked",
            "Check Leads is running for job",
        ]:
            self.assertIn(expected, source)

        for unexpected in [
            "renderLeadFunnelCard",
            "lead-funnel-cards",
            "lead-funnel-compare-row",
            "Current Live Funnel",
            "Next Batch Funnel",
        ]:
            self.assertNotIn(unexpected, source)
            self.assertNotIn(unexpected, styles)

        for expected in [
            ".lead-funnel-table",
            ".lead-funnel-table-wrap",
            "border-collapse: collapse",
            "table-layout: fixed",
            ".lead-funnel-stage-col",
            "width: 40%",
            ".lead-funnel-value-col",
            "width: 30%",
            ".status-pill",
            ".leads-run-safety-card-wait",
            ".leads-run-safety-card-blocked",
            ".leads-run-safety-card-safe-to-continue",
            ".leads-pipeline-step-stale",
        ]:
            self.assertIn(expected, styles)

    def test_stale_check_status_stops_raw_running_job_poll_and_safety_state(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        safety_start = source.index("function leadsRunSafety")
        safety_end = source.index("function dispatchActionBlockReason", safety_start)
        safety_body = source[safety_start:safety_end]
        self.assertIn('const checkRunning = leadCheckWorkflowStatus(leadCheck) === "running";', safety_body)
        self.assertNotIn("const checkRunning = isActiveImportantLeadCheckJob(activeCheckJob);", safety_body)

        render_start = source.index("function renderLeadsStatus")
        render_end = source.index("async function fetchLeadsStatus", render_start)
        render_body = source[render_start:render_end]
        self.assertIn(
            'const selectedCheckIsRunning = leadCheckWorkflowStatus(currentLeadCheckStatus(lastLeadsStatus)) === "running";',
            render_body,
        )
        self.assertIn("const activeCheckJob = selectedCheckIsRunning ? currentImportantCheckJob(lastLeadsStatus) : null;", render_body)
        self.assertIn("if (!selectedCheckIsRunning)", render_body)
        self.assertIn("stopImportantLeadCheckJobPolling();", render_body)

    def test_leads_funnel_table_rows_keep_three_native_cells(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        cell_match = re.search(r"function renderFunnelCell\(stage\) \{.*?\n\}", source, re.DOTALL)
        self.assertIsNotNone(cell_match)
        cell_source = cell_match.group(0)
        self.assertIn('<td class="lead-funnel-value">', cell_source)
        self.assertEqual(1, cell_source.count("<td"))
        self.assertEqual(1, cell_source.count('<span class="status-pill'))
        self.assertNotIn("lead-funnel-cell", cell_source)

        row_match = re.search(r"function renderFunnelComparisonRow\(label, currentStage, nextStage\) \{.*?\n\}", source, re.DOTALL)
        self.assertIsNotNone(row_match)
        row_source = row_match.group(0)
        self.assertIn("<tr>", row_source)
        self.assertIn('<td class="lead-funnel-stage">', row_source)
        self.assertEqual(2, row_source.count("renderFunnelCell("))
        self.assertNotIn("colspan", row_source)
        self.assertNotIn("rowspan", row_source)

        summary_match = re.search(r"function renderLeadFunnelSummary\(funnel\) \{.*?function renderLeadsRunSafety", source, re.DOTALL)
        self.assertIsNotNone(summary_match)
        summary_source = summary_match.group(0)
        self.assertIn('<table class="lead-funnel-table"', summary_source)
        self.assertIn("<tbody>", summary_source)
        self.assertEqual(8, summary_source.count("renderFunnelComparisonRow("))
        self.assertEqual(2, summary_source.count('<td class="lead-funnel-value"><span class="status-pill">'))
        self.assertNotIn("colspan", summary_source)
        self.assertNotIn("rowspan", summary_source)

        forbidden_display_selectors = [
            ".lead-funnel-table tr",
            ".lead-funnel-table td {\n  display",
            ".lead-funnel-table th {\n  display",
            ".lead-funnel-value {\n  display",
        ]
        for selector in forbidden_display_selectors:
            self.assertNotIn(selector, styles)

    def test_sender_cards_render_message_readiness_fields(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")
        for expected in [
            "renderMessageReadiness",
            "runProfilePreviewValidation",
            "Message Readiness",
            "Regenerate & Validate Preview",
            "/api/profiles/",
            "/preview-validate",
            "preview-validate-profile-btn",
            "Regenerating and validating the current preview",
            "BookTitle column",
            "BookTitle rows",
            "Fallback rows",
            "Invalid emails",
            "Duplicate emails",
            "Preview CSV",
            "Validation",
            "Expected mode",
            "Actual mode",
            "message_readiness",
            "overview-message-readiness",
            "detail-message-readiness-slot",
            "els.profileDetail.contains(previewButton)",
        ]:
            self.assertIn(expected, source)

        for expected in [
            ".message-readiness-pass",
            ".message-readiness-fail",
            ".message-readiness-stale",
            ".message-readiness-not-run",
            ".message-readiness-grid",
            ".message-readiness-feedback-success",
            ".message-readiness-feedback-error",
        ]:
            self.assertIn(expected, styles)

    def test_campaign_run_history_panel_renders_recent_records(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        markup = INDEX_HTML.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")
        for expected in [
            "campaign-run-history",
            "Campaign Run History",
        ]:
            self.assertIn(expected, markup)
        for expected in [
            "renderCampaignRunHistory",
            "campaign_run_history",
            "campaignHistoryEventLabel",
            "campaignHistoryReason",
            "Readiness",
            "Validation",
            "Result / Reason",
        ]:
            self.assertIn(expected, source)
        for expected in [
            ".campaign-history-panel",
            ".campaign-history-table",
        ]:
            self.assertIn(expected, styles)

    def test_quarantine_review_inbox_wires_filters_selection_and_actions(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "refreshQuarantineReview",
            "renderQuarantineReview",
            "runQuarantineReviewAction",
            "loadQuarantineReviewLeadDetail",
            "selectedQuarantineLeadIds",
            "/api/leads/quarantine-review?",
            "/api/leads/quarantine-review/action",
            "data-quarantine-select",
            "data-quarantine-inspect",
            "promote_dispatch_ready",
            "send_to_strict_verify",
        ]:
            self.assertIn(expected, source)

    def test_quarantine_review_bulk_selection_controls_and_accessibility_are_present(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "data-quarantine-page-toggle",
            "data-quarantine-check-page",
            "data-quarantine-uncheck-page",
            "data-quarantine-select-all-filtered",
            "data-quarantine-clear-selection",
            "aria-checked",
            "\"mixed\"",
            "applyQuarantineHeaderCheckboxState",
            "selectAllFilteredQuarantineLeads",
            "excluded_lead_ids",
            "select_all_filtered",
        ]:
            self.assertIn(expected, source)

    def test_quarantine_review_pagination_and_range_controls_are_present(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "quarantinePageSize",
            "quarantinePageIndex",
            "QUARANTINE_PAGE_SIZE_OPTIONS",
            "data-quarantine-page-size",
            "data-quarantine-prev-page",
            "data-quarantine-next-page",
            "Showing",
            "quarantineVisibleRange",
            "quarantineTotalPages",
        ]:
            self.assertIn(expected, source)

    def test_verify_stop_button_requests_cancel_without_clearing_outputs(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "leadsImportantVerifyStopBtn",
            "stopImportantLeadVerify",
            "/cancel",
            "Stop Verify",
            "Stopping...",
        ]:
            self.assertIn(expected, source)

    def test_fast_triage_is_default_and_strict_public_proof_is_separate(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        for expected in [
            "VERIFY_MODE_FAST_TRIAGE",
            "VERIFY_MODE_MANUAL_AUTHOR_RESEARCH",
            "VERIFY_MODE_STRICT_PUBLIC_PROOF",
            "leadsImportantVerifyStrictBtn",
            "leads_triaged_keep.csv",
            "leads_triaged_reject.csv",
            "leads_triaged_quarantine.csv",
            "leads_verified.csv",
            "leads_verify_rejected.csv",
            "leads_quarantine.csv",
            "runImportantLeadVerify(VERIFY_MODE_FAST_TRIAGE)",
            "runImportantLeadVerify(VERIFY_MODE_STRICT_PUBLIC_PROOF)",
            "Manual Author Research mode keeps rows with valid AuthorName and AuthorEmail when no hard safety blocker exists. Rows missing BookTitle are kept only when the selected template has a safe fallback subject/body. Missing proof/enrichment fields are warnings, not dispatch blockers.",
            "Keep with fallback",
            "Soft warnings that did not block Keep.",
            "Review/Quarantine rows are not dispatched automatically.",
            "soft_warning_counts",
            "hard_reject_counts",
            "Already Contacted Evidence",
        ]:
            self.assertIn(expected, source)
        self.assertIn('intake_mode: els.leadsImportantIntakeMode?.value || "standard"', source)
        self.assertNotIn("leads-important-intake-mode", html)
        self.assertNotIn("<option value=\"manual_author_research\">Manual Author Research</option>", html)

    def test_leads_workspace_uses_operator_first_layout(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        react_source = REACT_MAIN.read_text(encoding="utf-8")
        leads_start = html.index('<section id="leads-view"')
        leads_end = html.index("</main>", leads_start)
        leads_html = html[leads_start:leads_end]
        styles = STYLES_CSS.read_text(encoding="utf-8") + TAILWIND_CSS.read_text(encoding="utf-8")

        for expected in [
            "Leads Operations",
            "Clean, triage, and prepare lead sources.",
            "Command Center",
            "Prepare Dispatch",
            "leads-control-bar",
            "leads-ops-bar",
            "Campaign Intake",
            "Upload Source",
            "Next source action",
            "leads-important-upload-file",
            "leads-important-upload-type",
            "leads-important-upload-check-btn",
            "leads-important-check-btn",
            "Check Leads",
            "leads-control-check-chips",
            "Select source and mode",
            "Dispatch Preview",
            "Confirm queue",
            "Start Senders",
            "Preview Dispatch",
            "Confirm queue",
            "Advanced diagnostics",
            "leads-current-run-panel",
            "leads-workflow-task-list",
            "leads-command-center",
            "leads-campaign-command",
            "leads-preview-command",
            "leads-confirm-command",
            "leads-start-command",
            "leads-page-title",
            "leads-current-queue-note",
            "leads-dispatch-current-queue-note",
            "Private JC has an unfinished recipient queue. Finish the current queue before confirming a new dispatch.",
            "Changing source changes the eligible count.",
            "leads-operator-status-strip",
            "leads-workflow-status-banner",
            "leads-active-alerts",
        ]:
            self.assertIn(expected, leads_html)
        self.assertIn('<input id="leads-important-upload-type" type="hidden" value="cold" />', leads_html)
        self.assertNotIn('<select id="leads-important-upload-type"', leads_html)
        for expected in [
            'formData.append("upload_type", selectedLeadUploadType())',
            "Warm upload checked. Generate drafts before explicit Warm Private JC confirmation.",
            "Warm email ready",
            "Contact forms",
            "Already contacted",
            "Warm Research uses its own draft, confirmation, and Private JC lane.",
            "Warm Research Outputs",
            "Explicit confirmation required",
            "Historical sender activity below does not unlock this upload workflow.",
            "applyWarmResearchLayoutState",
            "warm-research-mode",
            "Generate Warm Draft Preview",
            "/api/leads/check-important/warm-preview",
            "warm_email_preview.csv",
        ]:
            self.assertIn(expected, source)
        self.assertIn("#leads-view.warm-research-mode .leads-campaign-command", styles)
        self.assertIn("#leads-view.warm-research-mode .leads-command-column-right", styles)
        for old_heading in [
            "Recommended Next Action",
            "Workflow and Source",
            "Workflow Progress",
            "Current Source Summary",
            "Advanced run details",
            "STEP 1",
            "Lead Triage",
            "Active Alerts",
            "Alert details",
            "Raw paths",
            "Run/debug details",
            "Debug state",
            "Safety Rule",
            "One sender route per lead",
            "leads-check-section",
            "leads-triage-section",
            "leads-alerts-section",
        ]:
            self.assertNotIn(old_heading, leads_html)
        self.assertEqual(leads_html.count('class="leads-control-bar leads-ops-bar"'), 1)
        self.assertEqual(leads_html.count('id="leads-workflow-status-banner"'), 1)
        self.assertEqual(leads_html.count('id="leads-workflow-task-list"'), 1)
        self.assertEqual(leads_html.count('id="leads-current-run-panel"'), 1)
        self.assertEqual(leads_html.count('class="leads-command-main"'), 1)
        self.assertEqual(leads_html.count('class="leads-command-section leads-preview-command"'), 1)
        self.assertEqual(leads_html.count('class="leads-command-section leads-confirm-command"'), 1)
        self.assertEqual(leads_html.count('class="leads-collapsible advanced-details leads-advanced-diagnostics"'), 1)
        self.assertEqual(leads_html.count("Dispatch Preview"), 1)
        self.assertNotIn("Writable after history filtering", leads_html)
        self.assertNotIn("Private JC planned", leads_html)
        self.assertNotIn("Advanced dispatch details", source)
        action_start = leads_html.index('class="leads-control-actions"')
        action_end = leads_html.index("</div>", action_start)
        action_html = leads_html[action_start:action_end]
        self.assertLess(action_html.index("Check Leads"), action_html.index("Upload &amp; Check"))
        self.assertLess(
            leads_html.index('id="leads-important-upload-check-btn"'),
            leads_html.index('id="leads-important-dispatch-preview-btn"'),
        )
        self.assertNotIn("leads-important-dispatch-preview-top-btn", leads_html)
        self.assertIn('<details class="campaign-control-details">', leads_html)

        for expected in [
            "renderLeadsCurrentRunPanel",
            "renderLeadsWorkflowTaskList",
            "renderLeadsCurrentQueueNote",
            "selectedLeadUploadType",
            "selectedLeadCheckReport",
            "selectedLeadTriageReport",
            "selectedModeLeadCheckStatus",
            "reportMatchesUploadType",
            "if (checkTime && (!triageTime || triageTime < checkTime)) return {}",
            "Latest check result does not match the selected upload type.",
            "Do not preview. Rerun Upload & Check for the selected upload type.",
            "No current check is ready for the selected upload type.",
            "checkReadyForCounts ? Number(latestCheck.input_rows || pipeline.input_rows || 0) : 0",
            "checkReadyForCounts ? Number(latestTriage.keep_count || latestTriage.kept_rows || dispatchSource.dispatch_eligible_row_count || 0) : 0",
            "lastImportantLeadCheck = selectedLeadCheckReport(lastLeadsStatus)",
            "lastImportantVerify = selectedLeadTriageReport(lastLeadsStatus)",
            "currentRunWorkflowState",
            "currentRunPreviewBlockMessage",
            "Source ready for preview",
            "Source Summary",
            "Input",
            "Cleaned",
            "Rejected",
            "Triage Keep",
            "Triage reject",
            "Dispatch eligible",
            "Check Leads",
            "Triage",
            "Source",
            "Check",
            "Preview",
            "Confirm",
            "Locked until Check/Triage completes.",
            "safer_recontact_source_summary",
            "lastSaferRecontactSummary = lastLeadsStatus.safer_recontact_source_summary",
            "Previously contacted:",
            "Source:",
            "selectedDispatchSourceLabel",
            "leads-dispatch-section-deferred",
            "Counts below describe the current checked and triaged source only.",
            "Source rows 0 · Not ready for preview until Upload & Check completes.",
            "leadsControlCheckResult",
            "Private JC has an unfinished recipient queue.",
            "Reason ledger and queues",
            "Selected source has",
            "broader than the confirmed safe source",
            "Preview blocked: current staged keep is empty",
            "Preview blocked: source file missing",
            "renderLeadsOperatorStatusStrip",
            "renderLeadsWorkflowStatusBanner",
            "renderLeadsActiveAlerts",
            "leads-alert-summary-row",
            "Safety messages",
            "New dispatch source warning",
            "Check complete. Next step: Run Fast Triage.",
            "Fast Triage running...",
            "Fast Triage complete. Preview Dispatch is ready.",
            "No preview yet.",
            "Locked until Check/Triage completes.",
            "Preview failed. Retry Preview Dispatch.",
            "Preview blocked.",
            "Preview/source/cap mismatch. Retry Preview Dispatch.",
            "Triage not ready: leads_triaged_keep.csv is missing. Run Fast Triage after Check Leads completes.",
            "Triage not ready: leads_triaged_keep.csv has no Keep rows. Review/Quarantine rows are not dispatched automatically.",
            "Manual Author Research mode keeps rows with valid AuthorName and AuthorEmail when no hard safety blocker exists. Rows missing BookTitle are kept only when the selected template has a safe fallback subject/body. Missing proof/enrichment fields are warnings, not dispatch blockers.",
            "Rows missing BookTitle are kept only when the selected template has a safe fallback subject/body.",
            "Soft warnings that did not block Keep.",
            "Review/Quarantine rows are not dispatched automatically.",
            "SendGrid added 0 rows because the selected rows were excluded before queue write",
            "Advanced file details",
            "const previewMetricsMarkup = dispatchPreview",
            "Sent-log overlap",
            "Skipped math",
            "Review required",
            "sentLogOverlap",
            "Skipped rows ${summary.skippedRows.toLocaleString()} do not match skipped reasons",
            "History filter excluded ${dispatchSummary.historyRemoved.toLocaleString()}",
            "workflow-banner-inline",
            "Current step",
            "leads-control-check-result",
        ]:
            self.assertIn(expected, source)

        for expected in [
            ".leads-page-title",
            ".leads-current-queue-note",
            ".leads-control-bar",
            ".leads-ops-bar",
            ".leads-command-main",
            ".leads-command-column",
            ".leads-current-run-panel",
            ".leads-workflow-task-list",
            ".leads-command-center",
            ".leads-command-section",
            ".workflow-tracker-row",
            ".workflow-track-step-good",
            ".workflow-track-step-warn",
            ".leads-dispatch-section-deferred",
            ".leads-dispatch-current-queue-note",
            ".leads-alert-summary-row",
            ".leads-alert-details",
            ".leads-advanced-diagnostics",
            ".current-run-card",
            ".current-run-summary-line",
            ".current-run-next-action",
            ".current-run-blocker",
            ".lead-triage-details-drawer",
            ".operator-status-strip",
            ".leads-workflow-status-banner",
            ".workflow-banner-inline",
            ".workflow-banner-chip",
            ".workflow-banner-meta",
            ".leads-control-check-chips",
            ".leads-source-actions-label",
            ".btn.is-loading::before",
            ".btn.is-next-action:not(:disabled)",
            ".dispatch-next-step-banner",
            ".dispatch-step-subhead",
            ".operator-workflow-section",
            ".advanced-details",
            ".leads-active-alerts",
            ".leads-alert-card",
        ]:
            self.assertIn(expected, styles)

        self.assertIn(
            '<div className="leads-command-main react-lead-workspace">',
            react_source,
        )
        self.assertIn(
            "<CommandRail left={view.commandLeft} right={view.commandRight} />",
            react_source,
        )
        self.assertRegex(
            styles,
            r"#leads-view\.react-leads-page:not\(\.warm-research-mode\)\s*"
            r"\.react-lead-workspace\.leads-command-main\s*\{[^}]*"
            r"grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important;",
        )

        self.assertIn("#leads-view .leads-page-title {\n  order: 1;", styles)
        self.assertIn("#leads-view .leads-command-center {\n  order: 2;", styles)
        self.assertIn("grid-template-columns: minmax(0, 42%) minmax(0, 58%) !important;", styles)
        self.assertIn("position: static !important;", styles)
        self.assertIn("transform: none !important;", styles)
        self.assertIn("overflow-wrap: anywhere;", styles)
        self.assertIn("width: min(100%, 150px);", styles)
        self.assertIn("max-height: none;", styles)
        self.assertIn("max-height: 54px;", styles)
        self.assertIn("#leads-view #leads-important-check-meta", styles)
        self.assertIn("white-space: normal;", styles)
        self.assertIn("text-overflow: clip;", styles)
        self.assertNotIn("leads-current-live-dispatch-card", leads_html)
        self.assertNotIn("current-live-dispatch-card", styles)

        tab_start = source.index("function applyDashboardTab()")
        tab_end = source.index("function isOpsTabVisible()", tab_start)
        tab_body = source[tab_start:tab_end]
        self.assertIn("const leadsActive = activeDashboardTab === \"leads\" && !wallboardMode;", tab_body)
        self.assertIn("mountExclusiveDashboardPanel(leadsActive);", tab_body)
        self.assertIn("els.opsTabBtn.classList.toggle(\"is-active\", !leadsActive);", tab_body)
        self.assertIn("els.leadsTabBtn.classList.toggle(\"is-active\", leadsActive);", tab_body)
        self.assertIn("els.opsView.hidden = leadsActive;", tab_body)
        self.assertIn("els.leadsView.hidden = !leadsActive;", tab_body)
        self.assertIn("els.opsView.setAttribute(\"aria-hidden\", String(leadsActive));", tab_body)
        self.assertIn("els.leadsView.setAttribute(\"aria-hidden\", String(!leadsActive));", tab_body)
        self.assertIn("els.opsView.setAttribute(\"inert\", \"\");", tab_body)
        self.assertIn("els.leadsView.setAttribute(\"inert\", \"\");", tab_body)

        self.assertNotIn("// --- TAB VISIBILITY GUARD ---", source)
        self.assertNotIn("// HARD TAB BODY CLASS FIX", source)
        self.assertNotIn("/* HARD TAB VISIBILITY FIX */", styles)

        self.assertIn('<details class="leads-collapsible advanced-details leads-advanced-diagnostics">', html)
        self.assertNotIn("advanced-file-details", html)
        self.assertNotIn("run-readiness-advanced", html)

    def test_dashboard_tabs_mount_only_active_panel_in_live_dom(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for expected in [
            "function mountExclusiveDashboardPanel(leadsActive)",
            "ensureTabPanelMountAnchors();",
            "if (els.opsView?.isConnected) els.opsView.remove();",
            "if (els.leadsView?.isConnected) els.leadsView.remove();",
            "insertAfterAnchor(tabPanelMounts.opsAnchor, els.opsView);",
            "insertAfterAnchor(tabPanelMounts.leadsAnchor, els.leadsView);",
        ]:
            self.assertIn(expected, source)

        apply_start = source.index("function applyDashboardTab()")
        apply_end = source.index("function isOpsTabVisible()", apply_start)
        body = source[apply_start:apply_end]
        self.assertLess(body.index("mountExclusiveDashboardPanel(leadsActive);"), body.index("els.opsView.classList.toggle"))

        self.assertIn("#leads-view.leads-workspace:not([hidden])", styles)
        self.assertNotIn("#leads-view.leads-workspace {\n  display: grid;", styles)

    def test_current_run_operator_panel_hides_stale_dispatch_noise_from_main_view(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("leads-current-run-panel", html)
        self.assertIn("data-leads-next-action", source)
        self.assertIn('action === "preview_dispatch"', source)
        self.assertIn('action === "confirm_dispatch"', source)
        zero_add_index = source.index("SendGrid added 0 rows.")
        dispatch_function_start = source.index("function renderImportantDispatch")
        self.assertGreater(zero_add_index, dispatch_function_start)
        self.assertNotIn("<summary>Advanced dispatch details</summary>", source[dispatch_function_start:zero_add_index])
        self.assertIn("Number(queue.count || 0) > 0 && !hasCaseInsensitiveField(queue.fields, \"BookTitle\")", source)

    def test_leads_live_dispatch_source_truth_is_separate_from_new_preview(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "currentLiveDispatchState",
            "hasActualLiveQueueActivity",
            "active_campaign_snapshot",
            "intended_source_row_count",
            "latest_confirmed_dispatch",
            "Private JC pending",
            "SendGrid pending",
            "New dispatch source warning",
            "newDispatchOnlySafetyWarning",
            "inactiveSendgridBookTitleOnly",
            "alertLooksLikeNewDispatchSourceWarning",
            "This warning applies to preparing a new dispatch. It does not block the already confirmed current live dispatch.",
            "Current live dispatch: Ready",
            "queueSafetySourceContext",
            "OUTSIDE_CHECKED_OUTPUT",
            "Live queues differ from the selected checked output.",
        ]:
            self.assertIn(expected, source)
        start = source.index("function renderLeadsCurrentRunPanel")
        end = source.index("function renderLeadsWorkflowStatusBanner", start)
        body = source[start:end]
        self.assertNotIn("OUTSIDE_CHECKED_OUTPUT", body)
        self.assertNotIn("current_send_safety", body)

    def test_empty_live_queue_does_not_render_stale_current_live_queue_blocker(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")

        for expected in [
            "function activeSenderStateNames",
            "function activeSenderProcessCount",
            "function liveRecipientQueueCounts",
            "function hasActualLiveQueueActivity",
            "const queueUnsafe = backendQueueUnsafe && hasLiveActivity && !sourceWarningOnly;",
            "const queueWarnings = backendQueueUnsafe && !queueUnsafe ? backendReasons : [];",
            "else if (Array.isArray(safety.queueWarnings) && safety.queueWarnings.length)",
            "sourceWarning ? \"New dispatch source warning\" : \"Inactive live queue warning\"",
            "blocks: false",
            "currentLiveDispatchState(status).hasLiveQueue",
        ]:
            self.assertIn(expected, source)

        safety_start = source.index("function leadsRunSafety")
        safety_end = source.index("function dispatchActionBlockReason", safety_start)
        safety_body = source[safety_start:safety_end]
        self.assertIn("backendQueueUnsafe", safety_body)
        self.assertIn("hasActualLiveQueueActivity(status, snapshot)", safety_body)
        self.assertIn("queueWarnings", safety_body)
        self.assertNotIn("const queueUnsafe = Object.prototype.hasOwnProperty.call", safety_body)

        alerts_start = source.index("function renderLeadsActiveAlerts")
        alerts_end = source.index("function renderLeadsRunSafety", alerts_start)
        alerts_body = source[alerts_start:alerts_end]
        self.assertIn("New dispatch source warning", alerts_body)
        self.assertIn("Current live queue blocked", alerts_body)
        self.assertLess(alerts_body.index("safety.queueWarnings"), alerts_body.index("currentLiveDispatchState(status).hasLiveQueue"))

    def test_dashboard_ops_hierarchy_uses_fleet_summary_and_compact_sender_warnings(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "total_awaiting_outcome",
            "sendgridOutcomeHealthSummaryHtml",
            "sendgrid_outcome_health",
            "Route yes",
            "Public key yes",
            "Receiver URL no",
            "Latest outcome event",
            "SendGrid outcome feed is stale. Emails may have been accepted by SendGrid, but delivery/bounce/spam outcomes are not currently being received.",
            "Alerts",
            "Next Action",
            "summary-alert-counts",
            "summary-inline-details",
            "Start JC",
            "Use the Private JC sender row below.",
            "fleetProfileStatus",
            "renderFleetProfileStrip",
            "renderSummaryInsightList",
            "profileRunSentDisplay",
            "run_sent_display",
            "strongestProfileWarning",
            "overview-metrics",
            "overview-warning-text",
            "overviewStateIndicator",
            "overview-state-line",
            "Cooldown",
            "profileActivityState",
            "Running",
            "Stopped",
            "readiness_label",
            "reason_code",
            "telemetry_quality_label",
        ]:
            self.assertIn(expected, source)

        styles = STYLES_CSS.read_text(encoding="utf-8")
        for expected in [
            ".summary-grid",
            ".summary-strip",
            ".alert-card",
            ".alert-row",
            ".alerts-progress-row",
            ".alerts-progress-value-row",
            "--status-green",
            "--status-amber",
            "--status-red",
            ".summary-card-private_jc",
            ".summary-card-next_action",
            ".sender-status-pill-good",
        ]:
            self.assertIn(expected, styles)

    def test_sender_status_badge_prefers_active_runtime_before_blocked_queue(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        start = source.index("function senderStatusBadge(profile)")
        end = source.index("function renderSenderStatusConsole", start)
        body = source[start:end]
        self.assertLess(body.index('["running", "starting", "sleeping"]'), body.index("queueSafetyBlockedForProfile(profile)"))
        self.assertLess(body.index('["cooldown", "paused"]'), body.index("queueSafetyBlockedForProfile(profile)"))
        self.assertIn('return { label: "Running", tone: "good" };', body)
        self.assertIn('return { label: "Complete", tone: "good" };', body)
        self.assertIn('return { label: "Resume", tone: "good" };', body)
        self.assertIn('return { label: "Ready", tone: "good" };', body)
        self.assertIn('return { label: "Blocked", tone: "bad" };', body)
        self.assertLess(body.index('return { label: "Complete", tone: "good" };'), body.index("queueSafetyBlockedForProfile(profile)"))

    def test_manual_sender_start_warns_and_requires_confirmation(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")

        self.assertIn('path.startsWith("/api/start/")', source)
        self.assertNotIn('path === "/api/start"', source)
        self.assertIn("LIVE SENDER ACTION", source)
        self.assertIn("This starts or resumes real sender workers and can consume pending queue rows", source)
        self.assertIn("Use only on the live Windows/WSL machine", source)
        self.assertIn("Dashboard auto-start may be disabled", source)
        self.assertIn("Manual Start/Resume cancelled. No sender workers were started.", source)
        self.assertIn("Manual Start/Resume can launch real workers and consume queues.", html)
        self.assertIn("Auto-start remains separate.", html)

    def test_zero_queue_sender_buttons_show_no_queue(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("Start unavailable — no pending leads.", source)
        self.assertIn('noPendingQueue ? "No queue" : "Start"', source)
        self.assertIn("|| noPendingQueue", source)
        self.assertIn(
            "|| (!warmProfile && !stopAvailable && !previewSyncAvailable && !startAvailable)",
            source,
        )
        self.assertIn('previewSyncAvailable ? "preview_sync" : "start"', source)
        self.assertIn("profilePendingCount(profile) > 0", source)
        self.assertIn("pendingCount <= 0", source)

    def test_bulk_start_control_is_absent_and_individual_start_remains(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        markup = INDEX_HTML.read_text(encoding="utf-8")

        self.assertNotIn('id="start-btn"', markup)
        self.assertNotIn('startBtn: document.getElementById("start-btn")', source)
        self.assertNotIn('postAction("/api/start")', source)
        self.assertNotIn('"Start all available senders."', source)
        self.assertIn('path.startsWith("/api/start/")', source)
        self.assertIn('postAction(`/api/start/${profile}`', source)

    def test_dashboard_next_action_prefers_active_private_jc_monitoring(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn('value: "Monitor Private JC"', source)
        self.assertIn("Private JC is running. Remaining recipients are verified against the confirmed preview.", source)
        self.assertIn('value: "Resume Private JC"', source)
        self.assertIn("Queue partially consumed — remaining recipients verified safe.", source)

    def test_sendgrid_metric_disclaimer_and_bounce_warnings_render_from_existing_metrics(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for expected in [
            "SENDGRID_METRIC_DISCLAIMER_COPY",
            "SendGrid delivery status only. Delivered means accepted by the recipient server, not confirmed inbox placement. Non-bounced emails may still land in spam or be filtered. Astra/private JC sends are tracked separately and are not included in SendGrid totals.",
            "function sendgridBounceRateFromSummary",
            "summary.processed",
            "summary.bounce",
            "bounceRate > 0.10",
            "bounceRate > 0.25",
            "High SendGrid bounce rate detected. Pause SendGrid dispatch until recipient queues are cleaned.",
            "SendGrid dispatch unsafe. Bounce rate is critically high.",
            "renderSendGridMetricDisclaimer(summary)",
        ]:
            self.assertIn(expected, source)

        for expected in [
            ".sendgrid-metric-disclaimer",
            ".sendgrid-metric-disclaimer-warn",
            ".sendgrid-metric-disclaimer-bad",
            ".sendgrid-metric-disclaimer-alert",
        ]:
            self.assertIn(expected, styles)

    def test_private_jc_queue_repair_panel_explains_block_and_calls_repair_endpoint(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for expected in [
            "renderPrivateJcQueueRepair",
            "Private JC queue is blocked because the live queue contains recipients that overlap rejected leads or are outside the current approved source.",
            "Repair archives the current JC queue, clears the unsafe live file, and rebuilds JC recipients only from the current approved dispatch source. It does not start JC.",
            "repair-private-jc-queue-btn",
            "/api/profiles/private_jc/repair-queue",
            "unsafe_queue_rows_archived",
            "reject_overlap_rows_removed",
            "outside_source_rows_removed",
            "rebuilt_queue_rows",
            "backup_path",
        ]:
            self.assertIn(expected, source)

        for expected in [
            ".private-jc-repair-panel",
            ".private-jc-repair-head",
            ".private-jc-repair-summary",
            ".private-jc-repair-feedback-success",
            ".private-jc-repair-feedback-error",
        ]:
            self.assertIn(expected, styles)

    def test_dispatch_confirmed_summary_uses_persisted_counts_and_clear_missing_preview_warning(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "confirmedPrivateJcTotal",
            "confirmedSendgridTotal",
            "confirmedSg1",
            "confirmedSg2",
            "confirmedSg3",
            "confirmedSg4",
            "confirmedSg5",
            "No queue rows will be written.",
            "Nothing to confirm for queue writes because all eligible rows were already queued/skipped",
            "SendGrid added 0 rows because the selected rows were excluded before queue write",
            "already contacted",
            "already sent through SendGrid",
        ]:
            self.assertIn(expected, source)

    def test_dashboard_sender_workspace_uses_master_detail_layout_shell(self) -> None:
        source = INDEX_HTML.read_text(encoding="utf-8")
        for expected in [
          "app-shell",
          "app-rail",
          "app-main",
          "app-rail-status",
          "workspace-status-row",
          "workspace-header",
          "workspace-controls-card",
          "workspace-controls toolbar",
          "toolbar-field-window",
          "toolbar-field-cap",
          "send-cap-note",
          "ops-progress-strip",
          "ops-progress-shell",
          "ops-alerts-strip",
          "workspace-metric-details",
          "ops-progress-summary",
          "ops-progress-details-toggle",
          "ops-progress-details",
          "workspace-metric-drawer",
          "alerts-caption",
          "alerts-grid",
          "alerts-progress",
          "summary-grid",
          "summary-strip",
          "workspace-summary-strip",
          "workspace-primary",
          "workspace-card-detail-main",
          "detail-stage",
          "Active Alerts",
          "Run Progress / Alerts",
          "Run Progress / Alerts details",
          "View details",
          "Profile Detail",
        ]:
            self.assertIn(expected, source)

    def test_profile_detail_uses_compact_core_runtime_and_collapsible_diagnostics(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "renderDetailCoreRuntime",
            "renderDiagnosticRows",
            "renderDetailPrimaryWarning",
            "detail-core-runtime",
            "detail-primary-warning-slot",
            "detail-live-disclosure",
            "detail-webhook-disclosure",
            "detail-guard-disclosure",
            "diagnostic-row-list",
            "Pane Tail / Runtime Output",
            "truncateMiddle",
            "detail-state-line",
            "Effective Pace",
            "Readiness",
            "Reason",
            "Confidence",
        ]:
            self.assertIn(expected, source)

    def test_profile_detail_wording_distinguishes_recovered_vs_active_failure(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn("Recovered from an earlier run issue", source)
        self.assertIn("Active sender failure needs review", source)
        self.assertNotIn("current-run errors", source)

    def test_quarantine_review_styles_support_sticky_inbox_and_dense_rows(self) -> None:
        source = STYLES_CSS.read_text(encoding="utf-8")
        for expected in [
            ".summary-grid",
            ".summary-strip",
            ".ops-progress-shell",
            ".ops-alerts-strip",
            ".alerts-progress-row",
            ".alerts-progress-list",
            ".alerts-progress-main",
            ".alerts-progress-label-row",
            ".alerts-progress-value-row",
            ".alerts-progress-dot",
            ".alert-card",
            ".alert-row",
        ]:
            self.assertIn(expected, source)

    def test_dashboard_alerts_and_dispatch_use_compact_markup(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "summary-card-compact",
            "alert-card-compact",
            "alert-row",
            "alert-row-main",
            "renderAlertsProgress",
            "summarizeAlertProgress",
            "renderProgressSummaryStrip",
            "syncProgressDetailsToggle",
            "opsProgressDetailsToggle",
            "els.opsProgressDetails.open = !els.opsProgressDetails.open",
            'opsRoot?.querySelector(".ops-progress-strip")',
            "data.auth_enabled === false",
            "is-auth-disabled",
            "ops-progress-summary-item",
            "messageWithProfile",
            "blocks_sending",
            "Blocks Start",
            "Non-blocking",
            "alerts-progress-row",
            "Private Email",
            "SendGrid",
            "Dispatch Preview",
            "Preview is read-only and writes no queues.",
            "Duplicate planned emails",
            "quarantine-list-row",
            "quarantine-list-shell",
            "Lead Inspector",
        ]:
            self.assertIn(expected, source)

    def test_local_dev_auth_bypass_hides_login_without_removing_controls(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        markup = INDEX_HTML.read_text(encoding="utf-8")

        for expected in [
            "authDisabled",
            "data.auth_disabled",
            '? "Local dev"',
            'els.authLogoutBtn.classList.toggle("hidden", authDisabled)',
            "authState.authDisabled || !authState.authEnabled || authState.authenticated",
            "Local dev auth disabled.",
        ]:
            self.assertIn(expected, source)

        self.assertNotIn('id="start-btn"', markup)

        for control_id in [
            'id="stop-btn"',
            'id="ops-tab-btn"',
            'id="leads-tab-btn"',
            'id="leads-important-dispatch-preview-btn"',
        ]:
            self.assertIn(control_id, markup)

    def test_environment_banner_reports_auth_auto_start_and_live_sender_safety(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        component = (APP_JS.parent / "src" / "main.jsx").read_text(encoding="utf-8")

        for expected in [
            "dashboard-environment-banner",
            "Local / dev mode",
            "Live mode",
            "Auth disabled",
            "Auto-start disabled",
            "Manual Start/Resume can launch real workers and consume queues.",
        ]:
            self.assertIn(expected, source + component)

    def test_warm_lane_requires_explicit_confirm_and_separate_start(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")

        for expected in [
            "Confirm Warm Private JC",
            "Start Warm Private JC",
            "/api/leads/check-important/warm-confirm",
            "/api/start/private_jc_warm",
            "Warm Private JC Sender History",
            "<div><span>Ready / Original</span>",
            "<div><span>Running</span>",
            "<div><span>Cap</span>",
        ]:
            self.assertIn(expected, source)

    def test_navigation_uses_senders_and_lead_ops_labels(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")

        self.assertIn('setNodeText(els.opsTabBtn, "Senders")', source)
        self.assertIn('setNodeText(els.leadsTabBtn, "Lead Ops")', source)

    def test_warm_jc_sender_row_is_visible_but_opens_lead_ops_instead_of_starting(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        render_start = source.index("function renderSenderStatusConsole")
        render_end = source.index("function createAlertCardNode", render_start)
        render_body = source[render_start:render_end]
        click_start = source.index("async function handleSenderStatusClick")
        click_end = source.index("async function postAction", click_start)
        click_body = source[click_start:click_end]

        for expected in [
            'warmCanOpenLeadOps ? "open_lead_ops" : "no_queue"',
            'action === "open_lead_ops"',
            'status.label === "Partial" ? "Resume in Lead Ops" : "Open Lead Ops"',
            "private_jc_warm",
            "Private JC sender",
            "same limits as JC",
            'warmMax > 0 ? `max ${warmMax.toLocaleString()}` : "no run cap"',
            "No activity yet",
            "warmDraftPreviewCount",
            "warmHasDraftPreview",
            "No queue",
            "is-warm-jc",
        ]:
            self.assertIn(expected, render_body)
        for expected in [
            "function warmSenderDisplayState",
            'const label = String(lane.state || "No queue")',
            'label === "Blocked"',
            '"Running", "Ready", "Complete"',
            'label === "Partial" || label === "Not confirmed"',
        ]:
            self.assertIn(expected, source)
        self.assertNotIn("recipients_private_jc_warm.csv", render_body)
        self.assertNotIn("private_jc_warm_log.csv", render_body)
        self.assertNotIn("|| 10", render_body)
        self.assertIn("profile?.max_total ?? profile?.configured_max_total", render_body)
        self.assertNotIn('Age ${profile.last_age}', render_body)
        self.assertIn('profile === "private_jc_warm" && action === "open_lead_ops"', click_body)
        self.assertIn('setLeadWorkflow("warm")', click_body)
        self.assertIn("async function hydrateWarmSenderLeadStatus", source)
        self.assertIn('fetchJson("/api/leads/status")', source)
        self.assertIn("void hydrateWarmSenderLeadStatus()", source)

        styles = STYLES_CSS.read_text(encoding="utf-8")
        self.assertIn("#ops-view .sender-status-table tr.is-warm-jc td", styles)
        self.assertIn("#ops-view .sender-status-profile-meta", styles)
        self.assertIn('if (String(value || "") === "private_jc_warm") return "Warm Outreach";', source)
        self.assertNotIn("Warm Private JC${warmMax", render_body)

    def test_sender_table_render_is_idempotent_across_snapshot_and_tab_cycles(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        ensure_start = source.index("function ensureSenderStatusPanel")
        ensure_end = source.index("function syncProgressDetailsToggle", ensure_start)
        ensure_body = source[ensure_start:ensure_end]
        render_start = source.index("function renderSenderStatusConsole")
        render_end = source.index("async function hydrateWarmSenderLeadStatus", render_start)
        render_body = source[render_start:render_end]
        snapshot_start = source.index("function renderSnapshot")
        snapshot_end = source.index("async function fetchSnapshot", snapshot_start)
        snapshot_body = source[snapshot_start:snapshot_end]

        self.assertEqual(ensure_body.count('id="senders-table-panel"'), 1)
        self.assertIn('opsRoot?.querySelectorAll(".sender-status-panel")', ensure_body)
        self.assertIn("panels.shift()", ensure_body)
        self.assertIn("panels.forEach((panel) => panel.remove())", ensure_body)
        self.assertNotIn("senderStatusPanel?.isConnected", ensure_body)
        self.assertIn("setNodeHtml(", render_body)
        self.assertIn("allProfiles.findIndex", render_body)
        self.assertEqual(snapshot_body.count("renderSenderStatusConsole(snapshot, selectedProfile)"), 1)

        # Repeated snapshot/refresh renders replace the one tbody; they never append a panel.
        self.assertEqual(render_body.count("ensureSenderStatusPanel()"), 1)
        self.assertEqual(render_body.count("Private JC sender"), 1)
        self.assertEqual(render_body.count('profile?.name === "private_jc_warm"'), 1)

    def test_sender_panel_lookup_survives_detached_ops_view_during_lead_ops_tab(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        ensure_start = source.index("function ensureSenderStatusPanel")
        ensure_end = source.index("function syncProgressDetailsToggle", ensure_start)
        ensure_body = source[ensure_start:ensure_end]
        mount_start = source.index("function mountExclusiveDashboardPanel")
        mount_end = source.index("function applyDashboardTab", mount_start)
        mount_body = source[mount_start:mount_end]

        self.assertIn("if (els.opsView?.isConnected) els.opsView.remove()", mount_body)
        self.assertIn("const opsRoot = els.opsView", ensure_body)
        self.assertIn('opsRoot?.querySelector(".ops-progress-strip")', ensure_body)
        self.assertIn('opsRoot?.querySelectorAll(".sender-status-panel")', ensure_body)

    def test_sender_rows_dedupe_warm_jc_and_jc_by_profile_name(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        render_start = source.index("function renderSenderStatusConsole")
        render_end = source.index("async function hydrateWarmSenderLeadStatus", render_start)
        render_body = source[render_start:render_end]

        self.assertIn("allProfiles.findIndex", render_body)
        self.assertIn("candidate?.name === profile?.name", render_body)
        self.assertIn('profile?.name === "private_jc_warm"', render_body)
        self.assertIn("formatProfileName(profile.name)", render_body)

    def test_warm_research_groups_outputs_and_lane_status_with_safety_copy(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for expected in [
            "Warm Research Outputs",
            "Warm Private JC Sender History",
            "Previous Warm Outreach Run",
            "warm-private-action-panel",
            "warm-action-stack",
            "warm-research-output-group",
            "warm-private-lane-group",
            "warm-safety-card",
            "warm-post-command-grid",
            "Safety Rules",
            "Cold dispatch disabled for Warm Research",
            "Explicit confirmation required",
            "Warm confirmation stays separate",
            "Warm Outreach uses individual sender controls",
        ]:
            self.assertIn(expected, source)

        for expected in [
            "#leads-view.warm-research-mode .leads-control-bar",
            "#leads-view.warm-research-mode .leads-current-run-panel",
            "#leads-view.warm-research-mode .warm-action-stack .btn",
            "#leads-view.warm-research-mode .warm-research-output-group .operator-metric",
            "#leads-view.warm-research-mode .warm-safety-card",
            ".app-shell.warm-research-shell",
            "grid-template-columns: repeat(4, minmax(0, 1fr))",
        ]:
            self.assertIn(expected, styles)

        self.assertIn("controlBar.appendChild(els.leadsCurrentRunPanel)", source)
        self.assertIn("commandLeft.insertBefore(els.leadsCurrentRunPanel", source)
        self.assertIn("commandCenter.insertBefore(workflowTaskContainer, els.leadsWorkflowStatusBanner)", source)
        self.assertEqual(source.count('<p class="eyebrow">Warm Research Outputs</p>'), 0)
        self.assertEqual(source.count("Warm Private JC Sender History"), 1)
        self.assertEqual(source.count('<p class="eyebrow">Safety Rules</p>'), 1)

    def test_warm_research_uses_one_compact_four_step_workflow(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        warm_start = source.index("if (warmResearchUploadMode()) {", source.index("function renderLeadsWorkflowTaskList"))
        warm_end = source.index("const state = currentRunWorkflowState", warm_start)
        warm_workflow = source[warm_start:warm_end]

        for step in [
            "Upload Warm Research",
            "Review Split Outputs",
            "Generate Draft Preview",
            "Warm Private JC",
        ]:
            self.assertEqual(warm_workflow.count(f'step: "{step}"'), 1)
        for state in ["Complete", "Available", "Waiting", "Required"]:
            self.assertIn(state, warm_workflow)
        self.assertNotIn("workflow-banner-inline warm-workflow-banner", source)

    def test_lead_ops_and_senders_share_live_warm_status_counts_and_states(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")
        lead_start = source.index("function renderLeadsCurrentRunPanel")
        lead_end = source.index("function renderLeadsWorkflowTaskList", lead_start)
        lead_body = source[lead_start:lead_end]
        sender_start = source.index("function renderSenderStatusConsole")
        sender_end = source.index("async function hydrateWarmSenderLeadStatus", sender_start)
        sender_body = source[sender_start:sender_end]

        self.assertIn("function currentWarmPrivateJcStatus", source)
        self.assertIn("status?.warm_private_jc_status", source)
        self.assertIn("snapshot?.warm_private_jc_status", source)
        self.assertIn("currentWarmPrivateJcStatus(status, lastSnapshot)", lead_body)
        self.assertIn("currentWarmPrivateJcStatus(lastLeadsStatus, snapshot)", sender_body)
        for field in [
            "queued_remaining_count",
            "sent_count",
            "ready_original_count",
            "last_sent_email",
            "last_sent_timestamp",
            "next_queued_email",
            "last_worker_reason",
            "timeline",
        ]:
            self.assertIn(field, source)
        for state in ["Partial", "Running", "Complete", "Blocked"]:
            self.assertIn(state, source)
        self.assertIn("Resume Warm Private JC", lead_body)
        self.assertIn("Stop Warm Private JC", lead_body)
        self.assertIn("Resume in Lead Ops", sender_body)
        self.assertIn("warm-run-timeline", lead_body)
        self.assertIn("warm-live-warning", lead_body)
        self.assertIn("#leads-view.warm-research-mode .warm-run-timeline", styles)
        self.assertIn('els.wsLabel.textContent = "Live status"', source)

    def test_warm_activity_uses_readable_utc_timestamp_and_empty_copy(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        start = source.index("function formatWarmActivity")
        end = source.index("function formatProfileName", start)
        body = source[start:end]

        self.assertIn('if (!timestamp) return "No activity yet"', body)
        self.assertIn('timeZone: "UTC"', body)
        self.assertIn("year: \"numeric\"", body)
        self.assertIn("minute: \"2-digit\"", body)
        self.assertNotIn("second:", body)
        self.assertIn("formatWarmActivity(warmStatus.last_sent_timestamp, warmStatus.last_sent_email)", source)
        self.assertIn("formatWarmActivity(lane.last_sent_timestamp)", source)
        self.assertIn('href="mailto:${escapeHtml(lane.last_sent_email)}"', source)
        self.assertIn('formatWarmActivity(event.timestamp || "")', source)

    def test_private_email_total_explains_cold_and_warm_composition(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        self.assertIn("function privateEmailSentBreakdown", source)
        self.assertIn("const warm = Number(warmStatus.sent_count", source)
        self.assertIn("return { cold, warm, total: cold + warm }", source)
        self.assertIn("Private Email total:", source)
        self.assertIn("JC cold:", source)
        self.assertIn("Warm JC:", source)
        self.assertIn("#ops-view .summary-private-breakdown", styles)

    def test_lead_ops_density_polish_applies_to_warm_and_cold_layouts(self) -> None:
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for selector in [
            "#leads-view .leads-command-center",
            "#leads-view .leads-control-bar",
            "#leads-view .leads-command-main",
            "#leads-view .leads-command-section",
            "#leads-view.warm-research-mode .leads-control-bar",
            "#leads-view.warm-research-mode .current-run-card",
        ]:
            self.assertIn(selector, styles)
        self.assertIn("grid-template-rows: auto auto auto", styles)
        self.assertIn("align-content: start", styles)
        self.assertIn("height: auto", styles)

    def test_warm_source_stack_and_timeline_are_compact_and_top_aligned(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for expected in [
            "#leads-view.warm-research-mode .leads-control-source",
            "#leads-view.warm-research-mode .leads-control-results",
            "#leads-view.warm-research-mode .leads-control-actions",
            "#leads-view.warm-research-mode .warm-timeline-list",
            "max-height: 176px",
            "overflow-y: auto",
            "align-content: start",
            "grid-row: 1 / span 3",
        ]:
            self.assertIn(expected, styles)
        self.assertLess(styles.rfind("grid-row: 1;"), styles.rfind("grid-row: 2;"))
        self.assertLess(styles.rfind("grid-row: 2;"), styles.rfind("grid-row: 3;"))
        self.assertIn("warmTimeline.map((event)", source)
        self.assertIn("event.type", source)
        self.assertIn('formatWarmActivity(event.timestamp || "")', source)
        self.assertNotIn("${escapeHtml(event.timestamp || \"\")}", source)

    def test_warm_complete_summary_is_compact_and_human_readable(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")

        self.assertIn("Current Warm Outreach · Ready for review", source)
        self.assertIn("Previous Warm Outreach Run", source)
        self.assertIn("Historical / live lane", source)
        self.assertIn("warm-status-summary", source)
        self.assertIn("formatWarmActivity(lane.last_sent_timestamp)", source)
        self.assertIn('href="mailto:${escapeHtml(lane.last_sent_email)}"', source)

    def test_header_status_is_compact_and_overflow_safe(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        self.assertIn('els.wsLabel.textContent = "Live status"', source)
        self.assertIn('els.wsLabel.textContent = "Connected"', source)
        self.assertNotIn("Leads local snapshot loaded", source)
        self.assertIn('setNodeText(els.toolbarGeneratedAt, "Local snapshot")', source)
        self.assertIn(".app-shell > .app-rail #ws-label", styles)
        self.assertIn("text-overflow: ellipsis", styles)
        self.assertIn("white-space: nowrap", styles)


if __name__ == "__main__":
    unittest.main()
