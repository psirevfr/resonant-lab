import {pins,type CircuitProject,type Pin} from './circuitProject';

export const samePin=(a:Pin,b:Pin)=>a.component===b.component&&a.pin===b.pin;

/** A draft is UI state. Only two distinct, validated contacts create a wire. */
export function cableStep(project:CircuitProject,anchor:Pin|null,target:Pin,restart=false):{anchor:Pin|null;connection?:[Pin,Pin]} {
 const valid=(pin:Pin)=>{const part=project.parts.find(p=>p.id===pin.component);return !!part&&pins(part).includes(pin.pin)};
 if(!valid(target))throw Error('Point de connexion inconnu.');
 if(restart||!anchor||!valid(anchor))return {anchor:target};
 if(samePin(anchor,target))return {anchor};
 if(project.wires.some(w=>samePin(w.from,anchor)&&samePin(w.to,target)||samePin(w.to,anchor)&&samePin(w.from,target)))throw Error('Ces deux points sont déjà reliés.');
 if(project.wires.length>=200)throw Error('Limite : 200 fils.');
 return {anchor:null,connection:[anchor,target]};
}

/** Defer a wiring click so a native double click never commits its first half. */
export function pinGestures(choose:(pin:Pin)=>void,start:(pin:Pin)=>void,schedule=(fn:()=>void)=>setTimeout(fn,280),cancel=(id:ReturnType<typeof setTimeout>)=>clearTimeout(id)) {
 let timer:ReturnType<typeof setTimeout>|undefined;
 const clear=()=>{if(timer!==undefined){cancel(timer);timer=undefined}};
 return {
  click(pin:Pin,mode:string,detail=1){if(detail===0){clear();if(mode==='wire')choose(pin);else start(pin);return}if(mode!=='wire'||detail>1)return;clear();timer=schedule(()=>{timer=undefined;choose(pin)})},
  doubleClick(pin:Pin){clear();start(pin)},
  dispose:clear,
 };
}
