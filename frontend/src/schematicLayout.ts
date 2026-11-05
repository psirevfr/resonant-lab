import {pins,type Part,type CircuitProject} from './circuitProject';
export type Point={x:number;y:number};
export type Side='left'|'right'|'top'|'bottom';
export type Terminal=Point&{id:string;side:Side};
export type SymbolLayout={width:number;height:number;terminals:Terminal[];rotation:number;baseWidth:number;baseHeight:number};
const terminal=(id:string,x:number,y:number,side:Side):Terminal=>({id,x,y,side});
export function symbolLayout(part:Part):SymbolLayout{
 let width=128,height=128,ts:Terminal[];const names=pins(part);
 if(part.type==='junction'){width=height=16;ts=[terminal('0',0,0,'right')]}
 else if(part.type==='ground'){width=height=64;ts=[terminal('0',32,0,'top')]}
 else if(['voltage','capacitor','electrolytic'].includes(part.type))ts=[terminal(names[0],64,0,'top'),terminal(names[1],64,128,'bottom')];
 else if(part.type==='potentiometer')ts=[terminal('1',0,80,'left'),terminal('W',64,0,'top'),terminal('3',128,80,'right')];
 else if(part.type==='npn')ts=[terminal('B',0,64,'left'),terminal('C',128,16,'top'),terminal('E',128,112,'bottom')];
 else if(part.type==='nmos')ts=[terminal('G',0,64,'left'),terminal('D',128,16,'top'),terminal('S',128,112,'bottom')];
 else if(part.type==='button')ts=[terminal('1a',0,32,'left'),terminal('1b',0,96,'left'),terminal('2a',128,32,'right'),terminal('2b',128,96,'right')];
 else if(part.type==='switch')ts=[terminal('1',128,32,'right'),terminal('C',0,64,'left'),terminal('2',128,96,'right')];
 else if(part.type==='tmp36')ts=[terminal('V+',0,32,'left'),terminal('OUT',128,64,'right'),terminal('GND',0,96,'left')];
 else if(names.length===2)ts=[terminal(names[0],0,64,'left'),terminal(names[1],128,64,'right')];
 else {width=192;height=Math.max(128,(Math.ceil(names.length/2)+2)*16);const half=Math.ceil(names.length/2);ts=names.map((pin,i)=>terminal(pin,i<half?0:width,(i<half?i:i-half)*16+32,i<half?'left':'right'))}
 const baseWidth=width,baseHeight=height,rotation=part.type==='junction'?0:part.schematicRotation??0;
 if(rotation===90||rotation===270)[width,height]=[height,width];
 const sides:Side[]=['top','right','bottom','left'];
 ts=ts.map(t=>{const x=t.x-baseWidth/2,y=t.y-baseHeight/2,a=rotation*Math.PI/180;return {...t,x:Math.round(width/2+x*Math.cos(a)-y*Math.sin(a)),y:Math.round(height/2+x*Math.sin(a)+y*Math.cos(a)),side:sides[(sides.indexOf(t.side)+rotation/90)%4]}});
 return {width,height,terminals:ts,rotation,baseWidth,baseHeight};
}
export {designators} from './componentReference';
const vector:Record<Side,Point>={left:{x:-16,y:0},right:{x:16,y:0},top:{x:0,y:-16},bottom:{x:0,y:16}};
export type Obstacle={x:number;y:number;width:number;height:number};
export function orthogonalRoute(a:Point,b:Point,sideA:Side,sideB:Side,obstacles:Obstacle[]=[]):Point[]{
 const s={x:a.x+vector[sideA].x,y:a.y+vector[sideA].y},t={x:b.x+vector[sideB].x,y:b.y+vector[sideB].y};
 const candidates:Point[][]=[...(Math.abs(a.x-b.x)<.01?[[a,{x:a.x,y:b.y},b]]:Math.abs(a.y-b.y)<.01?[[a,{x:b.x,y:a.y},b]]:[]),[a,s,{x:t.x,y:s.y},t,b],[a,s,{x:s.x,y:t.y},t,b]];
 const xs=[Math.round((s.x+t.x)/32)*16,Math.min(s.x,t.x)-32,Math.max(s.x,t.x)+32,...obstacles.flatMap(o=>[o.x-16,o.x+o.width+16])],ys=[Math.round((s.y+t.y)/32)*16,Math.min(s.y,t.y)-32,Math.max(s.y,t.y)+32,...obstacles.flatMap(o=>[o.y-16,o.y+o.height+16])];
 for(const x of xs)candidates.push([a,s,{x,y:s.y},{x,y:t.y},t,b]);for(const y of ys)candidates.push([a,s,{x:s.x,y},{x:t.x,y},t,b]);
 const compact=(points:Point[])=>points.filter((p,i)=>!i||p.x!==points[i-1].x||p.y!==points[i-1].y);
 const score=(points:Point[])=>points.reduce((score,p,i)=>{if(!i)return score;const q=points[i-1];return score+Math.abs(p.x-q.x)+Math.abs(p.y-q.y)+obstacles.filter(o=>p.x===q.x?p.x>o.x&&p.x<o.x+o.width&&Math.max(p.y,q.y)>o.y&&Math.min(p.y,q.y)<o.y+o.height:p.y>o.y&&p.y<o.y+o.height&&Math.max(p.x,q.x)>o.x&&Math.min(p.x,q.x)<o.x+o.width).length*100000},points.length*8);
 return candidates.map(compact).sort((a,b)=>score(a)-score(b))[0];
}
export const routePath=(points:Point[])=>points.map((p,i)=>(i?'L':'M')+p.x+','+p.y).join(' ');

/** An explicit display operation. Never alters wires or physical placement. */
export function arrangeSchematic(p:CircuitProject):CircuitProject{
 const source=p.parts.find(p=>p.type==='voltage'),ground=p.parts.find(p=>p.type==='ground'),passives=p.parts.filter(p=>['resistor','capacitor','led'].includes(p.type));
 if(p.parts.length===4&&source&&ground&&passives.length===2){const positions:Record<string,Point&{schematicRotation:number}>={[source.id]:{x:64,y:128,schematicRotation:0},[passives[0].id]:{x:256,y:64,schematicRotation:0},[passives[1].id]:{x:448,y:128,schematicRotation:passives[1].type==='capacitor'?0:90},[ground.id]:{x:288,y:256,schematicRotation:0}};return {...p,parts:p.parts.map(part=>({...part,...positions[part.id]}))}}
 return {...p,parts:p.parts.map((part,i)=>({...part,x:64+(i%4)*256,y:96+Math.floor(i/4)*336}))};
}
