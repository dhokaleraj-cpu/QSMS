from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

from core.calculations import band_status, calculate_di, calculate_jominy_curve
from core.attachments import AttachmentService
from core.database import get_session_client
from core.repository import Repository


class RMTCService:
    def __init__(self) -> None:
        self.repo=Repository()

    def parts(self):
        return self.repo.select('parts',eq={'status':'ACTIVE'},order_by='part_number',limit=2000)

    def parties(self,kind):
        return self.repo.select('parties',contains={'party_types':[kind]},eq={'status':'ACTIVE'},order_by='party_name',limit=2000)

    def source_details(self, part_id):
        value = str(part_id or '').strip()
        if not value:
            return []
        return self.repo.select('part_raw_material_details', eq={'part_id': value, 'status': 'ACTIVE'}, order_by='sequence_no', limit=200)

    def employees(self,authority):
        rows=self.repo.select('employees',eq={'status':'ACTIVE'},order_by='first_name',limit=2000)
        return [r for r in rows if authority in (r.get('approval_authorities') or [])]

    def chemistry_template(self,material_grade_id):
        return self.repo.select('material_grade_elements',eq={'material_grade_id':material_grade_id},order_by='element',limit=200)

    def jominy_template(self,part_id):
        """Return Part Jominy requirements with a reliable 1/16-inch -> mm conversion.

        New records carry ``jominy_distance_id``. Older trial/master rows sometimes
        contained only the distance label (and a few labels included a leading J),
        so we resolve by ID first and then by a normalized label/fraction fallback.
        """
        reqs=self.repo.select('part_jominy_requirements',eq={'part_id':part_id,'status':'ACTIVE'},order_by='sequence_no',limit=100)
        distances=self.repo.select('jominy_distances',eq={'status':'ACTIVE'},order_by='distance_16th',limit=100)
        by_id={str(d.get('id')):d for d in distances if d.get('id')}
        def norm(value):
            text=str(value or '').strip().upper().replace('INCH','').replace('IN.','').replace('IN','').replace('″','"')
            text=text.replace(' ', '').replace('J','',1) if text.startswith('J') else text.replace(' ', '')
            return text.rstrip('"')
        by_label={norm(d.get('distance_label')):d for d in distances}
        prepared=[]
        for requirement in reqs:
            distance=by_id.get(str(requirement.get('jominy_distance_id') or '')) or by_label.get(norm(requirement.get('distance_label')))
            sixteenth=int((distance or {}).get('distance_16th') or 0)
            if not sixteenth:
                import re
                match=re.search(r'(\d+)\s*/\s*16', str(requirement.get('distance_label') or ''), re.I)
                sixteenth=int(match.group(1)) if match else 0
                distance=next((row for row in distances if int(row.get('distance_16th') or 0)==sixteenth), distance)
            prepared.append({**requirement,'jominy_distance_id':(distance or {}).get('id') or requirement.get('jominy_distance_id'),'distance_16th':sixteenth,'distance_mm':round(float(sixteenth)*25.4/16,2) if sixteenth else None})
        return prepared

    def requirements(self,part_id):
        rows = self.repo.select(
            'part_metallurgical_requirements',
            eq={'part_id':part_id,'status':'ACTIVE'},
            order_by='sequence_no',
            limit=200,
        )
        if rows:
            prepared = []
            for row in rows:
                lower = row.get('minimum_spec')
                upper = row.get('maximum_spec')
                ctype = str(row.get('characteristic_type') or 'NUMBER').upper()
                if ctype in ('TEXT', 'ATTRIBUTE'):
                    requirement = str(row.get('specification_text') or '').strip()
                else:
                    requirement = ' '.join(
                        value for value in (
                            f"Min {lower}" if lower is not None else '',
                            f"Max {upper}" if upper is not None else '',
                        ) if value
                    )
                prepared.append({
                    **row,
                    'parameter_name': row.get('parameter_name'),
                    'requirement_value': requirement,
                })
            return prepared
        return self.repo.select(
            'part_heat_treatment_details',
            eq={'part_id':part_id,'status':'ACTIVE'},
            order_by='sequence_no',
            limit=200,
        )

    @staticmethod
    def normalize_heat_number(value: Any) -> str:
        return re.sub(r'[^A-Za-z0-9]', '', str(value or '')).upper()

    @staticmethod
    def normalize_supplier_rmtc_number(value: Any) -> str:
        return re.sub(r'[^A-Za-z0-9]', '', str(value or '')).upper()

    def heat_summary(self, heat_number: str) -> dict:
        normalized=self.normalize_heat_number(heat_number)
        if not normalized:return {}
        rows=self.repo.select('v_qsms_heat_summary',eq={'normalized_heat_number':normalized},limit=1)
        return rows[0] if rows else {}

    def heat_usage(self, heat_number: str) -> list[dict]:
        normalized=self.normalize_heat_number(heat_number)
        if not normalized:return []
        return self.repo.select('v_qsms_heat_steel_ledger',eq={'normalized_heat_number':normalized},order_by='created_at',desc=True,limit=500)

    def heat_ledger(self, heat_number: str | None = None) -> list[dict]:
        eq = {}
        normalized = self.normalize_heat_number(heat_number) if heat_number else ''
        if normalized:
            eq['normalized_heat_number'] = normalized
        return self.repo.select('v_qsms_heat_steel_ledger', eq=eq or None, order_by='updated_at', desc=True, limit=5000)

    def supplier_rmtc_duplicate(self, heat_number: str, supplier_rmtc_number: str, exclude_rmtc_id: str | None = None) -> dict | None:
        heat_key = self.normalize_heat_number(heat_number)
        ref_key = self.normalize_supplier_rmtc_number(supplier_rmtc_number)
        if not heat_key or not ref_key:
            return None
        rows = self.repo.select('rmtc_approvals', eq={
            'normalized_heat_number': heat_key,
            'normalized_supplier_rmtc_number': ref_key,
        }, order_by='created_at', desc=True, limit=20)
        return next((row for row in rows if str(row.get('id')) != str(exclude_rmtc_id or '')), None)

    def list(self):
        return self.repo.select('rmtc_approvals',order_by='created_at',desc=True,limit=2000)

    def get(self,rmtc_id):
        return self.repo.get('rmtc_approvals',rmtc_id)

    def covered_parts(self,rmtc_id):
        return self.repo.select('rmtc_part_approvals',eq={'rmtc_approval_id':rmtc_id},order_by='created_at',limit=100)

    def details(self,rmtc_id,part_id=None):
        eq={'rmtc_approval_id':rmtc_id}
        if part_id: eq['part_id']=part_id
        return {
            'parts':self.covered_parts(rmtc_id),
            'chemistry':self.repo.select('rmtc_chemistry_results',eq=eq,order_by='element',limit=300),
            'jominy':self.repo.select('rmtc_jominy_results',eq=eq,order_by='distance_mm',limit=300),
            'requirements':self.repo.select('rmtc_requirement_results',eq=eq,order_by='sequence_no',limit=300),
        }

    # Previous local guard used find_one('rmtc_approvals', eq={'rmtc_number': ...});
    # idempotency is now enforced atomically by qsms_save_rmtc_header.
    # Legacy initializer call was self.repo.rpc('qsms_initialize_rmtc_details', ...);
    # The atomic server save still invokes qsms_initialize_rmtc_details before returning.
    def save_header(self, payload, part_ids, rmtc_id: str | None = None):
        """Atomically save a Draft header and initialize all covered Part Worksheets."""
        return self.repo.rpc('qsms_save_rmtc_header', {
            'p_rmtc_id': str(rmtc_id) if rmtc_id else None,
            'p_payload': payload,
            'p_part_ids': [str(value) for value in part_ids],
        })

    def create_header(self, payload, part_ids):
        return self.save_header(payload, part_ids, None)

    def update_header(self, rmtc_id, payload, part_ids):
        return self.save_header(payload, part_ids, rmtc_id)

    def add_part_to_approved_rmtc(self, rmtc_id: str, part_id: str) -> dict:
        return self.repo.rpc('qsms_add_part_to_approved_rmtc', {
            'p_rmtc_id': rmtc_id, 'p_part_id': part_id,
        }) or {}

    def validate_added_part(self, rmtc_id: str, part_id: str) -> dict:
        return self.repo.rpc('qsms_validate_added_rmtc_part', {
            'p_rmtc_id': rmtc_id, 'p_part_id': part_id,
        }) or {}

    def decide_added_part(self, rmtc_id: str, part_id: str, disposition: str, reason: str | None, approver_id: str) -> dict:
        return self.repo.rpc('qsms_decide_added_rmtc_part', {
            'p_rmtc_id': rmtc_id, 'p_part_id': part_id,
            'p_disposition': disposition, 'p_reason': reason or None,
            'p_approved_by_employee_id': approver_id,
        }) or {}


    def report_payload(self, rmtc_id: str) -> dict:
        """Return a fully resolved RMTC record bundle for controlled PDF printing."""
        record = self.get(rmtc_id) or {}
        if not record:
            raise ValueError('RMTC record not found.')
        details = self.details(rmtc_id)
        part_ids = [str(row.get('part_id')) for row in details['parts'] if row.get('part_id')]
        part_master = self.repo.select('parts', in_={'id': part_ids}, limit=max(len(part_ids), 1) + 10) if part_ids else []
        parts = {str(row.get('id')): row for row in part_master}
        grade_ids = [str(row.get('material_grade_id')) for row in part_master if row.get('material_grade_id')]
        grade_rows = self.repo.select('material_grades', in_={'id': grade_ids}, limit=max(len(grade_ids), 1) + 10) if grade_ids else []
        grades = {str(row.get('id')): row for row in grade_rows}
        party_ids = [str(value) for value in (record.get('supplier_id'), record.get('steel_mill_id')) if value]
        party_rows = self.repo.select('parties', in_={'id': party_ids}, limit=20) if party_ids else []
        parties = {str(row.get('id')): row for row in party_rows}
        employee_ids = [str(value) for value in (
            record.get('prepared_by_employee_id'), record.get('validated_by_employee_id'),
            record.get('approved_by_employee_id'), record.get('decision_by_employee_id'),
        ) if value]
        employee_rows = self.repo.select('employees', in_={'id': employee_ids}, limit=20) if employee_ids else []
        employees = {str(row.get('id')): row for row in employee_rows}
        heat_summary = self.heat_summary(str(record.get('heat_number') or ''))
        heat_usage = self.heat_usage(str(record.get('heat_number') or ''))
        microstructure_images = []
        try:
            attachment_service = AttachmentService(self.repo)
            attachments = attachment_service.list_active('RMTC', rmtc_id)
            by_type = {str(row.get('document_type') or ''): row for row in attachments}
            for slot in range(1, 4):
                attachment = by_type.get(f'RMTC_MICROSTRUCTURE_{slot}')
                image_bytes = b''
                if attachment:
                    try:
                        image_bytes = attachment_service.download(attachment)
                    except Exception:
                        image_bytes = b''
                microstructure_images.append({
                    'slot': slot,
                    'caption': record.get(f'microstructure_caption_{slot}') or f'Microstructure Photo {slot}',
                    'bytes': image_bytes,
                    'file_name': (attachment or {}).get('file_name'),
                })
        except Exception:
            microstructure_images = [
                {'slot': slot, 'caption': record.get(f'microstructure_caption_{slot}') or f'Microstructure Photo {slot}', 'bytes': b'', 'file_name': None}
                for slot in range(1, 4)
            ]
        return {
            'record': record,
            'part_approvals': details['parts'],
            'parts': parts,
            'material_grades': grades,
            'chemistry': details['chemistry'],
            'jominy': details['jominy'],
            'requirements': details['requirements'],
            'supplier': parties.get(str(record.get('supplier_id'))) or {},
            'steel_mill': parties.get(str(record.get('steel_mill_id'))) or {},
            'employees': employees,
            'heat_summary': heat_summary,
            'heat_usage': heat_usage,
            'microstructure_images': microstructure_images,
        }

    def decision_revisions(self, rmtc_id):
        return self.repo.select('rmtc_decision_revisions', eq={'rmtc_approval_id': rmtc_id}, order_by='reopened_at', desc=True, limit=100)

    def next_heat_code(self,steel_mill_id:str)->str:
        return str(self.repo.rpc('qsms_next_heat_code',{'p_steel_mill_id':steel_mill_id}) or '')

    def upload_copy(self,rmtc_id:str,file:Any)->str:
        client=get_session_client()
        if client is None: raise RuntimeError('Live Supabase session is required for RMTC attachment upload.')
        ext=Path(file.name).suffix.lower() or '.bin'; content=file.getvalue()
        path=f"{self.repo.tenant_id}/rmtc/{rmtc_id}/rmtc_copy_{hashlib.sha1(file.name.encode()).hexdigest()[:8]}{ext}"
        client.storage.from_('quality-documents').upload(path,content,{'content-type':file.type or 'application/octet-stream','upsert':'true'})
        existing=self.repo.find_one('document_attachments',eq={'entity_type':'RMTC','entity_id':rmtc_id,'document_type':'RMTC_COPY'})
        payload={'entity_type':'RMTC','entity_id':rmtc_id,'document_type':'RMTC_COPY','file_name':file.name,'object_path':path,'mime_type':file.type,'size_bytes':len(content),'checksum':hashlib.sha256(content).hexdigest(),'status':'ACTIVE'}
        if existing:self.repo.update('document_attachments',str(existing['id']),payload)
        else:self.repo.insert('document_attachments',payload)
        self.repo.update('rmtc_approvals',rmtc_id,{'rmtc_copy_path':path})
        return path

    @staticmethod
    def _range(text:str)->tuple[float|None,float|None]:
        nums=[float(x) for x in re.findall(r'-?\d+(?:\.\d+)?',str(text or ''))]
        if len(nums)>=2:return min(nums[0],nums[1]),max(nums[0],nums[1])
        if len(nums)==1:return nums[0],nums[0]
        return None,None

    def production_summary(self, rmtc_id: str) -> dict:
        rows = self.repo.select('v_qsms_heat_production_summary', eq={'rmtc_approval_id': rmtc_id}, limit=1)
        return rows[0] if rows else {}

    def save_part_worksheet(self,rmtc_id:str,part_id:str,chem_rows:list[dict],jominy_rows:list[dict],requirement_rows:list[dict],grain_size:int|None,actual_di:float|None,di_applicable:bool=True,planned_production_quantity_pcs:float=0,input_weight_kg:float|None=None):
        chemistry_map={str(row.get('element') or '').strip():row.get('actual_value') for row in chem_rows if row.get('result')!='NOT_APPLICABLE'}
        curve=calculate_jominy_curve(chemistry_map)
        di=calculate_di(chemistry_map,int(grain_size)) if grain_size else {'value':None,'factors':{},'error':'Grain size not entered.'}

        chemistry_payload=[]
        for row in chem_rows:
            chemistry_payload.append({'rmtc_approval_id':rmtc_id,'part_id':part_id,'material_grade_element_id':row.get('material_grade_element_id'),'element':row.get('element'),'minimum_value':row.get('minimum_value'),'maximum_value':row.get('maximum_value'),'actual_value':row.get('actual_value'),'unit':row.get('unit') or '%','result':row.get('result') or 'NOT_EVALUATED','remarks':row.get('remarks')})
        self.repo.bulk_upsert('rmtc_chemistry_results',chemistry_payload,on_conflict='tenant_id,rmtc_approval_id,part_id,material_grade_element_id')

        jominy_payload=[]
        for row in jominy_rows:
            distance=int(row.get('distance_16th') or 0); calculated=curve.get(distance) if row.get('applicability')!='NOT_APPLICABLE' else None
            actual_result=band_status(row.get('actual_hrc'),row.get('minimum_hrc'),row.get('maximum_hrc'),row.get('applicability')!='NOT_APPLICABLE')
            calculated_result=band_status(calculated,row.get('minimum_hrc'),row.get('maximum_hrc'),row.get('applicability')!='NOT_APPLICABLE')
            jominy_payload.append({'rmtc_approval_id':rmtc_id,'part_id':part_id,'jominy_distance_id':row.get('jominy_distance_id'),'distance_label':row.get('distance_label'),'distance_mm':round(float(distance)*25.4/16,2) if distance else 0,'actual_hrc':row.get('actual_hrc'),'result':actual_result,'calculated_hrc':calculated,'calculated_result':calculated_result,'applicability':row.get('applicability') or 'APPLICABLE','remarks':row.get('remarks')})
        self.repo.bulk_upsert('rmtc_jominy_results',jominy_payload,on_conflict='tenant_id,rmtc_approval_id,part_id,jominy_distance_id')

        existing_requirements={str(r.get('source_requirement_id')):r for r in self.repo.select('rmtc_requirement_results',eq={'rmtc_approval_id':rmtc_id,'part_id':part_id},limit=500)}
        requirement_payload=[]
        for row in requirement_rows:
            source_id=str(row.get('source_requirement_id') or '')
            existing=existing_requirements.get(source_id) or {}
            payload={'id':existing.get('id') or None,'rmtc_approval_id':rmtc_id,'part_id':part_id,'requirement_source':'PART_HEAT_TREATMENT','source_requirement_id':row.get('source_requirement_id'),'requirement_code':row.get('requirement_name'),'requirement_name':row.get('requirement_name'),'requirement_value':row.get('requirement_value'),'actual_value':row.get('actual_value'),'unit':row.get('unit'),'result':row.get('result') or 'NOT_EVALUATED','sequence_no':row.get('sequence_no') or 10,'remarks':row.get('remarks')}
            if not payload['id']: payload.pop('id')
            requirement_payload.append(payload)
        self.repo.bulk_upsert('rmtc_requirement_results',requirement_payload,on_conflict='id')

        di_requirement=next((row for row in requirement_rows if 'DI' in str(row.get('requirement_name') or '').upper()),None)
        low,high=self._range(str((di_requirement or {}).get('requirement_value') or ''))
        calculated_di=di.get('value') if di_applicable else None
        actual_status=band_status(actual_di,low,high,di_applicable)
        calculated_status=band_status(calculated_di,low,high,di_applicable)
        part_row=self.repo.find_one('rmtc_part_approvals',eq={'rmtc_approval_id':rmtc_id,'part_id':part_id})
        planned_pcs=float(planned_production_quantity_pcs or 0)
        if planned_pcs<=0:
            raise ValueError('Part Production Quantity is mandatory and must be greater than zero.')
        weight=float(input_weight_kg or (part_row or {}).get('input_weight_kg') or 0)
        planned_steel=round(planned_pcs*weight,3)
        updates={'grain_size':grain_size,'actual_di':actual_di,'calculated_di':calculated_di,'actual_di_status':actual_status,'calculated_di_status':calculated_status,'planned_production_quantity_pcs':planned_pcs,'input_weight_kg':weight or None,'planned_steel_quantity_kg':planned_steel,'worksheet_completed_at':datetime.now(timezone.utc).isoformat(),'worksheet_completed_by':str((st.session_state.get('profile') or {}).get('id') or '') or None}
        if part_row:self.repo.update('rmtc_part_approvals',str(part_row['id']),updates)
        self.repo.rpc('qsms_evaluate_rmtc',{'p_rmtc_id':rmtc_id})
        return {'jominy_curve':curve,'di':di,'actual_di_status':actual_status,'calculated_di_status':calculated_status,'planned_production_quantity_pcs':planned_pcs,'planned_steel_quantity_kg':planned_steel}
