import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import create from '@o.z/ngspice-wasm';
import {simulateOnDevice} from '../.test-build/circuitClient.mjs';
import {compileCircuit,runWasm} from '../.test-build/circuitEngine.mjs';
import {example,validateProject,newPart,contactGroup,fromPatch} from '../.test-build/circuitProject.mjs';
import {MusicalRouter,midiEvent} from '../.test-build/musicalEvents.mjs';
import {transposeInstrument} from '../.test-build/instrumentLocal.mjs';
import {renderGraph} from '../.test-build/audioDsp.mjs';
import {buildTeensySketch} from '../.test-build/firmware/teensySketch.mjs';
const fixtures=JSON.parse(readFileSync(new URL('./fixtures/dsp.json',import.meta.url)));
test('transposition locale : parité Python des notes 0, 69, 81, 127 avec attaque et phase',()=>{for(const f of fixtures.instruments){const actual=transposeInstrument(f.source,fixtures.catalog,f.note,69,100);assert.deepEqual(actual.muted,f.muted);const samples=renderGraph(actual.patch,fixtures.catalog);const max=Math.max(...samples.map((v,i)=>Math.abs(v-f.samples[i])));assert.ok(max<2e-9,`MIDI ${f.note}: ${max}`)}});
test('ngspice WASM réel : diviseur, résistance modifiée, RC',async()=>{
 const p=example('divider');let r=await runWasm(create,compileCircuit(p));let out=Object.keys(r.labels).find(k=>r.labels[k].includes('Résistance · 2')&&r.labels[k].includes('Résistance · 1'));
 assert.ok(out);assert.ok(Math.abs(r.signals[out].at(-1)-2.5)<1e-8);
 p.parts[2].value=2000;p.revision++;r=await runWasm(create,compileCircuit(p));assert.ok(Math.abs(r.signals[out].at(-1)-10/3)<1e-6);
 const rc=example('rc');r=await runWasm(create,compileCircuit(rc,'step',.005));out=Object.keys(r.labels).find(k=>r.labels[k].includes('Condensateur · 1'));const i=r.time.findIndex(t=>t>=.001),t0=r.time[i-1],t1=r.time[i],y0=r.signals[out][i-1],y1=r.signals[out][i];const y=y0+(y1-y0)*(.001-t0)/(t1-t0);assert.ok(Math.abs(y-5*(1-Math.exp(-1)))<.005);assert.ok(r.raw_points<=4000);
});
test('breadboard : bus A–E, séparation centrale et continuité de circuit',()=>{
 assert.equal(contactGroup('a1'),contactGroup('e1'));assert.notEqual(contactGroup('a1'),contactGroup('f1'));assert.notEqual(contactGroup('a1'),contactGroup('a2'));assert.equal(contactGroup('pL1'),contactGroup('pL10'));assert.notEqual(contactGroup('pL1'),contactGroup('nL1'));
 const p=example('divider'),board=newPart('breadboard',4);p.parts.push(board);const w=p.wires[1];p.wires.splice(1,1,{id:'b1',from:w.from,to:{component:board.id,pin:'a1'}},{id:'b2',from:{component:board.id,pin:'e1'},to:w.to});const same=compileCircuit(p);p.wires.find(w=>w.id==='b2').from.pin='f1';const split=compileCircuit(p);assert.notEqual(same.netlist,split.netlist);assert.equal(same.names.length+1,split.names.length);
});
test('projets : paramètres, fils et placements préservés ; imports invalides refusés',()=>{const p=example('rc');assert.deepEqual(validateProject(JSON.parse(JSON.stringify(p))),p);p.wires[0].from.pin='absent';assert.throws(()=>validateProject(p),/Connexion/);const q=example('rc');q.parts[0].value=Infinity;assert.throws(()=>compileCircuit(q));const d=example('divider');d.wires.pop();assert.throws(()=>compileCircuit(d),/Raccordez/)});
test('pont audio : 38 modes conservés, sans substitution par les 13 partiels',()=>{const p=structuredClone(fixtures.patches[0].patch);p.nodes=Array.from({length:38},(_,i)=>({...p.nodes[0],id:'s'+i})).concat(p.nodes[1]);const analysis={partials:Array.from({length:13},()=>({frequency:100,amplitude:1,tau:1,phase:0})),f0:100,attack:.01};assert.equal(buildTeensySketch(p,analysis).partialCount,38);const project=fromPatch(p);assert.equal(validateProject(JSON.parse(JSON.stringify(project))).source.patch.nodes.length,39)});
test('clic et MIDI : même note 69, vélocité, hauteur 440 Hz et échantillons',()=>{const p=structuredClone(fixtures.patches[0].patch);p.nodes[0].parameters={frequency:440,amplitude:.3,phase:0};const render=e=>{let voice;const router=new MusicalRouter({start:v=>voice=v,stop:()=>{},bend:()=>{},changed:()=>{}});router.dispatch(e);return renderGraph(transposeInstrument(p,fixtures.catalog,voice.note,69,voice.velocity).patch,fixtures.catalog)};const a=render({type:'on',source:'screen',channel:0,note:69,value:100}),b=render(midiEvent('keyboard',new Uint8Array([0x90,69,100])));assert.deepEqual(a,b);for(let i=0;i<a.length;i++)assert.ok(Math.abs(a[i]-.3*100/127*Math.sin(2*Math.PI*440*i/44100))<1e-10)});
test('MIDI : sources/canaux, sustain, bend, vélocité nulle et déconnexion',()=>{const started=[],stopped=[],bends=[];const r=new MusicalRouter({start:v=>started.push({...v}),stop:v=>stopped.push(v.key),bend:v=>bends.push(v.bend),changed:()=>{}});for(const [source,channel] of [['mouse',0],['midi',1]])r.dispatch({source,channel,type:'on',note:69,value:100});r.dispatch(midiEvent('midi',[0xB1,64,127]));r.dispatch(midiEvent('midi',[0x91,69,0]));assert.equal(r.voices.size,2);r.dispatch(midiEvent('midi',[0xE1,127,127]));assert.ok(bends[0]>199);r.dispatch(midiEvent('midi',[0xB1,64,0]));assert.equal(r.voices.size,1);assert.ok([...r.voices.values()].every(v=>v.source==='mouse'));r.stopSource('mouse');assert.equal(r.voices.size,0);assert.equal(stopped.length,2);r.dispatch({source:'x',channel:0,type:'on',note:0,value:1});r.dispatch({source:'x',channel:0,type:'on',note:127,value:127});assert.equal(r.voices.size,2);r.stop();assert.equal(r.voices.size,0)});

test('MIDI : messages invalides ignorés et extinction réinitialise sustain et bend',()=>{
 for(const data of [[],[0x90,60],[0xB0,64],[0x90,128,100],[0x90,60,NaN],[NaN,60,100]])assert.equal(midiEvent('test',data),null);
 const r=new MusicalRouter({start:()=>{},stop:()=>{},bend:()=>{},changed:()=>{}});
 r.dispatch({source:'test',channel:0,type:'on',note:69,value:NaN});assert.equal(r.voices.size,0);
 r.dispatch(midiEvent('test',[0xB0,64,127]));r.dispatch(midiEvent('test',[0xE0,127,127]));r.dispatch(midiEvent('test',[0xB0,123,0]));
 r.dispatch(midiEvent('test',[0x90,69,100]));assert.equal([...r.voices.values()][0].bend,0);
 r.dispatch(midiEvent('test',[0x80,69,0]));assert.equal(r.voices.size,0);
});

test('simulation locale : annulation et erreur libèrent réellement le worker',async()=>{
 const OriginalWorker=globalThis.Worker;let worker;
 class FakeWorker{constructor(){worker=this;this.terminated=0}postMessage(input){this.input=input}terminate(){this.terminated++}}
 globalThis.Worker=FakeWorker;
 try{
  const c=new AbortController(),promise=simulateOnDevice(example('divider'),'dc',.005,c.signal);const cancelled=worker;c.abort();await assert.rejects(promise,{name:'AbortError'});assert.equal(cancelled.terminated,1);
  const next=simulateOnDevice(example('rc'),'step',.005,new AbortController().signal);worker.onerror();await assert.rejects(next,/indisponible/);assert.equal(worker.terminated,1);
  const done=simulateOnDevice(example('divider'),'dc',.005,new AbortController().signal);const result={revision:2};worker.onmessage({data:{result}});assert.equal(await done,result);assert.equal(worker.terminated,1);
 }finally{globalThis.Worker=OriginalWorker}
});
