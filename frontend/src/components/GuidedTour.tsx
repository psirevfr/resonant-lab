import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {GuideMascot} from './GuideMascot';

import {guideSteps as stops,type GuideStep} from '../guideContent';

export function GuidedTour({onEnd,onArea}:{onEnd:()=>void;onArea:(step:GuideStep)=>void}){
 const [step,setStep]=useState(0),[rect,setRect]=useState<{top:number;left:number;width:number;height:number}|null>(null);
 const card=useRef<HTMLElement>(null),current=stops[step];
 useEffect(()=>{onArea(current)},[current,onArea]);
 useEffect(()=>{
  let frame=0;
  let target=document.querySelector<HTMLElement>(`[data-workspace="${current.space}"] [data-guide="${current.target}"]`);
  target?.scrollIntoView({block:'center',behavior:'instant'});
  function update(){cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{
   const latest=document.querySelector<HTMLElement>(`[data-workspace="${current.space}"] [data-guide="${current.target}"]`);
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
 },[current]);
 useEffect(()=>{card.current?.focus()},[step]);
 useEffect(()=>{function escape(e:KeyboardEvent){if(e.key==='Escape')onEnd()};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape)},[onEnd]);
 const small=innerWidth<700;
 const cardStyle=rect&&!small?{top:rect.top>270?20:undefined,bottom:rect.top>270?undefined:20,left:rect.left>innerWidth/2?20:undefined,right:rect.left>innerWidth/2?undefined:20}:{};
 return createPortal(<div className="guided-tour">
 {rect?<><div className="tour-shade" style={{top:0,left:0,right:0,height:rect.top}}/><div className="tour-shade" style={{top:rect.top+rect.height,left:0,right:0,bottom:0}}/><div className="tour-shade" style={{top:rect.top,left:0,width:rect.left,height:rect.height}}/><div className="tour-shade" style={{top:rect.top,left:rect.left+rect.width,right:0,height:rect.height}}/><div className="tour-focus" style={rect}/></>:<div className="tour-shade" style={{inset:0}}/>}
 <section ref={card} tabIndex={-1} className="tour-coach" style={cardStyle} role="dialog" aria-modal="false" aria-labelledby="tour-title">
 <div className="tour-coach-heading"><GuideMascot/><b>Rémi · visite interactive</b><button onClick={onEnd} aria-label="Quitter la visite interactive">✕</button></div>
 <h2 id="tour-title" aria-live="polite">{current.title}</h2><p>{current.text}</p>
 <div className="guide-navigation"><button disabled={step===0} onClick={()=>setStep(s=>s-1)}>Précédent</button><span aria-label="Étape">{step+1} / {stops.length}</span><button onClick={()=>{if(step===stops.length-1)onEnd();else setStep(s=>s+1)}}>{step===stops.length-1?'Terminer':'Suivant →'}</button></div>
 </section></div>,document.body)
}
