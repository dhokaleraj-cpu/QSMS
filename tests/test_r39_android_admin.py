"""R39: Android app - STAWN Developer Console, trial-data purge, Licence & Company, shell branding, Employee Master R38
parity and Users & Access link checks (static checks of the Java sources)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_new_files_exist():
    for name in ("DevConsoleScreen.java", "DevPurgeScreen.java", "LicBrand.java", "LicCompanyScreen.java", "LicProfile.java",
                 "LicService.java", "EmpDetailsScreen.java", "EmpLinks.java"):
        assert (SRC / name).exists(), name


def test_catalogue_registers_licence_and_developer_console_developer_only():
    cat = read("CatAdmin.java")
    assert '"licence_company"' in cat and "LicCompanyScreen::new" in cat
    assert "Catalog.DEVELOPER_CONSOLE" in cat and "DevConsoleScreen::new" in cat
    catalog = read("Catalog.java")
    assert 'DEVELOPER_CONSOLE = "stawn_developer"' in catalog
    assert "LicService.isDeveloper()" in catalog and "!listed(m)" in catalog
    more = read("MoreScreen.java")
    assert "new LicCompanyScreen(a)" in more and "if (LicService.isDeveloper())" in more and "new DevConsoleScreen(a)" in more
    lic = read("Licence.java")
    assert "new LicCompanyScreen(a)" in lic and "new DevConsoleScreen(a)" in lic
    assert '"licence-company"' not in lic and '"stawn-developer"' not in lic


def test_developer_console_uses_web_rpcs_and_checks_developer():
    svc = read("LicService.java")
    for rpc in ("qcms_dev_licence_overview", "qcms_dev_issue_licence", "qcms_dev_update_licence", "qcms_dev_create_company",
                "qcms_dev_assign_profile", "qcms_validate_licence", "qcms_company_profiles"):
        assert rpc in svc, rpc
    assert 'LOGIN_COVER_BUCKET = "qcms-public"' in svc and 'LOGIN_COVER_PREFIX = "login/cover"' in svc
    assert "/company_profile/company_logo." in svc
    dev = read("DevConsoleScreen.java")
    assert 'optBoolean("is_stawn_developer", false)' in dev
    for status in ('"SUSPENDED"', '"REVOKED"', '"ACTIVE"'):
        assert status in dev
    assert "ClipData.newPlainText" in dev and "Copy licence key" in dev
    assert "new DevPurgeScreen(a)" in dev and "uploadLoginCover" in dev and "resetLoginCover" in dev
    assert "LicProfile.section(" in dev


def test_purge_matches_web_service():
    purge = read("DevPurgeScreen.java")
    assert 'CONFIRM_PHRASE = "DELETE TRIAL DATA"' in purge
    assert "qcms_dev_purge_preview" in purge and "qcms_dev_purge_execute" in purge and "qcms_purge_runs" in purge
    assert '"p_include_rows"' in purge and '"p_confirm"' in purge and '"p_reason"' in purge
    assert "api.verifyPassword(password)" in purge and "reason.trim().length() < 5" in purge
    assert 'is_stawn_developer' in purge and "isRootTable(table)" in purge
    assert "ExportKit.xlsx(" in purge and "removeFrom(Api.BUCKET" in purge
    from core import dev_purge_service as web
    block = purge.split("MODULES = {")[1].split("};")[0]
    tables = set(re.findall(r'\{"[^"]+", "([a-z_]+)", "[a-z_]+", "[a-z_]*"', block))
    assert tables == set(web.ROOT_TABLES)
    for master in ("employees", "parts", "parties", "profiles"):
        assert f'"{master}", "' not in purge.split("MODULES = {")[1].split("};")[0]


def test_shell_company_logo_avatar_cover_and_version_only_in_user_details():
    main = read("MainActivity.java")
    assert "companyLogoView" in main and "avatarPhoto" in main and "void refreshBrand()" in main
    assert "LicBrand.loginCover(this)" in main and "LicBrand.clear(this)" in main
    assert "bell()" in main and 'barButton("⇩")' in main
    assert "VERSION_NAME" not in main.split("void showLogin")[1].split("void hideKeyboard")[0]
    assert "VERSION_NAME" not in read("MoreScreen.java")
    assert "VERSION_NAME" not in read("Licence.java").split("static View blockingView")[1].split("private static void aboutDialog")[0]
    acc = read("GenAccountScreen.java")
    assert "BuildConfig.VERSION_NAME" in acc and "LicBrand.userPhoto" in acc
    brand = read("LicBrand.java")
    assert "qcms_company_profiles?select=logo_path" in brand and "photo_storage_path" in brand
    assert "LicService.loginCoverBytes()" in brand and "getCacheDir()" in brand


def test_employee_photo_and_reporting_details():
    people = read("MstPeople.java")
    assert '"/employees/" + employeeId + "/photo_" + employeeId + "."' in people
    assert "PHOTO_MAX_BYTES = 3 * 1024 * 1024" in people and '"photo_storage_path", path' in people
    det = read("EmpDetailsScreen.java")
    assert "qcms_module_approval_routes" in det and "qcms_notification_schedules" in det
    assert "ESCALATION_MAX_LEVELS = 4" in det and "reports_to_employee_id" in det
    assert "Direct reports" in det and "MstPeople.uploadPhoto" in det
    assert "new EmpDetailsScreen(a, " in read("CatMasters.java")


def test_users_access_link_checks():
    links = read("EmpLinks.java")
    assert "is already linked to another QCMS login" in links and "Email mismatch" in links
    assert "No QCMS login" in links
    ua = read("AdmUsersScreen.java")
    assert "Create login for an Employee without login" in ua and "EmpLinks.linkProblem" in ua and "EmpLinks.linkCheckRows" in ua
    assert '"create_user"' in ua and '"update_user"' in ua


def test_no_service_role_or_secrets():
    for name in ("DevConsoleScreen.java", "DevPurgeScreen.java", "LicBrand.java", "LicService.java", "EmpDetailsScreen.java", "EmpLinks.java"):
        text = read(name)
        assert "service_role" not in text and "WHATSAPP_TOKEN\"" not in text, name


def test_department_first_in_queued_mail_subjects():
    """Web R38 notification_service.department_subject ported to SndMail and used where the app queues event mails."""
    mail = read("SndMail.java")
    assert "static String departmentSubject(String subject, String department, String eventKey)" in mail
    assert "static String departmentLabel(String value)" in mail and "static String eventDepartment(String eventKey)" in mail
    from core import notification_service as web
    block = mail.split("DEPARTMENT_LABELS = {")[1].split("};")[0]
    assert dict(re.findall(r'\{"([a-z]+)", "([^"]+)"\}', block)) == web.DEPARTMENT_LABELS
    events = mail.split("EVENT_DEPARTMENTS = {")[1].split("};")[0]
    assert tuple(re.findall(r'\{"([A-Z_]+)", "([^"]+)"\}', events)) == web.EVENT_DEPARTMENTS
    adm = read("AdmMail.java")
    assert adm.count("SndMail.departmentSubject(") >= 2
    assert "SndMail.departmentSubject(subject" in read("SndPoSend.java")
