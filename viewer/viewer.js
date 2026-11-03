import {Atlas} from './mesh.js';
const el = id=>document.getElementById(id);
async function request(path,options) {
  const response = await fetch(path,options);
  if(!response.ok) {
    const text=await response.text();
    let error;try {error=JSON.parse(text).error;} catch {error=response.statusText;}
    throw new Error(error||response.statusText);
  }
  return response;
}
const titleCase=s=>s.replace(/([a-z])([A-Z])/g,'$1 $2').replaceAll('-',' ').replace(/^./,c=>c.toUpperCase());
let kits, atlas, catalog, clip, recipe, loadedEntry, startClock, playing=false, requestNumber=0;
function message(text,warning=false) {el('status').textContent=text;el('status').classList.toggle('warning',warning);}
function refresh() {
  if(!clip)return;
  atlas.draw();const f=atlas.frame;
  el('scrub').value=Math.round(atlas.time/clip.duration*1000);
  el('clock').textContent=atlas.time.toFixed(2)+' s';
  el('phase').textContent=titleCase(f.phase);
  el('primary').textContent=f.muscles.primary.map(titleCase).join(', ')||'—';
  el('secondary').textContent=f.muscles.secondary.map(titleCase).join(', ')||'—';
  const phase=recipe?.phases?.find(p=>p.id===f.phase);
  const claims=phase?.contacts??recipe?.contacts??[];
  const descriptions=claims.map(c=>{
    const target=typeof c.target==='string'?c.target:c.target.item?c.target.item+'.'+c.target.socket:'world point';
    return titleCase(c.effector)+' → '+target;
  });
  if(recipe?.start?.stance&&phase?.contacts===undefined)descriptions.push('Stance width and foot angle');
  for(const support of f.supports||[])descriptions.push(titleCase(support.body)+' on '+support.surface);
  for(const d of f.diagnostics)descriptions.push(d.message || (titleCase(d.effector)+' · '+d.reason+' · '+(d.residual*1000).toFixed(0)+' mm'));
  el('contacts').textContent=descriptions.join(' · ')||'Free pose';
}
function stop(){playing=false;el('play').textContent='Play';}
function preview(data,source) {
  stop();clip=data;atlas.kit=kits[data.eml];atlas.setClip(clip);atlas.time=0;
  el('title').textContent=data.title;el('view').value='recipe';
  el('kit').textContent=data.equipment.map(x=>titleCase(x.kind)).join(', ')||'Bodyweight';
  const link=el('source');if(source){link.href='/api/source?entry='+encodeURIComponent(source);link.hidden=false;}else{link.removeAttribute('href');link.hidden=true;}
  el('scrub').disabled=false;el('play').disabled=false;
  const warnings=data.frames.filter(f=>f.diagnostics.length).length;
  message(warnings?`${warnings} samples have movement findings. Inspect their phase and measurement.`:'',Boolean(warnings));
  refresh();
}
function parameters(doc,entry) {
  recipe=doc;loadedEntry=entry;el('instructions').textContent=doc.instructions||'';
  const host=el('fields');host.replaceChildren();
  for(const [key,rule] of Object.entries(doc.parameters||{})){
    const label=document.createElement('label');label.textContent=titleCase(key);
    const input=document.createElement('input');input.name=key;input.type='number';input.step='any';
    input.min=rule.min;input.max=rule.max;input.value=rule.default;input.required=true;
    label.append(input);host.append(label);
  }
  el('params').hidden=host.childElementCount===0;refresh();
}
el('params').onsubmit=async e=>{
  e.preventDefault();if(!recipe)return;
  const number=++requestNumber,params=Object.fromEntries([...el('fields').querySelectorAll('input')].map(i=>[i.name,Number(i.value)]));
  const phase=atlas.time/clip.duration,cam=[atlas.yaw,atlas.pitch,atlas.zoom];stop();message('Applying parameters…');
  try{
    const data=await(await request('/api/parameters',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({recipe,parameters:params})})).json();
    if(number!==requestNumber)return;preview(data,loadedEntry);
    [atlas.yaw,atlas.pitch,atlas.zoom]=cam;atlas.time=phase*data.duration;refresh();
  }catch(error){if(number===requestNumber)message(error.message,true);}
};
async function select(entry) {
  const number=++requestNumber;stop();message('Solving '+titleCase(catalog[entry].title)+'…');
  try{const [data,doc]=await Promise.all(['/api/clip','/api/source'].map(url=>request(url+'?entry='+encodeURIComponent(entry)).then(r=>r.json())));
    if(number!==requestNumber)return;preview(data,entry);parameters(doc,entry);
    const url=new URL(location.href);url.searchParams.set('id',catalog[entry].id);history.replaceState(null,'',url);
  }catch(error){
    if(number===requestNumber){el('catalog').value=loadedEntry||'';if(!clip)el('title').textContent='Cannot load recipe';message(error.message,true);}
  }
}
function loop(now) {
  if(playing){atlas.time=((now-startClock)/1000)%clip.duration;refresh();requestAnimationFrame(loop);}
}
el('play').onclick=()=>{
  if(playing){stop();return;}
  playing=true;el('play').textContent='Pause';startClock=performance.now()-atlas.time*1000;requestAnimationFrame(loop);
};
el('scrub').oninput=()=>{stop();atlas.time=el('scrub').value/1000*clip.duration;refresh();};
el('catalog').onchange=()=>select(el('catalog').value);
el('reset').onclick=()=>{el('view').value='recipe';atlas?.camera('recipe');};
el('view').onchange=()=>atlas?.camera(el('view').value);
el('file').onchange=async()=>{
  const file=el('file').files[0];if(!file)return;
  const number=++requestNumber;
  try {
    if(file.size>512000)throw new Error('Recipe exceeds the 512 KB viewer input limit.');
    const sourceText=await file.text();
    const data=await(await request('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:sourceText})).json();
    if(number!==requestNumber)return;
    preview(data,null);parameters(JSON.parse(sourceText),null);el('catalog').value='';
  }catch(error){if(number===requestNumber)message(error.message,true);}
  finally{el('file').value='';}
};
try {
  const [model,vertices,indices,equipment,entries]=await Promise.all([
    request('/anatomy/model.json').then(x=>x.json()),request('/anatomy/vertices.bin').then(x=>x.arrayBuffer()),
    request('/anatomy/indices.bin').then(x=>x.arrayBuffer()),request('/library/equipment.json').then(x=>x.json()),request('/api/catalog').then(x=>x.json())]);
  kits={'1.0':await request('/compat/1.0/library/equipment.json').then(r=>r.json()),'1.1':equipment};
  atlas=new Atlas(el('anatomy'),model,vertices,indices,equipment);catalog=entries;
  const groups={};for(const [path,row] of Object.entries(entries)){
    const section=path.startsWith('exercises/')?'Catalog':'Examples';
    if(!groups[section]){groups[section]=document.createElement('optgroup');groups[section].label=section;el('catalog').append(groups[section]);}
    const option=new Option(row.title,path);groups[section].append(option);
  }
  el('rig-label').textContent=`Atlas · ${model.joints.length} joints`;
  const id=new URL(location.href).searchParams.get('id')||'goblet-squat';
  const initial=Object.keys(entries).find(p=>entries[p].id===id)||Object.keys(entries)[0];
  el('catalog').disabled=false;
  if(initial){el('catalog').value=initial;await select(initial);}
  else{el('title').textContent='Open a recipe';message('Choose a local EML JSON document.');}
}catch(error){message(error.message,true);el('title').textContent='Atlas unavailable';}
