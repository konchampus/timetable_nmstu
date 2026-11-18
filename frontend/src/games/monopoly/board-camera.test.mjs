import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const module={exports:{}};
new Function('module','exports',ts.transpileModule(readFileSync(new URL('./board-camera.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(module,module.exports);
const {BOARD_SIDE,CELL_SIDE,cellPosition,constrain,focusCell,fitCamera,zoomAt}=module.exports;
test('all 40 cells map uniquely around the board perimeter',()=>{const cells=Array.from({length:40},(_,i)=>cellPosition(i));assert.equal(new Set(cells.map(String)).size,40);for(const [x,y]of cells)assert.ok(x===0||x===10||y===0||y===10);assert.deepEqual(cellPosition(0),[10,10]);assert.deepEqual(cellPosition(10),[0,10]);assert.deepEqual(cellPosition(20),[0,0]);assert.deepEqual(cellPosition(30),[10,0]);});
for(const v of [{width:336,height:300},{width:560,height:510},{width:366,height:400}]){
 test('readable follow mode keeps active cell visible and large at '+v.width,()=>{for(let id=0;id<40;id++){const c=focusCell(id,v),[col,row]=cellPosition(id),x=c.x+col*CELL_SIDE*c.scale,y=c.y+row*CELL_SIDE*c.scale;assert.ok(CELL_SIDE*c.scale>=64);assert.ok(x>=-1&&x+CELL_SIDE*c.scale<=v.width+1);assert.ok(y>=-1&&y+CELL_SIDE*c.scale<=v.height+1);}});
 test('whole field fits while panning is bounded at '+v.width,()=>{const c=fitCamera(v);assert.ok(BOARD_SIDE*c.scale<=v.width+.01&&BOARD_SIDE*c.scale<=v.height+.01);const bounded=constrain({scale:1,x:99999,y:-99999},v);assert.ok(bounded.x<=0);assert.ok(bounded.y>=v.height-BOARD_SIDE);});
}
test('pinch or button zoom preserves the chosen world anchor away from limits',()=>{const v={width:400,height:400},c={x:-150,y:-150,scale:1},a={x:200,y:200};const z=zoomAt(c,1.2,v,a);assert.ok(Math.abs((a.x-c.x)/c.scale-(a.x-z.x)/z.scale)<.001);assert.ok(Math.abs((a.y-c.y)/c.scale-(a.y-z.y)/z.scale)<.001);});
test('zoom limits and viewport growth never expose an unbounded canvas',()=>{const v={width:560,height:480};assert.equal(zoomAt({x:0,y:0,scale:1},100,v).scale,2.5);assert.equal(zoomAt({x:0,y:0,scale:1},0,v).scale,480/BOARD_SIDE);const c=constrain({x:-999,y:999,scale:1},{width:1000,height:900});assert.equal(c.x,(1000-900)/2);assert.equal(c.y,0);});
