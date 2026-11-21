import test from 'node:test';
import assert from 'node:assert/strict';
import {editorCommand} from '../.test-build/editorShortcuts.mjs';

const context={inside:true,editable:false,blocked:false};
const key=(key,extra={})=>({key,ctrlKey:false,metaKey:false,altKey:false,shiftKey:false,isComposing:false,defaultPrevented:false,...extra});

test('Editor keyboard commands are limited to the focused circuit, with text and modal protection',()=>{
 for(const event of [key('Delete'),key('Backspace'),key('Escape'),key('z',{ctrlKey:true}),key('z',{metaKey:true,shiftKey:true})]){
  for(const protection of [{inside:false},{editable:true},{blocked:true}])assert.equal(editorCommand(event,{...context,...protection}),null);
  assert.equal(editorCommand({...event,isComposing:true},context),null);
  assert.equal(editorCommand({...event,defaultPrevented:true},context),null);
 }
});

test('Delete and Backspace remove a selection; modified text-editing keys do not become destructive commands',()=>{
 for(const name of ['Delete','Backspace']){
  assert.equal(editorCommand(key(name),context),'delete');
  for(const modifier of ['ctrlKey','metaKey','altKey'])assert.equal(editorCommand(key(name,{[modifier]:true}),context),null);
 }
 assert.equal(editorCommand(key('Escape'),context),'escape');
 assert.equal(editorCommand(key('ArrowLeft'),context),null);
});

test('Undo and redo work consistently with Control or Command, including uppercase Z',()=>{
 for(const modifier of ['ctrlKey','metaKey']){
  assert.equal(editorCommand(key('z',{[modifier]:true}),context),'undo');
  assert.equal(editorCommand(key('Z',{[modifier]:true,shiftKey:true}),context),'redo');
 }
 assert.equal(editorCommand(key('z'),context),null);
});
