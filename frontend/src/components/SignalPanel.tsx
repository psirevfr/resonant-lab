import {useState} from 'react';
import type {SignalView,RenderResult,Analysis} from '../types';
import {Plot,colors} from './Plot';
import type {Data} from 'plotly.js';
export function SignalPanel({original,result,analysis}:{original?:SignalView;result:RenderResult|null;analysis:Analysis|null}){
 const [tab,setTab]=useState('wave'),[cursor,setCursor]=useState(0),[specSource,setSpecSource]=useState('original');
 const ref=result?.reference??original; const model=result?.view;
 const traces:Data[]=[];
 function line(x:number[],y:number[],name:string,color:string):Data{return{x,y,type:'scatter',mode:'lines',name,line:{color,width:1.3}}}
 if(tab==='wave'||tab==='env'){
  if(ref)traces.push(line(tab==='wave'?ref.time:ref.envelope_time,tab==='wave'?ref.wave:ref.envelope,'Original',colors.original));
  if(model)traces.push(line(tab==='wave'?model.time:model.envelope_time,tab==='wave'?model.wave:model.envelope,'Synthèse',colors.model));
  if(tab==='wave'&&result?.difference)traces.push({...line(result.difference.time,result.difference.wave,'Résidu',colors.error),visible:'legendonly'});
 }else if(tab==='fft'){
  if(ref)traces.push(line(ref.frequency,ref.spectrum,'Original',colors.original));if(model)traces.push(line(model.frequency,model.spectrum,'Synthèse',colors.model));
 }else if(tab==='auto'&&analysis){traces.push(line(analysis.autocorrelation.lag,analysis.autocorrelation.value,'Autocorrélation',colors.original))}
 const source=specSource==='model'?model:specSource==='difference'?result?.difference:ref;
 return <section className="signal-panel"><div className="signal-toolbar"><div className="tabs">{[['wave','Signal'],['fft','Spectre'],['spec','Spectrogramme'],['env','Enveloppe'],['auto','Autocorrélation']].map(([id,label])=><button key={id} onClick={()=>setTab(id)} className={tab===id?'active':''}>{label}</button>)}</div><div className="plot-legend"><span className="original">Original</span><span className="model">Synthèse</span></div></div>
 {tab==='spec'?<><div className="spectrogram-control"><select aria-label="Signal du spectrogramme" value={specSource} onChange={e=>setSpecSource(e.target.value)}><option value="original">Original</option><option value="model">Synthèse</option><option value="difference">Résidu</option></select><span>dBFS · mêmes limites : −100 à 0 dB</span></div>{source?<Plot key="spectrogram" height={235} onCursor={setCursor} cursor={cursor} data={[{x:source.spectrogram.time,y:source.spectrogram.frequency,z:source.spectrogram.db,type:'heatmap',colorscale:[[0,'#111a27'],[.25,'#263853'],[.5,'#426d79'],[.75,'#a7c66e'],[1,'#f2e2a0']],zmin:-100,zmax:0,colorbar:{thickness:10,title:{text:'dB'}},hovertemplate:'%{x:.3f} s · %{y:.1f} Hz<br>%{z:.1f} dB<extra></extra>'}]} layout={{margin:{l:58,r:60,t:12,b:40},yaxis:{title:{text:'Fréquence (Hz)'},range:[0,10000]}}}/>:<Empty/>}</>:traces.length?<Plot key={tab} height={250} data={traces} onCursor={tab==='wave'||tab==='env'?setCursor:undefined} cursor={tab==='wave'||tab==='env'?cursor:undefined} layout={{showlegend:tab!=='auto',legend:{orientation:'h',x:.01,y:1.12,font:{size:11}},xaxis:{title:{text:tab==='fft'?'Fréquence (Hz)':tab==='auto'?'Retard (s)':'Temps dans la sélection (s)'},type:tab==='fft'?'log':'linear',gridcolor:'#26323e'},yaxis:{title:{text:tab==='fft'?'Amplitude (dBFS)':tab==='auto'?'Corrélation':'Amplitude'},gridcolor:'#26323e'}}}/>:<Empty text={tab==='auto'?'Lancez l’analyse pour afficher l’autocorrélation.':undefined}/>}
 </section>
}
function Empty({text='Importez un WAV ou chargez la note de démonstration.'}:{text?:string}){return <div className="plot-empty">{text}</div>}
