# QSMS 4.9.1 — OSP Process Parameter Groups and Heat/OSP Reports

## OSP Process specification groups in Part Master

Each Part Number can now maintain one controlled specification group for every outsourced process, such as Case Carburizing, Quench & Tempering, Gas Nitriding or Nitro Carburising.

The OSP Process is the parent key. Every parameter, specification and drawing remains inside that process group and cannot be mixed with another process.

Each process group records:

- OSP Process and Process Type
- Inward Type: OSP Process
- Process Specification / Standard and reference
- Drawing Number and Drawing Revision
- Dimensional inspection requirement
- MetLAB inspection requirement
- Sample quantity
- Status and remarks
- One optional downloadable process drawing

## Process-specific inspection parameters

The selected OSP Process group contains its own inspection-parameter grid. Every parameter supports:

- Inspection Type: Dimensional or MetLAB
- Parameter name
- Specification text
- Minimum specification
- Maximum specification
- Unit
- Variable or Attribute characteristic
- Checking method
- Sample size
- Mandatory / Allow N.A.
- Sequence, status and remarks

Parameters previously used for the same outsourced process are available as reusable selections while remaining editable for the current Part Number.

## Inspection layout generation

The **Create / Update Inspection Layouts** action generates approved OSP Dimensional and MetLAB layouts directly from the active process group.

- Only parameters belonging to the selected Part + OSP Process are included.
- The process drawing number and revision are carried into the generated layout metadata.
- Unused generated layouts are refreshed in place.
- A layout already used by an inspection report is superseded and a new revision is generated, preserving the audit history.
- The generated layout remains linked to its original Part Master OSP Process specification group.

## Process drawing control

One optional process drawing can be uploaded for each Part + OSP Process group. The drawing can be downloaded at any time and can be replaced or deleted only through the existing password-controlled attachment workflow. DWG and DXF files are supported in addition to the existing document and image formats.

## New reports module

### Heat Number Global Balance with Transactions

Shows Heat-wise:

- Global Heat steel quantity
- Planned steel
- Material Inward steel
- Committed steel
- Global Heat balance
- OSP outward quantity
- OSP inward quantity
- Quantity at OSP vendor
- Complete transaction history covering RMTC Plan, Material Inward, OSP Out and OSP Inward

The report can be filtered by Heat Number and downloaded to Excel with separate Summary and Transactions sheets.

### Heat Number OSP Outward / Inward / Balance

Shows Heat Number and Part Number-wise:

- Quality-released production quantity
- Quantity sent to OSP
- Quantity inwarded from OSP
- Balance available to send to OSP
- Quantity currently at OSP vendor
- OSP process and vendor details
- Last OSP activity

The report can be filtered by Heat Number and Part Number and downloaded to Excel.

## Data protection

- The live Supabase migration is additive and preserves existing RMTC, Material Inward, inspection, OSP and attachment records.
- Existing credentials, Streamlit secrets and Git history remain unchanged.
- The deployment updater pushes directly to GitHub `main`; Streamlit Cloud rebuilds the live application automatically.
