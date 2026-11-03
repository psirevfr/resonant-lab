import {lazy,Suspense,useMemo,useState} from 'react';
import {api} from '../api';
import './CircuitWorkbench.css';

const RCCircuit3D=lazy(()=>import('./RCCircuit3D').then(module=>({default:module.RCCircuit3D})));
type Project={schema_version:1;name:string;resistance_ohms:number;capacitance_farads:number};
type Trace={engine:string;analysis:string;project:Project;expected_tau_seconds:number;measured_tau_seconds:number|null;cutoff_hz:number;time_seconds:number[];signals:{vin:number[];vout:number[]};raw_points:number;display_points:number};
const key='resonant-electronics-project-v1';
const initial:Project={schema_version:1,name:'RC · réponse à un échelon',resistance_ohms:1000,capacitance_farads:1e-6};
const fmt=(n:number)=>new Intl.NumberFormat('fr-FR',{maximumSignificantDigits:4}).format(n);
function initialProject():Project{try{const p=JSON.parse(localStorage.getItem(key)||'null');if(p?.schema_version===1&&Number.isFinite(p.resistance_ohms)&&Number.isFinite(p.capacitance_farads))return p}catch{}return initial}

function CircuitSchematic({project}:{project:Project}){return <svg className="rc-schematic" viewBox="0 0 760 250" role="img" aria-label={`Schéma RC : source 5 volts, résistance ${fmt(project.resistance_ohms)} ohms, condensateur ${fmt(project.capacitance_farads*1e6)} microfarads`}>
 <path className="rc-wire" d="M105 120 H202 M298 120 H433 M433 120 H535 V130 M535 144 V174 H202 V120"/><circle className="rc-source" cx="105" cy="147" r="27"/><path className="rc-source-mark" d="M105 133 V146 M99 140 H111 M99 158 H111"/><text x="53" y="205">V1 · échelon 0 → 5 V</text>
 <path className="rc-resistor" d="M202 120 l12 -15 16 30 16 -30 16 30 16 -30 20 15"/><text x="205" y="77">R1 · {fmt(project.resistance_ohms)} Ω</text>
 <path className="rc-capacitor" d="M520 130 H550 M520 144 H550"/><path className="rc-ground" d="M535 174 V191 M516 191 H554 M522 198 H548 M528 205 H542"/><text x="566" y="140">C1 · {fmt(project.capacitance_farads*1e6)} µF</text><text x="441" y="102">V(out)</text><circle cx="433" cy="120" r="5" className="rc-probe"/>
 </svg>}

function Oscilloscope({trace}:{trace:Trace}){
 const points=useMemo(()=>{const t=trace.time_seconds,v=trace.signals;const maxT=Math.max(t.at(-1)??0,1e-9);const path=(s:number[])=>s.map((value,i)=>`${i?'L':'M'} ${(46+(t[i]/maxT)*710).toFixed(1)} ${(222-(Math.max(0,Math.min(5,value))/5)*180).toFixed(1)}`).join(' ');return {vin:path(v.vin),vout:path(v.vout)}},[trace]);
 return <svg className="rc-scope" viewBox="0 0 800 270" role="img" aria-label="Oscilloscope issu de la simulation ngspice, tension en volts selon le temps en secondes"><rect x="46" y="32" width="710" height="190" className="scope-bg"/>{Array.from({length:6},(_,i)=><g key={i}><path className="scope-grid" d={`M46 ${42+i*36}H756`}/><text x="8" y={46+i*36}>{5-i} V</text></g>)}{Array.from({length:6},(_,i)=><path key={i} className="scope-grid" d={`M${46+i*142} 32V222`}/>)}<path d={points.vin} className="scope-vin"/><path d={points.vout} className="scope-vout"/><text x="46" y="250">0 s</text><text x="716" y="250">{fmt(trace.time_seconds.at(-1)??0)} s</text></svg>
}

export function CircuitWorkbench(){
 const [project,setProject]=useState<Project>(initialProject),[trace,setTrace]=useState<Trace|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[view,setView]=useState<'2d'|'3d'>('2d');
 const tau=project.resistance_ohms*project.capacitance_farads;
 function edit(next:Partial<Project>){setProject(p=>({...p,...next}));setTrace(null);setError('');setNotice('')}
 async function simulate(){setBusy(true);setError('');setNotice('');try{const result=await api<Trace>('/circuit/simulate',project);setTrace(result)}catch(e){setError(e instanceof Error?e.message:'Simulation indisponible.')}finally{setBusy(false)}}
 function save(){try{localStorage.setItem(key,JSON.stringify(project));setNotice('Projet enregistré sur cet appareil.')}catch{setError('Enregistrement local impossible (stockage navigateur indisponible).')}}
 function reload(){try{const stored=localStorage.getItem(key);if(!stored){setNotice('Aucune sauvegarde locale pour ce projet.');return}const parsed=JSON.parse(stored);if(parsed?.schema_version!==1||!Number.isFinite(parsed.resistance_ohms)||!Number.isFinite(parsed.capacitance_farads))throw new Error();setProject(parsed);setTrace(null);setError('');setNotice('Projet rechargé depuis cet appareil.')}catch{setError('La sauvegarde locale est invalide ou illisible.')}}
 return <section className="circuit-workbench" aria-label="Simulateur de circuit RC">
  <header className="circuit-workbench-header"><div><span className="eyebrow">LOT 1 · CIRCUIT RC</span><h2>{project.name}</h2><p>Un même projet alimente le schéma, le montage 3D, la netlist ngspice et l’oscilloscope. La connectivité reste fixe dans ce premier exemple.</p></div><div className="circuit-workbench-actions"><button onClick={save}>Enregistrer</button><button onClick={reload}>Recharger</button><button className="run-circuit" onClick={()=>void simulate()} disabled={busy}>{busy?'Simulation…':'Simuler avec ngspice'}</button></div></header>
  <div className="circuit-project-controls"><label>Résistance R1 (Ω)<input type="number" min="100" max="100000" step="100" value={project.resistance_ohms} onChange={e=>Number.isFinite(e.target.valueAsNumber)&&edit({resistance_ohms:e.target.valueAsNumber})}/></label><label>Condensateur C1 (µF)<input type="number" min="0.001" max="1000" step="0.1" value={project.capacitance_farads*1e6} onChange={e=>Number.isFinite(e.target.valueAsNumber)&&edit({capacitance_farads:e.target.valueAsNumber/1e6})}/></label><div className="rc-calculated"><span>τ = R × C</span><b>{fmt(tau*1000)} ms</b><span>fc ≈ {fmt(1/(2*Math.PI*tau))} Hz</span></div><div className="circuit-view-toggle"><button className={view==='2d'?'active':''} onClick={()=>setView('2d')}>Schéma 2D</button><button className={view==='3d'?'active':''} onClick={()=>setView('3d')}>Breadboard 3D</button></div></div>
  <div className="circuit-project-view">{view==='2d'?<CircuitSchematic project={project}/>:<Suspense fallback={<div className="rc-loading">Chargement de la scène…</div>}><RCCircuit3D resistance={project.resistance_ohms} capacitance={project.capacitance_farads}/></Suspense>}</div>
  <div className="rc-topology-note"><b>Topologie validée :</b> V1 → R1 en série → nœud V(out) ; C1 relie V(out) à la masse. Le solveur reçoit uniquement ces composants typés, jamais une netlist ou une commande saisie par le navigateur.</div>
  {error&&<p className="rc-error" role="alert">{error}</p>}{notice&&<p className="rc-notice" role="status">{notice}</p>}
  <section className="rc-scope-panel"><div className="rc-scope-title"><div><span className="eyebrow">OSCILLOSCOPE · TRANSITOIRE</span><h3>V(out) après un échelon de 5 V</h3></div>{trace&&<div className="rc-scope-meta"><span>Moteur : {trace.engine}</span><span>τ théorique {fmt(trace.expected_tau_seconds*1000)} ms</span><span>τ mesurée {trace.measured_tau_seconds===null?'non mesurée':fmt(trace.measured_tau_seconds*1000)+' ms'}</span><span>{trace.raw_points} points calculés</span></div>}</div>
   {trace?<><div className="rc-scope-legend"><span><i className="vin-key"/> V(in)</span><span><i className="vout-key"/> V(out)</span></div><Oscilloscope trace={trace}/></>:<div className="rc-scope-empty">Lance la simulation pour afficher les tensions réellement calculées par ngspice. Aucune courbe de démonstration n’est affichée ici.</div>}
  </section>
  <footer className="rc-provenance">Projet version 1 · simulation native ngspice en sous-processus borné · durée maximale 5 s · trace limitée à 513 points affichés · sauvegarde privée au navigateur.</footer>
 </section>
}
