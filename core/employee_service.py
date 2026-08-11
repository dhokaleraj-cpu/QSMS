from __future__ import annotations
from datetime import date
from typing import Any
from core.repository import Repository

AUTHORITIES = [
 'RMTC_PREPARE','RMTC_VALIDATE','RMTC_APPROVE','MATERIAL_INWARD_PREPARE','RAW_MATERIAL_INSPECTION','SETUP_APPROVAL',
 'STAGE_INSPECTION','OSP_QUALITY_RELEASE','LAB_VALIDATION','FINAL_QUALITY_RELEASE',
 'PPAP_APPROVAL','CALIBRATION_APPROVAL','AUDIT_APPROVAL'
]

class EmployeeService:
    def __init__(self): self.repo=Repository()
    def list(self, active_only=False):
        return self.repo.select('employees', eq={'status':'ACTIVE'} if active_only else {}, order_by='first_name', limit=1000)
    def options(self, authority=None):
        rows=self.list(True)
        if authority: rows=[r for r in rows if authority in (r.get('approval_authorities') or [])]
        return {str(r['id']): f"{r.get('first_name','')} {r.get('last_name','')} · {r.get('designation','')}" for r in rows}
    def save(self, payload:dict[str,Any], record_id:str|None=None):
        payload=dict(payload)
        for k in ('first_name','last_name','email','department','designation','plant','employee_code'):
            if not str(payload.get(k) or '').strip(): raise ValueError(f"{k.replace('_',' ').title()} is mandatory.")
        rows=self.list(False)
        for field in ('employee_code','email'):
            value=' '.join(str(payload.get(field) or '').split()).casefold()
            if not value: continue
            for row in rows:
                if record_id and str(row.get('id'))==str(record_id): continue
                if ' '.join(str(row.get(field) or '').split()).casefold()==value:
                    raise ValueError(f"Duplicate {field.replace('_',' ').title()} is not allowed.")
        if record_id: return self.repo.update('employees',record_id,payload)
        return self.repo.insert('employees',payload)
    @staticmethod
    def years(start):
        if not start:return 0
        d=date.fromisoformat(str(start)[:10]); t=date.today(); return t.year-d.year-((t.month,t.day)<(d.month,d.day))
