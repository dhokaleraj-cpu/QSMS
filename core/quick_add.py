"""QCMS R37 · the "＋" quick-add menu in the website header (new transaction / new e-mail / new query).

Pure catalogue + permission filter (unit-tested without Streamlit) and one small Streamlit renderer
used by ``core.ui.render_shell_header``. Each action opens its entry screen in "new" mode: the
module's edit-session keys are cleared first, so the screen does not reopen the last edited record.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class QuickAction:
    group: str                      # New transaction | New e-mail | New query
    label: str
    icon: str                       # Material icon (":material/...:")
    route: str                      # website route (streamlit_app PAGE_ITEMS)
    module: str | None = None       # permission module key (None = everyone who can log in)
    right: str = "can_create"       # permission needed
    clear: tuple[str, ...] = ()     # session keys removed before opening ("new" mode)
    set_state: tuple[tuple[str, Any], ...] = field(default_factory=tuple)


GROUPS: tuple[str, ...] = ("New transaction", "New e-mail", "New query", "New dashboard")

QUICK_ACTIONS: tuple[QuickAction, ...] = (
    QuickAction("New transaction", "Customer Order", ":material/receipt_long:", "supply-customer-orders", "SUPPLY_CHAIN",
                clear=("supply_customer_order_edit_select",)),
    QuickAction("New transaction", "Purchase Order", ":material/request_quote:", "supply-purchase-orders", "SUPPLY_CHAIN",
                clear=("supply_po_edit_request_id",)),
    QuickAction("New transaction", "Indirect PO", ":material/shopping_bag:", "indirect-po", "SUPPLY_CHAIN",
                clear=("indirect_po_edit_id", "indirect_po_edit_select")),
    QuickAction("New transaction", "Indirect Requisition", ":material/playlist_add:", "indirect-requisition", "SUPPLY_CHAIN"),
    QuickAction("New transaction", "RM Procurement", ":material/shopping_cart:", "supply-rm-procurement", "SUPPLY_CHAIN",
                clear=("supply_rm_po_edit_select",)),
    QuickAction("New transaction", "RM Receipt", ":material/local_shipping:", "supply-rm-receipt", "SUPPLY_CHAIN"),
    QuickAction("New transaction", "RM to Forging", ":material/swap_horiz:", "supply-rm-dispatch", "SUPPLY_CHAIN"),
    QuickAction("New transaction", "RMTC", ":material/fact_check:", "rmtc-entry", "RMTC_ENTRY",
                clear=("edit_rmtc_id",), set_state=(("rmtc_entry_mode", "new"),)),
    QuickAction("New transaction", "Material Inward", ":material/input:", "inward-entry", "MATERIAL_INWARD",
                clear=("edit_inward_id", "supply_rm_po_link_id", "supply_customer_order_link_id")),
    QuickAction("New transaction", "MetLAB Report", ":material/science:", "metlab-entry", "METLAB_REPORT", clear=("edit_metlab_id",)),
    QuickAction("New transaction", "Bend Test Report", ":material/architecture:", "bend-test-entry", "METLAB_REPORT", clear=("edit_metlab_id",)),
    QuickAction("New transaction", "Dimensional Report", ":material/straighten:", "dimensional-entry", "DIMENSIONAL_REPORT",
                clear=("edit_dimensional_id",)),
    QuickAction("New transaction", "OSP Material Out", ":material/local_shipping:", "osp-material-out", "OSP_TRANSACTIONS",
                clear=("osp_material_out_manage_id",)),
    QuickAction("New transaction", "Customer Complaint", ":material/record_voice_over:", "customer-complaint", "COMPLAINT_MANAGEMENT",
                clear=("selected_customer_complaint",)),
    QuickAction("New transaction", "Supplier Complaint", ":material/feedback:", "supplier-complaint", "COMPLAINT_MANAGEMENT",
                clear=("selected_supplier_complaint",)),
    QuickAction("New transaction", "NPD Order", ":material/timeline:", "npd-status", "NPD_APQP", clear=("npd_order_edit",)),
    QuickAction("New transaction", "APQP Project", ":material/assignment_turned_in:", "apqp", "NPD_APQP",
                clear=("apqp_project_edit_request_id",)),
    QuickAction("New transaction", "Calibration Record", ":material/straighten:", "calibration-validation", "CALIBRATION_VALIDATION"),
    QuickAction("New transaction", "Standard Room Inspection", ":material/biotech:", "standard-room-inspection", "CALIBRATION_VALIDATION",
                clear=("std_room_choice", "selected_standard_room_id")),
    QuickAction("New transaction", "QC Calculation", ":material/calculate:", "qc-tools", "QC_CALCULATION_TOOLS"),
    QuickAction("New e-mail", "New e-mail", ":material/mail:", "email-send", None, right=""),
    QuickAction("New query", "Search & AI query", ":material/smart_toy:", "global-search", None, right="",
                set_state=(("_qcms_global_search_open_ai", True),)),
    QuickAction("New dashboard", "New dashboard", ":material/dashboard_customize:", "kpi-dashboards", None, right="",
                set_state=(("_kpi_open_view", "My Dashboards"),)),
)

_PERM_CACHE_KEY = "_qcms_quick_add_perms"
_PERM_TTL_SECONDS = 300


def allowed_actions(
    available_routes: Iterable[str],
    can: Callable[[str, str], bool],
    actions: Sequence[QuickAction] = QUICK_ACTIONS,
) -> list[QuickAction]:
    """Actions whose route exists in this build and that the user may perform (``can(module, right)``)."""
    routes = set(available_routes)
    out: list[QuickAction] = []
    for action in actions:
        if action.route not in routes:
            continue
        if action.module and action.right and not can(action.module, action.right):
            continue
        out.append(action)
    return out


def grouped(actions: Sequence[QuickAction]) -> dict[str, list[QuickAction]]:
    groups: dict[str, list[QuickAction]] = {}
    for group in GROUPS:
        items = [a for a in actions if a.group == group]
        if items:
            groups[group] = items
    return groups


def prepare_new_mode(state: Any, action: QuickAction) -> None:
    """Clear the module's edit-session keys and set the "new" flags (``state`` = st.session_state or a dict)."""
    for key in action.clear:
        try:
            state.pop(key, None)
        except Exception:
            pass
    for key, value in action.set_state:
        state[key] = value


def permission_checker(profile: Mapping[str, Any]) -> Callable[[str, str], bool]:
    """``module_permissions`` cached per user in the session for 5 minutes (the header renders on every page)."""
    import streamlit as st
    from core.access import module_permissions

    user = f"{profile.get('tenant_id') or ''}:{profile.get('id') or profile.get('email') or ''}"
    cache = st.session_state.get(_PERM_CACHE_KEY)
    if not isinstance(cache, dict) or cache.get("user") != user or time.time() - float(cache.get("at") or 0) > _PERM_TTL_SECONDS:
        cache = {"user": user, "at": time.time(), "rights": {}}
        st.session_state[_PERM_CACHE_KEY] = cache
    rights: dict[str, dict] = cache["rights"]

    def can(module: str, right: str) -> bool:
        if module not in rights:
            try:
                rights[module] = dict(module_permissions(profile, module) or {})
            except Exception:
                rights[module] = {}
        return bool(rights[module].get(right))

    return can


def render_quick_add(profile: Mapping[str, Any], *, key: str = "qcms_quick_add") -> None:
    """The "＋" popover: grouped quick actions, only routes this user can create."""
    import streamlit as st

    pages = st.session_state.get("_qsms_pages") or {}
    if not pages:
        return
    actions = allowed_actions(pages.keys(), permission_checker(profile or {}))
    st.markdown(
        "<style>.st-key-qcms_header_quick_add button{background:#FFFFFF!important;color:#0B6E70!important;border:1px solid #CFE3E3!important;"
        "border-radius:999px!important;font-size:20px!important;font-weight:800!important;min-height:38px!important;padding:0 6px!important}"
        ".st-key-qcms_header_quick_add button:hover{background:#E8F4F4!important}"
        ".qcms-quick-add-head{font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#0B6E70;margin:6px 0 4px}</style>",
        unsafe_allow_html=True,
    )
    with st.popover("＋", help="New transaction, new e-mail, new query or new dashboard", width="stretch"):
        if not actions:
            st.caption("You do not have Create permission for any module.")
            return
        for group, items in grouped(actions).items():
            st.markdown(f'<div class="qcms-quick-add-head">{group}</div>', unsafe_allow_html=True)
            cols = st.columns(2, gap="small") if len(items) > 2 else [st.container()]
            for index, action in enumerate(items):
                target = cols[index % len(cols)]
                if target.button(action.label, icon=action.icon, key=f"{key}_{action.route}_{index}", width="stretch"):
                    prepare_new_mode(st.session_state, action)
                    st.switch_page(pages[action.route])
