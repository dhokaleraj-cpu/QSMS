# QSMS 4.8.6

Live Supabase-first quality workflow for Four Star Industries.

Visible workspaces:

1. Dashboard
2. Masters
3. RMTC
4. Material Inward
5. Inspections
6. Records Centre
7. Templates


## Release 4.8.6 — Supplier RMTC Identity & Heat Steel Ledger

- The same Heat Number may be used by multiple RMTC records only when the Supplier RMTC Number is different.
- Supplier and Part Number may repeat when the supplier has issued a new RMTC number.
- The Heat Steel Ledger lists Part-wise planned quantity, planned steel, inward quantity, inward steel, global Heat quantity and balance.
- Heat Steel Ledger records can be downloaded to Excel.
- Global Heat steel validation remains shared across every RMTC, supplier, part and inward transaction.
- Existing records remain unchanged.


## Release 4.8.4 — Unified Records and Inward Status Consistency

- Add a prominent **Add New RMTC for This Heat Number** action while retaining the searched Heat Number.
- Permit a new RMTC for the same Heat Number when Supplier or Part Number differs, while active duplicate Supplier–Part combinations remain blocked.
- Add one Records Centre page covering RMTC, Material Inward, Dimensional, MetLAB, Inspection Layouts and Masters.
- Use one enriched Material Inward register for Dashboard, Inward Entry and Inward Records so counts and statuses match.
- Show Supplier and Part names instead of UUIDs on Dashboard and registers.
- Show existing Hold Pending Inspection inward records directly on the Material Inward entry page.

## Release 4.8.3 — Heat Number Search and Global Steel Ledger

- Search the Heat Number before creating an RMTC.
- View every RMTC, Supplier, Part Number, planned quantity and steel usage under that Heat Number.
- Reuse a rejected RMTC Heat Number for a new Supplier or Part Number.
- Prevent active duplicate Supplier–Part combinations.
- Enforce one global steel balance across all RMTC and Material Inward transactions for the Heat Number.

## Release 4.8.2 — Automatic Master Codes and Dashboard Analytics

- RMTC certificate quantity is treated as the total steel quantity for the complete Heat Number.
- Every covered Part Worksheet records Part Production Quantity, supplier Input Weight and calculated Planned Steel Quantity.
- Total planned steel across all parts cannot exceed the RMTC heat steel quantity.
- Material Inward splits production into Accepted, Rejected and On Hold quantities in pieces and calculates each steel quantity automatically.
- Cumulative steel consumption across all inward transactions and all parts for the Heat Number cannot exceed the RMTC steel quantity.
- MetLAB reports support four private microstructure images with individual captions.
- Supplier forging parameters are inherited from the Part Master and displayed in source selection.
- Dimensional and MetLAB layouts are automatically selected from approved Part + Process + Inspection Stage layouts, with manual override.
- Layout name and layout type/section are inherited automatically.
- Dimensional characteristics are generated from the selected approved layout.
- Raw Material MetLAB mirrors the RMTC Part Worksheet with Chemistry, Jominy, Heat Treatment / Mechanical Requirements and additional layout characteristics.
- Multi-row grid saves use bulk Supabase upsert to reduce submission time.

## RMTC Workflow

Save the RMTC header, complete each Part Worksheet, submit for validation, validate against masters, and record the authorized final decision. Manual acceptance remains available with a mandatory reason and audit history.

## Local run

```bash
cd /Users/dhokaleraj/QSMS
source .venv/bin/activate
python -m streamlit run streamlit_app.py --server.port 8510
```

## GitHub

```bash
./scripts/push_github.sh
```

Local Supabase secrets remain in `.streamlit/secrets.toml` and are excluded from Git.


## Release 4.8.2 — Automatic Master Codes and Dashboard Analytics

- Automatic editable codes for Customers, Suppliers, Steel Mills, OSP Vendors, Approved Sources, Processes, Inspection Stages and Quality Assets.
- Expanded KPI dashboard with steel and production totals.
- Pie charts for recent inward disposition, RMTC validation status and inward status.
- Existing records and codes remain unchanged.

### Heat Steel Ledger
The same Heat Number may have multiple RMTC records only when the Supplier RMTC Number is different. The Heat Steel Ledger lists Part-wise planned steel, inward steel, global Heat quantity and balance.
