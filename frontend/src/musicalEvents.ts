export type MusicalEvent={source:string;channel:number;type:'on'|'off'|'sustain'|'bend'|'allOff';note?:number;value:number};
export type Voice={key:string;token:number;source:string;channel:number;note:number;velocity:number;held:boolean;bend:number};
export function midiEvent(source:string,data:ArrayLike<number>):MusicalEvent|null{const status=data[0],kind=status&240,channel=status&15,n=data[1],v=data[2];if(!Number.isInteger(status)||status<128||status>=240||data.length<3||!Number.isInteger(n)||n<0||n>127||!Number.isInteger(v)||v<0||v>127)return null;if(kind===144||kind===128)return {source,channel,type:kind===144&&v>0?'on':'off',note:n,value:v};if(kind===176){if(n===64)return {source,channel,type:'sustain',value:v};if(n===120||n===123)return {source,channel,type:'allOff',value:0}}if(kind===224)return {source,channel,type:'bend',value:((v<<7)|n)-8192};return null}
export class MusicalRouter{
 voices=new Map<string,Voice>();private sustain=new Map<string,boolean>();private bends=new Map<string,number>();private serial=0;
 constructor(private callbacks:{start:(v:Voice)=>void;stop:(v:Voice,immediate:boolean)=>void;bend:(v:Voice)=>void;changed:(voices:Voice[])=>void},private maxVoices=8){}
 dispatch(e:MusicalEvent){if(!Number.isInteger(e.channel)||e.channel<0||e.channel>15||!Number.isFinite(e.value))return;const scope=e.source+':'+e.channel;const key=scope+':'+e.note;
  if(e.type==='on'){if(!Number.isInteger(e.note)||e.note!<0||e.note!>127||e.value<1||e.value>127)return;const old=this.voices.get(key);if(old)this.callbacks.stop(old,true);this.voices.delete(key);if(this.voices.size>=this.maxVoices){const first=this.voices.values().next().value!;this.callbacks.stop(first,true);this.voices.delete(first.key)}const voice:Voice={key,token:++this.serial,source:e.source,channel:e.channel,note:e.note!,velocity:e.value,held:true,bend:this.bends.get(scope)??0};this.voices.set(key,voice);this.callbacks.start(voice)}
  else if(e.type==='off'){const v=this.voices.get(key);if(v){v.held=false;if(!this.sustain.get(scope))this.release(v,false)}}
  else if(e.type==='sustain'){this.sustain.set(scope,e.value>=64);if(e.value<64)for(const v of [...this.voices.values()])if(v.source===e.source&&v.channel===e.channel&&!v.held)this.release(v,false)}
  else if(e.type==='bend'){const cents=Math.max(-8192,Math.min(8191,e.value))/8192*200;this.bends.set(scope,cents);for(const v of this.voices.values())if(v.source===e.source&&v.channel===e.channel){v.bend=cents;this.callbacks.bend(v)}}
  else {for(const v of [...this.voices.values()])if(v.source===e.source&&v.channel===e.channel)this.release(v,true);this.sustain.delete(scope);this.bends.delete(scope)}
  this.callbacks.changed([...this.voices.values()]);
 }
 private release(v:Voice,immediate:boolean){this.voices.delete(v.key);this.callbacks.stop(v,immediate)}
 active(v:Voice){return this.voices.get(v.key)?.token===v.token}
 finish(v:Voice){if(this.active(v)){this.voices.delete(v.key);this.callbacks.changed([...this.voices.values()])}}
 stopSource(source:string){for(const v of [...this.voices.values()])if(v.source===source)this.release(v,true);for(const key of this.sustain.keys())if(key.startsWith(source+':'))this.sustain.delete(key);for(const key of this.bends.keys())if(key.startsWith(source+':'))this.bends.delete(key);this.callbacks.changed([...this.voices.values()])}
 stop(){for(const v of [...this.voices.values()])this.release(v,true);this.sustain.clear();this.bends.clear();this.callbacks.changed([])}
}
