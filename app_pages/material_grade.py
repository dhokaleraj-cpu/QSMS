from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.catalog import LearnedValueCatalog
from core.delete_service import password_delete_panel
from core.repository import Repository
from core.reporting import controlled_record_pdf_bytes
from core.selection_labels import material_grade_label
from core.ui import page_header, save_success_popup, section_bar, stage_section, subpage_navigation, template_download_row

DEFAULT_ELEMENTS = ["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni"]


def _grade_labels(rows: list[dict]) -> dict[str, str]:
    return {str(r["id"]): material_grade_label(r) for r in rows}


def render_entry() -> None:
    subpage_navigation(
        ("masters", "Back to Masters", ":material/arrow_back:"),
        ("grade-records", "Material Grade Records", ":material/table_view:"),
    )
    page_header("Material Grade · Entry", "Material header and chemical composition maintained together.", "New / edit")
    template_download_row([("Material_Grade_Template.xlsx", "Download Material Grade Template")], key_prefix="material_grade")
    repo = Repository(); catalog = LearnedValueCatalog(repo); perms = current_permissions("MATERIAL_GRADE")
    grades = repo.select("material_grades", order_by="grade_code", limit=2000)
    labels = _grade_labels(grades)
    requested = str(st.session_state.pop("edit_grade_id", "") or "")
    options = ["__new__"] + list(labels); index = options.index(requested) if requested in options else 0
    selected = st.selectbox("Material Grade record", options, index=index, format_func=lambda x: "＋ New Material Grade" if x == "__new__" else labels[x])
    existing = next((g for g in grades if str(g["id"]) == selected), {})
    writable = perms["can_edit"] if existing else perms["can_create"]
    material_number_key = "_qcms_new_material_number"
    if not existing and not st.session_state.get(material_number_key):
        try:
            generated = repo.rpc("qcms_next_material_number", {})
            if isinstance(generated, dict):
                generated = generated.get("code") or generated.get("qcms_next_material_number")
            st.session_state[material_number_key] = str(generated or "").strip()
        except Exception as exc:
            st.warning(f"Automatic Material Number could not be generated: {exc}")
            st.session_state[material_number_key] = ""

    with stage_section("A", 'MATERIAL GRADE DETAILS', 'Grade name, auto Material Number, specification and revision.', key="material_grade_render_entry_a"):
        with st.form("material_grade_header"):
            c = st.columns(4, gap="small")
            grade_code = c[0].text_input("Material Grade", value=str(existing.get("grade_code") or ""))
            material_number = c[1].text_input("Material Number", value=str(existing.get("material_number") or st.session_state.get(material_number_key) or ""), help="Generated automatically for new Material Grades and editable before save.")
            standard = c[2].text_input("Standard / Specification", value=str(existing.get("standard") or ""))
            revision = c[3].text_input("Revision", value=str(existing.get("revision") or "00"))
            c = st.columns(3, gap="small")
            effective_value = None
            if existing.get("effective_date"):
                try: effective_value = date.fromisoformat(str(existing.get("effective_date"))[:10])
                except Exception: effective_value = None
            effective = c[0].date_input("Effective Date", value=effective_value, format="DD-MM-YYYY")
            status = c[1].selectbox("Status", ["ACTIVE", "INACTIVE"], index=0 if str(existing.get("status") or "ACTIVE") == "ACTIVE" else 1)
            remarks = c[2].text_input("Remarks", value=str(existing.get("remarks") or ""))
            save = st.form_submit_button("Save Material Grade", type="primary", disabled=not writable, width="stretch")
        if save:
            try:
                if not grade_code.strip(): raise ValueError("Material Grade is mandatory.")
                if not material_number.strip(): raise ValueError("Material Number is mandatory and is normally generated automatically.")
                payload = {"grade_code": grade_code.strip(), "material_number": material_number.strip(), "standard": standard.strip() or None, "revision": revision.strip() or "00", "effective_date": effective.isoformat() if effective else None, "status": status, "remarks": remarks.strip() or None}
                expected_code = grade_code.strip().casefold()
                for row in repo.select("material_grades", limit=5000):
                    if existing and str(row.get("id")) == str(existing.get("id")):
                        continue
                    if str(row.get("grade_code") or "").strip().casefold() == expected_code:
                        raise ValueError("Duplicate Material Grade code is not allowed. Standard, revision and other common fields may repeat and should be updated on the same grade record.")
                saved = repo.update("material_grades", str(existing["id"]), payload) if existing else repo.insert("material_grades", payload)
                catalog.remember_many("material.standard", [standard]); catalog.remember_many("material.grade", [grade_code])
                st.session_state.pop(material_number_key, None)
                st.session_state["edit_grade_id"] = str(saved["id"]); save_success_popup(f"Material Grade {saved.get('grade_code')} saved successfully.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(str(exc))

        if not existing:
            st.info("Save the Material Grade header first. Chemical Composition will then become available on this same page.")
            return
        grade_id = str(existing["id"])
    with stage_section("B", 'CHEMICAL COMPOSITION', 'Enter element names for the first time; they are remembered and offered for future grades.', key="material_grade_render_entry_b"):
        chemistry = repo.select("material_grade_elements", eq={"material_grade_id": grade_id}, order_by="element", limit=300)
        if password_delete_panel(repo=repo, table="material_grade_elements", rows=chemistry, labeler=lambda r: f"{r.get('element')} · {r.get('minimum')} to {r.get('maximum')} {r.get('unit') or '%'}", key=f"delete_chem_{grade_id}", can_delete=perms["can_archive"], title="Delete Chemical Composition row"):
            st.rerun()
        existing_by_name = {str(r.get("element") or "").strip().casefold(): r for r in chemistry}
        chemistry_rows = [
            {"Element": r.get("element"), "Minimum %": r.get("minimum"), "Maximum %": r.get("maximum"), "Unit": r.get("unit") or "%", "Test Method": r.get("test_method")}
            for r in chemistry
        ]
        for element in DEFAULT_ELEMENTS:
            if element.casefold() not in existing_by_name:
                chemistry_rows.append({"Element": element, "Minimum %": None, "Maximum %": None, "Unit": "%", "Test Method": None})
        cdf = pd.DataFrame(chemistry_rows, columns=["Element", "Minimum %", "Maximum %", "Unit", "Test Method"])
        edited = st.data_editor(
            cdf, num_rows="dynamic", hide_index=True, width="stretch", height=440,
            key=f"chem_{grade_id}", disabled=not writable,
            column_config={"Minimum %": st.column_config.NumberColumn(format="%.4f"), "Maximum %": st.column_config.NumberColumn(format="%.4f")},
        )
        suggestions = catalog.suggestions("material.element")
        if suggestions:
            st.caption("Available element names from previous grades: " + ", ".join(suggestions[:30]))
        if st.button("Save Chemical Composition", type="primary", disabled=not writable, width="stretch"):
            try:
                for _, row in edited.iterrows():
                    element = str(row.get("Element") or "").strip()
                    if not element: continue
                    low = None if pd.isna(row.get("Minimum %")) else row.get("Minimum %"); high = None if pd.isna(row.get("Maximum %")) else row.get("Maximum %")
                    if low is not None and high is not None and float(low) > float(high): raise ValueError(f"{element}: Minimum cannot exceed Maximum.")
                    payload = {"material_grade_id": grade_id, "element": element, "minimum": low, "maximum": high, "unit": str(row.get("Unit") or "%").strip() or "%", "test_method": str(row.get("Test Method") or "").strip() or None}
                    repo.upsert_by("material_grade_elements", payload, natural_key={"material_grade_id": grade_id, "element": element})
                    catalog.remember_many("material.element", [element]); catalog.remember_many("material.test_method", [row.get("Test Method")])
                save_success_popup("Chemical Composition saved inside the Material Grade Master.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(str(exc))


def render_records() -> None:
    subpage_navigation(
        ("dashboard", "Back to Dashboard", ":material/arrow_back:"),
        ("masters", "Back to Masters", ":material/dataset:"),
        ("grade-entry", "New Material Grade / Edit", ":material/science:"),
    )
    page_header("Material Grade · Records", "Select a grade above the register to review chemistry, edit or delete.", "Records")
    repo = Repository(); perms = current_permissions("MATERIAL_GRADE")
    grades = repo.select("material_grades", order_by="grade_code", limit=3000)
    search = st.text_input("Search Material Grade, Material Number or Standard")
    rows = [g for g in grades if not search or search.casefold() in " ".join(str(g.get(k) or "") for k in ("grade_code", "material_number", "standard")).casefold()]

    selected = ""
    composition: list[dict] = []
    if rows:
        labels = _grade_labels(rows)
        selected = st.selectbox("Select Material Grade record", list(labels), format_func=lambda x: labels[x])
        composition = repo.select("material_grade_elements", eq={"material_grade_id": selected}, order_by="element", limit=300)
        st.session_state["edit_grade_id"] = selected
        selected_row = next(g for g in rows if str(g.get("id")) == selected)
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            st.page_link(st.session_state["_qsms_pages"]["grade-entry"], label="Open Selected Material Grade", icon=":material/edit:", width="stretch")
        with c2:
            pdf = controlled_record_pdf_bytes(
                "MATERIAL GRADE RECORD",
                {"Material Grade": selected_row.get("grade_code"), "Material Number": selected_row.get("material_number"), "Standard / Specification": selected_row.get("standard"), "Revision": selected_row.get("revision"), "Effective Date": selected_row.get("effective_date"), "Status": selected_row.get("status"), "Remarks": selected_row.get("remarks")},
                {"Chemical Composition": [{"Element": row.get("element"), "Minimum": row.get("minimum"), "Maximum": row.get("maximum"), "Unit": row.get("unit"), "Test Method": row.get("test_method")} for row in composition]},
                record_number=f"{selected_row.get('grade_code')}-REV-{selected_row.get('revision')}",
            )
            st.download_button("Download Grade PDF", pdf, file_name=f"Material_Grade_{selected_row.get('grade_code')}_Rev_{selected_row.get('revision')}.pdf", mime="application/pdf", width="stretch")
        with c3:
            if password_delete_panel(
                repo=repo,
                table="material_grades",
                rows=[selected_row],
                labeler=lambda r: f"{r.get('grade_code')} · {r.get('material_number') or '-'}",
                key=f"delete_grade_{selected}",
                can_delete=perms["can_archive"],
                title="Delete Selected Material Grade",
                help_text="Linked Part or RMTC records will block deletion. Set the grade to Inactive instead.",
            ):
                st.rerun()
    else:
        st.info("No Material Grade records match the search.")

    section_bar("MATERIAL GRADE REGISTER", "Material Grade header records.")
    df = pd.DataFrame([{"Material Grade": g.get("grade_code"), "Material Number": g.get("material_number"), "Standard": g.get("standard"), "Revision": g.get("revision"), "Effective Date": g.get("effective_date"), "Status": g.get("status")} for g in rows])
    portal_table(df, hide_index=True, width="stretch", height=430)
    if selected:
        section_bar("SELECTED GRADE · CHEMICAL COMPOSITION", "Chemical elements remain embedded inside the selected Material Grade Master.")
        portal_table(pd.DataFrame([{"Element": r.get("element"), "Minimum %": r.get("minimum"), "Maximum %": r.get("maximum"), "Unit": r.get("unit"), "Test Method": r.get("test_method")} for r in composition]), hide_index=True, width="stretch", height=300)
