import {useCallback,useEffect,useState,useRef} from 'react';
import {ReactFlow,ReactFlowProvider,Background,Controls,MiniMap,Handle,Position,applyNodeChanges,applyEdgeChanges,useReactFlow,useNodesInitialized,type Edge,type Node,type NodeProps,type NodeChange,type EdgeChange,type Connection} from '@xyflow/react';
import {Activity,Volume2,SlidersHorizontal,AudioWaveform} from 'lucide-react';
import type {Patch,Catalog,Block} from '../types';
import '@xyflow/react/dist/style.css';
import {appendModule} from '../defaults';
type AudioNode = Node<{block:Block;catalog:Catalog},'audio'>;
function BlockNode({data,selected}:NodeProps<AudioNode>){const b=data.block,d=data.catalog[b.type];if(!d)return null;const generator=d.inputs===0;const Icon=b.type==='output'?Volume2:generator?AudioWaveform:b.type==='sum'?Activity:SlidersHorizontal;
 return <div className={`audio-node ${selected?'chosen':''} ${generator?'generator':''} ${b.type==='output'?'output':''}`}>
 {!generator&&<Handle type="target" position={Position.Left}/>}<div className="node-title"><Icon size={16}/><span>{d.label}</span></div>{b.label&&b.label!==d.label&&<small>{b.label}</small>}<div className="node-values">{Object.entries(b.parameters).slice(0,2).map(([k,v])=><span key={k}>{d.parameters[k]?.label??k} <b>{Math.abs(v)<.01&&v!==0?v.toExponential(1):Number(v.toFixed(2))}</b> {d.parameters[k]?.unit}</span>)}{!Object.keys(b.parameters).length&&<span>{d.inputs<0?'Σ entrées':b.type==='output'?'Audio':'Signal'}</span>}</div>{b.type!=='output'&&<Handle type="source" position={Position.Right}/>}</div>
}
const nodeTypes={audio:BlockNode};
function Inner({patch,catalog,onChange,onSelect,selected,disabled}:Props){const flow=useReactFlow();
 const [nodes,setNodes]=useState<AudioNode[]>([]);
 useEffect(()=>setNodes(previous=>patch.nodes.map(b=>({...previous.find(n=>n.id===b.id),id:b.id,type:'audio' as const,position:b.position,data:{block:b,catalog},selected:b.id===selected}))),[patch.nodes,catalog,selected]);
 const initialized=useNodesInitialized();const fitted=useRef('');const nodeKey=patch.nodes.map(n=>n.id).join('|');
 useEffect(()=>{if(initialized&&fitted.current!==nodeKey){fitted.current=nodeKey;void flow.fitView({padding:.2,duration:200})}},[initialized,nodeKey,flow]);
 const host=useRef<HTMLDivElement>(null);
 const [edges,setEdges]=useState<Edge[]>([]);
 useEffect(()=>setEdges(previous=>patch.edges.map(e=>({...e,type:'smoothstep',selected:previous.find(old=>old.id===e.id)?.selected??false,interactionWidth:24,style:{stroke:'#789864',strokeWidth:1.8},ariaLabel:'Câble de '+(patch.nodes.find(n=>n.id===e.source)?.label||e.source)+' vers '+(patch.nodes.find(n=>n.id===e.target)?.label||e.target)}))),[patch.edges,patch.nodes]);
 const changeNodes=useCallback((changes:NodeChange<AudioNode>[])=>{if(disabled&&changes.every(c=>c.type!=='dimensions'))return;const select=changes.find(c=>c.type==='select'&&c.selected);if(select&&'id'in select)onSelect(select.id);const updated=applyNodeChanges(changes,nodes);setNodes(updated);if(changes.some(c=>c.type==='position'||c.type==='remove')){const ids=new Set(updated.map(n=>n.id));onChange({...patch,nodes:updated.map(n=>({...n.data.block,position:n.position})),edges:patch.edges.filter(e=>ids.has(e.source)&&ids.has(e.target))})}},[nodes,patch,onChange,onSelect,disabled]);
 const changeEdges=(changes:EdgeChange[])=>{if(disabled)return;const updated=applyEdgeChanges(changes,edges);setEdges(updated);if(changes.some(c=>c.type==='remove'))onChange({...patch,edges:updated.map(({id,source,target})=>({id,source,target}))})};
 function deleteSelection(e:React.KeyboardEvent){
  if(disabled||!['Delete','Backspace'].includes(e.key)||(e.target as HTMLElement).closest('input,textarea,select,[contenteditable="true"]'))return;
  const cables=new Set(edges.filter(edge=>edge.selected).map(edge=>edge.id));
  const blocks=new Set(cables.size?[]:nodes.filter(node=>node.selected).map(node=>node.id));
  if(!cables.size&&!blocks.size)return;
  e.preventDefault();e.stopPropagation();
  onChange({...patch,nodes:patch.nodes.filter(n=>!blocks.has(n.id)),edges:patch.edges.filter(edge=>!cables.has(edge.id)&&!blocks.has(edge.source)&&!blocks.has(edge.target))});
  if(blocks.size)onSelect('');
 }
 const connect=(c:Connection)=>{if(disabled||!c.source||!c.target||c.source===c.target||patch.edges.some(e=>e.source===c.source&&e.target===c.target))return;onChange({...patch,edges:[...patch.edges,{id:crypto.randomUUID(),source:c.source,target:c.target}]})};
 return <div className="graph-wrap" data-guide="graph" ref={host} tabIndex={0} aria-label="Câblage libre" onKeyDown={deleteSelection} onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect='copy'}} onDrop={e=>{e.preventDefault();if(disabled)return;const type=e.dataTransfer.getData('application/resonant');if(!catalog[type])return;const position=flow.screenToFlowPosition({x:e.clientX,y:e.clientY});const added=appendModule(patch,type,catalog,position);onChange(added.patch);onSelect(added.id)}}>
 <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={changeNodes} onEdgesChange={changeEdges} onConnect={connect} onNodeClick={(_,n)=>onSelect(n.id)} onEdgeClick={()=>{onSelect('');host.current?.focus({preventScroll:true})}} onPaneClick={()=>onSelect('')} fitView fitViewOptions={{padding:.2}} minZoom={.15} maxZoom={2} zoomOnScroll={false} zoomOnPinch={false} zoomOnDoubleClick={false} preventScrolling={false} colorMode="dark" deleteKeyCode={null} nodesDraggable={!disabled} nodesConnectable={!disabled}><Background color="#33414e" gap={22} size={1}/><Controls showInteractive={false}/><MiniMap nodeColor={n=>(n.data as {block:Block}).block.type==='modal'?'#b4ed79':'#506474'} maskColor="#0e151cbb" pannable/></ReactFlow>
 </div>
}
interface Props{patch:Patch;catalog:Catalog;onChange:(p:Patch)=>void;onSelect:(id:string)=>void;selected:string;disabled:boolean}
export function Graph(props:Props){return <ReactFlowProvider><Inner {...props}/></ReactFlowProvider>}
