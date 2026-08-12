# QCMS 4.10.3

## Part Master standards visibility
- Linked Standard download controls now display Standard Code, Standard Name, Author, Related Process and Revision.
- Existing links are protected from ordinary edit/save operations.
- Adding standards remains available to users with Part Master edit permission.

## Admin-only unlink
- Unlinking a Standard / Specification from a Part is available only to the QCMS ADMIN role.
- Administrator current-password confirmation is required in the UI.
- A database trigger and RLS DELETE policy enforce the Admin-only rule even outside the Streamlit UI.

## Readability
- Global application typography has approximately 10% stronger visual weight for normal text, labels, inputs, menus, buttons and data grids.
- Font sizes and compact page density remain unchanged.
