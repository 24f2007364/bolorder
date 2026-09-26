import {test} from 'node:test';
import assert from 'node:assert/strict';
import {localDB} from '../local-db.mjs';
import {initial,start,update,confirm,view,consent,mutate,handle} from '../server.mjs';
const make=s=>start(s,{customer_id:'raja',mode:'demo',request_id:crypto.randomUUID()});
const sample='Kal ke liye 10 carton Aashirvaad atta, 5 carton Maggi aur 4 carton Parle-G bhej dena.';
const auth='Basic '+btoa('bolorder:test-password-for-sites');

test('shortage, substitute, confirmation, prices, and idempotent reservation',()=>{
 const s=initial();let o=make(s);const id=o.id;
 o=update(s,id,{items:[{product_id:'ATT-AA-5',quantity:10},{product_id:'NDL-MG-70',quantity:5},{product_id:'BIS-PG-010',quantity:4}]},0);
 assert.equal(o.shortages[0].alternatives[0].id,'NDL-YP-70');assert.equal(o.state,'WAITING_FOR_CLARIFICATION');
 assert.throws(()=>confirm(s,id,o.revision,'yes',true));
 o=update(s,id,{items:[{product_id:'NDL-MG-70',quantity:3},{product_id:'NDL-YP-70',quantity:2}]},o.revision);
 assert.equal(o.total,2462400);assert.equal(o.state,'READY_FOR_CONFIRMATION');
 assert.equal(s.products[1].demo_stock,3);assert.throws(()=>confirm(s,id,0,'Haan confirm',true));
 o=confirm(s,id,o.revision,'Haan confirm',true);assert.equal(o.state,'COMPLETED');assert.equal(s.products[1].demo_stock,0);assert.equal(s.products[1].stock,3);
 assert.equal(confirm(s,id,o.revision,'Haan confirm',true).sales_number,o.sales_number);assert.equal(s.products[1].demo_stock,0);
});
test('reject invalid products, fractional quantities, stale updates and non-consent',()=>{
 const s=initial(),o=make(s);
 assert.throws(()=>update(s,o.id,{items:[{product_id:'fake',quantity:1}]},0));
 assert.throws(()=>update(s,o.id,{items:[{product_id:'NDL-MG-70',quantity:1.5}]},0));
 assert.throws(()=>confirm(s,o.id,0,'Haan confirm',false));
 for(const t of ['do not confirm','haan confirm mat karo','confirm 5 more maggi','हाँ कन्फर्म मत करो'])assert.equal(consent(t),false);
 assert.ok(consent('हाँ कन्फर्म'));assert.ok(consent('Haan confirm.'));
});
test('D1 compare-and-swap prevents competing orders reserving the same stock',async()=>{
 const db=localDB();const sid=crypto.randomUUID();
 const a=await mutate(db,sid,s=>make(s));const b=await mutate(db,sid,s=>make(s));
 await mutate(db,sid,s=>update(s,a.id,{items:[{product_id:'ATT-AA-5',quantity:10}]},0));
 await mutate(db,sid,s=>update(s,b.id,{items:[{product_id:'ATT-AA-5',quantity:10}]},0));
 const results=await Promise.allSettled([mutate(db,sid,s=>confirm(s,a.id,1,'Haan confirm',true)),mutate(db,sid,s=>confirm(s,b.id,1,'Haan confirm',true))]);
 assert.equal(results.filter(r=>r.status==='fulfilled').length,1);const row=await db.prepare('SELECT payload FROM workspaces WHERE id=?').bind(sid).first();const s=JSON.parse(row.payload);assert.equal(s.products[0].demo_stock,0);assert.equal(Object.values(s.orders).filter(o=>o.state==='COMPLETED').length,1);db.close();
});
test('hosted HTTP flow: gate, session isolation, persisted cart, replay, invoice and origin',async()=>{
 const env={DB:localDB(),APP_ACCESS_PASSWORD:'test-password-for-sites'};let cookie='';
 const call=async(path,body,other={})=>{const res=await handle(new Request('https://bolorder.test'+path,{method:body===undefined?'GET':'POST',headers:{Authorization:auth,...(cookie?{Cookie:cookie}:{}),...(body?{'Content-Type':'application/json'}:{}),...other},...(body!==undefined?{body:JSON.stringify(body)}:{})}),env);if(res.headers.get('set-cookie'))cookie=res.headers.get('set-cookie').split(';')[0];return res;};
 assert.equal((await handle(new Request('https://bolorder.test/api/bootstrap'),env)).status,401);
 assert.equal((await call('/api/bootstrap')).status,200);
 let o=await (await call('/api/orders',{customer_id:'raja',mode:'demo',request_id:crypto.randomUUID()})).json();
 for(const line of [sample,'Haan, 3 Maggi aur 2 Yippee kar do.','Haan confirm.']){
  const body={text:line,request_id:crypto.randomUUID(),revision:o.revision};const response=await call('/api/orders/'+o.id+'/turn',body);assert.equal(response.status,200);const result=await response.json();o=result.order;
  assert.deepEqual(await(await call('/api/orders/'+o.id+'/turn',body)).json(),result);
 }
 assert.equal(o.state,'COMPLETED');assert.equal(o.total,2462400);assert.equal((await call(o.invoice_url)).status,200);
 assert.equal((await call('/api/orders/'+o.id)).status,200);
 assert.equal((await call('/api/demo/reset',{}, {Origin:'https://malicious.test'})).status,403);
 cookie='';assert.equal((await call('/api/orders/'+o.id)).status,404);
 env.DB.close();
});
