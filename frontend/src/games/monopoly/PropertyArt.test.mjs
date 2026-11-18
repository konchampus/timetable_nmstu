import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';
const require=createRequire(import.meta.url),cache=new Map();
function load(name){if(cache.has(name))return cache.get(name);const module={exports:{}};cache.set(name,module.exports);const code=ts.transpileModule(readFileSync(new URL('./'+name+'.tsx',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;new Function('require','module','exports',code)(path=>path==='./AssetArt'?load('AssetArt'):require(path),module,module.exports);cache.set(name,module.exports);return module.exports;}
const Art=load('PropertyArt').default,ids=[1,3,6,8,9,11,13,14,16,18,19,21,23,24,26,27,29,31,32,34,37,39,5,15,25,35,12,28];
const render=id=>renderToStaticMarkup(React.createElement(Art,{tile:{id,name:'Актив',group:'same',kind:'street'},color:'#123456'}));
test('all 28 purchasable assets have different visible SVG geometry, not only labels or colors',()=>{const hashes=ids.map(id=>createHash('sha256').update(render(id)).digest('hex'));assert.equal(new Set(hashes).size,28);});
test('property artwork remains decorative, colorable vector geometry with no external assets',()=>{for(const id of ids){const svg=render(id);assert.match(svg,/^<svg/);assert.match(svg,/viewBox="0 0 120 100"/);assert.match(svg,/aria-hidden="true"/);assert.match(svg,/#123456/);assert.doesNotMatch(svg,/<image|<img|data:image|https?:|NaN|undefined/);}});
test('non-property board cells still have standalone SVG artwork',()=>{for(const id of [0,10,20,30])assert.match(render(id),/^<svg/);});
