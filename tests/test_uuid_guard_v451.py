from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repository_get_guards_blank_uuid() -> None:
    text = (ROOT / "core/repository.py").read_text()
    assert "if not value:" in text
    assert "uuid.UUID(value)" in text


def test_rmtc_selection_is_not_popped_on_rerun() -> None:
    text = (ROOT / "app_pages/rmtc_pages.py").read_text()
    assert "st.session_state.get('edit_rmtc_id')" in text
    assert "pop('edit_rmtc_id','')" not in text
    assert "def _valid_uuid" in text


def test_compact_density_and_visible_fields_are_present() -> None:
    text = (ROOT / "core/ui.py").read_text()
    assert ".fsi-status-card .value,.fsi-kpi-value{font-size:18px" in text
    assert "min-height:31px!important" in text
    assert "color:var(--fsi-text)!important" in text
    assert ".fsi-master-card-body{display:none}" in text
