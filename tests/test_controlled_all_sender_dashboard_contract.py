from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "web_dashboard/index.html"
APP = ROOT / "web_dashboard/app.js"
BACKEND = ROOT / "live_dashboard.py"


def test_all_sender_control_is_present_and_isolated():
    index = INDEX.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    backend = BACKEND.read_text(encoding="utf-8")

    assert 'id="controlled-send-test-all-btn"' in index
    assert "Send All 6 Controlled Tests" in index
    assert "All 6 sender test" in index
    assert (
        "Recipient: astraproductionsbyjc+allsendersv1@gmail.com"
        in index
    )
    assert (
        "JC · Annette · Jordan · Jodi · Alison · Fiorela"
        in index
    )

    assert '"/api/controlled-test/all"' in app
    assert "runControlledAllSenderTest" in app
    assert "exactly SIX real validation emails" in app

    assert '@app.get("/api/controlled-test/all")' in backend
    assert '@app.post("/api/controlled-test/all")' in backend
    assert "execute_controlled_all_sender_test" in backend


def test_all_sender_ui_never_starts_production_workers():
    app = APP.read_text(encoding="utf-8")

    start = app.index(
        "async function runControlledAllSenderTest()"
    )

    end = app.index(
        "async function postAction(path, options = {})",
        start,
    )

    segment = app[start:end]

    assert "/api/start/" not in segment
    assert "/api/start-ready" not in segment
    assert "send_shard.py" not in segment
