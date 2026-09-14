from pathlib import Path
from streamlit.testing.v1 import AppTest
import pytest

@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    return AppTest.from_file(str(Path(__file__).parents[1] / "streamlit_app.py"), default_timeout=30).run()

def element(collection, label):
    return next(item for item in collection if item.label == label)

def test_all_pages_render_without_exceptions(app):
    assert not app.exception
    for page in ("Log activity", "Tank board", "Records", "Data checks", "Administration", "Guide"):
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page

def test_packaged_output_is_persisted_and_visible(app):
    app.sidebar.radio[0].set_value("Log activity").run()
    element(app.selectbox, "Activity").set_value("Packaged output").run()
    element(app.text_input, "Entered by").set_value("Test operator")
    element(app.text_input, "Packaging reference").set_value("UI-P1")
    element(app.number_input, "Actual packaged volume (hL)").set_value(75.0)
    element(app.button, "Save record").click().run()
    assert not app.exception
    assert any("Record saved:" in s.value for s in app.success)
    app.sidebar.radio[0].set_value("Records").run()
    assert any("UI-P1" in str(v) for table in app.dataframe for v in table.value.get("Details", []))

def test_live_mode_blocks_missing_database(monkeypatch):
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("APP_PASSWORD", "test-only-password-16-plus")
    app = AppTest.from_file(str(Path(__file__).parents[1] / "streamlit_app.py")).run()
    element(app.text_input, "Application password").set_value("test-only-password-16-plus")
    element(app.button, "Sign in").click().run()
    assert any("Awaiting live setup" in x.value for x in app.error)
    assert not app.exception

def test_material_batch_form_preserves_factors(app):
    app.sidebar.radio[0].set_value("Log activity").run()
    element(app.selectbox, "Activity").set_value("Material batch").run()
    element(app.selectbox, "Material").set_value("Sugar").run()
    element(app.text_input, "Entered by").set_value("Test operator")
    element(app.text_input, "Batch ID").set_value("UI-SUGAR")
    element(app.button, "Save record").click().run()
    assert not app.exception
    assert any("Record saved:" in s.value for s in app.success)
