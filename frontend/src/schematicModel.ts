import {contactGroup,definitions,newPart,pins,physicalProject,validateProject,type Assembly,type CircuitProject,type Part,type Pin,type Wire} from './circuitProject';
import {connectivity,electricalSignature,isSupport,pinKey} from './circuitConnectivity';
import {footprintGrid} from './componentExtras';
import {mountOnBoard,unmount} from './physicalLayout';

function logicalWires(physical:CircuitProject,parts:Part[],previous:Wire[]):Wire[]{
 const intrinsic=connectivity({...physical,parts,wires:[],assembly:undefined});
 const wires:Wire[]=[];
 for(const net of connectivity(physical).groups){const seen=new Set<string>(),ends=net.filter(pin=>{const r=intrinsic.root(pin);if(seen.has(r))return false;seen.add(r);return true});
  for(const target of ends.slice(1)){const source=ends[0],old=previous.find(w=>pinKey(w.from)===pinKey(source)&&pinKey(w.to)===pinKey(target)||pinKey(w.to)===pinKey(source)&&pinKey(w.from)===pinKey(target));wires.push(old??{id:crypto.randomUUID(),from:source,to:target})}
 }
 return wires;
}
function assemblyOf(physical:CircuitProject,signature:string):Assembly{
 return {version:1,signature,boards:physical.parts.filter(isSupport),placements:physical.parts.filter(p=>!isSupport(p)).map(p=>({id:p.id,px:p.px,z:p.z,rotation:p.rotation,...(p.mount?{mount:p.mount}:{})})),wires:physical.wires};
}
/** Explicit migration: preserve the previous board wiring as a linked layout. */
export function makeSchematic(input:CircuitProject):CircuitProject{
 const p=validateProject(input);if(p.assembly||!p.parts.some(p=>isSupport(p)||p.mount))return p;
 let free=p;for(const part of p.parts)if(part.mount)free=unmount(free,part.id);
 const parts=free.parts.filter(p=>!isSupport(p));
 const result={...p,parts,wires:logicalWires(p,parts,p.wires)};
 if(electricalSignature(result)!==electricalSignature(p))throw Error('Le schéma extrait ne conserve pas les réseaux.');
 return validateProject({...result,assembly:assemblyOf(p,electricalSignature(result))});
}
/** A physical wiring edit changes the same logical circuit, never a second copy. */
export function syncPhysicalEdit(logical:CircuitProject,physical:CircuitProject):CircuitProject{
 if(!logical.assembly)return validateProject(physical);
 const valid=validateProject(physical);if(electricalSignature(valid)===electricalSignature(logical))return validateProject({...logical,assembly:assemblyOf(valid,electricalSignature(logical))});let free=valid;for(const p of valid.parts)if(p.mount)free=unmount(free,p.id);
 const parts=free.parts.filter(p=>!isSupport(p)).map(p=>{const previous=logical.parts.find(q=>q.id===p.id);return {...p,...(previous?{x:previous.x,y:previous.y,schematicRotation:previous.schematicRotation}:{})}});
 const result={...logical,source:valid.source,parts,wires:logicalWires(valid,parts,logical.wires),assembly:undefined};
 return validateProject({...result,assembly:assemblyOf(valid,electricalSignature(result))});
}
export function assemblyCurrent(p:CircuitProject){return !!p.assembly&&p.assembly.signature===electricalSignature(p)&&electricalSignature(physicalProject(p))===electricalSignature(p)}

/** Never display a schematic calculation as a measurement of a stale layout. */
export function circuitForSimulation(p:CircuitProject,physical=false){
 if(!physical)return p;
 if(!assemblyCurrent(p))throw Error('Actualisez l’implantation depuis le schéma avant de simuler le montage 3D.');
 return physicalProject(p);
}

/** Deterministic placement and star buses, followed by a full connectivity proof.
 * No optimisation of wire length or manufacturer enclosure fit is claimed. */
export function createAssembly(input:CircuitProject):{project:CircuitProject;mounted:number;boards:number;wires:number;warnings:string[]}{
 const p=makeSchematic(input),{assembly:_,...base}=p;
 if(!base.parts.length)throw Error('Ajoutez des composants au schéma.');
 let physical:CircuitProject={...base,parts:base.parts.map(p=>({...p,mount:undefined})),wires:[]};
 let board:Part|undefined,column=3;const boards:Part[]=[];let mounted=0,external=0;
 function reserve(width:number){if(!board||column+width>62){if(physical.parts.length>=48)throw Error('Pas assez de place pour ajouter une platine (limite de 48 éléments physiques).');board=newPart('breadboard830',boards.length);board.label='BB'+(boards.length+1)+' · Platine 830';board.px=(boards.length%2)*190;board.z=Math.floor(boards.length/2)*90;boards.push(board);physical.parts.push(board);column=3}const slot={board:board!,column};column+=width+3;return slot}
 physical.parts.forEach((part,index)=>{if(isSupport(part))return;const pattern=footprintGrid(part.type);if(pattern){const slot=reserve(Math.max(...pattern.map(p=>p[0])));physical=mountOnBoard(physical,part.id,slot.board.id,part.type==='opamp'?'e':'c',slot.column);mounted++}else{part.px=-115-(Math.floor(external/4)*80);part.z=-25+(external++%4)*35;part.rotation=0}});
 const occupied=new Set(physical.parts.flatMap(p=>p.mount?Object.values(p.mount.pins).map(h=>p.mount!.board+':'+h):[]));
 const intrinsic=connectivity(physical),colorFor=(net:Pin[],i:number)=>net.some(pin=>p.parts.some(p=>p.id===pin.component&&p.type==='ground'))?'#424a4b':net.some(pin=>pin.pin==='+'&&p.parts.some(p=>p.id===pin.component&&p.type==='voltage'))?'#d65345':['#d4c265','#6db2bc','#9bb57c','#b69bc6'][i%4];
 const spare=(pin:Pin)=>{const part=physical.parts.find(p=>p.id===pin.component);if(!part?.mount)return [];const b=physical.parts.find(b=>b.id===part.mount!.board)!,group=contactGroup(part.mount.pins[pin.pin],b.railSplit);return pins(b).filter(h=>contactGroup(h,b.railSplit)===group).map(h=>({component:b.id,pin:h})).filter(h=>!occupied.has(h.component+':'+h.pin))};
 const available=(b:Part,col:number)=>[...'abcde'].map(r=>({component:b.id,pin:r+col})).filter(e=>!occupied.has(e.component+':'+e.pin));
 const take=(contacts:Pin[])=>{const endpoint=contacts.shift();if(!endpoint)throw Error('Contacts de liaison insuffisants.');occupied.add(endpoint.component+':'+endpoint.pin);return endpoint};
 const terminal=(pin:Pin)=>{const part=physical.parts.find(p=>p.id===pin.component)!;if(!part.mount)return pin;const b=physical.parts.find(b=>b.id===part.mount!.board)!,group=contactGroup(part.mount.pins[pin.pin],b.railSplit);const contacts=pins(b).filter(h=>contactGroup(h,b.railSplit)===group).map(h=>({component:b.id,pin:h})).filter(h=>!occupied.has(h.component+':'+h.pin));return take(contacts)};
 const addWire=(from:Pin,to:Pin,color:string)=>{if(physical.wires.length>=200)throw Error('Implantation trop complexe : plus de 200 liaisons.');physical.wires.push({id:crypto.randomUUID(),from,to,color})};
 connectivity(base).groups.forEach((net,index)=>{const seen=new Set<string>(),ends=net.filter(pin=>{const r=intrinsic.root(pin);if(seen.has(r))return false;seen.add(r);return true});if(ends.length<2)return;const color=colorFor(net,index);if(ends.length===2){addWire(terminal(ends[0]),terminal(ends[1]),color);return}const center=ends.find(pin=>spare(pin).length>=ends.length-1);if(center){const hub=spare(center);for(const pin of ends)if(pin!==center)addWire(terminal(pin),take(hub),color);return}let slot=reserve(0),hub=available(slot.board,slot.column);ends.forEach((pin,i)=>{if(hub.length===1&&i<ends.length-1){slot=reserve(0);const next=available(slot.board,slot.column);addWire(take(hub),take(next),color);hub=next}addWire(terminal(pin),take(hub),color)})});
 physical=validateProject(physical);
 const signature=electricalSignature(base);if(electricalSignature(physical)!==signature)throw Error('Implantation refusée : un réseau a été modifié.');
 const project=validateProject({...base,assembly:assemblyOf(physical,signature)});
 const warnings=[...new Set(base.parts.filter(part=>definitions[part.type].status==='visuel uniquement').map(part=>part.label+' : implantation seulement, comportement non émulé.'))];
 return {project,mounted,boards:boards.length,wires:physical.wires.length,warnings};
}

export function splitSchematicWire(project:CircuitProject,id:string,x:number,y:number):CircuitProject{
 const wire=project.wires.find(w=>w.id===id);if(!wire)throw Error('Fil de schéma inconnu.');if(project.parts.length>=47||project.wires.length>=200)throw Error('Limite du montage atteinte.');
 const part=newPart('junction',project.parts.length);part.label='J'+(project.parts.filter(p=>p.type==='junction').length+1);part.x=Math.round(x/16)*16;part.y=Math.round(y/16)*16;const joint={component:part.id,pin:'0'};
 return validateProject({...project,parts:[...project.parts,part],wires:project.wires.flatMap(w=>w.id===id?[{...w,to:joint},{...w,id:crypto.randomUUID(),from:joint}]:[w])});
}
