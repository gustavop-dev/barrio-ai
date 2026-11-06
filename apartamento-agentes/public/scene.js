/* A compact, original apartment layout composed from licensed LimeZu sprites. */
window.OfficeScene=(()=>{
 const images={};let ready=false,evening=false;
 const load=fetch('assets/manifest.json').then(r=>{if(!r.ok)throw Error('No se pudo cargar el catálogo');return r.json()}).then(async manifest=>{await Promise.all(Object.keys(manifest).map(name=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>{images[name]=im;resolve()};im.onerror=()=>reject(Error('Recurso no disponible: '+name));im.src='assets/'+name+'.png'})));ready=true});
 const positions=[[[93,126],[153,126]],[[249,126],[309,126]],[[80,229],[144,229],[112,279]],[[243,226],[274,226],[307,226],[242,278],[308,278]],[[406,247]]];
 const labels=[[122,76],[279,76],[111,181],[275,181],[405,195]];
 const boxes=[[52,87,128,68],[207,87,135,68],[48,192,130,98],[211,193,130,99],[370,206,72,77]];
 // Ambient clock advances only while motion is enabled; a pause freezes trips too.
 let elapsed=0,lastFrame=null,wasMoving=false;
 const homes=positions.flat();
 const exits=[
  [[93,148],[190,148],[190,186]],[[153,148],[190,148],[190,186]],
  [[249,136],[345,136],[345,186],[190,186]],[[309,136],[345,136],[345,186],[190,186]],
  [[80,195],[190,195],[190,186]],[[144,195],[190,195],[190,186]],
  [[112,282],[190,282],[190,186]],
  [[243,242],[220,242],[190,242],[190,186]],[[274,242],[220,242],[190,242],[190,186]],[[307,242],[220,242],[190,242],[190,186]],
  [[220,278],[190,278],[190,186]],[[308,286],[190,286],[190,186]],
  [[368,247],[368,202],[345,202],[345,186],[190,186]]
 ];
 const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
 function along(route,travel){
  for(let i=1;i<route.length;i++){const a=route[i-1],b=route[i],len=distance(a,b);if(travel<=len){const f=len?travel/len:1;return {x:a[0]+(b[0]-a[0])*f,y:a[1]+(b[1]-a[1])*f,direction:Math.abs(b[0]-a[0])>Math.abs(b[1]-a[1])?(b[0]>a[0]?0:2):(b[1]>a[1]?3:1)}}travel-=len}
  const a=route.at(-1);return {x:a[0],y:a[1],direction:3};
 }
 function actorsAt(ms){
  const cycle=Math.floor(Math.max(0,ms-6000)/65000),phase=Math.max(0,ms-6000)%65000;
  const pair=[cycle%13,(cycle+5)%13];
  return homes.map(([x,y],i)=>{
   const home={id:i,x,y,direction:(i<4||i===6||i===12)?1:3,action:i>=7&&i<=11?'reading':'idle_anim',away:false,talking:false};
   if(ms<6000||!pair.includes(i))return home;
   const slot=pair.indexOf(i),kitchen=cycle%2===0;
   const destination=kitchen?[390+slot*26,101]:[174+slot*24,186];
   const tail=kitchen?[[345,186],[345,101],destination]:[destination];
   const route=[[x,y],...exits[i],...tail];
   const length=route.slice(1).reduce((sum,p,j)=>sum+distance(route[j],p),0),travelTime=length/30*1000;
   const start=slot*800,local=phase-start,hold=8500;
   if(local<0||local>travelTime*2+hold)return home;
   if(local<travelTime)return {...home,...along(route,local/1000*30),action:'run',away:true};
   if(local<travelTime+hold)return {...home,x:destination[0],y:destination[1],direction:slot===0?0:2,action:'idle_anim',away:true,talking:true};
   return {...home,...along([...route].reverse(),(local-travelTime-hold)/1000*30),action:'run',away:true};
  });
 }
 function draw(ctx,t,selected,moving){
  if(t>0){if(moving&&wasMoving&&lastFrame!==null)elapsed+=Math.min(100,Math.max(0,t-lastFrame));lastFrame=t;wasMoving=moving}
  const actors=actorsAt(elapsed);

  ctx.save();ctx.scale(2,2);ctx.imageSmoothingEnabled=false;
  const fill=(x,y,w,h,c)=>{ctx.fillStyle=c;ctx.fillRect(x,y,w,h)};
  const sprite=(name,x,y,w,h)=>{const a=images[name];if(a)ctx.drawImage(a,Math.round(x),Math.round(y),w||a.width,h||a.height)};
  const monitor=(x,y,w=24,h=20,kind=0)=>{
   sprite('monitorFront',x,y,w,h);
   // Tiny lit workspaces, kept inside the original pixel-art bezel.
   fill(x+2,y+2,w-4,h-7,'#d8edf0');
   fill(x+2,y+2,w-4,2,'#427b97');
   fill(x+3,y+5,4,h-11,'#8bb9c6');
   if(kind===1){
    fill(x+9,y+10,2,3,'#719e87');fill(x+12,y+8,2,5,'#57968b');fill(x+15,y+6,3,7,'#427b97');
   }else{
    fill(x+9,y+5,9,2,'#78a9b7');
    fill(x+9,y+9,7,1,'#638b9d');fill(x+9,y+12,9,1,'#83b6ba');
    if(kind===2)fill(x+18,y+9,2,3,'#79aa74');
   }
   fill(x+w-4,y+h-4,1,1,'#a9ebae');
  };
  const tile=(name,x,y,w,h)=>{const a=images[name];ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();for(let yy=y;yy<y+h;yy+=a.height)for(let xx=x;xx<x+w;xx+=a.width)sprite(name,xx,yy);ctx.restore()};
  fill(0,0,480,330,'#c4d1c4');
  // Soft exterior shadow and raised foundation.
  fill(24,36,438,269,'#758d7c');fill(21,32,438,269,'#92a591');fill(18,25,438,270,'#4b5655');
  if(!ready){fill(24,52,426,235,'#d4c0a2');ctx.restore();return actors}
  tile('floor',24,53,426,236);
  // Cream plaster wall, sage wainscot and oak skirting.
  fill(24,28,426,27,'#eee5cc');fill(24,46,426,10,'#9ba998');fill(24,53,426,3,'#667b70');fill(24,27,426,3,'#fff5dd');
  fill(18,25,6,270,'#536b61');fill(21,28,3,263,'#b9c5ae');fill(450,25,6,270,'#536b61');fill(450,29,3,261,'#b9c5ae');
  // Windows overlook a quiet canopy rather than a sprawling city.
  for(const x of [65,195,282]){fill(x+3,30,40,18,'#a0c9ca');fill(x+3,40,40,8,'#728f79');sprite('window',x,26);}
  sprite('board',133,31,30,18);sprite('books',248,30);sprite('plantSmall',37,32);
  // Compact kitchen, separated only by its tiled floor.
  tile('tile',352,55,98,102);fill(350,55,2,102,'#aa987f');
  for(let x=357;x<419;x+=31)sprite('cabinet',x,64,31,25);
  sprite('sink',357,62,29,17);sprite('stove',389,59,18,29);sprite('fridge',423,52,20,40);
  sprite('wallCabinet',361,29,27,19);sprite('wallCabinet',392,29,27,19);sprite('coffee',409,68,14,16);
  sprite('desk',370,112,60,26);sprite('fruit',390,108,13,13);sprite('cup',414,114,8,8);sprite('chairNorthGold',376,133,20,18);sprite('chairNorthGold',409,133,20,18);
  // Rugs define the teams without dividing the room.
  sprite('rugGreen',52,87,130,68);sprite('rugBlue',207,87,135,68);
  sprite('rugRust',48,194,130,98);sprite('rugBlue',211,194,132,98);sprite('rugGreen',370,209,72,73);
  // Selected team's warm brass corner brackets.
  const n=['strategy','research','editorial','readers','review'].indexOf(selected);const b=boxes[n];
  if(b){const [x,y,w,h]=b;ctx.strokeStyle='#f8d47d';ctx.lineWidth=1.5;for(const [xx,yy,dx,dy] of [[x-3,y-3,1,1],[x+w+3,y-3,-1,1],[x-3,y+h+3,1,-1],[x+w+3,y+h+3,-1,-1]]){ctx.beginPath();ctx.moveTo(xx,yy+dy*8);ctx.lineTo(xx,yy);ctx.lineTo(xx+dx*8,yy);ctx.stroke()}}
  // Strategy and listening benches.
  for(const [x,y] of [[67,93],[127,93],[222,93],[282,93]]){sprite('deskLight',x,y,48,29);monitor(x+12,y-4,24,20,x>200?1:0);sprite('cup',x+36,y+9,6,7)}
  // Low bookcases, pinboard and plants line the shared central passage.
  sprite('library',198,146,64,28);sprite('books',269,148,32,26);sprite('plantSmall',319,148);sprite('plant',32,137,20,32);
  // Editorial table: three people, three computers, room for notes.
  sprite('chair',70,223,16,24);sprite('chair',135,223,16,24);// The north-facing editorial seat is drawn in front of its occupant below.
  sprite('desk',65,231,96,32);sprite('laptop',72,232,16,16);sprite('laptop',137,232,16,16);sprite('book',105,237,18,14);sprite('cup',122,247,7,7);
  // The barrio is a living room: a long sofa and two easy chairs.
  sprite('sofa',222,205,104,35);sprite('roundChair',229,261,24,28);sprite('roundChair',296,261,24,28);
  sprite('coffeeTable',251,245,45,23);sprite('book',262,242,14,12);sprite('cup',283,246,6,7);sprite('lamp',329,237,12,32);
  // Quiet review desk; no enclosed office.
  sprite('deskLight',380,217,52,30);monitor(391,211,25,21,2);sprite('printer',430,270,15,15);
  sprite('plant',350,242,20,35);sprite('plant',429,176,20,35);sprite('plantSmall',173,267);sprite('palm',30,253,21,35);
  // Entry, communal project wall and coat-free circulation.
  sprite('door',183,29,16,28);sprite('map',363,172,38,25);sprite('board',405,170,26,20);
  // Characters have authentic frame animation from the pack.
  const person=(i,x,y,action='idle_anim',direction=3)=>{const a=images['person'+i+'-'+action]||images['person'+i+'-idle_anim'];if(!a)return;const fw=action==='sit'?32:16;const per=6;const dirs=action==='reading'?3:action==='sit'?2:4;let dir=action==='reading'?2:direction%dirs;const frame=moving?Math.floor(elapsed/210+i)%per:0;ctx.drawImage(a,(dir*per+frame)*fw,0,fw,32,Math.round(x-fw/2),Math.round(y-29),fw,32)};
  // Empty chairs remain at the desks while their owners take a break.
  const chairIds=[0,1,2,3,6,12];
  for(const i of chairIds)if(actors[i].away){const [x,y]=homes[i];sprite('chairNorth',x-11,y-6,22,20)}
  [...actors].sort((a,b)=>a.y-b.y).forEach(a=>person(a.id,a.x,a.y,a.action,a.direction));
  for(const i of chairIds)if(!actors[i].away){const [x,y]=homes[i];sprite('chairNorth',x-11,y-6,22,20)}
  for(const a of actors.filter(a=>a.talking)){
   const x=Math.round(a.x),y=Math.round(a.y-40);fill(x-9,y,19,10,'#354c48');fill(x-8,y+1,17,8,'#fff4d6');fill(x-2,y+10,3,3,'#fff4d6');
   for(let d=0;d<3;d++)fill(x-5+d*4,y+4-(moving&&Math.floor(elapsed/300)%3===d?1:0),2,2,'#64796c');
  }
  // Sunlight and subtle room depth, composited above the sprites.
  ctx.fillStyle='rgba(255,240,184,.10)';for(const x of [65,195,282]){ctx.beginPath();ctx.moveTo(x,56);ctx.lineTo(x+45,56);ctx.lineTo(x+17,148);ctx.lineTo(x-27,148);ctx.fill()}
  fill(24,56,426,4,'#3a41421b');fill(24,56,4,233,'#3a414217');
  // Balcony garden, small enough to keep the whole office in view.
  fill(171,290,167,25,'#889b8c');tile('floor',175,292,159,19);fill(171,312,167,3,'#475d56');for(let x=175;x<338;x+=12)fill(x,306,2,8,'#536b61');sprite('plantSmall',178,284,12,22);sprite('plantSmall',319,284,12,22);
  fill(18,289,153,6,'#526c61');fill(338,289,118,6,'#526c61');fill(22,289,149,2,'#c6ceae');fill(338,289,114,2,'#c6ceae');
  if(evening){fill(18,25,438,270,'#17224446');ctx.globalCompositeOperation='screen';for(const [x,y] of [[89,103],[150,103],[245,103],[306,103],[404,230],[332,250]]){const g=ctx.createRadialGradient(x,y,0,x,y,32);g.addColorStop(0,'#ffc87540');g.addColorStop(1,'#ffc87500');ctx.fillStyle=g;ctx.fillRect(x-32,y-32,64,64)}ctx.globalCompositeOperation='source-over'}
  ctx.restore();
  return actors;
 }
 return {load,draw,positions,labels,boxes,actorsAt,toggleLight(){evening=!evening;return evening},portrait(i){return 'assets/portrait'+i+'.png'}};
})();
