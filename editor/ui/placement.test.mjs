import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {runInNewContext} from 'node:vm';

const {relocateBlock}=runInNewContext(readFileSync(new URL('placement.js',import.meta.url),'utf8')+'\n({relocateBlock})');
const block=(x,y,w=12,h=2)=>({x,y,w,h});

test('Un bloc transposé avant un autre se cale sur sa ligne sans recouvrement',()=>{
 const first=block(0,0),second=block(0,2);
 relocateBlock([first,second],second,first,false);
 assert.deepEqual(second,block(0,0));
 assert.deepEqual(first,block(0,2));
});

test('Une colonne adjacente s’aligne sans décaler un voisin',()=>{
 const first=block(0,1,6),second=block(0,4,6);
 relocateBlock([first,second],second,first,false,11);
 assert.deepEqual(second,block(6,1,6));
 assert.deepEqual(first,block(0,1,6));
});

test('Une insertion en bout de page échoue sans modifier les blocs',()=>{
 const first=block(0,238),second=block(0,0);
 assert.throws(()=>relocateBlock([first,second],second,first,true),/hauteur/);
 assert.deepEqual(first,block(0,238));
 assert.deepEqual(second,block(0,0));
});
