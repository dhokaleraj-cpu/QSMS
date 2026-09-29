from copy import deepcopy
import pytest
from core.osp_service import OSPService

REQ='00000000-0000-0000-0000-000000000123'
LINES=[{'inward_lot_id':'in-a','quantity_dispatched':10,'sample_quantity':1},{'inward_lot_id':'in-b','quantity_dispatched':20,'sample_quantity':2}]

class Repo:
    def __init__(self): self.calls=[]; self.tables={}
    def rpc(self,name,args):
        self.calls.append((name,deepcopy(args)))
        return {'id':'document','material_out_number':'OUT-1','lines':[{'id':str(i),**r} for i,r in enumerate(args.get('p_lines',[]))]}
    def select(self,table,eq=None,in_=None,**kwargs):
        return deepcopy([r for r in self.tables.get(table,[]) if all(r.get(k)==v for k,v in (eq or {}).items()) and all(r.get(k) in v for k,v in (in_ or {}).items())])

def service():
    obj=OSPService.__new__(OSPService); obj.repo=Repo(); return obj

def test_multi_save_is_one_atomic_rpc_with_both_source_ids():
    obj=service(); obj.create_material_out({'dispatch_challan':'CH-1'},LINES,REQ)
    assert len(obj.repo.calls)==1
    name,args=obj.repo.calls[0]
    assert name=='qcms_create_osp_material_out' and args['p_request_id']==REQ
    assert [r['inward_lot_id'] for r in args['p_lines']]==['in-a','in-b']
    assert [r['quantity_dispatched'] for r in args['p_lines']]==[10,20]

@pytest.mark.parametrize('bad',[[],[LINES[0],LINES[0]],[{'inward_lot_id':'a','opening_stock_id':'b','quantity_dispatched':1}],[{'quantity_dispatched':1}],[{**LINES[0],'quantity_dispatched':float('nan')}],[{**LINES[0],'quantity_dispatched':float('inf')}],[{**LINES[0],'quantity_dispatched':0}],[{**LINES[0],'quantity_dispatched':-1}],[{**LINES[0],'sample_quantity':11}],[{**LINES[0],'sample_quantity':float('nan')}],[{**LINES[0],'sample_quantity':0}]])
def test_bad_lines_rejected_without_any_remote_write(bad):
    obj=service()
    with pytest.raises(ValueError): obj.create_material_out({},bad,REQ)
    assert obj.repo.calls==[]


def test_save_response_requires_all_lines():
    obj=service(); obj.repo.rpc=lambda *a,**k:{'id':'doc','lines':[{'id':'one'}]}
    with pytest.raises(RuntimeError,match='same entry'): obj.create_material_out({},LINES,REQ)


def test_group_totals_do_not_merge_heat_jobs_and_legacy_still_visible():
    rows=[{'id':'a','material_out_id':'g','material_out_number':'OUT-1','material_out_line_no':1,'heat_number':'H1','rmtc_number':'R1','quantity_dispatched':10,'quantity_received':5,'status':'AT_VENDOR'}, {'id':'b','material_out_id':'g','material_out_number':'OUT-1','material_out_line_no':2,'heat_number':'H2','rmtc_number':'R2','quantity_dispatched':20,'quantity_received':20,'status':'COMPLETED'}, {'id':'old','osp_job_number':'OSP-OLD','heat_number':'H1','quantity_dispatched':3,'quantity_received':0,'status':'AT_VENDOR'}]
    before=deepcopy(rows); docs=OSPService.material_out_documents(rows)
    assert len(docs)==2 and docs[0]['quantity_dispatched']==30 and docs[0]['quantity_received']==25
    assert docs[0]['heat_numbers']=='H1, H2' and docs[0]['rmtc_numbers']=='R1, R2'
    assert docs[0]['status']=='PARTIAL / MIXED' and not docs[1]['is_group']
    assert [r['id'] for r in docs[0]['lines']]==['a','b'] and rows==before


def test_rmtc_enrichment_uses_inward_certificate_id_not_heat_number():
    obj=service(); obj.repo.tables={'inward_lots':[{'id':'in-a','rmtc_approval_id':'r-a'},{'id':'in-b','rmtc_approval_id':'r-b'}], 'rmtc_approvals':[{'id':'r-a','rmtc_number':'R1','certificate_reference':'SUP1'},{'id':'r-b','rmtc_number':'R2','certificate_reference':'SUP2'}]}
    result=obj._enrich_rmtc([{'source_inward_lot_id':'in-a','heat_number':'SAME'},{'source_inward_lot_id':'in-b','heat_number':'SAME'}])
    assert [r['rmtc_number'] for r in result]==['R1','R2']
    assert [r['supplier_rmtc_number'] for r in result]==['SUP1','SUP2']


def test_receipt_and_inspection_eligibility_remain_per_heat():
    obj=service(); rows=[{'id':'a','material_out_id':'g','quantity_dispatched':10,'quantity_received':5,'sample_gate_status':'ACCEPTED','sample_received_date':'2026-09-29','dimensional_required':True,'status':'AT_VENDOR'}, {'id':'b','material_out_id':'g','quantity_dispatched':20,'quantity_received':0,'sample_gate_status':'PENDING','dimensional_required':True,'status':'AT_VENDOR'}]
    obj.register=lambda:rows
    assert [r['id'] for r in obj.jobs_for_full_receipt()]==['a']
    assert [r['id'] for r in obj.jobs_for_sample_receipt()]==['b']
    assert obj.jobs_for_inspection('OSP_RECEIPT','DIMENSIONAL')==[]
    rows[0]['quantity_received']=10
    assert [r['id'] for r in obj.jobs_for_inspection('OSP_RECEIPT','DIMENSIONAL')]==['a']
    assert rows[1]['sample_gate_status']=='PENDING'


def test_each_downstream_rpc_keeps_selected_heat_job_id():
    obj=service()
    obj.record_sample({'osp_job_id':'a','sample_received_date':'2026-09-29','sample_reference':'S1','vendor_batch_number':'VA'})
    obj.receive_batch({'osp_job_id':'b','receipt_date':'2026-09-29','receipt_challan':'RC','vendor_invoice_number':'INV','vendor_invoice_date':'2026-09-29','tc_number':'TC','tc_date':'2026-09-29','vendor_batch_number':'VB','quantity_received':5})
    assert obj.repo.calls[0][1]['p_osp_job_id']=='a'
    assert obj.repo.calls[1][1]['p_osp_job_id']=='b'


def test_streamlit_multiple_sources_submit_one_document():
    from streamlit.testing.v1 import AppTest
    script='''
import streamlit as st
from app_pages.osp_transactions import _render_material_out_entry
from core.osp_service import OSPService
class Repo:
 def rpc(self,name,args):
  st.session_state['submitted_rpc']={'name':name,'args':args}
  return {'id':'doc','material_out_number':'OUT-TEST','lines':[{'id':str(i),**r} for i,r in enumerate(args['p_lines'])]}
class Service(OSPService):
 def __init__(self): self.repo=Repo()
 def dispatch_candidates(self): return [{'candidate_key':'INWARD:a','inward_lot_id':'a','part_id':'part','part_number':'PN','rmtc_number':'RM-A','heat_number':'HA','inward_number':'IN-A','osp_available_quantity_pcs':10}, {'candidate_key':'INWARD:b','inward_lot_id':'b','part_id':'part','part_number':'PN','rmtc_number':'RM-B','heat_number':'HB','inward_number':'IN-B','osp_available_quantity_pcs':20}]
 def specifications(self,part): return [{'id':'spec','process_id':'process','sample_quantity':1}]
 def processes(self): return {'process':{'id':'process','process_name':'Heat Treatment'}}
 def vendors(self): return [{'id':'vendor','party_name':'OSP Vendor'}]
_render_material_out_entry(Service(),{'can_create':True})
'''
    app=AppTest.from_string(script).run(timeout=20)
    assert not app.exception
    app.multiselect[0].select('INWARD:a').select('INWARD:b').run()
    assert not app.exception
    next(x for x in app.text_input if x.label=='Material Out Challan Number').set_value('CH-MULTI')
    next(x for x in app.button if x.label=='Create OSP Material Out').click().run(timeout=20)
    assert not app.exception
    saved=app.session_state['submitted_rpc']
    assert saved['name']=='qcms_create_osp_material_out'
    assert len(saved['args']['p_lines'])==2
    assert saved['args']['p_header']['dispatch_challan']=='CH-MULTI'
