from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = (ROOT / "live_dashboard.py").read_text(encoding="utf-8")
APP = (ROOT / "web_dashboard" / "app.js").read_text(encoding="utf-8")


def test_patch8a2_backend_route_plumbing_contract():
    assert 'recontact_route: str = ""' in LIVE
    assert 'requested_recontact_route = str(' in LIVE
    assert 'recontact_route=requested_recontact_route or None' in LIVE
    assert '"recontact_route": requested_recontact_route or None' in LIVE
    assert 'def _validate_dashboard_recontact_route(' in LIVE
    assert '"Recontact route is missing or mismatched. Re-run Preview Dispatch."' in LIVE
    assert '"recontact_route": str(recontact_route or "").strip()' in LIVE
    assert 'recontact_route=(str(job.get("recontact_route") or "").strip() or None)' in LIVE
    assert 'recontact_route=requested_recontact_route,' in LIVE


def test_patch8a2_frontend_route_identity_and_payload_contract():
    assert 'let selectedRecontactRoute = "sendgrid";' in APP
    assert 'const invalidatedRecontactPreviewIds = new Set();' in APP
    assert 'function normalFullRecontactSelectionActive(' in APP
    assert 'if (normalFullRecontactSelectionActive(source)) key.push(selectedRecontactRoute);' in APP
    assert 'if (preview.full_recontact_sendgrid_only === true)' in APP
    assert 'const route = normalizeRecontactRoute(preview.recontact_route);' in APP
    assert 'if (!route) return "";' in APP
    assert '? { recontact_route: selectedRecontactRoute }' in APP
    assert 'invalidatedRecontactPreviewIds.has(preview.preview_id)' in APP
    assert 'Route changed to ${recontactRouteLabel()} — Preview Dispatch required.' in APP


def test_patch8a2_recontact_selector_is_two_route_only():
    import re

    match = re.search(
        r'<select data-recontact-route[^>]*>(.*?)</select>',
        APP,
        re.S,
    )
    assert match is not None
    selector = match.group(1)

    assert selector.count('>SendGrid Cold</option>') == 1
    assert selector.count('>Private JC Cold</option>') == 1
    assert '>Both — Split</option>' not in selector

    option_values = re.findall(r'<option value="([^"]+)"', selector)
    assert option_values == ["sendgrid", "private_jc"]

def test_patch8a2_controlled_test_hidden_only_from_main_sender_table():
    assert 'profile["controlled_test"] = bool(' in LIVE
    assert 'PROFILES.get(profile_name, {}).get("controlled_test")' in LIVE
    assert '!profile?.controlled_test' in APP
    assert 'controlledSendTestBtn' in APP
    assert 'controlledSendTestJcBtn' in APP
    assert 'controlledSendTestAllBtn' in APP
    assert 'Send All 6 Controlled Tests' in APP
