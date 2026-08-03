from core.inspection_queue import build_inspection_queue, pending_count, report_queue_status


def _inward(record_id: str) -> dict:
    return {
        "id": record_id,
        "inward_number": f"IN-{record_id}",
        "receipt_disposition": "ACCEPTED",
        "status": "HOLD_PENDING_INSPECTION",
        "created_at": f"2026-08-0{record_id}T10:00:00+00:00",
    }


def test_missing_reports_are_pending_immediately_after_inward():
    queue = build_inspection_queue([_inward("1"), _inward("2")], [], [])
    assert pending_count(queue, "DIMENSIONAL") == 2
    assert pending_count(queue, "METLAB") == 2
    assert all(row["dimensional_queue_status"] == "PENDING" for row in queue)
    assert all(row["metlab_queue_status"] == "PENDING" for row in queue)


def test_final_dimensional_closes_only_that_queue():
    queue = build_inspection_queue(
        [_inward("1"), _inward("2")],
        [{
            "id": "dim-1", "inward_lot_id": "1", "report_type": "DIMENSIONAL",
            "status": "FINAL", "disposition": "ACCEPTED_UNDER_RESERVE",
            "updated_at": "2026-08-03T10:00:00+00:00",
        }],
        [],
    )
    assert pending_count(queue, "DIMENSIONAL") == 1
    assert pending_count(queue, "METLAB") == 2
    row_1 = next(row for row in queue if row["id"] == "1")
    assert row_1["dimensional_queue_status"] == "COMPLETED"
    assert row_1["dimensional_pending"] is False
    assert row_1["metlab_pending"] is True


def test_on_hold_and_draft_reports_remain_in_pending_worklist():
    assert report_queue_status({"status": "FINAL", "disposition": "ON_HOLD"}) == ("ON_HOLD", True)
    assert report_queue_status({"status": "DRAFT", "disposition": "PENDING"}) == ("PENDING", True)
    assert report_queue_status({"status": "FINAL", "disposition": "REJECTED"}) == ("COMPLETED", False)


def test_inspection_pages_use_shared_inward_based_queue():
    home = open("app_pages/inspection_home.py", encoding="utf-8").read()
    dashboard = open("app_pages/dashboard.py", encoding="utf-8").read()
    dimensional = open("app_pages/dimensional_report.py", encoding="utf-8").read()
    metlab = open("app_pages/metlab_report.py", encoding="utf-8").read()
    assert "PENDING INSPECTION WORKLIST" in home
    assert 'pending_count(queue, "DIMENSIONAL")' in home
    assert 'pending_count(queue, "METLAB")' in home
    assert 'pending_count(inspection_queue, "DIMENSIONAL")' in dashboard
    assert "DIMENSIONAL PENDING LIST" in dimensional
    assert "METLAB PENDING LIST" in metlab
