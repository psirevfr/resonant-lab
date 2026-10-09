import test from 'node:test';
import assert from 'node:assert/strict';
import {computeLocally,disposeCompute} from '../.test-build/computeEngine.mjs';
import {withDeadline} from '../.test-build/requestDeadline.mjs';
const workers=[];
class FakeWorker{
 constructor(){this.terminated=false;this.messages=[];workers.push(this)}
 postMessage(message){this.messages.push(message);this.last=message}
 terminate(){this.terminated=true}
 emit(phase,options={}){this.onmessage?.({data:{id:this.last.id,phase,...options}})}
}
globalThis.Worker=FakeWorker;
globalThis.fetch=async path=>path==='/api/me'?Response.json({csrf_token:'local-test'}):new Response(new Float64Array(2205).buffer,{headers:{'X-Sample-Rate':'44100'}});
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('one computation, stale results ignored, controlled worker reuse',async()=>{
 disposeCompute();const updates=[];
 const first=computeLocally('generate',{},new AbortController().signal,v=>updates.push(v.phase));await tick();
 const worker=workers.at(-1);
 await assert.rejects(computeLocally('compact',{},new AbortController().signal,()=>{}),/déjà actif/);
 worker.onmessage({data:{id:'obsolete',phase:'result',result:{wrong:true}}});assert.deepEqual(updates,[]);
 worker.emit('progress',{progress:{evaluations:1}});worker.emit('result',{result:{patch:'first'}});
 assert.deepEqual(await first,{patch:'first'});assert.equal(worker.terminated,false);
 const second=computeLocally('optimize',{},new AbortController().signal,()=>{});await tick();
 assert.equal(workers.at(-1),worker);worker.emit('result',{result:{patch:'second'}});await second;disposeCompute();
});

test('abort really terminates worker, releases capacity and discards late messages',async()=>{
 const controller=new AbortController();const promise=computeLocally('generate',{},controller.signal,()=>{});await tick();
 const worker=workers.at(-1);controller.abort();await assert.rejects(promise,e=>e.name==='AbortError');
 assert.equal(worker.terminated,true);assert.equal(worker.onmessage,null);
 const next=computeLocally('compact',{},new AbortController().signal,()=>{});await tick();assert.notEqual(workers.at(-1),worker);
 workers.at(-1).emit('result',{result:{patch:'next'}});await next;disposeCompute();
});

test('worker errors recover without implicitly submitting a server job',async()=>{
 const first=computeLocally('generate',{},new AbortController().signal,()=>{});await tick();
 workers.at(-1).emit('error',{error:'test failure'});await assert.rejects(first,/test failure/);
 const second=computeLocally('generate',{},new AbortController().signal,()=>{});await tick();
 workers.at(-1).emit('result',{result:{patch:'recovered'}});await second;disposeCompute();
});

test('invalid reference is rejected before starting worker',async()=>{
 const saved=globalThis.fetch,count=workers.length;
 globalThis.fetch=async()=>new Response(new Uint8Array(3),{headers:{'X-Sample-Rate':'44100'}});
 try{await assert.rejects(computeLocally('generate',{},new AbortController().signal,()=>{}),/incompatible/);assert.equal(workers.length,count)}finally{globalThis.fetch=saved}
});

test('tracking deadline distinguishes transport timeout and cleans up signal',async()=>{
 const controller=new AbortController();let child;
 await assert.rejects(withDeadline(controller.signal,signal=>new Promise((resolve,reject)=>{
  child=signal;signal.addEventListener('abort',()=>reject(signal.reason),{once:true});
 }),10),e=>e.name==='TimeoutError');
 assert.equal(controller.signal.aborted,false);assert.equal(child.aborted,true);
 assert.equal(await withDeadline(controller.signal,async()=>42,10),42);
});

test('deadline also interrupts a transport that ignores the signal',async()=>{
 await assert.rejects(withDeadline(new AbortController().signal,()=>new Promise(()=>{}),10),e=>e.name==='TimeoutError');
 const controller=new AbortController();controller.abort();let submitted=false;
 await assert.rejects(withDeadline(controller.signal,async()=>{submitted=true}),e=>e.name==='AbortError');
 assert.equal(submitted,false);
});
