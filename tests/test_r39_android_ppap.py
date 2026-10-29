"""R39 (agent P): Android PPAP parity with the website - package list / KPIs, create from template linked to APQP / part /
customer, element edit, document revisions + ZIP, send package to the customer, assignment e-mail (RPC + qcms-send-email)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_files_and_registration():
    for name in ("CatPpap.java", "PpapData.java", "PpapHomeScreen.java", "PpapPackageScreen.java", "PpapPackageEditScreen.java",
                 "PpapElementScreen.java", "PpapSend.java"):
        assert (SRC / name).exists(), name
    assert "CatPpap.register(list);" in read("Catalog.java")
    cat = read("CatPpap.java")
    assert 'new Module("ppap", "PPAP Document Manager", Catalog.MORE' in cat and '"ppap_packages"' in cat and ".custom(PpapHomeScreen::new)" in cat
    # APQP project -> PPAP packages (open / create)
    assert "PpapHomeScreen.fromApqp(a, row)" in read("CatMore.java")
    home = read("PpapHomeScreen.java")
    assert "static void tiles(MainActivity a, LinearLayout parent, List<? extends View> tiles)" in home   # used by EcnScreen
    assert "new PpapPackageEditScreen(a, null, projectId)" in home and "PpapData.packagesForApqp(" in home


def test_template_32_elements_and_create_package():
    d = read("PpapData.java")
    assert '{32, "IMDS", true}' in d and '{1, "Supplier Timing", true}' in d
    for needle in ("ppap_customer_template_elements?select=*&customer_id=eq.", "ppap_element_master?select=*&order=element_no.asc",
                   'api.insert("ppap_packages", payload)', 'api.insert("ppap_package_elements", e)', 'e.put("status", required ? "NOT_STARTED" : "NA")',
                   "static JSONObject headerFromApqp(JSONObject project, JSONObject part)"):
        assert needle in d, needle
    edit = read("PpapPackageEditScreen.java")
    assert "PpapData.createPackage(api, payload" in edit and "PpapData.assignmentMail(api, PpapData.s(saved, \"id\"), null, false)" in edit
    for f in ('"apqp_project_id"', '"part_id"', '"customer_id"', '"submission_level"', '"owner_employee_id"'):
        assert f in edit, f


def test_assignment_mail_contract():
    d = read("PpapData.java")
    assert 'api.rpcValue("qcms_ppap_assignment_mail", args)' in d
    for k in ('"p_package_id"', '"p_element_ids"', '"p_resend"', '"p_app_url"'):
        assert k in d, k
    assert "SndMail.dispatch(api, outbox)" in d
    snd = read("SndMail.java")
    assert 'api.invokeFunction("qcms-send-email", new JSONObject().put("outbox_ids", toArray(ids)))' in snd
    # same trigger rule as core/ppap_service.needs_assignment_mail
    assert "static boolean needsAssignmentMail(JSONObject before, JSONObject after)" in d
    el = read("PpapElementScreen.java")
    assert "PpapData.needsAssignmentMail(element, merged)" in el and "PpapData.assignmentMail(api, PpapData.s(pkg, \"id\"), ids, true)" in el
    pkg = read("PpapPackageScreen.java")
    assert "PpapData.needsAssignmentMail(e, values)" in pkg and "Send assignment e-mail again" in pkg
    assert "PpapData.assignmentMail(api, id, elementIds, true)" in pkg


def test_element_edit_and_documents():
    el = read("PpapElementScreen.java")
    for needle in ('Field.lookup("responsible_employee_id"', 'Field.date("due_date"', 'Field.select("status"', '"applicable"', 'Field.area("remarks"',
                   "PpapData.upload(api, pkg, element, file"):
        assert needle in el, needle
    d = read("PpapData.java")
    assert "ppap_element_documents" in d and "static String nextRevision(String current)" in d and "is_latest" in d
    assert "import java.util.zip.ZipOutputStream;" in d and "static byte[] zip(Api api, List<JSONObject> docs, List<JSONObject> elements)" in d
    pkg = read("PpapPackageScreen.java")
    assert "Download all current documents (ZIP)" in pkg and "Download selected documents (ZIP)" in pkg


def test_send_to_customer_rules():
    s = read("PpapSend.java")
    assert "MAX_EMAIL_BYTES = 10L * 1024 * 1024" in s and "MAX_EMAIL_FILES = 18" in s and "SIGNED_LINK_SECONDS = 7 * 24 * 3600" in s
    assert "only documents of this PPAP package can be sent to its customer" in s
    assert "static List<String> foreignRecipients(List<String> addresses, List<JSONObject> parties, String customerId)" in s
    assert "belong(s) to another customer / supplier" in s
    assert 'api.signedUrl(zipPath, SIGNED_LINK_SECONDS)' in s and '"/submissions/"' in s
    assert 'api.insert("qcms_notification_outbox", row)' in s and 'EVENT = "PPAP_PACKAGE_SUBMISSION"' in s
    assert 'api.insert("ppap_customer_submissions", sub)' in s and 'put("status", "SUBMITTED")' in s
    assert "PpapSend.dialog(a, api, pkg, latest(), elements, this::reload)" in read("PpapPackageScreen.java")


def test_no_service_role_in_ppap_sources():
    for path in SRC.glob("Ppap*.java"):
        text = path.read_text(encoding="utf-8").lower()
        assert "service_role" not in text and "service-role" not in text, path.name
