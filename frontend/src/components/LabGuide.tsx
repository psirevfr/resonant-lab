import {useEffect,useRef,useState} from 'react';
import type {Catalog} from '../types';

export const moduleHelp:Record<string,string>={
 input:'Une entrée de test : elle envoie un petit choc pour observer la réaction du montage. Ce bloc ne lit pas votre fichier WAV.',
 oscillator:'Il crée une vibration régulière, comme un sifflement pur. La fréquence choisit la hauteur : plus elle monte, plus le son est aigu.',
 modal:'Imaginez une corde que l’on frappe : elle vibre, puis le son s’éteint. Ce bloc recrée une de ces vibrations. Plusieurs vibrations composent une note de piano.',
 noise:'Il crée un souffle contenant beaucoup de fréquences. Avec une enveloppe très courte et un filtre, il peut imiter le bruit du marteau au début d’une note.',
 impulse:'Un choc extrêmement bref, comme une petite tape. Il peut faire vibrer un résonateur ou servir à tester un filtre.',
 gain:'C’est un réglage de volume. Un gain négatif retourne la vibration ; il ne crée pas de nouvelles fréquences.',
 sum:'Une table de mixage très simple : elle additionne les sons qui arrivent. Plusieurs sons forts peuvent produire un résultat trop fort.',
 multiply:'Ce bloc multiplie deux signaux. Avec une enveloppe, il ouvre et ferme le volume du son : c’est le rôle d’un VCA, un volume commandé par un signal.',
 lowpass:'Il adoucit le son en atténuant les aigus et en laissant davantage passer les graves. La fréquence de coupure règle la limite de cette action.',
 highpass:'Il atténue les graves et laisse davantage passer les aigus. Il peut aider à isoler une attaque brillante ou un souffle.',
 bandpass:'Il laisse surtout passer une zone de fréquences, comme si vous choisissiez une couleur précise dans le son.',
 notch:'Il creuse une zone précise du son pour atténuer une fréquence gênante, tout en gardant les fréquences autour.',
 resonator:'Comme une caisse qui résonne après un choc : il renforce une vibration particulière et la laisse s’éteindre progressivement.',
 delay:'Il décale le son dans le temps. Seul, il ne répète pas le son ; mélangé à l’original, il peut produire une impression de double ou d’écho.',
 envelope:'Elle dessine le volume au fil du temps : le son apparaît, puis s’éteint. Ici, elle agit directement sur le son qui entre.',
 adsr:'Quatre moments du volume : Attack, le son monte ; Decay, il redescend ; Sustain, il tient un niveau ; Release, il s’éteint quand la note se termine.',
 saturation:'Elle arrondit les grandes vibrations et ajoute des fréquences liées à la note, appelées harmoniques. Le son devient plus riche, mais pas forcément plus fidèle.',
 asymmetric_saturation:'Elle déforme différemment les deux côtés de la vibration pour enrichir le son. Le calcul à quatre fois la fréquence aide à limiter les fréquences parasites, sans toutes les supprimer.',
 peak_eq:'Un réglage ciblé : il augmente ou diminue une zone de fréquences. Il permet d’éclaircir ou d’assombrir une partie du son sans tout changer.',
 lowpass1:'Un filtre qui adoucit les aigus plus progressivement que le passe-bas habituel. Utile pour une correction légère.',
 output:'Le point d’arrivée du montage : c’est le son connecté à cette sortie que vous écoutez et exportez.'
};

const steps=[
 {title:'Bienvenue, je suis Rémi !',text:'Ici, vous partez d’un son et vous construisez une petite machine capable de lui ressembler. Pas besoin de connaître les formules : je vais vous montrer le chemin.',tip:'Vous pouvez fermer cette visite à tout moment. Le bouton Help reste disponible.'},
 {title:'Commencez par un son',text:'Importez un fichier WAV, ou essayez la note de démonstration. Le son d’origine sert de référence : c’est celui que nous voulons retrouver.',tip:'Pour commencer, choisissez un extrait court autour du début de la note. Le début contient souvent le choc et le bruit de l’attaque.'},
 {title:'Analyser, puis générer',text:'Analyser observe ce qu’il y a dans le son : des vibrations graves ou aiguës, leur force et la façon dont elles s’éteignent. Générer propose ensuite un montage de petits blocs pour le reproduire.',tip:'L’analyse décrit le son. La génération construit le modèle. Ce sont deux étapes différentes.'},
 {title:'Les blocs et les câbles',text:'Un générateur crée un son. Un filtre en change la couleur. Une enveloppe fait évoluer son volume. Les câbles indiquent le chemin jusqu’à la sortie. Cliquez sur un bloc pour découvrir ses réglages.',tip:'Exemple d’attaque : bruit blanc → filtre → enveloppe courte → somme avec les vibrations de la note → sortie.'},
 {title:'Écoutez, ajustez, simplifiez',text:'Comparez l’original et le modèle. Optimiser ajuste les réglages pour rapprocher les deux sons. Simplifier essaie de garder moins de blocs, en contrôlant l’écart autorisé.',tip:'Une saturation peut enrichir un générateur, puis des filtres sculptent ce son. Mais moins de blocs ne garantit pas une meilleure copie : écoutez et regardez les écarts.'},
 {title:'Votre appareil, votre instrument',text:'Le mode « Cet appareil » effectue génération, optimisation et simplification sur votre ordinateur ou téléphone. Le mode serveur utilise une file d’attente. Le clavier permet ensuite d’essayer le modèle sur différentes notes.',tip:'Le premier calcul local charge son moteur et peut prendre du temps. La lecture et le WAV sont préparés dans le navigateur. Une note bien copiée ne garantit pas encore un piano parfait sur toutes les notes.'}
];

function Mascot(){return <svg className="lab-mascot" viewBox="0 0 140 140" role="img" aria-label="Rémi, le petit guide du laboratoire"><path d="M70 27V13m-6 0h12" stroke="#b4ed79" strokeWidth="5" strokeLinecap="round"/><rect x="25" y="30" width="90" height="77" rx="25" fill="#233743" stroke="#b4ed79" strokeWidth="3"/><rect x="36" y="43" width="68" height="40" rx="13" fill="#101c25"/><circle cx="53" cy="61" r="5" fill="#b4ed79"/><circle cx="87" cy="61" r="5" fill="#b4ed79"/><path d="M59 74q11 8 22 0M17 64l-9 10m115-10 9 10M49 110l-6 15m48-15 6 15" stroke="#b4ed79" strokeWidth="5" fill="none" strokeLinecap="round"/><path d="M48 96h8l5-7 8 14 7-12 5 5h10" stroke="#a7c9e1" fill="none" strokeWidth="2"/></svg>}

export function ModuleHelp({type}:{type:string}){return moduleHelp[type]?<details className="module-simple-help"><summary>En mots simples</summary><p>{moduleHelp[type]}</p><p>Amplitude = force du son · fréquence = hauteur · attaque = vitesse d’apparition · décroissance = temps pour s’éteindre. Dans un filtre, Q règle à quel point l’action est concentrée autour d’une fréquence.</p></details>:null}

export function LabGuide({userId,catalog}:{userId?:number;catalog:Catalog}){
 const dialog=useRef<HTMLDialogElement>(null),trigger=useRef<HTMLButtonElement>(null);
 const [open,setOpen]=useState(false),[step,setStep]=useState(0),[mode,setMode]=useState<'tour'|'modules'>('tour'),[type,setType]=useState('modal');
 const key=`resonant-guide-v1:${userId}`;
 useEffect(()=>{if(!userId)return;try{if(localStorage.getItem(key)!=='seen')setOpen(true)}catch{setOpen(true)}},[userId,key]);
 useEffect(()=>{if(open&&userId){if(!dialog.current?.open)dialog.current?.showModal()}else if(dialog.current?.open)dialog.current.close()},[open,userId]);
 function close(){dialog.current?.close();setOpen(false);try{localStorage.setItem(key,'seen')}catch{/* Help remains usable when storage is blocked. */}trigger.current?.focus()}
 function reopen(){setStep(0);setMode('tour');setOpen(true)}
 if(!userId)return null;
 return <><button ref={trigger} className="lab-help-button" onClick={reopen} aria-haspopup="dialog"><span aria-hidden="true">✦</span> Help <span className="help-fr">· Guide</span></button>
 <dialog ref={dialog} className="lab-guide" aria-labelledby="lab-guide-title" onCancel={e=>{e.preventDefault();close()}}>
 <div className="guide-top"><span>RÉMI · VOTRE GUIDE</span><button onClick={close} aria-label="Fermer le guide">✕</button></div>
 <div className="guide-body"><Mascot/><div className="guide-speech"><h2 id="lab-guide-title" aria-live="polite">{mode==='tour'?steps[step].title:'À quoi sert chaque module ?'}</h2>
 <nav className="guide-tabs" aria-label="Sections du guide"><button aria-pressed={mode==='tour'} onClick={()=>setMode('tour')}>Premiers pas</button><button aria-pressed={mode==='modules'} onClick={()=>setMode('modules')}>Les modules</button></nav>
 {mode==='tour'?<><p>{steps[step].text}</p><div className="guide-tip">{steps[step].tip}</div><div className="guide-progress">Étape {step+1} sur {steps.length}</div><div className="guide-navigation"><button disabled={step===0} onClick={()=>setStep(s=>s-1)}>Précédent</button>{step<steps.length-1?<button className="primary" onClick={()=>setStep(s=>s+1)}>Suivant →</button>:<button className="primary" onClick={close}>À moi de jouer !</button>}</div></>:<><label className="guide-module-select">Choisir un module<select value={type} onChange={e=>setType(e.target.value)}>{Object.entries(catalog).map(([id,def])=><option key={id} value={id}>{def.label}</option>)}</select></label><p>{moduleHelp[type]??'Ce module ne dispose pas encore d’une explication simplifiée.'}</p><div className="guide-tip">Retrouvez aussi « En mots simples » dans l’inspecteur, après avoir sélectionné un bloc du montage.</div></>}
 </div></div><button className="guide-skip" onClick={close}>Fermer et explorer le laboratoire</button></dialog></>
}
