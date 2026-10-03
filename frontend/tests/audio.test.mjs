import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {renderGraph,encodeWav,signalView} from '../.test-build/audioDsp.mjs';
const fixtures=JSON.parse(readFileSync(new URL('./fixtures/dsp.json',import.meta.url)));
for(const {name,patch,samples} of fixtures.patches){
 test('DSP local / Python : '+name,()=>{
  const actual=renderGraph(patch,fixtures.catalog);
  assert.equal(actual.length,samples.length);
  const error=Math.max(...actual.map((v,i)=>Math.abs(v-samples[i])));
  assert.ok(error<2e-9,`maximum error ${error}`);
 });
}
test('WAV float mono, sans écrêtage, avec données réelles',()=>{
 const x=new Float64Array([0,1.5,-2,.25]),data=new DataView(encodeWav(x,48000));
 assert.equal(data.getUint16(20,true),3);assert.equal(data.getUint16(22,true),1);assert.equal(data.getUint32(24,true),48000);
 assert.equal(data.getFloat32(48,true),1.5);assert.equal(data.getFloat32(52,true),-2);
});
test('Bruit local déterministe, gain nul et graphe invalide',()=>{
 const patch=structuredClone(fixtures.patches[0].patch);patch.nodes[0].type='noise';patch.nodes[0].parameters={amplitude:.2,seed:42};
 const a=renderGraph(patch,fixtures.catalog),b=renderGraph(patch,fixtures.catalog);assert.deepEqual(a,b);
 const rms=Math.sqrt(a.reduce((s,x)=>s+x*x,0)/a.length);assert.ok(rms>.18&&rms<.22);
 patch.nodes[0].parameters.amplitude=0;assert.ok(renderGraph(patch,fixtures.catalog).every(v=>v===0));
 patch.edges=[];assert.throws(()=>renderGraph(patch,fixtures.catalog),/Connexions/);
});
test('Vues du signal complètes et valeurs finies',()=>{
 const x=renderGraph(fixtures.patches[0].patch,fixtures.catalog),v=signalView(x,44100);
 assert.ok(v.time.length&&v.spectrum.length&&v.spectrogram.db.length);
 assert.ok(v.rms>0);assert.ok(v.spectrum.every(Number.isFinite));assert.equal(v.time.length,v.wave.length);
});
