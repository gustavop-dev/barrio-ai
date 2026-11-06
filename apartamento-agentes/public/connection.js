'use strict';
const connected={online:false,summary:{},jobs:[],memory:[],busy:false,agent:'posicionamiento',draft:'',useAI:false,search:'',pending:[]};
const jobNames={queued:'En cola',running:'Trabajando',complete:'Terminado',failed:'No completado',interrupted:'Requiere revisión',cancelled:'Cancelado'};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function message(text,error=false){const el=$('#toast');el.textContent=text;el.className=error?'visible error':'visible';clearTimeout(message.timer);message.timer=setTimeout(()=>el.className='',9000);}
async function relay(operation,body={},id=crypto.randomUUID()){
 const response=await fetch('/api/office/request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,operation,body})});
 const data=await response.json();if(!response.ok)throw Error(data.detail||'No se pudo enviar la solicitud.');
 for(let i=0;i<100;i++){
  await sleep(i<8?700:1500);
  const result=await fetch('/api/office/result/'+id);const packet=await result.json();
  if(!result.ok)throw Error(packet.detail||'No se pudo confirmar el resultado.');
  if(packet.state==='done'){
   if(packet.status>=400)throw Error(packet.data?.detail||Object.values(packet.data||{}).flat().join(' · ')||'No se completó la solicitud');
   return packet.data;
  }
 }
 throw Error('La respuesta está tardando. Revisa el historial antes de reenviar el encargo.');
}
async function connectionStatus(){
 try{
  const response=await fetch('/api/office/connection');const info=await response.json();
  if(!response.ok)throw Error(info.detail||'No se pudo conectar');
  connected.online=info.online&&info.summary.backend_ok;connected.summary=info.summary;
  $('.mode').textContent=connected.online?'● Equipo conectado':'○ Backend desconectado';
  $('.mode').classList.toggle('offline',!connected.online);
  $('.panelfooter').textContent=connected.online?`${info.summary.units||0} unidades · Memoria central conectada`:'Enciende el equipo para consultar o enviar encargos';
  const note=$('.notice p');note.textContent=connected.online?'Posicionamiento y Perfil están disponibles. Las vistas previas no usan IA pagada. Los demás equipos siguen en planificación.':'La oficina está disponible, pero el equipo que ejecuta los agentes no está conectado. Los encargos guardados se conservan.';
 }catch(error){connected.online=false;$('.mode').textContent='○ Sin conexión';$('.panelfooter').textContent=error.message;}
}
function openResult(title,html){$('#resultbody').innerHTML=`<p class="eyebrow">LINKEDIN TEAM</p><h2>${esc(title)}</h2>${html}`;if(!$('#resultdialog').open)$('#resultdialog').showModal();}
let jobDialogTimer;
$('#closeResult').onclick=()=>{clearTimeout(jobDialogTimer);$('#resultdialog').dataset.job='';$('#resultdialog').close();};
function textBlock(value){return `<pre class="readable">${esc(typeof value==='string'?value:JSON.stringify(value,null,2))}</pre>`;}
function sourceButtons(units){return units.map(u=>`<button class="source-link" data-unit="${esc(u.unit_id||u.id)}">${esc(u.unit_id||u.id)}${u.title?' · '+esc(u.title):''}</button>`).join('');}
function bindSources(root=document){root.querySelectorAll('[data-unit]').forEach(b=>b.onclick=()=>showUnit(b.dataset.unit));}
async function showUnit(id){
 clearTimeout(jobDialogTimer);$('#resultdialog').dataset.job='';
 openResult('Consultando fuente…','<p>Recuperando la unidad original.</p>');
 try{const unit=await relay('unit',{id});openResult(unit.title,`<p class="sectionlabel">${esc(unit.id)} · CLASE ${unit.session}</p><p>Conocimiento original del curso. No ha sido reescrito por este agente.</p>${Object.entries(unit.original).map(([k,v])=>`<details ${k==='explanation'?'open':''}><summary>${esc(k)}</summary>${textBlock(v)}</details>`).join('')}<h3>Evidencias originales</h3>${unit.sources.map(s=>`<details><summary>${esc(s.key)}</summary>${textBlock(s.original)}</details>`).join('')}`);}catch(e){openResult('No se pudo consultar',`<p class="error">${esc(e.message)}</p>`);}
}
function drawJobs(){
 const el=$('#joblist');if(!el)return;
 el.innerHTML=connected.jobs.length?connected.jobs.map(j=>`<article class="task"><div class="jobhead"><strong>${j.agent==='perfil'?'Perfil':'Posicionamiento'}</strong><span class="badge ${esc(j.status)}">${esc(jobNames[j.status]||j.status)}</span></div><p>${esc(j.task)}</p><small>${new Date(j.created_at).toLocaleString('es-CO')} · ${j.execute?'Con Claude':'Vista previa'}</small><button class="secondary" data-result="${j.id}">Ver resultado y fuentes</button>${j.status==='queued'?`<button class="secondary" data-cancel="${j.id}">Cancelar</button>`:''}${j.result_status==='validation_failed'?'<p class="error">Las referencias necesitan revisión.</p>':''}</article>`).join(''):'<p class="empty">Todavía no hay encargos en el backend.</p>';
 el.querySelectorAll('[data-result]').forEach(b=>b.onclick=()=>showJob(b.dataset.result));
 el.querySelectorAll('[data-cancel]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await relay('cancel',{id:b.dataset.cancel});await loadJobs();}catch(e){message(e.message,true);b.disabled=false;}});
 $('#taskcount').textContent=String(connected.jobs.length);
}
async function loadJobs(){
 const el=$('#joblist');if(el)el.textContent='Consultando encargos…';
 try{const result=await relay('runs');connected.jobs=result.results;drawJobs();}catch(e){if($('#joblist'))$('#joblist').textContent=e.message;}
}
async function showJob(id,quiet=false){
 clearTimeout(jobDialogTimer);
 if(quiet&&(!$('#resultdialog').open||$('#resultdialog').dataset.job!==id))return;
 if(!quiet)openResult('Consultando encargo…','<p>Recuperando estado y resultado.</p>');
 $('#resultdialog').dataset.job=id;
 try{
  const job=await relay('run',{id}),p=job.result?.payload;
  if(!$('#resultdialog').open||$('#resultdialog').dataset.job!==id)return;
  let html=`<p>${esc(job.task||'')}</p><p class="badge">${esc(jobNames[job.status]||job.status)}</p>`;
  if(job.error)html+=`<p class="error">${esc(job.error)}</p>`;
  if(p?.error)html+=`<p class="error">${esc(p.error)}</p>`;
  if(p?.answer)html+=`<h3>Propuesta para tu revisión</h3>${textBlock(p.answer.text)}<p class="small-note">Consumo estimado de generación: USD ${Number(p.answer.estimated_usd||0).toFixed(4)}</p><p class="result-note">${job.result_status==='validation_failed'?'La comprobación técnica detectó referencias o una respuesta incompleta.':'Referencias comprobadas técnicamente. El contenido sigue pendiente de tu revisión.'}</p>`;
  if(p?.context)html+=`<h3>${p.answer?'Conocimiento consultado':'Vista previa: conocimiento preparado'}</h3><p>${p.context.units.length} unidades · ${p.context.context_tokens.toLocaleString('es-CO')} tokens de contexto</p>${sourceButtons(p.context.units)}${!p.answer?'<p class="result-note">Esta vista previa reúne las fuentes. Para obtener una propuesta escrita, crea un encargo y activa “Generar propuesta con Claude”.</p>':''}<details><summary>Memoria confirmada utilizada</summary>${textBlock(p.context.confirmed_user_memory)}</details>`;
  if(['queued','running'].includes(job.status))html+='<p>El trabajador está procesándolo. Puedes cerrar esta ventana y volver desde el historial.</p><button id="refreshJob" class="primary">Actualizar estado</button>';
  openResult(job.agent==='perfil'?'Encargo de Perfil':'Encargo de Posicionamiento',html);bindSources($('#resultdialog'));if($('#refreshJob')){ $('#refreshJob').onclick=()=>showJob(id);jobDialogTimer=setTimeout(()=>showJob(id,true),5000); }
 }catch(e){openResult('No se pudo obtener el resultado',`<p class="error">${esc(e.message)}</p>`);}
}
function tasksPanel(){
 $('#panelcontent').innerHTML=`<p class="sectionlabel">UN ENCARGO PARA TU EQUIPO</p><form id="connectedTask"><label for="taskagent">Agente</label><select id="taskagent"><option value="posicionamiento">Posicionamiento</option><option value="perfil">Perfil</option></select><label for="tasktext">¿En qué quieres trabajar?</label><textarea id="tasktext" maxlength="6000" required placeholder="Por ejemplo: ayúdame a identificar qué información necesitas para definir mi nicho y mi audiencia.">${esc(connected.draft)}</textarea><label class="checklabel"><input type="checkbox" id="useAI" ${connected.useAI?'checked':''}> Generar propuesta con Claude</label><p class="small-note">Desactivado: reúne fuentes sin gasto en IA. Activado: genera una propuesta usando el presupuesto ya configurado.</p><button class="primary" type="submit" ${connected.busy?'disabled':''}>${connected.busy?'Enviando…':'Enviar encargo'}</button><p id="taskmsg" role="status"></p></form><div class="history-title"><h3>Historial</h3><button id="reloadJobs" class="secondary">Actualizar</button></div><div id="joblist"></div>`;
 $('#taskagent').value=connected.agent;$('#taskagent').onchange=e=>connected.agent=e.target.value;
 $('#tasktext').oninput=e=>connected.draft=e.target.value;$('#useAI').onchange=e=>connected.useAI=e.target.checked;
 $('#reloadJobs').onclick=loadJobs;drawJobs();
 $('#connectedTask').onsubmit=async e=>{
  e.preventDefault();if(connected.busy)return;if(!connected.online){message('El backend está desconectado; no se ha enviado el encargo.',true);return;}
  const task=$('#tasktext').value.trim();if(!task)return;
  const button=e.target.querySelector('[type=submit]');connected.busy=true;button.disabled=true;button.textContent='Enviando…';
  const requestId=crypto.randomUUID();
  try{
   const job=await relay('enqueue',{agent:connected.agent,task,execute:connected.useAI,mode:connected.useAI?'hybrid':'lexical',request_id:requestId});
   connected.draft='';if($('#tasktext'))$('#tasktext').value='';message('Encargo recibido. El equipo está trabajando.');await loadJobs();await showJob(job.id);
  }catch(error){message(error.message+' ID del encargo: '+requestId,true);}
  finally{connected.busy=false;if(button.isConnected){button.disabled=false;button.textContent='Enviar encargo';}}
 };
 if(connected.online)loadJobs();
}
async function loadMemory(){
 try{connected.memory=await relay('memory');const el=$('#memorylist');if(!el)return;
  el.innerHTML=connected.memory.length?connected.memory.map(m=>`<article class="memoryitem"><strong>${esc(m.key)}</strong>${textBlock(m.value)}<small>${m.status==='confirmed'?'Confirmado por ti':'Propuesta pendiente'} · Versión ${m.version}</small>${m.status==='proposed'&&m.namespace==='user'?`<button class="secondary" data-confirm="${m.id}" data-version="${m.version}">Confirmar este dato</button>`:''}</article>`).join(''):'<p class="empty">Aún no hay hechos personales confirmados. No inventaremos tu nicho, servicios ni clientes.</p>';
  el.querySelectorAll('[data-confirm]').forEach(button=>button.onclick=async()=>{if(!confirm('¿Confirmas que este dato es correcto y puede usarse como contexto de los agentes?'))return;button.disabled=true;try{await relay('confirm',{id:button.dataset.confirm,expected_version:Number(button.dataset.version)});message('Dato confirmado. Los próximos encargos podrán utilizarlo.');await loadMemory();}catch(e){message(e.message,true);button.disabled=false;}});
 }catch(e){if($('#memorylist'))$('#memorylist').textContent=e.message;}
}
function memoryPanel(){
 $('#panelcontent').innerHTML=`<p class="sectionlabel">UNA MEMORIA PARA TODO EL EQUIPO</p><p class="small-note">Los agentes usan hechos que tú confirmas. Una propuesta nueva no sustituye al último dato confirmado hasta que la apruebes.</p><div id="memorylist">Consultando memoria…</div><form id="centralMemory"><label for="memorykey">Nombre del dato</label><input id="memorykey" maxlength="200" required placeholder="Ej.: servicio principal"><label for="memoryvalue">Lo que quieres que el equipo recuerde</label><textarea id="memoryvalue" maxlength="4000" required placeholder="Describe un hecho real sobre ti o tu negocio."></textarea><button class="primary" type="submit">Proponer dato</button></form>${saved.notes.length?`<details><summary>Notas anteriores de este navegador (${saved.notes.length})</summary>${saved.notes.map(n=>`<p>${esc(n.text)}</p>`).join('')}<p class="small-note">No se han convertido automáticamente en hechos confirmados.</p></details>`:''}`;
 $('#centralMemory').onsubmit=async e=>{e.preventDefault();const key=$('#memorykey').value.trim(),value=$('#memoryvalue').value.trim();if(!key||!value)return;const button=e.target.querySelector('button');button.disabled=true;
  try{const old=connected.memory.find(m=>m.namespace==='user'&&m.key===key);await relay('propose',{namespace:'user',key,value,evidence:'Declaración explícita del propietario en la oficina LinkedIn Team',expected_version:old?.version||0});$('#memorykey').value='';$('#memoryvalue').value='';message('Propuesta guardada. Confírmala cuando hayas revisado el dato.');await loadMemory();}catch(e){message(e.message,true);}finally{if(button.isConnected)button.disabled=false;}};
 if(connected.online)loadMemory();else $('#memorylist').textContent='Conecta el backend para consultar la memoria.';
}
function libraryPanel(){
 $('#panelcontent').innerHTML=`<p class="sectionlabel">BIBLIOTECA COMPARTIDA · CLASES 01–06</p><p class="small-note">Busca las unidades originales y comprueba sus evidencias. Una misma unidad puede servir a varios agentes.</p><form id="librarySearch"><label for="libraryquery">¿Qué conocimiento necesitas?</label><input id="libraryquery" maxlength="6000" required value="${esc(connected.search)}" placeholder="Titular, comprador, barrio…"><button class="primary">Buscar fuentes</button></form><div id="searchresults" aria-live="polite"></div>`;
 $('#librarySearch').onsubmit=async e=>{e.preventDefault();connected.search=$('#libraryquery').value.trim();const button=e.target.querySelector('button');button.disabled=true;$('#searchresults').textContent='Buscando en las clases…';try{const data=await relay('search',{query:connected.search,mode:'lexical',limit:8});if($('#searchresults')){$('#searchresults').innerHTML=data.results.length?sourceButtons(data.results):'<p>No encontramos coincidencias. Prueba con otras palabras.</p>';bindSources($('#searchresults'));}}catch(error){if($('#searchresults'))$('#searchresults').textContent=error.message;}finally{if(button.isConnected)button.disabled=false;}};
}
const planningRender=render;
render=function(){planningRender();
 if(tab==='tasks'&&selected==='strategy')tasksPanel();
 if(tab==='memory')memoryPanel();
 if(tab==='library')libraryPanel();
 if(tab==='team'&&selected==='strategy'){
  document.querySelectorAll('.member small').forEach(el=>el.textContent='Conectado · Clases 01–06');
  $('.infobox').innerHTML='<strong>Dos agentes listos para empezar.</strong>Encarga una tarea, consulta sus fuentes y revisa la propuesta antes de adoptarla. Los demás equipos se configurarán después.';
 }
 $('.panelfooter').textContent=connected.online?`${connected.summary.units||0} unidades · Memoria central conectada`:'Consultando conexión del equipo…';
};
const planningAgent=showAgent;
showAgent=function(key){planningAgent(key);const available=key.startsWith('strategy:');$('#agentdialog .placeholder').textContent=available?'Agente conectado · Conocimiento compartido de las clases 01–06':'Rol propuesto · Configuración pendiente';$('#agentdialog p:last-of-type').textContent=available?'Abre Encargos en su equipo para preparar contexto o generar una propuesta. Sus resultados conservan las referencias al curso.':'Este personaje aún no ejecuta tareas; lo configuraremos con detalle más adelante.';if(available)connected.agent=key.endsWith(':0')?'posicionamiento':'perfil';};
selectTeam('strategy');connectionStatus();setInterval(connectionStatus,15000);
