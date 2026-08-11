# QSMS 4.9.3 — High-Contrast Export Shipment App Theme

## Purpose

This release corrects the washed-out header and menu appearance visible in the live Quality Control Monitoring System and aligns the application shell with the approved Export Shipment Monitoring System reference.

## Visual corrections

- Dark navy-to-blue Four Star Industries application header is now forced through Streamlit 1.60+ keyed-container wrappers.
- Company identity, QSMS title, active page, Apps launcher, user details and Exit action remain readable in white on the blue header.
- Application background uses the approved light-blue Export Shipment style rather than an almost-white flat canvas.
- The MODULES panel uses a clearly visible white surface, blue-grey border and stronger shadow.
- Inactive module buttons use a light-blue background and dark navy text.
- Active module buttons use a high-contrast blue gradient with white text.
- The active module submenu uses the same visible panel treatment and consistent Aptos/Segoe UI typography.
- Streamlit stale-rerun opacity is neutralized so the header and menus do not become unreadable during page switching.

## Existing v4.9.2 functionality retained

- Dedicated Process Master.
- OSP Inspection for MetLAB requirement grid with Parameter, Minimum Specification and Maximum Specification.
- Part-level Metallurgical Requirements grid without Process selection.
- Process-specific OSP MetLAB and final Metallurgical inspection layout generation.
- One main menu and one active-module submenu.
- Common PDF and Excel report header, footer, colour theme and page numbering.

## Data protection

This is a source and styling update only. It introduces no destructive database migration. Existing Supabase users, permissions, masters, RMTC records, Material Inward records, OSP transactions, inspections, layouts, attachments and legacy audit information remain unchanged.
