from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v487_version_release_and_attachment_migration():
    assert (ROOT / "VERSION").read_text().strip() in {"4.8.7", "4.8.8", "4.9.0", "4.9.1", "4.9.2", "4.9.3", "4.9.4", "4.9.5", "4.9.6", "4.9.7", "4.9.8", "4.9.9", "4.10.0", "4.10.1", "4.10.2", "4.10.3", "4.10.4"}
    assert (ROOT / "docs/RELEASE_4_8_7.md").exists()
    sql = (ROOT / "supabase/migrations/20260803090000_qsms_optional_attachments_v487.sql").read_text()
    for token in [
        "qsms_delete_document_attachment",
        "RMTC_ENTRY",
        "MATERIAL_INWARD",
        "qsms_storage_delete",
        "authenticated QSMS session",
    ]:
        assert token in sql


def test_dashboard_removes_master_kpis_and_has_distinct_quick_action_colors():
    text = (ROOT / "app_pages/dashboard.py").read_text()
    for removed in ["Active Parts", '"Customers"', '"Suppliers"', "Steel Mills"]:
        assert removed not in text
    for color in ["#0F4C81", "#7C3AED", "#00897B", "#F59E0B", "#0284C7", "#16A34A", "#C026D3", "#475569"]:
        assert color in text
    ui = (ROOT / "core/ui.py").read_text()
    assert "linear-gradient(135deg" in ui
    assert "--dash-color" in ui


def test_every_top_level_module_has_a_submenu():
    app = (ROOT / "streamlit_app.py").read_text()
    for module in ["Dashboard", "Masters", "RMTC", "Inward", "Inspections", "Records", "Templates"]:
        assert f'"{module}": (' in app
    assert "module_submenu(current_module" in app
    ui = (ROOT / "core/ui.py").read_text()
    assert "def module_submenu" in ui
    assert "fsi_module_subnav" in ui


def test_rmtc_and_inward_support_three_optional_attachments():
    rmtc = (ROOT / "app_pages/rmtc_pages.py").read_text()
    inward = (ROOT / "app_pages/material_inward.py").read_text()
    for token in ["RMTC_COPY", "RMTC_ATTACHMENT_2", "RMTC_ATTACHMENT_3"]:
        assert token in rmtc
    for token in ["INWARD_COPY", "INWARD_ATTACHMENT_2", "INWARD_ATTACHMENT_3"]:
        assert token in inward
    assert "new_attachment_uploaders" in rmtc
    assert "render_attachment_manager" in rmtc
    assert "new_attachment_uploaders" in inward
    assert "render_attachment_manager" in inward


def test_attachment_manager_supports_download_password_replace_and_delete():
    text = (ROOT / "core/attachments.py").read_text()
    for token in [
        "st.download_button",
        "verify_current_password(password)",
        "Replace attachment",
        "Delete attachment",
        "All attachment slots are optional",
        "qsms_delete_document_attachment",
    ]:
        assert token in text


def test_attachment_register_has_module_specific_write_policies():
    sql = (ROOT / "supabase/migrations/20260803091000_qsms_attachment_module_permissions_v487.sql").read_text()
    for token in [
        "qsms_attachment_module",
        "qsms_can_manage_attachment",
        "tenant_insert on public.document_attachments",
        "tenant_update on public.document_attachments",
        "RMTC_ENTRY",
        "MATERIAL_INWARD",
    ]:
        assert token in sql


def test_cloud_dependencies_are_declared_directly():
    requirements = (ROOT / "requirements.txt").read_text().lower()
    assert "plotly" in requirements
    assert "httpx" in requirements
