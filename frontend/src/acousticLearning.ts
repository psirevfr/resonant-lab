import {api,ApiError} from './api';
import {withDeadline} from './requestDeadline';

const profiles=['transient','sustained','decaying'] as const;
const strategies=['adsr','decay'] as const;
type Profile=typeof profiles[number];
type Strategy=typeof strategies[number];
export interface AcousticTrial {
 version:1;
 clip:string;
 profile:Profile;
 strategy:Strategy;
 reward:number;
 accepted:boolean;
}
type Score={count:number;reward:number};
type History=Partial<Record<Profile,Partial<Record<Strategy,Score>>>>;
export type CollectiveHistory=Partial<Record<Profile,Partial<Record<Strategy,{contributors:number;mean:number}>>>>;
export interface AcousticHint {version:1;history:History;community?:CollectiveHistory;explore?:true}
export type LearningDecision='accepted'|'refused';
export interface LearningConsent {version:number;decision:LearningDecision|null}
export const consentPath='/acoustic-learning/consent';
const limit=128;
const prefix='resonant-acoustic-learning-v1:';

function isTrial(value:unknown):value is AcousticTrial {
 if(!value||typeof value!=='object')return false;
 const t=value as AcousticTrial;
 return t.version===1&&typeof t.clip==='string'&&/^(44100|48000|96000):[a-f0-9]{64}$/.test(t.clip)
  &&profiles.includes(t.profile)&&strategies.includes(t.strategy)
  &&typeof t.reward==='number'&&Number.isFinite(t.reward)&&t.reward>=0&&t.reward<=1
  &&typeof t.accepted==='boolean'&&t.accepted===(t.reward>0);
}
function trials(owner:number):AcousticTrial[]{
 try{
  const stored=localStorage.getItem(prefix+owner);
  if(!stored||stored.length>50_000)return [];
  const value:unknown=JSON.parse(stored);
  if(!Array.isArray(value))return [];
  const unique=new Map<string,AcousticTrial>();
  for(const t of value.slice(-limit).filter(isTrial))unique.set(t.clip+':'+t.strategy,t);
  return [...unique.values()];
 }catch{return [];}
}
export function acousticEnabled(owner:number):boolean{
 try{return localStorage.getItem(prefix+'enabled:'+owner)==='1';}catch{return false;}
}
export function setAcousticEnabled(owner:number, enabled:boolean){
 if(enabled)localStorage.setItem(prefix+'enabled:'+owner,'1');
 else localStorage.removeItem(prefix+'enabled:'+owner);
}
export function acousticHint(owner:number, collective:CollectiveHistory={}, explore=false):AcousticHint{
 const history:History={};
 for(const {profile,strategy,reward} of acousticEnabled(owner)?trials(owner):[]){
  const row=history[profile]??={};
  const score=row[strategy]??={count:0,reward:0};
  score.count++;
  score.reward+=reward;
 }
 const community:CollectiveHistory={};
 for(const profile of profiles)for(const strategy of strategies){
  const prior=collective[profile]?.[strategy];
  if(!prior||!Number.isInteger(prior.contributors)||prior.contributors<5||!Number.isFinite(prior.mean)||prior.mean<=0||prior.mean>1)continue;
  (community[profile]??={})[strategy]={contributors:prior.contributors,mean:prior.mean};
 }
 return {version:1,history,...(Object.keys(community).length?{community}:{}),...(explore?{explore:true}:{})};
}
export function recordAcousticTrial(owner:number,value:unknown){
 if(!acousticEnabled(owner)||!isTrial(value))return;
 const records=trials(owner);
 if(records.some(t=>t.clip===value.clip&&t.strategy===value.strategy))return;
 const {version,clip,profile,strategy,reward,accepted}=value;
 const record={version,clip,profile,strategy,reward,accepted};
 try{localStorage.setItem(prefix+owner,JSON.stringify([...records,record].slice(-limit)));}
 catch{/* The model is still usable when local storage is full or unavailable. */}
}
export function acousticTrialCount(owner:number):number{return trials(owner).length;}
export function clearAcousticTrials(owner:number){localStorage.removeItem(prefix+owner);}

export function contribution(ticket:string,value:unknown){
 return isTrial(value)&&value.accepted?{ticket,profile:value.profile,strategy:value.strategy,reward:value.reward}:null;
}

export async function sendContribution(report:NonNullable<ReturnType<typeof contribution>>,signal:AbortSignal){
 for(const delay of [0,1000,4000]){
  if(delay)await new Promise<void>(resolve=>setTimeout(resolve,delay));
  if(signal.aborted)return;
  try{
   await withDeadline(signal,attempt=>api('/acoustic-learning',report,attempt),8000);
   return;
  }catch(error){
   if(error instanceof ApiError&&error.status<500)return;
  }
 }
}
