from __future__ import annotations

# Legacy build marker retained for regression compatibility: BUILD 4111-ZOHO-VISIBLE-SHELL
# Legacy Export Shipment shell build marker retained for regression compatibility: BUILD 4112-EXPORT-SHELL

import base64
import re
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
    if key in {"ACCEPTED", "APPROVED", "PASS", "RELEASED", "ACTIVE", "FINAL", "COMPLETED"}:
        return "background-color:#DCFCE7;color:#14532D;font-weight:700"
    if key in {"ACCEPTED_UNDER_RESERVE"}:
        return "background-color:#FFEDD5;color:#9A3412;font-weight:700"
    if key in {"ON_HOLD", "HOLD", "HOLD_PENDING_INSPECTION", "HOLD_PENDING_OSP_INSPECTION", "PART_RECEIVED", "APPROVAL_PENDING", "PARTIALLY_APPROVED"}:
        return "background-color:#FEF3C7;color:#92400E;font-weight:700"
    if key in {"REJECTED", "FAIL", "LOCKED"}:
        return "background-color:#FEE2E2;color:#991B1B;font-weight:700"
    if key in {"PENDING", "DRAFT", "NOT_EVALUATED", "AT_VENDOR", "AT_OSP"}:
        return "background-color:#DBEAFE;color:#1E3A8A;font-weight:700"
    if key in {"NOT_APPLICABLE", "INACTIVE", "CLOSED"}:
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
    """Enterprise ERP design system with clear hierarchy and collision-safe spacing."""
    st.markdown(r"""
    <style>
    :root{
      --erp-navy:#0B2D4D;--erp-blue:#1469A8;--erp-indigo:#4F46E5;
      --erp-teal:#0F766E;--erp-amber:#B45309;--erp-red:#B42318;
      --erp-bg:#F3F6F9;--erp-legacy-bg:#EEF2F5;--erp-surface:#FFFFFF;--erp-soft:#F8FAFC;
      --erp-border:#C7D3DE;--erp-border-strong:#8FA6B8;
      --erp-text:#17212B;--erp-muted:#5C6B79;--fsi-text:#17212B;
      --erp-font:Aptos,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
    }
    /* legacy density marker: min-height:31px!important */
    html,body,.stApp,[class*="css"],button,input,textarea,select{font-family:var(--erp-font)!important;}
    .stApp,div[data-testid="stAppViewContainer"],section.main{background:var(--erp-bg)!important;color:var(--erp-text)!important;}
    header[data-testid="stHeader"]{height:0!important;background:transparent!important;}
    #MainMenu,footer,div[data-testid="stToolbar"],div[data-testid="stDecoration"],section[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important;}
    .block-container{padding:.8rem 1rem 1.5rem!important;max-width:1880px!important;}
    h1,h2,h3,h4,h5,h6{color:var(--erp-navy)!important;margin:.25rem 0 .45rem!important;font-weight:800!important;line-height:1.25!important;overflow:visible!important;}
    p{font-size:13px!important;line-height:1.35!important;margin:.12rem 0!important;}

    .st-key-fsi_shell>div[data-testid="stVerticalBlockBorderWrapper"]{
      background:linear-gradient(110deg,#082F5C 0%,#073B73 44%,#0A66A8 100%)!important;
      border:1px solid #7FB2D8!important;border-radius:14px!important;padding:.72rem .85rem!important;
      box-shadow:0 5px 16px rgba(3,35,70,.20)!important;overflow:visible!important;
    }
    .fsi-company-block{display:flex;align-items:center;gap:10px;min-width:0}.fsi-logo-card{display:flex;align-items:center;justify-content:center;background:#fff;border-radius:9px;padding:6px 8px;min-width:70px;height:52px;box-shadow:0 1px 5px rgba(0,0,0,.14)}
    .fsi-logo{width:68px;max-height:38px;object-fit:contain;object-position:center}.fsi-company-name{font-size:16px;font-weight:900;color:#fff;line-height:1.05;white-space:normal}.fsi-company-sub{font-size:9px;font-weight:750;color:#D6E9FA;margin-top:4px;line-height:1.15;letter-spacing:.02em}
    .fsi-header-title{text-align:center;font-size:25px;line-height:.93;font-weight:950;color:#fff;letter-spacing:.01em;text-shadow:0 1px 2px rgba(0,0,0,.18)}.fsi-header-page{text-align:center;color:#D7EBFB;font-size:9px;font-weight:750;margin-top:6px;text-transform:uppercase;letter-spacing:.08em}
    .fsi-user{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.30);border-radius:10px;padding:7px 9px;text-align:right;line-height:1.25}.fsi-user-name{font-size:11px;font-weight:850;color:#fff}.fsi-user-meta{font-size:9px;color:#E8F3FB}.fsi-live{display:inline-flex;align-items:center;gap:4px;margin-top:4px;padding:2px 6px;border-radius:999px;background:rgba(255,255,255,.22);color:#fff;border:1px solid rgba(255,255,255,.25);font-size:8px;font-weight:850}.fsi-dot{width:6px;height:6px;border-radius:50%;background:#73F0B3}
    .st-key-fsi_shell .stButton>button{background:rgba(255,255,255,.18)!important;border-color:rgba(255,255,255,.45)!important;color:#fff!important;min-height:34px!important}.st-key-fsi_shell .stButton>button *{color:#fff!important}

    .st-key-fsi_top_nav>div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border:1px solid #C8D6E3!important;border-radius:12px!important;padding:.5rem .65rem .65rem!important;margin:.55rem 0 .45rem!important;box-shadow:0 4px 14px rgba(11,45,77,.10)!important;overflow:visible!important;}
    .fsi-top-menu-title{font-size:10px;font-weight:900;letter-spacing:.06em;color:#0B3F72;padding:.12rem .1rem .4rem;margin:0 0 .28rem;border-bottom:1px solid #D8E2EA}
    [class*="st-key-menu_"]>div[data-testid="stVerticalBlockBorderWrapper"]{border:0!important;padding:0!important;background:transparent!important;overflow:visible!important;}
    [class*="st-key-menu_"] div[data-testid="stPageLink"] a,[class*="st-key-menu_"] .stButton>button{
      min-height:38px!important;padding:.35rem .45rem!important;justify-content:center!important;text-align:center!important;
      border-radius:8px!important;border:1px solid transparent!important;background:transparent!important;color:#17212B!important;
      font-size:11px!important;font-weight:750!important;text-decoration:none!important;box-shadow:none!important;white-space:normal!important;line-height:1.15!important;width:100%!important;
    }
    [class*="st-key-menu_"] div[data-testid="stPageLink"] a *,[class*="st-key-menu_"] .stButton>button *{color:inherit!important;fill:currentColor!important;}
    [class*="st-key-menu_"] div[data-testid="stPageLink"] a:hover,[class*="st-key-menu_"] .stButton>button:hover{background:#EAF3FB!important;border-color:#B9D0E2!important;color:#0A4C80!important;}
    [class*="st-key-menu_active_"] div[data-testid="stPageLink"] a,[class*="st-key-menu_active_"] .stButton>button{background:linear-gradient(100deg,#08477D,#0D78C7)!important;border-color:#075087!important;color:#fff!important;box-shadow:0 3px 8px rgba(7,76,128,.22)!important;font-weight:900!important;}
    [class*="st-key-menu_active_"] div[data-testid="stPageLink"] a *,[class*="st-key-menu_active_"] .stButton>button *{color:#fff!important;fill:#fff!important;}

    .st-key-fsi_subnav>div[data-testid="stVerticalBlockBorderWrapper"]{background:var(--erp-surface)!important;border:1px solid var(--erp-border)!important;border-radius:9px!important;padding:.35rem .4rem!important;margin:0 0 .55rem!important;overflow:visible!important;}
    .st-key-fsi_subnav div[data-testid="stPageLink"] a{min-height:34px!important;padding:.3rem .45rem!important;border-radius:7px!important;border:1px solid #0B4F78!important;background:#0B6FA4!important;color:#fff!important;font-size:11px!important;font-weight:800!important;text-decoration:none!important;justify-content:center!important;white-space:normal!important;line-height:1.15!important;}
    .st-key-fsi_subnav div[data-testid="stPageLink"] a *{color:inherit!important;fill:currentColor!important;}
    .st-key-fsi_subnav [data-testid="column"]:nth-child(5n+2) div[data-testid="stPageLink"] a{background:#4F46E5!important;border-color:#3730A3!important;color:#fff!important;}
    .st-key-fsi_subnav [data-testid="column"]:nth-child(5n+3) div[data-testid="stPageLink"] a{background:#0F766E!important;border-color:#0B544F!important;color:#fff!important;}
    .st-key-fsi_subnav [data-testid="column"]:nth-child(5n+4) div[data-testid="stPageLink"] a{background:#B45309!important;border-color:#7C2D12!important;color:#fff!important;}
    .st-key-fsi_subnav div[data-testid="stPageLink"] a:hover{border-color:var(--erp-blue)!important;filter:brightness(.99)!important;}

    .fsi-page-head{display:flex;align-items:center;min-height:60px;margin:.25rem 0 .85rem;padding:.72rem .9rem;background:var(--erp-surface);border:1px solid var(--erp-border);border-left:5px solid var(--erp-blue);border-radius:10px;box-shadow:0 2px 6px rgba(11,45,77,.07);overflow:visible;position:relative;z-index:1;}
    .fsi-kicker,.fsi-page-subtitle,.fsi-context{display:none!important}.fsi-page-title{font-size:22px;font-weight:850;color:var(--erp-navy);line-height:1.25;white-space:normal;overflow-wrap:anywhere;padding:0;margin:0;}

    .fsi-section-bar{display:block;position:relative;z-index:1;overflow:visible;background:var(--erp-navy);color:#fff;padding:10px 13px;border:1px solid #08243D;border-radius:8px;font-size:13px;font-weight:850;line-height:1.4;letter-spacing:.01em;margin:1rem 0 .65rem;box-shadow:0 1px 4px rgba(11,45,77,.13);white-space:normal;overflow-wrap:anywhere;min-height:39px;}
    .fsi-section-note{display:none}.fsi-info-strip{padding:.48rem .65rem;border:1px solid var(--erp-border);border-left:4px solid var(--erp-blue);border-radius:7px;background:#fff;margin:.35rem 0 .55rem}.fsi-info-strip strong,.fsi-info-strip span{font-size:12px!important;}

    div[data-testid="stHorizontalBlock"]{gap:.78rem!important;}div[data-testid="stVerticalBlock"]{gap:.7rem!important;}
    div[data-testid="column"]{min-width:0!important;overflow:visible!important;}
    div[data-testid="stForm"],details[data-testid="stExpander"]{border-radius:9px!important;overflow:visible!important;}
    div[data-testid="stForm"]{background:#fff!important;border:1px solid var(--erp-border)!important;padding:.75rem .85rem!important;box-shadow:0 1px 4px rgba(11,45,77,.05)!important;margin-bottom:.55rem!important;}
    label[data-testid="stWidgetLabel"]{margin-bottom:.22rem!important;overflow:visible!important;}
    label[data-testid="stWidgetLabel"] p{font-size:12px!important;font-weight:800!important;color:#26394A!important;line-height:1.25!important;white-space:normal!important;overflow:visible!important;}
    input,textarea,[data-baseweb="select"]{font-size:13px!important;color:var(--fsi-text)!important;}
    input::placeholder,textarea::placeholder{color:#7B8B98!important;opacity:1!important;}
    [data-baseweb="select"] span{color:var(--erp-text)!important;line-height:1.2!important;}
    [data-baseweb="input"],[data-baseweb="select"]>div,textarea{background:#fff!important;border:1px solid var(--erp-border-strong)!important;border-radius:7px!important;min-height:38px!important;box-shadow:none!important;overflow:visible!important;}
    [data-baseweb="input"]:focus-within,[data-baseweb="select"]>div:focus-within,textarea:focus{border-color:var(--erp-blue)!important;box-shadow:0 0 0 3px rgba(11,111,164,.15)!important;}
    textarea{min-height:76px!important;}[data-testid="stNumberInput"] button{min-height:36px!important;}
    [data-testid="stFileUploaderDropzone"]{min-height:72px!important;padding:.5rem!important;border:1px dashed var(--erp-border-strong)!important;background:#FAFCFE!important;border-radius:8px!important;}
    [data-testid="stFileUploaderDropzone"] small{font-size:10px!important;}
    [data-testid="stCaptionContainer"] p{font-size:11px!important;color:var(--erp-muted)!important;line-height:1.3!important;}

    .stButton>button,.stDownloadButton>button,.stFormSubmitButton>button,.stLinkButton>a{min-height:36px!important;border-radius:7px!important;border:1px solid var(--erp-blue)!important;font-size:12px!important;font-weight:850!important;padding:.32rem .65rem!important;white-space:normal!important;line-height:1.15!important;}
    .stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:var(--erp-blue)!important;color:#fff!important;}
    .stButton>button:hover,.stFormSubmitButton>button:hover,.stDownloadButton>button:hover{border-color:var(--erp-navy)!important;box-shadow:0 2px 5px rgba(11,45,77,.12)!important;}

    div[data-testid="stDataFrame"],div[data-testid="stDataEditor"]{border:1px solid var(--erp-border-strong)!important;border-radius:8px!important;background:#fff!important;overflow:hidden!important;margin:.25rem 0 .6rem!important;}
    div[data-testid="stDataFrame"] *,div[data-testid="stDataEditor"] *{font-size:11px!important;}
    [data-testid="stAlert"]{padding:.5rem .65rem!important;border-radius:7px!important;margin:.3rem 0 .55rem!important;}[data-testid="stAlert"] p{font-size:12px!important;line-height:1.35!important;}

    .fsi-status-grid,.fsi-kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:11px;margin:.28rem 0 .78rem;}
    .fsi-status-card,.fsi-kpi{background:#fff;border:1px solid var(--erp-border);border-left:5px solid var(--erp-blue);border-radius:9px;padding:11px 12px;min-height:88px;box-shadow:0 2px 6px rgba(11,45,77,.06);overflow:visible;}
    .fsi-status-card .label,.fsi-kpi-label{font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.025em;color:#607284;white-space:normal;line-height:1.35;overflow-wrap:anywhere;}
    .fsi-status-card .value,.fsi-kpi-value{font-size:18px;font-weight:850;color:var(--erp-navy);line-height:1.2;margin:7px 0 4px;overflow-wrap:anywhere;}
    .fsi-status-card .foot,.fsi-kpi-foot{font-size:10px;color:#6B7D8D;white-space:normal;line-height:1.35;overflow-wrap:anywhere;}
    .fsi-status-accepted{border-left-color:#087443;background:#ECFDF3}.fsi-status-reserve{border-left-color:#EA580C;background:#FFF7ED}.fsi-status-hold{border-left-color:#D97706;background:#FFFBEB}.fsi-status-rejected{border-left-color:#B42318;background:#FEF2F2}.fsi-status-pending{border-left-color:#D97706;background:#FFF7ED}


    [class*="st-key-fsi_module_subnav_"]>div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border:1px solid #C8D6E3!important;border-radius:10px!important;padding:.52rem .62rem!important;margin:.05rem 0 .72rem!important;box-shadow:0 2px 8px rgba(11,45,77,.06)!important;overflow:visible!important;}
    .fsi-module-subnav-title{font-size:9px;font-weight:900;letter-spacing:.08em;color:#0B4F78;margin:0 0 .3rem .08rem;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a{min-height:40px!important;padding:.36rem .45rem!important;font-size:10.5px!important;font-weight:750!important;background:#F7FAFC!important;border:1px solid #D2DEE8!important;border-radius:7px!important;color:#17324A!important;justify-content:center!important;text-align:center!important;line-height:1.25!important;white-space:normal!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a:hover{background:#E8F3FB!important;border-color:#1469A8!important;color:#0B4F7A!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a[aria-current="page"]{background:#0B5E9A!important;border-color:#084773!important;color:#fff!important;font-weight:900!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a[aria-current="page"] *{color:#fff!important;fill:#fff!important;}
    [class*="st-key-master_card_"]>div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border:1px solid var(--erp-border)!important;border-left:5px solid var(--card-color,var(--erp-blue))!important;border-radius:10px!important;min-height:164px!important;padding:.75rem!important;margin-bottom:.45rem!important;box-shadow:0 2px 7px rgba(11,45,77,.07)!important;overflow:visible!important;}
    .fsi-master-card-head{display:grid;grid-template-columns:42px minmax(0,1fr);align-items:center;gap:11px;min-height:70px;padding:.15rem 0 .85rem!important;color:var(--erp-text)!important;}
    .fsi-master-card-icon{display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:8px;background:color-mix(in srgb,var(--card-color,var(--erp-blue)) 14%,white);font-size:19px;}
    .fsi-master-card-title{font-size:15px;font-weight:850;color:var(--erp-navy);line-height:1.2;white-space:normal;overflow-wrap:anywhere;}
    .fsi-master-card-count{display:block;font-size:11px;font-weight:750;color:#66788A;margin-top:6px;line-height:1.25;min-height:14px;}.fsi-master-card-body{display:none}
    [class*="st-key-master_card_"] div[data-testid="stHorizontalBlock"]{margin-top:.2rem!important;}
    [class*="st-key-master_card_"] div[data-testid="stPageLink"] a{min-height:40px!important;font-size:12px!important;padding:.34rem .42rem!important;background:#0B6FA4!important;border:1px solid #07577F!important;color:#fff!important;border-radius:7px!important;}
    [class*="st-key-master_card_"] div[data-testid="stPageLink"] a,[class*="st-key-master_card_"] div[data-testid="stPageLink"] a *{color:#fff!important;fill:#fff!important;text-shadow:none!important;}

    [class*="st-key-dashboard_card_"]>div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border:1px solid var(--erp-border)!important;border-left:5px solid var(--dash-color,var(--erp-blue))!important;border-radius:10px!important;padding:.65rem!important;min-height:122px!important;box-shadow:0 2px 7px rgba(11,45,77,.07)!important;overflow:visible!important;}
    .fsi-dashboard-card{padding:.55rem .6rem!important;margin:-.1rem -.1rem .55rem!important;border-radius:8px!important;border:1px solid color-mix(in srgb,var(--dash-color,var(--erp-blue)) 34%,white)!important;background:linear-gradient(135deg,color-mix(in srgb,var(--dash-color,var(--erp-blue)) 16%,white),#fff 76%)!important}.fsi-dashboard-count{font-size:10px;font-weight:800;color:color-mix(in srgb,var(--dash-color,var(--erp-blue)) 78%,#17212B);line-height:1.2}.fsi-dashboard-title{font-size:15px;font-weight:850;color:var(--erp-navy);margin:4px 0;line-height:1.2;white-space:normal;overflow-wrap:anywhere}.fsi-dashboard-text{display:none}
    [class*="st-key-dashboard_card_"] div[data-testid="stPageLink"] a{min-height:34px!important;font-size:11px!important;background:var(--dash-color,#0B6FA4)!important;color:#fff!important;border:1px solid color-mix(in srgb,var(--dash-color,#0B6FA4) 72%,#000)!important;border-radius:7px!important;}
    [class*="st-key-dashboard_card_"] div[data-testid="stPageLink"] a *{color:#fff!important;fill:#fff!important;}

    .fsi-flow-wrap{display:flex;align-items:stretch;gap:10px;margin:.3rem 0 .9rem;overflow-x:auto;padding:4px 2px 8px;scrollbar-width:thin;}
    .fsi-flow-step{--flow-color:#1469A8;--flow-bg:#EFF6FF;--flow-icon-bg:#DBEAFE;display:flex;align-items:center;gap:10px;flex:1 1 205px;min-width:185px;min-height:84px;border:1px solid #C9D7E3;border-left:6px solid var(--flow-color);border-radius:10px;padding:12px 13px;background:var(--flow-bg);box-shadow:0 2px 7px rgba(11,45,77,.07);overflow:visible;}
    .fsi-flow-copy{min-width:0;padding:1px 0}.fsi-flow-icon{width:31px;height:31px;display:flex;align-items:center;justify-content:center;border-radius:50%;font-size:15px;font-weight:950;background:var(--flow-icon-bg);color:var(--flow-color);border:1px solid rgba(11,45,77,.10);flex:0 0 auto;}
    .fsi-flow-label{font-size:12px;font-weight:900;color:#10314D;line-height:1.28;white-space:normal;overflow-wrap:anywhere}.fsi-flow-detail{font-size:10px;color:#5C7082;margin-top:5px;line-height:1.3;white-space:normal;overflow-wrap:anywhere}
    .fsi-flow-arrow{display:flex;align-items:center;justify-content:center;color:#567187;font-size:28px;font-weight:900;padding:0 1px;min-width:14px;}
    .fsi-flow-tone-0{--flow-color:#1469A8;--flow-bg:#EAF4FB;--flow-icon-bg:#D7ECFA}.fsi-flow-tone-1{--flow-color:#6D28D9;--flow-bg:#F5F3FF;--flow-icon-bg:#EDE9FE}.fsi-flow-tone-2{--flow-color:#B45309;--flow-bg:#FFF7ED;--flow-icon-bg:#FFEDD5}.fsi-flow-tone-3{--flow-color:#0F766E;--flow-bg:#F0FDFA;--flow-icon-bg:#CCFBF1}.fsi-flow-tone-4{--flow-color:#15803D;--flow-bg:#F0FDF4;--flow-icon-bg:#DCFCE7}.fsi-flow-tone-5{--flow-color:#4338CA;--flow-bg:#EEF2FF;--flow-icon-bg:#E0E7FF}.fsi-flow-tone-6{--flow-color:#BE123C;--flow-bg:#FFF1F2;--flow-icon-bg:#FFE4E6}.fsi-flow-tone-7{--flow-color:#0E7490;--flow-bg:#ECFEFF;--flow-icon-bg:#CFFAFE}
    .fsi-flow-current{box-shadow:0 0 0 2px var(--flow-color),0 4px 10px rgba(11,45,77,.10)}.fsi-flow-current .fsi-flow-detail{font-weight:800;color:var(--flow-color)}
    .fsi-flow-complete .fsi-flow-icon{background:#DCFCE7;color:#166534;border-color:#86EFAC}.fsi-flow-complete{border-top-color:#86EFAC;border-bottom-color:#86EFAC}
    .fsi-flow-pending{opacity:.88}.fsi-flow-pending .fsi-flow-icon{background:#fff;color:var(--flow-color);border:2px solid var(--flow-color)}
    .fsi-flow-hold{--flow-color:#D97706;--flow-bg:#FFFBEB;--flow-icon-bg:#FEF3C7}.fsi-flow-rejected{--flow-color:#B42318;--flow-bg:#FEF2F2;--flow-icon-bg:#FEE2E2}

    .fsi-template-strip{background:#fff;border:1px solid var(--erp-border);border-radius:9px;padding:.5rem .6rem;margin:.15rem 0 .6rem;}
    .fsi-chip{display:inline-block;padding:3px 7px;border-radius:999px;font-size:9px;font-weight:850;}
    .fsi-footer{text-align:center;font-size:10px;color:#50677B;margin-top:.8rem;padding:.5rem .25rem;border-top:1px solid #C6D8E5;font-family:var(--erp-font)!important;font-weight:600}.fsi-footer a{color:#0B6FAE!important;text-decoration:none!important;font-weight:700}

    /* QSMS 4.9.3 — high-contrast Export Shipment shell compatibility.
       Streamlit 1.60+ can insert an extra wrapper between a keyed container and
       stVerticalBlockBorderWrapper. Descendant selectors keep the blue shell,
       menu panels and fonts visible on every rerun and browser size. */
    html,body,.stApp,div[data-testid="stAppViewContainer"],section.main{
      background:linear-gradient(180deg,#E9F2FA 0%,#F5F9FC 46%,#EDF4FA 100%)!important;
      color:#14283A!important;-webkit-font-smoothing:antialiased!important;text-rendering:optimizeLegibility!important;
    }
    .stApp [data-stale="true"]{opacity:1!important;}

    .st-key-fsi_shell,
    [class*="st-key-fsi_shell"]{
      background:linear-gradient(110deg,#073462 0%,#073E78 46%,#0A68AC 100%)!important;
      border:1px solid #6EA9D5!important;border-radius:14px!important;
      box-shadow:0 6px 18px rgba(3,35,70,.24)!important;overflow:visible!important;
    }
    .st-key-fsi_shell div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_shell"] div[data-testid="stVerticalBlockBorderWrapper"]{
      background:transparent!important;border:0!important;border-radius:14px!important;
      padding:.72rem .85rem!important;box-shadow:none!important;overflow:visible!important;
    }
    [class*="st-key-fsi_shell"] .fsi-company-name,
    [class*="st-key-fsi_shell"] .fsi-header-title,
    [class*="st-key-fsi_shell"] .fsi-user-name{color:#FFFFFF!important;opacity:1!important;text-shadow:0 1px 2px rgba(0,0,0,.20)!important;}
    [class*="st-key-fsi_shell"] .fsi-company-sub,
    [class*="st-key-fsi_shell"] .fsi-header-page,
    [class*="st-key-fsi_shell"] .fsi-user-meta{color:#DCEEFE!important;opacity:1!important;}
    [class*="st-key-fsi_shell"] .fsi-user{background:rgba(255,255,255,.15)!important;border-color:rgba(255,255,255,.34)!important;}
    [class*="st-key-fsi_shell"] .stButton>button,
    [class*="st-key-fsi_shell"] button[data-testid="stBaseButton-secondary"]{
      background:rgba(255,255,255,.16)!important;border-color:rgba(255,255,255,.48)!important;color:#FFFFFF!important;
    }
    [class*="st-key-fsi_shell"] .stButton>button *,
    [class*="st-key-fsi_shell"] button[data-testid="stBaseButton-secondary"] *{color:#FFFFFF!important;fill:#FFFFFF!important;}

    .st-key-fsi_top_nav,
    [class*="st-key-fsi_top_nav"]{
      background:#FFFFFF!important;border:1px solid #BED0DF!important;border-radius:12px!important;
      box-shadow:0 5px 15px rgba(11,45,77,.12)!important;overflow:visible!important;
    }
    .st-key-fsi_top_nav div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_top_nav"] div[data-testid="stVerticalBlockBorderWrapper"]{
      background:transparent!important;border:0!important;border-radius:12px!important;
      padding:.5rem .65rem .65rem!important;box-shadow:none!important;overflow:visible!important;
    }
    .fsi-top-menu-title{color:#083D70!important;font-family:var(--erp-font)!important;font-weight:900!important;opacity:1!important;}
    [class*="st-key-menu_"] div[data-testid="stPageLink"] a,
    [class*="st-key-menu_"] .stButton>button{
      background:#F3F8FC!important;border-color:#D1E0EB!important;color:#173550!important;
      font-family:var(--erp-font)!important;font-weight:800!important;opacity:1!important;
    }
    [class*="st-key-menu_"] div[data-testid="stPageLink"] a *,
    [class*="st-key-menu_"] .stButton>button *{color:inherit!important;fill:currentColor!important;opacity:1!important;}
    [class*="st-key-menu_"] div[data-testid="stPageLink"] a:hover,
    [class*="st-key-menu_"] .stButton>button:hover{background:#E4F1FA!important;border-color:#8FB8D6!important;color:#083F70!important;}
    [class*="st-key-menu_active_"] div[data-testid="stPageLink"] a,
    [class*="st-key-menu_active_"] .stButton>button{
      background:linear-gradient(100deg,#07508A 0%,#0B75BD 100%)!important;
      border-color:#064879!important;color:#FFFFFF!important;box-shadow:0 4px 10px rgba(7,76,128,.25)!important;font-weight:900!important;
    }
    [class*="st-key-menu_active_"] div[data-testid="stPageLink"] a *,
    [class*="st-key-menu_active_"] .stButton>button *{color:#FFFFFF!important;fill:#FFFFFF!important;}

    [class*="st-key-fsi_module_subnav_"]{
      background:#FFFFFF!important;border:1px solid #C5D6E3!important;border-radius:10px!important;
      box-shadow:0 3px 10px rgba(11,45,77,.08)!important;overflow:visible!important;
    }
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stVerticalBlockBorderWrapper"]{
      background:transparent!important;border:0!important;border-radius:10px!important;
      padding:.4rem .52rem!important;box-shadow:none!important;overflow:visible!important;
    }
    .fsi-module-subnav-title{color:#0A4778!important;font-weight:900!important;opacity:1!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a{
      background:#F2F7FB!important;border-color:#C9D9E5!important;color:#173550!important;
      font-family:var(--erp-font)!important;font-weight:800!important;opacity:1!important;
    }
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a *{color:inherit!important;fill:currentColor!important;opacity:1!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a[aria-current="page"]{
      background:linear-gradient(100deg,#07508A,#0B75BD)!important;border-color:#064879!important;color:#FFFFFF!important;
    }

    @media(max-width:1100px){.block-container{padding:.5rem .55rem 1rem!important}.fsi-logo{width:108px}.fsi-app-title{font-size:17px}.fsi-app-sub{display:none}.fsi-status-grid,.fsi-kpi-grid{grid-template-columns:repeat(3,1fr)}[class*="st-key-menu_"] div[data-testid="stPageLink"] a{font-size:11px!important;padding:.32rem .25rem!important;}}
    @media(max-width:760px){.block-container{padding:.4rem .35rem .8rem!important}.fsi-page-title{font-size:18px}.fsi-status-grid,.fsi-kpi-grid{grid-template-columns:repeat(2,1fr)}.fsi-user{display:none}.st-key-fsi_top_nav div[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;}[class*="st-key-menu_"] div[data-testid="stPageLink"] a{min-height:38px!important;}}

    /* QCMS 4.9.7 — NPD / APQP real-time process cards */
    .npd-process-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:.35rem 0 .95rem;align-items:stretch;}
    .npd-process-card{min-height:132px;border:1px solid #CBD9E5;border-left:6px solid #7890A4;border-radius:11px;padding:12px 13px;background:#F8FBFD;box-shadow:0 2px 7px rgba(11,45,77,.08);overflow:visible;}
    .npd-process-card .npd-op{font-size:10px;font-weight:900;letter-spacing:.05em;text-transform:uppercase;color:#60788C;}
    .npd-process-card .npd-process-name{font-size:14px;font-weight:900;color:#0B3558;line-height:1.25;margin:5px 0 8px;white-space:normal;overflow-wrap:anywhere;}
    .npd-process-card .npd-process-status{font-size:11px;font-weight:900;text-transform:uppercase;margin-bottom:5px;}
    .npd-process-card .npd-process-date{font-size:10px;line-height:1.35;color:#5B7082;white-space:normal;overflow-wrap:anywhere;}
    .npd-completed{border-left-color:#15803D;background:#F0FDF4}.npd-completed .npd-process-status{color:#15803D}
    .npd-completed_late{border-left-color:#6B7280;background:#F8FAFC}.npd-completed_late .npd-process-status{color:#4B5563}
    .npd-in_progress{border-left-color:#2563EB;background:#EFF6FF;box-shadow:0 0 0 1px #93C5FD,0 3px 9px rgba(37,99,235,.12)}.npd-in_progress .npd-process-status{color:#1D4ED8}
    .npd-pending{border-left-color:#D97706;background:#FFF7ED}.npd-pending .npd-process-status{color:#B45309}
    .npd-overdue{border-left-color:#B91C1C;background:#FEF2F2;box-shadow:0 0 0 1px #FCA5A5,0 3px 9px rgba(185,28,28,.11)}.npd-overdue .npd-process-status{color:#B91C1C}
    .npd-hold{border-left-color:#7C3AED;background:#F5F3FF}.npd-hold .npd-process-status{color:#6D28D9}
    .npd-not_planned{border-left-color:#64748B;background:#F8FAFC}.npd-not_planned .npd-process-status{color:#475569}

    /* QCMS 4.10.2 — all-parts NPD horizontal card rows */
    .npd-order-status-row{display:flex;gap:10px;align-items:stretch;margin:.45rem 0 .75rem;padding:8px;background:#FFFFFF;border:1px solid #C7D8E5;border-radius:12px;box-shadow:0 2px 8px rgba(11,45,77,.08);overflow-x:auto;}
    .npd-order-summary-card{flex:0 0 238px;min-width:238px;background:linear-gradient(145deg,#0B416F,#0B75B7);color:#FFFFFF;border-radius:9px;padding:12px 13px;box-shadow:0 2px 6px rgba(8,59,110,.18);}
    .npd-order-part{font-size:17px;font-weight:950;line-height:1.15;}.npd-order-name{font-size:11px;font-weight:800;opacity:.95;margin:4px 0 9px;line-height:1.25;}
    .npd-order-meta{font-size:9.5px;line-height:1.45;overflow-wrap:anywhere;}.npd-order-progress{display:inline-block;margin-top:8px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);border-radius:999px;padding:3px 8px;font-size:9px;font-weight:900;}
    .npd-row-process-strip{display:flex;gap:8px;align-items:stretch;min-width:max-content;}
    .npd-row-process-card{flex:0 0 185px;width:185px;min-height:116px;border:1px solid #CBD9E5;border-left:6px solid #7890A4;border-radius:9px;padding:9px 10px;background:#F8FBFD;box-shadow:0 2px 5px rgba(11,45,77,.06);}
    .npd-row-process-card .npd-op{font-size:9px;font-weight:900;letter-spacing:.04em;color:#617789;text-transform:uppercase}.npd-row-process-card .npd-process-name{font-size:12px;font-weight:900;color:#0B3558;margin:4px 0 7px;line-height:1.2}.npd-row-process-card .npd-process-status{font-size:10px;font-weight:900;margin-bottom:5px;text-transform:uppercase}.npd-row-process-card .npd-process-date{font-size:8.8px;line-height:1.3;color:#607284}
    .npd-empty-process{padding:30px 16px;color:#607284;font-weight:800;}

    /* QCMS 4.10.9 — readability: approximately 10% stronger visual font weight */
    html,body,.stApp,div[data-testid="stAppViewContainer"],section.main{font-weight:450!important;}
    p,[data-testid="stMarkdownContainer"],div[data-testid="stCaptionContainer"] p,[data-testid="stAlert"] p{font-weight:500!important;}
    label[data-testid="stWidgetLabel"] p{font-weight:880!important;}
    input,textarea,[data-baseweb="select"],[data-baseweb="select"] span{font-weight:520!important;}
    .stButton>button,.stDownloadButton>button,.stFormSubmitButton>button,.stLinkButton>a{font-weight:900!important;}
    div[data-testid="stDataFrame"] *,div[data-testid="stDataEditor"] *{font-weight:500!important;}
    [class*="st-key-menu_"] div[data-testid="stPageLink"] a,[class*="st-key-menu_"] .stButton>button{font-weight:850!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a{font-weight:850!important;}
    .fsi-master-card-count,.fsi-dashboard-count,.fsi-order-meta,.npd-order-meta{font-weight:800!important;}

/* QCMS 4.10.5 — centered authentication experience inspired by the shipment system */
.stApp:has([class*="st-key-qcms_login_shell"]),
div[data-testid="stAppViewContainer"]:has([class*="st-key-qcms_login_shell"]){
  background:linear-gradient(180deg,#EFF4F8 0%,#F7FAFC 100%)!important;
}
[class*="st-key-qcms_login_shell"]{
  max-width:560px!important;margin:4.4vh auto 1rem!important;padding:0!important;
  background:transparent!important;border:none!important;box-shadow:none!important;overflow:visible!important;
}
[class*="st-key-qcms_login_shell"] > div[data-testid="stVerticalBlock"]{gap:.85rem!important;}
.qcms-login-header-card{background:#fff;border:1px solid #B8CBE0;border-radius:18px;padding:18px 20px 16px;box-shadow:0 6px 18px rgba(10,55,93,.08);text-align:center;}
.qcms-login-header-logo{display:flex;justify-content:center;align-items:center;margin-bottom:10px;}
.qcms-login-logo{width:156px;max-height:54px;object-fit:contain}.qcms-login-logo-fallback{font-size:28px;font-weight:900;color:#0B416F}
.qcms-login-header-title{font-size:27px;font-weight:950;line-height:1.03;letter-spacing:.01em;color:#0D5EAB;margin-bottom:6px;text-transform:uppercase;}
.qcms-login-header-subtitle{font-size:11px;font-weight:650;line-height:1.4;color:#5F7486;}
.qcms-login-field-caption{font-size:12px;font-weight:700;color:#24384C;margin:0 0 .35rem;}
[class*="st-key-qcms_login_shell"] div[data-testid="stForm"]{border:none!important;background:transparent!important;padding:0!important;box-shadow:none!important;}
[class*="st-key-qcms_login_shell"] label[data-testid="stWidgetLabel"] p{font-size:14px!important;font-weight:900!important;color:#123A5B!important;}
[class*="st-key-qcms_login_shell"] [data-baseweb="input"]{min-height:46px!important;border-radius:10px!important;border:1px solid #BED0E1!important;background:#FFFFFF!important;box-shadow:0 1px 3px rgba(10,55,93,.04)!important;}
[class*="st-key-qcms_login_shell"] [data-baseweb="input"]:focus-within{border-color:#0E6FAF!important;box-shadow:0 0 0 3px rgba(14,111,175,.10)!important;}
[class*="st-key-qcms_login_shell"] .stFormSubmitButton>button{min-height:44px!important;padding:0 26px!important;border-radius:9px!important;background:linear-gradient(180deg,#0C79BE 0%,#075E95 100%)!important;border:none!important;box-shadow:0 8px 16px rgba(9,103,159,.16)!important;font-size:14px!important;font-weight:900!important;}
[class*="st-key-qcms_login_shell"] details[data-testid="stExpander"]{background:#FFFFFF!important;border:1px solid #D2DEE9!important;border-radius:11px!important;box-shadow:0 3px 10px rgba(10,55,93,.05)!important;}
[class*="st-key-qcms_login_shell"] details[data-testid="stExpander"] summary{font-weight:850!important;color:#25425C!important;}
.qcms-login-divider{height:1px;background:#D9E2EA;margin:.55rem 0 .3rem;}
.qcms-login-footer{padding:10px 4px 0;text-align:center;font-size:12px;font-weight:700;color:#203548;line-height:1.45;}
.qcms-login-footer span{display:inline-block;padding:0 10px;color:#7B8B98;}
@media(max-width:900px){
  [class*="st-key-qcms_login_shell"]{max-width:92vw!important;margin:1.2rem auto .6rem!important;}
  .qcms-login-header-card{padding:16px 14px 14px;}
  .qcms-login-header-title{font-size:22px;}
  .qcms-login-footer{font-size:11px;}
  .qcms-login-footer span{padding:0 6px;}
}

    </style>
    """, unsafe_allow_html=True)



    # QCMS 4.11.1 — Zoho-inspired clean white/blue enterprise shell visibility layer.
    # Visual principles only: high-contrast white header, dark readable navigation,
    # restrained blue accents, generous whitespace and subtle warm/sky background depth.
    st.markdown(r"""
    <style>
    :root{
      --qcms-zoho-blue:#1884D8;
      --qcms-zoho-blue-dark:#0E5F9F;
      --qcms-zoho-blue-soft:#EAF5FF;
      --qcms-zoho-ink:#121820;
      --qcms-zoho-text:#26323D;
      --qcms-zoho-muted:#687783;
      --qcms-zoho-line:#DDE4EA;
      --qcms-zoho-surface:#FFFFFF;
      --qcms-zoho-soft:#F7FAFC;
      --qcms-zoho-warm:#FFF7ED;
    }

    html,body,.stApp,[class*="css"],button,input,textarea,select{
      font-family:Aptos,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif!important;
    }
    .stApp,div[data-testid="stAppViewContainer"],section.main{
      background:
        radial-gradient(circle at 52% 0%,rgba(255,217,174,.20),transparent 27%),
        radial-gradient(circle at 86% 18%,rgba(196,231,255,.23),transparent 31%),
        linear-gradient(180deg,#FFFFFF 0%,#FAFCFE 30%,#F5FAFD 100%)!important;
      color:var(--qcms-zoho-text)!important;
    }
    .block-container{padding:.46rem .85rem 1.15rem!important;max-width:1900px!important;}
    .stApp [data-stale="true"]{opacity:1!important;}

    /* --- HIGH-CONTRAST APPLICATION HEADER --- */
    .st-key-fsi_shell,[class*="st-key-fsi_shell"]{
      background:transparent!important;border:0!important;box-shadow:none!important;
      opacity:1!important;visibility:visible!important;
    }
    .st-key-fsi_shell>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_shell"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_shell"] div[data-testid="stVerticalBlockBorderWrapper"]{
      position:relative!important;
      background:#FFFFFF!important;
      border:1px solid #E0E6EB!important;
      border-radius:12px!important;
      padding:.48rem .66rem!important;
      box-shadow:0 5px 18px rgba(37,68,91,.08)!important;
      overflow:visible!important;
      opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"]>div[data-testid="stVerticalBlockBorderWrapper"]:before{
      content:"";position:absolute;left:0;right:0;top:0;height:3px;border-radius:12px 12px 0 0;
      background:linear-gradient(90deg,#0D6EBC 0%,#27A5F1 54%,#78C8F5 100%);
    }
    [class*="st-key-fsi_shell"] .fsi-company-block{gap:9px!important;opacity:1!important;visibility:visible!important;}
    [class*="st-key-fsi_shell"] .fsi-logo-card{
      height:42px!important;min-width:70px!important;padding:4px 8px!important;
      border:1px solid #E3E8EC!important;border-radius:8px!important;box-shadow:none!important;background:#fff!important;
    }
    [class*="st-key-fsi_shell"] .fsi-logo{width:64px!important;max-height:33px!important;opacity:1!important;}
    [class*="st-key-fsi_shell"] .fsi-company-name{
      font-size:13px!important;font-weight:900!important;color:#17202A!important;opacity:1!important;
      visibility:visible!important;text-shadow:none!important;letter-spacing:.01em!important;
    }
    [class*="st-key-fsi_shell"] .fsi-company-sub{
      display:block!important;font-size:8px!important;font-weight:800!important;color:#73808B!important;
      opacity:1!important;visibility:visible!important;margin-top:2px!important;letter-spacing:.055em!important;
    }
    [class*="st-key-fsi_shell"] .fsi-header-title{
      display:block!important;font-size:18px!important;line-height:1.08!important;font-weight:900!important;
      color:#111827!important;opacity:1!important;visibility:visible!important;text-shadow:none!important;
      letter-spacing:-.005em!important;white-space:normal!important;
    }
    [class*="st-key-fsi_shell"] .fsi-header-page{
      display:block!important;font-size:8px!important;color:#73818D!important;opacity:1!important;visibility:visible!important;
      margin-top:3px!important;letter-spacing:.065em!important;font-weight:800!important;
    }
    [class*="st-key-fsi_shell"] .fsi-user{
      display:block!important;background:#F7FAFC!important;border:1px solid #DEE6EC!important;border-radius:8px!important;
      padding:5px 8px!important;box-shadow:none!important;opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"] .fsi-user-name{
      font-size:10px!important;font-weight:900!important;color:#1D2A35!important;opacity:1!important;visibility:visible!important;text-shadow:none!important;
    }
    [class*="st-key-fsi_shell"] .fsi-user-meta{
      font-size:8px!important;color:#6B7B87!important;opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"] .fsi-live{
      margin-top:2px!important;padding:1px 5px!important;background:#ECF8F1!important;color:#247248!important;
      border:1px solid #C8E5D4!important;font-size:7px!important;font-weight:900!important;
    }
    [class*="st-key-fsi_shell"] .fsi-dot{width:5px!important;height:5px!important;background:#36A269!important;}
    [class*="st-key-fsi_shell"] .stButton>button,
    [class*="st-key-fsi_shell"] div[data-testid="stPageLink"] a{
      min-height:31px!important;border-radius:7px!important;background:#FFFFFF!important;border:1px solid #D7E0E7!important;
      color:#23313D!important;box-shadow:none!important;font-size:9px!important;font-weight:850!important;
      opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"] .stButton>button *,
    [class*="st-key-fsi_shell"] div[data-testid="stPageLink"] a *{color:inherit!important;fill:currentColor!important;opacity:1!important;}
    [class*="st-key-fsi_shell"] .stButton>button:hover,
    [class*="st-key-fsi_shell"] div[data-testid="stPageLink"] a:hover{
      background:var(--qcms-zoho-blue-soft)!important;border-color:#9BCDF1!important;color:#0E5F9F!important;
    }

    /* --- ZOHO-STYLE SIMPLE APP NAVIGATION: white, dark labels, blue active state --- */
    .st-key-fsi_top_nav,[class*="st-key-fsi_top_nav"]{
      background:transparent!important;border:0!important;box-shadow:none!important;opacity:1!important;visibility:visible!important;
    }
    .st-key-fsi_top_nav>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_top_nav"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_top_nav"] div[data-testid="stVerticalBlockBorderWrapper"]{
      background:#FFFFFF!important;border:1px solid #E1E7EC!important;border-radius:10px!important;
      padding:.18rem .30rem .20rem!important;margin:.34rem 0 .28rem!important;
      box-shadow:0 2px 9px rgba(31,57,77,.045)!important;overflow:visible!important;
      opacity:1!important;visibility:visible!important;
    }
    .fsi-top-menu-title{display:none!important;}
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] div[data-testid="stPageLink"] a,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] .stButton>button{
      min-height:34px!important;padding:.28rem .26rem!important;border-radius:7px!important;border:1px solid transparent!important;
      background:#FFFFFF!important;color:#202A33!important;font-size:10.5px!important;font-weight:800!important;
      line-height:1.08!important;box-shadow:none!important;opacity:1!important;visibility:visible!important;
      text-decoration:none!important;
    }
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] div[data-testid="stPageLink"] a *,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] .stButton>button *{
      color:inherit!important;fill:currentColor!important;opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] div[data-testid="stPageLink"] a:hover,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] .stButton>button:hover{
      background:#F3F9FE!important;border-color:#D2E8F8!important;color:#0E65A8!important;
    }
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_active_"] div[data-testid="stPageLink"] a,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_active_"] .stButton>button{
      background:#EAF5FF!important;border-color:#A9D5F4!important;color:#0C67AB!important;
      box-shadow:inset 0 -3px 0 #1784D8!important;font-weight:900!important;
    }
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_active_"] div[data-testid="stPageLink"] a *,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_active_"] .stButton>button *{
      color:#0C67AB!important;fill:#0C67AB!important;opacity:1!important;
    }

    /* Compact second-level navigation */
    [class*="st-key-fsi_module_subnav_"]{background:transparent!important;border:0!important;box-shadow:none!important;}
    [class*="st-key-fsi_module_subnav_"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stVerticalBlockBorderWrapper"]{
      background:#FBFCFD!important;border:1px solid #E2E8ED!important;border-radius:8px!important;
      padding:.20rem .30rem!important;box-shadow:none!important;overflow:visible!important;
    }
    .fsi-module-subnav-title{
      font-size:8px!important;font-weight:900!important;letter-spacing:.08em!important;color:#74818B!important;
      text-transform:uppercase!important;padding:.04rem .14rem .12rem!important;
    }
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a{
      min-height:30px!important;padding:.20rem .28rem!important;border-radius:6px!important;background:#FFFFFF!important;
      border:1px solid #E1E7EB!important;color:#34424D!important;font-size:9px!important;font-weight:800!important;box-shadow:none!important;
      opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a *{color:inherit!important;fill:currentColor!important;opacity:1!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a:hover{
      background:#F2F8FD!important;border-color:#C8E1F4!important;color:#0D66A8!important;
    }
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a[aria-current="page"]{
      background:#E9F5FF!important;border-color:#A8D5F4!important;color:#0D66A8!important;
      box-shadow:inset 3px 0 0 #1884D8!important;font-weight:900!important;
    }

    /* Minimal, readable content hierarchy */
    .fsi-page-head{
      min-height:36px!important;margin:.20rem 0 .46rem!important;padding:.34rem .10rem .38rem!important;
      background:transparent!important;border:0!important;border-bottom:1px solid #DFE5EA!important;border-left:0!important;
      border-radius:0!important;box-shadow:none!important;
    }
    .fsi-page-title{font-size:20px!important;line-height:1.1!important;font-weight:900!important;color:#17212B!important;letter-spacing:-.01em!important;}
    .fsi-section-bar{
      min-height:29px!important;margin:.62rem 0 .38rem!important;padding:.27rem .06rem .30rem!important;background:transparent!important;
      border:0!important;border-bottom:1px solid #D7E2EA!important;border-radius:0!important;box-shadow:none!important;
      color:#245B80!important;font-size:11px!important;font-weight:900!important;letter-spacing:.05em!important;text-transform:uppercase!important;
    }
    .fsi-info-strip{padding:.38rem .52rem!important;border:1px solid #DEE7ED!important;border-left:3px solid #52A7E1!important;border-radius:7px!important;background:#FBFDFF!important;margin:.25rem 0 .42rem!important;}

    .fsi-status-grid,.fsi-kpi-grid{grid-template-columns:repeat(auto-fit,minmax(132px,1fr))!important;gap:8px!important;margin:.18rem 0 .52rem!important;}
    .fsi-status-card,.fsi-kpi{
      border:1px solid #E0E6EA!important;border-top:3px solid #63AEE0!important;border-left:1px solid #E0E6EA!important;
      border-radius:8px!important;padding:8px 10px!important;min-height:64px!important;background:#FFFFFF!important;
      box-shadow:0 2px 7px rgba(32,59,78,.045)!important;
    }
    .fsi-status-card .label,.fsi-kpi-label{font-size:8.5px!important;color:#6E7B85!important;letter-spacing:.04em!important;}
    .fsi-status-card .value,.fsi-kpi-value{font-size:15px!important;color:#1F2D38!important;margin:4px 0 2px!important;}
    .fsi-status-card .foot,.fsi-kpi-foot{font-size:8.5px!important;color:#7A858D!important;}

    [class*="st-key-master_card_"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-dashboard_card_"]>div[data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="stForm"],details[data-testid="stExpander"]{
      border:1px solid #E0E6EB!important;border-radius:9px!important;background:#FFFFFF!important;
      box-shadow:0 2px 7px rgba(31,57,77,.04)!important;
    }
    div[data-testid="stForm"]{padding:.72rem!important;}
    label[data-testid="stWidgetLabel"] p{font-size:10.5px!important;color:#3A4853!important;font-weight:850!important;}
    [data-baseweb="input"],[data-baseweb="select"]>div,textarea{
      border-color:#D0D9E0!important;border-radius:7px!important;background:#FFFFFF!important;box-shadow:none!important;color:#22303A!important;
    }
    [data-baseweb="input"]{min-height:37px!important;}
    [data-baseweb="input"]:focus-within,[data-baseweb="select"]>div:focus-within,textarea:focus{
      border-color:#69B3E4!important;box-shadow:0 0 0 3px rgba(24,132,216,.10)!important;
    }
    .stButton>button,.stFormSubmitButton>button,.stDownloadButton>button,.stLinkButton>a{
      min-height:34px!important;border-radius:7px!important;font-size:10px!important;font-weight:850!important;box-shadow:none!important;
    }
    .stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{
      background:#1884D8!important;border-color:#0F70BA!important;color:#fff!important;
    }
    .stButton>button[kind="primary"] *, .stFormSubmitButton>button[kind="primary"] *{color:#fff!important;}
    div[data-testid="stDataFrame"],div[data-testid="stDataEditor"]{border:1px solid #DDE5EB!important;border-radius:8px!important;overflow:hidden!important;background:#fff!important;}
    [data-testid="stAlert"]{border-radius:7px!important;box-shadow:none!important;font-size:10px!important;}
    .fsi-footer{font-size:8.8px!important;color:#7A858D!important;margin-top:.70rem!important;padding:.40rem .2rem!important;border-top:1px solid #DDE4E9!important;}
    .fsi-footer a{color:#0D70B8!important;}

    @media(max-width:1100px){
      [class*="st-key-fsi_shell"] .fsi-header-title{font-size:15px!important;}
      [class*="st-key-fsi_shell"] .fsi-user{display:none!important;}
      [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] div[data-testid="stPageLink"] a{font-size:9.5px!important;}
      .fsi-status-grid,.fsi-kpi-grid{grid-template-columns:repeat(3,1fr)!important;}
    }
    @media(max-width:760px){
      .block-container{padding:.3rem .35rem .7rem!important;}
      [class*="st-key-fsi_shell"] .fsi-company-name{font-size:11px!important;}
      [class*="st-key-fsi_shell"] .fsi-company-sub{display:none!important;}
      [class*="st-key-fsi_shell"] .fsi-header-title{font-size:12px!important;}
      .fsi-status-grid,.fsi-kpi-grid{grid-template-columns:repeat(2,1fr)!important;}
      .st-key-fsi_top_nav div[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;}
    }
    </style>
    """, unsafe_allow_html=True)


    # QCMS 4.11.2 — Export Shipment-inspired navy header and module navigation shell.
    # Reference: the user's live Export Shipment UI. Keep the QCMS functionality and
    # central Records routing unchanged; only the shell/header/navigation presentation changes.
    st.markdown(r"""
    <style>
    :root{
      --qcms-export-navy:#073462;
      --qcms-export-navy-mid:#073E78;
      --qcms-export-blue:#0A68AC;
      --qcms-export-active:#0B78C5;
      --qcms-export-bg:#EEF5FB;
      --qcms-export-surface:#FFFFFF;
      --qcms-export-line:#C9D9E7;
      --qcms-export-text:#121D2B;
      --qcms-export-muted:#60778B;
    }

    html,body,.stApp,[class*="css"],button,input,textarea,select{
      font-family:Aptos,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif!important;
    }
    .stApp,div[data-testid="stAppViewContainer"],section.main{
      background:linear-gradient(180deg,#EAF2F9 0%,#F7FAFD 38%,#EEF5FB 100%)!important;
      color:var(--qcms-export-text)!important;
    }
    .block-container{padding:.72rem .78rem 1.2rem!important;max-width:1920px!important;}
    .stApp [data-stale="true"]{opacity:1!important;}

    /* Header: match Export Shipment's dark navy-to-blue company shell. */
    .st-key-fsi_shell,[class*="st-key-fsi_shell"]{
      background:linear-gradient(110deg,var(--qcms-export-navy) 0%,var(--qcms-export-navy-mid) 47%,var(--qcms-export-blue) 100%)!important;
      border:1px solid #6EA9D5!important;border-radius:15px!important;
      box-shadow:0 7px 20px rgba(3,35,70,.22)!important;overflow:visible!important;
      opacity:1!important;visibility:visible!important;
    }
    .st-key-fsi_shell>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_shell"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_shell"] div[data-testid="stVerticalBlockBorderWrapper"]{
      background:transparent!important;border:0!important;border-radius:15px!important;
      padding:.72rem .82rem!important;box-shadow:none!important;overflow:visible!important;
    }
    [class*="st-key-fsi_shell"] .fsi-company-block{gap:10px!important;align-items:center!important;}
    [class*="st-key-fsi_shell"] .fsi-logo-card{
      height:54px!important;min-width:72px!important;padding:5px 8px!important;background:#FFFFFF!important;
      border:1px solid rgba(255,255,255,.70)!important;border-radius:10px!important;box-shadow:0 2px 6px rgba(0,0,0,.14)!important;
    }
    [class*="st-key-fsi_shell"] .fsi-logo{width:68px!important;max-height:42px!important;opacity:1!important;}
    [class*="st-key-fsi_shell"] .fsi-company-name{
      color:#FFFFFF!important;font-size:15px!important;font-weight:950!important;line-height:1.02!important;
      text-shadow:0 1px 2px rgba(0,0,0,.20)!important;opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"] .fsi-company-sub{
      display:block!important;color:#D9ECFB!important;font-size:8.7px!important;font-weight:850!important;
      margin-top:4px!important;letter-spacing:.02em!important;opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"] .fsi-header-title{
      color:#FFFFFF!important;font-size:25px!important;font-weight:950!important;line-height:.98!important;
      text-align:center!important;letter-spacing:.005em!important;text-shadow:0 1px 2px rgba(0,0,0,.22)!important;
      opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"] .fsi-header-page{
      color:#D9ECFB!important;font-size:8.4px!important;font-weight:800!important;margin-top:5px!important;
      letter-spacing:.06em!important;opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"] .fsi-user{
      background:rgba(255,255,255,.15)!important;border:1px solid rgba(255,255,255,.30)!important;
      border-radius:11px!important;padding:7px 9px!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.08)!important;
      opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"] .fsi-user-name{color:#FFFFFF!important;font-size:10.5px!important;font-weight:950!important;text-shadow:none!important;}
    [class*="st-key-fsi_shell"] .fsi-user-meta{color:#E6F2FC!important;font-size:8.5px!important;font-weight:750!important;}
    [class*="st-key-fsi_shell"] .fsi-user-pills{display:flex!important;justify-content:flex-end!important;gap:5px!important;flex-wrap:wrap!important;margin-top:5px!important;}
    [class*="st-key-fsi_shell"] .fsi-user-pill{
      display:inline-block!important;padding:2px 7px!important;border-radius:999px!important;
      background:rgba(255,255,255,.21)!important;border:1px solid rgba(255,255,255,.22)!important;
      color:#FFFFFF!important;font-size:7.7px!important;font-weight:900!important;line-height:1.25!important;
    }
    [class*="st-key-fsi_shell"] .fsi-live{
      margin-top:0!important;padding:2px 7px!important;background:rgba(115,240,179,.16)!important;color:#E9FFF3!important;
      border:1px solid rgba(115,240,179,.35)!important;font-size:7.5px!important;font-weight:900!important;
    }
    [class*="st-key-fsi_shell"] .fsi-dot{width:5px!important;height:5px!important;background:#73F0B3!important;}
    [class*="st-key-fsi_shell"] .stButton>button,
    [class*="st-key-fsi_shell"] div[data-testid="stPageLink"] a{
      min-height:29px!important;border-radius:7px!important;background:rgba(255,255,255,.16)!important;
      border:1px solid rgba(255,255,255,.40)!important;color:#FFFFFF!important;box-shadow:none!important;
      font-size:8.5px!important;font-weight:850!important;opacity:1!important;visibility:visible!important;
    }
    [class*="st-key-fsi_shell"] .stButton>button *,
    [class*="st-key-fsi_shell"] div[data-testid="stPageLink"] a *{color:#FFFFFF!important;fill:#FFFFFF!important;opacity:1!important;}
    [class*="st-key-fsi_shell"] .stButton>button:hover,
    [class*="st-key-fsi_shell"] div[data-testid="stPageLink"] a:hover{background:rgba(255,255,255,.24)!important;border-color:rgba(255,255,255,.62)!important;}

    /* MODULES heading is a separate white rounded bar, as in Export Shipment. */
    .st-key-fsi_top_nav,[class*="st-key-fsi_top_nav"]{
      background:transparent!important;border:0!important;box-shadow:none!important;opacity:1!important;visibility:visible!important;
    }
    .st-key-fsi_top_nav>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_top_nav"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_top_nav"] div[data-testid="stVerticalBlockBorderWrapper"]{
      background:transparent!important;border:0!important;border-radius:0!important;padding:0!important;margin:.62rem 0 .20rem!important;
      box-shadow:none!important;overflow:visible!important;
    }
    .fsi-top-menu-title{
      display:block!important;background:#FFFFFF!important;border:1px solid #CCDCE9!important;border-radius:12px!important;
      box-shadow:0 4px 12px rgba(10,57,95,.08)!important;color:#073D70!important;
      font-size:9.5px!important;font-weight:950!important;letter-spacing:.045em!important;
      padding:.68rem .82rem!important;margin:0 0 .48rem!important;line-height:1!important;
    }
    [class*="st-key-fsi_top_nav"] div[data-testid="stHorizontalBlock"]{
      gap:.38rem!important;align-items:stretch!important;background:transparent!important;
    }
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"]>div[data-testid="stVerticalBlockBorderWrapper"]{
      background:transparent!important;border:0!important;padding:0!important;margin:0!important;box-shadow:none!important;
    }
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] [data-testid="stIconMaterial"]{display:none!important;}
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] div[data-testid="stPageLink"] a,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] .stButton>button{
      min-height:39px!important;padding:.32rem .28rem!important;border-radius:8px!important;border:1px solid transparent!important;
      background:transparent!important;color:#131E2C!important;font-size:10.5px!important;font-weight:760!important;
      line-height:1.08!important;box-shadow:none!important;text-decoration:none!important;opacity:1!important;visibility:visible!important;
      justify-content:center!important;text-align:center!important;
    }
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] div[data-testid="stPageLink"] a *,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] .stButton>button *{color:inherit!important;fill:currentColor!important;opacity:1!important;}
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] div[data-testid="stPageLink"] a:hover,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] .stButton>button:hover{
      background:#E1EFFB!important;border-color:#BDD6E9!important;color:#084E84!important;
    }
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_active_"] div[data-testid="stPageLink"] a,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_active_"] .stButton>button{
      background:linear-gradient(105deg,#084C84 0%,#0C7BC7 100%)!important;border-color:#07568F!important;
      color:#FFFFFF!important;box-shadow:0 5px 12px rgba(7,76,128,.21)!important;font-weight:900!important;
    }
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_active_"] div[data-testid="stPageLink"] a *,
    [class*="st-key-fsi_top_nav"] [class*="st-key-menu_active_"] .stButton>button *{color:#FFFFFF!important;fill:#FFFFFF!important;}

    /* Second-level menu stays compact and uses the same navy/blue language. */
    [class*="st-key-fsi_module_subnav_"]{background:transparent!important;border:0!important;box-shadow:none!important;}
    [class*="st-key-fsi_module_subnav_"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stVerticalBlockBorderWrapper"]{
      background:#FFFFFF!important;border:1px solid #D2E0EB!important;border-radius:10px!important;
      padding:.28rem .36rem .34rem!important;box-shadow:0 3px 10px rgba(10,57,95,.055)!important;overflow:visible!important;
    }
    .fsi-module-subnav-title{
      display:block!important;color:#0A477A!important;font-size:8.3px!important;font-weight:950!important;letter-spacing:.075em!important;
      padding:.04rem .12rem .18rem!important;text-transform:uppercase!important;
    }
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a{
      min-height:30px!important;padding:.20rem .26rem!important;border-radius:6px!important;background:#FFFFFF!important;
      border:1px solid #DCE6EE!important;color:#243747!important;font-size:9px!important;font-weight:800!important;box-shadow:none!important;
    }
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a:hover{background:#EAF4FC!important;border-color:#BDD8EB!important;color:#07558F!important;}
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a[aria-current="page"]{
      background:linear-gradient(105deg,#084C84,#0C7BC7)!important;border-color:#07568F!important;color:#FFFFFF!important;
      box-shadow:0 2px 7px rgba(7,76,128,.16)!important;font-weight:900!important;
    }
    [class*="st-key-fsi_module_subnav_"] div[data-testid="stPageLink"] a[aria-current="page"] *{color:#FFFFFF!important;fill:#FFFFFF!important;}

    /* Content remains minimal so the strong shell does not make pages bulky. */
    .fsi-page-head{margin:.22rem 0 .46rem!important;padding:.34rem .08rem .38rem!important;border-bottom:1px solid #CADBE8!important;}
    .fsi-page-title{color:#0B3558!important;font-size:20px!important;}
    .fsi-section-bar{color:#0B527F!important;border-bottom-color:#C9DBE8!important;}
    .fsi-footer{border-top-color:#C7D9E6!important;color:#60778B!important;}
    .fsi-footer a{color:#0A68AC!important;}

    @media(max-width:1120px){
      [class*="st-key-fsi_shell"] .fsi-header-title{font-size:20px!important;}
      [class*="st-key-fsi_shell"] .fsi-company-name{font-size:13px!important;}
      [class*="st-key-fsi_top_nav"] [class*="st-key-menu_"] div[data-testid="stPageLink"] a{font-size:9.3px!important;}
    }
    /* QCMS 4.11.4 — dedicated header action rail: no profile/action overlap. */
    [class*="st-key-fsi_header_actions"]{
      background:transparent!important;border:0!important;box-shadow:none!important;
      display:block!important;position:relative!important;z-index:3!important;
    }
    [class*="st-key-fsi_header_actions"]>div[data-testid="stVerticalBlockBorderWrapper"],
    [class*="st-key-fsi_header_actions"] div[data-testid="stVerticalBlockBorderWrapper"]{
      background:transparent!important;border:0!important;padding:0!important;margin:0!important;box-shadow:none!important;
      display:flex!important;flex-direction:column!important;gap:6px!important;overflow:visible!important;
    }
    [class*="st-key-fsi_header_actions"] div[data-testid="stPageLink"],
    [class*="st-key-fsi_header_actions"] .stButton{margin:0!important;padding:0!important;}
    [class*="st-key-fsi_header_actions"] div[data-testid="stPageLink"] a,
    [class*="st-key-fsi_header_actions"] .stButton>button{
      width:100%!important;min-height:32px!important;margin:0!important;padding:.28rem .42rem!important;
      border-radius:8px!important;background:rgba(255,255,255,.16)!important;
      border:1px solid rgba(255,255,255,.42)!important;color:#FFFFFF!important;font-size:8.8px!important;font-weight:850!important;
      display:flex!important;align-items:center!important;justify-content:center!important;box-shadow:none!important;
    }
    [class*="st-key-fsi_header_actions"] div[data-testid="stPageLink"] a *,
    [class*="st-key-fsi_header_actions"] .stButton>button *{color:#FFFFFF!important;fill:#FFFFFF!important;}
    [class*="st-key-fsi_shell"] .fsi-user{min-height:66px!important;display:flex!important;flex-direction:column!important;justify-content:center!important;}

    @media(max-width:980px){
      [class*="st-key-fsi_header_actions"] div[data-testid="stPageLink"] a,
      [class*="st-key-fsi_header_actions"] .stButton>button{font-size:8px!important;padding:.22rem .28rem!important;}
    }
    @media(max-width:760px){
      .block-container{padding:.45rem .35rem .8rem!important;}
      [class*="st-key-fsi_shell"] .fsi-company-sub{display:none!important;}
      [class*="st-key-fsi_shell"] .fsi-header-title{font-size:15px!important;}
      [class*="st-key-fsi_shell"] .fsi-user{display:none!important;}
      [class*="st-key-fsi_header_actions"]{display:none!important;}
      .st-key-fsi_top_nav div[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;}
      .fsi-top-menu-title{padding:.55rem .65rem!important;}
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


def render_shell_header(profile: Mapping[str, Any], active_page: str) -> bool:
    s = get_settings()
    now = datetime.now(ZoneInfo(s.timezone))
    uri = logo_data_uri()
    logo = f'<img class="fsi-logo" src="{uri}" alt="FSI">' if uri else '<b>FSI</b>'
    with st.container(border=True, key="fsi_shell"):
        # QCMS 4.11.4: user information and actions use separate columns so
        # Account / Exit can never overlap the profile card at desktop widths.
        c1, c2, c3, c4 = st.columns([2.8, 4.8, 2.25, 1.25], vertical_alignment="center")
        with c1:
            st.markdown(
                f'<div class="fsi-company-block"><div class="fsi-logo-card">{logo}</div>'
                f'<div><div class="fsi-company-name">FOUR STAR INDUSTRIES</div>'
                f'<div class="fsi-company-sub">QUALITY CONTROL MONITORING SYSTEM</div></div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                '<div class="fsi-header-title">QUALITY CONTROL<br>MONITORING SYSTEM</div>'
                f'<div class="fsi-header-page">{safe(active_page)} · BUILD 4114-COMPLAINT-MEDIA-HEADER-FIX</div>',
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f'<div class="fsi-user"><div class="fsi-user-name">User: {safe(profile.get("full_name") or "Quality User")}</div>'
                f'<div class="fsi-user-meta">Role: {safe(role_label(profile))}</div>'
                f'<div class="fsi-user-pills"><span class="fsi-live"><span class="fsi-dot"></span>{"PREVIEW" if is_preview_session() else "LIVE"}</span>'
                f'<span class="fsi-user-pill">v{safe(s.version)}</span><span class="fsi-user-pill">{now.strftime("%d-%m-%Y %H:%M")}</span></div></div>',
                unsafe_allow_html=True,
            )
        with c4:
            with st.container(key="fsi_header_actions"):
                account_page = (st.session_state.get("_qsms_pages") or {}).get("my-account")
                if account_page is not None:
                    st.page_link(account_page, label="Account", icon=":material/manage_accounts:", width="stretch")
                if st.button("Exit", key="fsi_signout", width="stretch"):
                    return True
    return False

def render_side_navigation(pages: Sequence[Any]) -> None:
    return None


def subpage_navigation(*items: tuple[str, str, str]) -> None:
    """Page-level navigation is intentionally suppressed.

    QSMS uses one persistent main menu and one module submenu. Older page-level
    links remain callable for compatibility but no longer render duplicate menus.
    """
    return None



def module_submenu(title: str, *items: tuple[str, str, str], max_columns: int = 8) -> None:
    """Render a persistent second-level menu for the active top-level module."""
    valid = [(path, label, icon) for path, label, icon in items if path in st.session_state.get("_qsms_pages", {})]
    if not valid:
        return
    slug = re.sub(r"[^a-z0-9]+", "_", title.casefold()).strip("_") or "module"
    with st.container(border=True, key=f"fsi_module_subnav_{slug}"):
        st.markdown(f'<div class="fsi-module-subnav-title">{safe(title)}</div>', unsafe_allow_html=True)
        for start in range(0, len(valid), max_columns):
            group = valid[start:start + max_columns]
            cols = st.columns(len(group), gap="small")
            for col, (path, label, icon) in zip(cols, group):
                with col:
                    st.page_link(st.session_state["_qsms_pages"][path], label=label, width="stretch")

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
    # Data-heavy pages deliberately show only one clear title; taglines and context
    # badges are suppressed to prevent clutter and field overlap.
    st.markdown(f'<div class="fsi-page-head"><div class="fsi-page-title">{safe(title)}</div></div>', unsafe_allow_html=True)


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
