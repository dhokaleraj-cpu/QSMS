from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = "4143-PART-GRADES-LEADTIME-OPENING-STOCK-PASSWORD-EDIT-O365"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_identity_and_v4142_regression_marker():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10"}
    for path in ("streamlit_app.py", "core/auth.py", "core/ui.py"):
        text = read(path)
        assert BUILD in text
        assert "4142-PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY" in text


def test_part_description_can_repeat_but_identity_cannot():
    part = read("app_pages/part_master.py")
    masters = read("core/master_service.py")
    assert "Duplicate Part Number is not allowed." in part
    assert "Duplicate FSI Part Number is not allowed." in part
    assert "Duplicate Part Description" not in part
    assert '"parts": ("fsi_part_number",)' in masters
    assert "_fuzzy_word_duplicate" in masters
    identity = masters.split("_IDENTITY_DUPLICATE_FIELDS", 1)[1].split("}", 1)[0]
    assert "part_name" not in identity


def test_multiple_grades_sections_and_supplier_lead_time():
    sql = read("supabase/migrations/20260826110000_qcms_part_supply_auth_opening_stock_v4143.sql")
    part = read("app_pages/part_master.py")
    assert "part_material_grade_links" in sql
    assert "material_grade_id" in sql
    assert "lead_time_days" in sql
    assert "drop constraint if exists part_raw_material_details_tenant_id_part_id_supplier_id_key" in sql
    assert "Approved / Alternate Material Grades" in part
    assert "Raw Material Section" in part
    assert "Lead Time (Days)" in part


def test_part_master_data_editors_are_batched_in_forms():
    part = read("app_pages/part_master.py")
    for token in (
        'with st.form(f"osp_metlab_requirements_form_',
        'with st.form(f"metallurgical_requirements_form_',
        'with st.form(f"raw_material_grid_form_',
        'with st.form(f"rm_technical_form_',
        'with st.form(f"price_history_form_',
        'with st.form(f"jominy_grid_form_',
    ):
        assert token in part


def test_opening_stock_stage_control_and_osp_genealogy():
    sql = read("supabase/migrations/20260826110000_qcms_part_supply_auth_opening_stock_v4143.sql")
    supply = read("app_pages/supply_chain.py")
    service = read("core/supply_chain_service.py")
    osp = read("core/osp_service.py")
    app = read("streamlit_app.py")
    assert "supply_opening_stock" in sql
    assert "FINISHED_GOODS" in sql and "OSP_READY" in sql
    assert "qsms_create_osp_dispatch_from_opening_stock" in sql
    assert "render_opening_stock" in supply
    assert 'stage": "FINISHED_GOODS"' in service
    assert "qsms_create_osp_dispatch_from_opening_stock" in osp
    assert "supply-opening-stock" in app


def test_customer_order_attachment_and_po_lead_time_default():
    supply = read("app_pages/supply_chain.py")
    attach_sql = read("supabase/migrations/20260826110000_qcms_part_supply_auth_opening_stock_v4143.sql")
    assert 'entity_type="SUPPLY_CUSTOMER_ORDER"' in supply
    assert "SUPPLY_CUSTOMER_ORDER" in attach_sql
    assert "lead_time_days" in supply
    assert "Delivery default calculated from Part Master supplier lead time" in supply
    assert 'section_bar,' in supply  # v4.14.2 screenshot NameError must stay fixed.


def test_functional_departments_and_roles():
    employee = read("app_pages/employee_master.py")
    users = read("app_pages/user_access.py")
    access = read("core/access.py")
    sql = read("supabase/migrations/20260826110000_qcms_part_supply_auth_opening_stock_v4143.sql")
    for department in ("Supply Chain", "Management", "Business Development", "Procurement"):
        assert department in employee
    for role in ("SUPPLY_CHAIN", "MANAGEMENT", "BUSINESS_DEVELOPMENT", "PROCUREMENT"):
        assert role in users and role in access and role in sql


def test_password_controlled_amendments_and_self_service_passwords():
    helper = read("core/password_edit.py")
    auth = read("core/auth.py")
    account = read("app_pages/my_account.py")
    for page in ("app_pages/rmtc_pages.py", "app_pages/metlab_report.py", "app_pages/dimensional_report.py"):
        assert "password_reopen_for_edit" in read(page)
    assert "Administrator access is not required" in helper
    assert "verify_current_password" in helper
    assert "qcms_password_edit_audit" in helper
    assert "request_password_reset" in auth and "Forgot Password?" in auth
    assert "Change My Login Password" in account


def test_smtp_secret_is_never_embedded_in_source_or_migration():
    # Credentials are applied server-side after release verification and must not be packaged.
    forbidden_literal = "Rajesh" + "@2011"
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".py", ".sql", ".md", ".toml", ".json", ".ts", ".command", ".txt"}:
            assert forbidden_literal not in path.read_text(encoding="utf-8", errors="ignore")
