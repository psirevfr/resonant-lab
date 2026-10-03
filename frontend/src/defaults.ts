import type {Patch,Block} from './types';
const block=(id:string,type:string,label:string,parameters:Record<string,number>,x:number,y:number):Block=>({id,type,label,parameters,position:{x,y},reason:'Patch de départ manuel : valeurs d’illustration, non estimées à partir d’un enregistrement.'});
export function initialPatch():Patch{return{version:1,name:'Atelier libre',sample_rate:44100,duration:3,nodes:[block('osc-1','oscillator','Fondamentale',{frequency:261.63,amplitude:.3,phase:0},0,0),block('osc-2','oscillator','Deuxième partiel',{frequency:523.26,amplitude:.12,phase:0},0,150),block('sum','sum','Somme',{},260,75),block('filter','lowpass','Filtre spectral',{fc:3500,q:.70710678},500,75),block('env','envelope','Décroissance',{attack:.005,tau:1},740,75),block('out','output','Sortie',{},980,75)],edges:[['osc-1','sum'],['osc-2','sum'],['sum','filter'],['filter','env'],['env','out']].map(([source,target])=>({id:`${source}-${target}`,source,target}))}}

// Creating a mode in the editor inserts its two executable functions explicitly.
export function appendModule(patch:Patch,type:string,catalog:import('./types').Catalog,position:{x:number;y:number}):{patch:Patch;id:string}{
 const id=crypto.randomUUID(),d=catalog[type],values=Object.fromEntries(Object.entries(d.parameters).map(([k,p])=>[k,p.default]));
 const block={id,type,label:d.label,parameters:values,position,reason:'Bloc ajouté manuellement.'};
 if(type!=='modal')return {id,patch:{...patch,nodes:[...patch.nodes,block]}};
 const envId=id+'-env',phase=((values.phase-2*Math.PI*values.frequency*values.onset+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI;
 return {id,patch:{...patch,nodes:[...patch.nodes,{...block,type:'oscillator',label:'Mode · sinus',parameters:{frequency:values.frequency,amplitude:values.amplitude,phase}},{...block,id:envId,type:'envelope',label:'Mode · enveloppe',parameters:{attack:values.attack,tau:values.tau,onset:values.onset},position:{x:position.x+240,y:position.y}}],edges:[...patch.edges,{id:id+'-to-env',source:id,target:envId}]}};
}
