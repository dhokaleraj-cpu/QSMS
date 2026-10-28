"""R35 · STAWN QCMS licence & company setup (company admin) and STAWN developer console.

Rights
- STAWN developer (STAWN PRECISION PRIVATE LIMITED login, public.qcms_stawn_developers): every company, issues licence keys,
  creates companies, moves a login into a company as its administrator, suspends / renews licences.
- Company administrator (role ADMIN of that company): own company only – one-time company profile + logo, licence key
  activation / online validation, WhatsApp settings. Never sees other companies or licence keys in full.
- Other users: read-only licence summary (About page).
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core import about
from core import licence_service as lic
from core.auth import current_profile
from core.db_errors import db_message
from core.ui import page_header, portal_table, save_success_popup, section_bar, stage_section

STATUS_TONE = {"ACTIVE": "green", "GRACE": "orange", "EXPIRED": "red", "SUSPENDED": "red", "REVOKED": "red", "INVALID": "red",
               "NONE": "red", "NOT_STARTED": "orange", "UNCHECKED": "gray"}


def _licence_card(status: dict) -> None:
    st_ = str(status.get("status") or "UNCHECKED")
    tone = STATUS_TONE.get(st_, "gray")
    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.markdown(f"**Licence status**  \n:{tone}-badge[{st_}]")
    c2.markdown(f"**Plan**  \n{status.get('plan') or '-'}")
    c3.markdown(f"**Users**  \n{status.get('used_users') or 0} of {status.get('max_users') or '-'} licensed")
    c4.markdown(f"**Valid until**  \n{status.get('expires_on') or 'No expiry'}")
    st.caption(f"{status.get('reason') or ''} · Key {status.get('licence_key_masked') or '-'} · last online check "
               f"{str(status.get('last_validated_at') or 'now')[:16].replace('T', ' ')}")


def _company_setup(profile: dict, status: dict, *, can_edit: bool, tenant_id: str | None = None, letter: str = "B",
                   kp: str = "qcms_lic") -> None:
    company = lic.company_profile(tenant_id)
    done = bool(company.get("setup_complete"))
    note = ("Completed. The company administrator can still correct the details." if done else
            "One-time setup: fill the company details and upload the logo. They are printed on reports and shown in the app.")
    with stage_section(letter, "COMPANY PROFILE & LOGO", note, key=f"{kp}_company"):
        logo = lic.company_logo_bytes(company.get("logo_path"))
        l1, l2 = st.columns([1, 3], gap="small")
        if logo:
            l1.image(logo, width=140, caption="Company logo")
        else:
            l1.info("No logo yet")
        upload = l2.file_uploader("Company logo (PNG / JPG, max 2 MB)", type=["png", "jpg", "jpeg"], disabled=not can_edit,
                                  key=f"{kp}_logo")
        values: dict = {"tenant_id": company.get("tenant_id")}
        cols = st.columns(3, gap="small")
        for i, (field, label) in enumerate(lic.COMPANY_FIELDS):
            default = company.get(field) or (status.get("company_legal_name") if field == "legal_name" else "") or \
                ("India" if field == "country" else "")
            values[field] = cols[i % 3].text_input(label, value=str(default or ""), disabled=not can_edit, key=f"{kp}_cp_{field}_{company.get('tenant_id')}")
        if not can_edit:
            st.caption("Only the company administrator (or STAWN) can change the company profile.")
            return
        b1, b2 = st.columns(2, gap="small")
        save = b1.button("Save draft", width="stretch", key=f"{kp}_cp_save")
        finish = b2.button("Save & complete company setup" if not done else "Save company details", type="primary",
                           width="stretch", key=f"{kp}_cp_finish")
        if save or finish:
            try:
                if upload is not None:
                    values["logo_path"] = lic.upload_company_logo(upload, company.get("tenant_id"))
                    st.session_state.pop("_qcms_r35_logo_cache", None)
                    st.session_state.pop("_qcms_r38_header_company_logo", None)  # R38: refresh the logo in the top ribbon
                lic.save_company_profile(values, complete=bool(finish), profile_id=str(profile.get("id") or "") or None)
                save_success_popup("Company profile saved." + (" Setup complete." if finish else ""), queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))


def _whatsapp_settings(profile: dict, *, can_edit: bool) -> None:
    with stage_section("D", "WHATSAPP AUTO MESSAGES (META WHATSAPP BUSINESS CLOUD API)",
                       "Approval requests and tasks are sent as WhatsApp template messages to users who opted in "
                       "(My Notifications). The access token is a server secret – it is never stored in QCMS tables.",
                       key="qcms_lic_whatsapp"):
        wa = lic.whatsapp_settings()
        c1, c2, c3 = st.columns(3, gap="small")
        enabled = c1.toggle("WhatsApp messages ON", value=bool(wa.get("enabled")), disabled=not can_edit, key="qcms_wa_enabled")
        phone_id = c2.text_input("Phone Number ID", value=str(wa.get("phone_number_id") or ""), disabled=not can_edit, key="qcms_wa_phone_id")
        waba = c3.text_input("WhatsApp Business Account ID", value=str(wa.get("business_account_id") or ""), disabled=not can_edit, key="qcms_wa_waba")
        c4, c5, c6 = st.columns(3, gap="small")
        t_appr = c4.text_input("Approval template", value=str(wa.get("approval_template") or "qcms_approval_request"), disabled=not can_edit, key="qcms_wa_t1")
        t_task = c5.text_input("Task template", value=str(wa.get("task_template") or "qcms_task_alert"), disabled=not can_edit, key="qcms_wa_t2")
        t_upd = c6.text_input("Update template", value=str(wa.get("update_template") or "qcms_update_alert"), disabled=not can_edit, key="qcms_wa_t3")
        c7, c8, c9 = st.columns(3, gap="small")
        lang = c7.text_input("Template language", value=str(wa.get("template_language") or "en"), disabled=not can_edit, key="qcms_wa_lang")
        cc = c8.text_input("Default country code", value=str(wa.get("default_country_code") or "91"), disabled=not can_edit, key="qcms_wa_cc")
        link = c9.text_input("App link in messages", value=str(wa.get("app_link") or "https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app"),
                             disabled=not can_edit, key="qcms_wa_link")
        cats = st.multiselect("Send these on WhatsApp", ["APPROVAL", "TASK", "UPDATE", "ALERT"],
                              default=[c for c in (wa.get("send_categories") or ["APPROVAL", "TASK"]) if c in {"APPROVAL", "TASK", "UPDATE", "ALERT"}],
                              disabled=not can_edit, key="qcms_wa_cats")
        if can_edit and st.button("Save WhatsApp settings", type="primary", key="qcms_wa_save"):
            try:
                lic.save_whatsapp_settings({"enabled": enabled, "phone_number_id": phone_id.strip() or None,
                                            "business_account_id": waba.strip() or None, "approval_template": t_appr.strip(),
                                            "task_template": t_task.strip(), "update_template": t_upd.strip(),
                                            "template_language": lang.strip() or "en", "default_country_code": cc.strip() or "91",
                                            "app_link": link.strip() or None, "send_categories": cats or ["APPROVAL", "TASK"]},
                                           profile_id=str(profile.get("id") or "") or None)
                save_success_popup("WhatsApp settings saved.")
            except Exception as exc:
                st.error(db_message(exc))
        t1, t2 = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        to = t1.text_input("Send a test message to", placeholder="9198XXXXXXXX", key="qcms_wa_test_to")
        if t2.button("Send WhatsApp test", width="stretch", disabled=not can_edit, key="qcms_wa_test"):
            try:
                out = lic.whatsapp_test(to)
                (st.success if out.get("ok") else st.error)(out.get("error") or f"Test sent to {out.get('to')} (message id {out.get('message_id')}).")
            except Exception as exc:
                st.error(db_message(exc))
        with st.expander("How to connect WhatsApp (one time, about 30 minutes)"):
            st.markdown(
                "1. Create a **Meta Business** account and open **developers.facebook.com → My Apps → Create app → Business → WhatsApp**.\n"
                "2. Add and verify the company's WhatsApp number (a number that is **not** used in the normal WhatsApp app).\n"
                "3. Copy the **Phone Number ID** and **WhatsApp Business Account ID** into the fields above.\n"
                "4. In **Business Settings → System users** create a system user, give it the WhatsApp app, and generate a "
                "**permanent access token** with `whatsapp_business_messaging` permission.\n"
                "5. Put the token into Supabase as a secret (Terminal on the Mac):\n"
                "   `supabase secrets set WHATSAPP_TOKEN=<token> --project-ref xxrxopzxzyjnzumrwuwy`\n"
                "6. In **WhatsApp Manager → Message templates** create three *Utility* templates in English named "
                "`qcms_approval_request`, `qcms_task_alert`, `qcms_update_alert`, each with body text using {{1}} name, "
                "{{2}} title, {{3}} details, e.g. *Hello {{1}}, STAWN QCMS: {{2}}. {{3}}*. Wait for Meta approval.\n"
                "7. Switch **WhatsApp messages ON** above, press **Send WhatsApp test**, and ask each user to opt in on "
                "**My Notifications**. Messages are sent every 2 minutes by the `qcms-whatsapp-dispatch` service.\n\n"
                "Meta charges per conversation (utility messages in India cost well under ₹1 each); the first test with "
                "`hello_world` works before your own templates are approved."
            )


def render() -> None:
    page_header("Licence & Company", f"{about.PRODUCT} licence, company profile and logo, WhatsApp settings", "Admin")
    profile = current_profile() or {}
    status = lic.licence_status(force=True)
    is_dev = bool(status.get("is_stawn_developer"))
    is_admin = bool(status.get("is_company_admin")) or str(profile.get("role") or "").upper() == "ADMIN"

    with stage_section("A", f"{about.PRODUCT} LICENCE", f"Licensed by {about.COMPANY}. The key is checked online every time the app starts.",
                       key="qcms_lic_status"):
        _licence_card(status)
        if is_admin or is_dev:
            k1, k2, k3 = st.columns([3, 1, 1], gap="small", vertical_alignment="bottom")
            key = k1.text_input("Licence key from STAWN", placeholder="STAWN-QCMS-XXXXX-XXXXX-XXXXX-XXXXX", key="qcms_lic_key")
            if k2.button("Validate online", width="stretch", key="qcms_lic_validate"):
                try:
                    res = lic.validate_key(key)
                    (st.success if res.get("valid") else st.error)(f"{res.get('status')}: {res.get('reason')}")
                except Exception as exc:
                    st.error(db_message(exc))
            if k3.button("Activate", type="primary", width="stretch", key="qcms_lic_activate"):
                try:
                    res = lic.activate_key(key)
                    if res.get("valid"):
                        save_success_popup(f"Licence activated: {res.get('plan')} · {res.get('max_users')} users.", queue_for_rerun=True)
                        st.rerun()
                    st.error(f"{res.get('status')}: {res.get('reason')}")
                except Exception as exc:
                    st.error(db_message(exc))
        else:
            st.caption("Only the company administrator can enter or change the licence key.")

    _company_setup(profile, status, can_edit=is_admin or is_dev)

    with stage_section("C", "DEVELOPER", key="qcms_lic_dev_info"):
        st.markdown(f"**{about.COMPANY}** · Thane, Maharashtra, India · [{about.EMAIL}](mailto:{about.EMAIL}) · {about.COPYRIGHT}")

    _whatsapp_settings(profile, can_edit=is_admin or is_dev)


# ------------------------------------------------------------------------------------------- STAWN developer console
# ---------------------------------------------------------------------------------------------------------------
# R38 · Login page cover photo (STAWN developer only). Stored in the PUBLIC bucket qcms-public at login/cover.<ext>
# because the Login page is shown before any session exists.
# ---------------------------------------------------------------------------------------------------------------
def _cover_ext(file: object) -> str:
    mime = str(getattr(file, "type", "") or "").lower()
    name = str(getattr(file, "name", "") or "").lower()
    if mime.endswith("png") or name.endswith(".png"):
        return "png"
    if mime.endswith(("jpeg", "jpg")) or name.endswith((".jpg", ".jpeg")):
        return "jpg"
    raise ValueError("Use a JPG or PNG photo for the login cover.")


def upload_login_cover(file: object, client: object | None = None) -> str:
    """Store the cover at qcms-public/login/cover.<ext> (replacing any other format) and return the object path."""
    from core.auth import LOGIN_COVER_BUCKET, LOGIN_COVER_EXTENSIONS, LOGIN_COVER_MAX_BYTES, LOGIN_COVER_PREFIX, clear_login_cover_cache
    from core.database import get_session_client

    data = file.getvalue() if hasattr(file, "getvalue") else b""
    if not data:
        raise ValueError("The selected photo is empty.")
    if len(data) > LOGIN_COVER_MAX_BYTES:
        raise ValueError("Use a cover photo smaller than 5 MB (JPG or PNG).")
    ext = _cover_ext(file)
    client = client or get_session_client()
    if client is None:
        raise RuntimeError("A live QCMS session is required to upload the login cover photo.")
    bucket = client.storage.from_(LOGIN_COVER_BUCKET)
    path = f"{LOGIN_COVER_PREFIX}.{ext}"
    bucket.upload(path, data, {"content-type": "image/png" if ext == "png" else "image/jpeg", "upsert": "true", "cache-control": "60"})
    others = [f"{LOGIN_COVER_PREFIX}.{e}" for e in LOGIN_COVER_EXTENSIONS if e != ext]
    try:
        bucket.remove(others)
    except Exception:
        pass
    clear_login_cover_cache()
    return path


def reset_login_cover(client: object | None = None) -> None:
    """Remove the uploaded cover - the Login page shows the default factory photo again."""
    from core.auth import LOGIN_COVER_BUCKET, LOGIN_COVER_EXTENSIONS, LOGIN_COVER_PREFIX, clear_login_cover_cache
    from core.database import get_session_client

    client = client or get_session_client()
    if client is None:
        raise RuntimeError("A live QCMS session is required.")
    client.storage.from_(LOGIN_COVER_BUCKET).remove([f"{LOGIN_COVER_PREFIX}.{e}" for e in LOGIN_COVER_EXTENSIONS])
    clear_login_cover_cache()


def _login_cover_section() -> None:
    from pathlib import Path

    from core.auth import login_cover_bytes

    with stage_section("H", "LOGIN PAGE COVER PHOTO (STAWN ONLY)",
                       "Add or replace the photo on the left of the Login page (JPG / PNG, max 5 MB, landscape ~ 1600 × 900 px). "
                       "Reset to show the default factory photo again.", key="qcms_dev_login_cover"):
        current = login_cover_bytes()
        default = Path(__file__).resolve().parents[1] / "assets" / "login_factory.jpeg"
        c1, c2 = st.columns([2, 3], gap="medium")
        with c1:
            if current:
                st.image(current, width="stretch", caption="Current login cover (uploaded)")
            elif default.exists():
                st.image(str(default), width="stretch", caption="Current login cover (default factory photo)")
        with c2:
            upload = st.file_uploader("New login cover photo (JPG / PNG, max 5 MB)", type=["jpg", "jpeg", "png"], key="qcms_dev_login_cover_file")
            if upload is not None:
                st.image(upload.getvalue(), width="stretch", caption="Preview of the new cover")
            b1, b2 = st.columns(2, gap="small")
            if b1.button("Save as login cover", type="primary", width="stretch", disabled=upload is None, key="qcms_dev_login_cover_save",
                         icon=":material/upload:"):
                try:
                    upload_login_cover(upload)
                    save_success_popup("Login page cover photo updated. It shows on the Login page within a minute.", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))
            if b2.button("Reset to default photo", width="stretch", disabled=not current, key="qcms_dev_login_cover_reset",
                         icon=":material/restart_alt:"):
                try:
                    reset_login_cover()
                    save_success_popup("Login page cover reset to the default factory photo.", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))


def render_developer() -> None:
    page_header("STAWN Developer Console", "All companies, licences and administrators · STAWN PRECISION PRIVATE LIMITED only", "Admin")
    status = lic.licence_status(force=True)
    if not status.get("is_stawn_developer"):
        st.error("This console is only for the STAWN PRECISION PRIVATE LIMITED developer login.")
        return
    try:
        rows = lic.dev_overview()
    except Exception as exc:
        st.error(db_message(exc))
        rows = []

    with stage_section("A", "LICENSED COMPANIES", key="qcms_dev_overview"):
        if rows:
            frame = pd.DataFrame(rows)
            show = frame[[c for c in ("tenant_code", "company_name", "plan", "evaluated_status", "valid_to", "used_users",
                                      "max_users", "setup_complete", "licence_key", "last_validated_at") if c in frame.columns]]
            portal_table(show.rename(columns={"tenant_code": "Code", "company_name": "Company", "plan": "Plan",
                                              "evaluated_status": "Status", "valid_to": "Valid to", "used_users": "Users",
                                              "max_users": "Licensed users", "setup_complete": "Setup done",
                                              "licence_key": "Licence key", "last_validated_at": "Last online check"}))
        else:
            st.info("No companies yet.")
    companies = {f"{r.get('tenant_code')} · {r.get('company_name')}": r for r in rows}

    with stage_section("B", "ISSUE / RENEW LICENCE KEY", "A new key replaces the company's active key (old key → SUPERSEDED).", key="qcms_dev_issue"):
        if companies:
            pick = st.selectbox("Company", list(companies), key="qcms_dev_issue_company")
            c1, c2, c3 = st.columns(3, gap="small")
            plan = c1.selectbox("Plan", ["STANDARD", "PROFESSIONAL", "ENTERPRISE", "TRIAL"], key="qcms_dev_plan")
            users = c2.number_input("Licensed users", min_value=1, max_value=5000, value=25, step=1, key="qcms_dev_users")
            no_expiry = c3.checkbox("No expiry", value=plan != "TRIAL", key="qcms_dev_noexp")
            valid_to = None if no_expiry else st.date_input("Valid until", value=date.today() + timedelta(days=30 if plan == "TRIAL" else 365),
                                                            key="qcms_dev_validto")
            notes = st.text_input("Notes (order / invoice reference)", key="qcms_dev_notes")
            if st.button("Issue licence key", type="primary", key="qcms_dev_issue_btn"):
                try:
                    out = lic.dev_issue_licence(str(companies[pick]["tenant_id"]), plan, int(users), valid_to, ["ALL"], notes)
                    st.success(f"Licence key issued – send it to the company administrator:\n\n`{out.get('licence_key')}`")
                except Exception as exc:
                    st.error(db_message(exc))
            sel = companies[pick]
            if sel.get("licence_id"):
                st.caption("Change the current licence")
                d1, d2, d3 = st.columns(3, gap="small")
                if d1.button("Suspend", width="stretch", key="qcms_dev_suspend"):
                    try:
                        lic.dev_update_licence(str(sel["licence_id"]), status="SUSPENDED")
                        st.rerun()
                    except Exception as exc:
                        st.error(db_message(exc))
                if d2.button("Re-activate", width="stretch", key="qcms_dev_reactivate"):
                    try:
                        lic.dev_update_licence(str(sel["licence_id"]), status="ACTIVE")
                        st.rerun()
                    except Exception as exc:
                        st.error(db_message(exc))
                if d3.button("Revoke", width="stretch", key="qcms_dev_revoke"):
                    try:
                        lic.dev_update_licence(str(sel["licence_id"]), status="REVOKED")
                        st.rerun()
                    except Exception as exc:
                        st.error(db_message(exc))

    with stage_section("C", "NEW CUSTOMER COMPANY", "Creates the company (tenant). Then issue its licence key and assign its administrator.",
                       key="qcms_dev_newco"):
        c1, c2, c3 = st.columns([1, 2.4, 1], gap="small")
        code = c1.text_input("Company code", placeholder="ABC", key="qcms_dev_newco_code")
        name = c2.text_input("Company name", key="qcms_dev_newco_name")
        plant = c3.text_input("Plant code", key="qcms_dev_newco_plant")
        if st.button("Create company", type="primary", key="qcms_dev_newco_btn"):
            try:
                tid = lic.dev_create_company(code, name, plant)
                save_success_popup(f"Company created ({tid}). Issue its licence key next.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))

    with stage_section("D", "ASSIGN COMPANY ADMINISTRATOR",
                       "Create the person's login first (Admin → Users & Access). This moves that login into the selected company "
                       "as ADMIN; the company admin then completes the company profile and logo once.", key="qcms_dev_assign"):
        if companies:
            c1, c2, c3 = st.columns([2, 2, 1], gap="small", vertical_alignment="bottom")
            email = c1.text_input("Login e-mail", key="qcms_dev_assign_email")
            target = c2.selectbox("Company", list(companies), key="qcms_dev_assign_company")
            role = c3.selectbox("Role", ["ADMIN", "MANAGEMENT", "QUALITY_MANAGER", "QUALITY_ENGINEER", "SUPPLY_CHAIN", "VIEWER"], key="qcms_dev_assign_role")
            if st.button("Assign", type="primary", key="qcms_dev_assign_btn"):
                try:
                    lic.dev_assign_profile(email, str(companies[target]["tenant_id"]), role)
                    save_success_popup(f"{email} is now {role} of {target}.")
                except Exception as exc:
                    st.error(db_message(exc))
    if companies:
        section_bar("COMPANY PROFILE & LOGO OF ANY COMPANY")
        target_co = st.selectbox("Company to edit (STAWN can complete or correct any licensed company's details)", list(companies),
                                 key="qcms_dev_profile_company")
        _company_setup(current_profile() or {}, {"company_legal_name": companies[target_co].get("company_name")}, can_edit=True,
                       tenant_id=str(companies[target_co]["tenant_id"]), letter="E", kp="qcms_dev")

    with stage_section("F", "STAWN QCMS BRANDING (STAWN ONLY)",
                       "The product name, icon and developer details are fixed by STAWN PRECISION PRIVATE LIMITED. Company "
                       "administrators cannot change them; their company name and logo appear under the STAWN QCMS name.",
                       key="qcms_dev_branding"):
        from pathlib import Path
        icon = Path(__file__).resolve().parents[1] / "assets" / "stawn_qcms_icon.png"
        b1, b2 = st.columns([1, 4], gap="small")
        if icon.exists():
            b1.image(str(icon), width=96)
        b2.markdown(f"**App name:** {about.PRODUCT} – {about.TAGLINE}  \n"
                    "**Website:** STAWN icon in the browser tab, address bar and on the left of the top bar  \n"
                    "**Android / iPhone / iPad:** STAWN logo on the left of the top bar  \n"
                    "App versions are shown only in the user details (top right) and on the About page.  \n"
                    f"**Developer:** {about.COMPANY} · {about.EMAIL}")

    _login_cover_section()

    with stage_section("G", "ALL ADMINISTRATION TOOLS", "Every admin right in one place for the STAWN developer login.",
                       key="qcms_dev_admin_tools"):
        pages = st.session_state.get("_qcms_page_by_path") or {}
        tools = (("user-access", "Users & Access", ":material/admin_panel_settings:"),
                 ("licence-company", "Licence, Company & WhatsApp", ":material/verified_user:"),
                 ("system-settings", "System Settings", ":material/tune:"),
                 ("email-settings", "Email Server & Notifications", ":material/forward_to_inbox:"),
                 ("print-designer", "Print Layout Designer", ":material/design_services:"),
                 ("master-import", "Master Import", ":material/upload_file:"),
                 ("employee-records", "Employees", ":material/groups:"),
                 ("deployment-diagnostics", "Deployment Diagnostics", ":material/verified:"),
                 ("records-center", "Records Centre / Delete", ":material/description:"))
        cols = st.columns(3, gap="small")
        for i, (route, label, icon_name) in enumerate(tools):
            if route in pages:
                cols[i % 3].page_link(pages[route], label=label, icon=icon_name, width="stretch")

    from app_pages import dev_purge
    dev_purge.render_section()
    section_bar("STAWN DEVELOPER RIGHTS")
    st.caption("The STAWN developer login keeps ADMIN rights in its home company, is never counted as a licensed user, and can "
               "see and manage every company's licence. Company administrators only manage their own company.")
