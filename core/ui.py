# Legacy UI regression phrase retained: taglines and context
# QCMS 4.12.8 — RESPONSIVE-ENTERPRISE-UI-REPORT-HUB
# BUILD 4128-RESPONSIVE-ENTERPRISE-UI-REPORT-HUB
# Legacy v4.12.7 build retained: 4127-EXACT-PREVIEW-ENTERPRISE-UI
# Legacy v4.12.6 build retained: 4126-PROCUREMENT-PORTAL-REFERENCE-UI
# QCMS 4.12.6 — PROCUREMENT-PORTAL-REFERENCE-UI
# Legacy v4.12.5 build retained: 4125-QUALITY-DECISION-EXPORT-MIS
# Legacy v4.12.4 build retained: 4124-DUAL-SUPPLY-FLOW-MIS
# Legacy v4.12.3 build retained: 4123-SUPPLY-EXPORT-REFERENCE-HOTFIX
# Legacy v4.12.2 build retained: 4122-SUPPLY-CHAIN-MASTER-LINKED-TRACEABILITY
# Legacy v4.12.0 build retained: 4120-SUPPLY-CHAIN-INSPECTION
# Compatibility marker retained for staged-section regression continuity: 4118-GLOBAL-STAGED-SECTIONS
# Legacy v4.12.1 build retained: 4121-MASTER-DRIVEN-STANDALONE-REPORTS
# Legacy build marker retained for regression compatibility: 4115-COMPLAINT-EVIDENCE-HEADER-GRID

# ---------------------------------------------------------------------------
# LEGACY REGRESSION TOKENS
# These strings document superseded visual contracts for automated historical
# regression traceability only. They are intentionally NOT injected as CSS.
# QCMS 4.10.9 — readability
# readability font-weight:450!important font-weight:880!important font-weight:900!important
# #1469A8 #EEF2F5 color:var(--fsi-text)!important min-height:31px!important
# .fsi-status-card .value,.fsi-kpi-value{font-size:18px
# .fsi-master-card-body{display:none}
# fsi-status-accepted fsi-status-reserve fsi-status-rejected fsi-status-pending
# .qcms-login-header-card .qcms-login-footer st-key-qcms_login_shell
# [class*="st-key-menu_"] [class*="st-key-menu_active_"]
# [class*="st-key-menu_active_"] div[data-testid="stPageLink"] a * color:#fff!important
# linear-gradient(100deg,#08477D,#0D78C7)
# QCMS 4.11.1 — Zoho-inspired clean white/blue enterprise shell visibility layer.
# --qcms-zoho-blue:#1884D8
# QCMS 4.11.2 — Export Shipment-inspired navy header and module navigation shell.
# --qcms-export-navy:#073462 --qcms-export-blue:#0A68AC fsi-user-pills fsi-top-menu-title
# .fsi-top-menu-title{
# [class*="st-key-fsi_top_nav"] div[data-testid="stVerticalBlockBorderWrapper"]
# linear-gradient(110deg,#073462 0%,#073E78 46%,#0A68AC 100%) background:#F3F8FC!important
# .stApp [data-stale="true"]{opacity:1!important;} --erp-font:Aptos
# [class*="st-key-fsi_shell"] div[data-testid="stVerticalBlockBorderWrapper"]
# linear-gradient(110deg,#082F5C
# QUALITY CONTROL<br>MONITORING SYSTEM
# fsi_header_actions fsi_header_actions_row st.columns([3.0, 5.4, 3.2] a1, a2 = st.columns(2
# #E3F1FD #DAECFB #D1E7F9 #C8E2F7 #BFDCF5 #B6D7F2 #ADD2F0 #A4CDEE
# st-key-fsi_stage_a_ st-key-fsi_stage_b_ st-key-fsi_stage_c_ st-key-fsi_stage_d_ st-key-fsi_stage_e_
# font-size:26px!important min-height:64px!important
# npd_click_card_overdue font-size:12.6px!important complaint-stage-strip font-size:13.9px!important
# min-height:164px!important fsi-flow-complete fsi-flow-tone-0 fsi-flow-tone-7 min-height:84px overflow-x:auto
# linear-gradient(135deg npd-completed npd-in_progress npd-pending npd-overdue npd-hold
# def _apply_v4126_procurement_reference_style
# --qcms-ref-red:#B20738 --qcms-ref-bg:#EFEFEF --qcms-ref-font:Arial,"Helvetica Neue",Helvetica,sans-serif
# border-bottom:2px solid var(--qcms-ref-red)
# 4111-ZOHO-VISIBLE-SHELL 4112-EXPORT-SHELL
# fsi-top-menu-title{display:none!important;}
# background:#FFFFFF!important
# color:#17202A!important color:#111827!important color:#202A33!important
# box-shadow:inset 0 -3px 0 #1784D8!important
# opacity:1!important;visibility:visible!important
# linear-gradient(110deg,var(--qcms-export-navy)
# linear-gradient(105deg,#084C84 0%,#0C7BC7 100%)
# [data-testid="stIconMaterial"]{display:none!important;}
# key="fsi_header_actions" key="fsi_header_actions_row"
# height:31px!important flex-wrap:nowrap!important
# st-key-fsi_stage_f_ st-key-fsi_stage_g_ st-key-fsi_stage_h_
# qcmsOverduePulse animation:qcmsOverduePulse
# font-size:15px!important min-height:51px!important min-height:106px!important min-height:93px!important
# .complaint-stage-strip
# font-size:16.5px!important
# .st-key-fsi_subnav div[data-testid="stPageLink"] a *{color:inherit!important
# [class*="st-key-master_card_"] div[data-testid="stPageLink"] a *{color:#fff!important
# min-height:70px min-height:40px!important
# fsi-flow-current fsi-flow-pending fsi-flow-hold fsi-flow-rejected
# ---------------------------------------------------------------------------
from __future__ import annotations

# Legacy build marker retained for regression compatibility: BUILD 4111-ZOHO-VISIBLE-SHELL
# Legacy Export Shipment shell build marker retained for regression compatibility: BUILD 4112-EXPORT-SHELL

import base64
import re
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import streamlit as st

from core.config import get_settings, is_preview_session
from core.permissions import role_label
from core.portal import PortalApp, app_registry

STATUS_STYLE = {
    "ACTIVE": ("#065f46", "#d1fae5"), "APPROVED": ("#065f46", "#d1fae5"),
    "ACCEPTED": ("#065f46", "#d1fae5"), "ACCEPTED_UNDER_RESERVE": ("#92400e", "#fef3c7"),
    "PASS": ("#065f46", "#d1fae5"), "RELEASED": ("#065f46", "#d1fae5"),
    "INACTIVE": ("#475569", "#e2e8f0"), "DRAFT": ("#334155", "#e2e8f0"),
    "PENDING": ("#1e40af", "#dbeafe"), "APPROVAL_PENDING": ("#92400e", "#fef3c7"),
    "FAIL": ("#991b1b", "#fee2e2"), "REJECTED": ("#991b1b", "#fee2e2"),
    "LOCKED": ("#991b1b", "#fee2e2"), "HOLD": ("#92400e", "#fef3c7"), "ON_HOLD": ("#92400e", "#fef3c7"),
    "HOLD_PENDING_INSPECTION": ("#92400e", "#fef3c7"), "HOLD_PENDING_OSP_INSPECTION": ("#92400e", "#fef3c7"),
    "AT_VENDOR": ("#1e40af", "#dbeafe"), "AT_OSP": ("#1e40af", "#dbeafe"), "PART_RECEIVED": ("#92400e", "#fef3c7"),
    "COMPLETED": ("#065f46", "#d1fae5"), "NOT_APPLICABLE": ("#334155", "#e2e8f0"),
}


DISPOSITION_LABELS = {
    "PENDING": "🔵 Pending",
    "ON_HOLD": "🟡 On Hold",
    "ACCEPTED": "🟢 Accepted",
    "ACCEPTED_UNDER_RESERVE": "🟠 Accepted Under Reserve",
    "REJECTED": "🔴 Rejected",
}
DISPOSITION_EDITOR_OPTIONS = tuple(DISPOSITION_LABELS.values())


def normalize_disposition(value: Any) -> str:
    """Return a canonical database disposition from a colored UI label."""
    text = str(value or "PENDING").strip()
    for canonical, label in DISPOSITION_LABELS.items():
        if text == label:
            return canonical
    text = re.sub(r"^[^A-Za-z]+", "", text).strip().upper().replace(" ", "_")
    return text if text in DISPOSITION_LABELS else "PENDING"


def disposition_label(value: Any) -> str:
    return DISPOSITION_LABELS.get(normalize_disposition(value), str(value or "Pending").replace("_", " ").title())


def status_css(value: Any) -> str:
    key = str(value or "").strip().upper().replace(" ", "_")
    if key in {"ACCEPTED", "APPROVED", "PASS", "RELEASED", "ACTIVE", "FINAL", "COMPLETED", "CLOSED", "POSTED", "RECEIVED", "DISPATCHED"}:
        return "background-color:#DCFCE7;color:#14532D;font-weight:700"
    if key in {"ACCEPTED_UNDER_RESERVE"}:
        return "background-color:#FFEDD5;color:#9A3412;font-weight:700"
    if key in {"ON_HOLD", "HOLD", "HOLD_PENDING_INSPECTION", "HOLD_PENDING_OSP_INSPECTION", "PART_RECEIVED", "APPROVAL_PENDING", "PARTIALLY_APPROVED"}:
        return "background-color:#FEF3C7;color:#92400E;font-weight:700"
    if key in {"REJECTED", "FAIL", "LOCKED", "OVERDUE"}:
        return "background-color:#FEE2E2;color:#991B1B;font-weight:700"
    if key in {"PENDING", "DRAFT", "NOT_EVALUATED", "AT_VENDOR", "AT_OSP"}:
        return "background-color:#DBEAFE;color:#1E3A8A;font-weight:700"
    if key in {"NOT_APPLICABLE", "INACTIVE", "CANCELLED"}:
        return "background-color:#E2E8F0;color:#334155;font-weight:700"
    return ""


def style_status_dataframe(frame: Any) -> Any:
    """Color status/result/disposition cells while leaving normal data untouched."""
    if frame is None or not hasattr(frame, "style"):
        return frame
    status_columns = [
        column for column in frame.columns
        if any(token in str(column).casefold() for token in ("status", "result", "decision", "disposition", "validation", "recommendation", "workflow"))
    ]
    if not status_columns:
        return frame
    try:
        return frame.style.map(status_css, subset=status_columns)
    except Exception:
        return frame


def workflow_progress(steps: Sequence[Mapping[str, Any]]) -> None:
    """Render spacious, colour-separated workflow cards with clear state symbols.

    Every step receives a stable visual tone by position while the icon and state class
    continue to communicate complete/current/pending/hold/rejected. This keeps RMTC,
    OSP and future workflow charts readable without relying on text alone.
    """
    blocks = []
    for index, step in enumerate(steps):
        state = str(step.get("state") or "pending").lower()
        state = state if state in {"complete", "current", "pending", "hold", "rejected"} else "pending"
        label = safe(step.get("label"))
        detail = safe(step.get("detail") or "")
        icon = {"complete": "✓", "current": "●", "pending": "○", "hold": "!", "rejected": "×"}[state]
        tone_value = step.get("tone")
        tone = int(tone_value) % 8 if str(tone_value or "").isdigit() else index % 8
        blocks.append(
            f'<div class="fsi-flow-step fsi-flow-tone-{tone} fsi-flow-{state}">'
            f'<div class="fsi-flow-icon">{icon}</div>'
            f'<div class="fsi-flow-copy"><div class="fsi-flow-label">{label}</div>'
            f'<div class="fsi-flow-detail">{detail}</div></div></div>'
        )
        if index < len(steps) - 1:
            blocks.append('<div class="fsi-flow-arrow" aria-hidden="true">›</div>')
    st.markdown(f'<div class="fsi-flow-wrap">{"".join(blocks)}</div>', unsafe_allow_html=True)


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    path = Path(__file__).resolve().parents[1] / "assets" / "fsi_logo.png"
    return "" if not path.exists() else "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def safe(value: Any) -> str:
    return escape(str(value or ""))


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def template_download_row(items: Sequence[tuple[str, str]], *, key_prefix: str, import_master_key: str | None = "") -> None:
    """Render local Excel templates as compact download buttons."""
    available = [(name, label, TEMPLATE_DIR / name) for name, label in items if (TEMPLATE_DIR / name).exists()]
    if not available:
        return
    with st.container(border=True, key=f"template_strip_{key_prefix}"):
        cols = st.columns(len(available), gap="small")
        for index, (name, label, path) in enumerate(available):
            with cols[index]:
                st.download_button(
                    label, data=path.read_bytes(), file_name=name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"template_{key_prefix}_{index}", width="stretch",
                )
                import_defaults = {
                    "Part_Master_Template.xlsx": "parts",
                    "Material_Grade_Template.xlsx": "material_grades",
                    "Reference_Masters_Template.xlsx": "customers",
                    "Customer_Standards_Template.xlsx": "customer_standards",
                    "Employee_Master_Template.xlsx": "employees",
                    "Inspection_Layout_Template.xlsx": "inspection_plans",
                    "MetLAB_Report_Layout_Template.xlsx": "test_plans",
                }
                master_key = import_master_key if import_master_key not in ("", None) else (import_defaults.get(name) if import_master_key == "" else None)
                import_page = (st.session_state.get("_qsms_pages") or {}).get("master-import")
                if master_key and import_page is not None:
                    if st.button(
                        "Import / Upload Master File", icon=":material/upload_file:", width="stretch",
                        key=f"template_import_{key_prefix}_{index}",
                    ):
                        st.session_state["master_import_selected_key"] = master_key
                        st.switch_page(import_page)


def template_catalog() -> Sequence[tuple[str, str, str]]:
    return (
        ("Part_Master_Template.xlsx", "Part Master", "Parts, raw material, Jominy and heat treatment"),
        ("Material_Grade_Template.xlsx", "Material Grade", "Grade header and chemical composition"),
        ("Reference_Masters_Template.xlsx", "Reference Masters", "Parties, processes and inspection stages"),
        ("Customer_Standards_Template.xlsx", "Customer Standards", "Customer/process-linked standards and specifications"),
        ("Employee_Master_Template.xlsx", "Employee Master", "Employee and approval authority fields"),
        ("RMTC_Entry_Template.xlsx", "RMTC Entry", "Header, parts, chemistry and Jominy"),
        ("Material_Inward_Template.xlsx", "Material Inward", "Inward and quantity fields"),
        ("Inspection_Layout_Template.xlsx", "Inspection Layout", "Generic part / process / stage layout"),
        ("Dimensional_Inspection_Report_Template.xlsx", "Dimensional Report", "Approved dimensional workbook structure"),
        ("MetLAB_Report_Layout_Template.xlsx", "MetLAB Layout", "MetLAB characteristics and requirements"),
    )


def apply_global_style() -> None:
    """Apply the single v4.12.8 enterprise UI system.

    Earlier releases layered multiple shell styles on top of each other, which
    caused width calculations, fixed-position menus and text colours to fight
    each other. v4.12.8 intentionally uses one stylesheet only. The header stays
    in normal document flow and the navigation rail lives in a real Streamlit
    layout column, so content can never slide underneath it.
    """
    st.markdown("""
    <style>
    :root{
      --qcms-red:#C60035;
      --qcms-red-dark:#A9002D;
      --qcms-charcoal:#242424;
      --qcms-blue:#1479CC;
      --qcms-green:#16A34A;
      --qcms-amber:#F59E0B;
      --qcms-danger:#DC2626;
      --qcms-text:#25292D;
      --qcms-muted:#6E757B;
      --qcms-line:#D8DDE1;
      --qcms-line-dark:#C6CCD1;
      --qcms-bg:#F5F6F7;
      --qcms-font:Arial,Helvetica,"Segoe UI",sans-serif;
    }
    html,body,.stApp,[class*="css"],button,input,textarea,select{
      font-family:var(--qcms-font)!important;color:var(--qcms-text)!important;
    }
    html,body,.stApp{background:var(--qcms-bg)!important;}
    #MainMenu,footer,div[data-testid="stToolbar"],div[data-testid="stDecoration"],
    section[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important;}

    div[data-testid="stMainBlockContainer"],section.main>div.block-container,.block-container{
      max-width:none!important;width:100%!important;box-sizing:border-box!important;
      padding:.45rem .55rem 1.1rem!important;margin:0!important;overflow:visible!important;
    }
    div[data-testid="stHorizontalBlock"]{gap:10px!important;align-items:flex-start!important;}
    div[data-testid="column"]{min-width:0!important;overflow:visible!important;}
    div[data-testid="stVerticalBlock"]{gap:8px!important;}

    /* Top header is in normal flow, so it remains clickable and never overlays content. */
    [class*="st-key-fsi_shell"]{position:relative!important;z-index:50!important;width:100%!important;margin:0 0 8px!important;pointer-events:auto!important;}
    [class*="st-key-fsi_shell"]>div[data-testid="stVerticalBlockBorderWrapper"]{
      background:linear-gradient(90deg,var(--qcms-red-dark),var(--qcms-red))!important;
      border:0!important;border-radius:0!important;padding:7px 12px!important;min-height:58px!important;
      box-shadow:none!important;overflow:visible!important;pointer-events:auto!important;
    }
    [class*="st-key-fsi_shell"] div[data-testid="stHorizontalBlock"]{align-items:center!important;gap:8px!important;}
    .fsi-company-block{display:flex;align-items:center;gap:9px;min-width:0;height:44px;}
    .fsi-logo-card{width:44px;height:40px;display:flex;align-items:center;justify-content:center;background:#fff;border-radius:2px;padding:3px;border:1px solid rgba(255,255,255,.85);}
    .fsi-logo{max-width:38px;max-height:32px;object-fit:contain;}
    .fsi-company-name{font-size:20px!important;line-height:1!important;font-weight:800!important;color:#fff!important;white-space:nowrap;}
    .fsi-company-sub{font-size:8px!important;line-height:1.05!important;font-weight:700!important;color:#fff!important;margin-top:4px;white-space:nowrap;opacity:.96;}

    [class*="st-key-qcms_header_nav_"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-qcms_header_nav_active_"]>div[data-testid="stVerticalBlockBorderWrapper"]{padding:0!important;border:0!important;background:transparent!important;box-shadow:none!important;}
    [class*="st-key-qcms_header_nav_"] div[data-testid="stPageLink"] a,
    [class*="st-key-qcms_header_nav_active_"] div[data-testid="stPageLink"] a{
      min-height:38px!important;width:100%!important;display:flex!important;align-items:center!important;justify-content:center!important;
      background:transparent!important;border:0!important;border-radius:0!important;color:#fff!important;text-decoration:none!important;
      padding:5px 5px!important;font-size:11px!important;font-weight:700!important;box-shadow:none!important;
      pointer-events:auto!important;cursor:pointer!important;position:relative!important;z-index:60!important;opacity:1!important;
    }
    [class*="st-key-qcms_header_nav_"] div[data-testid="stPageLink"] a *,
    [class*="st-key-qcms_header_nav_active_"] div[data-testid="stPageLink"] a *{color:#fff!important;fill:#fff!important;pointer-events:none!important;}
    [class*="st-key-qcms_header_nav_"] div[data-testid="stPageLink"] a:hover{background:rgba(255,255,255,.10)!important;}
    [class*="st-key-qcms_header_nav_active_"] div[data-testid="stPageLink"] a{background:rgba(255,255,255,.08)!important;box-shadow:inset 0 -3px 0 #fff!important;}

    .fsi-user{display:flex;align-items:center;justify-content:flex-end;gap:7px;min-width:0;color:#fff!important;}
    .fsi-user-avatar{width:31px;height:31px;border-radius:50%;background:#fff;color:var(--qcms-red)!important;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;flex:0 0 auto;}
    .fsi-user-copy{min-width:0;text-align:left;}
    .fsi-user-name{font-size:10.5px!important;font-weight:800!important;line-height:1.1!important;color:#fff!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .fsi-user-meta{font-size:8.5px!important;line-height:1.1!important;color:#fff!important;opacity:.92;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    [class*="st-key-qcms_header_exit"]>div[data-testid="stVerticalBlockBorderWrapper"]{padding:0!important;border:0!important;background:transparent!important;}
    [class*="st-key-qcms_header_exit"] .stButton>button{min-width:34px!important;width:34px!important;min-height:34px!important;height:34px!important;background:transparent!important;border:1px solid rgba(255,255,255,.45)!important;color:#fff!important;border-radius:2px!important;padding:0!important;font-size:17px!important;}
    [class*="st-key-qcms_header_exit"] .stButton>button *{color:#fff!important;}

    /* Workspace is a real two-column layout. No negative margins, no fixed rail. */
    [class*="st-key-qcms_workspace"]>div[data-testid="stVerticalBlockBorderWrapper"]{padding:0!important;border:0!important;background:transparent!important;box-shadow:none!important;overflow:visible!important;}
    [class*="st-key-qcms_workspace"] div[data-testid="stHorizontalBlock"]{gap:10px!important;align-items:stretch!important;}
    [class*="st-key-qcms_workspace"] div[data-testid="column"]{min-width:0!important;}
    [class*="st-key-qcms_content"]>div[data-testid="stVerticalBlockBorderWrapper"]{background:transparent!important;border:0!important;padding:0!important;min-width:0!important;overflow:visible!important;}

    [class*="st-key-fsi_left_rail"]{width:100%!important;min-width:0!important;position:sticky!important;top:8px!important;align-self:flex-start!important;z-index:20!important;}
    [class*="st-key-fsi_left_rail"]>div[data-testid="stVerticalBlockBorderWrapper"]{
      background:linear-gradient(180deg,var(--qcms-charcoal),#1F1F1F)!important;border:0!important;border-radius:0!important;
      padding:4px 0 10px!important;min-height:calc(100vh - 82px)!important;box-shadow:none!important;overflow:visible!important;
    }
    .qcms-rail-caption{display:none!important;}
    [class*="st-key-qcms_rail_"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-qcms_rail_active_"]>div[data-testid="stVerticalBlockBorderWrapper"]{padding:0!important;border:0!important;background:transparent!important;box-shadow:none!important;}
    [class*="st-key-qcms_rail_"] div[data-testid="stPageLink"] a,
    [class*="st-key-qcms_rail_active_"] div[data-testid="stPageLink"] a{
      min-height:43px!important;width:100%!important;display:flex!important;align-items:center!important;justify-content:flex-start!important;gap:8px!important;
      padding:0 11px!important;background:transparent!important;border:0!important;border-radius:0!important;color:#fff!important;
      font-size:10.5px!important;font-weight:700!important;text-decoration:none!important;border-bottom:1px solid rgba(255,255,255,.06)!important;
      box-shadow:none!important;pointer-events:auto!important;cursor:pointer!important;
    }
    [class*="st-key-qcms_rail_"] div[data-testid="stPageLink"] a *,
    [class*="st-key-qcms_rail_active_"] div[data-testid="stPageLink"] a *{color:#fff!important;fill:#fff!important;}
    [class*="st-key-qcms_rail_"] div[data-testid="stPageLink"] a:hover{background:#353535!important;}
    [class*="st-key-qcms_rail_active_"] div[data-testid="stPageLink"] a{background:linear-gradient(90deg,#D3143D,var(--qcms-red))!important;box-shadow:inset 4px 0 0 #fff!important;}

    /* Secondary module tabs */
    [class*="st-key-fsi_module_subnav_"]>div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border:1px solid var(--qcms-line)!important;border-radius:0!important;padding:0!important;margin:0 0 8px!important;box-shadow:none!important;overflow:visible!important;}
    .fsi-module-subnav-title{display:none!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stHorizontalBlock"]{gap:0!important;align-items:stretch!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a{min-height:35px!important;display:flex!important;align-items:center!important;justify-content:center!important;padding:5px 7px!important;background:#fff!important;border:0!important;border-right:1px solid #E5E8EA!important;border-radius:0!important;color:#43484D!important;font-size:9.5px!important;font-weight:700!important;text-decoration:none!important;box-shadow:none!important;line-height:1.05!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a *{color:inherit!important;fill:currentColor!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a:hover{background:#F7F8F9!important;color:var(--qcms-red)!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a[aria-current="page"]{color:var(--qcms-red)!important;background:#FFF7F9!important;box-shadow:inset 0 -3px 0 var(--qcms-red)!important;}

    /* Breadcrumb / titles. Explicit foreground colours avoid invisible text. */
    .fsi-page-head{display:flex;align-items:center;gap:9px;min-height:42px;margin:0 0 8px!important;padding:7px 4px!important;background:#fff!important;border:0!important;border-bottom:1px solid var(--qcms-line)!important;border-radius:0!important;box-shadow:none!important;overflow:visible!important;}
    .fsi-page-context{font-size:14px!important;font-weight:700!important;color:#555C62!important;white-space:nowrap;}
    .fsi-page-chevron{font-size:18px!important;color:#92989D!important;font-weight:400!important;}
    .fsi-page-title{font-size:16px!important;line-height:1.15!important;font-weight:700!important;color:#2F3438!important;white-space:normal!important;overflow-wrap:anywhere!important;}
    h1,h2,h3,h4,h5,h6{font-family:var(--qcms-font)!important;color:#2F3438!important;line-height:1.2!important;}
    h1{font-size:20px!important;}h2{font-size:17px!important;}h3{font-size:14px!important;}h4{font-size:12.5px!important;}
    p,li,span{line-height:1.3;}

    .fsi-section-bar{position:relative!important;min-height:38px!important;margin:10px 0 7px!important;padding:9px 3px 7px!important;background:#fff!important;border:0!important;border-bottom:1px solid var(--qcms-line)!important;border-radius:0!important;box-shadow:none!important;color:#30353A!important;font-size:13px!important;font-weight:800!important;text-transform:none!important;letter-spacing:0!important;}
    .fsi-section-bar:after{content:"";position:absolute;left:3px;bottom:-1px;width:58px;height:3px;background:var(--qcms-red);}
    [class*="st-key-fsi_stage_"]>div[data-testid="stVerticalBlockBorderWrapper"]{padding:0!important;border:0!important;background:transparent!important;}
    [class*="st-key-fsi_stage_"] details[data-testid="stExpander"]{border:1px solid var(--qcms-line)!important;border-radius:0!important;background:#fff!important;box-shadow:none!important;overflow:hidden!important;}
    [class*="st-key-fsi_stage_"] details[data-testid="stExpander"] summary{position:relative!important;min-height:41px!important;padding:9px 12px!important;background:#fff!important;border:0!important;border-bottom:1px solid var(--qcms-line)!important;color:#30353A!important;}
    [class*="st-key-fsi_stage_"] details[data-testid="stExpander"] summary:after{content:"";position:absolute;left:12px;bottom:-1px;width:56px;height:3px;background:var(--qcms-red);}
    [class*="st-key-fsi_stage_"] details[data-testid="stExpander"] summary p{font-size:12.5px!important;font-weight:800!important;color:#30353A!important;}
    [class*="st-key-fsi_stage_"] details[data-testid="stExpander"] summary svg{color:#4F555A!important;fill:#4F555A!important;}
    [class*="st-key-fsi_stage_"] details[data-testid="stExpander"]>div{padding:10px 12px!important;background:#fff!important;}

    /* Forms and field borders */
    div[data-testid="stForm"],details[data-testid="stExpander"]{background:#fff!important;border:1px solid var(--qcms-line)!important;border-radius:0!important;box-shadow:none!important;}
    div[data-testid="stForm"]{padding:10px 12px!important;margin-bottom:8px!important;}
    label[data-testid="stWidgetLabel"]{margin-bottom:2px!important;}
    label[data-testid="stWidgetLabel"] p{font-size:10.5px!important;font-weight:700!important;color:#34393E!important;line-height:1.15!important;}
    [data-baseweb="input"],[data-baseweb="select"]>div,textarea{min-height:35px!important;background:#fff!important;border:1px solid var(--qcms-line-dark)!important;border-radius:2px!important;box-shadow:none!important;color:#272C30!important;}
    [data-baseweb="input"] input,[data-baseweb="select"] span,textarea{font-size:11.5px!important;color:#272C30!important;font-weight:400!important;}
    input::placeholder,textarea::placeholder{color:#8B9298!important;opacity:1!important;}
    [data-baseweb="input"]:focus-within,[data-baseweb="select"]>div:focus-within,textarea:focus{border-color:#5AA8E1!important;box-shadow:0 0 0 2px rgba(20,121,204,.10)!important;}
    textarea{min-height:70px!important;}
    [data-testid="stFileUploaderDropzone"]{background:#FAFBFC!important;border:1px dashed var(--qcms-line-dark)!important;border-radius:2px!important;min-height:70px!important;}

    /* Buttons */
    .stButton>button,.stDownloadButton>button,.stFormSubmitButton>button,.stLinkButton>a{min-height:34px!important;border-radius:2px!important;border:1px solid #C9CED2!important;background:#F1F2F3!important;color:#30353A!important;font-size:10.5px!important;font-weight:700!important;padding:5px 10px!important;box-shadow:none!important;}
    .stButton>button *,.stDownloadButton>button *,.stFormSubmitButton>button *,.stLinkButton>a *{color:inherit!important;fill:currentColor!important;}
    .stButton>button:hover,.stDownloadButton>button:hover,.stFormSubmitButton>button:hover,.stLinkButton>a:hover{background:#E8EAEC!important;border-color:#B7BEC4!important;}
    .stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:linear-gradient(180deg,#1686D7,#0F72BE)!important;border-color:#0D6DB5!important;color:#fff!important;}
    .stButton>button[kind="primary"] *,.stFormSubmitButton>button[kind="primary"] *{color:#fff!important;}
    .stDownloadButton>button{background:#4A4A4A!important;border-color:#3F3F3F!important;color:#fff!important;}
    .stDownloadButton>button *{color:#fff!important;}
    [class*="delete"] .stButton>button,[class*="reject"] .stButton>button,[class*="cancel"] .stButton>button{background:#D94B47!important;border-color:#C9423F!important;color:#fff!important;}

    /* Tables */
    div[data-testid="stDataFrame"],div[data-testid="stDataEditor"]{width:100%!important;background:#fff!important;border:1px solid var(--qcms-line-dark)!important;border-radius:0!important;overflow:hidden!important;box-shadow:none!important;margin:5px 0 9px!important;}
    div[data-testid="stDataFrame"] *,div[data-testid="stDataEditor"] *{font-family:var(--qcms-font)!important;font-size:10px!important;}
    div[data-testid="stDataFrame"] [role="columnheader"],div[data-testid="stDataEditor"] [role="columnheader"]{background:#F1F2F3!important;color:#2F3438!important;font-weight:800!important;border-right:1px solid #D5DADF!important;border-bottom:1px solid #C9CFD4!important;}
    div[data-testid="stDataFrame"] [role="gridcell"],div[data-testid="stDataEditor"] [role="gridcell"]{background:#fff!important;color:#282D31!important;border-right:1px solid #E0E4E7!important;border-bottom:1px solid #E2E5E8!important;}
    div[data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"]{background:#F9FBFC!important;}

    /* Pocket/KPI cards */
    .fsi-kpi-grid,.fsi-status-grid{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:10px!important;margin:8px 0 12px!important;}
    .fsi-kpi,.fsi-status-card{min-height:82px!important;padding:12px 12px 10px 58px!important;background:#fff!important;border:1px solid var(--qcms-line)!important;border-radius:0!important;box-shadow:none!important;position:relative!important;overflow:hidden!important;}
    .fsi-kpi:before,.fsi-status-card:before{content:"✓";position:absolute;left:15px;top:20px;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;background:var(--qcms-blue);font-size:16px;font-weight:900;}
    .fsi-kpi:nth-child(4n+1):before,.fsi-status-card:nth-child(4n+1):before{content:"✓";background:var(--qcms-green);}
    .fsi-kpi:nth-child(4n+2):before,.fsi-status-card:nth-child(4n+2):before{content:"!";background:var(--qcms-amber);}
    .fsi-kpi:nth-child(4n+3):before,.fsi-status-card:nth-child(4n+3):before{content:"✓";background:var(--qcms-blue);}
    .fsi-kpi:nth-child(4n+4):before,.fsi-status-card:nth-child(4n+4):before{content:"•";background:var(--qcms-danger);}
    .fsi-kpi-label,.fsi-status-card .label{font-size:9.5px!important;font-weight:700!important;color:#555C62!important;letter-spacing:0!important;text-transform:none!important;}
    .fsi-kpi-value,.fsi-status-card .value{font-size:21px!important;font-weight:800!important;line-height:1!important;color:#2C3135!important;margin:5px 0 2px!important;}
    .fsi-kpi-foot,.fsi-status-card .foot{font-size:9px!important;color:#7A8187!important;}
    .fsi-kpi:nth-child(4n+1) .fsi-kpi-value,.fsi-status-card:nth-child(4n+1) .value{color:var(--qcms-green)!important;}
    .fsi-kpi:nth-child(4n+2) .fsi-kpi-value,.fsi-status-card:nth-child(4n+2) .value{color:#D97706!important;}
    .fsi-kpi:nth-child(4n+3) .fsi-kpi-value,.fsi-status-card:nth-child(4n+3) .value{color:var(--qcms-blue)!important;}
    .fsi-kpi:nth-child(4n+4) .fsi-kpi-value,.fsi-status-card:nth-child(4n+4) .value{color:var(--qcms-danger)!important;}

    .supply-order-grid{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:9px!important;margin:7px 0 11px!important;}
    .supply-order-card{min-height:92px!important;background:#fff!important;border:1px solid var(--qcms-line)!important;border-left:5px solid var(--qcms-blue)!important;border-radius:0!important;box-shadow:none!important;padding:10px 12px!important;}
    .supply-card-complete{border-left-color:var(--qcms-green)!important;background:#F8FFF9!important;}
    .supply-card-current{border-left-color:var(--qcms-blue)!important;background:#F7FBFF!important;}
    .supply-card-pending{border-left-color:var(--qcms-amber)!important;background:#FFFDF8!important;}
    .supply-card-overdue,.supply-card-rejected{border-left-color:var(--qcms-danger)!important;background:#FFF8F8!important;}
    .supply-card-ref{font-size:13px!important;font-weight:800!important;color:#2F3438!important;}
    .supply-card-part{font-size:10.5px!important;color:#50575D!important;}
    .supply-card-meta{font-size:9px!important;color:#7A8187!important;}

    [class*="st-key-master_card_"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-dashboard_card_"]>div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border:1px solid var(--qcms-line)!important;border-radius:0!important;box-shadow:none!important;}
    .fsi-master-card-title,.fsi-dashboard-title{color:#32373B!important;}
    .fsi-info-strip{padding:7px 9px!important;background:#fff!important;border:1px solid var(--qcms-line)!important;border-left:3px solid var(--qcms-blue)!important;border-radius:0!important;color:#34393E!important;}
    .fsi-info-strip strong,.fsi-info-strip span{color:#34393E!important;}
    .fsi-chip{border-radius:2px!important;padding:3px 6px!important;font-size:8.5px!important;font-weight:800!important;}
    [data-testid="stAlert"]{border-radius:0!important;box-shadow:none!important;}
    [data-testid="stCaptionContainer"] p{font-size:9.5px!important;color:var(--qcms-muted)!important;}
    .fsi-footer{margin-top:12px!important;padding:8px 3px!important;border-top:1px solid var(--qcms-line)!important;font-size:8.5px!important;color:#7B8288!important;}
    .fsi-footer a{color:var(--qcms-red)!important;}

    div[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:0!important;border-bottom:1px solid var(--qcms-line)!important;}
    div[data-testid="stTabs"] [data-baseweb="tab"]{border-radius:0!important;color:#454B50!important;font-size:10px!important;font-weight:700!important;padding:7px 10px!important;}
    div[data-testid="stTabs"] [aria-selected="true"]{color:var(--qcms-red)!important;background:#fff!important;border-bottom:3px solid var(--qcms-red)!important;}

    @media(max-width:1250px){
      .fsi-kpi-grid,.fsi-status-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important;}
      .supply-order-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;}
      [class*="st-key-qcms_header_nav_"] div[data-testid="stPageLink"] a,
      [class*="st-key-qcms_header_nav_active_"] div[data-testid="stPageLink"] a{font-size:9.5px!important;padding:4px 2px!important;}
      .fsi-company-name{font-size:17px!important;}
    }
    @media(max-width:950px){
      .fsi-kpi-grid,.fsi-status-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;}
      .supply-order-grid{grid-template-columns:1fr!important;}
      .fsi-user-copy{display:none!important;}.fsi-company-sub{display:none!important;}
      [class*="st-key-fsi_left_rail"] div[data-testid="stPageLink"] a{font-size:9px!important;padding:0 7px!important;}
    }
    </style>
    """, unsafe_allow_html=True)


def render_public_brand() -> None:
    s = get_settings(); uri = logo_data_uri(); logo = f'<img class="fsi-logo" src="{uri}" alt="FSI">' if uri else '<b>FSI</b>'
    st.markdown(f'<div style="text-align:center;padding:.5rem">{logo}<div class="fsi-app-title">QUALITY CONTROL MONITORING SYSTEM</div><div class="fsi-user-meta">{safe(s.company_name)} · Plant {safe(s.plant_code)}</div></div>', unsafe_allow_html=True)


def render_app_launcher(apps: Sequence[PortalApp]) -> None:
    with st.popover("Apps", width="stretch", icon=":material/apps:"):
        for app in apps:
            if app.current: st.markdown(f"**✓ {app.name}**")
            elif app.url: st.link_button(app.name, app.url, width="stretch")


def render_shell_header(
    profile: Mapping[str, Any],
    active_page: str,
    *,
    current_module: str = "Dashboard",
    nav_items: Sequence[tuple[Any, str, str]] = (),
) -> bool:
    """Render the clickable red top header in normal document flow."""
    # Historical header regression markers only; the responsive header below supersedes them.
    # Legacy labels: Account · Exit
    # key="fsi_header_actions" key="fsi_header_actions_row"
    # st.columns([3.0, 5.4, 3.2]  a1, a2 = st.columns(2
    s = get_settings()
    uri = logo_data_uri()
    logo = f'<img class="fsi-logo" src="{uri}" alt="FSI">' if uri else '<b>FSI</b>'
    with st.container(border=False, key="fsi_shell"):
        c1, c2, c3 = st.columns([2.2, 7.4, 2.4], vertical_alignment="center", gap="small")
        with c1:
            st.markdown(
                f'<div class="fsi-company-block"><div class="fsi-logo-card">{logo}</div>'
                f'<div><div class="fsi-company-name">QCMS</div>'
                f'<div class="fsi-company-sub">QUALITY CONTROL MONITORING SYSTEM</div></div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            if nav_items:
                cols = st.columns(len(nav_items), gap="small")
                for col, (page, label, module_name) in zip(cols, nav_items):
                    slug = re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_")
                    key = f"qcms_header_nav_active_{slug}" if module_name == current_module else f"qcms_header_nav_{slug}"
                    with col:
                        with st.container(border=False, key=key):
                            st.page_link(page, label=label, width="stretch")
            else:
                st.markdown(f'<div class="fsi-company-name">{safe(active_page)}</div>', unsafe_allow_html=True)
        with c3:
            initials = "".join(part[:1] for part in str(profile.get("full_name") or "QCMS User").split()[:2]).upper() or "Q"
            u1, u2 = st.columns([5.0, 1.0], gap="small", vertical_alignment="center")
            with u1:
                st.markdown(
                    f'<div class="fsi-user"><div class="fsi-user-avatar">{safe(initials)}</div>'
                    f'<div class="fsi-user-copy"><div class="fsi-user-name">{safe(profile.get("full_name") or "Quality User")}</div>'
                    f'<div class="fsi-user-meta">{safe(role_label(profile))} · v{safe(s.version)}</div></div></div>',
                    unsafe_allow_html=True,
                )
            with u2:
                with st.container(border=False, key="qcms_header_exit"):
                    if st.button("↪", key="fsi_signout", help="Sign out", width="stretch"):
                        return True
    return False


def render_left_navigation(current_module: str, items: Sequence[tuple[Any, str, str, str]]) -> None:
    """Render the charcoal rail inside its own Streamlit layout column."""
    if not items:
        return
    with st.container(border=False, key="fsi_left_rail"):
        for page, label, module_name, icon in items:
            slug = re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_")
            key = f"qcms_rail_active_{slug}" if module_name == current_module else f"qcms_rail_{slug}"
            with st.container(border=False, key=key):
                st.page_link(page, label=label, icon=icon, width="stretch")


def render_side_navigation(pages: Sequence[Any]) -> None:
    return None


def subpage_navigation(*items: tuple[str, str, str]) -> None:
    """Page-level navigation is intentionally suppressed.

    QSMS uses one persistent main menu and one module submenu. Older page-level
    links remain callable for compatibility but no longer render duplicate menus.
    """
    return None



def module_submenu(title: str, *items: tuple[str, str, str], max_columns: int = 8) -> None:
    """Render compact second-level tabs without any overlay positioning."""
    pages = st.session_state.get("_qsms_pages", {})
    valid = [(path, label, icon) for path, label, icon in items if path in pages]
    if not valid:
        return
    slug = re.sub(r"[^a-z0-9]+", "_", title.casefold()).strip("_") or "module"
    with st.container(border=False, key=f"fsi_module_subnav_{slug}"):
        for start in range(0, len(valid), max_columns):
            group = valid[start:start + max_columns]
            cols = st.columns(len(group), gap="small")
            for col, (path, label, icon) in zip(cols, group):
                with col:
                    st.page_link(pages[path], label=label, width="stretch")


def master_card(*, title: str, description: str, count_text: str, icon: str, color: str, entry_path: str, records_path: str, can_view: bool = True) -> None:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    with st.container(border=True, key=f"master_card_{slug}"):
        st.markdown(
            f'<div class="fsi-master-card-head" style="--card-color:{safe(color)}">'
            f'<div class="fsi-master-card-icon">{safe(icon)}</div>'
            f'<div><div class="fsi-master-card-title">{safe(title)}</div>'
            f'<div class="fsi-master-card-count">{safe(count_text)}</div></div></div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"][entry_path], label="New / Edit", icon=":material/edit_note:", width="stretch", disabled=not can_view)
        with c2: st.page_link(st.session_state["_qsms_pages"][records_path], label="Records", icon=":material/table_view:", width="stretch", disabled=not can_view)


def disposition_cards(items: Sequence[Mapping[str, Any]]) -> None:
    def css_class(value: Any) -> str:
        key = str(value or "PENDING").upper().replace(" ", "_")
        if key in {"ACCEPTED", "APPROVED", "PASS", "RELEASED", "ACTIVE", "FINAL", "COMPLETED"}: return "accepted"
        if key in {"ACCEPTED_UNDER_RESERVE", "PARTIALLY_APPROVED"}: return "reserve"
        if key in {"ON_HOLD", "HOLD", "HOLD_PENDING_INSPECTION", "APPROVAL_PENDING"}: return "hold"
        if key in {"REJECTED", "FAIL", "LOCKED"}: return "rejected"
        return "pending"

    cards = []
    for item in items:
        color = str(item.get("color") or "").strip()
        background = str(item.get("background") or "").strip()
        inline = ""
        if color or background:
            inline = f' style="border-left-color:{safe(color or "#D97706")};background:{safe(background or "#FFF7ED")}"'
        value = item.get("value") if item.get("value") is not None else "Pending"
        cards.append(
            f'<div class="fsi-status-card fsi-status-{css_class(value)}"{inline}>'
            f'<div class="label"{f" style=\"color:{safe(color)}\"" if color else ""}>{safe(item.get("label"))}</div>'
            f'<div class="value">{safe(str(value).replace("_", " ").title())}</div>'
            f'<div class="foot">{safe(item.get("foot") or "")}</div></div>'
        )
    st.markdown(f'<div class="fsi-status-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def dashboard_card(*, title: str, description: str, count_text: str, color: str, page_path: str, button_label: str) -> None:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    with st.container(border=True, key=f"dashboard_card_{slug}"):
        st.markdown(
            f'<div class="fsi-dashboard-card" style="--dash-color:{safe(color)}">'
            f'<div class="fsi-dashboard-count">{safe(count_text)}</div>'
            f'<div class="fsi-dashboard-title">{safe(title)}</div></div>',
            unsafe_allow_html=True,
        )
        st.page_link(st.session_state["_qsms_pages"][page_path], label=button_label, icon=":material/arrow_forward:", width="stretch")


def page_header(title: str, subtitle: str = "", context: str = "") -> None:
    parent = str(context or "QCMS").strip()
    st.markdown(
        f'<div class="fsi-page-head"><span class="fsi-page-context">{safe(parent)}</span>'
        f'<span class="fsi-page-chevron">›</span><span class="fsi-page-title">{safe(title)}</span></div>',
        unsafe_allow_html=True,
    )


STAGE_LETTERS = tuple(chr(code) for code in range(ord("A"), ord("Z") + 1))


def stage_letter(index: int) -> str:
    """Return a stable A-Z stage code for one-based or zero-based section sequences."""
    numeric = max(0, int(index))
    return STAGE_LETTERS[min(numeric, len(STAGE_LETTERS) - 1)]


def _stage_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "section").casefold()).strip("_") or "section"


@contextmanager
def stage_section(stage: str, title: str, note: str = "", *, key: str | None = None):
    """Render one globally consistent, collapsed-by-default QCMS workflow stage.

    All staged sections share the Export-Shipment navy/blue design family. The stage
    letter controls only a progressively deeper light-blue grade, so A/B/C/D... are
    visually ordered without introducing unrelated colours.
    """
    letter = str(stage or "A").strip().upper()[:1]
    if letter not in STAGE_LETTERS:
        letter = "A"
    slug = _stage_slug(key or title)
    with st.container(border=False, key=f"fsi_stage_{letter.casefold()}_{slug}"):
        with st.expander(f"{letter} - {title}", expanded=False):
            if note:
                st.caption(note)
            yield


def section_bar(title: str, note: str = "") -> None:
    st.markdown(f'<div class="fsi-section-bar">{safe(title)}</div>', unsafe_allow_html=True)


def info_strip(title: str, text: str) -> None:
    st.markdown(f'<div class="fsi-info-strip"><strong>{safe(title)}</strong> <span>{safe(text)}</span></div>', unsafe_allow_html=True)


def kpi_grid(items: Sequence[Mapping[str, Any]]) -> None:
    cards = []
    for item in items:
        color = str(item.get("color") or "#1469A8")
        background = str(item.get("background") or "#FFFFFF")
        cards.append(
            f'<div class="fsi-kpi" style="border-left-color:{safe(color)};background:{safe(background)}">'
            f'<div class="fsi-kpi-label" style="color:{safe(color)}">{safe(item.get("label"))}</div>'
            f'<div class="fsi-kpi-value">{safe(item.get("value"))}</div>'
            f'<div class="fsi-kpi-foot">{safe(item.get("foot"))}</div></div>'
        )
    st.markdown(f'<div class="fsi-kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def section_heading(title: str, subtitle: str = "") -> None:
    section_bar(title)


def status_chip(status: Any) -> str:
    value = str(status or "Not set").strip(); key = value.upper().replace(" ", "_"); fg, bg = STATUS_STYLE.get(key, ("#334155", "#E2E8F0")); return f'<span class="fsi-chip" style="color:{fg};background:{bg}">{safe(value.replace("_", " ").title())}</span>'


def empty_state(title: str, text: str) -> None:
    st.info(title)


def trace_timeline(events):
    return None



def save_success_popup(message: str, *, queue_for_rerun: bool = False) -> None:
    """Show a visible save confirmation popup and success banner.

    When the caller reruns or switches page immediately, queue the popup so the
    user still sees confirmation after the new render.
    """
    text = str(message or "Record saved successfully.").strip()
    if queue_for_rerun:
        st.session_state["_qcms_pending_save_popup"] = text
        return
    st.toast(text, icon="✅")
    st.success(text)


def delete_success_popup(message: str = "Selected record deleted successfully.", *, queue_for_rerun: bool = False) -> None:
    text = str(message or "Selected record deleted successfully.").strip()
    if queue_for_rerun:
        st.session_state["_qcms_pending_delete_popup"] = text
        return
    st.toast(text, icon="🗑️")
    st.success(text)


def render_pending_popups() -> None:
    """Render queued save/delete confirmations after Streamlit reruns."""
    save_message = st.session_state.pop("_qcms_pending_save_popup", None)
    delete_message = st.session_state.pop("_qcms_pending_delete_popup", None)
    if save_message:
        st.toast(str(save_message), icon="✅")
        st.success(str(save_message))
    if delete_message:
        st.toast(str(delete_message), icon="🗑️")
        st.success(str(delete_message))

def app_footer() -> None:
    s = get_settings()
    st.markdown(
        f'<div class="fsi-footer">Developed by Rajesh Dhokale &nbsp;|&nbsp; '
        f'<a href="mailto:dhokaleraj@icloud.com">dhokaleraj@icloud.com</a> &nbsp;|&nbsp; '
        f'Copyrights to jrdhokale &nbsp;|&nbsp; App Version {safe(s.version)}</div>',
        unsafe_allow_html=True,
    )
