import {useLayoutEffect,useMemo,useRef,useState} from 'react';
import type {Patch,Catalog} from '../types';
const cableColors=['#b4ed79','#79c5ee','#f3ba79','#df9edb','#a2a6ff'];
export function Rack({patch,catalog,onSelect,selected,disabled,onParameter}:{patch:Patch;catalog:Catalog;onSelect:(id:string)=>void;selected:string;disabled:boolean;onParameter:(id:string,key:string,value:number)=>void}){
 const [focus,setFocus]=useState(''),[allCables,setAllCables]=useState(false);
 const grid=useRef<HTMLDivElement>(null),ports=useRef(new Map<string,HTMLButtonElement>());
 const [wires,setWires]=useState<{id:string;path:string;color:string}[]>([]);
 const ordered=useMemo(()=>{
  const pending=[...patch.nodes],done=new Set<string>(),out:typeof pending=[];
  // Keep each ready processing chain adjacent to its source, until a mixer
  // needs the next branch. Every node stays visible, including unused nodes.
  let previous='';
  while(pending.length){
   const ready=(id:string)=>patch.edges.filter(e=>e.target===id).every(e=>done.has(e.source));
   let index=pending.findIndex(n=>ready(n.id)&&patch.edges.some(e=>e.source===previous&&e.target===n.id));
   if(index<0)index=pending.findIndex(n=>ready(n.id));
   if(index<0){out.push(...pending);break}
   const [n]=pending.splice(index,1);done.add(n.id);out.push(n);previous=n.id;
  }
  return out;
 },[patch]);
 const activeFocus=focus||selected;
 useLayoutEffect(()=>{
  const element=grid.current;if(!element)return;
  const update=()=>{
   const box=element.getBoundingClientRect();
   setWires(patch.edges.flatMap((e,i)=>{
    if(!allCables&&e.source!==activeFocus&&e.target!==activeFocus)return [];
    const a=ports.current.get(e.id+':out')?.getBoundingClientRect(),b=ports.current.get(e.id+':in')?.getBoundingClientRect();
    if(!a||!b)return [];
    const x1=a.left-box.left+14,y1=a.top-box.top+a.height/2,x2=b.left-box.left+14,y2=b.top-box.top+b.height/2;
    const bend=Math.min(100,35+Math.abs(y2-y1)*.18);
    return [{id:e.id,path:`M ${x1} ${y1} C ${x1-bend} ${y1+35}, ${x2-bend} ${y2+35}, ${x2} ${y2}`,color:cableColors[i%cableColors.length]}];
   }));
  };
  update();const observer=new ResizeObserver(update);observer.observe(element);
  return()=>observer.disconnect();
 },[patch,activeFocus,allCables]);
 const names=Object.fromEntries(patch.nodes.map(n=>[n.id,n.label||catalog[n.type]?.label||n.type]));
 function port(e:Patch['edges'][number],direction:'in'|'out'){
  const other=direction==='in'?e.source:e.target,i=patch.edges.indexOf(e);
  return <button key={e.id} ref={el=>{if(el)ports.current.set(e.id+':'+direction,el);else ports.current.delete(e.id+':'+direction)}} title={`Câble ${i+1} : ${e.source} → ${e.target}`} onClick={ev=>{ev.stopPropagation();setFocus(other);onSelect(other)}}><i style={{borderColor:cableColors[i%cableColors.length]}}/><span><small>#{i+1}</small> {names[other]}</span></button>;
 }
 return <div className="rack-view"><div className="rack-guide"><b>{patch.nodes.length} modules · {patch.edges.length} câbles</b><span>Molette = défilement · sélectionner un module pour suivre son signal</span><button aria-pressed={allCables} onClick={()=>setAllCables(v=>!v)}>{allCables?'Câbles du module':'Tous les câbles'}</button></div><div className="rack-grid" ref={grid}>
 <svg className="rack-wires" aria-hidden="true">{wires.map(w=><g key={w.id}><path d={w.path} stroke="#0b121a" strokeWidth="5"/><path d={w.path} stroke={w.color} strokeWidth="2.2"/></g>)}</svg>
 {ordered.map((b,i)=>{const d=catalog[b.type];if(!d)return null;const related=allCables||!activeFocus||b.id===activeFocus||patch.edges.some(e=>e.source===activeFocus&&e.target===b.id||e.target===activeFocus&&e.source===b.id);
 return <article key={b.id} className={`rack-module ${b.id===selected?'selected':''} ${related?'':'dimmed'} kind-${d.category}`} onClick={()=>{setFocus(b.id);onSelect(b.id)}}>
 <div className="rack-screws"><i/><small>{String(i+1).padStart(2,'0')} · {d.category}</small><i/></div><h3>{b.label||d.label}</h3><div className="rack-model">{d.label} <code>{b.id}</code></div>
 <div className="rack-parameters">{Object.entries(d.parameters).map(([key,p])=>{
 const value=b.parameters[key]??p.default,max=['frequency','fc'].includes(key)?Math.min(p.maximum,patch.sample_rate*.499):p.maximum;
 const ratio=p.minimum>0&&max/p.minimum>100?Math.log(Math.max(p.minimum,value)/p.minimum)/Math.log(max/p.minimum):(value-p.minimum)/(max-p.minimum);
 return <label key={key}><span><i className="rack-knob" aria-hidden="true" style={{transform:`rotate(${-135+270*Math.max(0,Math.min(1,ratio))}deg)`}}/>{p.label}</span><input aria-label={`${b.label||b.id} · ${p.label}`} type="number" step="any" min={p.minimum} max={max} value={value} disabled={disabled} onChange={e=>{if(Number.isFinite(e.target.valueAsNumber))onParameter(b.id,key,e.target.valueAsNumber)}}/><small>{p.unit}</small></label>;
 })}</div>
 <div className="rack-ports"><b>ENTRÉES</b>{patch.edges.filter(e=>e.target===b.id).map(e=>port(e,'in'))}{d.inputs===0&&<span>Source du signal</span>}<b>SORTIES</b>{patch.edges.filter(e=>e.source===b.id).map(e=>port(e,'out'))}{b.type==='output'&&<span>Audio mono</span>}</div>
 <details onClick={e=>e.stopPropagation()}><summary>Équation / rôle</summary><code>{d.equation}</code><p>{b.reason||d.description}</p></details></article>;
 })}</div></div>;
}
