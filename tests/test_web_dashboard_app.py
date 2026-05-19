from __future__ import annotations

from pathlib import Path
import re
import unittest


APP_JS = Path(__file__).resolve().parents[1] / "web_dashboard" / "app.js"
INDEX_HTML = Path(__file__).resolve().parents[1] / "web_dashboard" / "index.html"
STYLES_CSS = Path(__file__).resolve().parents[1] / "web_dashboard" / "styles.css"


class WebDashboardAppTests(unittest.TestCase):
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
            "confirmImportantLeadDispatch",
            "dispatchPreviewMatchesCurrentSelection",
            "currentDispatchPlanKey",
            "leadsImportantDispatchCap",
            "/api/leads/dispatch-important/preview",
            "/api/leads/dispatch-important/confirm",
            "Dispatch blocked: stop active senders first",
            "Confirm Dispatch blocked",
            "activeSenderSummary",
            "Preflight",
            "leadsImportantDispatchPreviewBtn.disabled = activeDispatch || sourceBlocked || sendersActive || activeCheck",
            "rows_to_add_sendgrid_5",
        ]:
            self.assertIn(expected, source)

    def test_leads_run_safety_card_reports_wait_blocked_freshness_and_stale_pipeline(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        markup = INDEX_HTML.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        for expected in [
            "leads-run-safety-card",
            "Current Run Safety",
            "WAIT",
        ]:
            self.assertIn(expected, markup)

        for expected in [
            "function leadsRunSafety",
            "lead-funnel-table-wrap",
            "<table class=\"lead-funnel-table\"",
            "<col class=\"lead-funnel-stage-col\"",
            "<col class=\"lead-funnel-value-col\"",
            "<th>Stage</th>",
            "<th>Current live</th>",
            "<th>Next batch</th>",
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
            "Run Preview + Validate",
            "/api/profiles/",
            "/preview-validate",
            "preview-validate-profile-btn",
            "Generating preview and validating",
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
        for expected in [
            "VERIFY_MODE_FAST_TRIAGE",
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
        ]:
            self.assertIn(expected, source)

    def test_dashboard_ops_hierarchy_uses_fleet_summary_and_compact_sender_warnings(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for expected in [
            "total_awaiting_outcome",
            "Critical Alerts",
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
        ]:
            self.assertIn(expected, styles)

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
          "ops-progress-shell",
          "ops-alerts-strip",
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
            "messageWithProfile",
            "blocks_sending",
            "Blocks Start",
            "Non-blocking",
            "alerts-progress-row",
            "Private Email",
            "SendGrid",
            "dispatch-preflight-strip",
            "Dispatch Checklist",
            "Preview Surface",
            "Live queue comparison",
            "quarantine-list-row",
            "quarantine-list-shell",
            "Lead Inspector",
        ]:
            self.assertIn(expected, source)


if __name__ == "__main__":
    unittest.main()
