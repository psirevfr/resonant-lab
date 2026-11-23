import test from 'node:test';
import assert from 'node:assert/strict';
import {acousticEnabled,acousticHint,acousticTrialCount,clearAcousticTrials,recordAcousticTrial,setAcousticEnabled} from '../.test-build/acousticLearning.mjs';

const storage=new Map();
globalThis.localStorage={
 getItem:key=>storage.get(key)??null,
 setItem:(key,value)=>storage.set(key,value),
 removeItem:key=>storage.delete(key),
};
const trial=(id,reward=.25)=>({version:1,profile:'sustained',strategy:'adsr',clip:'44100:'+id.toString(16).padStart(64,'0'),reward,accepted:reward>0});

test('La mémoire est locale, activée volontairement et séparée par compte',()=>{
 storage.clear();
 assert.equal(acousticEnabled(1),false);
 recordAcousticTrial(1,trial(1));
 assert.equal(acousticTrialCount(1),0);
 setAcousticEnabled(1,true);
 recordAcousticTrial(1,{...trial(1),audio:'do-not-store'});
 recordAcousticTrial(1,trial(1));
 assert.equal(acousticTrialCount(1),1);
 assert.deepEqual(acousticHint(1),{version:1,history:{sustained:{adsr:{count:1,reward:.25}}}});
 assert.equal(acousticTrialCount(2),0);
 assert.ok([...storage.values()].every(value=>!value.includes('do-not-store')));
 setAcousticEnabled(1,false);
 recordAcousticTrial(1,trial(2));
 assert.equal(acousticTrialCount(1),1);
 clearAcousticTrials(1);
 assert.equal(acousticTrialCount(1),0);
});

test('La réserve reste bornée et rejette les mesures non finies',()=>{
 storage.clear();
 setAcousticEnabled(3,true);
 recordAcousticTrial(3,trial(0,NaN));
 assert.equal(acousticTrialCount(3),0);
 for(let i=1;i<=140;i++)recordAcousticTrial(3,trial(i));
 assert.equal(acousticTrialCount(3),128);
 assert.deepEqual(acousticHint(3).history.sustained.adsr,{count:128,reward:32});
});

test('Le prior collectif est borné et une petite cohorte est ignorée',()=>{
 storage.clear();
 setAcousticEnabled(1,true);
 recordAcousticTrial(1,trial(1));
 const hint=acousticHint(1,{sustained:{adsr:{contributors:100,mean:.5},decay:{contributors:4,mean:1}}});
 assert.deepEqual(hint.history,{sustained:{adsr:{count:7,reward:3.25}}});
});
