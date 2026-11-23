import {useEffect,useRef,useState} from 'react';
import {api} from '../api';
import {consentPath,type LearningConsent,type LearningDecision} from '../acousticLearning';
import {withDeadline} from '../requestDeadline';

type ConsentState={owner:number;value:LearningConsent|null};

export function useLearningConsent(owner:number|undefined){
 const [state,setState]=useState<ConsentState>();
 const [retry,setRetry]=useState(0);
 const [editing,setEditing]=useState(false),[saving,setSaving]=useState(false);
 const [error,setError]=useState('');
 const current=useRef<AbortController|null>(null);
 const savingRequest=useRef(false);

 useEffect(()=>{
  const controller=new AbortController();
  current.current=controller;
  savingRequest.current=false;
  setEditing(false);setSaving(false);setError('');
  if(owner!==undefined){
   setState(undefined);
   void withDeadline(controller.signal,signal=>api<LearningConsent>(consentPath,undefined,signal))
    .then(value=>{if(!controller.signal.aborted)setState({owner,value});})
    .catch(()=>{if(!controller.signal.aborted)setState({owner,value:null});});
  }
  return ()=>controller.abort();
 },[owner,retry]);

 const ready=owner!==undefined&&state?.owner===owner;
 const value=ready?state?.value:null;
 async function choose(decision:LearningDecision){
  const controller=current.current;
  if(owner===undefined||!value||!controller||savingRequest.current)return;
  savingRequest.current=true;setSaving(true);setError('');
  try{
   const next=await withDeadline(controller.signal,signal=>api<LearningConsent>(consentPath,{version:value.version,decision},signal));
   if(!controller.signal.aborted){setState({owner,value:next});setEditing(false);}
  }catch{
   if(!controller.signal.aborted)setError('Le choix n’a pas pu être confirmé. Réessayez.');
  }finally{
   if(!controller.signal.aborted){savingRequest.current=false;setSaving(false);}
  }
 }
 return {
  decision:value?.decision??null, ready, unavailable:ready&&!value, saving, error,
  open:!!value&&(value.decision===null||editing), choose,
  toggle:()=>{setError('');setEditing(value=>!value);},
  reload:()=>setRetry(value=>value+1),
 };
}
