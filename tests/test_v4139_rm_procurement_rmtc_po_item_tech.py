from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def text(path): return (ROOT/path).read_text(encoding='utf-8')

def test_customer_purchase_order_keeps_live_rm_procurement_visibility():
    s=text('core/supply_chain_service.py')
    token='proposed_three_month_qty=number(order.get("order_qty_pcs")) if str(order.get("order_type") or "") == "PURCHASE_ORDER" else 0.0'
    assert s.count(token) >= 2
    assert 'def pending_customer_orders_for_rm' in s
    assert 'def create_purchase_order' in s

def test_incremental_approved_rmtc_part_guard_allows_pending_part():
    sql=text('supabase/migrations/20260822224500_qcms_rmtc_incremental_part_release_guard_v4139.sql')
    assert "v_pending_decisions" in sql
    assert "new.status = 'PARTIALLY_APPROVED' and v_release_decisions <= 0" in sql
    assert "APPROVED RMTC status requires every covered Part Number" in sql
    assert "PARTIALLY_APPROVED permits released Parts together with newly pending/on-hold/rejected" in sql

def test_po_print_is_item_then_item_specific_technical_data():
    p=text('core/purchase_order_reporting.py')
    assert 'RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA' in p
    assert 'compact_technical_pairs' in p
    assert 'Item-wise technical pocket directly under the item line.' in p
    assert p.index('item_row_bottom = y - 21') < p.index('compact_technical_pairs(item)')

def test_build_markers():
    marker='4139-RM-PROCUREMENT-LINK-RMTC-PART-PO-ITEM-TECH'
    for f in ('core/ui.py','core/auth.py','streamlit_app.py'):
        assert marker in text(f)
