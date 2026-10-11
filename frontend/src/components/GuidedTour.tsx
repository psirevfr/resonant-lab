import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {GuideMascot} from './GuideMascot';

const stops=[
 {target:'reference',title:'1 · Partons d’une vraie note',text:'Voici votre son de référence. Chargeons une note d’exemple : vous la verrez apparaître ici. Votre travail actuel sera remis en place à la fin.',action:'Charger la note d’exemple'},
 {target:'generate',title:'2 · Construisons son modèle',text:'Ce bouton transforme la note en montage. L’exemple utilise un extrait de 0,25 seconde et trois vibrations maximum. Lancez-le pour voir les vrais modules apparaître ; le calcul se fera sur cet appareil.',action:'Générer l’exemple sur cet appareil'},
 {target:'graph',title:'3 · Suivez le chemin du son',text:'Voici le montage réellement exécuté. Les vibrations créent le son, les enveloppes règlent son évolution, les câbles mènent à la sortie. Vous pouvez sélectionner un bloc dans la zone éclairée.'},
 {target:'inspector',title:'4 · Essayez un réglage',text:'Le bloc sélectionné s’explique ici. Ouvrez « En mots simples », puis changez légèrement un réglage : le modèle audio est recalculé. Vous pouvez expérimenter sans perdre votre montage de départ.'},
 {target:'player',title:'5 · Écoutez la différence',text:'Utilisez les boutons de lecture pour écouter la note originale puis le modèle. L’écoute démarre uniquement quand vous cliquez. Une petite différence peut venir de l’attaque, du souffle ou des vibrations manquantes.'},
 {target:'export',title:'6 · Votre tour !',text:'Ce menu permet de garder le son en WAV ou le montage pour le reprendre plus tard. Optimiser ajuste les réglages ; simplifier cherche moins de blocs. En terminant la visite, votre travail précédent revient. Help permet de recommencer.'}
];

export function GuidedTour({onEnd,onDemo,onGenerate,onArea,onCancel,busy,loaded,generated}:{onEnd:()=>void;onDemo:()=>Promise<void>;onGenerate:()=>Promise<void>;onArea:(target:string)=>void;onCancel:()=>void;busy:boolean;loaded:boolean;generated:boolean}){
 const [step,setStep]=useState(0),[rect,setRect]=useState<{top:number;left:number;width:number;height:number}|null>(null),[message,setMessage]=useState(''),[acting,setActing]=useState(false);
 const card=useRef<HTMLElement>(null),current=stops[step];const waiting=busy||acting;
 useEffect(()=>{onArea(current.target)},[current.target,onArea]);
 useEffect(()=>{
  let frame=0;
  let target=document.querySelector<HTMLElement>(`[data-guide="${current.target}"]`);
  target?.scrollIntoView({block:'center',behavior:'instant'});
  function update(){cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{
   const latest=document.querySelector<HTMLElement>(`[data-guide="${current.target}"]`);
   if(latest!==target){target=latest;observer.disconnect();if(target){observer.observe(target);target.scrollIntoView({block:'center',behavior:'instant'})}}
   const r=target?.getBoundingClientRect();
   if(!r){setRect(null);return}
   const left=Math.max(4,r.left-6),top=Math.max(4,r.top-6);
   const next={left,top,width:Math.max(0,Math.min(innerWidth-4,r.right+6)-left),height:Math.max(0,Math.min(innerHeight-4,r.bottom+6)-top)};
   setRect(old=>old&&old.left===next.left&&old.top===next.top&&old.width===next.width&&old.height===next.height?old:next);
  })}
  const observer=new ResizeObserver(update);if(target)observer.observe(target);
  const mutations=new MutationObserver(update);mutations.observe(document.querySelector('.workbench')??document.body,{childList:true,subtree:true});
  update();window.addEventListener('resize',update);window.addEventListener('scroll',update,true);
  return()=>{cancelAnimationFrame(frame);observer.disconnect();mutations.disconnect();window.removeEventListener('resize',update);window.removeEventListener('scroll',update,true)};
 },[current.target,loaded,generated]);
 useEffect(()=>{card.current?.focus()},[step]);
 useEffect(()=>{function escape(e:KeyboardEvent){if(e.key==='Escape'&&!waiting)onEnd()};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape)},[waiting,onEnd]);
 async function act(){setActing(true);setMessage('');try{await(step===0?onDemo():onGenerate());setMessage(step===0?'La note est chargée. Passez à la génération.':'Le modèle est prêt : découvrons son montage.')}catch(e){setMessage(e instanceof Error?e.message:'La démonstration n’a pas abouti. Vous pouvez continuer la visite sans calcul.')}finally{setActing(false)}}
 const ready=step===0?loaded:step===1?generated:true;
 const small=innerWidth<700;
 const cardStyle=rect&&!small?{top:rect.top>270?20:undefined,bottom:rect.top>270?undefined:20,left:rect.left>innerWidth/2?20:undefined,right:rect.left>innerWidth/2?undefined:20}:{};
 return createPortal(<div className="guided-tour">
 {rect?<><div className="tour-shade" style={{top:0,left:0,right:0,height:rect.top}}/><div className="tour-shade" style={{top:rect.top+rect.height,left:0,right:0,bottom:0}}/><div className="tour-shade" style={{top:rect.top,left:0,width:rect.left,height:rect.height}}/><div className="tour-shade" style={{top:rect.top,left:rect.left+rect.width,right:0,height:rect.height}}/><div className="tour-focus" style={rect}/></>:<div className="tour-shade" style={{inset:0}}/>}
 <section ref={card} tabIndex={-1} className="tour-coach" style={cardStyle} role="dialog" aria-modal="false" aria-labelledby="tour-title">
 <div className="tour-coach-heading"><GuideMascot/><b>Rémi · visite interactive</b><button disabled={waiting} onClick={onEnd} aria-label="Quitter la visite interactive">✕</button></div>
 <h2 id="tour-title" aria-live="polite">{current.title}</h2><p>{current.text}</p>
 {current.action&&<button className="primary tour-example" disabled={waiting||ready||(step===1&&!loaded)} onClick={()=>void act()}>{ready?'✓ Étape réalisée':waiting?'Démonstration en cours…':current.action}</button>}
 {waiting&&<button onClick={onCancel}>Annuler le calcul de démonstration</button>}
 {message&&<p className="tour-feedback" role="status">{message}</p>}
 <div className="guide-navigation"><button disabled={waiting||step===0} onClick={()=>{setMessage('');setStep(s=>s-1)}}>Précédent</button><button disabled={waiting} onClick={()=>{setMessage('');if(step===stops.length-1)onEnd();else setStep(s=>s+1)}}>{step===stops.length-1?'Terminer et retrouver mon travail':'Suivant →'}</button></div>
 {!ready&&!waiting&&<small>Vous pouvez aussi passer cette étape sans lancer de calcul.</small>}
 </section></div>,document.body);
}
