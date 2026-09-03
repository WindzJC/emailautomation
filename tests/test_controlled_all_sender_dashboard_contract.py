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
        'id="controlled-send-test-all-recipient"'
        in index
    )
    assert (
        "astraproductionsbyjc+allsendersv1@gmail.com"
        in index
    )
    assert (
        "JC · Annette · Jordan · Jodi · Alison · Fiorela"
        in index
    )

    assert '"/api/controlled-test/all"' in app
    assert "runControlledAllSenderTest" in app
    assert 'id="controlled-send-test-all-title"' in index
    assert 'id="controlled-send-test-all-status"' in index
    assert "Single Sender Controlled Send Test" in index
    assert "All 6 Sender Controlled Test" in index
    assert "controlledSendTestAllStatus" in app

    single_start = index.index(
        'id="controlled-send-test-title"'
    )
    all_start = index.index(
        'id="controlled-send-test-all-title"'
    )

    single_segment = index[single_start:all_start]
    all_segment = index[all_start:]

    assert 'id="controlled-send-test-profile"' in single_segment
    assert 'id="controlled-send-test-btn"' in single_segment
    assert 'id="controlled-send-test-all-btn"' not in single_segment

    assert 'id="controlled-send-test-all-btn"' in all_segment
    assert 'id="controlled-send-test-profile"' not in all_segment

    function_start = app.index(
        "async function runControlledAllSenderTest()"
    )
    function_end = app.index(
        "async function postAction(path, options = {})",
        function_start,
    )
    all_function = app[function_start:function_end]

    assert "controlledSendTestAllStatus" in all_function
    assert "controlledSendTestStatus" not in all_function
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


def test_jc_only_control_is_present_and_isolated():
    index = INDEX.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    backend = BACKEND.read_text(encoding="utf-8")

    assert 'id="controlled-send-test-jc-title"' in index
    assert "JC Controlled Send Test" in index
    assert 'id="controlled-send-test-jc-btn"' in index
    assert 'id="controlled-send-test-jc-status"' in index
    assert (
        'id="controlled-send-test-jc-recipient"'
        in index
    )

    assert "jc@astraproductions.co" in index
    assert (
        "astraproductionsbyjc+allsendersv1@gmail.com"
        in index
    )
    assert "PrivateEmail SMTP" in index
    assert "LOGO ASTRA bg.png" in index

    assert '"/api/controlled-test/jc"' in app
    assert "runControlledJcSenderTest" in app
    assert "controlledSendTestJcStatus" in app

    jc_start = index.index(
        'id="controlled-send-test-jc-title"'
    )
    all_start = index.index(
        'id="controlled-send-test-all-title"'
    )

    jc_segment = index[jc_start:all_start]

    assert 'id="controlled-send-test-jc-btn"' in jc_segment
    assert 'id="controlled-send-test-all-btn"' not in jc_segment
    assert 'id="controlled-send-test-profile"' not in jc_segment

    function_start = app.index(
        "async function runControlledJcSenderTest()"
    )
    function_end = app.index(
        "function renderControlledAllSendTestStatus(",
        function_start,
    )

    jc_function = app[function_start:function_end]

    assert '"/api/controlled-test/jc"' in jc_function
    assert "/api/controlled-test/all" not in jc_function
    assert "/api/sendgrid/controlled-test" not in jc_function
    assert "/api/start/" not in jc_function
    assert "/api/start-ready" not in jc_function
    assert "exactly ONE real validation email" in jc_function

    assert (
        '@app.post("/api/controlled-test/jc")'
        in backend
    )
    assert (
        'execute_controlled_sender_test,\n'
        '                "private_jc",'
        in backend
    )


def test_jc_only_control_never_starts_production_workers():
    app = APP.read_text(encoding="utf-8")

    start = app.index(
        "async function runControlledJcSenderTest()"
    )
    end = app.index(
        "function renderControlledAllSendTestStatus(",
        start,
    )

    segment = app[start:end]

    assert "/api/start/" not in segment
    assert "/api/start-ready" not in segment
    assert "send_shard.py" not in segment
