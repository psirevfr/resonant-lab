'use strict';
const library={inventory:'Inventaire audio',compact:'Résultats de simplification',status:'État du rendu',metrics:'Mesures de fidélité',transfer:'Transfert du réseau',knobs:'Potentiomètres',reference:'Importer et analyser',graph:'Câblage libre',player:'Lecteur audio',keyboard:'Piano MIDI',signals:'Graphiques du signal',settings:'Réglages audio',hardware:'Plan de montage',workshop:'Atelier électronique',text:'Texte',image:'Image',link:'Bouton de direction'};
const plotNames={wave:'Onde',env:'Enveloppe',fft:'Spectre',auto:'Autocorrélation',spectrogram:'Spectrogramme','measured-envelope':'Enveloppe mesurée',optimization:'Optimisation',global:'Transfert global','bode-gain':'Bode · gain','bode-phase':'Bode · phase',impulse:'Réponse impulsionnelle'};
let selectedBlock='',plotKey='wave',dragging=null;
const createId=prefix=>prefix+'-'+crypto.randomUUID().slice(0,12);
const current=()=>layout?.pages.find(p=>p.id===page);
const displayName=p=>p.name||draft?.labels[p.id]||p.id;
const button=(text,action)=>{const el=document.createElement('button');el.textContent=text;el.onclick=action;return el};
const field=(text,value,cb,options={})=>{
 const label=document.createElement('label'),input=document.createElement(options.values?'select':'input');
 label.append(text,input);
 if(options.values){for(const [v,title] of options.values){const o=document.createElement('option');o.value=v;o.textContent=title;input.append(o)}}
 else {input.type=options.type||'text';if(options.max!==undefined)input.max=options.max;if(options.min!==undefined)input.min=options.min;if(options.length)input.maxLength=options.length;}
 if(input.type==='checkbox')input.checked=!!value;else input.value=value??'';
 input.addEventListener('change',()=>cb(input.type==='checkbox'?input.checked:input.type==='number'?input.valueAsNumber:input.value));
 return label;
};
function gridPage(p){
 if(!p.custom){p.custom=true;const kinds=p.id==='atelier'?['workshop']:['reference','settings','inventory','compact','graph','hardware','status','keyboard','signals','metrics','player','transfer'];let y=0;
  p.blocks=kinds.map(kind=>{const h=kind==='workshop'?12:kind==='graph'?8:kind==='reference'?4:2;const block={id:createId('bloc'),kind,x:0,y,w:12,h};y+=h;return block;});
 }
 return p;
}
function modify(action){
 if(busy()||!layout)return;
 const before=snapshot();
 try{action()}catch(e){restore(before);showMessage(e.message,true);return;}
 if(same(before.layout,layout))return;
 undo.push(before);if(undo.length>50)undo.shift();redo=[];lastChange=null;
 renderLayout();refresh();sendPreview();
}
function openPage(id){page=id;selectedBlock='';setPage(id);renderLayout();}
function append(kind,existing=null,place=null){
 modify(()=>{
  const p=gridPage(current());
  if(p.blocks.length>=40)throw Error('Limite de blocs par page atteinte.');
  const b=existing??{id:createId('bloc'),kind,x:0,y:0,w:kind==='text'||kind==='image'||kind==='link'?6:12,h:kind==='workshop'?12:kind==='graph'?8:2};
  b.x=place?Math.min(place.x,12-b.w):b.x;
  b.y=place?place.y:Math.min(239,Math.max(0,...p.blocks.map(v=>v.y+v.h)));
  if(kind==='text'&&!existing)b.text='Texte';
  if(kind==='image'&&!existing)b.target='/favicon.svg';
  if(kind==='link'&&!existing){b.text='Ouvrir';b.target='analyse';}
  p.blocks.push(b);
  if(existing)layout.bank=layout.bank.filter(item=>item.id!==existing.id);
  selectedBlock=b.id;
 });
}
function newPage(){
 if(layout?.pages.length>=24){showMessage('Limite de 24 pages atteinte.',true);return;}
 const id=createId('page');
 modify(()=>layout.pages.push({id,name:'Nouvelle page',parent:null,custom:true,blocks:[]}));
 openPage(id);showSection('layout');
}
function renderLayout(){
 if(!layout||!draft)return;
 const p=current()??layout.pages[0];page=p.id;
 const pageList=$('#page-list');pageList.replaceChildren(...layout.pages.map(item=>{
  const el=button(displayName(item),()=>openPage(item.id));el.className='page'+(item.id===page?' active':'');if(item.parent)el.classList.add('subpage');return el;
 }));
 const board=$('#layout-board'),editing=['layout','insert','bank'].includes(section);
 board.hidden=!editing;$('.preview-viewport').hidden=editing;
 if(editing)$('#preview-loading').hidden=true;else $('#preview-loading').hidden=!!previewOrigin;
 const insert=$('#insert-list');insert.replaceChildren(...Object.entries(library).map(([kind,label])=>{
  const el=button(label,()=>append(kind));el.draggable=true;el.ondragstart=e=>{dragging={kind};e.dataTransfer.setData('text/plain',kind)};return el;
 }));
 const bank=$('#bank-list');bank.replaceChildren(...layout.bank.map(block=>{
  const el=button((block.text||library[block.kind])+' ↗',()=>append(block.kind,block));el.draggable=true;el.ondragstart=e=>{dragging={bank:block.id};e.dataTransfer.setData('text/plain',block.id)};return el;
 }));
 if(!layout.bank.length)bank.textContent='Banque vide';
 const opts=layout.pages.filter(op=>op.id!==p.id).map(op=>[op.id,displayName(op)]);
 const pageControls=$('#page-controls');
 pageControls.replaceChildren(field('Nom de la page',displayName(p),val=>modify(()=>{p.name=val}),{length:60}));
 const root=p.id==='analyse'||p.id==='atelier';
 if(!root)pageControls.append(field('Page parente',p.parent||'',val=>modify(()=>{
  let parent=val;const visited=new Set([p.id]);
  while(parent){if(visited.has(parent))throw Error('Une page ne peut pas contenir sa propre page parente.');visited.add(parent);parent=layout.pages.find(v=>v.id===parent)?.parent;}
  if(visited.size>5)throw Error('Profondeur de page maximale atteinte.');
  p.parent=val||null;
 }),{values:[['','Aucune'],...opts]}));
 for(const [label,dir] of [['↑',-1],['↓',1]]){
  const el=button(label,()=>modify(()=>{const i=layout.pages.indexOf(p),j=i+dir;if(i>0&&j>0&&j<layout.pages.length)[layout.pages[i],layout.pages[j]]=[layout.pages[j],layout.pages[i]];}));
  el.setAttribute('aria-label',dir<0?'Monter la page':'Descendre la page');el.disabled=p.id==='analyse';pageControls.append(el);
 }
 if(!root)pageControls.append(button('Supprimer la page',()=>{modify(()=>{
  if(layout.bank.length+p.blocks.length>100)throw Error('Banque pleine.');
  layout.bank.push(...p.blocks);layout.pages=layout.pages.filter(v=>v.id!==p.id);layout.pages.forEach(v=>{if(v.parent===p.id)v.parent=p.parent});page='analyse';
 });openPage(page)}));
 if(!p.custom)pageControls.append(button('Modifier la disposition',()=>modify(()=>gridPage(p))));
 const block=p.blocks.find(b=>b.id===selectedBlock),controls=$('#block-controls');
 controls.replaceChildren();
 if(block){
  for(const [k,label,min,max] of [['x','Colonne',0,12-block.w],['y','Ligne',0,239],['w','Largeur',1,12-block.x],['h','Hauteur',1,12]]){
   controls.append(field(label,block[k],val=>modify(()=>{if(Number.isInteger(val)&&val>=min&&val<=max)block[k]=val;}),{type:'number',min,max}));
  }
  if(['text','link','image'].includes(block.kind))controls.append(field(block.kind==='image'?'Description':'Texte',block.text,v=>modify(()=>{block.text=v}),{length:400}));
  if(block.kind==='image')controls.append(field('Image (/assets/…)',block.target,v=>modify(()=>{block.target=v}),{length:240}));
  if(block.kind==='link')controls.append(field('Destination',block.target,v=>modify(()=>{block.target=v}),{values:[...layout.pages.map(p=>[p.id,displayName(p)]),...p.blocks.filter(b=>b.id!==block.id).map(b=>['#'+b.id,b.text||library[b.kind]])]}));
  controls.append(button('Dupliquer',()=>{append(block.kind,{...block,id:createId('bloc')});}));
  controls.append(button('Mettre en banque',()=>modify(()=>{if(layout.bank.length>=100)throw Error('Banque pleine.');layout.bank.push(block);p.blocks=p.blocks.filter(b=>b.id!==block.id);selectedBlock='';})));
 }
 board.replaceChildren();
 board.style.minHeight=Math.max(360,Math.max(1,...p.blocks.map(b=>b.y+b.h))*32)+'px';
 for(const b of p.blocks){
  const tile=button(b.text||library[b.kind],()=>{selectedBlock=b.id;showSection('layout')});
  tile.className='layout-tile'+(b.id===selectedBlock?' active':'');
  tile.style.cssText=`left:${b.x/12*100}%;top:${b.y*32}px;width:${b.w/12*100}%;height:${b.h*32}px`;
  tile.draggable=true;
  tile.ondragstart=e=>{dragging={block:b.id,dx:Math.floor((e.clientX-tile.getBoundingClientRect().left)/(board.clientWidth/12)),dy:Math.floor((e.clientY-tile.getBoundingClientRect().top)/32)};e.dataTransfer.setData('text/plain',b.id);};
  const handle=document.createElement('span');handle.className='tile-resize';handle.title='Redimensionner';tile.append(handle);
  handle.onpointerdown=e=>{
   e.preventDefault();e.stopPropagation();handle.setPointerCapture(e.pointerId);
   const x=e.clientX,y=e.clientY,w=b.w,h=b.h;
   handle.onpointermove=move=>{tile.style.width=Math.min(12-b.x,Math.max(1,w+Math.round((move.clientX-x)/(board.clientWidth/12))))/12*100+'%';tile.style.height=Math.min(12,Math.max(1,h+Math.round((move.clientY-y)/32)))*32+'px'};
   handle.onpointerup=up=>{handle.onpointermove=null;modify(()=>{b.w=Math.min(12-b.x,Math.max(1,w+Math.round((up.clientX-x)/(board.clientWidth/12))));b.h=Math.min(12,Math.max(1,h+Math.round((up.clientY-y)/32)));});renderLayout();};
   handle.onpointercancel=()=>renderLayout();
  };
  board.append(tile);
 }
 const styles=layout.plots[plotKey]||{};
 const axes=[['title','Titre'],['x','Axe horizontal'],['xUnit','Unité horizontale'],['y','Axe vertical'],['yUnit','Unité verticale']];
 if(plotKey==='global')axes.push(['y2','Axe vertical droit'],['y2Unit','Unité verticale droite']);
 const traceCount=['wave','env','fft'].includes(plotKey)?3:plotKey==='global'?2:1;
 const traceControls=Array.from({length:traceCount},(_,i)=>{
  function changeTrace(key,value){modify(()=>{
   const plot=layout.plots[plotKey]??={};
   plot.traces??=[];
   while(plot.traces.length<=i)plot.traces.push({});
   plot.traces[i][key]=value;
  });}
  const style=styles.traces?.[i],color=style?.color||(i===0&&styles.color)||['#9bd5ea','#b4ed79','#ed987a'][i];
  return [field('Nom · courbe '+(i+1),style?.name,v=>changeTrace('name',v),{length:100}),
   field('Couleur · courbe '+(i+1),color,v=>changeTrace('color',v),{type:'color'})];
 }).flat();
 $('#plot-controls').replaceChildren(field('Graphique',plotKey,v=>{plotKey=v;renderLayout()},{values:Object.entries(plotNames)}),
 ...axes.map(([k,label])=>field(label,styles[k],v=>modify(()=>{(layout.plots[plotKey]??={})[k]=v;}),{length:100})),
 field('Légende',styles.legend,v=>modify(()=>{(layout.plots[plotKey]??={}).legend=v;}),{type:'checkbox'}),
 ...traceControls);
}
$('#new-page').onclick=newPage;
const board=$('#layout-board');
board.ondragover=e=>{
 if(!dragging)return;e.preventDefault();const r=board.getBoundingClientRect();
 board.style.setProperty('--guide-x',100*Math.max(0,Math.min(11,Math.floor((e.clientX-r.left)/r.width*12)))/12+'%');
 board.style.setProperty('--guide-y',32*Math.max(0,Math.floor((e.clientY-r.top)/32))+'px');board.classList.add('dragging');
};
board.ondragleave=e=>{if(!board.contains(e.relatedTarget))board.classList.remove('dragging')};
board.ondrop=e=>{
 e.preventDefault();board.classList.remove('dragging');const d=dragging;dragging=null;if(!d)return;
 const r=board.getBoundingClientRect(),x=Math.max(0,Math.min(11,Math.floor((e.clientX-r.left)/r.width*12))),y=Math.max(0,Math.min(239,Math.floor((e.clientY-r.top)/32)));
 if(d.block)modify(()=>{const b=current().blocks.find(b=>b.id===d.block);if(b){b.x=Math.min(12-b.w,Math.max(0,x-d.dx));b.y=Math.max(0,y-d.dy);selectedBlock=b.id;}});
 else if(d.bank){const b=layout.bank.find(b=>b.id===d.bank);if(b)append(b.kind,b,{x,y});}
 else if(d.kind in library)append(d.kind,null,{x,y});
};
document.addEventListener('dragend',()=>{dragging=null;board.classList.remove('dragging')});
