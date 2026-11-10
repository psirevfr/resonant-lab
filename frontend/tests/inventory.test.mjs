import test from 'node:test';
import assert from 'node:assert/strict';
import {audioModuleInventory} from '../.test-build/audioInventory.mjs';

test('Inventaire : noms réels prioritaires, niveaux et enveloppes explicites, branches inactives signalées',()=>{
 const patch={nodes:[{id:'a',type:'modal',label:'Banque magique',parameters:{frequency:440,amplitude:.2,phase:0,attack:.003,onset:0,tau:.3}},{id:'unused',type:'gain',label:'Invisible',parameters:{gain:2}},{id:'out',type:'output',label:'',parameters:{}}],edges:[{source:'a',target:'out'}]};
 const before=JSON.stringify(patch),catalog={oscillator:{label:'Sinus'},envelope:{label:'Enveloppe exponentielle'},gain:{label:'Gain'},output:{label:'Sortie'}};
 const rows=audioModuleInventory(patch,catalog);
 assert.equal(rows.length,4);
 assert.deepEqual(rows.map(r=>r.name),['Sinus','Enveloppe exponentielle','Gain','Sortie']);
 assert.equal(rows[0].parameters.frequency,440);assert.equal(rows[1].parameters.tau,.3);
 assert.equal(rows[2].active,false);assert.equal(rows[3].active,true);
 assert.ok(rows.every(r=>r.material.length>20));assert.equal(JSON.stringify(patch),before);
});

test('Inventaire : valeurs implicites et phase réellement exécutée au début du son',()=>{
 const catalog={modal:{parameters:{frequency:{default:440},amplitude:{default:.3},phase:{default:.7},onset:{default:.013},attack:{default:.003},tau:{default:.3}}},oscillator:{label:'Sinus'},envelope:{label:'Enveloppe'},gain:{label:'Gain',parameters:{gain:{default:1}}}};
 const rows=audioModuleInventory({nodes:[{id:'m',type:'modal',parameters:{},label:''},{id:'g',type:'gain',parameters:{},label:''}],edges:[]},catalog);
 assert.equal(rows[0].parameters.frequency,440);assert.equal(rows[1].parameters.onset,.013);assert.equal(rows[2].parameters.gain,1);
 assert.ok(Math.abs(Math.sin(rows[0].parameters.phase+2*Math.PI*440*.013)-Math.sin(.7))<1e-12);
});
