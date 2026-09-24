"""Current Section E authority for linked raw forging/casting parts."""
from datetime import date

INHERITED_FIELDS = (
    'supplier_id', 'material_grade_id',
    'supplier_rm_item_code', 'supplier_forging_part_number', 'hsn_sac_code',
    'lead_time_days', 'forging_weight_kg', 'gross_weight_kg', 'input_weight_kg',
    'section_size', 'forging_route',
)


def live_rows(repo, table, **kwargs):
    try:
        return repo.select(table, require_live=True, **kwargs)
    except RuntimeError as exc:
        raise ValueError("Cannot verify current linked raw-part data. Restore the database connection and retry.") from exc


def current_approvals(repo, part_id, supplier_id=None, today=None):
    today = (today or date.today()).isoformat()
    rows = live_rows(repo, 'part_supplier_links', eq={'part_id': part_id, 'approved': True}, limit=5000)
    return [r for r in rows if r.get('approved') is True
            and (not supplier_id or str(r.get('supplier_id')) == str(supplier_id))
            and (not r.get('valid_from') or str(r['valid_from'])[:10] <= today)
            and (not r.get('valid_to') or str(r['valid_to'])[:10] >= today)]


def resolve_raw_source(repo, part, raw, supplier_id=None):
    """Read current masters; fail closed rather than reuse finished-part copies.

    Multiple active rows for the selected source/supplier are ranked as revisions; updated_at, then
    created_at, then id provide deterministic latest-first selection.
    Linked chains are rejected: each purchase source must own its Section E.
    """
    source_id = str(raw.get('source_part_id') or '').strip()
    if not source_id:
        return dict(part), dict(raw)
    source_rows = live_rows(repo, 'parts', eq={'id': source_id}, limit=1)
    source = source_rows[0] if source_rows else {}
    label = source.get('part_number') or source_id
    if not source or source.get('status') != 'ACTIVE':
        raise ValueError(f'Linked raw part {label} must be ACTIVE.')
    if source_id == str(part.get('id')):
        raise ValueError('A raw source cannot link to itself.')
    kind = str(raw.get('material_section_name') or '').strip().casefold()
    if kind not in {'forging', 'casting'}:
        raise ValueError('Linked raw sources require Forging or Casting material type.')
    sid = supplier_id or raw.get('supplier_id')
    rows = live_rows(repo, 'part_raw_material_details', eq={'part_id': source_id, 'status': 'ACTIVE'}, limit=5000)
    rows = [r for r in rows if r.get('status') == 'ACTIVE'
            and (not sid or str(r.get('supplier_id')) == str(sid))]
    if not rows:
        raise ValueError(f'Linked raw part {label}: add an ACTIVE Section E row for the selected supplier.')
    rows.sort(key=lambda r: (str(r.get('updated_at') or r.get('created_at') or ''), str(r.get('created_at') or ''), str(r.get('id') or '')), reverse=True)
    selected = dict(rows[0])
    if selected.get('source_part_id'):
        raise ValueError(f'Linked raw part {label} must own its Section E details; nested raw-part links are not supported.')
    approvals = current_approvals(repo, source_id, selected.get('supplier_id'))
    if not approvals:
        raise ValueError(f'Linked raw part {label}: supplier approval is missing, expired or not yet valid in Section E.')
    selected['_supplier_approvals'] = approvals
    return dict(source), selected


def effective_link(repo, part, raw):
    """Inherit values but retain finished-part link ID for order genealogy."""
    source, resolved = resolve_raw_source(repo, part, raw)
    if not raw.get('source_part_id'):
        return dict(raw)
    return {**raw, **{k: resolved.get(k) for k in INHERITED_FIELDS},
            '_source_raw_id': resolved['id'], '_source_part_number': source.get('part_number'),
            '_supplier_approvals': resolved.get('_supplier_approvals', [])}
