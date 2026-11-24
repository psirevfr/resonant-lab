import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {runInNewContext} from 'node:vm';

const {mergePresentation}=runInNewContext(readFileSync(new URL('sync.js',import.meta.url),'utf8')+'\n({mergePresentation})',
 {same:(a,b)=>JSON.stringify(a)===JSON.stringify(b)});
const normalize=value=>JSON.parse(JSON.stringify(value));

test('Merge independently changed presentation fields and block rows',()=>{
 const base={colors:{accent:'#fff',text:'#ccc'},pages:[{id:'analyse',blocks:[{id:'source',x:0,y:0}]}]};
 const local=structuredClone(base);
 local.colors.accent='#000';local.pages[0].blocks[0].x=2;
 const disk=structuredClone(base);
 disk.colors.text='#eee';disk.pages[0].blocks[0].y=4;disk.pages.push({id:'next',blocks:[]});
 assert.deepEqual(normalize(mergePresentation(base,local,disk)),{
  colors:{accent:'#000',text:'#eee'},
  pages:[{id:'analyse',blocks:[{id:'source',x:2,y:4}]},{id:'next',blocks:[]}],
 });
});

test('A draft value for an edited field stays pending when the disk changes the same field',()=>{
 assert.equal(mergePresentation('past','draft','disk'),'draft');
});

test('Two first-time element edits merge without losing either property',()=>{
 assert.deepEqual(normalize(mergePresentation({},{
  elements:{'element-a':{text:'Nouvelle commande'}},
 },{
  elements:{'element-a':{color:'#123456'},'element-b':{background:'#765432'}},
 })),{elements:{'element-a':{text:'Nouvelle commande',color:'#123456'},'element-b':{background:'#765432'}}});
});
