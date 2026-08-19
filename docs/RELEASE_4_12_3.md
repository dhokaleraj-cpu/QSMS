# QCMS 4.12.3

Build: `4123-SUPPLY-EXPORT-REFERENCE-HOTFIX`

## Fixes

- Fixes the Streamlit Cloud crash when Supply Chain Excel export titles contain Excel-forbidden worksheet characters such as `/`, `\\`, `?`, `*`, `:`, `[` or `]`.
- Uses one controlled Excel worksheet-name sanitizer in Supply Chain, Records Centre and Reports exports, including deterministic collision handling for multi-sheet workbooks.
- Reference Master record selectors now show the controlled code together with the record name/description and useful contextual fields instead of code-only labels.
- Lookup-based Reference Master records resolve linked Part, Supplier, Steel Mill and other master labels instead of displaying opaque UUIDs.
- Existing v4.12.2 Supply Chain master linkage, edit/delete, global search, status colors, six-month schedules, Material Inward bridge, lineage and import logic are preserved.

## Database

No new v4.12.3 database migration is required. The pending additive v4.12.1 and v4.12.2 migrations were applied directly to the connected QSMS Supabase project before this release was packaged, so deployment is a single application update command with no separate SQL action.
