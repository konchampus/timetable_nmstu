import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
// Model the same one/two-pointer transforms used by the live camera without a DOM dependency.
const module={exports:{}};new Function('module','exports',ts.transpileModule(readFileSync(new URL('./board-camera.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(module,module.exports);
const {constrain,zoomAt,focusCell,gestureMoved}=module.exports,v={width:360,height:310};
test('drag moves a magnified board, keeps bounds, and never changes authoritative position',()=>{const player={pos:6},c=focusCell(player.pos,v);const moved=constrain({...c,x:c.x-100,y:c.y+40},v);assert.equal(moved.x,c.x-100);assert.equal(moved.y,c.y+40);assert.equal(player.pos,6);const far=constrain({...c,x:-10000,y:10000},v);assert.equal(far.x,360-704);assert.equal(far.y,0);});
test('two-finger spread enlarges at midpoint and contraction returns to fit, not beyond',()=>{const c={x:-170,y:-200,scale:1},a={x:180,y:155};const spread=zoomAt(c,c.scale*160/80,v,a);assert.equal(spread.scale,2);assert.ok(Number.isFinite(spread.x)&&Number.isFinite(spread.y));const pinch=zoomAt(spread,.01,v,a);assert.equal(pinch.scale,310/704);assert.equal(pinch.y,0);});
test('pointer drag suppresses tile activation only beyond movement threshold',()=>{const moved=gestureMoved;assert.equal(moved(2,2,0,0),false);assert.equal(moved(6,0,0,0),true);assert.equal(moved(0,0,80,100),true);});
