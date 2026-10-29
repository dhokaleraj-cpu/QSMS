package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.util.List;

/** Supply Chain modules (Supply tab) - native editors port core/supply_chain_service.py. */
public final class CatSupply {
    private CatSupply() { }

    private static final String ORDERS = "Orders", PROC = "Procurement & receipts", PROD = "Production & dispatch", TRACE = "Traceability";

    public static void register(List<Module> list) {
        int T = Catalog.SUPPLY;

        // 1. Customer Orders / Schedules
        list.add(new Module("customer_orders", "Customer Orders / Schedules", T, ORDERS, "supply_customer_orders")
            .desc("Customer POs and six-month schedules with supply flow and RM procurement decision")
            .titleField("master_reference_no").status("status")
            .col("master_reference_no", "Customer Ref").col("order_position", "Pos").col("order_type", "Type").col("customer_id", "Customer").col("part_id", "Part")
            .col("supply_flow", "Supply Flow").col("order_qty_pcs", "Qty pcs").col("required_rm_kg", "RM kg").col("procurement_decision", "Procurement")
            .col("customer_delivery_date", "Delivery").col("status", "Status")
            .statuses("OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED")
            .child("RM Purchase Orders", "supply_rm_purchase_orders", "customer_order_id", "created_at.asc", new String[][]{{"supplier_order_no", "PO No."}, {"rm_supplier_id", "Supplier"}, {"ordered_qty_kg", "Ordered kg"}, {"expected_date", "Expected"}, {"status", "Status"}})
            .child("RM Receipts", "supply_rm_receipts", "customer_order_id", "created_at.asc", new String[][]{{"receipt_number", "Material Inward"}, {"receipt_date", "Date"}, {"heat_number", "Heat"}, {"received_qty_kg", "Received kg"}, {"rmtc_number", "RMTC"}})
            .child("RM to Forging", "supply_rm_dispatches", "customer_order_id", "created_at.asc", new String[][]{{"dispatch_number", "Dispatch No."}, {"dispatch_date", "Date"}, {"forging_supplier_id", "Forger"}, {"heat_number", "Heat"}, {"qty_kg", "Qty kg"}})
            .child("Forging Orders", "supply_forging_orders", "customer_order_id", "created_at.asc", new String[][]{{"supplier_order_no", "Order No."}, {"forging_supplier_id", "Forger"}, {"order_qty_pcs", "Qty pcs"}, {"expected_date", "Expected"}, {"status", "Status"}})
            .child("Forging Receipts", "supply_forging_receipts", "customer_order_id", "created_at.asc", new String[][]{{"receipt_number", "Receipt No."}, {"receipt_date", "Date"}, {"received_qty_pcs", "Received pcs"}, {"rejected_qty_pcs", "Rejected"}, {"heat_number", "Heat"}})
            .child("Production / Dispatch", "supply_downstream_events", "customer_order_id", "created_at.asc", new String[][]{{"event_type", "Stage"}, {"reference_no", "Reference"}, {"event_date", "Date"}, {"qty_pcs", "Qty pcs"}, {"invoice_no", "Invoice"}})
            .attach("SUPPLY_CUSTOMER_ORDER", "supply_customer_orders").slots("CUSTOMER_ORDER_ATTACHMENT")
            .action("Track all stages", "", (a, row, refresh) -> a.push(new OrderTrackerScreen(a, Lookups.j(row, "id"),
                Lookups.j(row, "master_reference_no") + " · Pos " + (Lookups.j(row, "order_position").isEmpty() ? "-" : Lookups.j(row, "order_position")))))
            .action("Create Purchase Order from this order", "status=OPEN|IN_PROGRESS", (a, row, refresh) -> a.push(new SupPoScreen(a, row)))
            .editor((a, id, prefill) -> new SupOrderScreen(a, id, prefill)));

        // 2. PO approval list
        list.add(new Module("po_approval", "Purchase Order Approval", T, ORDERS, "supply_purchase_orders")
            .desc("Pending / approved / cancelled POs · swipe to approve").custom(OrdersScreen::new));

        // 3. Purchase Orders
        list.add(new Module("purchase_orders", "Purchase Orders", T, ORDERS, "supply_purchase_orders")
            .desc("Controlled Raw Material / Forging supplier POs").titleField("po_number").status("status")
            .col("po_number", "PO No.").col("po_type", "Type").col("supplier_id", "Supplier").col("order_date", "PO Date").col("delivery_date", "Delivery")
            .col("grand_total", "Grand Total", "money").col("approval_status", "Approval").col("status", "Status")
            .statuses("PENDING_APPROVAL", "OPEN", "PARTIAL", "CLOSED", "CANCELLED")
            .child("PO Items", "supply_purchase_order_items", "purchase_order_id", "created_at.asc", new String[][]{{"item_no", "Item"}, {"item_description", "Description"}, {"hsn_sac_code", "HSN"}, {"quantity", "Qty"}, {"uom", "UOM"}, {"unit_price", "Price"}, {"line_total", "Line Total"}})
            .child("Customer Order sources", "supply_purchase_order_sources", "purchase_order_id", "created_at.asc", new String[][]{{"customer_order_id", "Customer Order"}, {"allocated_qty", "Allocated"}, {"allocation_uom", "UOM"}})
            .child("RM PO stages", "supply_rm_purchase_orders", "purchase_order_id", "created_at.asc", new String[][]{{"customer_order_id", "Customer Order"}, {"ordered_qty_kg", "Ordered kg"}, {"status", "Status"}})
            .child("Forging PO stages", "supply_forging_orders", "purchase_order_id", "created_at.asc", new String[][]{{"customer_order_id", "Customer Order"}, {"order_qty_pcs", "Qty pcs"}, {"heat_number", "Heat"}, {"status", "Status"}})
            .action("Preview / approve / cancel", "", (a, row, refresh) -> a.push(new PoDetailScreen(a, Lookups.j(row, "id"))))
            .action("Supplier confirmation", "approval_status=APPROVED;status!=CANCELLED", (a, row, refresh) -> a.push(new SupConfirmScreen(a, Lookups.j(row, "id"))))
            // R39 (web R37b): controlled amendment - Amendment No. / Date / Effective Date, latest price, price history, back to approval
            .action("Amend PO (price / qty from an Effective Date)", "status!=CANCELLED", (a, row, refresh) -> a.push(new SupPoAmendScreen(a, Lookups.j(row, "id"))))
            .child("Amendments", "supply_po_amendments", "purchase_order_id", "amendment_no.asc", new String[][]{{"amendment_no", "Amd No."}, {"amendment_date", "Amendment Date"}, {"effective_date", "Effective Date"}, {"reason", "Reason"}, {"status", "Status"}})
            .editor((a, id, prefill) -> id == null ? new SupPoScreen(a, prefill) : new SupPoEditScreen(a, id)));

        // 4. Supplier PO confirmations
        list.add(new Module("po_confirmations", "Supplier PO Confirmations", T, ORDERS, "supply_po_confirmations")
            .desc("Supplier acknowledgement of approved POs").titleField("confirmation_reference").status("confirmation_status").order("updated_at.desc")
            .col("purchase_order_id", "Purchase Order").col("supplier_id", "Supplier").col("confirmation_status", "Status").col("requested_at", "Requested")
            .col("confirmation_reference", "Reference").col("confirmation_date", "Confirmed").col("confirmed_delivery_date", "Confirmed Delivery")
            .col("reminder_count", "Reminders").col("last_reminder_at", "Last Reminder")
            .statuses("PENDING", "CONFIRMED")
            .attach("PO_CONFIRMATION", "supply-po-confirmation").slots("SUPPLIER_PO_CONFIRMATION")
            .action("Record supplier confirmation", "confirmation_status!=CONFIRMED", (a, row, refresh) -> a.push(new SupConfirmScreen(a, Lookups.j(row, "purchase_order_id"))))
            .action("Reminder sent", "confirmation_status!=CONFIRMED", (a, row, refresh) -> SupConfirmScreen.reminder(a, row, refresh))
            .readOnly());

        // 5. RM PO stages (read only)
        list.add(new Module("rm_po_stages", "Raw Material Orders", T, PROC, "supply_rm_purchase_orders")
            .desc("RM Procurement register per Customer Order (created by RM POs)").titleField("supplier_order_no").status("status")
            .col("supplier_order_no", "PO No.").col("customer_order_id", "Customer Order").col("rm_supplier_id", "RM Supplier").col("order_date", "Order Date")
            .col("ordered_qty_kg", "Ordered kg").col("expected_date", "Expected").col("status", "Status")
            .statuses("PENDING_APPROVAL", "OPEN", "PART_RECEIVED", "CLOSED", "CANCELLED")
            .child("RM Receipts", "supply_rm_receipts", "rm_purchase_order_id", "created_at.asc", new String[][]{{"receipt_number", "Material Inward"}, {"receipt_date", "Date"}, {"heat_number", "Heat"}, {"received_qty_kg", "Received kg"}})
            .noEdit());

        // 6. RM receipts (Material Inward link)
        list.add(new Module("rm_receipts", "RM Receipt · Material Inward Link", T, PROC, "supply_rm_receipts")
            .desc("Link Material Inward to a confirmed RM Purchase Order").titleField("receipt_number").status("")
            .col("receipt_number", "Material Inward").col("receipt_date", "Inward Date").col("customer_order_id", "Customer Order").col("rm_purchase_order_id", "RM PO")
            .col("heat_number", "Heat").col("heat_code", "Heat Code").col("rmtc_number", "RMTC").col("rmtc_qty_kg", "RMTC kg").col("received_qty_kg", "Received kg").col("supplier_challan", "GRN / Challan")
            .editor((a, id, prefill) -> new SupStageScreen(a, SupStageScreen.LINK, id)));

        // 7. RM dispatch to forger
        list.add(new Module("rm_dispatches", "RM to Forging", T, PROC, "supply_rm_dispatches")
            .desc("Dispatch received RM to the forging supplier with Heat traceability").titleField("dispatch_number").status("")
            .col("dispatch_number", "Dispatch No.").col("dispatch_date", "Date").col("customer_order_id", "Customer Order").col("forging_supplier_id", "Forging Supplier")
            .col("heat_number", "Heat").col("heat_code", "Heat Code").col("qty_kg", "Qty kg").col("challan_number", "Challan").col("vehicle_number", "Vehicle")
            .editor((a, id, prefill) -> new SupStageScreen(a, SupStageScreen.DISPATCH, id)));

        // 8. Forging orders
        list.add(new Module("forging_orders", "Forging Orders", T, PROC, "supply_forging_orders")
            .desc("Forging supplier orders · Flow 1 (RM dispatch) and Flow 2 (direct)").titleField("supplier_order_no").status("status")
            .col("supplier_order_no", "Order No.").col("customer_order_id", "Customer Order").col("forging_supplier_id", "Forging Supplier").col("order_date", "Order Date")
            .col("order_qty_pcs", "Qty pcs").col("required_rm_kg", "RM kg").col("expected_date", "Expected").col("heat_number", "Heat").col("status", "Status")
            .statuses("PENDING_APPROVAL", "OPEN", "PART_RECEIVED", "CLOSED", "CANCELLED")
            .child("Forging Receipts", "supply_forging_receipts", "forging_order_id", "created_at.asc", new String[][]{{"receipt_number", "Receipt No."}, {"receipt_date", "Date"}, {"received_qty_pcs", "Received pcs"}, {"rejected_qty_pcs", "Rejected"}})
            .editor((a, id, prefill) -> new SupStageScreen(a, SupStageScreen.FORGING_ORDER, id)));

        // 9. Forging receipts
        list.add(new Module("forging_receipts", "Forging Receipts", T, PROC, "supply_forging_receipts")
            .desc("Forgings received against confirmed forging orders").titleField("receipt_number").status("")
            .col("receipt_number", "Receipt No.").col("receipt_date", "Date").col("customer_order_id", "Customer Order").col("forging_supplier_id", "Forging Supplier")
            .col("received_qty_pcs", "Received pcs").col("rejected_qty_pcs", "Rejected pcs").col("actual_rm_consumed_kg", "RM Consumed kg").col("heat_number", "Heat").col("heat_code", "Heat Code")
            .editor((a, id, prefill) -> new SupStageScreen(a, SupStageScreen.FORGING_RECEIPT, id)));

        // 10. Downstream events
        list.add(new Module("downstream_events", "Part Production / Customer Dispatch", T, PROD, "supply_downstream_events")
            .desc("Machining, Finished Goods and Customer Dispatch / Invoice / ASN").titleField("reference_no").status("event_type")
            .col("event_type", "Stage").col("reference_no", "Reference").col("event_date", "Date").col("customer_order_id", "Customer Order")
            .col("qty_pcs", "Qty pcs").col("rejected_qty_pcs", "Rejected").col("heat_number", "Heat").col("invoice_no", "Invoice").col("invoice_date", "Invoice Date").col("asn_no", "ASN")
            .statuses("MACHINING", "FINISHED_GOODS", "CUSTOMER_DISPATCH")
            .editor((a, id, prefill) -> new SupStageScreen(a, SupStageScreen.DOWNSTREAM, id)));

        // 11. Opening stock
        list.add(new Module("opening_stock", "Supply Chain Opening Stock", T, PROD, "supply_opening_stock")
            .desc("Existing stock by Part, stage and location").titleField("lot_reference").status("status")
            .col("part_id", "Part").col("stage", "Stage").col("stock_location", "Location").col("location_party_id", "Lying At").col("material_grade_id", "Grade")
            .col("supplier_id", "Supplier").col("lot_reference", "Opening Reference").col("heat_number", "Heat").col("quantity_pcs", "Opening pcs")
            .col("available_quantity_pcs", "Available pcs").col("quantity_kg", "Opening kg").col("status", "Status")
            .statuses("ACTIVE", "CONSUMED", "INACTIVE")
            .editor((a, id, prefill) -> new SupOpeningScreen(a, id)));

        // 12. Traceability events (summary view)
        list.add(new Module("trace_events", "Traceability Events", T, TRACE, "v_qsms_trace_events")
            .desc("Heat-wise genealogy across inward, production, OSP and dispatch").id("").status("status").order("event_date.desc")
            .col("event_date", "Date").col("event_type", "Event").col("stage_no", "Stage").col("reference", "Reference").col("secondary_reference", "Secondary Ref")
            .col("part_number", "Part").col("heat_number", "Heat").col("heat_code", "Heat Code").col("quantity", "Qty").col("source_name", "Source")
            .col("process_name", "Process").col("result", "Result").col("status", "Status")
            .readOnly().noEdit());

        // R39 · Indirect Purchase (web app_pages/indirect_purchase.py, module key INDIRECT_PURCHASE) - separate from Direct POs
        registerIndirect(list, T);
    }

    static final String INDIRECT = "Indirect Purchase";

    static void registerIndirect(List<Module> list, int T) {
        list.add(new Module("indirect_purchase_orders", "Indirect Purchase Orders", T, INDIRECT, "indirect_purchase_orders")
            .desc("IPO series · approval route · print PDF · e-mail to supplier · cancel")
            .titleField("po_number").custom(IndScreens.PoList::new)
            .editor((a, id, prefill) -> id == null ? new IndScreens.PoEdit(a, null, null) : new IndScreens.PoView(a, id)).readOnly().noEdit());
        list.add(new Module("indirect_po_approval", "Indirect PO Approval", T, INDIRECT, "indirect_purchase_orders")
            .desc("Pending approval worklist · approve / reject with remarks").custom(IndScreens.Approvals::new).readOnly().noEdit());
        list.add(new Module("indirect_requisitions", "Purchase Requisitions", T, INDIRECT, "indirect_purchase_requisitions")
            .desc("New requisition · approve / reject · convert to Indirect PO").titleField("pr_number").custom(IndScreens.Requisitions::new)
            .editor((a, id, prefill) -> new IndScreens.PrEdit(a)).readOnly().noEdit());
        list.add(new Module("indirect_grns", "Indirect Inward (GRN)", T, INDIRECT, "indirect_grns")
            .desc("Goods receipt notes against Indirect PO / petty cash · print · approve GRN without PO")
            .titleField("grn_number").status("status")
            .col("grn_number", "GRN No.").col("grn_date", "GRN Date").col("grn_type", "Type").col("supplier_name", "Supplier").col("supplier_invoice_no", "Invoice")
            .col("challan_no", "Challan").col("department", "Department").col("grand_total", "Grand Total", "money").col("approval_status", "Approval").col("status", "Status")
            .child("GRN lines", "indirect_grn_items", "grn_id", "line_no.asc", new String[][]{{"line_no", "#"}, {"item_name", "Item"}, {"uom", "UOM"}, {"received_qty", "Received"},
                {"accepted_qty", "Accepted"}, {"rejected_qty", "Rejected"}, {"rejection_reason", "Reject Reason"}})
            .action("GRN PDF · View · Download · Print · Share", "", IndScreens::grnPdf)
            .action("Approve GRN (without PO)", "approval_status=PENDING_APPROVAL", (a, row, refresh) -> IndScreens.grnDecide(a, row, refresh, true))
            .action("Reject GRN (without PO)", "approval_status=PENDING_APPROVAL", (a, row, refresh) -> IndScreens.grnDecide(a, row, refresh, false))
            .readOnly().noEdit());
        list.add(new Module("indirect_items", "Indirect Item Master", T, INDIRECT, "indirect_items")
            .desc("Indirect items, categories, UOM, GST %, HSN and last price").titleField("item_code").order("item_code.asc")
            .col("item_code", "Item Code").col("item_name", "Item").col("category", "Category").col("uom", "UOM").col("gst_percent", "GST %").col("hsn_sac", "HSN/SAC")
            .col("last_price", "Last Price").col("status", "Status").statuses("ACTIVE", "INACTIVE").readOnly().noEdit());
        list.add(new Module("indirect_stock", "Indirect Stock Ledger", T, INDIRECT, "indirect_stock_ledger")
            .desc("Receipts (GRN), issues, returns, opening and adjustments with the running balance").order("txn_date.desc")
            .titleField("reference_no").col("txn_date", "Date").col("item_id", "Item").col("txn_type", "Type")
            .col("qty_in", "In").col("qty_out", "Out").col("balance_after", "Balance").col("reference_no", "Reference")
            .col("department", "Department").col("storage_location", "Location").col("remarks", "Remarks")
            .search("reference_no", "department", "remarks").readOnly().noEdit());
    }

    static JSONObject none() { return null; }
}
