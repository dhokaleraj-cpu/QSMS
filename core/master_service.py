from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from core.master_definitions import MASTER_BY_KEY, MasterDef, FieldDef
from core.repository import Repository
from core.selection_labels import (
    customer_standard_label, inspection_plan_label, inspection_stage_label,
    material_grade_label, part_label, party_label, process_label, quality_asset_label,
)


@dataclass(frozen=True)
class LookupOption:
    value: str | None
    label: str


class MasterService:
    def __init__(self, repository: Repository | None = None) -> None:
        self.repo = repository or Repository()
        self._lookup_cache: dict[str, list[LookupOption]] = {}


    _AUTO_CODE_PREFIX = {
        "customers": "CUST",
        "suppliers": "SUP",
        "steel_mills": "MILL",
        "osp_vendors": "OSPV",
        "approved_sources": "SRC",
        "processes": "PROC",
        "inspection_stages": "STG",
        "quality_assets": "AST",
        "customer_standards": "STD",
    }

    def next_master_code(self, definition: MasterDef) -> str:
        """Reserve the next controlled code. The generated value remains editable before save."""
        if not definition.auto_code_field:
            return ""
        if self.repo.preview:
            prefix = self._AUTO_CODE_PREFIX.get(definition.key, definition.key[:4].upper())
            rows = self.list_records(definition, status="All")
            highest = 0
            for row in rows:
                match = re.search(r"(\d+)$", str(row.get(definition.auto_code_field) or ""))
                if match:
                    highest = max(highest, int(match.group(1)))
            return f"{prefix}-{highest + 1:04d}"
        value = self.repo.rpc("qsms_next_master_code", {"p_master_key": definition.key})
        if isinstance(value, dict):
            value = value.get("code") or value.get("qsms_next_master_code")
        return str(value or "").strip()

    def definition(self, key: str) -> MasterDef:
        if key not in MASTER_BY_KEY:
            raise KeyError(f"Unknown master: {key}")
        return MASTER_BY_KEY[key]

    def list_records(self, definition: MasterDef, *, search: str = "", status: str = "All") -> list[dict]:
        eq: dict[str, Any] = {}
        if status != "All" and definition.status_field == "status":
            eq["status"] = status.upper()
        elif status != "All" and definition.status_field == "approved":
            eq["approved"] = status == "Approved"
        rows = self.repo.select(
            definition.table,
            eq=eq,
            contains=definition.array_filter,
            search_columns=definition.search_fields,
            search_term=search,
            order_by=definition.order_by,
            limit=1000,
        )
        return rows

    def get_record(self, definition: MasterDef, record_id: str | None) -> dict | None:
        if not record_id:
            return None
        return self.repo.get(definition.table, record_id)

    def _lookup_rows(self, lookup: str) -> list[dict]:
        definition = self.definition(lookup)
        return self.list_records(definition, status="All")

    def lookup_options(self, lookup: str, *, include_none: bool = True) -> list[LookupOption]:
        cache_key = f"{lookup}:{include_none}"
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]
        rows = self._lookup_rows(lookup)
        options: list[LookupOption] = [LookupOption(None, "— Not selected —")] if include_none else []
        for row in rows:
            if lookup in {"customers", "suppliers", "steel_mills", "osp_vendors"}:
                label = party_label(row)
            elif lookup == "material_grades":
                label = material_grade_label(row)
            elif lookup == "parts":
                label = part_label(row)
            elif lookup == "processes":
                label = process_label(row)
            elif lookup == "inspection_stages":
                label = inspection_stage_label(row)
            elif lookup == "quality_assets":
                label = quality_asset_label(row)
            elif lookup == "inspection_plans":
                label = inspection_plan_label(row)
            elif lookup == "customer_standards":
                label = customer_standard_label(row)
            else:
                label = str(row.get("id"))
            options.append(LookupOption(str(row.get("id")), label.strip(" ·")))
        self._lookup_cache[cache_key] = options
        return options

    def lookup_label_maps(self) -> dict[str, dict[str, str]]:
        maps: dict[str, dict[str, str]] = {}
        for lookup in ("customers", "suppliers", "steel_mills", "osp_vendors", "material_grades", "parts", "processes", "inspection_stages", "quality_assets", "inspection_plans", "customer_standards"):
            maps[lookup] = {str(option.value): option.label for option in self.lookup_options(lookup) if option.value}
        return maps

    @staticmethod
    def _empty(value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    def validate_payload(self, definition: MasterDef, payload: Mapping[str, Any]) -> list[str]:
        errors: list[str] = []
        for field in definition.fields:
            if field.required and self._empty(payload.get(field.name)):
                errors.append(f"{field.label} is mandatory.")
        if definition.key == "chemical_composition":
            minimum = payload.get("minimum")
            maximum = payload.get("maximum")
            if minimum is not None and maximum is not None and float(minimum) > float(maximum):
                errors.append("Minimum cannot be greater than maximum.")
        if definition.key == "quality_assets":
            frequency = payload.get("calibration_frequency_days")
            if frequency is not None and int(frequency) <= 0:
                errors.append("Calibration frequency must be greater than zero.")
        return errors

    @staticmethod
    def _normalize_json(field: FieldDef, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        text = str(value or "").strip()
        if not text:
            return [] if field.name == "special_characteristics" else {}
        try:
            parsed = json.loads(text)
            return parsed
        except json.JSONDecodeError:
            if field.name == "special_characteristics":
                return [{"note": text}]
            return {"criteria": text}

    def normalize_payload(self, definition: MasterDef, raw: Mapping[str, Any], *, existing: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field in definition.fields:
            value = raw.get(field.name, field.default)
            if field.kind == "json":
                value = self._normalize_json(field, value)
            elif field.kind == "number":
                value = None if value in (None, "") else float(value)
            elif field.kind == "integer":
                value = None if value in (None, "") else int(value)
            elif field.kind == "date":
                if isinstance(value, (date, datetime)):
                    value = value.isoformat()[:10]
                elif not value:
                    value = None
            elif field.kind == "boolean":
                value = bool(value)
            elif field.kind in {"text", "textarea"}:
                value = str(value or "").strip() or None
            payload[field.name] = value

        for key, value in definition.fixed_values.items():
            if key == "party_types":
                prior = set((existing or {}).get("party_types") or [])
                prior.update(value or [])
                payload[key] = sorted(prior)
            else:
                payload[key] = value
        return payload


    @staticmethod
    def _normalized_key_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            return "|".join(sorted(str(item).strip().casefold() for item in value))
        return re.sub(r"\s+", " ", str(value).strip()).casefold()

    @staticmethod
    def _matching_words_value(value: Any) -> str:
        """Punctuation-insensitive signature used for human-readable master names.

        Example: ``Kessler + Co. GmbH`` and ``KESSLER CO GMBH`` resolve to the
        same signature. Codes/part numbers continue to use their controlled
        natural-key rules so valid engineering punctuation is not destroyed.
        """
        return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))

    _FUZZY_STOP_WORDS = {
        "the", "and", "for", "with", "from", "of", "to", "a", "an", "in", "on",
        "pvt", "private", "ltd", "limited", "inc", "incorporated", "company", "co",
        "gmbh", "kg", "llc", "llp", "india", "active", "approved", "master",
    }

    @classmethod
    def _significant_words(cls, value: Any) -> tuple[str, ...]:
        words = [w for w in re.findall(r"[a-z0-9]+", str(value or "").casefold()) if len(w) >= 2]
        return tuple(w for w in words if w not in cls._FUZZY_STOP_WORDS)

    @classmethod
    def _fuzzy_word_duplicate(cls, left: Any, right: Any) -> bool:
        """Return True only when 2–3 meaningful words strongly identify the same value.

        This intentionally avoids loose substring matching.  Two-word values must share
        both meaningful words; values with three or more meaningful words must share at
        least three words and at least 67% of the shorter value.
        """
        a = cls._significant_words(left); b = cls._significant_words(right)
        if len(a) < 2 or len(b) < 2:
            return False
        sa, sb = set(a), set(b)
        shared = len(sa & sb); shorter = max(1, min(len(sa), len(sb)))
        needed = 2 if shorter <= 2 else 3
        return shared >= needed and (shared / shorter) >= 0.67

    def duplicate_match(
        self, definition: MasterDef, payload: Mapping[str, Any], *,
        record_id: str | None = None, extra_unique_fields: Sequence[str] = (),
    ) -> str | None:
        rows = self.list_records(definition, status="All")
        natural_fields = tuple(definition.natural_key)
        expected = tuple(self._normalized_key_value(payload.get(field)) for field in natural_fields)
        # Human-readable master fields where a 2–3 word near-match is meaningful.
        fuzzy_fields = list(extra_unique_fields)
        for field in definition.fields:
            name = field.name
            if field.kind not in {"text", "textarea"}:
                continue
            if name in fuzzy_fields or name in natural_fields:
                continue
            if any(token in name for token in ("name", "description", "standard", "parameter", "designation")):
                fuzzy_fields.append(name)

        for row in rows:
            if record_id and str(row.get("id")) == str(record_id):
                continue
            if natural_fields and all(expected) and expected == tuple(self._normalized_key_value(row.get(field)) for field in natural_fields):
                return "matching controlled key " + " + ".join(natural_fields)
            for field in fuzzy_fields:
                candidate = payload.get(field)
                existing = row.get(field)
                if self._normalized_key_value(candidate) and self._normalized_key_value(candidate) == self._normalized_key_value(existing):
                    return f"matching {field.replace('_', ' ')}"
                if self._fuzzy_word_duplicate(candidate, existing):
                    return f"2–3 matching words in {field.replace('_', ' ')} ({existing})"
        return None

    def assert_no_duplicate(
        self,
        definition: MasterDef,
        payload: Mapping[str, Any],
        *,
        record_id: str | None = None,
        extra_unique_fields: Sequence[str] = (),
    ) -> None:
        current=self.get_record(definition,record_id) if record_id else None
        natural_fields=tuple(definition.natural_key)
        expected=tuple(self._normalized_key_value(payload.get(field)) for field in natural_fields)
        current_key=tuple(self._normalized_key_value((current or {}).get(field)) for field in natural_fields)
        effective_record_id=record_id
        # Legacy duplicate records stay editable when their controlled natural key is unchanged.
        if current and expected==current_key:
            natural_payload=dict(payload)
            for field in natural_fields: natural_payload[field]=None
            reason=self.duplicate_match(definition,natural_payload,record_id=effective_record_id,extra_unique_fields=extra_unique_fields)
        else:
            reason=self.duplicate_match(definition,payload,record_id=effective_record_id,extra_unique_fields=extra_unique_fields)
        if reason:
            raise ValueError(f"Duplicate {definition.label} is not allowed. Matching words already exist: {reason}.")

    def save(self, definition: MasterDef, raw: Mapping[str, Any], *, record_id: str | None = None) -> tuple[dict, str]:
        existing = self.get_record(definition, record_id)
        payload = self.normalize_payload(definition, raw, existing=existing)
        if not existing and definition.auto_code_field and self._empty(payload.get(definition.auto_code_field)):
            payload[definition.auto_code_field] = self.next_master_code(definition)
        errors = self.validate_payload(definition, payload)
        if errors:
            raise ValueError("\n".join(errors))
        extra_unique_fields: tuple[str, ...] = ()
        if definition.key in {"customers", "suppliers", "steel_mills", "osp_vendors"}:
            extra_unique_fields = ("party_name",)
        elif definition.key == "processes":
            extra_unique_fields = ("process_name",)
        elif definition.key == "inspection_stages":
            extra_unique_fields = ("stage_name",)
        elif definition.key == "quality_assets":
            extra_unique_fields = ("asset_name",)
        self.assert_no_duplicate(
            definition,
            payload,
            record_id=str(existing["id"]) if existing else record_id,
            extra_unique_fields=extra_unique_fields,
        )
        if existing:
            return self.repo.update(definition.table, str(existing["id"]), payload), "updated"
        return self.repo.insert(definition.table, payload), "created"

    def deactivate(self, definition: MasterDef, record_id: str) -> dict:
        if definition.status_field == "status":
            return self.repo.update(definition.table, record_id, {"status": "INACTIVE"})
        if definition.status_field == "approved":
            return self.repo.update(definition.table, record_id, {"approved": False})
        raise ValueError("This controlled master has no deactivation field.")

    def display_rows(self, definition: MasterDef, rows: Sequence[Mapping[str, Any]]) -> list[dict]:
        maps = self.lookup_label_maps()
        result: list[dict] = []
        lookup_by_field = {field.name: field.lookup for field in definition.fields if field.lookup}
        for row in rows:
            display: dict[str, Any] = {"_record_id": row.get("id")}
            for column in definition.columns:
                value = row.get(column)
                lookup = lookup_by_field.get(column)
                if lookup and value:
                    value = maps.get(lookup, {}).get(str(value), str(value))
                elif isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                display[column] = value
            result.append(display)
        return result

    def completeness(self, definition: MasterDef, rows: Sequence[Mapping[str, Any]]) -> float:
        required = [field.name for field in definition.fields if field.required]
        if not rows or not required:
            return 100.0 if rows else 0.0
        total = len(rows) * len(required)
        complete = sum(1 for row in rows for key in required if not self._empty(row.get(key)))
        return round(complete * 100 / total, 1)

    def master_overview(self) -> list[dict[str, Any]]:
        overview = []
        for key in ("customers", "suppliers", "steel_mills", "parts", "material_grades", "processes", "inspection_stages", "quality_assets"):
            definition = self.definition(key)
            rows = self.list_records(definition)
            active = sum(
                1
                for row in rows
                if (
                    definition.status_field == "status" and str(row.get("status") or "ACTIVE").upper() == "ACTIVE"
                ) or (
                    definition.status_field == "approved" and bool(row.get("approved"))
                ) or not definition.status_field
            )
            overview.append({
                "key": key,
                "label": definition.label,
                "count": len(rows),
                "active": active,
                "completeness": self.completeness(definition, rows),
            })
        return overview
