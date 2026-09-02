from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_release_identity_and_publishable_verifier():
    assert text("VERSION").strip() in {"4.14.22", "4.14.23", "4.14.24"}
    assert any(b in text("streamlit_app.py") for b in ("41422-PUBLIC-VERIFY-BLANK-MASTER-RMTC-RESET", "41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE", "41424-PO-TECH-GRID-LIVE-IMPORT-APQP-DATE"))
    guard = text("scripts/qcms_remote_schema_guard.py")
    assert "DEFAULT_PUBLISHABLE_KEY" in guard
    assert "qcms_release_contract_v41422" in guard
    assert "QCMS_V41422_FULL_READY" in guard
    assert "--public-only" in guard

def test_master_data_centre_new_record_requests_blank_state():
    ui = text("core/ui.py")
    assert "consume_master_blank_request" in ui
    assert 'st.session_state["_qcms_master_blank_request"] = entry_path' in ui
    assert 'st.button("New Record"' in ui
    for path in (
        "app_pages/part_master.py", "app_pages/material_grade.py", "app_pages/employee_master.py",
        "app_pages/reference_master.py", "app_pages/process_master.py", "app_pages/company_branch.py",
        "app_pages/standards_bank.py", "app_pages/inspection_layouts.py",
    ):
        assert "consume_master_blank_request" in text(path), path

def test_same_heat_rmtc_hard_resets_old_certificate_widgets():
    page = text("app_pages/rmtc_pages.py")
    assert "Add New RMTC for This Heat Number" in page
    assert "rmtc_new_form_nonce" in page
    assert "for key in list(st.session_state)" in page
    assert "rmtc_cert_ref_" in page and "rmtc_parts_" in page and "rmtc_qty_" in page
    assert "New RMTC / TC Certified Quantity (kg)" in page
    assert "on_click=_start_new_rmtc_for_heat" in page

def test_transaction_delete_router_is_preserved():
    delete_service = text("core/delete_service.py")
    assert "TRANSACTION_DELETE_TABLES" in delete_service
    assert 'repo.rpc("qcms_delete_transaction_row"' in delete_service
    assert 'repo.rpc("qsms_delete_master_row"' in delete_service


def test_v41422_release_contract_is_independent_of_old_version_marker():
    migration = text("supabase/migrations/20260902010000_qcms_v41422_public_verify_blank_master.sql")
    assert "qcms_release_contract_v41421" not in migration
    for signature in (
        "qcms_update_osp_material_out(uuid,date,text,numeric,date,text)",
        "qcms_clear_osp_sample(uuid)",
        "qcms_update_osp_receipt(uuid,date,text,text,date,text,date,text,numeric,text)",
        "qcms_delete_osp_transaction(uuid)",
        "qcms_delete_osp_receipt(uuid)",
        "qcms_delete_transaction_row(text,uuid)",
    ):
        assert signature in migration
