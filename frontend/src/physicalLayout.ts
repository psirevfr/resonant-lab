import {footprintGrid} from './componentExtras';
import {pinOffset,pinPoint,pins,type CircuitProject,type Part,type Pin} from './circuitProject';
export const isBoard=(p:Part)=>p.type==='breadboard'||p.type==='breadboard830';
export const mountable=(p:Part)=>!!footprintGrid(p.type);
export const leadColumns=(p:Part)=>Math.max(...(footprintGrid(p.type)??[[0,0]]).map(p=>p[0]));
export function pose(project:CircuitProject,part:Part){
 if(part.mount){const board=project.parts.find(p=>p.id===part.mount!.board);if(board&&isBoard(board)){const ends=Object.values(part.mount.pins).map(pin=>pinPoint(board,pin));return {x:ends.reduce((s,v)=>s+v[0],0)/ends.length,z:ends.reduce((s,v)=>s+v[1],0)/ends.length,rotation:board.rotation,y:board.type==='breadboard830'?8.5:5}}}
 let height=0;if(mountable(part))for(const board of project.parts.filter(isBoard)){const a=-board.rotation*Math.PI/180,dx=part.px-board.px,dz=part.z-board.z,x=dx*Math.cos(a)-dz*Math.sin(a),z=dx*Math.sin(a)+dz*Math.cos(a);if(Math.abs(x)<(board.type==='breadboard830'?82.5:15.5)&&Math.abs(z)<(board.type==='breadboard830'?27.3:21.5))height=Math.max(height,board.type==='breadboard830'?8.5:5)}return {x:part.px,z:part.z,rotation:part.rotation,y:height};
}
export function physicalPin(project:CircuitProject,part:Part,pin:string):[number,number,number]{
 const p=pose(project,part);if(part.mount?.pins[pin]){const board=project.parts.find(b=>b.id===part.mount!.board)!;const q=pinPoint(board,part.mount.pins[pin]);return [q[0],p.y+.3,q[1]]}
 const [x,z]=pinOffset(part,pin),a=p.rotation*Math.PI/180;return [p.x+x*Math.cos(a)-z*Math.sin(a),p.y+(isBoard(part)?(part.type==='breadboard830'?8.5:5):part.type==='uno'?9.9:part.type==='teensy41'||part.type==='audioShield'?5:0.4),p.z+x*Math.sin(a)+z*Math.cos(a)];
}
export function mountOnBoard(project:CircuitProject,id:string,boardId:string,row='a',column=20):CircuitProject{
 const part=project.parts.find(p=>p.id===id),board=project.parts.find(p=>p.id===boardId);if(!part||!board||!isBoard(board)||!mountable(part)||!/^[a-j]$/.test(row)||!Number.isInteger(column))throw Error('Insertion non compatible.');
 const pattern=footprintGrid(part.type)!,ends=pins(part),rowIndex='abcdefghij'.indexOf(row);const contacts=pattern.map(([x,z])=>'abcdefghij'[rowIndex+z]+(column+x));if(contacts.some(pin=>!pins(board).includes(pin)))throw Error('Les pattes doivent rester sur la platine.');
 const start=pinOffset(board,contacts[0]),origin=pinOffset(part,ends[0]);for(let i=0;i<ends.length;i++){const point=pinOffset(board,contacts[i]),offset=pinOffset(part,ends[i]);if(Math.abs(point[0]-start[0]-offset[0]+origin[0])>1e-6||Math.abs(point[1]-start[1]-offset[1]+origin[1])>1e-6)throw Error('Écartement incompatible : un DIP se place sur les rangées E/F.');}
 const occupied=new Set(project.parts.filter(p=>p.id!==id&&p.mount?.board===boardId).flatMap(p=>Object.values(p.mount!.pins)));if(contacts.some(pin=>occupied.has(pin)))throw Error('Un trou est déjà occupé par une patte.');
 return {...project,parts:project.parts.map(p=>p.id===id?{...p,mount:{board:boardId,pins:Object.fromEntries(ends.map((pin,i)=>[pin,contacts[i]]))}}:p)};
}
export function unmount(project:CircuitProject,id:string):CircuitProject{return {...project,parts:project.parts.map(p=>{if(p.id!==id||!p.mount)return p;const q=pose(project,p),{mount:_,...rest}=p;return {...rest,px:q.x,z:q.z,rotation:q.rotation}})}}
export function movePart(project:CircuitProject,id:string,x:number,z:number):CircuitProject{const free=unmount(project,id);return {...free,parts:free.parts.map(p=>p.id===id?{...p,px:x,z}:p)}}
export function nearestMount(project:CircuitProject,id:string,boardId:string){const part=project.parts.find(p=>p.id===id)!,board=project.parts.find(p=>p.id===boardId)!;const q=pose(project,part);let best:{pin:string;distance:number}|null=null;for(const pin of pins(board).filter(p=>/^[a-j]\d+$/.test(p))){const [x,z]=pinPoint(board,pin),distance=(q.x-x)**2+(q.z-z)**2;if(!best||distance<best.distance)best={pin,distance}}const [,row,col]=/^([a-j])(\d+)$/.exec(best!.pin)!;return {row:part.type==='opamp'?'e':part.type==='button'?(row<='e'?(row>'c'?'c':row):(row>'h'?'h':row)):row,column:Math.max(1,Math.min(board.type==='breadboard830'?63-leadColumns(part):10-leadColumns(part),Number(col)-Math.floor(leadColumns(part)/2)))}}
export function endpointLabel(project:CircuitProject,endpoint:Pin){const part=project.parts.find(p=>p.id===endpoint.component);return (part?.label??'?')+' · '+endpoint.pin}
