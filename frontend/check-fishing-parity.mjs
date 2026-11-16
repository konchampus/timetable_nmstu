import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('./src/games/fishing-play.ts',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {replayFishing}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
const vectors=JSON.parse(await readFile(new URL('../backend/tests/fishing_play_vectors.json',import.meta.url),'utf8'));
for(const v of vectors){assert.deepEqual(replayFishing(v.challenge,v.proof),v.result);assert.equal(v.result.status,v.name.startsWith('balanced')?'caught':'lost');}
console.log('PASS: '+vectors.length+' fishing replay vectors: land fish, break line, lose through slack; rods 1–5.');
