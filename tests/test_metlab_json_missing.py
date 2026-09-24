"""Exercise real MetLab service and repository serialization without a live write."""
import json
from datetime import date
from types import SimpleNamespace
import httpx
import numpy as np
import pandas as pd
import pytest
from core.inspection_service import InspectionService
from core.repository import Repository, _json_ready

class StrictClient:
    def table(self, name):
        assert name in {"lab_tests", "inspection_results"}
        return self
    def _write(self, payload):
        request = httpx.Request("POST", "https://example.invalid", json=payload)
        self.payload = json.loads(request.content)
        return self
    insert = update = _write
    def upsert(self, payload, **kwargs):
        return self._write(payload)
    def eq(self, key, value):
        self.record_id = value
        return self
    def execute(self):
        rows = self.payload if isinstance(self.payload, list) else [dict(self.payload, id=getattr(self, "record_id", "saved-report"))]
        return SimpleNamespace(data=rows)

@pytest.fixture
def repository(monkeypatch):
    monkeypatch.setattr("core.repository.log_activity", lambda *a, **kw: None)
    repo = Repository.__new__(Repository)
    repo.preview = False
    repo.tenant_id = "test-tenant"
    repo.client = StrictClient()
    return repo

@pytest.mark.parametrize("report_id", [None, "existing-report"])
def test_metlab_create_and_edit_with_blank_limits(repository, report_id):
    service = InspectionService.__new__(InspectionService)
    service.repo = repository
    rows = pd.DataFrame([
        {"parameter": "Grade", "specification": "SAE8620H", "lower_spec": None, "upper_spec": None, "actual_value": "SAE8620H"},
        {"parameter": "Hardness", "specification": None, "lower_spec": 130, "upper_spec": 200, "actual_value": "168"},
    ]).to_dict("records")
    results = {"rows": rows, "chemistry_rows": [{"actual": np.float32('nan')}], "case_depth_traverse": [{"depth": 0.1, "hardness": pd.NA}]}
    saved = service.save_metlab({"report_number": "TEST", "test_date": date(2026, 9, 24)}, results, report_id)
    assert saved["results"]["rows"][0]["lower_spec"] is None
    assert saved["results"]["rows"][1]["lower_spec"] == 130
    assert saved["results"]["rows"][1]["actual_value"] == "168"
    assert saved["results"]["chemistry_rows"][0]["actual"] is None
    assert saved["results"]["case_depth_traverse"][0]["hardness"] is None
    assert saved["test_date"] == "2026-09-24"
    assert np.isnan(rows[0]["lower_spec"])
    if report_id:
        assert saved["id"] == report_id

def test_nested_missing_scalars_preserve_zero_false_and_text():
    value = {"missing": [float('nan'), np.float64('nan'), np.float32('nan'), pd.NA, pd.NaT, np.datetime64('NaT')], "valid": [0, False, "nan", "", np.int64(3), np.float32(1.5)]}
    result = _json_ready(value)
    assert result == {"missing": [None] * 6, "valid": [0, False, "nan", "", 3, 1.5]}
    json.dumps(result, allow_nan=False)

@pytest.mark.parametrize("value", [float('inf'), float('-inf'), np.float32('inf')])
def test_infinite_measurements_rejected_before_request(repository, value):
    with pytest.raises(ValueError, match="infinite numeric"):
        repository.insert("lab_tests", {"results": {"rows": [{"actual": value}]}})
    assert not hasattr(repository.client, "payload")

def test_bulk_inspection_rows_are_json_safe(repository):
    saved = repository.bulk_upsert("inspection_results", [{"lower_spec": np.float32('nan'), "observations": [0, np.float32(168)]}])
    assert saved[0]["lower_spec"] is None
    assert saved[0]["observations"] == [0, 168]
