from copy import deepcopy
from datetime import date
import pytest
from core.raw_source import resolve_raw_source, effective_link, current_approvals
from core.supply_chain_service import SupplyChainService

FINISHED = {'id':'finished','part_number':'10199346','status':'ACTIVE','part_name':'Finished housing'}
SOURCE = {'id':'source','part_number':'10121529','fsi_part_number':'1529','status':'ACTIVE','part_name':'Raw forging'}
LINK = {'id':'link','part_id':'finished','source_part_id':'source','supplier_id':'supplier','material_section_name':'Forging','status':'ACTIVE','gross_weight_kg':99,'material_grade_id':'old-grade'}
RAW = {'id':'new','part_id':'source','supplier_id':'supplier','material_section_name':'Forging','status':'ACTIVE','gross_weight_kg':3.69,'forging_weight_kg':2.95,'input_weight_kg':3.69,'material_grade_id':'grade','hsn_sac_code':'87089900','section_size':'65 MM','lead_time_days':45,'updated_at':'2026-09-24'}
APPROVAL = {'id':'approval','part_id':'source','supplier_id':'supplier','approved':True,'valid_from':'2020-01-01','valid_to':'2099-01-01','approval_reference':'AP-RAW'}

class Repo:
    def __init__(self):
        self.tables={'parts':[deepcopy(FINISHED),deepcopy(SOURCE)], 'part_raw_material_details':[deepcopy(LINK),{**RAW,'id':'old','updated_at':'2025-01-01','gross_weight_kg':2},deepcopy(RAW)],
                     'part_supplier_links':[deepcopy(APPROVAL)], 'parties':[{'id':'supplier','status':'ACTIVE','party_name':'Forge supplier'}],
                     'company_branches':[{'id':'branch','status':'ACTIVE'}], 'employees':[{'id':'employee','first_name':'Tester','status':'ACTIVE'}],
                     'part_supplier_price_history':[{'id':'price','part_id':'source','raw_material_detail_id':'new','supplier_id':'supplier','start_date':'2020-01-01','price':125,'uom':'NOS','status':'ACTIVE'}, {'id':'stale','part_id':'finished','raw_material_detail_id':'link','supplier_id':'supplier','start_date':'2020-01-01','price':999,'uom':'NOS','status':'ACTIVE'}]}
        self.writes=[]
    def select(self, table, eq=None, **kwargs):
        return deepcopy([r for r in self.tables.get(table,[]) if all(r.get(k)==v for k,v in (eq or {}).items())])
    def get(self, table, key):
        return next((r for r in self.select(table) if r.get('id')==key),None)
    def insert(self, table, payload):
        row={'id':f'{table}-{len(self.writes)}',**deepcopy(payload)}
        self.tables.setdefault(table,[]).append(row); self.writes.append((table,row)); return row
    def update(self, table, key, payload):
        for row in self.tables.get(table,[]):
            if row['id']==key: row.update(deepcopy(payload)); self.writes.append((table,row)); return deepcopy(row)
        raise AssertionError((table,key))
    def rpc(self,*a,**k): return 'PD9-TEST'

def service():
    svc=SupplyChainService(Repo())
    svc.order=lambda oid: {'id':oid,'part_id':'finished','raw_material_detail_id':'link','gross_weight_kg_snapshot':99}
    svc.save_transaction=lambda table,payload: svc.repo.insert(table,payload)
    svc.sync_order_status=lambda oid: None
    return svc

def po_payload():
    return dict(po_type='FORGING',supplier_id='supplier',company_branch_id='branch',ship_to_source_type='BRANCH',ship_to_branch_id='branch',requisitioner_employee_id='employee',order_date='2026-09-24',forging_sources=[{'customer_order_id':'customer-order','quantity':10}])

def test_current_source_overrides_finished_and_older_copy_without_changing_link_identity():
    svc=service(); effective=svc.raw_material_options('finished')[0]
    assert effective['id']=='link' and effective['part_id']=='finished'
    assert effective['gross_weight_kg']==3.69 and effective['_source_raw_id']=='new'
    svc.repo.tables['part_raw_material_details'][-1]['gross_weight_kg']=4.2
    assert svc.raw_material_options('finished')[0]['gross_weight_kg']==4.2
    assert svc.effective_current_price(FINISHED,LINK,'supplier',on_date='2026-09-24',uom='NOS')==125

@pytest.mark.parametrize('change,error',[
    ('no_rows','ACTIVE Section E'),('inactive_part','must be ACTIVE'),('expired','approval'),('future','approval'),('unapproved','approval'),('wrong_supplier','ACTIVE Section E'),('nested','nested')])
def test_invalid_source_never_uses_stale_finished_data_or_inserts_po(change,error):
    svc=service(); repo=svc.repo
    if change=='no_rows': repo.tables['part_raw_material_details']=[deepcopy(LINK)]
    elif change=='inactive_part': repo.tables['parts'][1]['status']='INACTIVE'
    elif change=='expired': repo.tables['part_supplier_links'][0]['valid_to']='2000-01-01'
    elif change=='future': repo.tables['part_supplier_links'][0]['valid_from']='2099-01-01'
    elif change=='unapproved': repo.tables['part_supplier_links'][0]['approved']=False
    elif change=='wrong_supplier':
        for r in repo.tables['part_raw_material_details'][1:]: r['supplier_id']='other'
    elif change=='nested': repo.tables['part_raw_material_details'][-1]['source_part_id']='finished'
    with pytest.raises(ValueError,match=error): svc.create_purchase_order(po_payload())
    assert repo.writes==[]
    assert svc.raw_material_options('finished')[0]['gross_weight_kg'] is None


def test_forging_po_purchases_raw_part_and_preserves_customer_order_genealogy():
    svc=service(); saved=svc.create_purchase_order(po_payload()); item=saved['item']
    assert item['item_no']=='10121529'
    assert item['part_id']=='finished' and item['original_part_number_snapshot']=='10199346'
    assert item['customer_order_id']=='customer-order' and item['raw_material_detail_id']=='link'
    assert item['material_grade_id']=='grade' and item['gross_weight_kg']==3.69
    assert item['unit_price']==125 and item['line_total']==1250
    assert saved['stage']['required_rm_kg']==36.9
    technical={r['heading']:r['value'] for r in item['technical_data_snapshot']}
    assert technical['Source Raw Forging / Casting Part']=='10121529'
    assert technical['Source Raw Material Detail ID']=='new'
    assert 'AP-RAW' in technical['Supplier Approval']
    assert item['price_history_snapshot'][0]['raw_material_detail_id']=='new'
    allocation=svc.repo.tables['supply_purchase_order_sources'][0]
    assert allocation['customer_order_id']=='customer-order' and allocation['allocated_qty']==10


def test_customer_order_revalidates_source_weight_and_keeps_finished_part():
    svc=service(); payload={'part_id':'finished','raw_material_detail_id':'link','gross_weight_kg_snapshot':99}
    svc._refresh_order_raw_source(payload)
    assert payload['part_id']=='finished' and payload['raw_material_detail_id']=='link'
    assert payload['gross_weight_kg_snapshot']==3.69 and payload['forging_supplier_id']=='supplier'

@pytest.mark.parametrize('field,value',[('uom','KGS'),('raw_material_detail_id','other'),('status','INACTIVE')])
def test_wrong_source_price_cannot_fall_back_to_finished_price(field,value):
    svc=service(); svc.repo.tables['part_supplier_price_history'][0][field]=value
    with pytest.raises(ValueError,match='current supplier price is missing'): svc.create_purchase_order(po_payload())
    assert svc.repo.writes==[]


def test_approval_boundaries_inclusive():
    repo=Repo(); approval=repo.tables['part_supplier_links'][0]; approval.update(valid_from='2026-09-24',valid_to='2026-09-24')
    assert current_approvals(repo,'source','supplier',date(2026,9,24))
    assert not current_approvals(repo,'source','supplier',date(2026,9,25))


def test_own_unlinked_raw_details_unchanged():
    raw={**RAW,'source_part_id':None}
    assert effective_link(Repo(),SOURCE,raw)==raw


def test_reprint_keeps_purchased_source_snapshot_after_master_change():
    svc=service(); saved=svc.create_purchase_order(po_payload()); item=deepcopy(saved['item'])
    svc.purchase_order=lambda key: saved['header']
    svc.purchase_order_items=lambda key: [item]
    svc.purchase_order_sources=lambda key: svc.repo.select('supply_purchase_order_sources')
    svc.customer_orders=lambda: [svc.order('customer-order')]
    svc.master_maps=lambda: ({'finished':FINISHED}, {}, {})
    svc.repo.tables['part_supplier_price_history'][0]['price']=800
    printed=svc.purchase_order_items_for_print(saved['header']['id'])[0]
    assert printed['unit_price']==125
    assert printed['price_history_snapshot'][0]['price']==125
    assert printed['part_description_master']=='Raw forging'
    assert printed['customer_source_rows'][0]['part_number']=='10199346'


def test_po_revision_refreshes_linked_source_not_finished_copy(monkeypatch):
    import core.supply_chain_service as module
    monkeypatch.setattr(module,'current_employee_id',lambda **kw:'employee')
    svc=service(); saved=svc.create_purchase_order(po_payload())
    svc.purchase_order=lambda key: svc.repo.get('supply_purchase_orders',key)
    svc.purchase_order_items=lambda key: svc.repo.select('supply_purchase_order_items',eq={'purchase_order_id':key})
    svc.purchase_order_sources=lambda key: svc.repo.select('supply_purchase_order_sources',eq={'purchase_order_id':key})
    svc.forging_orders=lambda: svc.repo.select('supply_forging_orders')
    svc.forging_receipts=lambda: []
    svc.purchase_order_item_received_qty=lambda key: 0
    svc.repo.tables['part_raw_material_details'][-1]['gross_weight_kg']=4.2
    svc.repo.tables['part_supplier_price_history'][0]['price']=150
    svc.update_purchase_order(saved['header']['id'],{'refresh_master_data':True})
    updated=svc.repo.get('supply_purchase_order_items',saved['item']['id'])
    assert updated['unit_price']==150 and updated['gross_weight_kg']==4.2
    assert updated['item_no']=='10121529'
    assert svc.repo.tables['supply_forging_orders'][0]['required_rm_kg']==42


def test_revoked_approval_blocks_revision_before_any_write(monkeypatch):
    import core.supply_chain_service as module
    monkeypatch.setattr(module,'current_employee_id',lambda **kw:'employee')
    svc=service(); saved=svc.create_purchase_order(po_payload())
    svc.purchase_order=lambda key:saved['header']
    svc.purchase_order_items=lambda key:saved['items']
    svc.purchase_order_sources=lambda key:svc.repo.select('supply_purchase_order_sources')
    svc.repo.tables['part_supplier_links'][0]['approved']=False
    count=len(svc.repo.writes)
    with pytest.raises(ValueError,match='approval'): svc.update_purchase_order(saved['header']['id'],{'refresh_master_data':True})
    assert len(svc.repo.writes)==count


def test_raw_forging_may_own_bar_details_without_changing_finished_link_type():
    svc=service(); svc.repo.tables['part_raw_material_details'][-1]['material_section_name']='Round Black Bar'
    effective=svc.raw_material_options('finished')[0]
    assert effective['material_section_name']=='Forging'
    assert effective['gross_weight_kg']==3.69
    item=svc.create_purchase_order(po_payload())['item']
    tech={r['heading']:r['value'] for r in item['technical_data_snapshot']}
    assert item['item_no']=='10121529' and tech['Raw Material Type']=='Round Black Bar'


def test_current_master_read_does_not_accept_repository_fallback_cache(monkeypatch):
    from core.repository import Repository
    repo=Repository.__new__(Repository); repo.preview=False; repo.client=object()
    monkeypatch.setattr(repo,'_retry',lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('offline')))
    monkeypatch.setattr(repo,'_read_cache',lambda: pytest.fail('A strict read must not fall back to cache'))
    with pytest.raises(RuntimeError,match='offline'): repo.select('parts',require_live=True)
    with pytest.raises(ValueError,match='Cannot verify'): resolve_raw_source(repo,FINISHED,LINK)
