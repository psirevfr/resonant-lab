import {useEffect,useRef,useState} from 'react';
import {Play,Pause,Square,Repeat,Volume2,Shuffle} from 'lucide-react';
type Source='original'|'model';
export function Player({originalUrl,modelUrl,onError}:{originalUrl?:string;modelUrl?:string;onError:(s:string)=>void}){
 const original=useRef<HTMLAudioElement>(null),model=useRef<HTMLAudioElement>(null);
 const [source,setSource]=useState<Source>('original'),[playing,setPlaying]=useState(false),[loop,setLoop]=useState(false),[volume,setVolume]=useState(.65),[time,setTime]=useState(0),[blind,setBlind]=useState(false),[swapped,setSwapped]=useState(false),[revealed,setRevealed]=useState(false);
 const sourceRef=useRef(source);sourceRef.current=source;
 const element=(s:Source)=>s==='original'?original.current:model.current;
 const url=source==='original'?originalUrl:modelUrl;
 useEffect(()=>{for(const a of [original.current,model.current]){a?.pause();a?.load()}setPlaying(false);setTime(0);setBlind(false);if(!originalUrl&&modelUrl)setSource('model')},[originalUrl,modelUrl]);
 useEffect(()=>{for(const a of [original.current,model.current])if(a)a.volume=volume},[volume]);
 function stop(){for(const a of [original.current,model.current])if(a){a.pause();a.currentTime=0}setTime(0);setPlaying(false)}
 async function change(next:Source){if(next===source)return;const from=element(source),to=element(next);const position=from?.currentTime??0;const resume=!!from&&!from.paused;from?.pause();setSource(next);sourceRef.current=next;
  if(to){try{to.currentTime=Math.min(position,Number.isFinite(to.duration)?Math.max(0,to.duration-.001):position);if(resume)await to.play()}catch(e){onError(String(e))}}
 }
 async function play(){const a=element(source);if(!a)return;if(a.paused){try{await a.play()}catch(e){onError(String(e))}}else a.pause()}
 const order:Source[]=blind&&swapped?['model','original']:['original','model'];
 return <div className="player">{(['original','model'] as Source[]).map(s=><audio key={s} ref={s==='original'?original:model} src={s==='original'?originalUrl:modelUrl} loop={loop} preload="auto" onPlay={()=>{if(sourceRef.current===s)setPlaying(true)}} onPause={()=>{if(sourceRef.current===s)setPlaying(false)}} onTimeUpdate={()=>{if(sourceRef.current===s)setTime(element(s)?.currentTime??0)}} onEnded={()=>{if(sourceRef.current===s)setPlaying(false)}} onError={()=>{if(s==='original'?originalUrl:modelUrl)onError('Lecture impossible ; régénérez le signal ou réimportez le WAV.')}}/>)}
 <div className="transport"><button className="play" disabled={!url} onClick={()=>void play()} aria-label={playing?'Pause':'Lire'}>{playing?<Pause size={18}/>:<Play size={18}/>}</button><button aria-label="Arrêter" onClick={stop}><Square size={14}/></button><button className={loop?'active':''} aria-label="Lecture en boucle" aria-pressed={loop} onClick={()=>setLoop(!loop)}><Repeat size={16}/></button><span className="timecode">{time.toFixed(2)} s</span></div>
 <div className="ab-switch">{order.map((s,i)=><button key={s} disabled={!(s==='original'?originalUrl:modelUrl)} className={source===s?'selected':''} onClick={()=>void change(s)}>{blind?(revealed?`${i?'B':'A'} · ${s==='original'?'Original':'Synthèse'}`:i?'B':'A'):s==='original'?'A · Original':'B · Synthèse'}</button>)}</div>
 <button className={`blind ${blind?'active':''}`} disabled={!originalUrl||!modelUrl} onClick={()=>{stop();const swap=Math.random()<.5;setBlind(!blind);setSwapped(swap);setRevealed(false);if(!blind)setSource(swap?'model':'original')}} title="Tirer au sort l’identité de A et B"><Shuffle size={14}/> Aveugle</button>{blind&&<button onClick={()=>setRevealed(!revealed)}>{revealed?'Masquer':'Révéler'}</button>}<div className="volume"><Volume2 size={15}/><input aria-label="Volume d’écoute" type="range" min="0" max="1" step=".01" value={volume} onChange={e=>setVolume(+e.target.value)}/></div>
 </div>
}
