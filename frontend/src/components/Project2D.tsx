import {useEffect,useMemo,useRef,useState} from 'react';
import {ReactFlow,Handle,Position,Background,BackgroundVariant,Controls,ConnectionMode,applyNodeChanges,useReactFlow,type Node,type NodeProps,type Connection,type EdgeProps,type Edge} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {definitions,type CircuitProject,type Part,type Pin} from '../circuitProject';
import {pinGestures} from '../cableInteraction';
import {pinKey} from '../circuitConnectivity';
import {designators,symbolLayout,orthogonalRoute,routePath,type Side} from '../schematicLayout';
import {engineeringValue} from '../hardwareCatalog';
import type {InteractionMode} from './Project3D';
import SchematicSymbol from './SchematicSymbol';
type Data={part:Part;reference:string;degree:Record<string,number>;onPin:(p:Pin,detail:number)=>void;onStartWire:(p:Pin)=>void;pending:Pin|null};
type PartNode=Node<Data>;
const positions:Record<Side,Position>={left:Position.Left,right:Position.Right,top:Position.Top,bottom:Position.Bottom};
function SymbolNode({data,selected}:NodeProps<PartNode>){
 const p=data.part,l=symbolLayout(p),name=p.label===definitions[p.type].name?data.reference:p.label;
 return <div className={'schematic-component kind-'+p.type+' '+(selected?'chosen ':'')+(p.type==='junction'?'schematic-junction':'')} style={{width:l.width,height:l.height}}>
  <SchematicSymbol part={p}/>{p.type==='junction'&&<span className="junction-name">{name}</span>}{p.type!=='junction'&&<div className="schematic-caption"><b>{name}</b>{definitions[p.type].unit&&<span>{engineeringValue(p.value,definitions[p.type].unit)}</span>}{definitions[p.type].status==='visuel uniquement'&&<small>non émulé</small>}</div>}
  {l.terminals.map(pin=><button key={pin.id} type="button" className={'schematic-terminal nodrag nopan '+(data.pending?.component===p.id&&data.pending.pin===pin.id?'cable-anchor':'')} style={{left:pin.x-8,top:pin.y-8}} data-cable-part={p.id} data-cable-pin={pin.id} aria-label={`${p.label} broche ${pin.id}`} title={name+' · '+pin.id} onPointerDown={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();data.onPin({component:p.id,pin:pin.id},e.detail)}} onDoubleClick={e=>{e.preventDefault();e.stopPropagation();data.onStartWire({component:p.id,pin:pin.id})}}>
   <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r={p.type==='junction'||data.degree[pinKey({component:p.id,pin:pin.id})]>1?3.5:2.3}/></svg><Handle id={pin.id} type="source" position={positions[pin.side]} style={{left:8,top:8,width:0,height:0,minWidth:0,minHeight:0,opacity:0,pointerEvents:'none'}}/>
  </button>)}
 </div>;
}
const nodeTypes={part:SymbolNode};
type WireData=Record<string,unknown>&{project:CircuitProject;onSelect:(id:string)=>void;onSplit:(id:string,x:number,y:number)=>void;highlight:boolean};
function SchematicWire({id,source,target,sourceHandleId,targetHandleId,sourceX,sourceY,targetX,targetY,data}:EdgeProps<Edge<WireData>>){
 const {screenToFlowPosition}=useReactFlow();if(!data)return null;const p=data.project,a=p.parts.find(p=>p.id===source)!,b=p.parts.find(p=>p.id===target)!,sa=symbolLayout(a).terminals.find(t=>t.id===sourceHandleId)!,sb=symbolLayout(b).terminals.find(t=>t.id===targetHandleId)!;
 if(!sa||!sb)return null;
 const obstacles=p.parts.filter(p=>p.type!=='junction').map(p=>{const l=symbolLayout(p);return {x:p.x+20,y:p.y+20,width:l.width-40,height:l.height-40}}),points=orthogonalRoute({x:sourceX,y:sourceY},{x:targetX,y:targetY},sa.side,sb.side,obstacles),path=routePath(points);
 const splitWithKeyboard=()=>{const segments=points.slice(1).map((q,i)=>({a:points[i],b:q,length:Math.abs(q.x-points[i].x)+Math.abs(q.y-points[i].y)})).sort((a,b)=>b.length-a.length),s=segments[0];if(s)data.onSplit(id,(s.a.x+s.b.x)/2,(s.a.y+s.b.y)/2)};
 return <g className={'schematic-wire '+(data.highlight?'selected':'')}><path className="wire-stroke" d={path}/><path className="wire-hit" d={path} role="button" tabIndex={0} aria-label="Fil du schéma : Entrée pour sélectionner, J pour ajouter une jonction" onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();data.onSelect(id)}else if(e.key.toLowerCase()==='j'){e.preventDefault();e.stopPropagation();splitWithKeyboard()}}} onClick={e=>{e.stopPropagation();data.onSelect(id)}} onDoubleClick={e=>{e.stopPropagation();e.preventDefault();const at=screenToFlowPosition({x:e.clientX,y:e.clientY});data.onSplit(id,at.x,at.y)}}><title>Fil · clic : sélectionner · double-clic : ajouter une jonction</title></path></g>;
}
const edgeTypes={schematic:SchematicWire};
export default function Project2D({project,selected,selectedWire,mode,pendingPin,onStartWire,onSelect,onPin,onWire,onMove,onDeleteWire,onSplitWire}:{project:CircuitProject;selected:string;selectedWire:string;mode:InteractionMode;pendingPin:Pin|null;onStartWire:(p:Pin)=>void;onSelect:(id:string)=>void;onPin:(p:Pin)=>void;onWire:(a:Pin,b:Pin)=>void;onMove:(id:string,x:number,y:number)=>void;onDeleteWire:(id:string)=>void;onSplitWire:(id:string,x:number,y:number)=>void}){
 const host=useRef<HTMLDivElement>(null),preview=useRef<SVGPathElement>(null),actions=useRef({onPin,onStartWire,mode});actions.current={onPin,onStartWire,mode};
 const gestures=useRef<ReturnType<typeof pinGestures>|null>(null);if(!gestures.current)gestures.current=pinGestures(pin=>actions.current.onPin(pin),pin=>actions.current.onStartWire(pin));
 useEffect(()=>()=>gestures.current?.dispose(),[]);useEffect(()=>{gestures.current?.dispose()},[mode,pendingPin]);
 const references=useMemo(()=>designators(project),[project.parts]),degree=useMemo(()=>{const d:Record<string,number>={};for(const w of project.wires)for(const e of [w.from,w.to])d[pinKey(e)]=(d[pinKey(e)]??0)+1;return d},[project.wires]);
 const buildNodes=():PartNode[]=>project.parts.map(part=>({id:part.id,type:'part',position:{x:part.x,y:part.y},data:{part,reference:references[part.id],degree,pending:pendingPin,onPin:(pin,detail)=>gestures.current?.click(pin,actions.current.mode,detail),onStartWire:pin=>gestures.current?.doubleClick(pin)},selected:part.id===selected}));
 const [nodes,setNodes]=useState<PartNode[]>(buildNodes);useEffect(()=>{setNodes(buildNodes())},[project.parts,project.wires,selected,pendingPin]);
 useEffect(()=>{const el=host.current;if(!el||!pendingPin)return;const draw=(e?:PointerEvent)=>{const button=el.querySelector<HTMLButtonElement>(`button[data-cable-part="${CSS.escape(pendingPin.component)}"][data-cable-pin="${CSS.escape(pendingPin.pin)}"]`);if(!button||!preview.current)return;const a=button.getBoundingClientRect(),r=el.getBoundingClientRect(),x=a.x+a.width/2-r.x,y=a.y+a.height/2-r.y,tx=e?e.clientX-r.x:x+50,ty=e?e.clientY-r.y:y+25;preview.current.setAttribute('d',`M${x},${y} H${tx} V${ty}`)};draw();el.addEventListener('pointermove',draw);return()=>el.removeEventListener('pointermove',draw)},[pendingPin,project.parts]);
 const edges:Edge<WireData>[]=project.wires.map(w=>({id:w.id,type:'schematic',source:w.from.component,sourceHandle:w.from.pin,target:w.to.component,targetHandle:w.to.pin,data:{project,onSelect:onDeleteWire,onSplit:onSplitWire,highlight:w.id===selectedWire}}));
 return <div className="schematic-view schematic-sheet" ref={host} aria-label="Schéma électrique éditable"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} connectOnClick={false} nodesDraggable={mode!=='wire'} onNodesChange={changes=>setNodes(nodes=>applyNodeChanges(changes,nodes))} connectionMode={ConnectionMode.Loose} onConnect={(c:Connection)=>c.source&&c.target&&c.sourceHandle&&c.targetHandle&&onWire({component:c.source,pin:c.sourceHandle},{component:c.target,pin:c.targetHandle})} onNodeClick={(_,n)=>onSelect(n.id)} onPaneClick={()=>onSelect('')} onNodeDragStop={(_,n)=>{setNodes(buildNodes());onMove(n.id,Math.round(n.position.x/16)*16,Math.round(n.position.y/16)*16)}} snapToGrid snapGrid={[16,16]} fitView fitViewOptions={{padding:.25,maxZoom:1.2}} minZoom={.15} maxZoom={3} deleteKeyCode={null} zoomOnDoubleClick={false}><Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#39433e"/><Controls showInteractive={false}/></ReactFlow>{pendingPin&&<svg className="cable-preview-2d" aria-hidden="true" data-testid="cable-preview-2d"><path ref={preview}/></svg>}</div>;
}
