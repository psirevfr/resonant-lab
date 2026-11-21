import test from 'node:test';
import assert from 'node:assert/strict';
import {canConnectAudio} from '../.test-build/graphConnections.mjs';

const catalog={oscillator:{inputs:0},gain:{inputs:1},sum:{inputs:-1},multiply:{inputs:2},output:{inputs:1}};
function fixture(){return {nodes:[{id:'a',type:'oscillator'},{id:'b',type:'oscillator'},{id:'g',type:'gain'},{id:'h',type:'gain'},{id:'s',type:'sum'},{id:'m',type:'multiply'},{id:'out',type:'output'}],edges:[]}}

test('Audio graph accepts sums and processor inputs without changing the existing patch',()=>{
 const p=fixture();p.edges=[{source:'a',target:'s'}];const before=JSON.stringify(p);
 assert.equal(canConnectAudio(p,catalog,'b','s'),true);
 assert.equal(canConnectAudio(p,catalog,'s','g'),true);
 assert.equal(canConnectAudio(p,catalog,'g','out'),true);
 assert.equal(JSON.stringify(p),before);
});

test('Audio graph rejects self-loops, indirect cycles and duplicate cables',()=>{
 const p=fixture();p.edges=[{source:'a',target:'s'},{source:'s',target:'g'},{source:'g',target:'h'}];
 assert.equal(canConnectAudio(p,catalog,'h','s'),false);
 assert.equal(canConnectAudio(p,catalog,'a','s'),false);
 assert.equal(canConnectAudio(p,catalog,'g','g'),false);
});

test('Audio graph respects the number of processor inputs and excludes invalid endpoints',()=>{
 const p=fixture();p.edges=[{source:'a',target:'g'},{source:'a',target:'m'}];
 assert.equal(canConnectAudio(p,catalog,'b','g'),false);
 assert.equal(canConnectAudio(p,catalog,'b','m'),true);
 p.edges.push({source:'b',target:'m'});
 assert.equal(canConnectAudio(p,catalog,'s','m'),false);
 assert.equal(canConnectAudio(p,catalog,'out','s'),false);
 assert.equal(canConnectAudio(p,catalog,'s','a'),false);
 assert.equal(canConnectAudio(p,catalog,'missing','s'),false);
 assert.equal(canConnectAudio(p,catalog,null,'s'),false);
 p.nodes[0].type='unknown';
 assert.equal(canConnectAudio(p,catalog,'a','out'),false);
});
