"""QCMS R38 · Engineering Change Note (ECN) / Process Change Note (PCN) service.

Format FSI/806/F05 rev 00 (sheets "ECN Form" and "PCN" of the customer workbook). An ECN is raised whenever a
controlled drawing / specification revision REPLACES a current revision (Part finish / forging / heat-treatment
drawing, or a process drawing / specification of a Part process). The ECN is created first (DRAFT or PENDING_APPROVAL),
the new revision is released, then the ECN is linked to the released revision - so no replacement revision can be
saved without its ECN (``release_with_ecn``). A Part process list change can raise a PCN the same way.

Status flow: DRAFT -> PENDING_APPROVAL -> APPROVED | DISAPPROVED -> COMPLETED (an APPROVED note is completed once the
change is implemented; DRAFT / DISAPPROVED can be CANCELLED). Approve / disapprove needs Part Master approve permission
(also enforced by the database trigger qcms_guard_part_ecn).

Public contract:
* ``ECNService(repo)``: ``list``, ``get``, ``create``, ``save``, ``transition``, ``link_revision``, ``cancel``,
  ``employees``, ``register_frame``
* ``next_ecn_number(repo, change_type, plant_code, on)`` -> ``ECN-<PLANT>-YYYY-####`` (``PCN-...`` for a PCN)
* ``release_with_ecn(service, payload, release, ...)``  create ECN -> release revision -> link (cancel ECN on failure)
* ``revision_defaults(...)``  ECN form defaults for a drawing replacement
* ``ecn_notifier(repo)``  NotificationService that attaches the ECN print (core.ecn_pdf)
* ``notify_ecn_created(repo, ecn)``  event ECN_CREATED -> e-mail (ECN print attached) to Quality + NPD employees
* ``ECNService.actions / open_actions / save_actions`` + ``normalize_action_rows`` / ``default_actions``: implementation
  actions (``part_ecn_actions``: affected document, action, responsible, target date, OPEN / IN_PROGRESS / DONE /
  NOT_REQUIRED). COMPLETED is refused while an action is open (app + trigger qcms_guard_part_ecn_completion).
Status mapping to the generic names: IMPLEMENTED / CLOSED = COMPLETED; REJECTED = DISAPPROVED.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Iterable, Mapping, Sequence

FORMAT_NO = "FSI/806/F05"
FORMAT_REV_DATE = "25.09.2024"
FORMAT_REV_NO = "00"

CHANGE_TYPES: dict[str, str] = {"ECN": "ENGINEERING CHANGE NOTE", "PCN": "PROCESS CHANGE NOTE"}
ECN_STATUSES: tuple[str, ...] = ("DRAFT", "PENDING_APPROVAL", "APPROVED", "DISAPPROVED", "COMPLETED", "CANCELLED")
# R38 first cut used other names - read them as the current ones
LEGACY_STATUSES: dict[str, str] = {"SUBMITTED": "PENDING_APPROVAL", "REJECTED": "DISAPPROVED", "IMPLEMENTED": "COMPLETED"}
STATUS_LABELS: dict[str, str] = {"DRAFT": "Draft", "PENDING_APPROVAL": "Pending Approval", "APPROVED": "Approved",
                                 "DISAPPROVED": "Disapproved", "COMPLETED": "Completed", "CANCELLED": "Cancelled"}
ATTACHMENT_ENTITY = "PART_ECN"
DEPARTMENT = "Engineering"
PRIORITIES: tuple[str, ...] = ("Normal", "High", "Urgent", "Low")
SUPPORTING_DOCUMENTS: tuple[tuple[str, str], ...] = (
    ("redline_drawing", "Redline Drawing"),
    ("datasheet", "Datasheet"),
    ("purchase_order", "Purchase Orders"),
    ("ppap", "PPAP"),
    ("pfd", "PFD"),
    ("control_plan", "CP"),
    ("pfmea", "PFMEA"),
    ("maintain_inventory", "Maintain Inventory"),
)
DRAWING_CHANGE_MODES: dict[str, str] = {
    "AS_SUGGESTED": "As suggested",
    "NOT_AS_SUGGESTED": "Not as suggested",
    "OTHER": "Other (See Comments)",
}
CUSTOMER_APPROVALS: tuple[str, ...] = ("PENDING", "APPROVED", "DISAPPROVED", "NOT_REQUIRED")
FSI_DECISIONS: tuple[str, ...] = ("APPROVED", "DISAPPROVED")
CONTACT_FIELDS: tuple[tuple[str, str], ...] = (("name", "Contact Name"), ("address", "Address"), ("phone", "Phone"), ("fax", "Fax"))

# Document scopes an ECN can belong to (Part drawings use the existing controlled-drawing document types).
DOCUMENT_SCOPES: dict[str, str] = {
    "FINISH_DRAWING": "Finish Drawing",
    "FORGING_DRAWING": "Forging Drawing",
    "HEAT_TREATMENT_DRAWING": "Heat Treatment Drawing",
    "PROCESS_DRAWING": "Process Drawing",
    "PROCESS_SPEC": "Process Specification",
    "PROCESS_FLOW": "Process Flow / Process List",
    "GENERAL": "General change",
}

# status -> {target: permission needed}
TRANSITIONS: dict[str, dict[str, str]] = {
    "DRAFT": {"PENDING_APPROVAL": "edit", "CANCELLED": "edit"},
    "PENDING_APPROVAL": {"APPROVED": "approve", "DISAPPROVED": "approve", "DRAFT": "edit"},
    "DISAPPROVED": {"DRAFT": "edit", "CANCELLED": "edit"},
    "APPROVED": {"COMPLETED": "edit"},
    "COMPLETED": {},
    "CANCELLED": {},
}
EDITABLE_STATUSES = {"DRAFT", "DISAPPROVED"}
# R38 step 3: implementation actions (part_ecn_actions) - every action DONE / NOT_REQUIRED before COMPLETED
ACTION_TABLE = "part_ecn_actions"
ACTION_STATUSES: tuple[str, ...] = ("OPEN", "IN_PROGRESS", "DONE", "NOT_REQUIRED")
OPEN_ACTION_STATUSES = {"OPEN", "IN_PROGRESS"}
# supporting-document flag -> default implementation action (affected document, action text)
DEFAULT_ACTIONS: tuple[tuple[str, str, str], ...] = (
    ("redline_drawing", "Drawing", "Release the revised drawing and withdraw the superseded copies from the shop floor"),
    ("pfd", "PFD", "Update the Process Flow Diagram"),
    ("control_plan", "Control Plan", "Update the Control Plan"),
    ("pfmea", "PFMEA", "Review / update the PFMEA"),
    ("ppap", "PPAP", "Prepare PPAP resubmission / customer approval"),
    ("purchase_order", "Purchase Orders", "Amend affected Purchase Orders"),
    ("maintain_inventory", "Inventory", "Disposition of existing stock (raw material / WIP / FG / at supplier)"),
)
NOTIFY_DEPARTMENTS: tuple[str, ...] = ("Quality", "NPD")
TRANSITION_LABELS: dict[str, str] = {"PENDING_APPROVAL": "Submit for Approval", "APPROVED": "Approve", "DISAPPROVED": "Disapprove",
                                     "COMPLETED": "Mark Completed", "DRAFT": "Return to Draft", "CANCELLED": "Cancel"}


def clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        import math
        if isinstance(value, float) and math.isnan(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = clean(value)
    return text[:10] or None


def _num(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_status(value: Any) -> str:
    status = clean(value).upper().replace(" ", "_") or "DRAFT"
    return LEGACY_STATUSES.get(status, status)


def status_label(value: Any) -> str:
    status = normalize_status(value)
    return STATUS_LABELS.get(status, status.title())


def change_title(change_type: Any) -> str:
    return CHANGE_TYPES.get(clean(change_type).upper(), CHANGE_TYPES["ECN"])


def plant_token(plant_code: Any) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "", clean(plant_code)).upper()
    return token or "FSI"


def ecn_prefix(change_type: Any, plant_code: Any, on: date | None = None) -> str:
    kind = "PCN" if clean(change_type).upper() == "PCN" else "ECN"
    return f"{kind}-{plant_token(plant_code)}-{(on or date.today()).year}-"


def format_ecn_number(change_type: Any, plant_code: Any, sequence: int, on: date | None = None) -> str:
    return f"{ecn_prefix(change_type, plant_code, on)}{int(sequence):04d}"


def next_from_existing(numbers: Iterable[Any], change_type: Any, plant_code: Any, on: date | None = None) -> str:
    prefix = ecn_prefix(change_type, plant_code, on)
    last = 0
    for value in numbers:
        text = clean(value)
        if text.startswith(prefix):
            digits = re.sub(r"[^0-9]", "", text[len(prefix):])
            if digits:
                last = max(last, int(digits))
    return f"{prefix}{last + 1:04d}"


def next_ecn_number(repo: Any, change_type: Any = "ECN", plant_code: Any = None, on: date | None = None) -> str:
    """Server series (qcms_next_ecn_number) - falls back to the register when the RPC is unavailable (preview)."""
    on = on or date.today()
    try:
        value = clean(repo.rpc("qcms_next_ecn_number", {"p_change_type": clean(change_type).upper() or "ECN",
                                                         "p_plant_code": plant_token(plant_code), "p_date": on.isoformat()}))
        if value:
            return value
    except Exception:
        pass
    rows = repo.select("part_ecns", limit=5000) or []
    return next_from_existing((r.get("ecn_number") for r in rows), change_type, plant_code, on)


def clean_contact(value: Any) -> dict[str, str]:
    data = value if isinstance(value, Mapping) else {}
    return {key: clean(data.get(key)) for key, _ in CONTACT_FIELDS}


def contact_text(value: Any) -> str:
    data = clean_contact(value)
    return " · ".join(v for v in (data["name"], data["address"], data["phone"] and f"Ph {data['phone']}", data["fax"] and f"Fax {data['fax']}") if v)


def clean_supporting(value: Any) -> dict[str, bool]:
    data = value if isinstance(value, Mapping) else {}
    return {key: bool(data.get(key)) for key, _ in SUPPORTING_DOCUMENTS}


def employee_name(row: Mapping[str, Any] | None) -> str:
    row = row or {}
    return " ".join(v for v in (clean(row.get("first_name")), clean(row.get("last_name"))) if v) or clean(row.get("employee_code"))


def normalize_ecn_payload(form: Mapping[str, Any]) -> dict[str, Any]:
    """Clean an ECN form (screen or import) into a ``part_ecns`` payload (only known columns)."""
    f = dict(form or {})
    change_type = "PCN" if clean(f.get("change_type")).upper() == "PCN" else "ECN"
    reps = [clean(v) for v in (f.get("fsi_representative_ids") or []) if clean(v)]
    mails = [clean(v) for v in (f.get("email_employee_ids") or []) if clean(v)]
    payload: dict[str, Any] = {
        "change_type": change_type,
        "ecn_date": _iso(f.get("ecn_date")) or date.today().isoformat(),
        "plant_code": clean(f.get("plant_code")) or None,
        "part_id": clean(f.get("part_id")) or None,
        "process_route_id": clean(f.get("process_route_id")) or None,
        "document_scope": clean(f.get("document_scope")).upper() or None,
        "previous_revision": clean(f.get("previous_revision")) or None,
        "new_revision": clean(f.get("new_revision")) or None,
        "fsi_representative_ids": list(dict.fromkeys(reps)),
        "fsi_representatives_text": clean(f.get("fsi_representatives_text")) or None,
        "to_contact": clean_contact(f.get("to_contact")),
        "cc_contact": clean_contact(f.get("cc_contact")),
        "from_contact": clean_contact(f.get("from_contact")),
        "requested_priority": clean(f.get("requested_priority")) or None,
        "response_by": _iso(f.get("response_by")),
        "response_by_party": clean(f.get("response_by_party")) or None,
        "drawing_number": clean(f.get("drawing_number")) or None,
        "part_number": clean(f.get("part_number")) or None,
        "part_name": clean(f.get("part_name")) or None,
        "previous_description": clean(f.get("previous_description")) or None,
        "revision_requested": clean(f.get("revision_requested")) or None,
        "supporting_documents": clean_supporting(f.get("supporting_documents")),
        "po_affected": bool(f.get("po_affected")),
        "inventory_affected": bool(f.get("inventory_affected")),
        "inventory_qty": _num(f.get("inventory_qty")) if f.get("inventory_affected") else None,
        "demands_affected": bool(f.get("demands_affected")),
        "demands_qty": _num(f.get("demands_qty")) if f.get("demands_affected") else None,
        "fsi_decision": clean(f.get("fsi_decision")).upper() or None,
        "drawing_change_mode": clean(f.get("drawing_change_mode")).upper() or None,
        "customer_approval": clean(f.get("customer_approval")).upper() or None,
        "customer_name_text": clean(f.get("customer_name_text")) or None,
        "fsi_approver_employee_id": clean(f.get("fsi_approver_employee_id")) or None,
        "fsi_approval_date": _iso(f.get("fsi_approval_date")),
        "customer_approver_name": clean(f.get("customer_approver_name")) or None,
        "customer_approval_date": _iso(f.get("customer_approval_date")),
        "completed_by_employee_id": clean(f.get("completed_by_employee_id")) or None,
        "completed_date": _iso(f.get("completed_date")),
        "comments": clean(f.get("comments")) or None,
        "benefit_of_change": clean(f.get("benefit_of_change")) or None,
        "email_employee_ids": list(dict.fromkeys(mails)),
    }
    if payload["fsi_decision"] not in (None, *FSI_DECISIONS):
        payload["fsi_decision"] = None
    if payload["drawing_change_mode"] not in (None, *DRAWING_CHANGE_MODES):
        payload["drawing_change_mode"] = None
    if payload["customer_approval"] not in (None, *CUSTOMER_APPROVALS):
        payload["customer_approval"] = None
    for key in ("document_attachment_id", "previous_attachment_id"):
        if clean(f.get(key)):
            payload[key] = clean(f.get(key))
    return payload


def validate_ecn(payload: Mapping[str, Any], *, submitting: bool = False) -> list[str]:
    """Errors for a DRAFT save (minimum) or a submission (complete identification + change description)."""
    p = dict(payload or {})
    errors: list[str] = []
    if not clean(p.get("part_number")) and not clean(p.get("part_id")):
        errors.append("Part No. is required.")
    if not clean(p.get("revision_requested")):
        errors.append("Revision Requested (new description) is required.")
    if p.get("inventory_affected") and p.get("inventory_qty") is not None and float(p.get("inventory_qty") or 0) < 0:
        errors.append("Current Inventory quantity cannot be negative.")
    if p.get("demands_affected") and p.get("demands_qty") is not None and float(p.get("demands_qty") or 0) < 0:
        errors.append("Current Demands quantity cannot be negative.")
    if submitting:
        if not (p.get("fsi_representative_ids") or clean(p.get("fsi_representatives_text"))):
            errors.append("Select at least one FSI Representative.")
        if not clean(p.get("drawing_number")):
            errors.append("Drawing No. is required.")
        if not clean(p.get("part_name")):
            errors.append("Part Name is required.")
        if not clean(p.get("previous_description")):
            errors.append("Previous Description is required.")
    return errors


def can_transition(current: Any, target: Any, perms: Mapping[str, Any] | None) -> bool:
    current_s, target_s = normalize_status(current), normalize_status(target)
    need = TRANSITIONS.get(current_s, {}).get(target_s)
    if not need:
        return False
    p = dict(perms or {})
    if need == "approve":
        return bool(p.get("can_approve"))
    return bool(p.get("can_edit") or p.get("can_create"))


def allowed_targets(current: Any, perms: Mapping[str, Any] | None) -> list[str]:
    return [t for t in TRANSITIONS.get(normalize_status(current), {}) if can_transition(current, t, perms)]


def revision_defaults(part: Mapping[str, Any] | None, *, document_scope: str, drawing_number: Any, current: Mapping[str, Any] | None,
                      new_revision: Any, new_revision_date: Any = None, process_text: str = "",
                      new_title: str = "") -> dict[str, Any]:
    """ECN form defaults for a drawing / document replacement."""
    part = part or {}
    current = current or {}
    scope = clean(document_scope).upper() or "GENERAL"
    label = DOCUMENT_SCOPES.get(scope, scope.title())
    is_process = scope in {"PROCESS_DRAWING", "PROCESS_SPEC"}
    where = f" · {process_text}" if process_text else ""
    previous = (
        f"{label}{where} {clean(current.get('drawing_number')) or clean(drawing_number)} Rev {clean(current.get('revision')) or '-'}"
        f" dated {clean(current.get('revision_date')) or '-'}"
        + (f" ({clean(current.get('document_title'))})" if clean(current.get("document_title")) else "")
    )
    requested = (
        f"Release {label}{where} {clean(drawing_number)} Rev {clean(new_revision)}"
        + (f" dated {_iso(new_revision_date)}" if _iso(new_revision_date) else "")
        + (f" ({clean(new_title)})" if clean(new_title) else "")
        + ". Describe the change: "
    )
    return {
        "change_type": "PCN" if is_process else "ECN",
        "document_scope": scope,
        "part_id": clean(part.get("id")) or None,
        "part_number": clean(part.get("part_number")),
        "part_name": clean(part.get("part_name")),
        "drawing_number": clean(drawing_number),
        "previous_revision": clean(current.get("revision")),
        "new_revision": clean(new_revision),
        "previous_attachment_id": clean(current.get("id")) or None,
        "previous_description": previous,
        "revision_requested": requested,
        "supporting_documents": {"redline_drawing": True},
        "drawing_change_mode": "AS_SUGGESTED",
        "customer_approval": "PENDING",
    }


class ECNService:
    TABLE = "part_ecns"

    def __init__(self, repo: Any | None = None) -> None:
        if repo is None:
            from core.repository import Repository
            repo = Repository()
        self.repo = repo

    # ---------------------------------------------------------------- reads
    def list(self, *, part_id: Any = None, status: Any = None, limit: int = 3000) -> list[dict]:
        eq: dict[str, Any] = {}
        if clean(part_id):
            eq["part_id"] = clean(part_id)
        if clean(status):
            eq["status"] = clean(status).upper()
        rows = self.repo.select(self.TABLE, eq=eq or None, order_by="ecn_date", desc=True, limit=limit) or []
        return [dict(r) for r in rows]

    def get(self, ecn_id: Any) -> dict:
        return dict(self.repo.get(self.TABLE, clean(ecn_id)) or {}) if clean(ecn_id) else {}

    def employees(self) -> list[dict]:
        try:
            return [dict(r) for r in (self.repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=3000) or [])]
        except Exception:
            return []

    def employee_names(self) -> dict[str, str]:
        return {clean(r.get("id")): employee_name(r) for r in self.employees()}

    def current_plant_code(self) -> str:
        try:
            from core.branch_context import resolve_current_branch
            branch = resolve_current_branch(self.repo) or {}
            return plant_token(branch.get("plant_code") or branch.get("branch_code"))
        except Exception:
            return "FSI"

    # ---------------------------------------------------------------- writes
    def create(self, form: Mapping[str, Any], *, status: str = "DRAFT", plant_code: Any = None) -> dict:
        target = normalize_status(status)
        if target not in {"DRAFT", "PENDING_APPROVAL"}:
            raise ValueError("A new ECN is saved as DRAFT or PENDING_APPROVAL.")
        payload = normalize_ecn_payload(form)
        errors = validate_ecn(payload, submitting=target == "PENDING_APPROVAL")
        if errors:
            raise ValueError(" ".join(errors))
        plant = plant_token(plant_code or payload.get("plant_code") or self.current_plant_code())
        on = date.fromisoformat(payload["ecn_date"]) if payload.get("ecn_date") else date.today()
        payload["plant_code"] = plant
        payload["ecn_number"] = next_ecn_number(self.repo, payload["change_type"], plant, on)
        payload["status"] = target
        return dict(self.repo.insert(self.TABLE, payload))

    def save(self, ecn_id: Any, form: Mapping[str, Any]) -> dict:
        current = self.get(ecn_id)
        if not current:
            raise ValueError("ECN was not found.")
        status = normalize_status(current.get("status"))
        payload = normalize_ecn_payload({**current, **dict(form or {})})
        if status not in EDITABLE_STATUSES:
            # Only the FSI-use / completion block and comments stay editable after submission.
            allowed = {"fsi_decision", "drawing_change_mode", "customer_approval", "customer_name_text", "fsi_approver_employee_id",
                       "fsi_approval_date", "customer_approver_name", "customer_approval_date", "completed_by_employee_id",
                       "completed_date", "comments", "benefit_of_change", "email_employee_ids"}
            payload = {k: v for k, v in payload.items() if k in allowed}
        else:
            errors = validate_ecn(payload)
            if errors:
                raise ValueError(" ".join(errors))
            if clean(current.get("ecn_number")):
                payload.pop("change_type", None)  # the number series already carries the type
        return dict(self.repo.update(self.TABLE, clean(ecn_id), payload))

    def transition(self, ecn_id: Any, target: str, perms: Mapping[str, Any] | None, *, remarks: str = "",
                   approver_employee_id: Any = None) -> dict:
        current = self.get(ecn_id)
        if not current:
            raise ValueError("ECN was not found.")
        status = normalize_status(current.get("status"))
        target_s = normalize_status(target)
        if not can_transition(status, target_s, perms):
            raise PermissionError(f"ECN {current.get('ecn_number')}: {status} -> {target_s} is not allowed for your permission.")
        if target_s == "PENDING_APPROVAL":
            errors = validate_ecn(current, submitting=True)
            if errors:
                raise ValueError(" ".join(errors))
        changes: dict[str, Any] = {"status": target_s}
        if target_s in {"APPROVED", "DISAPPROVED"}:
            changes["fsi_decision"] = target_s
            if not current.get("fsi_approval_date"):
                changes["fsi_approval_date"] = date.today().isoformat()
            if approver_employee_id and not current.get("fsi_approver_employee_id"):
                changes["fsi_approver_employee_id"] = clean(approver_employee_id)
        if target_s == "COMPLETED":
            pending = self.open_actions(ecn_id)
            if pending:
                raise ValueError(f"ECN {current.get('ecn_number')}: close every implementation action (DONE / NOT REQUIRED) "
                                 f"before completing - {len(pending)} action(s) still open.")
            if not current.get("completed_date"):
                changes["completed_date"] = date.today().isoformat()
            if approver_employee_id and not current.get("completed_by_employee_id"):
                changes["completed_by_employee_id"] = clean(approver_employee_id)
        if clean(remarks):
            prefix = clean(current.get("comments"))
            changes["comments"] = (prefix + "\n" if prefix else "") + f"[{target_s} {date.today().isoformat()}] {clean(remarks)}"
        return dict(self.repo.update(self.TABLE, clean(ecn_id), changes))

    def link_revision(self, ecn_id: Any, attachment_id: Any, previous_attachment_id: Any = None) -> dict:
        changes = {"document_attachment_id": clean(attachment_id) or None}
        if clean(previous_attachment_id):
            changes["previous_attachment_id"] = clean(previous_attachment_id)
        return dict(self.repo.update(self.TABLE, clean(ecn_id), changes))

    def cancel(self, ecn_id: Any, reason: str = "") -> dict:
        current = self.get(ecn_id)
        note = clean(current.get("comments"))
        text = f"[CANCELLED {date.today().isoformat()}] {clean(reason) or 'Revision release failed.'}"
        return dict(self.repo.update(self.TABLE, clean(ecn_id), {"status": "CANCELLED", "comments": (note + "\n" if note else "") + text}))

    def mark_emailed(self, ecn_id: Any) -> None:
        try:
            self.repo.update(self.TABLE, clean(ecn_id), {"emailed_at": datetime.now().astimezone().isoformat()})
        except Exception:
            pass

    # ---------------------------------------------------------------- implementation actions
    def actions(self, ecn_id: Any) -> list[dict]:
        if not clean(ecn_id):
            return []
        try:
            rows = self.repo.select(ACTION_TABLE, eq={"ecn_id": clean(ecn_id)}, order_by="sequence_no", limit=500) or []
        except Exception:
            return []
        return sorted((dict(r) for r in rows), key=lambda r: int(r.get("sequence_no") or 0))

    def open_actions(self, ecn_id: Any) -> list[dict]:
        return [r for r in self.actions(ecn_id) if clean(r.get("status")).upper() in OPEN_ACTION_STATUSES]

    def save_actions(self, ecn_id: Any, rows: Iterable[Mapping[str, Any]]) -> int:
        """Insert / update implementation actions (rows from ``normalize_action_rows``; ``id`` kept for updates)."""
        current = self.get(ecn_id)
        if not current:
            raise ValueError("ECN was not found.")
        if normalize_status(current.get("status")) in {"COMPLETED", "CANCELLED"}:
            raise ValueError("Actions of a COMPLETED / CANCELLED ECN cannot be changed.")
        existing = {clean(r.get("id")) for r in self.actions(ecn_id)}
        count = 0
        for row in rows:
            data = dict(row)
            row_id = clean(data.pop("id", None))
            data["ecn_id"] = clean(ecn_id)
            if row_id and row_id in existing:
                self.repo.update(ACTION_TABLE, row_id, data)
            else:
                self.repo.insert(ACTION_TABLE, data)
            count += 1
        return count

    # ---------------------------------------------------------------- register
    def register_frame(self, rows: Sequence[Mapping[str, Any]], parts: Mapping[str, Mapping[str, Any]] | None = None):
        import pandas as pd
        parts = parts or {}
        data = []
        for r in rows:
            part = parts.get(clean(r.get("part_id"))) or {}
            data.append({
                "ECN No.": r.get("ecn_number"),
                "Type": r.get("change_type"),
                "Date": r.get("ecn_date"),
                "Plant": r.get("plant_code"),
                "Part No.": r.get("part_number") or part.get("part_number"),
                "Part Name": r.get("part_name") or part.get("part_name"),
                "Document": DOCUMENT_SCOPES.get(clean(r.get("document_scope")).upper(), clean(r.get("document_scope"))),
                "Drawing No.": r.get("drawing_number"),
                "Rev From": r.get("previous_revision"),
                "Rev To": r.get("new_revision"),
                "Priority": r.get("requested_priority"),
                "Response By": r.get("response_by"),
                "Customer Approval": r.get("customer_approval"),
                "Status": status_label(r.get("status")),
                "Revision Linked": "Yes" if r.get("document_attachment_id") else "No",
            })
        columns = ["ECN No.", "Type", "Date", "Plant", "Part No.", "Part Name", "Document", "Drawing No.", "Rev From", "Rev To",
                   "Priority", "Response By", "Customer Approval", "Status", "Revision Linked"]
        return pd.DataFrame(data, columns=columns)


def release_with_ecn(service: ECNService, form: Mapping[str, Any], release: Callable[[], Mapping[str, Any]], *,
                     status: str = "DRAFT", plant_code: Any = None) -> tuple[dict, dict]:
    """Create the ECN, release the new revision, link them. If the release fails the ECN is CANCELLED and the
    error is raised again (no replacement revision exists without its ECN)."""
    ecn = service.create(form, status=status, plant_code=plant_code)
    try:
        released = dict(release() or {})
    except Exception as exc:
        try:
            service.cancel(ecn.get("id"), f"Revision release failed: {exc}")
        except Exception:
            pass
        raise
    new_id = clean(released.get("id"))
    previous_id = clean(form.get("previous_attachment_id")) or clean(released.get("superseded_id"))
    if new_id:
        ecn = service.link_revision(ecn.get("id"), new_id, previous_id or None) or ecn
    return ecn, released


def ecn_email_text(ecn: Mapping[str, Any]) -> tuple[str, str]:
    """Subject starts with the department: "Engineering · ECN ECN-D9-2026-0001 · Part 7568 · ... · Pending Approval"."""
    title = change_title(ecn.get("change_type")).title()
    kind = "PCN" if clean(ecn.get("change_type")).upper() == "PCN" else "ECN"
    subject = (f"{DEPARTMENT} · {kind} {clean(ecn.get('ecn_number'))} · Part {clean(ecn.get('part_number'))} · {title} · "
               f"{status_label(ecn.get('status'))}")
    body = "\n".join([
        "Dear Sir / Madam,",
        "",
        f"Please find attached {title} {clean(ecn.get('ecn_number'))} dated {clean(ecn.get('ecn_date'))}.",
        f"Part No.: {clean(ecn.get('part_number'))}  ·  Part Name: {clean(ecn.get('part_name'))}",
        f"Drawing No.: {clean(ecn.get('drawing_number'))}  ·  Revision {clean(ecn.get('previous_revision')) or '-'} -> {clean(ecn.get('new_revision')) or '-'}",
        f"Requested priority: {clean(ecn.get('requested_priority')) or '-'}  ·  Response by: {clean(ecn.get('response_by')) or '-'}",
        f"Status: {status_label(ecn.get('status'))}",
        "",
        "Revision requested:",
        clean(ecn.get("revision_requested")) or "-",
        "",
        "Regards,",
        "STAWN QCMS",
    ])
    return subject, body


def normalize_action_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict]:
    """Validate the actions grid (keys: id, affected_document, action_text, responsible_employee_id, responsible_text,
    target_date, completed_date, status, remarks) -> ``part_ecn_actions`` payloads. Blank rows are skipped."""
    out: list[dict] = []
    for index, row in enumerate(rows or [], start=1):
        text = clean(row.get("action_text"))
        other = any(clean(row.get(k)) for k in ("affected_document", "responsible_employee_id", "responsible_text", "target_date", "remarks"))
        if not text and not other:
            continue
        if not text:
            raise ValueError(f"Action row {index}: describe the action.")
        status = clean(row.get("status")).upper().replace(" ", "_") or "OPEN"
        if status not in ACTION_STATUSES:
            raise ValueError(f"Action row {index}: status must be one of {', '.join(ACTION_STATUSES)}.")
        payload = {
            "sequence_no": int(row.get("sequence_no") or index * 10),
            "affected_document": clean(row.get("affected_document")) or None,
            "action_text": text,
            "responsible_employee_id": clean(row.get("responsible_employee_id")) or None,
            "responsible_text": clean(row.get("responsible_text")) or None,
            "target_date": _iso(row.get("target_date")),
            "completed_date": _iso(row.get("completed_date")) or (date.today().isoformat() if status == "DONE" else None),
            "status": status,
            "remarks": clean(row.get("remarks")) or None,
        }
        if clean(row.get("id")):
            payload["id"] = clean(row.get("id"))
        out.append(payload)
    return out


def default_actions(ecn: Mapping[str, Any]) -> list[dict]:
    """Suggested implementation actions from the ticked supporting documents of the ECN form."""
    flags = clean_supporting((ecn or {}).get("supporting_documents"))
    rows = []
    for key, document, text in DEFAULT_ACTIONS:
        if flags.get(key):
            rows.append({"affected_document": document, "action_text": text, "status": "OPEN",
                         "target_date": clean((ecn or {}).get("response_by")) or None})
    return rows


def notification_recipients(repo: Any, departments: Sequence[str] = NOTIFY_DEPARTMENTS, extra: Sequence[str] = ()) -> list[str]:
    """Active Employee Master e-mails of the departments (Quality + NPD) followed by ``extra`` - unique, in order."""
    from core.notification_service import NotificationService
    service = NotificationService(repo)
    emails: list[str] = []
    for dept in departments:
        try:
            emails.extend(service.department_emails(dept))
        except Exception:
            pass
    emails.extend(extra or [])
    seen: set[str] = set()
    out = []
    for mail in emails:
        m = clean(mail)
        if "@" in m and m.casefold() not in seen:
            seen.add(m.casefold())
            out.append(m)
    return out


def notify_ecn_created(repo: Any, ecn: Mapping[str, Any], *, extra_emails: Sequence[str] = ()) -> tuple[int, str]:
    """Event ECN_CREATED: e-mail a new ECN / PCN (print attached) to Quality + NPD. Returns (recipients, message)."""
    emails = notification_recipients(repo, NOTIFY_DEPARTMENTS, extra_emails)
    if not emails:
        return 0, "No active Quality / NPD employee with an e-mail address in Employee Master."
    subject, body = ecn_email_text(ecn)
    subject = subject.replace(f"{DEPARTMENT} · ", f"{DEPARTMENT} · New ", 1)
    notifier = ecn_notifier(repo)
    row = notifier.enqueue("ECN_CREATED", subject=subject, body_text=body, related_table=ECNService.TABLE,
                           related_id=clean(ecn.get("id")), recipient_email=emails[0], cc_emails=emails[1:],
                           context={"department": DEPARTMENT}, include_supplier=False, include_generated_pdf=True,
                           include_record_attachments=False, dedupe_key=f"ECN_CREATED:{clean(ecn.get('id'))}", automatic=True)
    if not row:
        return 0, "ECN_CREATED notification is disabled or could not be queued."
    result = notifier.dispatch([row]) or {}
    if result.get("error"):
        return len(emails), f"Queued; delivery returned: {result.get('error')}."
    return len(emails), ""


def default_representative(employees: Sequence[Mapping[str, Any]], profile: Mapping[str, Any] | None) -> list[str]:
    """FSI Representative default = the signed-in user's Employee Master row (matched by profile id / employee id / e-mail)."""
    profile = profile or {}
    keys = {clean(profile.get("id")), clean(profile.get("profile_id"))} - {""}
    emp_id = clean(profile.get("employee_id"))
    mail = clean(profile.get("email")).casefold()
    for row in employees:
        if (emp_id and clean(row.get("id")) == emp_id) or (keys and clean(row.get("profile_id")) in keys) \
                or (mail and clean(row.get("email")).casefold() == mail):
            return [clean(row.get("id"))]
    return []


def ecn_notifier(repo: Any | None = None):
    """NotificationService that attaches the controlled ECN / PCN print as the generated PDF."""
    from core.notification_service import NotificationService

    class ECNNotificationService(NotificationService):
        def _generated_report(self, related_table: str, related_id: str):  # type: ignore[override]
            if related_table == ECNService.TABLE:
                try:
                    from core.ecn_pdf import ecn_pdf_bytes
                    ecn = ECNService(self.repo).get(related_id)
                    if not ecn:
                        return None
                    return f"{clean(ecn.get('ecn_number')) or 'ECN'}.pdf", ecn_pdf_bytes(related_id, self.repo)
                except Exception:
                    return None
            return super()._generated_report(related_table, related_id)

    return ECNNotificationService(repo)


__all__ = [
    "FORMAT_NO", "FORMAT_REV_DATE", "FORMAT_REV_NO", "CHANGE_TYPES", "ECN_STATUSES", "PRIORITIES", "SUPPORTING_DOCUMENTS",
    "DRAWING_CHANGE_MODES", "CUSTOMER_APPROVALS", "FSI_DECISIONS", "CONTACT_FIELDS", "DOCUMENT_SCOPES", "TRANSITIONS",
    "ECNService", "next_ecn_number", "next_from_existing", "format_ecn_number", "ecn_prefix", "normalize_ecn_payload",
    "validate_ecn", "can_transition", "allowed_targets", "revision_defaults", "release_with_ecn", "ecn_email_text",
    "ecn_notifier", "change_title", "contact_text", "employee_name", "normalize_status", "status_label", "STATUS_LABELS",
    "TRANSITION_LABELS", "LEGACY_STATUSES", "ATTACHMENT_ENTITY", "DEPARTMENT", "default_representative",
    "ACTION_TABLE", "ACTION_STATUSES", "DEFAULT_ACTIONS", "NOTIFY_DEPARTMENTS", "normalize_action_rows", "default_actions",
    "notification_recipients", "notify_ecn_created",
]
