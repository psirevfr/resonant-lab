import type {Patch,Catalog,Block} from './types';
const wrap=(v:number)=>((v+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI;
function values(n:Block,catalog:Catalog){return Object.fromEntries(Object.entries(catalog[n.type]?.parameters??{}).map(([k,s])=>[k,n.parameters[k]??s.default]))}
export function firstEnvelope(patch:Patch,source:string):Block|undefined{
 const nodes=new Map(patch.nodes.map(n=>[n.id,n])),memo=new Map<string,Set<string|null>>(),visiting=new Set<string>();
 const traversable=new Set(['sum','gain','lowpass','lowpass1','highpass','bandpass','notch','peak_eq','resonator','saturation','asymmetric_saturation']);
 const walk=(id:string):Set<string|null>=>{
  const cached=memo.get(id);if(cached)return cached;
  const n=nodes.get(id);if(!n||visiting.has(id))return new Set([null]);
  if(n.type==='envelope')return new Set([id]);if(!traversable.has(n.type))return new Set([null]);
  visiting.add(id);const children=patch.edges.filter(e=>e.source===id),found=new Set<string|null>();
  if(!children.length)found.add(null);for(const e of children)for(const target of walk(e.target))found.add(target);
  visiting.delete(id);memo.set(id,found);return found;
 };
 const children=patch.edges.filter(e=>e.source===source),found=new Set<string|null>();
 if(!children.length)found.add(null);for(const e of children)for(const target of walk(e.target))found.add(target);
 return found.size===1&&!found.has(null)?nodes.get([...found][0]!):undefined;
}
export function prepareInstrument(patch:Patch,catalog:Catalog):Patch{
 const p=structuredClone(patch);for(const n of [...p.nodes])if(n.type==='modal'){const v=values(n,catalog),eid=n.id+'-env';if(p.nodes.some(a=>a.id===eid))throw Error('Identifiant d’enveloppe déjà utilisé.');n.type='oscillator';n.parameters={frequency:v.frequency,amplitude:v.amplitude,phase:wrap(v.phase-2*Math.PI*v.frequency*v.onset)};for(const e of p.edges)if(e.source===n.id)e.source=eid;p.nodes.push({id:eid,type:'envelope',label:'Enveloppe · '+n.id,parameters:{attack:v.attack,tau:v.tau,onset:v.onset},position:{x:n.position.x+240,y:n.position.y},reason:'Enveloppe explicite du mode.'});p.edges.push({id:n.id+'-'+eid,source:n.id,target:eid})}
 const existing=p.nodes.filter(n=>['keyboard-velocity','keyboard-adsr'].includes(n.id));if(existing.length){if(existing.length!==2||!existing.some(n=>n.id==='keyboard-adsr'&&n.type==='adsr')||!existing.some(n=>n.id==='keyboard-velocity'&&n.type==='gain'))throw Error('Contrôles clavier incomplets.');return p}
 if(p.nodes.length>126)throw Error('Préparation MIDI limitée à 128 blocs.');const out=p.nodes.find(n=>n.type==='output'),parent=p.edges.find(e=>e.target===out?.id);if(!out||!parent)throw Error('Sortie du modèle non raccordée.');p.edges=p.edges.filter(e=>e.target!==out.id);p.nodes.push({id:'keyboard-velocity',type:'gain',label:'MIDI · vélocité / VCA',parameters:{gain:1},position:{x:out.position.x-240,y:out.position.y},reason:'Gain commun clic/MIDI.'},{id:'keyboard-adsr',type:'adsr',label:'MIDI · relâchement',parameters:{attack:0,decay:.001,sustain:1,gate:60,release:.2},position:{x:out.position.x,y:out.position.y},reason:'Relâchement appliqué par le gestionnaire de voix.'});for(const [source,target] of [[parent.source,'keyboard-velocity'],['keyboard-velocity','keyboard-adsr'],['keyboard-adsr',out.id]])p.edges.push({id:source+'-'+target,source,target});return p;
}
export function transposeInstrument(patch:Patch,catalog:Catalog,note:number,reference:number,velocity=127,gate=60,track=true){
 if(!Number.isInteger(note)||note<0||note>127||reference<0||reference>127)throw Error('Note MIDI hors limites.');const p=prepareInstrument(patch,catalog),ratio=2**((note-reference)/12),muted:string[]=[];const noise=new Set(p.nodes.filter(n=>n.type==='noise').map(n=>n.id));for(let i=0;i<p.nodes.length;i++)for(const e of p.edges)if(noise.has(e.source))noise.add(e.target);
 for(const n of p.nodes){const v=values(n,catalog);n.parameters=v;if(n.type==='oscillator'||n.type==='resonator'||n.type==='comb'){const old=v.frequency;let freq=old*ratio;if(freq>=Math.min(47000,p.sample_rate*.49)){if(n.type==='oscillator'){v.amplitude=0;muted.push(n.id)}freq=Math.min(47000,p.sample_rate*.49)}freq=Math.max(n.type==='comb'?20:1,freq);if(n.type==='oscillator'){const env=firstEnvelope(p,n.id),onset=env?values(env,catalog).onset:0;v.phase=wrap(v.phase-2*Math.PI*(freq-old)*onset)}v.frequency=Math.max(1,freq)}if(track&&'fc'in v&&!noise.has(n.id))v.fc=Math.max(5,Math.min(Math.min(47000,p.sample_rate*.45),v.fc*ratio))}
 p.nodes.find(n=>n.id==='keyboard-velocity')!.parameters.gain=velocity/127;p.nodes.find(n=>n.id==='keyboard-adsr')!.parameters.gate=gate;p.name=patch.name.slice(0,150)+' · MIDI '+note;return {patch:p,muted};
}
