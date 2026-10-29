"""R40 (Android): public RMTC QR (no login) + "RMTC QR Codes" module below the RMTC modules."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"
PUBLIC = "https://xxrxopzxzyjnzumrwuwy.supabase.co/functions/v1/qcms-rmtc-certificate"


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_public_url_constant_and_links():
    pub = read("IncQrPublic.java")
    assert '"https://xxrxopzxzyjnzumrwuwy.supabase.co"' in pub and '"qcms-rmtc-certificate"' in pub
    assert 'PROJECT_URL + "/functions/v1/" + FUNCTION_SLUG' in pub
    assert 'PUBLIC_BASE + "?t=" + token' in pub
    assert '"&f=zip"' in pub and '"&f=pdf"' in pub and '"&d="' in pub
    built = "https://xxrxopzxzyjnzumrwuwy.supabase.co" + "/functions/v1/" + "qcms-rmtc-certificate"
    assert built == PUBLIC


def test_secure_random_32_char_token():
    pub = read("IncQrPublic.java")
    assert "import java.security.SecureRandom;" in pub and "new SecureRandom()" in pub
    assert "TOKEN_LENGTH = 32" in pub
    alphabet = re.search(r'ALPHABET = "([^"]+)"', pub).group(1)
    assert sorted(alphabet) == sorted("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
    assert '[A-Za-z0-9]{32}' in pub
    assert "java.util.Random" not in pub and "Math.random" not in pub


def test_token_row_insert_and_certificate():
    pub = read("IncQrPublic.java")
    assert 'TABLE = "rmtc_qr_tokens"' in pub
    assert "api.insert(TABLE, row)" in pub
    assert '"&revoked=eq.false' in pub and "rmtc_approval_id=eq." in pub
    # tenant is filled by the column default (not sent by the client)
    insert_block = pub[pub.index("static JSONObject ensureToken"):pub.index("api.insert(TABLE, row)")]
    assert '"tenant_id"' not in insert_block
    assert 'CERT_FOLDER = "rmtc_certificates"' in pub
    assert 'tenant + "/" + CERT_FOLDER + "/" + Lookups.j(r, "id") + "/" + certificateName(r)' in pub
    assert '"RMTC_" + IncQrLabel.safeToken(Lookups.j(r, "rmtc_number")) + ".pdf"' in pub
    assert 'api.upload(path, certificatePdf(' in pub
    assert '.put("certificate_path", path).put("certificate_refreshed_at", now)' in pub
    assert "RptPdf.render(RptReports.rmtc(api, rid))" in pub
    # revoke = mark revoked + new code
    assert '.put("revoked", true).put("revoked_at", now)' in pub


def test_certificate_print_has_no_customer_fields():
    rpt = read("RptReports.java")
    start = rpt.index("static RptDoc rmtc(Api api, String id)")
    end = rpt.index("static final String QCMS_WEBSITE")
    body = rpt[start:end].lower()
    for word in ("customer", "customer_po", "customer_part", "delivery_date"):
        assert word not in body, word


def test_label_email_and_print_use_public_url():
    label = read("IncQrLabel.java")
    assert "IncQrPublic.ensure(api, r)" in label
    assert "Open / download all RMTC documents: " in label
    assert "new IncQrScreen.Detail(a, rid)" in label
    rpt = read("RptReports.java")
    assert "IncQrPublic.activeUrl(api, id)" in rpt
    decide = read("IncRmtcDecide.java")
    assert "IncQrLabel.onApproved(api, rid, true)" in decide
    # website link only as the fallback when the token cannot be created
    pub = read("IncQrPublic.java")
    assert "l.url = websiteUrl(r);" in pub and "could not be created" in pub


def test_module_registered_directly_below_rmtc():
    cat = read("CatIncoming.java")
    keys = re.findall(r'new Module\("([a-z0-9_]+)"', cat)
    assert keys.index("rmtc_qr") == keys.index("rmtc") + 1
    assert '"RMTC QR Codes"' in cat and "IncQrScreen::new" in cat
    assert '{"rmtc-qr", "rmtc_qr"}' in read("Notif.java")


def test_screen_features_and_permissions():
    scr = read("IncQrScreen.java")
    assert "class IncQrScreen extends Screen" in scr and "static final class Detail extends Screen" in scr
    assert 'AdmPerm.current(api, MODULE_KEY, "can_view")' in scr
    assert '"can_edit"' in scr and '"can_approve"' in scr
    assert "IncQrPublic.bulkCreate(api)" in scr and "IncQrPublic.revoke(api, rec)" in scr and "IncQrPublic.refreshCertificate(api, rec)" in scr
    assert "IncQrPublic.zipUrl(s.token)" in scr and "IncQrPublic.pdfUrl(s.token)" in scr
    assert "a.openInBrowser(" in scr and "openWeb(" not in scr
    assert "ClipboardManager" in scr and "Intent.ACTION_SEND" in scr
    assert "_QR_Label.pdf" in scr and "_QR.png" in scr and "_QR.jpg" in scr
    for field in ("rmtc_number", "heat_number", "grade", "sup"):
        assert field in scr
    docs = read("IncQrPublic.java")
    assert 'document_type=neq." + IncQrLabel.DOCUMENT_TYPE' in docs and "status=eq.ACTIVE" in docs


def test_no_secrets():
    for name in ("IncQrPublic.java", "IncQrScreen.java", "IncQrLabel.java"):
        text = read(name)
        assert "service_role" not in text and "SERVICE_ROLE" not in text, name
