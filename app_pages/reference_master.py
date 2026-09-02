from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.catalog import LearnedValueCatalog
from core.delete_service import password_delete_panel
from core.master_definitions import MASTER_BY_KEY
from core.master_service import MasterService
from core.selection_labels import reference_record_label
from core.reporting import controlled_record_pdf_bytes
from core.ui import consume_master_blank_request, page_header, record_widget_token, save_success_popup, section_bar, subpage_navigation, template_download_row

REFERENCE_KEYS = (
    "customers", "suppliers", "steel_mills", "osp_vendors",
    "inspection_stages", "quality_assets",
)


def _widget(service: MasterService, catalog: LearnedValueCatalog, definition, field, record: dict[str, Any], scope: str):
    value = record.get(field.name, field.default)
    key = f"ref_{definition.key}_{field.name}_{scope}"
    if field.kind == "select":
        opts = list(field.options); current = str(value or field.default or "")
        return st.selectbox(field.label, opts, index=opts.index(current) if current in opts else 0, key=key)
    if field.kind == "lookup":
        options = service.lookup_options(field.lookup, include_none=field.allow_none); vals = [o.value for o in options]; current = str(value) if value else None
        return st.selectbox(field.label, vals, index=vals.index(current) if current in vals else 0, format_func=lambda x: next((o.label for o in options if o.value == x), "— Not selected —"), key=key)
    if field.kind == "boolean": return st.checkbox(field.label, value=bool(value), key=key)
    if field.kind == "number": return st.number_input(field.label, value=float(value or 0), key=key)
    if field.kind == "integer": return st.number_input(field.label, value=int(value or field.default or 0), step=1, key=key)
    if field.kind == "date":
        d = None
        if value:
            try: d = date.fromisoformat(str(value)[:10])
            except Exception: d = None
        return st.date_input(field.label, value=d, format="DD-MM-YYYY", key=key)
    if field.kind == "json": return st.text_area(field.label, value=str(value or ""), height=100, key=key)
    if field.name == definition.auto_code_field:
        return st.text_input(field.label, value=str(value or ""), key=key, help="Generated automatically for new records. You can edit it before saving.")
    suggestions = catalog.suggestions(f"{definition.key}.{field.name}")
    if suggestions and field.kind == "text":
        # Existing-record value must always be the selected/default option.  The old
        # implementation used index=0 even when the saved value already existed in the
        # learned list, which made another record's first suggestion appear in the edit
        # form (the exact mismatch shown in the user video).
        current = str(value or "").strip()
        options: list[str] = []
        if current:
            options.append(current)
        options += [item for item in suggestions if item not in options]
        if not options:
            options = [""]
        return st.selectbox(field.label, options, index=0, accept_new_options=True, key=key, help="Type a new value or reuse a previously saved value.")
    if field.kind == "textarea": return st.text_area(field.label, value=str(value or ""), height=90, key=key)
    return st.text_input(field.label, value=str(value or ""), key=key)


def _master_selector() -> str:
    return st.selectbox(
        "Reference Master", REFERENCE_KEYS, format_func=lambda key: MASTER_BY_KEY[key].label,
        key="reference_master_type_selector",
    )


def _record_key_label(definition, row: dict) -> str:
    primary = definition.auto_code_field or (definition.natural_key[0] if definition.natural_key else "")
    value = str(row.get(primary) or "").strip() if primary else ""
    if value:
        return value
    values = [str(row.get(k) or "").strip() for k in definition.natural_key]
    return "_".join(v for v in values if v) or str(row.get("id"))


def _row_label(definition, row: dict, lookup_maps: dict[str, dict[str, str]] | None = None) -> str:
    return reference_record_label(definition, row, lookup_maps)


def render_entry() -> None:
    subpage_navigation(
        ("masters", "Back to Masters", ":material/arrow_back:"),
        ("reference-records", "Reference Master Records", ":material/table_view:"),
    )
    page_header("Reference Masters · Entry", "Create and edit controlled reference data without separate micro-masters.", "New / edit")
    template_download_row([("Reference_Masters_Template.xlsx", "Download Reference Masters Template")], key_prefix="reference_master", import_master_key=None)
    perms = current_permissions("REFERENCE_MASTERS"); service = MasterService(); catalog = LearnedValueCatalog(service.repo)
    requested_key = str(st.session_state.get("edit_reference_key", "") or "")
    if requested_key in REFERENCE_KEYS:
        st.session_state["reference_master_type_selector"] = requested_key
    force_new = consume_master_blank_request(
        "reference-entry", edit_keys=("edit_reference_id","edit_reference_key"),
        widget_keys=("reference_master_type_selector",),
    )
    if force_new and st.session_state.get("reference_master_type_selector") not in REFERENCE_KEYS:
        st.session_state["reference_master_type_selector"] = REFERENCE_KEYS[0]
    key = _master_selector()
    import_page = (st.session_state.get("_qsms_pages") or {}).get("master-import")
    if import_page is not None and st.button(f"Import / Upload {MASTER_BY_KEY[key].label}", icon=":material/upload_file:", width="stretch", key=f"reference_import_{key}"):
        st.session_state["master_import_selected_key"] = key
        st.switch_page(import_page)
    definition = service.definition(key); rows = service.list_records(definition, status="All")
    lookup_maps = service.lookup_label_maps()
    labels = {str(row["id"]): _row_label(definition, row, lookup_maps) for row in rows}
    requested = str(st.session_state.pop("edit_reference_id", "") or "")
    requested_key = str(st.session_state.pop("edit_reference_key", "") or "")
    options = ["__new__"] + list(labels); selector_key=f"reference_record_selector_{key}"
    if force_new: st.session_state[selector_key]="__new__"
    elif requested_key == key and requested in options: st.session_state[selector_key]=requested
    elif st.session_state.get(selector_key) not in options: st.session_state[selector_key]="__new__"
    selected = st.selectbox("Record", options, format_func=lambda x: "＋ New record" if x == "__new__" else labels[x], key=selector_key)
    record = next((row for row in rows if str(row["id"]) == selected), {})
    writable = perms["can_edit"] if record else perms["can_create"]
    form_record = dict(record)
    code_session_key = f"_qsms_auto_master_code_{key}"
    if not record and definition.auto_code_field:
        if not st.session_state.get(code_session_key):
            try:
                st.session_state[code_session_key] = service.next_master_code(definition)
            except Exception as exc:
                st.warning(f"Automatic code could not be reserved: {exc}")
                st.session_state[code_session_key] = ""
        form_record[definition.auto_code_field] = st.session_state.get(code_session_key, "")
    section_bar(definition.label.upper(), definition.description)
    scope = record_widget_token("reference-entry", record if record else {}, selected=selected)
    with st.form(f"reference_{key}_{scope}"):
        cols = st.columns(3, gap="small"); raw = {}
        for i, field in enumerate(definition.fields):
            with cols[i % 3]: raw[field.name] = _widget(service, catalog, definition, field, form_record, scope)
        save = st.form_submit_button("Save controlled record", type="primary", disabled=not writable, width="stretch")
    if save:
        try:
            _, result = service.save(definition, raw, record_id=str(record["id"]) if record else None)
            for field in definition.fields:
                if field.kind in {"text", "textarea"}: catalog.remember(f"{definition.key}.{field.name}", raw.get(field.name))
            st.session_state.pop(code_session_key, None)
            save_success_popup(f"{definition.label} {result} successfully.", queue_for_rerun=True); st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if record and definition.status_field:
        c1, c2 = st.columns(2, gap="small")
        with c1:
            if st.button("Deactivate selected record", disabled=not perms["can_archive"], width="stretch"):
                try: service.deactivate(definition, str(record["id"])); save_success_popup("Record deactivated successfully.", queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))
        with c2:
            if password_delete_panel(repo=service.repo, table=definition.table, rows=[record], labeler=lambda r: _row_label(definition, r, lookup_maps), key=f"delete_ref_entry_{key}_{record.get('id')}", can_delete=perms["can_archive"], title="Delete selected record", help_text="Permanent deletion requires your current password. Linked records may prevent deletion; use Deactivate in that case."):
                st.rerun()


def render_records() -> None:
    subpage_navigation(
        ("dashboard", "Back to Dashboard", ":material/arrow_back:"),
        ("masters", "Back to Masters", ":material/dataset:"),
        ("reference-entry", "New Reference / Edit", ":material/edit_note:"),
    )
    page_header("Reference Masters · Records", "Select a record above the full-width register for editing or password-protected deletion.", "Records")
    service = MasterService(); perms = current_permissions("REFERENCE_MASTERS")
    key = _master_selector(); definition = service.definition(key)
    c1, c2 = st.columns([3, 1], gap="small"); search = c1.text_input("Search"); status = c2.selectbox("Status", ["All", "Active", "Inactive", "Approved", "Not approved"])
    if definition.status_field == "status" and status not in ("All", "Active", "Inactive"): status = "All"
    if definition.status_field == "approved" and status not in ("All", "Approved", "Not approved"): status = "All"
    rows = service.list_records(definition, search=search, status=status)

    lookup_maps = service.lookup_label_maps()
    if rows:
        labels = {str(row["id"]): _row_label(definition, row, lookup_maps) for row in rows}
        selected = st.selectbox("Select reference record", list(labels), format_func=lambda x: labels[x])
        selected_row = next(row for row in rows if str(row["id"]) == selected)
        st.session_state["edit_reference_id"] = selected; st.session_state["edit_reference_key"] = key
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            st.page_link(st.session_state["_qsms_pages"]["reference-entry"], label="Open Selected Record", icon=":material/edit:", width="stretch")
        with c2:
            printable = {field.label: selected_row.get(field.name) for field in definition.fields if field.name not in {"created_by", "updated_by"}}
            pdf = controlled_record_pdf_bytes(
                f"{definition.label.upper()} RECORD",
                printable,
                record_number=_record_key_label(definition, selected_row),
            )
            st.download_button("Download Selected PDF", pdf, file_name=f"{definition.key}_{_record_key_label(definition, selected_row)}.pdf", mime="application/pdf", width="stretch")
        with c3:
            if password_delete_panel(
                repo=service.repo,
                table=definition.table,
                rows=[selected_row],
                labeler=lambda r: _row_label(definition, r, lookup_maps),
                key=f"delete_ref_records_{key}_{selected}",
                can_delete=perms["can_archive"],
                title="Delete Selected Record",
                help_text="Permanent deletion requires your current password. Linked data may prevent deletion; deactivate the record instead.",
            ):
                st.rerun()
    else:
        st.info("No reference records match the selected filters.")

    section_bar("REFERENCE REGISTER", "The selected record and controls are positioned above the table.")
    display = pd.DataFrame(service.display_rows(definition, rows)).drop(columns=["_record_id"], errors="ignore")
    display.columns = [c.replace("_", " ").title() for c in display.columns]
    portal_table(display, hide_index=True, width="stretch", height=620)
