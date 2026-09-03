import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import nodemailer from "npm:nodemailer@6.9.16";
import * as XLSX from "npm:xlsx@0.18.5";
import { Buffer } from "node:buffer";

const HEADERS = { "Content-Type": "application/json" };
type Row = Record<string, any>;
type DigestRow = { reference:string; part:string; party:string; due_date:string; status:string; quantity:string };
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
function workbook(title:string,reportDate:string,rows:DigestRow[]):Uint8Array {
  const records=rows.map((r,i)=>({
    "Sr No":i+1,"Reference":r.reference,"Part Number":r.part,"Supplier / Customer":r.party,
    "Due Date":r.due_date,"Status":r.status,"Quantity / Balance":r.quantity,
  }));
  const ws=XLSX.utils.json_to_sheet(records.length?records:[{"Sr No":"","Reference":"No records","Part Number":"","Supplier / Customer":"","Due Date":reportDate,"Status":"","Quantity / Balance":""}]);
  ws["!cols"]=[{wch:8},{wch:30},{wch:22},{wch:38},{wch:14},{wch:36},{wch:24}];
  const summary=XLSX.utils.aoa_to_sheet([["FOUR STAR INDUSTRIES PVT. LTD. · QCMS"],[title],[`Report Date: ${reportDate}`],[`Records: ${rows.length}`]]);
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
      out.push({reference:String(r.master_reference_no||r.customer_order_no||"-"),part:String(part.fsi_part_number||part.part_number||"-"),party:String(customer.party_name||customer.party_code||"-"),due_date:due,status:`OVERDUE · ${r.status||"OPEN"}`,quantity:`${n(r.order_qty_pcs)} pcs`});
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
      out.push({reference:String(r.master_reference_no||r.customer_order_no||"-"),part:String(part.fsi_part_number||part.part_number||"-"),party:String(customer.party_name||customer.party_code||"-"),due_date:due||delivery||"-",status:`${due&&due<localDate?"OVERDUE":"PENDING"} · RM PO PENDING · lead ${ld}d`,quantity:`${n(pending)} kg pending`});
    }
  } else if(key==="PO_PENDING_BIENNIAL") {
    const [{data:pos=[]},{data:confirmations=[]}]=await Promise.all([
      admin.from("supply_purchase_orders").select("*").eq("tenant_id",tenantId).limit(10000),
      admin.from("supply_po_confirmations").select("purchase_order_id,confirmation_status").eq("tenant_id",tenantId).limit(10000),
    ]);
    const confirmed=new Map<string,string>(); for(const c of confirmations) confirmed.set(String(c.purchase_order_id),String(c.confirmation_status||""));
    for(const r of pos) {
      const status=String(r.status||"").toUpperCase(); if(["CLOSED","CANCELLED"].includes(status)) continue;
      const supplier=partyMap.get(String(r.supplier_id))||{}, due=String(r.delivery_date||r.order_date||"").slice(0,10);
      let action="OPEN / RECEIPT PENDING";
      if(String(r.approval_status||"").toUpperCase()==="PENDING_APPROVAL") action="PENDING APPROVAL";
      else if(String(confirmed.get(String(r.id))||"").toUpperCase()!=="CONFIRMED") action="SUPPLIER CONFIRMATION PENDING";
      const overdue=Boolean(due)&&due<localDate;
      out.push({reference:String(r.po_number||"-"),part:String(r.po_type||"PURCHASE ORDER").replaceAll("_"," "),party:String(supplier.party_name||supplier.party_code||"-"),due_date:due||"-",status:`${overdue?"OVERDUE · ":""}${action}`,quantity:`${n(r.grand_total)} ${r.currency||""}`.trim()});
    }
  } else if(key==="FORGING_RECEIPT_OVERDUE_BIENNIAL") {
    const [{data:orders=[]},{data:receipts=[]}]=await Promise.all([
      admin.from("supply_forging_orders").select("*").eq("tenant_id",tenantId).limit(10000),
      admin.from("supply_forging_receipts").select("forging_order_id,received_qty_pcs").eq("tenant_id",tenantId).limit(20000),
    ]);
    const received=new Map<string,number>(); for(const rec of receipts) received.set(String(rec.forging_order_id),(received.get(String(rec.forging_order_id))||0)+Number(rec.received_qty_pcs||0));
    for(const r of orders) {
      if(["CLOSED","CANCELLED"].includes(String(r.status||"").toUpperCase())) continue;
      const due=String(r.expected_date||"").slice(0,10); if(!due||due>=localDate) continue;
      const balance=Math.max(Number(r.order_qty_pcs||0)-(received.get(String(r.id))||0),0); if(balance<=0.0001) continue;
      const supplier=partyMap.get(String(r.forging_supplier_id))||{};
      out.push({reference:String(r.supplier_order_no||r.id||"-"),part:"Forging Receipt",party:String(supplier.party_name||supplier.party_code||"-"),due_date:due,status:"OVERDUE · FORGING RECEIPT PENDING",quantity:`${n(balance)} pcs pending`});
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
        const subject=render(String(tpl.subject_template||`QCMS · ${schedule.schedule_label} · {{report_date}}`),ctx), bodyText=render(String(tpl.body_template||"Please find attached the QCMS Excel digest for {{report_date}}."),ctx);
        const bytes=workbook(String(schedule.schedule_label||"QCMS Supply Chain Digest"),clock.date,rows), fileName=`QCMS_${String(schedule.schedule_key)}_${clock.date}.xlsx`;
        for(const recipient of recipients.values()) {
          if(!rows.length) continue; const dedupe=`SUPPLY_DIGEST:${schedule.schedule_key}:${clock.date}:${recipient.email.toLowerCase()}`;
          const {data:existing}=await admin.from("qcms_notification_outbox").select("id").eq("tenant_id",tenantId).eq("dedupe_key",dedupe).maybeSingle(); if(existing?.id) continue;
          const {data:outbox,error:insertErr}=await admin.from("qcms_notification_outbox").insert({tenant_id:tenantId,event_key:schedule.event_key,recipient_email:recipient.email,recipient_name:recipient.name||null,subject,body_text:bodyText,body_html:html(bodyText),context:{...ctx,schedule_key:schedule.schedule_key,record_count:rows.length,attachment_name:fileName,run_every_days:every,export_format:"XLSX"},template_key:schedule.template_key||schedule.event_key,attachment_manifest:[],dedupe_key:dedupe,is_automatic:true,scheduled_for:now.toISOString(),status:"SENDING",attempts:1}).select("id").single(); if(insertErr) throw insertErr;
          try {
            await transporter.sendMail({from:settings.sender_name?`"${String(settings.sender_name).replaceAll('"','')}" <${settings.sender_email}>`:settings.sender_email,to:recipient.name?`"${recipient.name.replaceAll('"','')}" <${recipient.email}>`:recipient.email,replyTo:settings.reply_to||undefined,subject,text:bodyText,html:html(bodyText),attachments:[{filename:fileName,content:Buffer.from(bytes),contentType:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}]});
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
