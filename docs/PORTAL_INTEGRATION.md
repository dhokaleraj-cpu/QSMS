# FSI Digital Workplace Integration

## Common technology rule

The Company Portal and the current company applications use the same delivery pattern:

- **Python** for application logic
- **Streamlit** for the web interface
- **Supabase** for authentication, PostgreSQL, Row Level Security and storage
- **GitHub** for private source control and deployment workflow
- **VS Code** as the standard development workspace

## Application catalogue

| App ID | Application | Local port | Data ownership |
|---|---|---:|---|
| portal | FSI Company Portal | 8500 | Common identity, launcher, app access and announcements |
| export-shipment | Export Shipment Monitoring | 8501 | Shipment, delivery, payment and coverage data |
| qsms | Quality System Monitoring | 8510 | Quality masters, genealogy and evidence |
| hrms | HRMS | 8520 | Employee and HR workflows |

## Phase 1 integration

QSMS contains:

- A **Company apps** launcher in the common header.
- Configurable local and online URLs through Streamlit secrets.
- A machine-readable portal contract.
- A health endpoint supplied by Streamlit.
- Supabase tenant and role fields that the portal can map during the later SSO phase.

## Target identity model

The initial applications may retain their current Supabase Auth sessions. The portal identity phase will standardize:

- Company user identity
- Plant and department
- Application access
- Application role assignment
- SSO hand-off
- Cross-application access audit

Business data remains inside the owning application; the portal does not duplicate QSMS genealogy or shipment/HR transactions.
