import {useEffect,useRef,useState} from 'react';
import type {Catalog} from '../types';
import {GuidedTour} from './GuidedTour';
import {GuideMascot} from './GuideMascot';

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

const intro={title:'Bienvenue, je suis Rémi !',text:'Importez une note, construisez un montage de petits modules, puis comparez le son obtenu à l’original. Je vais vous montrer les commandes directement dans votre laboratoire, avec un exemple que vous pourrez essayer.',tip:'Votre travail sera conservé puis restauré à la fin de la visite. Rien n’est calculé sans votre clic. Vous pouvez aussi simplement explorer les explications des modules.'};



export function ModuleHelp({type}:{type:string}){return moduleHelp[type]?<details className="module-simple-help"><summary>En mots simples</summary><p>{moduleHelp[type]}</p><p>Amplitude = force du son · fréquence = hauteur · attaque = vitesse d’apparition · décroissance = temps pour s’éteindre. Dans un filtre, Q règle à quel point l’action est concentrée autour d’une fréquence.</p></details>:null}

export function LabGuide({userId,catalog,tour}:{userId?:number;catalog:Catalog;tour:{onStart:()=>void;onDemo:()=>Promise<void>;onGenerate:()=>Promise<void>;onRestore:()=>void;onArea:(target:string)=>void;onCancel:()=>void;busy:boolean;loaded:boolean;generated:boolean}}){
 const dialog=useRef<HTMLDialogElement>(null),trigger=useRef<HTMLButtonElement>(null);
 const [open,setOpen]=useState(false),[mode,setMode]=useState<'tour'|'modules'>('tour'),[type,setType]=useState('modal');
 const [walking,setWalking]=useState(false);
 const key=`resonant-guide-v2:${userId}`;
 useEffect(()=>{if(!userId)return;try{if(localStorage.getItem(key)!=='seen')setOpen(true)}catch{setOpen(true)}},[userId,key]);
 useEffect(()=>{if(open&&userId){if(!dialog.current?.open)dialog.current?.showModal()}else if(dialog.current?.open)dialog.current.close()},[open,userId]);
 function close(){dialog.current?.close();setOpen(false);try{localStorage.setItem(key,'seen')}catch{/* Help remains usable when storage is blocked. */}trigger.current?.focus()}
 function reopen(){setMode('tour');setOpen(true)}
 function walk(){if(tour.busy)return;tour.onStart();dialog.current?.close();setOpen(false);setWalking(true)}
 function endWalk(){tour.onRestore();setWalking(false);try{localStorage.setItem(key,'seen')}catch{}trigger.current?.focus()}
 if(!userId)return null;
 return <>{walking&&<GuidedTour onEnd={endWalk} {...tour}/>}<button ref={trigger} className="lab-help-button" onClick={reopen} aria-haspopup="dialog"><span aria-hidden="true">✦</span> Help <span className="help-fr">· Guide</span></button>
 <dialog ref={dialog} className="lab-guide" aria-labelledby="lab-guide-title" onCancel={e=>{e.preventDefault();close()}}>
 <div className="guide-top"><span>RÉMI · VOTRE GUIDE</span><button onClick={close} aria-label="Fermer le guide">✕</button></div>
 <div className="guide-body"><GuideMascot/><div className="guide-speech"><h2 id="lab-guide-title" aria-live="polite">{mode==='tour'?intro.title:'À quoi sert chaque module ?'}</h2>
 <nav className="guide-tabs" aria-label="Sections du guide"><button aria-pressed={mode==='tour'} onClick={()=>setMode('tour')}>Premiers pas</button><button aria-pressed={mode==='modules'} onClick={()=>setMode('modules')}>Les modules</button></nav>
 {mode==='tour'?<><p>{intro.text}</p><div className="guide-tip">{intro.tip}</div><button className="primary guide-interactive-start" disabled={tour.busy} onClick={walk}>Me montrer dans le laboratoire →</button></>:<><label className="guide-module-select">Choisir un module<select value={type} onChange={e=>setType(e.target.value)}>{Object.entries(catalog).map(([id,def])=><option key={id} value={id}>{def.label}</option>)}</select></label><p>{moduleHelp[type]??'Ce module ne dispose pas encore d’une explication simplifiée.'}</p><div className="guide-tip">Retrouvez aussi « En mots simples » dans l’inspecteur, après avoir sélectionné un bloc du montage.</div></>}
 </div></div><button className="guide-skip" onClick={close}>Fermer et explorer le laboratoire</button></dialog></>
}
