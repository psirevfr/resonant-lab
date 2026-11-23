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
export interface AcousticHint {version:1;history:History}
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
export function acousticHint(owner:number):AcousticHint{
 const history:History={};
 for(const {profile,strategy,reward} of trials(owner)){
  const row=history[profile]??={};
  const score=row[strategy]??={count:0,reward:0};
  score.count++;
  score.reward+=reward;
 }
 return {version:1,history};
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
