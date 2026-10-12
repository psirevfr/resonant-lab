import {createContext,useContext,useEffect,useRef,useState} from 'react';
import Plotly from 'plotly.js-dist-min';
import type {Data,Layout,PlotlyHTMLElement} from 'plotly.js';
import {download} from '../api';
export const colors={original:'#9bd5ea',model:'#b4ed79',error:'#ed987a'};
export const ExportPermission=createContext(false);
export function Plot({data,layout={},height=200,onCursor,cursor}:{data:Data[];layout?:Partial<Layout>;height?:number;onCursor?:(x:number)=>void;cursor?:number}){
 const canExport=useContext(ExportPermission);
 const [exportError,setExportError]=useState('');
 const ref=useRef<HTMLDivElement>(null),callback=useRef(onCursor),queue=useRef<Promise<unknown>>(Promise.resolve()),mounted=useRef(true),generation=useRef(0);callback.current=onCursor;
 useEffect(()=>{mounted.current=true;const el=ref.current!;let timer:ReturnType<typeof setTimeout>;
  const resize=new ResizeObserver(()=>{clearTimeout(timer);timer=setTimeout(()=>{queue.current=queue.current.catch(()=>{}).then(async()=>{if(mounted.current&&el.isConnected)await Plotly.Plots.resize(el)})},100)});
  resize.observe(el);
  return()=>{mounted.current=false;clearTimeout(timer);resize.disconnect();void queue.current.catch(()=>{}).then(()=>Plotly.purge(el))};
 },[]);
 useEffect(()=>{const el=ref.current!,revision=++generation.current;
  const base:Partial<Layout>={height,margin:{l:52,r:18,t:18,b:40},paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{family:'system-ui, sans-serif',color:'#94a6b6',size:11},colorway:[colors.original,colors.model,colors.error],xaxis:{gridcolor:'#24303b',zerolinecolor:'#34414e',title:{text:'Temps (s)'}},yaxis:{gridcolor:'#24303b',zerolinecolor:'#34414e'},showlegend:false,hovermode:'x unified',uirevision:'keep',...layout};
  if(cursor!==undefined)base.shapes=[{type:'line',xref:'x',yref:'paper',x0:cursor,x1:cursor,y0:0,y1:1,line:{color:'#8195a8',width:1,dash:'dot'}}];
  queue.current=queue.current.catch(()=>{}).then(async()=>{if(!mounted.current||revision!==generation.current)return;await Plotly.react(el,data,base,{responsive:false,displaylogo:false,scrollZoom:false,modeBarButtonsToRemove:['lasso2d','select2d','toImage'],modeBarButtonsToAdd:canExport?[{name:'Exporter le graphique en PNG',title:'Exporter le graphique en PNG',icon:{width:24,height:24,path:'M3 6h4l2-3h6l2 3h4v15H3z M12 8a5 5 0 1 0 0 10a5 5 0 1 0 0-10'},click:()=>{setExportError('');void Plotly.toImage(el,{format:'png',height:700,width:1200,scale:2}).then(async url=>{const blob=await(await fetch(url)).blob();await download(blob,'resonant-figure.png','image/png')}).catch(e=>setExportError(e instanceof Error?e.message:'Export du graphique impossible.'))}}]:[],toImageButtonOptions:{format:'png',filename:'resonant-figure',height:700,width:1200,scale:2}});if(!mounted.current)return;const plot=el as unknown as PlotlyHTMLElement;plot.removeAllListeners('plotly_hover');plot.on('plotly_hover',e=>{const x=e.points[0]?.x;if(typeof x==='number')callback.current?.(x)})});
 },[data,layout,height,cursor,canExport]);
 return <><div ref={ref} className="plot" style={{minHeight:height}}/>{exportError&&<p className="error-inline" role="alert">{exportError}</p>}</>;
}
