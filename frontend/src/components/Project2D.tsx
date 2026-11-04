import {setting} from '../componentExtras';
import {useEffect,useRef,useState} from 'react';
import {pinGestures} from '../cableInteraction';
import type {InteractionMode} from './Project3D';
import {ReactFlow,Handle,Position,Background,Controls,ConnectionMode,applyNodeChanges,type Node,type NodeProps,type Connection} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {definitions,pins,type CircuitProject,type Part,type Pin} from '../circuitProject';
import {engineeringValue} from '../hardwareCatalog';
import {isBoard} from '../physicalLayout';
type PartNode=Node<{part:Part;contacts:string[];onPin:(p:Pin,detail:number)=>void;onStartWire:(p:Pin)=>void;pending:Pin|null}>;
function ElectricalSymbol({part}:{part:Part}){
 const t=part.type;let symbol;
 if(['resistor','potentiometer','ldr','ntc'].includes(t))symbol=<><path d="M0 30H30M90 30h30"/><rect x="30" y="21" width="60" height="18"/>{t==='potentiometer'&&<path d="M60 0v22m-5-5 5 5 5-5"/>}{t==='ldr'&&<path d="m20 4 20 13m-1-6 1 6-7-1m-4-13 20 13m-1-6 1 6-7-1"/>}{t==='ntc'&&<path d="m28 46 60-32h10"/>}</>;
 else if(['capacitor','electrolytic'].includes(t))symbol=<><path d="M0 30h53M53 10v40M67 10v40M67 30h53"/>{t==='electrolytic'&&<path d="M34 12h10M39 7v10"/>}</>;
 else if(t==='inductor')symbol=<path d="M0 30h24c0-25 18-25 18 0c0-25 18-25 18 0c0-25 18-25 18 0c0-25 18-25 18 0h24"/>;
 else if(t==='led'||t==='diode')symbol=<><path d="M0 30h42M78 30h42M42 17l28 13-28 13Z M72 17v26"/>{t==='led'&&<path d="M68 10l10-8M76 18l10-8M74 2h4v4M82 10h4v4"/>}</>;
 else if(t==='npn')symbol=<><circle cx="60" cy="30" r="23"/><path d="M0 30h49M49 14v32M49 21l29-20M49 39l29 20M63 49l6-2-1 7"/></>;
 else if(t==='nmos')symbol=<><circle cx="60" cy="30" r="24"/><path d="M0 30h43M43 14v32M51 13v34M51 18h26V0M51 42h26v18M77 18v24"/></>;
 else if(t==='opamp')symbol=<><path d="M25 7v46l67-23ZM0 20h25M0 40h25M92 30h28M12 15v10M7 20h10M7 40h10"/></>;
 else if(t==='button'||t==='switch')symbol=<><path d="M0 35h38M82 35h38"/><circle cx="40" cy="35" r="2"/><circle cx="80" cy="35" r="2"/><path d={setting(part,t==='button'?'closed':'position')?'M42 35h36':'M42 35 78 13'}/>{t==='button'&&<path d="M60 4v15M48 4h24"/>}</>;
 else if(t==='voltage')symbol=<><circle cx="60" cy="30" r="20"/><path d="M0 30h40M80 30h40M51 23h8M55 19v8M64 38h8"/></>;
 else if(t==='ground')symbol=<path d="M60 4v28M40 32h40M46 39h28M53 46h14"/>;
 else symbol=<><rect x="18" y="8" width="84" height="44" rx="4"/><path d="M0 30h18M102 30h18"/>{t==='tmp36'&&<text x="60" y="35" textAnchor="middle" fill="currentColor" stroke="none" fontSize="12">T → V</text>}</>;
 return <svg viewBox="0 0 120 60" className="electrical-symbol" aria-hidden="true"><g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{symbol}</g></svg>;
}
function SymbolNode({data,selected}:NodeProps<PartNode>){const p=data.part,contacts=isBoard(p)?data.contacts:pins(p),multi=!isBoard(p)&&contacts.length>3;return <div className={'electrical-node symbol-node '+(selected?'chosen':'')+(isBoard(p)?' board-symbol':'')}><b>{p.label}</b>{isBoard(p)?<small>{p.type==='breadboard830'?'830 contacts · groupes A–E / F–J':'Platine 10 colonnes'} · {p.railSplit?'rails coupés':'rails continus'}</small>:<><ElectricalSymbol part={p}/><small>{definitions[p.type].unit?engineeringValue(p.value,definitions[p.type].unit):definitions[p.type].status}</small></>}<div className={'electrical-pins '+(isBoard(p)?'board-contacts':multi?'multipin':'')} style={multi?{gridTemplateRows:`repeat(${Math.ceil(contacts.length/2)},auto)`}:undefined}>{contacts.map((pin,i)=><div className="electrical-pin" key={pin}><button data-cable-part={p.id} data-cable-pin={pin} className={data.pending?.component===p.id&&data.pending.pin===pin?'cable-anchor':''} onClick={e=>{e.stopPropagation();data.onPin({component:p.id,pin},e.detail)}} onDoubleClick={e=>{e.preventDefault();e.stopPropagation();data.onStartWire({component:p.id,pin})}} aria-label={`${p.label} broche ${pin}`}>{pin}</button><Handle id={pin} type="source" position={isBoard(p)?Position.Bottom:multi?(i<Math.ceil(contacts.length/2)?Position.Left:Position.Right):i===0?Position.Left:Position.Right}/></div>)}</div></div>}
const nodeTypes={part:SymbolNode};
export default function Project2D({project,selected,mode,pendingPin,onStartWire,onSelect,onPin,onWire,onMove,onDeleteWire}:{project:CircuitProject;selected:string;mode:InteractionMode;pendingPin:Pin|null;onStartWire:(p:Pin)=>void;onSelect:(id:string)=>void;onPin:(p:Pin)=>void;onWire:(a:Pin,b:Pin)=>void;onMove:(id:string,x:number,y:number)=>void;onDeleteWire:(id:string)=>void}){
 const host=useRef<HTMLDivElement>(null),preview=useRef<SVGPathElement>(null),actions=useRef({onPin,onStartWire,mode});actions.current={onPin,onStartWire,mode};
 const gestures=useRef<ReturnType<typeof pinGestures>|null>(null);if(!gestures.current)gestures.current=pinGestures(pin=>actions.current.onPin(pin),pin=>actions.current.onStartWire(pin));
 useEffect(()=>()=>gestures.current?.dispose(),[]);
 useEffect(()=>{gestures.current?.dispose()},[mode,pendingPin]);
 useEffect(()=>{const el=host.current;if(!el||!pendingPin)return;const source=()=>el.querySelector<HTMLButtonElement>(`button[data-cable-part="${CSS.escape(pendingPin.component)}"][data-cable-pin="${CSS.escape(pendingPin.pin)}"]`);const draw=(e?:PointerEvent)=>{const button=source();if(!button||!preview.current)return;const a=button.getBoundingClientRect(),r=el.getBoundingClientRect(),x=a.x+a.width/2-r.x,y=a.y+a.height/2-r.y,tx=e?e.clientX-r.x:x+50,ty=e?e.clientY-r.y:y+25;preview.current.setAttribute('d',`M${x},${y} C${x+40},${y-30} ${tx-40},${ty-30} ${tx},${ty}`)};draw();el.addEventListener('pointermove',draw);return()=>el.removeEventListener('pointermove',draw)},[pendingPin,project.parts]);
 const buildNodes=():PartNode[]=>project.parts.map(part=>({id:part.id,type:'part',position:{x:part.x,y:part.y},data:{part,onPin:(pin,detail)=>gestures.current?.click(pin,actions.current.mode,detail),onStartWire:pin=>gestures.current?.doubleClick(pin),pending:pendingPin,contacts:[...new Set(project.wires.flatMap(w=>[w.from,w.to]).filter(e=>e.component===part.id).map(e=>e.pin).concat(project.parts.filter(p=>p.mount?.board===part.id).flatMap(p=>Object.values(p.mount!.pins))))]},selected:part.id===selected}));
 const [nodes,setNodes]=useState<PartNode[]>(buildNodes);
 useEffect(()=>{setNodes(buildNodes())},[project.parts,project.wires,selected,pendingPin]);
 const edges=project.wires.map(w=>({id:w.id,source:w.from.component,sourceHandle:w.from.pin,target:w.to.component,targetHandle:w.to.pin,style:{stroke:w.color??'#d4c67e',strokeWidth:2}})).concat(project.parts.filter(p=>p.mount).flatMap(p=>Object.entries(p.mount!.pins).map(([pin,contact])=>({id:'_mount:'+p.id+':'+pin,source:p.id,sourceHandle:pin,target:p.mount!.board,targetHandle:contact,style:{stroke:'#739a67',strokeWidth:1}}))));
 return <div className="schematic-view" ref={host}><ReactFlow connectOnClick={false} nodesDraggable={mode!=='wire'} nodes={nodes} edges={edges} onNodesChange={changes=>setNodes(nodes=>applyNodeChanges(changes,nodes))} nodeTypes={nodeTypes} connectionMode={ConnectionMode.Loose} onConnect={(c:Connection)=>c.source&&c.target&&c.sourceHandle&&c.targetHandle&&onWire({component:c.source,pin:c.sourceHandle},{component:c.target,pin:c.targetHandle})} onNodeClick={(_,n)=>onSelect(n.id)} onNodeDragStop={(_,n)=>onMove(n.id,n.position.x,n.position.y)} onEdgeClick={(_,e)=>{if(!e.id.startsWith('_mount:'))onDeleteWire(e.id)}} fitView minZoom={.15} maxZoom={3} deleteKeyCode={null}><Background gap={20} color="#333b2d"/><Controls showInteractive={false}/></ReactFlow>{pendingPin&&<svg className="cable-preview-2d" aria-hidden="true" data-testid="cable-preview-2d"><path ref={preview}/></svg>}</div>
}
