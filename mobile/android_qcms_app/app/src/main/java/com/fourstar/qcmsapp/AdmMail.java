package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * app_pages/email_settings.py constants and the parts of core/notification_service.py the Email Settings page uses
 * (enqueue with an explicit recipient, dispatch through the qcms-send-email edge function, retry_pending).
 * Network methods must run inside Api.async.
 */
final class AdmMail {
    private AdmMail() { }

    /** EVENTS (key, label, module). */
    static final String[][] EVENTS = {
        {"RMTC_APPROVAL_PENDING", "RMTC approval pending", "RMTC_ENTRY"},
        {"DIMENSIONAL_APPROVAL_PENDING", "Dimensional approval pending", "DIMENSIONAL_REPORT"},
        {"METLAB_APPROVAL_PENDING", "MetLAB approval pending", "METLAB_REPORT"},
        {"RM_PROCUREMENT_PENDING", "Raw Material procurement pending", "SUPPLY_CHAIN"},
        {"RM_PO_CREATED", "Raw Material PO released", "SUPPLY_CHAIN"},
        {"RM_RECEIPT_PENDING", "Raw Material receipt pending", "SUPPLY_CHAIN"},
        {"FORGING_ORDER_PENDING", "Forging order pending", "SUPPLY_CHAIN"},
        {"FORGING_PO_CREATED", "Forging PO released", "SUPPLY_CHAIN"},
        {"FORGING_RECEIPT_PENDING", "Forging receipt pending", "SUPPLY_CHAIN"},
        {"OSP_SAMPLE_PENDING", "OSP sample inspection pending", "OSP_TRANSACTIONS"},
        {"CUSTOMER_ORDER_OPEN_OVERDUE_DIGEST", "Customer Orders · Open / Overdue digest", "SUPPLY_CHAIN"},
        {"RM_PO_OPEN_OVERDUE_DIGEST", "Raw Material PO · Open / Overdue digest", "SUPPLY_CHAIN"},
        {"FORGING_ORDER_OPEN_OVERDUE_DIGEST", "Forging Orders · Open / Overdue digest", "SUPPLY_CHAIN"},
        {"OSP_RETURN_OPEN_OVERDUE_DIGEST", "OSP Returns · Open / Overdue digest", "OSP_TRANSACTIONS"},
        {"NPD_PROCESS_OPEN_OVERDUE_DIGEST", "NPD Process Steps · Open / Overdue digest", "NPD_APQP"},
        {"CUSTOMER_ORDER_OVERDUE_BIENNIAL", "Customer Orders · Overdue · Every 2 Days · Excel", "SUPPLY_CHAIN"},
        {"RM_PENDING_BIENNIAL", "RM Procurement · Pending · Every 2 Days · Excel", "SUPPLY_CHAIN"},
        {"PO_PENDING_BIENNIAL", "Purchase Orders · Pending · Every 2 Days · Excel", "SUPPLY_CHAIN"},
        {"FORGING_RECEIPT_OVERDUE_BIENNIAL", "Forging Receipts · Overdue · Every 2 Days · Excel", "SUPPLY_CHAIN"},
    };

    static final String TEMPLATE_VARIABLES = "{{document_no}}  {{document_type}}  {{part_number}}  {{fsi_part_number}}  {{part_description}}  "
        + "{{heat_number}}  {{supplier_name}}  {{customer_name}}  {{due_date}}  {{next_stage}}  {{department}}  "
        + "{{report_date}}  {{open_count}}  {{overdue_count}}";

    static final String[][] COMMON_FIELDS = {
        {"document_no", "Document Number", "Related transaction · controlled document number"},
        {"document_type", "Document Type", "Related transaction"},
        {"part_number", "Part Number", "Part Master / related transaction item"},
        {"fsi_part_number", "FSI / Supplier-facing Part Number", "Part Master / PO Item"},
        {"part_description", "Part Description", "Part Master / PO Item"},
        {"heat_number", "Heat Number", "Related quality transaction"},
        {"supplier_name", "Supplier Name", "Party Master · Supplier"},
        {"supplier_code", "Supplier Code", "Party Master · Supplier"},
        {"customer_name", "Customer Name", "Party Master · Customer"},
        {"due_date", "Due / Delivery Date", "Related transaction"},
        {"next_stage", "Next Stage", "Notification route / workflow context"},
        {"department", "Responsible Department", "Notification route"},
    };
    static final String[][] PO_FIELDS = {
        {"po_number", "Purchase Order Number", "supply_purchase_orders.po_number"},
        {"order_date", "PO Date", "supply_purchase_orders.order_date"},
        {"delivery_date", "Delivery Date", "supply_purchase_orders.delivery_date"},
        {"quantity", "Total PO Quantity + UOM", "supply_purchase_order_items.quantity + uom"},
        {"quantity_value", "Total PO Quantity", "supply_purchase_order_items.quantity"},
        {"uom", "PO UOM", "supply_purchase_order_items.uom"},
        {"original_part_number", "Original / Finished Part Number(s)", "supply_purchase_order_items.original_part_number_snapshot"},
        {"item_description", "PO Item Description(s)", "supply_purchase_order_items.item_description"},
        {"line_count", "PO Line Count", "supply_purchase_order_items"},
        {"requisitioner", "Requisitioner", "supply_purchase_orders.requisitioner"},
        {"payment_term", "Payment Term", "supply_purchase_orders.payment_term"},
        {"incoterm", "Incoterm", "supply_purchase_orders.incoterm"},
        {"quotation_reference", "Quotation Reference", "supply_purchase_orders.quotation_reference"},
    };
    static final String[][] RMTC_FIELDS = {
        {"rmtc_number", "QCMS RMTC Number", "rmtc_approvals.rmtc_number"},
        {"certificate_reference", "Supplier RMTC Number", "rmtc_approvals.certificate_reference"},
        {"certificate_date", "RMTC Date", "rmtc_approvals.certificate_date"},
        {"heat_code", "Internal Heat Code", "rmtc_approvals.heat_code"},
    };
    static final String[][] REPORT_FIELDS = {
        {"report_number", "Report Number", "inspection_reports / lab_tests.report_number"},
        {"test_date", "MetLAB Test Date", "lab_tests.test_date"},
        {"inspection_date", "Dimensional Inspection Date", "inspection_reports.inspection_date"},
        {"sample_reference", "Sample Reference", "quality report.sample_reference"},
    };

    static String label(String key) {
        for (String[] e : EVENTS) if (e[0].equals(key)) return e[1];
        return key;
    }

    static String module(String key) {
        for (String[] e : EVENTS) if (e[0].equals(key)) return e[2];
        return "";
    }

    static List<String> keys() {
        List<String> out = new ArrayList<>();
        for (String[] e : EVENTS) out.add(e[0]);
        return out;
    }

    /** "label · module" labels for selectors. */
    static List<String> keyLabels(boolean withModule) {
        List<String> out = new ArrayList<>();
        for (String[] e : EVENTS) out.add(withModule ? e[1] + " · " + e[2] : e[1]);
        return out;
    }

    /** _template_field_catalog. */
    static List<String[]> fieldCatalog(String eventKey) {
        String event = eventKey == null ? "" : eventKey.toUpperCase(Locale.ROOT);
        List<String[]> rows = new ArrayList<>();
        for (String[] r : COMMON_FIELDS) rows.add(r);
        if (java.util.Arrays.asList("RM_PO_CREATED", "FORGING_PO_CREATED", "PO_APPROVED", "PO_APPROVAL_PENDING", "PO_CONFIRMATION_REQUIRED", "PO_CONFIRMATION_RECEIVED").contains(event))
            for (String[] r : PO_FIELDS) rows.add(r);
        if (event.startsWith("RMTC")) for (String[] r : RMTC_FIELDS) rows.add(r);
        if (event.contains("METLAB") || event.contains("DIMENSIONAL")) for (String[] r : REPORT_FIELDS) rows.add(r);
        LinkedHashSet<String> seen = new LinkedHashSet<>();
        List<String[]> out = new ArrayList<>();
        for (String[] r : rows) if (seen.add(r[0])) out.add(r);
        return out;
    }

    /** _append_template_placeholder. */
    static String appendPlaceholder(String current, String field, boolean newline) {
        String token = "{{" + field + "}}";
        String cur = current == null ? "" : current;
        String spacer = newline && !cur.isEmpty() ? "\n" : (!cur.isEmpty() && !cur.endsWith(" ") && !cur.endsWith("\n") ? " " : "");
        return cur + spacer + token;
    }

    /** template_test_sender sample context. */
    static JSONObject sampleContext() {
        JSONObject s = new JSONObject();
        try {
            s.put("document_no", "TEST-0001").put("document_type", "QCMS TEMPLATE TEST").put("part_number", "TEST-PART")
                .put("fsi_part_number", "FSI-TEST").put("part_description", "Template test record").put("heat_number", "TEST-HEAT")
                .put("supplier_name", "Test Supplier").put("customer_name", "Test Customer").put("due_date", "DD-MM-YYYY")
                .put("next_stage", "Template Test / Next Stage").put("department", "Test Department").put("report_date", "DD-MM-YYYY")
                .put("open_count", 1).put("overdue_count", 0);
        } catch (Exception ignored) { }
        return s;
    }

    // ------------------------------------------------------------------ NotificationService
    static JSONObject route(Api api, String event) throws Exception {
        return AdmDb.first(AdmDb.select(api, "qcms_notification_routes", AdmDb.eq("event_key", event.toUpperCase(Locale.ROOT), "enabled", true), null, 1));
    }

    static JSONObject template(Api api, String templateKey, String event) {
        String key = (templateKey == null || templateKey.trim().isEmpty() ? (event == null ? "" : event) : templateKey).trim().toUpperCase(Locale.ROOT);
        if (key.isEmpty()) return null;
        try { return AdmDb.first(AdmDb.select(api, "qcms_email_templates", AdmDb.eq("template_key", key, "enabled", true), null, 1)); }
        catch (Exception e) { return null; }
    }

    /** department_emails. */
    static List<String> departmentEmails(Api api, String department, String exclude) throws Exception {
        String target = AdmPy.normDept(department);
        List<String> result = new ArrayList<>();
        if (target.isEmpty()) return result;
        String ex = AdmPy.fold(exclude == null ? "" : exclude);
        for (JSONObject row : AdmDb.list(AdmDb.select(api, "employees", AdmDb.eq("status", "ACTIVE"), "first_name.asc", 5000))) {
            if (!AdmPy.normDept(AdmPy.j(row, "department")).equals(target)) continue;
            String email = AdmPy.j(row, "email").trim();
            if (email.isEmpty() || AdmPy.fold(email).equals(ex)) continue;
            boolean dup = false;
            for (String x : result) if (AdmPy.fold(x).equals(AdmPy.fold(email))) { dup = true; break; }
            if (!dup) result.add(email);
        }
        return result;
    }

    static Map<String, Object> map(JSONObject o) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (Iterator<String> it = o.keys(); it.hasNext(); ) { String k = it.next(); m.put(k, o.opt(k)); }
        return m;
    }

    static String defaultSubject(String event) {
        return "QCMS · " + AdmPy.title(event.replace('_', ' '));
    }

    /** Subject the template test shows before sending (NotificationService.preview subject). */
    static String previewSubject(Api api, String event, JSONObject context) throws Exception {
        JSONObject r = route(api, event);
        JSONObject t = template(api, r == null ? null : AdmPy.j(r, "template_key"), event);
        JSONObject enriched = new JSONObject(context.toString());
        if (!enriched.has("event_key")) enriched.put("event_key", event);
        if (!enriched.has("next_stage")) enriched.put("next_stage", r != null && !AdmPy.j(r, "next_stage").isEmpty() ? AdmPy.j(r, "next_stage") : "Next QCMS stage");
        if (!enriched.has("department")) enriched.put("department", r == null ? "" : AdmPy.j(r, "department"));
        String subjectTemplate = t != null && !AdmPy.j(t, "subject_template").isEmpty() ? AdmPy.j(t, "subject_template") : (r == null ? "" : AdmPy.j(r, "subject_template"));
        String subject = subjectTemplate.isEmpty() ? defaultSubject(event) : AdmPy.templateText(subjectTemplate, map(enriched));
        // R39 (web R38): the subject starts with the related department instead of "QCMS"
        return SndMail.departmentSubject(subject, AdmPy.j(enriched, "department"), event);
    }

    /**
     * NotificationService.enqueue with an explicit recipient, no related record and no supplier copy
     * (the only way the Email Settings page calls it). Returns the outbox row or null when nothing was queued.
     */
    static JSONObject enqueue(Api api, String eventKey, String subject, String bodyText, String recipientEmail, String recipientName,
                              List<String> ccEmails, String templateKey, JSONObject context) throws Exception {
        String event = eventKey == null ? "" : eventKey.trim().toUpperCase(Locale.ROOT);
        if (event.isEmpty()) return null;
        JSONObject r = route(api, event);
        JSONObject t = template(api, templateKey != null && !templateKey.isEmpty() ? templateKey : (r == null ? null : AdmPy.j(r, "template_key")), event);
        String email = recipientEmail == null ? "" : recipientEmail.trim();
        if (r == null && email.isEmpty()) return null;
        if (email.isEmpty()) return null;
        JSONObject enriched = context == null ? new JSONObject() : new JSONObject(context.toString());
        if (!enriched.has("event_key")) enriched.put("event_key", event);
        if (!enriched.has("next_stage")) {
            String ns = r == null ? "" : AdmPy.j(r, "next_stage");
            if (ns.isEmpty()) ns = AdmPy.j(enriched, "next_task");
            enriched.put("next_stage", ns.isEmpty() ? "Next QCMS stage" : ns);
        }
        if (!enriched.has("department")) enriched.put("department", r == null ? "" : AdmPy.j(r, "department"));
        String name = recipientName == null ? "" : recipientName.trim();

        String subjectTemplate = t != null && !AdmPy.j(t, "subject_template").isEmpty() ? AdmPy.j(t, "subject_template") : (r == null ? "" : AdmPy.j(r, "subject_template"));
        String bodyTemplate = t == null ? "" : AdmPy.j(t, "body_template");
        String finalSubject = !subjectTemplate.isEmpty() ? AdmPy.templateText(subjectTemplate, map(enriched))
            : (subject == null || subject.isEmpty() ? defaultSubject(event) : subject).trim();
        // R39 (web R38 NotificationService.enqueue): department first in the subject (context / route department, else event key)
        finalSubject = SndMail.departmentSubject(finalSubject, AdmPy.j(enriched, "department"), event);
        String finalBody = !bodyTemplate.isEmpty() ? AdmPy.templateText(bodyTemplate, map(enriched)) : (bodyText == null ? "" : bodyText.trim());
        if (finalBody.isEmpty()) {
            String doc = AdmPy.j(enriched, "document_no"), ns = AdmPy.j(enriched, "next_stage");
            finalBody = "QCMS workflow notification\nDocument: " + (doc.isEmpty() ? "-" : doc) + "\nNext stage: " + (ns.isEmpty() ? "-" : ns);
        }
        List<String> cc = new ArrayList<>();
        if (ccEmails != null) for (String c : ccEmails) if (c != null && !c.trim().isEmpty()) cc.add(c.trim());
        if (r != null && AdmPy.truthy(r, "department_cc")) cc.addAll(departmentEmails(api, AdmPy.j(r, "department"), email));
        JSONArray finalCc = new JSONArray();
        List<String> seen = new ArrayList<>();
        for (String v : cc) {
            String f = AdmPy.fold(v);
            if (!v.isEmpty() && !f.equals(AdmPy.fold(email)) && !seen.contains(f)) { seen.add(f); finalCc.put(v); }
        }
        StringBuilder html = new StringBuilder();
        String[] lines = finalBody.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").split("\r\n|\n|\r", -1);
        for (int i = 0; i < lines.length; i++) { if (i > 0) html.append("<br>"); html.append(lines[i]); }
        String tk = t != null && !AdmPy.j(t, "template_key").isEmpty() ? AdmPy.j(t, "template_key") : (templateKey != null && !templateKey.isEmpty() ? templateKey : event);
        JSONObject payload = new JSONObject();
        payload.put("event_key", event);
        payload.put("recipient_email", email);
        payload.put("recipient_name", name.isEmpty() ? JSONObject.NULL : name);
        payload.put("cc_emails", finalCc);
        payload.put("subject", finalSubject);
        payload.put("body_text", finalBody);
        payload.put("body_html", html.toString());
        payload.put("related_table", JSONObject.NULL);
        payload.put("related_id", JSONObject.NULL);
        payload.put("context", enriched);
        payload.put("template_key", tk.toUpperCase(Locale.ROOT));
        payload.put("attachment_manifest", new JSONArray());
        payload.put("dedupe_key", JSONObject.NULL);
        payload.put("is_automatic", false);
        payload.put("status", "PENDING");
        return api.insert("qcms_notification_outbox", payload);
    }

    /** NotificationService.dispatch: {"processed": n, ...} or {"error": text} (never throws). */
    static JSONObject dispatch(Api api, List<String> outboxIds) {
        try {
            if (outboxIds.isEmpty()) return new JSONObject().put("processed", 0);
            JSONArray ids = new JSONArray();
            for (String id : outboxIds) ids.put(id);
            String body = api.invokeFunction("qcms-send-email", new JSONObject().put("outbox_ids", ids));
            String b = body == null ? "" : body.trim();
            return b.startsWith("{") ? new JSONObject(b) : new JSONObject().put("result", b);
        } catch (Exception e) {
            JSONObject o = new JSONObject();
            try { o.put("processed", 0).put("error", Api.message(e)); } catch (Exception ignored) { }
            return o;
        }
    }

    /** retry_pending(limit=50): PENDING then FAILED rows (oldest first), first 50. */
    static JSONObject retryPending(Api api) throws Exception {
        List<String> ids = new ArrayList<>();
        for (JSONObject r : AdmDb.list(AdmDb.select(api, "qcms_notification_outbox", AdmDb.eq("status", "PENDING"), "created_at.asc", 50))) ids.add(AdmPy.j(r, "id"));
        for (JSONObject r : AdmDb.list(AdmDb.select(api, "qcms_notification_outbox", AdmDb.eq("status", "FAILED"), "created_at.asc", 50))) ids.add(AdmPy.j(r, "id"));
        return dispatch(api, ids.size() > 50 ? ids.subList(0, 50) : ids);
    }
}
