from __future__ import annotations

from typing import Iterable

from core.repository import Repository


class LearnedValueCatalog:
    def __init__(self, repo: Repository | None = None) -> None:
        self.repo = repo or Repository()

    def suggestions(self, field_key: str) -> list[str]:
        rows = self.repo.select(
            "master_value_catalog",
            eq={"field_key": field_key, "status": "ACTIVE"},
            order_by="usage_count",
            desc=True,
            limit=500,
        )
        return [str(row.get("value_text") or "") for row in rows if str(row.get("value_text") or "").strip()]

    def remember(self, field_key: str, value: str | None) -> str:
        text = str(value or "").strip()
        if not text:
            return text
        try:
            result = self.repo.rpc("qsms_remember_master_value", {"p_field_key": field_key, "p_value_text": text})
            return str(result or text)
        except Exception:
            # Saving the main controlled record must not be blocked by a suggestion-list failure.
            return text

    def remember_many(self, field_key: str, values: Iterable[str | None]) -> None:
        for value in values:
            self.remember(field_key, value)
