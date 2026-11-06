// One owner's authenticated UI -> bounded relay -> local Django. Never calls LLMs.
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const operations=new Set(['enqueue','status','search','unit','source','runs','run','cancel','memory','propose','confirm']);
const reply=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
async function body(request,max=1000000){
 const raw=await request.text();if(new TextEncoder().encode(raw).length>max)throw new Error('body_size');
 return JSON.parse(raw);
}
async function digest(text){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),v=>v.toString(16).padStart(2,'0')).join('');}
async function secretMatches(a,b){if(!a||!b)return false;return await digest(a)===await digest(b);}
function owner(request,env){
 const id=request.headers.get('oai-authenticated-user-id');
 const email=request.headers.get('oai-authenticated-user-email');
 return id&&email&&env.OFFICE_OWNER_EMAIL&&email.toLowerCase()===env.OFFICE_OWNER_EMAIL.toLowerCase()?id:null;
}
export async function handleOffice(request,env){
 const db=env.DB;if(!db)return reply({detail:'Oficina sin configurar'},503);
 const url=new URL(request.url), path=url.pathname.replace(/^\/api\/office\/?/,'');
 const now=Date.now();
 try{
  if(path.startsWith('bridge/')){
   if(request.method!=='POST')return reply({detail:'Método no permitido'},405);
   if(!await secretMatches(request.headers.get('Authorization'),`Bearer ${env.OFFICE_BRIDGE_TOKEN||''}`)||!env.OFFICE_BRIDGE_TOKEN)return reply({detail:'Acceso denegado'},403);
   const data=await body(request);
   if(path==='bridge/poll'){
    const summary=JSON.stringify(data.summary||{});if(summary.length>16000)return reply({detail:'Resumen demasiado grande'},400);
    await db.batch([
     db.prepare("INSERT INTO relay_state(id,heartbeat,summary) VALUES('backend',?,?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat,summary=excluded.summary").bind(now,summary),
     db.prepare("UPDATE relay_requests SET state='expired' WHERE state IN ('queued','claimed') AND expires<?").bind(now),
     db.prepare('DELETE FROM relay_requests WHERE expires<?').bind(now-3600000),
    ]);
    const claim=crypto.randomUUID();
    const result=await db.prepare("UPDATE relay_requests SET state='claimed',claim=? WHERE id IN (SELECT id FROM relay_requests WHERE state='queued' AND expires>? ORDER BY created LIMIT 4) RETURNING id,operation,body,claim").bind(claim,now).all();
    const state=await db.prepare("SELECT viewer_seen FROM relay_state WHERE id='backend'").first();
    return reply({requests:result.results.map(r=>({...r,body:JSON.parse(r.body)})),poll_after:now-(state?.viewer_seen||0)<60000?2:10});
   }
   if(path==='bridge/result'){
    if(!UUID.test(data.id||'')||!UUID.test(data.claim||'')||!Number.isInteger(data.status)||data.status<100||data.status>599)return reply({detail:'Resultado inválido'},400);
    const result=JSON.stringify(data.data);if(result===undefined||result.length>900000)return reply({detail:'Resultado demasiado grande'},400);
    const changed=await db.prepare("UPDATE relay_requests SET state='done',result=?,http_status=?,completed=? WHERE id=? AND claim=? AND state='claimed'").bind(result,data.status,now,data.id,data.claim).run();
    // Re-sending a delivery is safe; local Django is never executed again.
    if(!changed.meta.changes){const old=await db.prepare('SELECT state,claim,result,http_status FROM relay_requests WHERE id=?').bind(data.id).first();
     if(old?.state==='done'&&old.claim===data.claim&&old.result===result&&old.http_status===data.status)return reply({saved:true});
     return reply({detail:'Solicitud expirada o no reclamada'},409);}
    return reply({saved:true});
   }
   return reply({detail:'Ruta no encontrada'},404);
  }
  const user=owner(request,env);if(!user)return reply({detail:'Inicia sesión con la cuenta propietaria de la oficina'},401);
  if(request.method==='POST'&&request.headers.get('origin')!==url.origin)return reply({detail:'Origen no permitido'},403);
  if(path==='connection'&&request.method==='GET'){
   await db.prepare("INSERT INTO relay_state(id,viewer_seen) VALUES('backend',?) ON CONFLICT(id) DO UPDATE SET viewer_seen=excluded.viewer_seen").bind(now).run();
   const state=await db.prepare("SELECT * FROM relay_state WHERE id='backend'").first();
   return reply({online:now-state.heartbeat<35000,last_seen:state.heartbeat||null,summary:JSON.parse(state.summary),user_id:user});
  }
  if(path==='request'&&request.method==='POST'){
   const data=await body(request,64000);
   if(!UUID.test(data.id||'')||!operations.has(data.operation)||!data.body||typeof data.body!=='object'||Array.isArray(data.body))return reply({detail:'Solicitud inválida'},400);
   const payload=JSON.stringify(data.body),fingerprint=await digest(data.operation+'\n'+payload);
   const old=await db.prepare('SELECT owner,fingerprint FROM relay_requests WHERE id=?').bind(data.id).first();
   if(old){if(old.owner!==user)return reply({detail:'No encontrado'},404);return old.fingerprint===fingerprint?reply({id:data.id},202):reply({detail:'Identificador ya usado para otra solicitud'},409);}
   const live=await db.prepare("SELECT heartbeat FROM relay_state WHERE id='backend'").first();
   if(!live||now-live.heartbeat>35000)return reply({detail:'El backend está desconectado. Enciende el equipo y vuelve a intentar.'},503);
   const inserted=await db.prepare("INSERT OR IGNORE INTO relay_requests(id,owner,operation,body,fingerprint,state,created,expires) SELECT ?,?,?,?,?,'queued',?,? WHERE (SELECT count(*) FROM relay_requests WHERE state IN ('queued','claimed') AND expires>?)<50").bind(data.id,user,data.operation,payload,fingerprint,now,now+180000,now).run();
   if(!inserted.meta.changes){const same=await db.prepare('SELECT owner,fingerprint FROM relay_requests WHERE id=?').bind(data.id).first();
    if(same?.owner===user&&same.fingerprint===fingerprint)return reply({id:data.id},202);
    return reply({detail:'Hay demasiadas solicitudes pendientes. Espera un momento.'},429);}
   return reply({id:data.id},202);
  }
  if(path.startsWith('result/')&&request.method==='GET'){
   const id=path.slice(7);if(!UUID.test(id))return reply({detail:'Identificador inválido'},400);
   const row=await db.prepare('SELECT * FROM relay_requests WHERE id=? AND owner=?').bind(id,user).first();
   if(!row)return reply({detail:'Solicitud no encontrada'},404);
   if(row.state==='done')return reply({state:'done',status:row.http_status,data:JSON.parse(row.result)});
   if(row.state==='expired'||row.expires<now)return reply({state:'expired',detail:'No se pudo confirmar la respuesta. Revisa el historial antes de reenviar una tarea.'},409);
   return reply({state:row.state},202);
  }
  return reply({detail:'Ruta no encontrada'},404);
 }catch(error){
  if(error instanceof SyntaxError||error.message==='body_size')return reply({detail:'Solicitud inválida o demasiado grande'},400);
  console.error('office_relay_failed',error?.name||'Error');
  return reply({detail:'No se pudo procesar la solicitud de la oficina'},503);
 }
}
