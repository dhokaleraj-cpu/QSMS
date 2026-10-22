# STAWN QCMS v4.14.49 R35b (includes everything in R35)

## R35b additions
- Website: every browser tab and the address bar now show the STAWN icon and "STAWN QCMS · <page>". Before this, each page's own icon replaced the favicon.
- Android and iPhone/iPad: the STAWN logo and "STAWN QCMS" sit on the left of the top bar.
- STAWN Developer admin section (left menu → STAWN Developer, shown only to the STAWN developer login) holds every right:
  - all companies and licences: issue, renew, suspend or revoke keys
  - create companies and assign company admins
  - edit any company's profile and logo
  - STAWN-only branding
  - one-click access to every admin tool

# STAWN QCMS v4.14.49 R35: issue fixes, notifications, licensing, KPI start dashboard

This release covers the website, Android app v3.4.0 and iPhone / iPad app v1.1.0. The database changes are live, and the updater re-applies them safely.

## Issues from "QCMS software issues.xlsx"

1. **MetLAB inward part entry**
   - The pending list now has a Layout column and names every part that cannot be entered, with the reason. For example, a part may have no inward layout, or only Final, OSP or Bend layouts.
   - Parts that currently cannot be entered:
     - 223001016, 41.1356.3 and 51.4465.2 have no layout.
     - 91.6289.2 has only Final and OSP layouts.
     - 40257237 has only Bend layouts.
2. **Bend Test and OSP finalization**
   - Finalize now saves newly chosen photos, the structure image and captions first.
   - Saved photos show as thumbnails and are kept.
   - The new "Add / replace photographs on this finalized report" option (password required) keeps the report FINAL.
   - Re-uploads no longer create duplicate attachment rows.
3. **Report errors**
   - Errors now name the field or step that failed: required field, duplicate, missing master, not-allowed value, permission, number or date, timeout.
   - Save and Finalize list every reason they are disabled.
4. **PO quantity and inward**
   - PO line Ordered Qty is editable, but never below the received quantity.
   - Inward above the PO quantity is allowed up to a tolerance (default 10%, admin setting).
   - Above the tolerance, a Supply Chain approver must tick an override and give a reason.
   - Duplicate-GRN retries are fixed.
5. **Inspection Layout Master**: a visible "＋ New Layout" button. The selector no longer jumps back to the last layout.
6. **Part Production / Customer Dispatch**: every previous-stage list shows CO · Pos · Part · FSI · Description · Heat · Qty · Ref · Stage, with a search box.
7. **User link (Saket Jha)**
   - Saket's employee record (qcd11@) has no QCMS login yet.
   - Users & Access now has "Create login for an Employee without login", plus a Link check list with an e-mail mismatch warning.
8. **OSP sample receipt to Dimensional**: the queue now also accepts the approved OSP layout of the same part and process.
   - Please correct the process of the layout "CASE CARBURIZING 9265" in Layout Master (it is saved under Quench & Tempering).

## Errors from the screenshots

- **Customer Order delete blocked by a PO**
  - A plain message replaces the raw error.
  - Each holding PO gets two actions: "Open in Edit PO" and "Remove this order from the PO".
  - Removing an order needs a reason and your password. On an approved PO it sends the PO back for re-approval.
- **RM PO "no common supplier-specific raw material"**
  - The message now shows, per order, which supplier, grade, section and size is missing.
  - Orders with the same steel but a different price or HSN stay on one PO as separate lines.

## New features

- **Machining / production selection**: order number, position, part number and quantity in every list, with search.
- **Six-month schedule re-entry**
  - Shows a preview first.
  - The current and future months are overwritten. Past months are never changed.
  - A month is never cut below quantity already used downstream, or cancelled once its RM is on a PO.
- **Live stage stock**: when creating a Customer Order, an RM or forging PO, or an RM to forging dispatch, a panel shows quantities at each stage:
  - open orders
  - RM ordered, pending, at FSI and at the forger
  - forgings received
  - machining WIP
  - FG stock
  - dispatched
- **Global search**
  - Searches every module, screen, field and database record.
  - "J5/16" finds every record holding it.
  - "bend test" lists the Bend Test modules to open plus all related records.
- **KPI start dashboard**
  - Quality comes first with your pending tasks, then Supply Chain, Production, NPD and Management.
  - Department tabs, with an animated automatic switch every 20 seconds.
- **Custom KPI dashboards**
  - Each user can build several dashboards from KPI cards, charts and tables, then reorder and resize them.
  - A dashboard can be shared with the company.
- **Notifications**
  - The 🔔 bell on the website and the app inbox show:
    - PO approval requests and decisions
    - deletion requests
    - report finalisation and approval
    - complaint and CAPA owners
    - customer-order responsibility
    - every QCMS e-mail to the user
  - Phone alerts:
    - **iPhone / iPad**: push notifications through APNs.
    - **Android**: phone alerts through a background check every 15 minutes.
- **WhatsApp auto messages**
  - Uses the Meta WhatsApp Business Cloud API.
  - The administrator connects the company number once in Admin → Licence & Company. Each user opts in on My Notifications.
- **STAWN branding and licensing**
  - "STAWN QCMS" is shown with the STAWN icon, and the licensed company appears under it.
  - Company licence keys have the form STAWN-QCMS-XXXXX-XXXXX-XXXXX-XXXXX. They are signed by STAWN, validated online and limited to the licensed number of users.
  - The company administrator sets up the company profile and logo once.
  - The STAWN Developer Console is for STAWN only. It shows every company and can issue, renew, suspend or revoke keys, create companies and assign company administrators.
  - Four Star Industries has an active ENTERPRISE licence with no expiry and 50 users.

## Mobile apps

- **Android v3.4.0**
  - KPI start dashboard
  - notification bell, inbox and phone alerts
  - WhatsApp opt-in
  - server-wide global search
  - licence check and licence details in About
- **iPhone / iPad v1.1.0**
  - the same features as Android, with real push notifications
  - signing fix for "Your team has no devices / No profiles found": the Team ID is detected automatically, and Release builds sign with Apple Distribution, so TestFlight needs no registered device.
