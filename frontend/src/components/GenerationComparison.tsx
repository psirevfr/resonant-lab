import {useEffect,useState} from 'react';
import type {Candidate,Catalog} from '../types';
import {renderPatchClientSide} from '../audioEngine';
import {Player} from './Player';
import {audioHardware} from '../hardwareAudio';
export type Comparison={additive:Candidate;subtractive:Candidate};
export function GenerationComparison({comparison,catalog,onLoad}:{comparison:Comparison;catalog:Catalog;onLoad:(row:Candidate)=>void}){
 const [urls,setUrls]=useState<string[]>([]),[error,setError]=useState('');
 useEffect(()=>{
  const control=new AbortController(),created:string[]=[];setUrls([]);setError('');
  void (async()=>{for(const row of [comparison.additive,comparison.subtractive]){
   const {blob}=await renderPatchClientSide(row.patch,catalog,control.signal);
   if(control.signal.aborted)return;
   created.push(URL.createObjectURL(blob));
  }setUrls(created.slice())})().catch(e=>{if(!control.signal.aborted)setError(e.message)});
  return()=>{control.abort();created.forEach(URL.revokeObjectURL)};
 },[comparison,catalog]);
 return <section className="generation-comparison" aria-label="Comparaison des méthodes"><div className="generation-columns">{([['Additive',comparison.additive],['Soustractive',comparison.subtractive]] as const).map(([label,row])=><div key={label}><b>{label}</b><span>{row.errors.total.toFixed(4)} · {row.modules} blocs</span><button disabled={row.within_tolerance===false} onClick={()=>onLoad(row)}>Charger</button></div>)}</div>{urls.length===2&&<Player originalUrl={urls[0]} modelUrl={urls[1]} labels={['A · Additive','B · Soustractive']} onError={setError}/ >}{error&&<p role="alert">{error}</p>}</section>;
}
export function HardwarePlan({patch}:{patch:Candidate['patch']}){
 return <details className="audio-detail"><summary>Plan de montage</summary><table><thead><tr><th>Module</th><th>Composants</th><th>Liaison</th></tr></thead><tbody>{patch.nodes.map(node=>{const h=audioHardware(node);return <tr key={node.id}><td>{node.label||node.type}</td><td>{h.parts}{h.frequency&&' · '+h.frequency.toFixed(1)+' Hz'}</td><td>{h.wiring}</td></tr>})}</tbody></table></details>;
}
