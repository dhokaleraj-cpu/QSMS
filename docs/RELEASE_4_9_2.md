# QSMS 4.9.2 — Simplified MetLAB Requirements, Process Master and Unified Print Theme

## Part Master redesign

The Part Master no longer displays the legacy **Heat Treatment Details** or the broad **OSP Process & Inward Specifications** grids. Existing database rows are preserved for audit and backward compatibility, but the live interface now uses two focused requirement sections.

### OSP Inspection for MetLAB

- Select an active outsourced Process from the dedicated Process Master.
- Maintain exactly three user-facing columns:
  - Parameter
  - Minimum Specification
  - Maximum Specification
- Every requirement is stored against the selected Part Number and OSP Process.
- Case Carburizing, Quench & Tempering, Gas Nitriding, Nitro Carburising and other processes remain isolated from one another.
- The optional OSP Process Drawing remains attached to the Part + Process group with password-controlled replace and delete actions.
- The generated approved OSP MetLAB layout contains only the active parameters for the selected Part + Process.

### Metallurgical Requirements

- No Process selection is used.
- Maintain Parameter, Minimum Specification and Maximum Specification.
- These values represent final drawing metallurgical or special-process requirements for the Part Number.
- The generated approved Final Metallurgical MetLAB layout contains only these active Part-level requirements.
- Report validation uses the generated minimum and maximum limits.

## Dedicated Process Master

Process maintenance is now available as a dedicated Master page with Process Code, Process Name, Process Type, Special Process, CQI Standard, Status and Remarks. The Process option is removed from the generic Reference Master selector to avoid duplicate maintenance screens.

## Inspection queue behavior

OSP inspection worklists honor the requirement flags stored for the Part + Process group. A MetLAB-only process does not create a Dimensional pending task. The Supabase quality gate continues to treat a non-required inspection as accepted for gate calculation without creating a report.

## Navigation and visual design

- One persistent main module menu.
- One persistent submenu for the selected module.
- Legacy page-level repeated menus are suppressed.
- The shell uses the approved Four Star Industries navy-to-blue Export Shipment theme with company identity left, QSMS title centered and live user information right.
- Active menu items use a blue gradient pill; inactive menu items remain clean and readable on a white rounded panel.

## Report print standard

QSMS report exports use a common controlled layout:

- Four Star Industries logo and company identity
- Navy/blue header
- Report title
- Plant, version and printed timestamp
- Repeated table header on every page
- Alternating light-blue report rows
- Controlled-report footer and page numbering
- Matching Excel print headers, footers and landscape setup

## Data protection

The migration is additive. Existing RMTC, Heat, Material Inward, OSP, inspection, attachment and legacy Part Master records are retained. The deployment package preserves local secrets, Git history and the Python environment and pushes directly to GitHub `main` for Streamlit Cloud redeployment.
