import type {ReactNode} from 'react';
import {pagePath,type LayoutPage,type BlockKind} from '../siteLayout';
import './layoutGrid.css';

export function LayoutGrid({page,blocks,onNavigate}:{page:LayoutPage;blocks:Partial<Record<BlockKind,ReactNode>>;onNavigate?:(id:string)=>void}){
 return <div className="site-layout-grid">{[...page.blocks].sort((a,b)=>a.y-b.y||a.x-b.x).map(block=>
  <section id={block.id} key={block.id} data-layout-block={block.id} style={{gridColumn:`${block.x+1}/span ${block.w}`,gridRow:`${block.y+1}/span ${block.h}`}}>
   {block.kind==='text'?<p>{block.text}</p>:block.kind==='image'?<img src={block.target} alt={block.text??''}/>:block.kind==='link'?<a className="layout-direction" href={block.target?.startsWith('#')?block.target:pagePath(block.target??'analyse')} onClick={event=>{
    if(!onNavigate||block.target?.startsWith('#')||event.metaKey||event.ctrlKey||event.altKey||event.shiftKey)return;
    event.preventDefault();onNavigate(block.target??'analyse');
   }}>{block.text||'Ouvrir'}</a>:blocks[block.kind]}
  </section>)}</div>;
}
