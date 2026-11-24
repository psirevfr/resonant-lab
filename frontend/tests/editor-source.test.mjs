import assert from 'node:assert/strict';
import test from 'node:test';
import {resolve} from 'node:path';
import {transformSync} from '@babel/core';
import {editorSource} from '../editorSource.mjs';

const compile=(code,options)=>transformSync(code,{
 filename:resolve('src/Toolbar.tsx'),babelrc:false,configFile:false,
 parserOpts:{plugins:['jsx','typescript']},plugins:[[editorSource,options]],
}).code;
const ids=code=>Object.fromEntries(Array.from(code.matchAll(/onClick=\{(\w+)\} data-site-element="([^"]+)"/g),m=>m.slice(1)));

test('The preview and release share element IDs even when moving sibling buttons',()=>{
 const play='<button onClick={play}><Icon/><span>Jouer</span></button>';
 const stop='<button onClick={stop}>Arrêter</button>';
 const source=`export function Toolbar(){return <div className="toolbar">${play}${stop}</div>}`;
 const preview=compile(source,{preview:true});
 assert.match(preview,/data-editor-source/);
 const keys=ids(preview);
 assert.match(keys.play,/^e-[a-f0-9]{24}$/);
 assert.notEqual(keys.play,keys.stop);
 const moved=compile(`\n\nexport function Toolbar(){return <div className="toolbar">${stop}${play}</div>}`,{preview:true});
 assert.deepEqual(ids(moved),keys);
 const release=compile(source,{elements:{[keys.play]:{text:'Écouter'}}});
 assert.doesNotMatch(release,/data-editor-source/);
 assert.deepEqual(ids(release),{play:keys.play});
 assert.match(release,/Jouer/);
 assert.match(release,/from "\.\/SiteElementText"/);
});
