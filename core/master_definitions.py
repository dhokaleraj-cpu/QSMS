from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class FieldDef:
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    options: Sequence[str] = ()
    lookup: str = ""
    placeholder: str = ""
    help: str = ""
    default: Any = None
    allow_none: bool = True


@dataclass(frozen=True)
class MasterDef:
    key: str
    label: str
    group: str
    table: str
    description: str
    fields: Sequence[FieldDef]
    columns: Sequence[str]
    search_fields: Sequence[str]
    natural_key: Sequence[str]
    order_by: str
    fixed_values: Mapping[str, Any] = field(default_factory=dict)
    array_filter: Mapping[str, Sequence[str]] = field(default_factory=dict)
    status_field: str = "status"
    auto_code_field: str = ""


MASTER_GROUPS = {
    "Parties": "Customers, suppliers, steel mills and outside-process vendors",
    "Product & Material": "Parts, grades, chemistry and approved source relationships",
    "Process & Quality": "Processes, inspection stages, gauges, fixtures, plans and tests",
    "Standards & Specifications": "Customer standards and specifications linked to processes and parts",
}


PARTY_FIELDS = (
    FieldDef("party_code", "Master code", required=True, placeholder="Auto-generated; editable"),
    FieldDef("party_name", "Name", required=True, placeholder="Company name"),
    FieldDef("country", "Country", placeholder="India"),
    FieldDef("state", "State / Region"),
    FieldDef("city", "City"),
    FieldDef("address", "Address", kind="textarea"),
    FieldDef("contact_person", "Contact person"),
    FieldDef("email", "Primary Email"),
    FieldDef("notification_emails", "Notification Email(s)", placeholder="Additional supplier/customer email addresses separated by comma or semicolon"),
    FieldDef("phone", "Phone"),
    FieldDef("tax_identifier", "GSTIN / Tax identifier"),
    FieldDef("approval_status", "Approval status", kind="select", options=("APPROVED", "PENDING", "REJECTED"), default="APPROVED", required=True),
    FieldDef("status", "Record status", kind="select", options=("ACTIVE", "INACTIVE"), default="ACTIVE", required=True),
    FieldDef("remarks", "Remarks", kind="textarea"),
)


DEFINITIONS = (
    MasterDef(
        key="customers", label="Customers", group="Parties", table="parties",
        description="Customer identity, location and approval status used by Part Master and dispatch genealogy.",
        fields=PARTY_FIELDS,
        columns=("party_code", "party_name", "country", "city", "contact_person", "approval_status", "status"),
        search_fields=("party_code", "party_name", "country", "city", "contact_person"),
        natural_key=("party_code",), order_by="party_code",
        fixed_values={"party_types": ["CUSTOMER"]}, array_filter={"party_types": ["CUSTOMER"]}, auto_code_field="party_code",
    ),
    MasterDef(
        key="suppliers", label="Suppliers", group="Parties", table="parties",
        description="Raw material, forging and bought-out component suppliers approved for quality use.",
        fields=PARTY_FIELDS,
        columns=("party_code", "party_name", "country", "city", "approval_status", "status"),
        search_fields=("party_code", "party_name", "country", "city"),
        natural_key=("party_code",), order_by="party_code",
        fixed_values={"party_types": ["SUPPLIER"]}, array_filter={"party_types": ["SUPPLIER"]}, auto_code_field="party_code",
    ),
    MasterDef(
        key="steel_mills", label="Steel Mills", group="Parties", table="parties",
        description="Approved steel-producing mills linked to RMTC approval and heat traceability.",
        fields=PARTY_FIELDS,
        columns=("party_code", "party_name", "country", "approval_status", "status"),
        search_fields=("party_code", "party_name", "country"),
        natural_key=("party_code",), order_by="party_code",
        fixed_values={"party_types": ["STEEL_MILL"]}, array_filter={"party_types": ["STEEL_MILL"]}, auto_code_field="party_code",
    ),
    MasterDef(
        key="osp_vendors", label="OSP Vendors", group="Parties", table="parties",
        description="Outside-process suppliers for heat treatment, gear shaping and other controlled processes.",
        fields=PARTY_FIELDS,
        columns=("party_code", "party_name", "country", "approval_status", "status"),
        search_fields=("party_code", "party_name", "country"),
        natural_key=("party_code",), order_by="party_code",
        fixed_values={"party_types": ["OSP_VENDOR", "SUPPLIER"]}, array_filter={"party_types": ["OSP_VENDOR"]}, auto_code_field="party_code",
    ),
    MasterDef(
        key="parts", label="Parts", group="Product & Material", table="parts",
        description="Customer part, drawing, controlled grade, weights and manufacturing-route definition.",
        fields=(
            FieldDef("part_number", "Part number", required=True, placeholder="71.784.3"),
            FieldDef("fsi_part_number", "FSI Part Number", placeholder="FSI-000123", help="Secondary FSI identity used on supplier-facing documents to protect the original/customer Part Number."),
            FieldDef("part_name", "Part description", required=True, placeholder="Differential Spider"),
            FieldDef("customer_id", "Customer", kind="lookup", lookup="customers", required=True, allow_none=False),
            FieldDef("material_grade_id", "Material grade", kind="lookup", lookup="material_grades", required=True, allow_none=False),
            FieldDef("drawing_number", "Drawing number"),
            FieldDef("drawing_revision", "Drawing revision"),
            FieldDef("finished_weight_kg", "Finished weight (kg)", kind="number"),
            FieldDef("forging_weight_kg", "Forging weight (kg)", kind="number"),
            FieldDef("gross_weight_kg", "Gross weight (kg)", kind="number"),
            FieldDef("section_size", "Raw material section"),
            FieldDef("manufacturing_route", "Manufacturing route", kind="textarea"),
            FieldDef("special_characteristics", "Special characteristics / Jominy / heat-treatment details", kind="json", help="Use JSON for structured requirements, or plain text."),
            FieldDef("status", "Record status", kind="select", options=("ACTIVE", "INACTIVE"), default="ACTIVE", required=True),
            FieldDef("remarks", "Remarks", kind="textarea"),
        ),
        columns=("part_number", "fsi_part_number", "part_name", "customer_id", "material_grade_id", "drawing_revision", "finished_weight_kg", "status"),
        search_fields=("part_number", "fsi_part_number", "part_name", "drawing_number", "manufacturing_route"),
        natural_key=("part_number",), order_by="part_number",
    ),
    MasterDef(
        key="material_grades", label="Material Grades", group="Product & Material", table="material_grades",
        description="Controlled material grade, governing standard, revision and effective date.",
        fields=(
            FieldDef("grade_code", "Grade", required=True, placeholder="20MnCr5"),
            FieldDef("standard", "Standard", placeholder="EN 10084"),
            FieldDef("revision", "Revision", default="Current"),
            FieldDef("effective_date", "Effective date", kind="date"),
            FieldDef("status", "Record status", kind="select", options=("ACTIVE", "INACTIVE"), default="ACTIVE", required=True),
            FieldDef("remarks", "Remarks", kind="textarea"),
        ),
        columns=("grade_code", "standard", "revision", "effective_date", "status"),
        search_fields=("grade_code", "standard", "revision"),
        natural_key=("grade_code", "revision"), order_by="grade_code",
    ),
    MasterDef(
        key="chemical_composition", label="Chemical Composition", group="Product & Material", table="material_grade_elements",
        description="Element-wise minimum and maximum chemistry limits for RMTC compliance evaluation.",
        fields=(
            FieldDef("material_grade_id", "Material grade", kind="lookup", lookup="material_grades", required=True, allow_none=False),
            FieldDef("element", "Element", required=True, placeholder="C"),
            FieldDef("minimum", "Minimum", kind="number"),
            FieldDef("maximum", "Maximum", kind="number"),
            FieldDef("unit", "Unit", kind="select", options=("%", "ppm"), default="%", required=True),
            FieldDef("test_method", "Test method"),
        ),
        columns=("material_grade_id", "element", "minimum", "maximum", "unit", "test_method"),
        search_fields=("element", "unit", "test_method"),
        natural_key=("material_grade_id", "element"), order_by="element", status_field="",
    ),
    MasterDef(
        key="approved_sources", label="Approved Sources", group="Product & Material", table="part_supplier_links",
        description="Part-wise supplier and steel-mill approval link required before RMTC approval.",
        fields=(
            FieldDef("source_code", "Master code", required=True, placeholder="Auto-generated; editable"),
            FieldDef("part_id", "Part", kind="lookup", lookup="parts", required=True, allow_none=False),
            FieldDef("supplier_id", "Supplier", kind="lookup", lookup="suppliers", required=True, allow_none=False),
            FieldDef("steel_mill_id", "Steel mill", kind="lookup", lookup="steel_mills"),
            FieldDef("supplier_part_number", "Supplier part number"),
            FieldDef("approval_reference", "Approval reference"),
            FieldDef("approved", "Approved", kind="boolean", default=True),
            FieldDef("valid_from", "Valid from", kind="date"),
            FieldDef("valid_to", "Valid to", kind="date"),
        ),
        columns=("source_code", "part_id", "supplier_id", "steel_mill_id", "supplier_part_number", "approval_reference", "approved", "valid_from", "valid_to"),
        search_fields=("source_code", "supplier_part_number", "approval_reference"),
        natural_key=("part_id", "supplier_id", "steel_mill_id"), order_by="created_at", status_field="approved", auto_code_field="source_code",
    ),
    MasterDef(
        key="customer_standards", label="Customer Standards & Specifications", group="Standards & Specifications", table="customer_standards",
        description="Controlled customer standards/specifications with author, revision, customer and related Process Master linkage.",
        fields=(
            FieldDef("standard_code", "Standard Code", required=True, placeholder="Auto-generated; editable"),
            FieldDef("standard_name", "Standard / Specification Name", required=True, placeholder="Heat Treatment Specification"),
            FieldDef("customer_id", "Customer", kind="lookup", lookup="customers", allow_none=True),
            FieldDef("process_id", "Related Process", kind="lookup", lookup="processes", required=True, allow_none=False),
            FieldDef("author_name", "Author / Issuing Authority"),
            FieldDef("revision_number", "Revision Number", required=True, default="00"),
            FieldDef("revision_date", "Revision Date", kind="date"),
            FieldDef("status", "Record Status", kind="select", options=("ACTIVE", "INACTIVE", "SUPERSEDED"), default="ACTIVE", required=True),
            FieldDef("remarks", "Remarks", kind="textarea"),
        ),
        columns=("standard_code", "standard_name", "customer_id", "process_id", "author_name", "revision_number", "revision_date", "status"),
        search_fields=("standard_code", "standard_name", "author_name", "revision_number", "remarks"),
        natural_key=("customer_id", "process_id", "standard_code", "revision_number"),
        order_by="standard_code", auto_code_field="standard_code",
    ),
    MasterDef(
        key="processes", label="Processes", group="Process & Quality", table="processes",
        description="In-house and outsourced process catalogue, including special-process and CQI controls.",
        fields=(
            FieldDef("process_code", "Master code", required=True, placeholder="Auto-generated; editable"),
            FieldDef("process_name", "Process name", required=True, placeholder="Case Carburizing"),
            FieldDef("process_type", "Process type", kind="select", options=("IN_HOUSE", "OUTSOURCED"), default="IN_HOUSE", required=True),
            FieldDef("special_process", "Special process", kind="boolean", default=False),
            FieldDef("cqi_standard", "CQI standard", placeholder="CQI-9"),
            FieldDef("status", "Record status", kind="select", options=("ACTIVE", "INACTIVE"), default="ACTIVE", required=True),
            FieldDef("remarks", "Remarks", kind="textarea"),
        ),
        columns=("process_code", "process_name", "process_type", "special_process", "cqi_standard", "status"),
        search_fields=("process_code", "process_name", "process_type", "cqi_standard"),
        natural_key=("process_code",), order_by="process_code", auto_code_field="process_code",
    ),
    MasterDef(
        key="inspection_stages", label="Inspection Stages", group="Process & Quality", table="inspection_stages",
        description="Controlled incoming, setup, stage, OSP receipt and final inspection sequence.",
        fields=(
            FieldDef("stage_code", "Master code", required=True, placeholder="Auto-generated; editable"),
            FieldDef("stage_name", "Stage name", required=True, placeholder="Final Inspection"),
            FieldDef("sequence_no", "Sequence", kind="integer", default=10, required=True),
            FieldDef("status", "Record status", kind="select", options=("ACTIVE", "INACTIVE"), default="ACTIVE", required=True),
        ),
        columns=("sequence_no", "stage_code", "stage_name", "status"),
        search_fields=("stage_code", "stage_name"), natural_key=("stage_code",), order_by="sequence_no", auto_code_field="stage_code",
    ),
    MasterDef(
        key="quality_assets", label="Quality Assets", group="Process & Quality", table="quality_assets",
        description="Instruments, equipment, gauges, fixtures, jigs, masters and reference standards.",
        fields=(
            FieldDef("asset_code", "Master code", required=True, placeholder="Auto-generated; editable"),
            FieldDef("asset_name", "Asset name", required=True),
            FieldDef("asset_type", "Asset type", kind="select", options=("INSTRUMENT", "EQUIPMENT", "GAUGE", "FIXTURE", "JIG", "MASTER", "REFERENCE_STANDARD"), default="GAUGE", required=True),
            FieldDef("manufacturer", "Manufacturer"),
            FieldDef("model", "Model"),
            FieldDef("serial_number", "Serial number"),
            FieldDef("range_text", "Range"),
            FieldDef("least_count", "Least count"),
            FieldDef("location", "Location"),
            FieldDef("calibration_frequency_days", "Calibration frequency (days)", kind="integer", default=365, required=True),
            FieldDef("last_calibration_date", "Last calibration date", kind="date"),
            FieldDef("next_due_date", "Next due date", kind="date"),
            FieldDef("status", "Record status", kind="select", options=("ACTIVE", "INACTIVE", "BLOCKED"), default="ACTIVE", required=True),
            FieldDef("remarks", "Remarks", kind="textarea"),
        ),
        columns=("asset_code", "asset_name", "asset_type", "location", "next_due_date", "status"),
        search_fields=("asset_code", "asset_name", "asset_type", "manufacturer", "serial_number", "location"),
        natural_key=("asset_code",), order_by="asset_code", auto_code_field="asset_code",
    ),
    MasterDef(
        key="inspection_plans", label="Inspection Plans", group="Process & Quality", table="inspection_plans",
        description="Part-wise process and stage inspection plan headers.",
        fields=(
            FieldDef("part_id", "Part", kind="lookup", lookup="parts", required=True, allow_none=False),
            FieldDef("process_id", "Process", kind="lookup", lookup="processes"),
            FieldDef("inspection_stage_id", "Inspection stage", kind="lookup", lookup="inspection_stages"),
            FieldDef("plan_number", "Plan number", required=True),
            FieldDef("revision", "Revision", default="00", required=True),
            FieldDef("effective_date", "Effective date", kind="date"),
            FieldDef("sample_plan", "Sample plan"),
            FieldDef("status", "Plan status", kind="select", options=("DRAFT", "APPROVAL_PENDING", "APPROVED", "SUPERSEDED"), default="DRAFT", required=True),
        ),
        columns=("plan_number", "revision", "part_id", "process_id", "inspection_stage_id", "sample_plan", "status"),
        search_fields=("plan_number", "revision", "sample_plan"),
        natural_key=("plan_number", "revision"), order_by="plan_number",
    ),
    MasterDef(
        key="inspection_characteristics", label="Inspection Characteristics", group="Process & Quality", table="inspection_plan_characteristics",
        description="Variable and attribute characteristics, checking aids, sample size and reaction plan.",
        fields=(
            FieldDef("inspection_plan_id", "Inspection plan", kind="lookup", lookup="inspection_plans", required=True, allow_none=False),
            FieldDef("sequence_no", "Sequence", kind="integer", default=10, required=True),
            FieldDef("characteristic_no", "Characteristic number"),
            FieldDef("characteristic", "Characteristic", required=True),
            FieldDef("specification", "Specification"),
            FieldDef("lower_spec", "Lower specification", kind="number"),
            FieldDef("upper_spec", "Upper specification", kind="number"),
            FieldDef("unit", "Unit"),
            FieldDef("characteristic_type", "Type", kind="select", options=("VARIABLE", "ATTRIBUTE"), default="VARIABLE", required=True),
            FieldDef("special_class", "Special class", placeholder="CC / SC"),
            FieldDef("checking_aid_id", "Checking aid", kind="lookup", lookup="quality_assets"),
            FieldDef("checking_method", "Checking method"),
            FieldDef("sample_size", "Sample size", kind="integer"),
            FieldDef("frequency", "Frequency"),
            FieldDef("reaction_plan", "Reaction plan", kind="textarea"),
        ),
        columns=("inspection_plan_id", "sequence_no", "characteristic_no", "characteristic", "specification", "checking_aid_id", "sample_size", "frequency"),
        search_fields=("characteristic_no", "characteristic", "specification", "checking_method", "frequency"),
        natural_key=("inspection_plan_id", "sequence_no"), order_by="sequence_no", status_field="",
    ),
    MasterDef(
        key="test_plans", label="Test Plans", group="Process & Quality", table="test_plans",
        description="Part-wise metallurgical, tensile, bend, impact, Jominy, DI, XRF and Millipore test planning.",
        fields=(
            FieldDef("part_id", "Part", kind="lookup", lookup="parts", required=True, allow_none=False),
            FieldDef("process_id", "Process", kind="lookup", lookup="processes"),
            FieldDef("inspection_stage_id", "Inspection stage", kind="lookup", lookup="inspection_stages"),
            FieldDef("plan_number", "Plan number", required=True),
            FieldDef("revision", "Revision", default="00", required=True),
            FieldDef("test_type", "Test type", kind="select", options=("TENSILE", "BEND", "METLAB", "IMPACT", "JOMINY", "DI_VALUE", "XRF", "MILLIPORE", "HARDNESS", "CASE_DEPTH"), required=True),
            FieldDef("specification_reference", "Specification reference"),
            FieldDef("frequency", "Frequency"),
            FieldDef("sample_size", "Sample size", kind="integer"),
            FieldDef("acceptance_criteria", "Acceptance criteria", kind="json", help="Use JSON for structured criteria, or plain text."),
            FieldDef("status", "Plan status", kind="select", options=("DRAFT", "APPROVAL_PENDING", "APPROVED", "SUPERSEDED"), default="DRAFT", required=True),
        ),
        columns=("plan_number", "revision", "part_id", "process_id", "inspection_stage_id", "test_type", "frequency", "status"),
        search_fields=("plan_number", "revision", "test_type", "specification_reference", "frequency"),
        natural_key=("plan_number", "revision"), order_by="plan_number",
    ),
)

MASTER_BY_KEY = {definition.key: definition for definition in DEFINITIONS}
