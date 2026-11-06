import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync,readdirSync} from 'node:fs';
import {handleOffice} from '../lib/office-relay.mjs';
const base='https://office.example';
class D1 {
 constructor(){this.db=new DatabaseSync(':memory:');for(const name of readdirSync('drizzle').filter(x=>x.endsWith('.sql')))this.db.exec(readFileSync('drizzle/'+name,'utf8'));}
 prepare(sql){const stmt=this.db.prepare(sql);const wrap=params=>({bind:(...args)=>wrap(args),first:async()=>stmt.get(...params)||null,all:async()=>({results:stmt.all(...params)}),run:async()=>({meta:{changes:Number(stmt.run(...params).changes)}})});return wrap([]);}
 async batch(statements){this.db.exec('BEGIN');try{const result=[];for(const statement of statements)result.push(await statement.run());this.db.exec('COMMIT');return result;}catch(e){this.db.exec('ROLLBACK');throw e;}}
}
function fixture(t){const DB=new D1();t.after(()=>DB.db.close());return {DB,OFFICE_OWNER_EMAIL:'owner@example.com',OFFICE_BRIDGE_TOKEN:'test-private'};}
function request(path,data,kind='owner',method=data?'POST':'GET'){
 const headers={'Content-Type':'application/json',Origin:base};
 if(kind==='owner')Object.assign(headers,{'oai-authenticated-user-id':'owner-id','oai-authenticated-user-email':'owner@example.com'});
 if(kind==='other')Object.assign(headers,{'oai-authenticated-user-id':'other-id','oai-authenticated-user-email':'other@example.com'});
 if(kind==='bridge')headers.Authorization='Bearer test-private';
 return new Request(base+'/api/office/'+path,{method,headers,body:data?JSON.stringify(data):undefined});
}
const invoke=(env,path,data,kind)=>handleOffice(request(path,data,kind),env);
const enqueue=(env,id=crypto.randomUUID(),operation='enqueue')=>invoke(env,'request',{id,operation,body:{agent:'perfil',task:'Preview',execute:false,mode:'lexical',request_id:id}});
async function online(env){await invoke(env,'bridge/poll',{summary:{backend_ok:true,units:1035}},'bridge');}

test('anonymous and different owner cannot use the office',async t=>{const env=fixture(t);assert.equal((await invoke(env,'connection',undefined,'none')).status,401);assert.equal((await invoke(env,'connection',undefined,'other')).status,401);});
test('owner cannot impersonate the backend bridge',async t=>{const env=fixture(t);assert.equal((await invoke(env,'bridge/poll',{})).status,403);});
test('offline backend rejects work without storing a command',async t=>{const env=fixture(t);assert.equal((await enqueue(env)).status,503);assert.equal(env.DB.db.prepare('SELECT count(*) n FROM relay_requests').get().n,0);});
test('cross-origin owner writes are rejected',async t=>{const env=fixture(t);await online(env);const req=request('request',{id:crypto.randomUUID(),operation:'memory',body:{}});req.headers.set('Origin','https://evil.example');assert.equal((await handleOffice(req,env)).status,403);});
test('queue idempotency rejects altered requests and does not double enqueue',async t=>{const env=fixture(t);await online(env);const id=crypto.randomUUID();assert.equal((await enqueue(env,id)).status,202);assert.equal((await enqueue(env,id)).status,202);assert.equal((await enqueue(env,id,'search')).status,409);assert.equal(env.DB.db.prepare('SELECT count(*) n FROM relay_requests').get().n,1);});
test('claimed work is not replayed when the bridge polls again',async t=>{const env=fixture(t);await online(env);await enqueue(env);const first=await(await invoke(env,'bridge/poll',{},'bridge')).json();const second=await(await invoke(env,'bridge/poll',{},'bridge')).json();assert.equal(first.requests.length,1);assert.equal(second.requests.length,0);});
test('results require the claim and delivery retry never changes the result',async t=>{const env=fixture(t);await online(env);const id=crypto.randomUUID();await enqueue(env,id);const {requests:[job]}=await(await invoke(env,'bridge/poll',{},'bridge')).json();const payload={id,claim:job.claim,status:202,data:{id,status:'queued'}};assert.equal((await invoke(env,'bridge/result',{...payload,claim:crypto.randomUUID()},'bridge')).status,409);assert.equal((await invoke(env,'bridge/result',payload,'bridge')).status,200);assert.equal((await invoke(env,'bridge/result',payload,'bridge')).status,200);assert.equal((await invoke(env,'bridge/result',{...payload,data:{tampered:true}},'bridge')).status,409);assert.deepEqual(await(await invoke(env,'result/'+id)).json(),{state:'done',status:202,data:{id,status:'queued'}});});
test('expired ambiguous work is never requeued',async t=>{const env=fixture(t);await online(env);const id=crypto.randomUUID();await enqueue(env,id);await invoke(env,'bridge/poll',{},'bridge');env.DB.db.prepare('UPDATE relay_requests SET expires=0 WHERE id=?').run(id);const result=await invoke(env,'result/'+id);assert.equal(result.status,409);assert.equal((await result.json()).state,'expired');const packet=await(await invoke(env,'bridge/poll',{},'bridge')).json();assert.equal(packet.requests.length,0);});
test('queue refuses arbitrary operations',async t=>{const env=fixture(t);await online(env);assert.equal((await enqueue(env,crypto.randomUUID(),'http://internal/admin')).status,400);assert.equal(env.DB.db.prepare('SELECT count(*) n FROM relay_requests').get().n,0);});
test('heartbeat reports real online and offline state without secrets',async t=>{const env=fixture(t);let result=await(await invoke(env,'connection')).json();assert.equal(result.online,false);await online(env);result=await(await invoke(env,'connection')).json();assert.equal(result.online,true);assert.equal(result.summary.units,1035);assert.equal(JSON.stringify(result).includes('test-private'),false);});
