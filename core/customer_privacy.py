"""R36b · Customer confidentiality.

Rule (STAWN QCMS policy for every company): customer identity and customer commercial details - customer name /
code, customer PO / order number and position, customer part number, customer delivery date, customer source
references - are INTERNAL. They are shown to the company's own team only and never leave QCMS towards a supplier,
vendor, steel mill, OSP vendor or any other outside address.

* A recipient is *internal* when the address belongs to an employee of the company or to one of the company's own
  mail domains (domains used by its employees / the configured sender mailbox). Everything else is *external*.
* Any e-mail with at least one external recipient is built from customer-safe data: customer fields are blanked in
  the template context, print-layout PDFs are rendered without customer details, the Purchase Order prints without
  the customer source reference, and customer-only documents are not attached.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

# Context / payload keys that carry customer information.
CUSTOMER_KEYS: frozenset[str] = frozenset({
    "customer", "customer_name", "customer_code", "customer_email", "customer_phone", "customer_address",
    "customer_po", "customer_po_no", "customer_po_number", "customer_order_no", "customer_order_number",
    "customer_order_position", "order_position", "po_position", "customer_part_number", "customer_part_no",
    "customer_delivery_date", "customer_source_rows", "customer_reference", "customer_references",
    "master_reference_no", "end_customer", "customer_party", "customers",
})
# document_attachments.entity_type values that are customer documents (never attached to an external e-mail).
CUSTOMER_ONLY_ENTITY_TYPES: frozenset[str] = frozenset({"SUPPLY_CUSTOMER_ORDER", "CUSTOMER_STANDARD"})
MASK = "—"
_EMAIL = re.compile(r"[^@\s<>;,]+@([^@\s<>;,]+)")


def _domain(email: str) -> str:
    match = _EMAIL.search(str(email or "").strip().lower())
    return match.group(1) if match else ""


def internal_directory(repo: Any) -> tuple[set[str], set[str]]:
    """(employee e-mails, company mail domains) of the signed-in company."""
    emails: set[str] = set()
    domains: set[str] = set()
    try:
        for row in repo.select("employees", limit=5000) or []:
            value = str(row.get("email") or "").strip().lower()
            if "@" in value:
                emails.add(value)
                domains.add(_domain(value))
    except Exception:
        pass
    try:
        rows = repo.select("qcms_email_settings", limit=1) or []
        sender = str((rows[0] if rows else {}).get("sender_email") or "").strip().lower()
        if "@" in sender:
            domains.add(_domain(sender))
    except Exception:
        pass
    # Public mailbox providers are never treated as a company domain.
    domains -= {"gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "icloud.com", "rediffmail.com", "live.com", ""}
    return emails, domains


def is_internal(email: str, directory: tuple[set[str], set[str]]) -> bool:
    value = str(email or "").strip().lower()
    if not value:
        return True
    emails, domains = directory
    return value in emails or _domain(value) in domains


def external_recipients(recipients: Iterable[str], directory: tuple[set[str], set[str]]) -> list[str]:
    return [str(r).strip() for r in recipients if str(r or "").strip() and not is_internal(str(r), directory)]


def scrub_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Template context with every customer field blanked (used for external e-mails)."""
    out = dict(context or {})
    for key in list(out):
        if key.lower() in CUSTOMER_KEYS or key.lower().startswith("customer_"):
            out[key] = MASK
    return out


def strip_customer(payload: Any, _depth: int = 0) -> Any:
    """Deep copy of a report / PO payload without customer data (print-layout PDFs for external use)."""
    if _depth > 4:
        return payload
    if isinstance(payload, Mapping):
        clean: dict[str, Any] = {}
        for key, value in payload.items():
            low = str(key).lower()
            if low in CUSTOMER_KEYS or low.startswith("customer_"):
                clean[key] = {} if isinstance(value, Mapping) else ([] if isinstance(value, (list, tuple)) else ("" if value is not None else None))
            else:
                clean[key] = strip_customer(value, _depth + 1)
        return clean
    if isinstance(payload, list):
        return [strip_customer(v, _depth + 1) for v in payload]
    return payload


def supplier_safe_po(header: Mapping[str, Any], items: Any) -> tuple[dict[str, Any], Any]:
    """Purchase Order header + lines for anything that can reach a supplier: no customer source reference."""
    options = dict((header or {}).get("print_options") or {})
    options["show_source_reference"] = False
    safe_header = {**dict(header or {}), "print_options": options}
    if isinstance(items, Mapping):
        return safe_header, strip_customer(items)
    return safe_header, [strip_customer(i) for i in (items or [])]
