import type {Catalog,Patch,Parameters} from './types';

export interface AudioModule {id:string;type:string;name:string;role:string;parameters:Parameters;active:boolean;material:string}
const material:Record<string,string>={
 oscillator:'Générateur de sinus : oscillateur analogique à dimensionner, ou calcul dans le microcontrôleur.',
 noise:'Source de bruit + amplification à dimensionner. Un AOP seul ne crée pas des harmoniques stables.',
 gain:'Amplificateur : AOP + réseau de résistances à dimensionner selon le gain et les alimentations.',
 saturation:'Étage non linéaire : AOP / diodes à dimensionner et caractériser ; tanh n’est pas un composant.',
 asymmetric_saturation:'Étage non linéaire asymétrique : AOP / diodes / polarisation à dimensionner. Le suréchantillonnage ×4 est un traitement numérique.',
 lowpass1:'Filtre RC du premier ordre ; fréquence, impédances et éventuel buffer AOP à dimensionner.',
 lowpass:'Filtre du second ordre : résistances, condensateurs et éventuellement AOP ; fréquence et Q à dimensionner.',
 highpass:'Filtre passe-haut : résistances, condensateurs et éventuellement AOP ; fréquence et Q à dimensionner.',
 bandpass:'Filtre passe-bande : résistances, condensateurs et AOP selon la topologie ; fréquence et Q à dimensionner.',
 notch:'Filtre coupe-bande : réseau RC et éventuellement AOP à dimensionner.',
 peak_eq:'Égaliseur : filtre actif et réseau de gain à dimensionner ; ce bloc contient plusieurs composants physiques.',
 envelope:'Générateur d’enveloppe exponentielle + VCA. Ils nécessitent des circuits physiques distincts ou une implémentation numérique.',
 adsr:'Générateur ADSR + VCA à réaliser. Le gate est une commande, pas une source audio.',
 sum:'Sommateur : réseau de résistances et éventuellement AOP à dimensionner selon les impédances.',
 multiply:'VCA / multiplieur : circuit actif à choisir et dimensionner.',
 output:'Sortie audio : conversion si numérique, adaptation d’impédance et alimentation à définir.',
 resonator:'Résonateur : circuit actif à dimensionner ; ce modèle numérique ne fournit pas directement les composants.',
 comb:'Filtre en peigne : mémoire de retard + interpolation + sommateur + réinjection. Réalisation microcontrôleur/DSP ; coût matériel et accordage à valider, pas un simple AOP.',
 delay:'Délai : mémoire et traitement numérique ; aucun circuit analogique équivalent fourni.',
};
export function audioModuleInventory(patch:Patch,catalog:Catalog):AudioModule[]{
 const active=new Set<string>();
 const visit=(id:string)=>{if(active.has(id))return;active.add(id);for(const e of patch.edges)if(e.target===id)visit(e.source)};
 for(const n of patch.nodes)if(n.type==='output')visit(n.id);
 return patch.nodes.flatMap(n=>{
  const values={...Object.fromEntries(Object.entries(catalog[n.type]?.parameters??{}).map(([key,p])=>[key,p.default])),...n.parameters};
  const row=(id:string,type:string,parameters:Parameters):AudioModule=>({id,type,name:catalog[type]?.label??type,role:n.label,parameters,active:active.has(n.id),material:material[type]??'Réalisation matérielle non définie pour ce bloc.'});
  // Legacy modal patches still show BOTH mechanisms. The normal analysis
  // path already expands them into independently wired oscillator/envelope nodes.
  if(n.type==='modal'){
   const phase=values.phase-2*Math.PI*values.frequency*values.onset;
   const oscillator={...Object.fromEntries(Object.entries(values).filter(([k])=>['frequency','amplitude','phase'].includes(k))),phase:((phase+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI};
   return [row(n.id,'oscillator',oscillator),row(n.id+'-env','envelope',Object.fromEntries(Object.entries(values).filter(([k])=>['attack','onset','tau'].includes(k))))];
  }
  return [row(n.id,n.type,values)];
 });
}
