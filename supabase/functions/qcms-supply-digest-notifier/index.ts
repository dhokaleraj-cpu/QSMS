import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import nodemailer from "npm:nodemailer@6.9.16";
import * as XLSX from "npm:xlsx@0.18.5";
import { Buffer } from "node:buffer";
import { MAX_ATTACHMENT_BYTES, XLSX_MIME, clean, companyName, day, emailShell, htmlTable, poLineRows, poUpdatedAt, pruneColumns, removeGenerated, snapshotAttachments, storeGenerated, textTable, toNumber, type Cell, type Col, type PoLine, type SnapshotCache, type SnapshotRef } from "./reminder_kit.ts";

// R38: e-mail subjects start with the related Department instead of "QCMS" (schedule department -> module department).
const R38_MODULE_DEPARTMENT: Record<string, string> = { SUPPLY_CHAIN: "Supply Chain", OSP_TRANSACTIONS: "Supply Chain", COMPLAINT_MANAGEMENT: "Quality", CALIBRATION_VALIDATION: "Quality", NPD_APQP: "NPD", PPAP: "Quality", RMTC: "Quality", METLAB: "MetLAB", MATERIAL_INWARD: "Stores", STORES: "Stores", PURCHASE: "Purchase", INDIRECT_PURCHASE: "Purchase", ADMIN: "Admin" };
const R38_DEPARTMENT_LABEL: Record<string, string> = { quality: "Quality", metlab: "MetLAB", supplychain: "Supply Chain", purchase: "Purchase", procurement: "Purchase", stores: "Stores", npd: "NPD", rd: "R & D", management: "Management", admin: "Admin", engineering: "Engineering", production: "Production", marketing: "Marketing" };
function r38DepartmentLabel(value: unknown): string {
  const raw = String(value ?? "").trim().replace(/\s+/g, " ");
  const norm = raw.toLowerCase().replace(/[^a-z0-9]+/g, "");
  if (!raw || ["qcmsteam", "qcms", "all", "none"].includes(norm)) return "";
  return R38_DEPARTMENT_LABEL[norm] || raw;
}
function r38ScheduleDepartment(schedule: Record<string, any>): string {
  const many = Array.isArray(schedule?.recipient_departments) ? schedule.recipient_departments : [];
  return r38DepartmentLabel(schedule?.recipient_department) || r38DepartmentLabel(many[0]) || R38_MODULE_DEPARTMENT[String(schedule?.module_key || "").toUpperCase()] || "";
}
function r38DepartmentSubject(subject: string, department: string): string {
  const re = /^\s*(?:STAWN\s+)?QCMS\s*[·:|\-–—]\s*/i;
  const label = r38DepartmentLabel(department);
  if (!label || !subject.trim()) return subject;
  if (re.test(subject)) return `${label} · ${subject.replace(re, "")}`;
  const head = subject.split("·")[0].trim();
  const known = subject.includes("·") && (Object.values(R38_DEPARTMENT_LABEL).includes(head) || Boolean(R38_DEPARTMENT_LABEL[head.toLowerCase().replace(/[^a-z0-9]+/g, "")]));
  return known ? subject : `${label} · ${subject.trim()}`;
}

const HEADERS = { "Content-Type": "application/json" };
type Row = Record<string, any>;
type DigestRow = { reference:string; part:string; party:string; due_date:string; status:string; quantity:string;
  // R36 detail columns (part number, customer, supplier, qty, price, delivery date) + PO PDF snapshot refs
  part_number?:string; part_description?:string; customer?:string; supplier?:string; qty?:number|null; uom?:string; price?:number|null; value?:number|null; currency?:string; delivery_date?:string; details?:string; refs?:SnapshotRef[] };
const DIGEST_HEADERS:Col[]=["Sr No","Reference","Part Number","Description","Customer","Supplier",{label:"Qty",kind:"number"},"UOM",{label:"Price",kind:"money"},{label:"Value",kind:"money"},"Currency",{label:"Due Date",kind:"date"},{label:"Delivery Date",kind:"date"},"Status","Quantity / Balance","Details"];
const DIGEST_KEEP=["Sr No","Reference","Part Number","Due Date","Status"];
function digestTable(rows:DigestRow[]):{headers:Col[];rows:Cell[][]} {
  return pruneColumns(DIGEST_HEADERS,rows.map((r,i)=>[i+1,r.reference,r.part_number||(r.part&&r.part!=="-"?r.part:""),r.part_description,r.customer,r.supplier,r.qty??null,r.uom,r.price??null,r.value??null,r.currency,r.due_date&&r.due_date!=="-"?r.due_date:"",r.delivery_date,r.status,r.quantity,r.details]),DIGEST_KEEP);
}
function joinShort(values:string[],max=3):string {
  const unique=[...new Set(values.map(clean).filter(Boolean))]; return unique.length>max?`${unique.slice(0,max).join(", ")} +${unique.length-max}`:unique.join(", ");
}
const KEYS = [
  "CUSTOMER_ORDER_OVERDUE_BIENNIAL",
  "RM_PENDING_BIENNIAL",
  "PO_PENDING_BIENNIAL",
  "FORGING_RECEIPT_OVERDUE_BIENNIAL",
];

function hex(bytes:ArrayBuffer):string {
  return Array.from(new Uint8Array(bytes)).map((b)=>b.toString(16).padStart(2,"0")).join("");
}
async function sha256(value:string):Promise<string> {
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
}
function localClock(now:Date,timeZone:string):{date:string;hour:number} {
  const parts=new Intl.DateTimeFormat("en-CA",{timeZone,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",hourCycle:"h23"}).formatToParts(now);
  const get=(type:string)=>parts.find((p)=>p.type===type)?.value||"00";
  return {date:`${get("year")}-${get("month")}-${get("day")}`,hour:Number(get("hour"))};
}
function addDays(iso:string,days:number):string {
  const d=new Date(`${iso}T00:00:00Z`); d.setUTCDate(d.getUTCDate()+days); return d.toISOString().slice(0,10);
}
function daysBetween(a:string,b:string):number {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(a)||!/^\d{4}-\d{2}-\d{2}$/.test(b)) return 999999;
  return Math.floor((new Date(`${b}T00:00:00Z`).getTime()-new Date(`${a}T00:00:00Z`).getTime())/86400000);
}
function norm(value:any):string { return String(value||"").toLowerCase().replace(/[^a-z0-9]/g,""); }
function targets(schedule:Row):string[] {
  const values=Array.isArray(schedule.recipient_departments)?schedule.recipient_departments.map((v:any)=>String(v||"").trim()).filter(Boolean):[];
  if(String(schedule.recipient_department||"").trim()) values.push(String(schedule.recipient_department).trim());
  return [...new Set(values.map(norm).filter(Boolean))];
}
function matchesRecipient(target:string,department:any,role:any):boolean {
  const t=norm(target), d=norm(department), r=norm(role);
  if(t && t===d) return true;
  if(t==="marketing") return ["marketing","businessdevelopment","sales"].includes(d)||r==="businessdevelopment";
  if(t==="procurement") return ["procurement","purchasing","purchase"].includes(d)||r==="procurement";
  if(t==="supplychain") return d==="supplychain"||r==="supplychain";
  if(t==="management") return d==="management"||r==="management";
  return false;
}
function render(value:string,ctx:Row):string {
  return String(value||"").replace(/\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g,(_m,key)=>String(ctx[key]??"-"));
}
function n(value:any):string {
  const x=Number(value||0); return Number.isFinite(x)?x.toLocaleString("en-IN",{maximumFractionDigits:3}):"0";
}
function html(value:string):string {
  const safe=String(value||"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
  return `<div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#273444;line-height:1.5">${safe.split("\n").join("<br>")}</div>`;
}
function workbook(title:string,reportDate:string,rows:DigestRow[],company="STAWN QCMS"):Uint8Array {
  const table=digestTable(rows);
  const labels=table.headers.map((h)=>typeof h==="string"?h:h.label);
  const ws=XLSX.utils.aoa_to_sheet([labels,...(table.rows.length?table.rows.map((r)=>r.map((v)=>v??"")):[["","No records"]])]);
  ws["!cols"]=labels.map((l,i)=>({wch:Math.min(48,Math.max(8,l.length+2,...table.rows.map((r)=>String(r[i]??"").length+2)))}));
  if(table.rows.length) ws["!autofilter"]={ref:XLSX.utils.encode_range({s:{r:0,c:0},e:{r:table.rows.length,c:labels.length-1}})};
  const summary=XLSX.utils.aoa_to_sheet([[`${company} · STAWN QCMS`],[title],[`Report Date: ${reportDate}`],[`Records: ${rows.length}`]]);
  summary["!cols"]=[{wch:72}];
  const wb=XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb,summary,"Summary"); XLSX.utils.book_append_sheet(wb,ws,"QCMS Digest");
  return new Uint8Array(XLSX.write(wb,{bookType:"xlsx",type:"array"}) as ArrayBuffer);
}

async function gather(admin:any,tenantId:string,key:string,localDate:string,partMap:Map<string,Row>,partyMap:Map<string,Row>):Promise<DigestRow[]> {
  const out:DigestRow[]=[];
  if(key==="CUSTOMER_ORDER_OVERDUE_BIENNIAL") {
    const {data=[]}=await admin.from("supply_customer_orders").select("*").eq("tenant_id",tenantId).limit(10000);
    for(const r of data) {
      if(["COMPLETED","CLOSED","CANCELLED"].includes(String(r.status||"").toUpperCase())) continue;
      const due=String(r.customer_delivery_date||"").slice(0,10); if(!due||due>=localDate) continue;
      const part=partMap.get(String(r.part_id))||{}, customer=partyMap.get(String(r.customer_id))||{};
      out.push({reference:String(r.master_reference_no||r.customer_order_no||"-"),part:String(part.fsi_part_number||part.part_number||"-"),party:String(customer.party_name||customer.party_code||"-"),due_date:due,status:`OVERDUE · ${r.status||"OPEN"}`,quantity:`${n(r.order_qty_pcs)} pcs`,
        part_number:clean(part.part_number)||clean(part.fsi_part_number),part_description:clean(part.part_name),customer:clean(customer.party_name)||clean(customer.party_code),supplier:clean(partyMap.get(String(r.forging_supplier_id||""))?.party_name),qty:toNumber(r.order_qty_pcs),uom:"PCS",delivery_date:due,details:clean(r.customer_order_no)?`Customer order ${clean(r.customer_order_no)}`:""});
    }
  } else if(key==="RM_PENDING_BIENNIAL") {
    const [{data:orders=[]},{data:rmPos=[]}]=await Promise.all([
      admin.from("supply_customer_orders").select("*").eq("tenant_id",tenantId).eq("rm_procurement_required",true).limit(10000),
      admin.from("supply_rm_purchase_orders").select("customer_order_id,ordered_qty_kg,status").eq("tenant_id",tenantId).limit(20000),
    ]);
    const partIds=[...new Set(orders.map((r:Row)=>String(r.part_id||"")).filter(Boolean))];
    const {data:details=[]}=partIds.length?await admin.from("part_raw_material_details").select("part_id,lead_time_days,status").eq("tenant_id",tenantId).eq("status","ACTIVE").in("part_id",partIds).limit(20000):{data:[]};
    const lead=new Map<string,number>(); for(const d of details) lead.set(String(d.part_id),Math.max(lead.get(String(d.part_id))||0,Number(d.lead_time_days||0)));
    const ordered=new Map<string,number>(); for(const po of rmPos) if(String(po.status||"").toUpperCase()!=="CANCELLED") ordered.set(String(po.customer_order_id),(ordered.get(String(po.customer_order_id))||0)+Number(po.ordered_qty_kg||0));
    for(const r of orders) {
      if(["COMPLETED","CLOSED","CANCELLED"].includes(String(r.status||"").toUpperCase())) continue;
      const pending=Math.max(Number(r.required_rm_kg||0)-(ordered.get(String(r.id))||0),0); if(pending<=0.0001) continue;
      const part=partMap.get(String(r.part_id))||{}, customer=partyMap.get(String(r.customer_id))||{}, ld=lead.get(String(r.part_id))||0;
      const delivery=String(r.customer_delivery_date||"").slice(0,10), due=delivery?addDays(delivery,-ld):"";
      out.push({reference:String(r.master_reference_no||r.customer_order_no||"-"),part:String(part.fsi_part_number||part.part_number||"-"),party:String(customer.party_name||customer.party_code||"-"),due_date:due||delivery||"-",status:`${due&&due<localDate?"OVERDUE":"PENDING"} · RM PO PENDING · lead ${ld}d`,quantity:`${n(pending)} kg pending`,
        part_number:clean(part.part_number)||clean(part.fsi_part_number),part_description:clean(part.part_name),customer:clean(customer.party_name)||clean(customer.party_code),qty:Math.round(pending*1000)/1000,uom:"KG",delivery_date:delivery});
    }
  } else if(key==="PO_PENDING_BIENNIAL") {
    const [{data:pos=[]},{data:confirmations=[]}]=await Promise.all([
      admin.from("supply_purchase_orders").select("*").eq("tenant_id",tenantId).limit(10000),
      admin.from("supply_po_confirmations").select("purchase_order_id,confirmation_status").eq("tenant_id",tenantId).limit(10000),
    ]);
    const confirmed=new Map<string,string>(); for(const c of confirmations) confirmed.set(String(c.purchase_order_id),String(c.confirmation_status||""));
    const lines:PoLine[]=await poLineRows(admin,tenantId,pos.filter((r:Row)=>!["CLOSED","CANCELLED"].includes(String(r.status||"").toUpperCase())).map((r:Row)=>String(r.id)));
    for(const r of pos) {
      const status=String(r.status||"").toUpperCase(); if(["CLOSED","CANCELLED"].includes(status)) continue;
      const supplier=partyMap.get(String(r.supplier_id))||{}, due=String(r.delivery_date||r.order_date||"").slice(0,10);
      let action="OPEN / RECEIPT PENDING";
      if(String(r.approval_status||"").toUpperCase()==="PENDING_APPROVAL") action="PENDING APPROVAL";
      else if(String(confirmed.get(String(r.id))||"").toUpperCase()!=="CONFIRMED") action="SUPPLIER CONFIRMATION PENDING";
      const overdue=Boolean(due)&&due<localDate;
      const pl=lines.filter((l)=>l.po_id===String(r.id)), uoms=[...new Set(pl.map((l)=>l.uom).filter(Boolean))];
      out.push({reference:String(r.po_number||"-"),part:String(r.po_type||"PURCHASE ORDER").replaceAll("_"," "),party:String(supplier.party_name||supplier.party_code||"-"),due_date:due||"-",status:`${overdue?"OVERDUE · ":""}${action}`,quantity:`${n(r.grand_total)} ${r.currency||""}`.trim(),
        part_number:joinShort(pl.map((l)=>l.part_number||l.fsi_part_number)),part_description:joinShort(pl.map((l)=>l.description||l.material),2),customer:joinShort(pl.map((l)=>l.customer)),supplier:clean(supplier.party_name)||clean(supplier.party_code),
        qty:pl.length&&uoms.length<=1?pl.reduce((s,l)=>s+(l.qty||0),0):null,uom:uoms.length===1?uoms[0]:"",price:pl.length===1?pl[0].unit_price:null,value:toNumber(r.subtotal)??(pl.length?pl.reduce((s,l)=>s+(l.line_value||0),0):null),currency:clean(r.currency),
        delivery_date:day(r.delivery_date),details:`${String(r.po_type||"PURCHASE ORDER").replaceAll("_"," ")} · grand total ${n(r.grand_total)} ${clean(r.currency)}`.trim(),
        refs:[{source_table:"supply_purchase_orders",record_id:String(r.id),updated_at:poUpdatedAt(pl,String(r.id),String(r.updated_at||""))}]});
    }
  } else if(key==="FORGING_RECEIPT_OVERDUE_BIENNIAL") {
    const [{data:orders=[]},{data:receipts=[]}]=await Promise.all([
      admin.from("supply_forging_orders").select("*").eq("tenant_id",tenantId).limit(10000),
      admin.from("supply_forging_receipts").select("forging_order_id,received_qty_pcs").eq("tenant_id",tenantId).limit(20000),
    ]);
    const fLines:PoLine[]=await poLineRows(admin,tenantId,orders.filter((r:Row)=>!["CLOSED","CANCELLED"].includes(String(r.status||"").toUpperCase())&&r.purchase_order_id).map((r:Row)=>String(r.purchase_order_id)));
    const received=new Map<string,number>(); for(const rec of receipts) received.set(String(rec.forging_order_id),(received.get(String(rec.forging_order_id))||0)+Number(rec.received_qty_pcs||0));
    for(const r of orders) {
      if(["CLOSED","CANCELLED"].includes(String(r.status||"").toUpperCase())) continue;
      const due=String(r.expected_date||"").slice(0,10); if(!due||due>=localDate) continue;
      const balance=Math.max(Number(r.order_qty_pcs||0)-(received.get(String(r.id))||0),0); if(balance<=0.0001) continue;
      const supplier=partyMap.get(String(r.forging_supplier_id))||{};
      const line=fLines.find((l)=>l.item_id===String(r.purchase_order_item_id||""))||fLines.find((l)=>l.po_id===String(r.purchase_order_id||""));
      out.push({reference:String(r.supplier_order_no||r.id||"-"),part:"Forging Receipt",party:String(supplier.party_name||supplier.party_code||"-"),due_date:due,status:"OVERDUE · FORGING RECEIPT PENDING",quantity:`${n(balance)} pcs pending`,
        part_number:clean(line?.part_number)||clean(line?.fsi_part_number),part_description:clean(line?.description),customer:clean(line?.customer),supplier:clean(supplier.party_name)||clean(supplier.party_code),qty:balance,uom:"PCS",
        price:line?.unit_price??null,value:line?.unit_price!=null?Math.round(balance*line.unit_price*100)/100:null,currency:clean(line?.currency),delivery_date:due,details:[line?.po_number?`PO ${line.po_number}`:"",`ordered ${n(r.order_qty_pcs)} pcs`].filter(Boolean).join(" · "),
        refs:r.purchase_order_id?[{source_table:"supply_purchase_orders",record_id:String(r.purchase_order_id),updated_at:line?poUpdatedAt(fLines,String(r.purchase_order_id)):""}]:[]});
    }
  }
  return out;
}

Deno.serve(async(req:Request)=>{
  try {
    if(req.method!=="POST") return new Response(JSON.stringify({error:"POST required"}),{status:405,headers:HEADERS});
    const schedulerToken=req.headers.get("X-QCMS-Scheduler")||""; if(!schedulerToken) return new Response(JSON.stringify({error:"Scheduler token required"}),{status:401,headers:HEADERS});
    const url=Deno.env.get("SUPABASE_URL")||"", serviceKey=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||""; if(!url||!serviceKey) throw new Error("Supabase function secrets are unavailable");
    const admin=createClient(url,serviceKey,{auth:{autoRefreshToken:false,persistSession:false}});
    const tokenHash=await sha256(schedulerToken); const {data:configs=[],error:cfgErr}=await admin.from("qcms_notification_scheduler_config").select("tenant_id,scheduler_token_hash"); if(cfgErr) throw cfgErr;
    const tenantIds=configs.filter((r:Row)=>String(r.scheduler_token_hash)===tokenHash).map((r:Row)=>String(r.tenant_id)); if(!tenantIds.length) return new Response(JSON.stringify({error:"Invalid scheduler token"}),{status:401,headers:HEADERS});
    let sent=0,failed=0,processed=0,rowsGenerated=0; const now=new Date();
    for(const tenantId of tenantIds) {
      const [{data:settings},{data:schedules=[]},{data:parts=[]},{data:parties=[]},{data:employees=[]},{data:profiles=[]},{data:templates=[]}]=await Promise.all([
        admin.from("qcms_email_settings").select("*").eq("tenant_id",tenantId).maybeSingle(),
        admin.from("qcms_notification_schedules").select("*").eq("tenant_id",tenantId).eq("enabled",true).in("schedule_key",KEYS).limit(20),
        admin.from("parts").select("id,part_number,fsi_part_number,part_name").eq("tenant_id",tenantId).limit(10000),
        admin.from("parties").select("id,party_code,party_name").eq("tenant_id",tenantId).limit(10000),
        admin.from("employees").select("id,profile_id,first_name,last_name,email,department,status").eq("tenant_id",tenantId).eq("status","ACTIVE").limit(10000),
        admin.from("profiles").select("id,role,status").eq("tenant_id",tenantId).eq("status","ACTIVE").limit(10000),
        admin.from("qcms_email_templates").select("*").eq("tenant_id",tenantId).eq("enabled",true).limit(1000),
      ]);
      if(!settings?.enabled||!settings?.smtp_host||!settings?.sender_email) continue;
      const transporter=nodemailer.createTransport({host:settings.smtp_host,port:Number(settings.smtp_port||587),secure:Boolean(settings.use_ssl),requireTLS:Boolean(settings.use_tls)&&!Boolean(settings.use_ssl),auth:settings.smtp_username?{user:settings.smtp_username,pass:settings.smtp_password||""}:undefined,connectionTimeout:Number(settings.timeout_seconds||20)*1000,greetingTimeout:Number(settings.timeout_seconds||20)*1000,socketTimeout:Number(settings.timeout_seconds||20)*1000});
      const company=await companyName(admin,tenantId,settings); const snapCache:SnapshotCache=new Map();
      const partMap=new Map<string,Row>(parts.map((r:Row)=>[String(r.id),r])), partyMap=new Map<string,Row>(parties.map((r:Row)=>[String(r.id),r])), profileMap=new Map<string,Row>(profiles.map((r:Row)=>[String(r.id),r])), templateMap=new Map<string,Row>(templates.map((r:Row)=>[String(r.template_key),r]));
      for(const schedule of schedules) {
        const clock=localClock(now,String(schedule.timezone||"Asia/Kolkata")); if(clock.hour!==Number(schedule.hour_local??8)) continue;
        const every=Math.max(1,Number(schedule.run_every_days||2));
        const {data:state}=await admin.from("qcms_supply_digest_state").select("last_run_local_date").eq("tenant_id",tenantId).eq("schedule_key",schedule.schedule_key).maybeSingle();
        const last=String(state?.last_run_local_date||"").slice(0,10); if(last&&daysBetween(last,clock.date)<every) continue;
        const rows=await gather(admin,tenantId,String(schedule.schedule_key),clock.date,partMap,partyMap); rowsGenerated+=rows.length; processed+=1;
        const wanted=targets(schedule), recipients=new Map<string,{email:string;name:string}>();
        for(const emp of employees) {
          const role=profileMap.get(String(emp.profile_id||""))?.role;
          if(emp.email&&wanted.some((target)=>matchesRecipient(target,emp.department,role))) recipients.set(String(emp.email).toLowerCase(),{email:String(emp.email),name:`${emp.first_name||""} ${emp.last_name||""}`.trim()});
        }
        const tpl=templateMap.get(String(schedule.template_key||schedule.event_key))||{}, overdue=rows.filter((r)=>r.status.startsWith("OVERDUE")).length;
        const ctx={report_date:clock.date,open_count:rows.length-overdue,overdue_count:overdue,department:schedule.recipient_department||"QCMS Team"};
        const subject=r38DepartmentSubject(render(String(tpl.subject_template||`QCMS · ${schedule.schedule_label} · {{report_date}}`),ctx),r38ScheduleDepartment(schedule)||"Supply Chain"), bodyText=render(String(tpl.body_template||"Please find attached the QCMS Excel digest for {{report_date}}."),ctx);
        const bytes=workbook(String(schedule.schedule_label||"QCMS Supply Chain Digest"),clock.date,rows,company), fileName=`QCMS_${String(schedule.schedule_key)}_${clock.date}.xlsx`;
        // R36: same rows as an HTML table in the body (part number, customer, supplier, qty, price, delivery date) + PO PDFs (overdue first, max 10).
        const table=digestTable(rows);
        const bodyHtml=emailShell({title:String(schedule.schedule_label||"QCMS Supply Chain Digest"),company,intro:[...bodyText.split("\n"),"",`Report date: ${clock.date} · ${rows.length} record(s) · overdue ${overdue}`],sections:[htmlTable(table.headers,table.rows,{caption:`${String(schedule.schedule_label||"QCMS Supply Chain Digest")} · ${rows.length} record(s)`})]});
        const fullText=`${bodyText}\n\n${textTable(table.headers,table.rows)}`;
        const refs=[...rows.filter((r)=>r.status.startsWith("OVERDUE")),...rows.filter((r)=>!r.status.startsWith("OVERDUE"))].flatMap((r)=>r.refs||[]);
        for(const recipient of recipients.values()) {
          if(!rows.length) continue; const dedupe=`SUPPLY_DIGEST:${schedule.schedule_key}:${clock.date}:${recipient.email.toLowerCase()}`;
          const {data:existing}=await admin.from("qcms_notification_outbox").select("id").eq("tenant_id",tenantId).eq("dedupe_key",dedupe).maybeSingle(); if(existing?.id) continue;
          const snaps=await snapshotAttachments(admin,tenantId,refs,10,MAX_ATTACHMENT_BYTES-bytes.byteLength,snapCache);
          const excelEntry=await storeGenerated(admin,tenantId,`SUPPLY_DIGEST_${schedule.schedule_key}`,{filename:fileName,contentType:XLSX_MIME,bytes});
          const manifest=[...(excelEntry?[excelEntry]:[]),...snaps.manifest];
          const {data:outbox,error:insertErr}=await admin.from("qcms_notification_outbox").insert({tenant_id:tenantId,event_key:schedule.event_key,recipient_email:recipient.email,recipient_name:recipient.name||null,subject,body_text:fullText,body_html:bodyHtml,context:{...ctx,schedule_key:schedule.schedule_key,record_count:rows.length,attachment_name:fileName,run_every_days:every,export_format:"XLSX",attachments:[fileName,...snaps.attachments.map((a)=>a.filename)]},template_key:schedule.template_key||schedule.event_key,attachment_manifest:manifest,dedupe_key:dedupe,is_automatic:true,scheduled_for:now.toISOString(),status:"SENDING",attempts:1}).select("id").single(); if(insertErr){await removeGenerated(admin,manifest);throw insertErr;}
          try {
            await transporter.sendMail({from:settings.sender_name?`"${String(settings.sender_name).replaceAll('"','')}" <${settings.sender_email}>`:settings.sender_email,to:recipient.name?`"${recipient.name.replaceAll('"','')}" <${recipient.email}>`:recipient.email,replyTo:settings.reply_to||undefined,subject,text:fullText,html:bodyHtml,attachments:[{filename:fileName,content:Buffer.from(bytes),contentType:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},...snaps.attachments]});
            await removeGenerated(admin,manifest);
            await admin.from("qcms_notification_outbox").update({status:"SENT",sent_at:new Date().toISOString(),last_error:null,updated_at:new Date().toISOString()}).eq("id",outbox.id); sent+=1;
          } catch(error) {
            const message=error instanceof Error?error.message:String(error); await admin.from("qcms_notification_outbox").update({status:"FAILED",last_error:message.slice(0,2000),updated_at:new Date().toISOString()}).eq("id",outbox.id); failed+=1;
          }
        }
        await admin.from("qcms_supply_digest_state").upsert({tenant_id:tenantId,schedule_key:schedule.schedule_key,last_run_local_date:clock.date,last_run_at:new Date().toISOString(),updated_at:new Date().toISOString()},{onConflict:"tenant_id,schedule_key"});
      }
    }
    return new Response(JSON.stringify({processed_schedules:processed,report_rows:rowsGenerated,sent,failed}),{headers:HEADERS});
  } catch(error) {
    const message=error instanceof Error?error.message:String(error); return new Response(JSON.stringify({error:message}),{status:500,headers:HEADERS});
  }
});
