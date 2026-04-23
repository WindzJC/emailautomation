from __future__ import annotations

from pathlib import Path
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
            "activeSenderSummary",
            "Preflight",
            "leadsImportantDispatchPreviewBtn.disabled = activeDispatch || sourceBlocked || sendersActive",
            "rows_to_add_sendgrid_5",
        ]:
            self.assertIn(expected, source)

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
