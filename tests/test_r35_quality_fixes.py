"""R35 · Quality fixes from the user's issue sheet (MetLAB / Bend / OSP / layouts / user links / DB errors)."""
from pathlib import Path

from core.db_errors import db_message, explain_db_error, report_generation_error
from core.osp_service import OSPService

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


# ---------------------------------------------------------------- #3 clear, field-level errors
def test_not_null_error_names_the_field():
    msg = db_message({"message": 'null value in column "prepared_by_employee_id" of relation "lab_tests" violates not-null constraint', "code": "23502"})
    assert "Prepared By" in msg and "required" in msg


def test_unique_error_names_fields_without_tenant():
    raw = "{'message': 'duplicate key value violates unique constraint \"inward_lots_tenant_id_grn_number_part_id_heat_number_key\"', 'code': '23505', 'details': 'Key (tenant_id, grn_number, part_id, heat_number)=(t, 113, p, A42474) already exists.'}"
    msg = db_message(raw)
    assert "GRN Number" in msg and "Heat Number" in msg and "Tenant" not in msg and "113" in msg


def test_rls_and_number_errors_are_plain():
    assert "not allowed" in explain_db_error({"message": 'new row violates row-level security policy for table "lab_tests"', "code": "42501"})
    assert "enter a number" in explain_db_error({"message": 'invalid input syntax for type numeric: "abc"', "code": "22P02"})


def test_previous_behaviour_kept():
    assert db_message("{'message': 'This transaction has downstream linked records.', 'code': 'P0001', 'hint': None, 'details': None}") == "This transaction has downstream linked records."
    assert db_message(ValueError("plain")) == "plain"


def test_report_generation_error_names_step():
    assert "Test Date" in report_generation_error(KeyError("test_date"))
    assert "photograph" in report_generation_error(type("UnidentifiedImageError", (Exception,), {})("cannot identify image file"))


def test_save_and_finalize_blockers_name_each_field():
    from app_pages.metlab_report import finalize_blockers, report_save_blockers
    reasons = report_save_blockers(existing=None, perms={"can_create": True}, prepared="", sample_ref="", case_depth_valid=False, notify_pref={"send": True, "confirmed": False}, plan_id="")
    text = "\n".join(reasons)
    for word in ("Layout", "Prepared By", "Sample / Reference", "Case Depth", "Confirm recipients"):
        assert word in text
    fin = finalize_blockers(existing={"status": "DRAFT"}, perms={"can_approve": True}, disposition="REJECTED", reason="", validator="", approver="")
    assert any("Decision Reason" in r for r in fin) and any("Validated By" in r for r in fin)


# ---------------------------------------------------------------- #2 photos kept, FINAL kept
def test_attachment_upload_reuses_existing_object_path_row():
    src = read("core/attachments.py")
    assert "existing_by_path" in src and "row = existing or self.existing_by_path(object_path)" in src
    svc = read("core/inspection_service.py")
    assert 'find_one("document_attachments", eq={"object_path": path})' in svc


def test_finalize_saves_chosen_photos_and_final_reports_accept_photos():
    met = read("app_pages/metlab_report.py")
    assert met.count("persist_pending_evidence(service") >= 2  # linked + standalone finalize
    assert "final_photo_update(service, existing" in met and "report stays FINAL" in met
    assert "saved_photo_preview(existing, slot)" in met
    osp = read("app_pages/osp_inspections.py")
    assert "persist_pending_evidence(inspection, report_id" in osp and "final_photo_update(inspection, existing" in osp


# ---------------------------------------------------------------- #1 layout readiness in the pending list
def test_metlab_pending_list_shows_layout_readiness():
    met = read("app_pages/metlab_report.py")
    assert "def layout_readiness" in met and '"Layout": (readiness or {})' in met
    assert "Layout check:" in met


def test_layout_readiness_explains_missing_inward_layout():
    from app_pages.metlab_report import layout_readiness
    from core.inspection_service import InspectionService

    svc = InspectionService.__new__(InspectionService)
    final = {"id": "f", "layout_type": "METLAB", "inward_type": "MATERIAL_INWARD", "requirement_scope": "FINAL_METALLURGICAL", "status": "APPROVED"}
    bend = {"id": "b", "layout_type": "METLAB", "inward_type": "MATERIAL_INWARD", "requirement_scope": "GENERAL", "inspection_method": "BEND_TEST", "status": "APPROVED"}
    svc.plans = lambda *a, **k: [final, bend]
    state = layout_readiness(svc, "p")
    assert state.startswith("Missing inward MetLAB layout") and "Bend Test only" in state and "Final Dispatch" in state
    assert layout_readiness(svc, "p", bend=True) == "Ready"
    svc.plans = lambda *a, **k: []
    assert "create & approve" in layout_readiness(svc, "p")


# ---------------------------------------------------------------- #5 New Layout visible
def test_layout_master_has_visible_new_layout_button_and_no_selector_override():
    src = read("app_pages/inspection_layouts.py")
    assert '"＋ New Layout"' in src and '_qcms_master_blank_request"] = page_key' in src
    assert "applied_request" in src
    assert "Create permission for Inspection Layouts" in src
    # records page no longer forces the last viewed layout into the entry page on every render
    records = src[src.index("def render_records"):]
    assert 'st.session_state["edit_inspection_layout_id"] = selected\n        c1, c2, c3' not in records


# ---------------------------------------------------------------- #8 OSP sample receipt → dimensional queue
def test_name_matched_layouts():
    layouts = [{"layout_name": "CASE CARBURIZING 9265"}, {"layout_name": "Nitriding"}]
    assert OSPService.name_matched_layouts(layouts, "Case Carburizing") == [layouts[0]]
    assert OSPService.name_matched_layouts(layouts, "") == []


def test_osp_queue_uses_part_process_layouts():
    src = read("core/osp_service.py")
    assert "part_layouts" in src and "name_matched_layouts(candidates" in src
    page = read("app_pages/osp_inspections.py")
    assert "OSPService.name_matched_layouts" in page


# ---------------------------------------------------------------- #7 user link safeguards
def test_user_link_mismatch_detection():
    from app_pages.user_access import link_check_rows, link_problem

    saket = {"first_name": "Saket", "last_name": "Jha", "email": "qcd11@x.com", "profile_id": None, "status": "ACTIVE"}
    assert "Email mismatch" in link_problem(saket, "scmd9@x.com")
    assert link_problem(saket, "QCD11@x.com") == ""
    komal = {"first_name": "Komal", "email": "mlab@x.com", "profile_id": "p1", "status": "ACTIVE"}
    rows = link_check_rows([komal, saket], [{"id": "p1", "email": "nikhil@x.com"}])
    assert any(r["Issue"].startswith("Email differs") for r in rows)
    assert any(r["Issue"].startswith("No QCMS login") for r in rows)


def test_user_access_prefill_and_activity_limit():
    src = read("app_pages/user_access.py")
    assert "Create login for an Employee without login" in src
    assert "Latest activity rows" in src


# ---------------------------------------------------------------- DB migration
def test_r35_quality_migration_is_additive():
    sql = read("supabase/migrations/20261021100000_qcms_r35_quality_fixes.sql").lower()
    assert "quality_asset_part_process_links" in sql and "set default public.current_tenant_id()" in sql
    assert "alter policy qcms_activity_admin_select" in sql and "(select public.current_app_role())" in sql
    assert "add column if not exists process_name_snapshot" in sql
    for bad in ("drop table", "drop column", "delete from", "truncate"):
        assert bad not in sql
