import {useMemo} from 'react';
import type {Patch,Catalog} from '../types';
import {audioModuleInventory} from '../audioInventory';

export function AudioInventory({patch,catalog}:{patch:Patch;catalog:Catalog}){
 const rows=useMemo(()=>audioModuleInventory(patch,catalog),[patch,catalog]);
 const counts=useMemo(()=>{const result=new Map<string,number>();for(const r of rows)result.set(r.name,(result.get(r.name)??0)+1);return [...result]},[rows]);
 return <details className="audio-inventory"><summary>Montage audio actuel : {rows.length} blocs explicites · préparation du montage réel</summary>
 <p>{counts.map(([name,n])=>`${n} × ${name}`).join(' · ')}</p>
 <p>Ce sont les traitements du signal, avec leurs vrais noms. Le nombre de blocs n’est pas le nombre de composants physiques : un filtre ou une enveloppe peut demander plusieurs composants. La consommation électrique n’est pas mesurée. Cette liste ne constitue pas encore un plan de câblage ni une nomenclature prête à construire.</p>
 <div className="table-scroll"><table><thead><tr><th>Bloc réellement utilisé</th><th>Réglages</th><th>Réalisation physique à prévoir</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td><b>{r.name}</b><code>{r.id}</code>{r.role&&r.role!==r.name&&<small>Rôle : {r.role}</small>}{!r.active&&<strong>Non relié à la sortie</strong>}</td><td>{Object.entries(r.parameters).map(([key,v])=><span key={key}>{catalog[r.type]?.parameters[key]?.label??key} : {Number(v.toPrecision(6))} {catalog[r.type]?.parameters[key]?.unit??''}<br/></span>)}</td><td>{r.material}</td></tr>)}</tbody></table></div>
 </details>;
}
