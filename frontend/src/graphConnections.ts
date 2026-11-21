import type {Patch,Catalog} from './types';

/** Audio DSP executes a DAG with a fixed number of input ports per processor. */
export function canConnectAudio(patch:Patch,catalog:Catalog,source:string|null|undefined,target:string|null|undefined):boolean{
 if(!source||!target||source===target)return false;
 const a=patch.nodes.find(n=>n.id===source),b=patch.nodes.find(n=>n.id===target);
 if(!a||!b||!catalog[a.type]||!catalog[b.type]||a.type==='output')return false;
 const inputs=catalog[b.type].inputs;
 if(inputs===0||patch.edges.some(e=>e.source===source&&e.target===target))return false;
 if(inputs>0&&patch.edges.filter(e=>e.target===target).length>=inputs)return false;
 const pending=[target],seen=new Set<string>();
 while(pending.length){
  const node=pending.pop()!;
  if(node===source)return false;
  if(seen.has(node))continue;
  seen.add(node);
  for(const edge of patch.edges)if(edge.source===node)pending.push(edge.target);
 }
 return true;
}
