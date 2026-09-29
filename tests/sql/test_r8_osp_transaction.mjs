// Run: node tests/sql/test_r8_osp_transaction.mjs /path/to/pglite/dist/index.js
// Uses PostgreSQL/PLpgSQL in isolation and controlled doubles for existing legacy RPCs.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {PGlite}=await import(pathToFileURL(process.argv[2]));
const db=new PGlite();
await db.exec(fs.readFileSync(new URL('r8_osp_fixture.sql',import.meta.url),'utf8'));
await db.exec(fs.readFileSync(new URL('../../supabase/migrations/20260929083249_qcms_r8_multi_heat_osp_material_out.sql',import.meta.url),'utf8'));
await db.exec(fs.readFileSync(new URL('../../supabase/migrations/20260929085020_qcms_r8_osp_archive_lock.sql',import.meta.url),'utf8'));
const id=n=>`00000000-0000-0000-0000-${String(n).padStart(12,'0')}`;
const header={vendor_id:id(60),process_id:id(40),process_specification_id:id(20),dispatch_date:'2026-09-29',expected_return_date:'2026-10-05',dispatch_challan:'CH-ONE',remarks:'Keep heats segregated'};
const lines=[{inward_lot_id:id(51),quantity_dispatched:10,sample_quantity:1},{inward_lot_id:id(52),quantity_dispatched:20,sample_quantity:2}];
const call=async(req,h=header,l=lines)=>(await db.query('select public.qcms_create_osp_material_out($1,$2,$3) result',[req,JSON.stringify(h),JSON.stringify(l)])).rows[0].result;
const count=async(table)=>(await db.query(`select count(*)::int n from public.${table}`)).rows[0].n;
const balances=async()=>(await db.query('select available::float8 n from public.inward_lots order by id')).rows.map(r=>r.n);
let tests=0;
async function fail(label,fn,pattern){
 await db.exec('begin');
 try {await fn(); await db.exec('set constraints all immediate'); assert.fail(`${label}: unexpectedly succeeded`);} catch(e){assert.match(e.message,pattern);} finally {await db.exec('rollback');}
 tests++; console.log('PASS',label);
}
await db.exec('set role authenticated');
const saved=await call(id(100));
assert.equal(await count('osp_material_outs'),1);assert.equal(await count('osp_jobs'),2);assert.deepEqual(await balances(),[90,180,200,200]);
assert.equal(saved.lines[0].material_out_id,saved.lines[1].material_out_id);
assert.notEqual(saved.lines[0].osp_batch_id,saved.lines[1].osp_batch_id);
assert.deepEqual(saved.lines.map(r=>r.source_inward_lot_id),[id(51),id(52)]);tests++;console.log('PASS one document two independent heat batches');
assert.equal((await call(id(100))).replayed,true);assert.equal(await count('osp_jobs'),2);tests++;console.log('PASS retry idempotence');
await fail('changed request cannot duplicate',()=>call(id(100),{...header,remarks:'changed'}),/different Material Out/);
await fail('duplicate source rejected',()=>call(id(101),header,[lines[0],lines[0]]),/only once/);
await fail('cross tenant rejected',()=>call(id(102),header,[lines[0],{...lines[1],inward_lot_id:id(53)}]),/selected Part and tenant/);
await fail('mixed parts rejected',()=>call(id(103),header,[lines[0],{...lines[1],inward_lot_id:id(54)}]),/selected Part and tenant/);
await fail('second line failure rolls back first allocation',()=>call(id(104),header,[lines[0],{...lines[1],quantity_dispatched:999}]),/exceeds available/);
assert.deepEqual(await balances(),[90,180,200,200]);assert.equal(await count('osp_material_outs'),1);assert.equal(await count('osp_jobs'),2);
for(const value of [0,-1,'NaN','Infinity']) await fail(`invalid quantity ${value}`,()=>call(id(105),header,[{...lines[0],quantity_dispatched:value}]),/finite positive/);
await fail('sample exceeds its heat quantity',()=>call(id(106),header,[{...lines[0],sample_quantity:11}]),/Sample quantity/);
await fail('two source identities rejected',()=>call(id(107),header,[{...lines[0],opening_stock_id:id(52)}]),/exactly one/);
await fail('missing source identity rejected',()=>call(id(108),header,[{quantity_dispatched:1,sample_quantity:1}]),/exactly one/);
await fail('permission denied',async()=>{await db.exec("select set_config('test.allowed','false',true)");await call(id(109));},/create permission/);
await fail('no session denied',async()=>{await db.exec("select set_config('test.uid','',true)");await call(id(110));},/Authenticated/);
await fail('wrong tenant sees no document',async()=>{await db.exec(`select set_config('test.tenant','${id(99)}',true)`);assert.equal(await count('osp_material_outs'),0);await db.query('select public.qcms_delete_osp_material_out_group($1)',[saved.id]);},/not found/);
const changes=saved.lines.map((r,i)=>({id:r.id,quantity_dispatched:i?25:15}));
await db.query('select public.qcms_update_osp_material_out_group($1,$2,$3)',[saved.id,JSON.stringify({...header,dispatch_challan:'CH-EDIT'}),JSON.stringify(changes)]);
assert.deepEqual(await balances(),[85,175,200,200]);tests++;console.log('PASS atomic grouped edit');
await fail('single line cannot change common header',()=>db.query("update public.osp_jobs set dispatch_challan='BROKEN' where id=$1",[saved.lines[0].id]),/same Part, Vendor/);
await fail('heat line cannot be reassigned',()=>db.query('update public.osp_jobs set source_inward_lot_id=$1 where id=$2',[id(52),saved.lines[0].id]),/cannot be reassigned/);
await db.query('update public.osp_jobs set sample_received_date=current_date where id=$1',[saved.lines[1].id]);
await fail('downstream activity blocks whole group edit',()=>db.query('select public.qcms_update_osp_material_out_group($1,$2,$3)',[saved.id,JSON.stringify(header),JSON.stringify(changes)]),/Downstream/);
await fail('downstream activity blocks whole group delete',()=>db.query('select public.qcms_delete_osp_material_out_group($1)',[saved.id]),/Downstream/);
assert.deepEqual(await balances(),[85,175,200,200]);assert.equal(await count('osp_jobs'),2);
await db.query('update public.osp_jobs set sample_received_date=null where id=$1',[saved.lines[1].id]);
await db.exec("select set_config('test.archive_only','true',false)");
await fail('archive-only role cannot edit header',()=>db.query("update public.osp_material_outs set material_out_number='BAD' where id=$1",[saved.id]),/row-level security/);
await db.query('select public.qcms_delete_osp_material_out_group($1)',[saved.id]);
assert.deepEqual(await balances(),[100,200,200,200]);assert.equal(await count('osp_jobs'),0);assert.equal(await count('osp_material_outs'),0);tests++;console.log('PASS grouped delete restores each heat balance');
await db.exec('reset role');
const grants=await db.query("select has_function_privilege('anon','public.qcms_create_osp_material_out(uuid,jsonb,jsonb)','EXECUTE') allowed");assert.equal(grants.rows[0].allowed,false);tests++;console.log('PASS anonymous RPC access denied');
console.log(`${tests} PostgreSQL transaction checks passed`);await db.close();
