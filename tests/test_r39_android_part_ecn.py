"""R39: Android app - Part Processes & Drawings, ECN / PCN (FSI/806/F05), ECN register and Part "Sections applicable"
parity with the R38 website (static checks of the Java sources against core/part_process_service.py / core/ecn_service.py)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"
FILES = ("EcnData.java", "EcnFormScreen.java", "EcnScreen.java", "EcnRegisterScreen.java", "EcnActionScreen.java",
         "MstPartProcessScreen.java", "MstPartProcessEditScreen.java", "MstPartProcessDocsScreen.java", "MstPartSections.java",
         "MstPartDrawingsScreen.java")


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_files_exist():
    for name in FILES:
        assert (SRC / name).exists(), name


def test_catalogue_registration():
    cat = read("CatMasters.java")
    for needle in ("new MstPartProcessScreen(a, row)", "new EcnRegisterScreen(a, row.optString(\"id\"))", "new MstPartSections(a, row)",
                   '"part_process_routes", "part_id"'):
        assert needle in cat, needle
    ppap = read("CatPpap.java")
    assert '"ecn_register"' in ppap and "new EcnRegisterScreen(a, null)" in ppap and "new EcnScreen(a," in ppap
    assert "CatPpap.register(list)" in read("Catalog.java")


def test_ecn_screen_uses_own_action_screen_and_tile_type():
    ecn = read("EcnScreen.java")
    assert "List<LinearLayout> t = new ArrayList<>()" in ecn and "PpapHomeScreen.tiles(a, tiles, t)" in ecn
    assert "new EcnActionScreen(a, ecn, r)" in ecn and "new EcnActionScreen(a, ecn, null)" in ecn
    assert "EcnData.email(api, ecn" in ecn


def test_ecn_number_series_and_status_flow_match_web():
    from core import ecn_service as svc
    data = read("EcnData.java")
    assert "qcms_next_ecn_number" in data and '"p_change_type"' in data and '"p_plant_code"' in data and '"p_date"' in data
    for status in svc.ECN_STATUSES:
        assert f'"{status}"' in data, status
    for legacy, new in svc.LEGACY_STATUSES.items():
        assert f'case "{legacy}": return "{new}"' in data
    for current, targets in svc.TRANSITIONS.items():
        for target, perm in targets.items():
            assert f'{{"{target}", "{perm}"}}' in data, (current, target)
    assert svc.FORMAT_NO in data and svc.FORMAT_REV_DATE in data
    for key, _label in svc.SUPPORTING_DOCUMENTS:
        assert f'"{key}"' in data
    for status in svc.ACTION_STATUSES:
        assert f'"{status}"' in data
    assert "qcms_effective_module_permission" in data and '"PART_MASTER"' in data


def test_completed_refused_while_actions_open_and_actions_table():
    data = read("EcnData.java")
    assert '"part_ecn_actions"' in data
    assert "close every implementation action" in data
    act = read("EcnActionScreen.java")
    assert "EcnData.ACTIONS" in act and '"responsible_employee_id"' in act and '"target_date"' in act
    assert "COMPLETED / CANCELLED ECN cannot be changed" in act


def test_ecn_print_two_pages_and_created_mail():
    data = read("EcnData.java")
    assert "d.keep(1000)" in data and "IMPLEMENTATION ACTIONS" in data  # page 2 like core/ecn_pdf.py
    assert '"ECN_CREATED"' in data and '"Quality", "NPD"' in data and "qcms_notification_outbox" in data
    assert "SndMail.dispatch" in data and "RptPdf.render" in data and '"ECN_CREATED:"' in data
    form = read("EcnFormScreen.java")
    assert "EcnData.notifyCreated(api, ecn)" in form and "EcnData.cancel(api" in form


def test_replacement_requires_ecn():
    drawings = read("MstPartDrawingsScreen.java")
    assert "qcms_activate_part_drawing_revision" in drawings
    assert "EcnData.revisionDefaults(part, type, number, cur" in drawings and "new EcnFormScreen(a, d, null, () -> releaseDrawing(" in drawings
    docs = read("MstPartProcessDocsScreen.java")
    assert "qcms_activate_part_process_document_revision" in docs and '"PART_PROCESS"' in docs
    assert '"PROCESS_DRAWING", "PROCESS_SPEC"' in docs and "/process_documents/" in docs
    assert "new EcnFormScreen(a, d, null, () -> releaseRevision(" in docs and "CURRENT" in docs and "OBSOLETE" in docs


def test_part_processes_match_service():
    proc = read("MstPartProcessScreen.java") + read("MstPartProcessEditScreen.java")
    assert '"part_process_routes"' in proc and "npd_process_flow_steps" in proc
    assert "Duplicate Op No." in proc and '"IN_HOUSE", "OSP"' in proc and "OUTSOURCED" in proc
    assert "EcnData.processChangeDefaults(part, before, now)" in proc


def test_sections_registry_matches_web():
    from core import part_process_service as pps
    from core import part_sections as legacy
    sec = read("MstPartSections.java")
    for key, label, group, legacy_key in pps.PART_SECTION_REGISTRY:
        assert f'{{"{key}", "{label}", "{group}", "{legacy_key or ""}"}}' in sec, key
    for key in legacy.SECTION_KEYS:
        assert f'"{key}"' in sec
    for table, key in pps.CHILD_TABLE_SECTION.items():
        assert f'CHILD_TABLE.put("{table}", "{key}")' in sec
    assert '"applicable_sections"' in sec and '"section_applicability"' in sec
    rec = read("RecordScreen.java")
    assert "MstPartSections.showAction(rec, act.label)" in rec and "MstPartSections.showChild(rec, child.table)" in rec


def test_no_secrets_and_no_supplier_data():
    for name in FILES:
        text = read(name)
        assert "service_role" not in text, name
        assert not re.search(r"eyJ[A-Za-z0-9_-]{20,}", text), name
