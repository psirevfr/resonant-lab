import {contactGroup,pins,type CircuitProject,type Pin} from './circuitProject';

export const pinKey=(p:Pin)=>JSON.stringify([p.component,p.pin]);
export const isSupport=(p:{type:string})=>p.type==='breadboard'||p.type==='breadboard830';

/** Electrical membership only. Display coordinates never create connections. */
export function connectivity(p:CircuitProject){
 const parent=new Map<string,string>();
 function root(k:string):string{if(!parent.has(k))parent.set(k,k);const r=parent.get(k)!;if(r!==k)parent.set(k,root(r));return parent.get(k)!}
 const union=(a:string,b:string)=>parent.set(root(a),root(b));
 const key=(id:string,pin:string)=>pinKey({component:id,pin});
 for(const part of p.parts){for(const pin of pins(part))root(key(part.id,pin));
  if(part.type==='ground')union(key(part.id,'0'),'ground');
  if(isSupport(part))for(const pin of pins(part))union(key(part.id,pin),JSON.stringify([part.id,'bus',contactGroup(pin,part.railSplit)]));
  if(part.type==='button'){union(key(part.id,'1a'),key(part.id,'1b'));union(key(part.id,'2a'),key(part.id,'2b'))}
 }
 for(const part of p.parts)if(part.mount)for(const [pin,hole] of Object.entries(part.mount.pins))union(key(part.id,pin),key(part.mount.board,hole));
 for(const w of p.wires)union(pinKey(w.from),pinKey(w.to));
 const groups=new Map<string,Pin[]>();
 for(const part of p.parts)if(!isSupport(part))for(const pin of pins(part)){const r=root(key(part.id,pin));if(!groups.has(r))groups.set(r,[]);groups.get(r)!.push({component:part.id,pin})}
 return {root:(p:Pin)=>root(pinKey(p)),groups:[...groups.values()]};
}

/** Stable partition of business pins: allows comparison across board placement. */
export function electricalSignature(p:CircuitProject){
 return JSON.stringify({parts:p.parts.filter(a=>!isSupport(a)).map(a=>[a.id,a.type]).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b))),nets:connectivity(p).groups.map(net=>net.map(pinKey).sort()).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)))});
}
