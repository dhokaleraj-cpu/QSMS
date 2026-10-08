"""R10 acceptance regressions: Forging PO source gate and full FSI RM -> Forging chain."""
from copy import deepcopy
import pytest
from test_r7_linked_raw_flow import service, po_payload


def chain_service(flow='FSI_RM', order_qty=100):
    svc = service()
    orders = {
        'co1': {'id': 'co1', 'master_reference_no': 'CO-1', 'part_id': 'finished', 'raw_material_detail_id': 'link',
                'gross_weight_kg_snapshot': 3.69, 'supply_flow': flow, 'order_qty_pcs': order_qty, 'status': 'OPEN',
                'forging_supplier_id': 'supplier'},
        'co2': {'id': 'co2', 'master_reference_no': 'CO-2', 'part_id': 'finished', 'raw_material_detail_id': 'link',
                'gross_weight_kg_snapshot': 3.69, 'supply_flow': 'FSI_RM', 'order_qty_pcs': 50, 'status': 'OPEN',
                'forging_supplier_id': 'supplier'},
    }
    svc.order = lambda oid: deepcopy(orders.get(oid))
    svc.customer_orders = lambda: [deepcopy(o) for o in orders.values()]
    svc.repo.tables['parties'].append({'id': 'other-forger', 'status': 'ACTIVE', 'party_name': 'Other forger'})
    svc.repo.tables['supply_rm_dispatches'] = [
        {'id': 'd1', 'customer_order_id': 'co1', 'dispatch_number': 'DSP-1', 'forging_supplier_id': 'supplier',
         'heat_number': 'H-77', 'heat_code': 'HC7', 'inward_lot_id': 'inw-1', 'qty_kg': 400},
        {'id': 'd2', 'customer_order_id': 'co2', 'dispatch_number': 'DSP-2', 'forging_supplier_id': 'other-forger',
         'heat_number': 'H-88', 'heat_code': 'HC8', 'inward_lot_id': 'inw-2', 'qty_kg': 200},
    ]
    svc.repo.tables.setdefault('supply_forging_orders', [])
    svc._invalidate_transactions()
    return svc


def forging(svc, *sources, supplier='supplier'):
    return svc.create_purchase_order({**po_payload(), 'supplier_id': supplier, 'forging_sources': list(sources)})


def test_fsi_rm_forging_po_inherits_dispatch_forger_and_heat():
    svc = chain_service()
    disp = svc.repo.get('supply_rm_dispatches', 'd1')
    sources = svc.pending_forging_po_sources()
    assert sorted(r['_source_id'] for r in sources) == ['d1', 'd2']
    saved = forging(svc, {'customer_order_id': 'co1', 'quantity': 100, 'rm_dispatch': disp})
    stage = saved['stage']
    assert stage['rm_dispatch_id'] == 'd1' and stage['heat_number'] == 'H-77' and stage['heat_code'] == 'HC7'
    assert stage['inward_lot_id'] == 'inw-1' and stage['forging_supplier_id'] == 'supplier'
    svc._invalidate_transactions()
    assert 'd1' not in [r['_source_id'] for r in svc.pending_forging_po_sources()]


def test_fsi_rm_without_dispatch_is_rejected_before_any_write():
    svc = chain_service()
    before = len(svc.repo.writes)
    with pytest.raises(ValueError, match='RM-to-Forger dispatch'):
        forging(svc, {'customer_order_id': 'co1', 'quantity': 10})
    assert len(svc.repo.writes) == before


def test_wrong_forger_dispatch_is_rejected():
    svc = chain_service()
    with pytest.raises(ValueError, match='different forger'):
        forging(svc, {'customer_order_id': 'co2', 'quantity': 10, 'rm_dispatch': {'id': 'd2'}})


def test_dispatch_of_other_order_and_reused_dispatch_are_rejected():
    svc = chain_service()
    with pytest.raises(ValueError, match='different Customer Order'):
        forging(svc, {'customer_order_id': 'co1', 'quantity': 10, 'rm_dispatch': {'id': 'd2'}})
    forging(svc, {'customer_order_id': 'co1', 'quantity': 40, 'rm_dispatch': {'id': 'd1'}})
    svc._invalidate_transactions()
    with pytest.raises(ValueError, match='already linked'):
        forging(svc, {'customer_order_id': 'co1', 'quantity': 10, 'rm_dispatch': {'id': 'd1'}})


def test_cancelled_forging_po_releases_dispatch_for_reissue():
    svc = chain_service()
    forging(svc, {'customer_order_id': 'co1', 'quantity': 40, 'rm_dispatch': {'id': 'd1'}})
    for row in svc.repo.tables['supply_forging_orders']:
        row['status'] = 'CANCELLED'
    svc._invalidate_transactions()
    forging(svc, {'customer_order_id': 'co1', 'quantity': 40, 'rm_dispatch': {'id': 'd1'}})


def test_direct_production_order_never_gets_forging_po():
    svc = chain_service('FSI_RM_DIRECT_PRODUCTION')
    with pytest.raises(ValueError, match='Direct Production'):
        forging(svc, {'customer_order_id': 'co1', 'quantity': 10, 'rm_dispatch': {'id': 'd1'}})


def test_forging_quantity_cannot_exceed_order_balance():
    svc = chain_service('DIRECT_FORGING', order_qty=30)
    with pytest.raises(ValueError, match='exceeds the pending forging balance'):
        forging(svc, {'customer_order_id': 'co1', 'quantity': 31})
    forging(svc, {'customer_order_id': 'co1', 'quantity': 30})
