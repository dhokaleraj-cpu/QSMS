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


# ---------------------------------------------------------------------------------------------------------------
# R38 · employee photo + reporting / escalation details (Employee Master view)
# ---------------------------------------------------------------------------------------------------------------
PHOTO_BUCKET = 'quality-documents'
PHOTO_MAX_BYTES = 3 * 1024 * 1024
ESCALATION_MAX_LEVELS = 4


def employee_name(row: dict | None) -> str:
    row = row or {}
    return ' '.join(str(row.get(k) or '').strip() for k in ('first_name', 'last_name')).strip() or str(row.get('employee_code') or '')


def escalation_chain(rows: list[dict], employee_id: str, max_levels: int = ESCALATION_MAX_LEVELS) -> list[dict]:
    """reports_to → their reports_to … up to ``max_levels`` levels (cycle-safe). Each item carries ``level`` 1..n."""
    by_id = {str(r.get('id')): r for r in rows or []}
    chain: list[dict] = []
    seen = {str(employee_id)}
    current = by_id.get(str(employee_id)) or {}
    while len(chain) < max_levels:
        manager_id = str(current.get('reports_to_employee_id') or '')
        if not manager_id or manager_id in seen or manager_id not in by_id:
            break
        seen.add(manager_id)
        current = by_id[manager_id]
        chain.append({**current, 'level': len(chain) + 1})
    return chain


def direct_reports(rows: list[dict], employee_id: str) -> list[dict]:
    return sorted((r for r in rows or [] if str(r.get('reports_to_employee_id') or '') == str(employee_id)
                   and str(r.get('id')) != str(employee_id)), key=employee_name)


def approver_routes(routes: list[dict], employee_id: str) -> list[dict]:
    """Approval-route levels (qcms_module_approval_routes) where this employee is the approver."""
    found = [r for r in routes or [] if str(r.get('employee_id') or '') == str(employee_id)
             and str(r.get('status') or 'ACTIVE').upper() not in {'INACTIVE', 'ARCHIVED'}]
    return sorted(found, key=lambda r: (str(r.get('module_key') or ''), str(r.get('department') or ''), int(r.get('level_no') or 0)))


def schedule_escalations(schedules: list[dict], employee_id: str) -> list[dict]:
    """Notification schedules (qcms_notification_schedules) where this employee is the overdue Level-1 / Level-2 escalation."""
    out: list[dict] = []
    for sch in schedules or []:
        for level in (1, 2):
            if str(sch.get(f'overdue_level{level}_employee_id') or '') == str(employee_id) and str(employee_id):
                out.append({
                    'schedule_key': sch.get('schedule_key'), 'schedule_label': sch.get('schedule_label') or sch.get('schedule_key'),
                    'module_key': sch.get('module_key'), 'department': sch.get('recipient_department'), 'level': level,
                    'after_hours': sch.get(f'overdue_level{level}_after_hours'), 'enabled': bool(sch.get('enabled', True)),
                })
    return sorted(out, key=lambda r: (str(r.get('schedule_label') or ''), int(r.get('level') or 0)))


def employee_details(rows: list[dict], routes: list[dict], employee_id: str, schedules: list[dict] | None = None) -> dict[str, Any]:
    by_id = {str(r.get('id')): r for r in rows or []}
    me = by_id.get(str(employee_id)) or {}
    chain = escalation_chain(rows, employee_id)
    mine = approver_routes(routes, employee_id)
    departments = sorted({d for d in [str(me.get('department') or '').strip()] + [str(r.get('department') or '').strip() for r in mine] if d})
    return {
        'employee': me,
        'reporting_to': chain[0] if chain else {},
        'escalation': chain,
        'direct_reports': direct_reports(rows, employee_id),
        'approval_routes': mine,
        'schedule_escalations': schedule_escalations(schedules or [], employee_id),
        'departments': departments,
    }


def photo_path(tenant_id: str, employee_id: str, filename: str) -> str:
    ext = (str(filename or '').rsplit('.', 1)[-1] or 'jpg').lower()
    ext = 'jpg' if ext == 'jpeg' else ext
    if ext not in {'jpg', 'png'}:
        raise ValueError('Use a JPG or PNG photo.')
    return f"{tenant_id}/employees/{employee_id}/photo_{employee_id}.{ext}"


def upload_employee_photo(repo: Repository, employee_id: str, file: Any) -> str:
    """Store the photo in quality-documents/{tenant}/employees/{id}/ and save employees.photo_storage_path."""
    from core.database import get_session_client

    data = file.getvalue() if hasattr(file, 'getvalue') else bytes(file or b'')
    if not data:
        raise ValueError('The selected photo is empty.')
    if len(data) > PHOTO_MAX_BYTES:
        raise ValueError('Use a photo smaller than 3 MB.')
    path = photo_path(repo.tenant_id, employee_id, getattr(file, 'name', 'photo.jpg'))
    client = get_session_client()
    if client is None:
        raise RuntimeError('A live QCMS session is required to upload the photo.')
    mime = getattr(file, 'type', None) or ('image/png' if path.endswith('.png') else 'image/jpeg')
    client.storage.from_(PHOTO_BUCKET).upload(path, data, {'content-type': mime, 'upsert': 'true'})
    repo.update('employees', str(employee_id), {'photo_storage_path': path})
    try:
        import streamlit as st
        st.session_state.get('_qcms_r38_employee_photo_cache', {}).pop(path, None)
    except Exception:
        pass
    return path


def employee_photo_bytes(path: str | None) -> bytes | None:
    if not path:
        return None
    try:
        import streamlit as st
        cache = st.session_state.setdefault('_qcms_r38_employee_photo_cache', {})
    except Exception:
        cache = {}
    if path in cache:
        return cache[path]
    try:
        from core.database import get_session_client
        client = get_session_client()
        data = bytes(client.storage.from_(PHOTO_BUCKET).download(path)) if client else None
    except Exception:
        data = None
    cache[path] = data
    return data
