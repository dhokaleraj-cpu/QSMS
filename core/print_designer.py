"""QCMS R21 · Print Layout Designer.

Admin-editable print layouts (design selector + theme + section visibility + renamed
headings) for every controlled PDF. Layouts are stored as JSON in the tenant-scoped
``master_value_catalog`` table (key ``qcms.print.layout.<DOC>``); every save keeps the
previous version as INACTIVE so a layout can be restored. No SQL migration is needed.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Mapping

LAYOUT_KEY_PREFIX = "qcms.print.layout."
_CACHE_KEY = "_qcms_print_layouts"
_CACHE_SECONDS = 60

# Document families that can be designed.
DOCUMENTS: dict[str, str] = {
    "PURCHASE_ORDER": "Purchase Order",
    "RMTC": "RMTC Report",
    "METLAB": "MetLAB Report",
    "BEND_TEST": "Bend Test Report",
    "DIMENSIONAL": "Dimensional Report",
    "MATERIAL_INWARD": "Material Inward Report",
    "QUALITY_RECORD": "Other Quality Records / Registers",
}

BAR_STYLES = {"fill": "Filled heading bar", "underline": "Heading text + underline", "outline": "Outlined heading bar"}

# Purchase Order sections that can be shown / hidden and renamed.
PO_SECTIONS: dict[str, str] = {
    "PLANT / COMPANY BRANCH": "show_plant",
    "VENDOR": "show_vendor",
    "REFERENCE DETAILS": "show_reference",
    "OLD PO DETAILS": "show_old_po",
    "SHIP TO": "show_ship_to",
    "PO SOURCE REFERENCE": "show_source_reference",
    "RAW MATERIAL DETAILS & SUPPLIER TECHNICAL DATA": "show_technical",
    "PRICE REVISION HISTORY": "show_price_history",
    "COMMENTS OR SPECIAL INSTRUCTIONS": "show_special_instructions",
}

# Report-family presets. B5 is the approved Purchase Order design (R21).
PRESETS: dict[str, dict[str, Any]] = {
    "B1": {"accent": "#0B6E70", "bar": "fill", "rule": "#C9D6D6", "head_fill": "", "label_fill": "", "remark": "#9A3412", "remark_fill": "", "conclusion": "#166534"},
    "B2": {"accent": "#0B6E70", "bar": "underline", "rule": "#C9D6D6", "head_fill": "", "label_fill": "", "remark": "#9A3412", "remark_fill": "", "conclusion": "#166534"},
    "B3": {"accent": "#0B6E70", "bar": "outline", "rule": "#C9D6D6", "head_fill": "", "label_fill": "", "remark": "#9A3412", "remark_fill": "", "conclusion": "#166534"},
    "B4": {"accent": "#334155", "bar": "fill", "rule": "#CBD5E1", "head_fill": "", "label_fill": "#F1F5F9", "remark": "#0B6E70", "remark_fill": "", "conclusion": "#166534"},
    "B5": {"accent": "#0B6E70", "bar": "fill", "rule": "#C9D6D6", "head_fill": "#EAF4F4", "label_fill": "#F3F8F8", "remark": "#9A3412", "remark_fill": "#FFF7ED", "conclusion": "#166534"},
}
PRESET_NAMES = {
    "B1": "B1 · Open Lines Teal",
    "B2": "B2 · Teal Underline",
    "B3": "B3 · Teal Outline",
    "B4": "B4 · Graphite & Teal",
    "B5": "B5 · Teal Bands (approved)",
}
DEFAULT_PRESET = "B5"


def default_layout(doc: str) -> dict[str, Any]:
    doc = str(doc or "").upper()
    layout: dict[str, Any] = {"preset": DEFAULT_PRESET, **PRESETS[DEFAULT_PRESET], "labels": {}, "company_name": "", "footer_text": ""}
    if doc == "PURCHASE_ORDER":
        layout.update({"title": "PURCHASE ORDER", "show_approval_stamp": True, **{flag: True for flag in PO_SECTIONS.values()}})
    else:
        # Quality reports keep the approved Design B (R17/R18) unless the designer changes it.
        layout.update({"preset": "B1", **PRESETS["B1"], "rule": "#9AA5A5", "body_pt": 8.6, "heading_pt": 10.5})
    return layout


HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def normalize_layout(doc: str, layout: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge a saved / edited layout over the defaults and drop invalid values."""
    base = default_layout(doc)
    data = dict(layout or {})
    preset = str(data.get("preset") or "").upper()
    if preset in PRESETS and preset != base["preset"]:
        base.update(PRESETS[preset]); base["preset"] = preset
    for key, value in data.items():
        if key in {"accent", "rule", "remark", "conclusion"}:
            if isinstance(value, str) and HEX.match(value):
                base[key] = value.upper()
        elif key in {"head_fill", "label_fill", "remark_fill"}:
            if value in ("", None) or (isinstance(value, str) and HEX.match(value)):
                base[key] = (value or "").upper()
        elif key == "bar":
            if value in BAR_STYLES:
                base[key] = value
        elif key in {"body_pt", "heading_pt"}:
            try:
                base[key] = max(6.0, min(14.0, float(value)))
            except (TypeError, ValueError):
                pass
        elif key.startswith("show_"):
            base[key] = bool(value)
        elif key == "labels" and isinstance(value, Mapping):
            base["labels"] = {str(k).strip(): str(v).strip() for k, v in value.items() if str(k).strip() and str(v).strip()}
        elif key in {"title", "company_name", "footer_text"}:
            base[key] = str(value or "").strip()[:120]
    return base


def layout_key(doc: str) -> str:
    return LAYOUT_KEY_PREFIX + str(doc or "").upper()


def _session_state():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            return None
        import streamlit as st
        return st.session_state
    except Exception:
        return None


def read_layout(repo: Any, doc: str) -> dict[str, Any]:
    """Saved layout from the database (or defaults)."""
    try:
        rows = repo.select("master_value_catalog", eq={"field_key": layout_key(doc), "status": "ACTIVE"}, order_by="last_used_at", desc=True, limit=1)
        saved = json.loads(str(rows[0].get("value_text") or "{}")) if rows else {}
    except Exception:
        saved = {}
    return normalize_layout(doc, saved)


def saved_layout(doc: str) -> dict[str, Any]:
    """Layout used when printing. Outside a signed-in Streamlit session -> defaults."""
    state = _session_state()
    if state is None:
        return default_layout(doc)
    cache = state.get(_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        state[_CACHE_KEY] = cache
    hit = cache.get(doc)
    if hit and time.time() - hit[0] < _CACHE_SECONDS:
        return dict(hit[1])
    try:
        from core.database import get_session_client
        if get_session_client() is None:
            layout = default_layout(doc)
        else:
            from core.repository import Repository
            layout = read_layout(Repository(), doc)
    except Exception:
        layout = default_layout(doc)
    cache[doc] = (time.time(), layout)
    return dict(layout)


def save_layout(repo: Any, doc: str, layout: Mapping[str, Any], profile: Mapping[str, Any] | None) -> dict[str, Any]:
    from core.system_settings import set_system_value
    clean = normalize_layout(doc, layout)
    set_system_value(repo, layout_key(doc), json.dumps(clean, sort_keys=True, ensure_ascii=False), profile)
    forget_cache()
    return clean


def layout_history(repo: Any, doc: str, limit: int = 20) -> list[dict[str, Any]]:
    try:
        rows = repo.select("master_value_catalog", eq={"field_key": layout_key(doc)}, order_by="updated_at", desc=True, limit=limit)
    except Exception:
        rows = []
    return rows


def forget_cache() -> None:
    state = _session_state()
    if state is not None:
        state.pop(_CACHE_KEY, None)
        state.pop("_qcms_export_bytes_memo", None)


def relabel(layout: Mapping[str, Any] | None, title: str) -> str:
    """Renamed heading if the layout defines one (prefix match keeps dynamic suffixes)."""
    labels = dict((layout or {}).get("labels") or {})
    if title in labels:
        return labels[title]
    for original, new in labels.items():
        if title.startswith(original):
            return new + title[len(original):]
    return title
