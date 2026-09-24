from copy import deepcopy
import pytest
from core.inspection_service import InspectionService

RAW={"id":"raw","part_id":"40257237","layout_type":"METLAB","inward_type":"MATERIAL_INWARD","requirement_scope":"GENERAL","status":"APPROVED"}
FINAL={**RAW,"id":"final","requirement_scope":"FINAL_METALLURGICAL"}
OSP={**RAW,"id":"osp","inward_type":"OSP_PROCESS","requirement_scope":"OSP_METLAB","process_id":"heat"}
class Repo:
    def __init__(self): self.saved=None
    def insert(self, table, payload): self.saved=deepcopy(payload); return {"id":"report",**payload}
    def update(self, table, record_id, payload): return self.insert(table,payload)

def service(plans=None):
    svc=InspectionService.__new__(InspectionService); svc.repo=Repo()
    svc.plans=lambda *a,**k: plans if plans is not None else [RAW,FINAL,OSP]
    svc.get_plan=lambda key: {p['id']:p for p in [RAW,FINAL,OSP]}.get(key)
    svc.plan_characteristics=lambda key: [{"id":"hardness","characteristic":"HARDNESS","lower_spec":140,"upper_spec":210}] if key=='raw' else [{"id":"case-depth"}]
    return svc

def test_no_final_fallback_when_raw_layout_is_missing():
    assert service([FINAL,OSP]).standalone_plans('METLAB','40257237','RAW_MATERIAL_STAGE')==[]

def test_final_dispatch_requires_final_layout():
    assert service([RAW,OSP]).standalone_plans('METLAB','40257237','FINAL_DISPATCH_STAGE')==[]
    assert service().standalone_plans('METLAB','40257237','FINAL_DISPATCH_STAGE')==[FINAL]

@pytest.mark.parametrize('scope,inward',[('RAW_MATERIAL_STAGE',None),(None,'inward')])
def test_raw_save_keeps_layout_rows_and_drops_section_h(scope,inward):
    svc=service(); results={"rows":[{"inspection_plan_characteristic_id":"hardness","actual_value":168},{"inspection_plan_characteristic_id":"case-depth","actual_value":1}],"requirement_rows":[{"requirement_name":"ENP Layer"}],"chemistry_rows":[{"element":"C"}]}
    original=deepcopy(results)
    saved=svc.save_metlab({"part_id":"40257237","layout_plan_id":"raw","inspection_scope":scope,"inward_lot_id":inward},results)
    assert saved['results']['rows']==[results['rows'][0]]
    assert saved['results']['requirement_rows']==[]
    assert saved['results']['chemistry_rows']==[]
    assert results==original

@pytest.mark.parametrize('scope',['RAW_MATERIAL_STAGE','OSP_STAGE','OSP_SAMPLE'])
def test_final_layout_rejected_outside_dispatch(scope):
    svc=service()
    with pytest.raises(ValueError,match='Final Dispatch'):
        svc.save_metlab({"part_id":"40257237","layout_plan_id":"final","inspection_scope":scope},{"rows":[]})
    assert svc.repo.saved is None

def test_final_requirements_preserved_at_dispatch():
    results={"rows":[{"inspection_plan_characteristic_id":"case-depth","actual_value":1}],"requirement_rows":[{"requirement_name":"Core Hardness"}]}
    saved=service().save_metlab({"part_id":"40257237","layout_plan_id":"final","inspection_scope":"FINAL_DISPATCH_STAGE"},results)
    assert saved['results']['rows']==results['rows']
    assert saved['results']['requirement_rows']==results['requirement_rows']


def test_raw_layout_without_case_depth_excludes_legacy_traverse():
    record = {"part_id":"40257237", "layout_plan_id":"raw"}
    old = {"rows":[], "case_depth_applicable":True, "case_depth_locations":[{"location":"Final"}], "case_depth_traverse":[{"depth":0.1,"hardness":650}]}
    clean = service().raw_material_results(record, old)
    assert not clean["case_depth_applicable"]
    assert clean["case_depth_locations"] == clean["case_depth_traverse"] == []
    assert old["case_depth_applicable"] is True


def test_saved_raw_report_reloads_limits_from_layout_not_legacy_rows():
    from app_pages.metlab_report import _layout_rows
    existing={"inspection_scope":"RAW_MATERIAL_STAGE", "results":{"rows":[{"inspection_plan_characteristic_id":"hardness","lower_spec":999,"actual_value":168},{"inspection_plan_characteristic_id":"case-depth","actual_value":1}]}}
    rows=_layout_rows(service(),'raw',existing)
    assert len(rows)==1
    assert rows[0]['lower_spec']==140
    assert rows[0]['upper_spec']==210
    assert rows[0]['actual_value']==168
    assert existing['results']['rows'][0]['lower_spec']==999
