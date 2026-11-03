import {useEffect,useState} from 'react';
import {ReactFlow,Handle,Position,Background,Controls,ConnectionMode,applyNodeChanges,type Node,type NodeProps,type Connection} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {definitions,pins,type CircuitProject,type Part,type Pin} from '../circuitProject';
type PartNode=Node<{part:Part;onPin:(p:Pin)=>void}>;
function SymbolNode({data,selected}:NodeProps<PartNode>){const p=data.part;return <div className={'electrical-node '+(selected?'chosen':'')+(p.type==='breadboard'?' board-node':'')}><b>{p.label}</b><small>{definitions[p.type].unit?p.value+' '+definitions[p.type].unit:definitions[p.type].status}</small><div className="electrical-pins">{pins(p).map(pin=><div className="electrical-pin" key={pin}><button onClick={e=>{e.stopPropagation();data.onPin({component:p.id,pin})}} aria-label={`${p.label} broche ${pin}`}>{pin}</button><Handle id={pin} type="source" position={Position.Bottom}/></div>)}</div></div>}
const nodeTypes={part:SymbolNode};
export default function Project2D({project,selected,onSelect,onPin,onWire,onMove,onDeleteWire}:{project:CircuitProject;selected:string;onSelect:(id:string)=>void;onPin:(p:Pin)=>void;onWire:(a:Pin,b:Pin)=>void;onMove:(id:string,x:number,y:number)=>void;onDeleteWire:(id:string)=>void}){
 const [nodes,setNodes]=useState<PartNode[]>([]);
 useEffect(()=>{setNodes(project.parts.map(part=>({id:part.id,type:'part',position:{x:part.x,y:part.y},data:{part,onPin},selected:part.id===selected})))},[project.parts,selected,onPin]);
 const edges=project.wires.map(w=>({id:w.id,source:w.from.component,sourceHandle:w.from.pin,target:w.to.component,targetHandle:w.to.pin,style:{stroke:'#75b7b3',strokeWidth:2}}));
 return <ReactFlow nodes={nodes} edges={edges} onNodesChange={changes=>setNodes(nodes=>applyNodeChanges(changes,nodes))} nodeTypes={nodeTypes} connectionMode={ConnectionMode.Loose} onConnect={(c:Connection)=>c.source&&c.target&&c.sourceHandle&&c.targetHandle&&onWire({component:c.source,pin:c.sourceHandle},{component:c.target,pin:c.targetHandle})} onNodeClick={(_,n)=>onSelect(n.id)} onNodeDragStop={(_,n)=>onMove(n.id,n.position.x,n.position.y)} onEdgeClick={(_,e)=>{if(confirm('Supprimer cette liaison ?'))onDeleteWire(e.id)}} fitView minZoom={.2} maxZoom={2} deleteKeyCode={null}><Background gap={20}/><Controls showInteractive={false}/></ReactFlow>
}
