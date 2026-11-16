import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('./src/games/arcade.ts',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {replay,trajectory}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
const vectors=JSON.parse(await readFile(new URL('../backend/tests/arcade_vectors.json',import.meta.url),'utf8'));
for(const v of vectors){assert.deepEqual(replay(v.game,v.challenge,v.shot),v.result);assert.equal(trajectory(v.challenge,v.shot).length,61);}
console.log('PASS: '+vectors.length+' shared client/server shot vectors.');
