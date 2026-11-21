import type {Block} from './types';

const series={E12:[10,12,15,18,22,27,33,39,47,56,68,82],E24:[10,11,12,13,15,16,18,20,22,24,27,30,33,36,39,43,47,51,56,62,68,75,82,91]};
const resistance=(r:number,key:'E12'|'E24')=>Array.from({length:7},(_,i)=>series[key].map(n=>n*10**(i-1))).flat().filter(v=>v>=100&&v<=1e6).sort((a,b)=>Math.abs(Math.log(a/r))-Math.abs(Math.log(b/r)))[0];
const label=(r:number)=>r>=1000?Number((r/1000).toPrecision(4))+' kΩ':r+' Ω';

export function audioHardware(block:Block){
 const p=block.parameters;
 if(['lowpass1','highpass1'].includes(block.type)){
  const c=10e-9, r=resistance(1/(2*Math.PI*p.fc*c),'E24');
  return {parts:'R '+label(r)+' · C 10 nF (E12) · TL072 (suiveur)',wiring:block.type==='lowpass1'?'Entrée → R → nœud de sortie ; C entre le nœud et la masse.':'Entrée → C → nœud de sortie ; R entre le nœud et la masse.',frequency:1/(2*Math.PI*r*c)};
 }
 if(block.type==='gain'){
  const g=p.gain??1, rf=resistance(Math.abs(g<0?g:g-1)*10000,'E24');
  if(g===0)return {parts:'Sortie reliée à la référence',wiring:'Couper le signal, sans relier la source à la masse.'};
  if(g===1)return {parts:'TL072 · suiveur',wiring:'Sortie reliée à l’entrée − ; signal sur l’entrée +.'};
  if(g>0&&g<1){const r=resistance(10000*(1/g-1),'E24');return {parts:'R '+label(r)+' · R 10 kΩ · TL072',wiring:'Diviseur : R depuis l’entrée vers le nœud, 10 kΩ du nœud à la masse. Suiveur sur le nœud.'};}
  return {parts:'TL072 · R 10 kΩ · Rf '+label(rf)+' (E24)',wiring:g<0?'Entrée → 10 kΩ → entrée − ; Rf de la sortie vers − ; entrée + à la référence.':'Entrée + reçoit le signal ; 10 kΩ de l’entrée − à la référence ; Rf de la sortie vers −.'};
 }
 const filters:Record<string,string>={
  sallen_key:'Sallen-Key · TL072',mfb:'Passe-bande à rétroaction multiple · TL072',
  svf_lowpass:'Filtre à variables d’état · sortie passe-bas · TL074',
  svf_highpass:'Filtre à variables d’état · sortie passe-haut · TL074',
  svf_bandpass:'Filtre à variables d’état · sortie passe-bande · TL074',
  vcf:'Filtre à transconductance · LM13700',
 };
 if(filters[block.type])return {parts:filters[block.type],wiring:'Équivalent de principe · valeurs à valider'};
 const equivalent:Record<string,string>={oscillator:'VCO sinusoïdal · pont de Wien',modal:'VCO + VCA + enveloppe',white_noise:'Source de bruit à jonction + TL072',noise:'Source de bruit à jonction + TL072',pink_noise:'Source de bruit + filtre rose',saw:'VCO à rampe · intégrateur + remise à zéro',triangle:'Intégrateur + comparateur LM393',pulse:'Comparateur LM393 + rampe',pulse_train:'Générateur d’impulsions · 555',lfo:'Oscillateur basse fréquence',relaxation:'TL072 + réseau RC + hystérésis',lowpass:'Sallen-Key',highpass:'Sallen-Key passe-haut',bandpass:'Passe-bande MFB ou à variables d’état',notch:'Double T actif',peak_eq:'Égaliseur actif à variables d’état',resonator:'Résonateur actif',comb:'Ligne de retard numérique + réinjection',envelope:'Enveloppe RC + VCA',adsr:'Générateur ADSR + VCA',multiply:'AD633 · multiplicateur quatre quadrants',sum:'Sommateur TL072',schmitt:'LM393 + réaction positive',clipper:'1N4148 tête-bêche + résistance série',rectifier:'Redresseur de précision TL072 + 1N4148',wavefolder:'Réseau de repliement à diodes + TL072',sample_hold:'CD4066 + condensateur + suiveur',integrator:'Intégrateur TL072 avec fuite',differentiator:'Dérivateur TL072 à bande limitée',delay:'Ligne de retard numérique',saturation:'Limiteur analogique',asymmetric_saturation:'Limiteur asymétrique analogique',output:'Codec ou sortie audio tamponnée',input:'Entrée audio tamponnée',impulse:'Générateur d’impulsion'};
 return {parts:equivalent[block.type]??'À étudier',wiring:'Équivalent de principe · valeurs à valider'};
}
