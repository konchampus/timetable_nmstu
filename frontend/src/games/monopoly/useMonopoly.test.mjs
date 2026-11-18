import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

// A small deterministic hooks scheduler: tests the real hook's async ownership,
// not React rendering/DOM. Requests deliberately ignore abort to expose late replies.
const source=readFileSync(new URL('./useMonopoly.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222',KEY='33333333-3333-4333-8333-333333333333';
const storageKey='magtu-monopoly-pending:7:g1';
const snapshot=(id=A,version=1)=>({id,version,event_version:version,messages:[],state:{phase:'lobby'},server_now:new Date().toISOString()});
const envelope=(action='ready',path='/monopoly/rooms/'+A+'/actions')=>({path,body:{action,key:KEY,version:1}});
class ApiError extends Error {constructor(message,status){super(message);this.status=status;}}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function harness({stored={},handler=()=>undefined,visible=false}={}){
 const slots=[],effects=[],calls=[],store=new Map(Object.entries(stored));let cursor=0,dirty=false,mounted=true,writesAfterUnmount=0,model;
 let now=0,nextTimer=1;const timers=new Map(),listeners=new Map();
 const schedule=(fn,ms,interval=false)=>{const id=nextTimer++;timers.set(id,{fn,at:now+ms,ms,interval});return id;};
 const setTimeout=(fn,ms)=>schedule(fn,ms),clearTimeout=id=>timers.delete(id),setInterval=(fn,ms)=>schedule(fn,ms,true),clearInterval=clearTimeout;
 const addEventListener=(name,fn)=>{if(!listeners.has(name))listeners.set(name,new Set());listeners.get(name).add(fn);};
 const removeEventListener=(name,fn)=>listeners.get(name)?.delete(fn);
 const document={hidden:false,addEventListener,removeEventListener};
 const same=(a,b)=>a&&b&&a.length===b.length&&a.every((v,i)=>Object.is(v,b[i]));
 const react={
  useState(initial){const i=cursor++;if(!slots[i])slots[i]={value:initial};return [slots[i].value,next=>{if(!mounted)writesAfterUnmount++;slots[i].value=typeof next==='function'?next(slots[i].value):next;dirty=true;}];},
  useRef(value){const i=cursor++;return slots[i]??=( {current:value} );},
  useCallback(fn,deps){const i=cursor++;if(!slots[i]||!same(slots[i].deps,deps))slots[i]={fn,deps};return slots[i].fn;},
  useEffect(fn,deps){const i=cursor++;if(!slots[i]||!same(slots[i].deps,deps)){const old=slots[i];slots[i]={fn,deps,cleanup:old?.cleanup};effects.push(slots[i]);}},
 };
 const api=async(path,init={})=>{calls.push({path,...init,at:now});const override=handler(path,init,calls);if(override!==undefined)return override;if(path==='/me')return {id:7,account_generation:'g1'};if(path==='/monopoly/board')return {tiles:[{id:0}],colors:['#2254ff']};if(path==='/monopoly/rooms')return {items:[]};if(path.includes('/events?'))return deferred().promise;return snapshot(path.endsWith(B)?B:A);};
 const sessionStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)};
 const exports={};
 new Function('require','exports','sessionStorage','window','document','setTimeout','clearTimeout','clearInterval',compiled)(name=>name==='react'?react:name.includes('monopoly-link')?{parseMonopolyLink:()=>({code:''})}:{api,ApiError,messageOf:e=>e.message,mutationKey:()=>KEY},exports,sessionStorage,{setInterval,addEventListener,removeEventListener},document,setTimeout,clearTimeout,clearInterval);
 function render(){cursor=0;dirty=false;model=exports.useMonopoly(visible);for(const effect of effects.splice(0)){effect.cleanup?.();effect.cleanup=effect.fn();}return model;}
 async function flush(){for(let i=0;i<30;i++){await Promise.resolve();if(dirty&&mounted)render();}return model;}
 function unmount(){mounted=false;for(const slot of slots)slot?.cleanup?.();}
 function strictReplay(){for(const slot of slots)if(slot?.cleanup){slot.cleanup();slot.cleanup=slot.fn();}}
 async function advance(ms){const end=now+ms;await flush();for(let steps=0;;steps++){const due=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!due)break;if(steps>1000)throw new Error('Timer hot spin');const [id,timer]=due;now=timer.at;if(timer.interval)timer.at+=timer.ms;else timers.delete(id);timer.fn();await flush();}now=end;await flush();}
 function setHidden(value){document.hidden=value;for(const fn of listeners.get('visibilitychange')??[])fn();}
 render();return {exports,calls,store,flush,advance,setHidden,unmount,strictReplay,get timerCount(){return timers.size;},get model(){if(dirty&&mounted)render();return model;},get writesAfterUnmount(){return writesAfterUnmount;}};
}

test('recovery validator rejects unsafe paths, bodies, keys and noninteger fields',()=>{
 const {validPending}=harness().exports;
 assert.equal(validPending(envelope()),true);
 assert.equal(validPending(envelope('create','/monopoly/rooms')),true);
 assert.equal(validPending(envelope('join','/monopoly/rooms/'+A+'/join')),true);
 for(const path of ['/monopoly/rooms-evil','/monopoly/rooms/'+A+'/actions/extra','/monopoly/rooms/'+A+'/actions?x=1','/monopoly/rooms/'+A+'/actions'+String.fromCharCode(10),'/MONOPOLY/rooms/'+A+'/actions','/monopoly/rooms/not-a-uuid/actions'])assert.equal(validPending({...envelope(),path}),false,path);
 for(const body of [null,[],{...envelope().body,key:'x'},{...envelope().body,key:KEY+String.fromCharCode(10)},{...envelope().body,version:1.5},{...envelope().body,version:0},{...envelope().body,action:'evil'},{...envelope().body,tile:40},{...envelope().body,give:[1.5]},{...envelope().body,amount:'1'},{...envelope().body,extra:true}])assert.equal(validPending({...envelope(),body}),false);
 assert.equal(validPending(envelope('roll','/monopoly/rooms')),false);
 assert.equal(validPending(envelope('create','/monopoly/rooms/'+A+'/actions')),false);
});

test('restored pending has actionable error and replays same key then GETs authoritative room',async()=>{
 const h=harness({stored:{[storageKey]:JSON.stringify(envelope())},handler:(path,init)=>init.method==='POST'?snapshot(A,1):path==='/monopoly/rooms/'+A?snapshot(A,9):undefined});
 await h.flush();assert.ok(h.model.pending);assert.ok(h.model.error);assert.equal(h.model.ready,true);
 const result=await h.model.retry();await h.flush();
 assert.equal(result.version,1);assert.equal(h.model.room.version,9);assert.equal(h.model.pending,null);assert.equal(h.store.has(storageKey),false);
 assert.equal(JSON.parse(h.calls.find(c=>c.method==='POST').body).key,KEY);assert.equal(typeof h.model.room.received_at,'number');h.unmount();
});

for(const failedPath of ['/me','/monopoly/board'])test('refresh retries failed initialization: '+failedPath,async()=>{
 let fail=true;const h=harness({handler:path=>path===failedPath&&fail?Promise.reject(new ApiError('offline',503)):undefined});
 await h.flush();assert.equal(h.model.ready,false);assert.equal(h.model.loading,false);assert.equal(h.calls.filter(c=>c.path===failedPath).length,1);
 fail=false;await h.model.refresh();await h.flush();assert.equal(h.model.ready,true);assert.equal(h.model.tiles.length,1);assert.equal(h.model.error,'');h.unmount();
});

for(const navigation of ['lobby','openB','leave'])test('late GET A cannot resurrect after '+navigation,async()=>{
 const late=deferred();let hold=false;const h=harness({handler:(path,init)=>path==='/monopoly/rooms/'+A&&init.method!=='POST'&&hold?late.promise:init.method==='POST'?snapshot(A,2):undefined});
 await h.flush();await h.model.open(A);hold=true;const old=h.model.refresh();await h.flush();
 if(navigation==='lobby')h.model.lobby();else if(navigation==='openB')await h.model.open(B);else await h.model.mutate('leave');
 late.resolve(snapshot(A,99));await old;await h.flush();assert.equal(h.model.room?.id??null,navigation==='openB'?B:null);assert.ok(h.calls.some(c=>c.signal?.aborted));h.unmount();
});

for(const status of [0,401,408,429,500,502,503])test('ambiguous '+status+' preserves recovery key',async()=>{
 const h=harness({handler:(path,init)=>init.method==='POST'?Promise.reject(new ApiError('uncertain',status)):undefined});await h.flush();await h.model.open(A);await h.model.mutate('ready');await h.flush();assert.equal(h.model.pending.body.key,KEY);assert.equal(JSON.parse(h.store.get(storageKey)).body.key,KEY);h.unmount();
});
for(const status of [400,403,404,409,422])test('known business rejection '+status+' clears recovery',async()=>{
 const h=harness({handler:(path,init)=>init.method==='POST'?Promise.reject(new ApiError('rejected',status)):undefined});await h.flush();await h.model.open(A);await h.model.mutate('ready');await h.flush();assert.equal(h.model.pending,null);assert.equal(h.store.has(storageKey),false);h.unmount();
});

test('post replay remains successful when authoritative GET fails',async()=>{
 const h=harness({stored:{[storageKey]:JSON.stringify(envelope())},handler:(path,init)=>init.method==='POST'?snapshot(A,2):path==='/monopoly/rooms/'+A?Promise.reject(new ApiError('gone',403)):undefined});await h.flush();const result=await h.model.retry();await h.flush();assert.equal(result.version,2);assert.equal(h.model.room.version,2);assert.equal(h.model.pending,null);assert.equal(h.model.error,'gone');h.unmount();
});

test('navigating to lobby while POST pending processes journal but does not navigate back',async()=>{
 const late=deferred();const h=harness({handler:(path,init)=>init.method==='POST'?late.promise:undefined});await h.flush();await h.model.open(A);const post=h.model.mutate('ready');h.model.lobby();late.resolve(snapshot(A,2));await post;await h.flush();assert.equal(h.model.room,null);assert.equal(h.model.pending,null);h.unmount();
});

test('unmount aborts mutation, ignores late response and retains pending storage',async()=>{
 const late=deferred();const h=harness({handler:(path,init)=>init.method==='POST'?late.promise:undefined});await h.flush();await h.model.open(A);const post=h.model.mutate('ready');h.unmount();assert.equal(h.calls.at(-1).signal.aborted,true);late.resolve(snapshot(A,2));assert.equal(await post,null);await h.flush();assert.equal(h.writesAfterUnmount,0);assert.equal(h.store.has(storageKey),true);
});

test('StrictMode replay ignores earlier bootstrap and binds storage to current account generation',async()=>{
 const old=deferred();let count=0;const h=harness({stored:{[storageKey]:JSON.stringify(envelope())},handler:path=>path==='/me'?(++count===1?old.promise:{id:7,account_generation:'g2'}):undefined});h.strictReplay();await h.flush();old.resolve({id:7,account_generation:'g1'});await h.flush();assert.equal(h.model.ready,true);assert.equal(h.model.pending,null);await h.model.open(A);await h.model.mutate('ready');assert.equal(h.store.has(storageKey),true);h.unmount();
});

test('409 conflict refetches authoritative state and preserves business error',async()=>{
 let version=1;const h=harness({handler:(path,init)=>init.method==='POST'?(version=7,Promise.reject(new ApiError('conflict',409))):path==='/monopoly/rooms/'+A?snapshot(A,version):undefined});await h.flush();await h.model.open(A);await h.model.mutate('ready');await h.flush();assert.equal(h.model.room.version,7);assert.equal(h.model.error,'conflict');h.unmount();
});

test('POST completion supersedes a GET begun before commit',async()=>{
 const post=deferred(),get=deferred();let hold=false;const h=harness({handler:(path,init)=>init.method==='POST'?post.promise:path==='/monopoly/rooms/'+A&&hold?get.promise:undefined});await h.flush();await h.model.open(A);const mutation=h.model.mutate('ready');hold=true;const precommit=h.model.refresh();await h.flush();hold=false;post.resolve(snapshot(A,2));await mutation;get.resolve(snapshot(A,1));await precommit;await h.flush();assert.equal(h.model.room.version,2);assert.ok(h.calls.filter(c=>c.path==='/monopoly/rooms/'+A).length>=3);h.unmount();
});

const eventsCalls=h=>h.calls.filter(c=>c.path.includes('/events?'));
const roomCalls=(h,id=A)=>h.calls.filter(c=>c.path==='/monopoly/rooms/'+id&&c.method!=='POST');
const withEvent=(event_version,messages=[])=>({...snapshot(A,1),event_version,messages});

test('visible events unmount during changed refresh aborts read and never writes or schedules afterwards',async t=>{
 const event=deferred(),read=deferred();let holding=false;
 const h=harness({visible:true,handler:path=>path.includes('/events?')?event.promise:path==='/monopoly/rooms/'+A&&holding?read.promise:undefined});t.after(()=>h.unmount());
 await h.flush();await h.model.open(A);await h.flush();assert.equal(eventsCalls(h).length,1,'visible=true must actually start events effect');
 holding=true;event.resolve({changed:true,event_version:2});await h.flush();assert.equal(roomCalls(h).length,2,'changed event starts authoritative refresh');
 h.unmount();assert.equal(roomCalls(h).at(-1).signal.aborted,true);read.resolve(withEvent(2));await h.flush();
 assert.equal(h.writesAfterUnmount,0);assert.equal(h.timerCount,0,'no orphan pause timer after cleanup');assert.equal(eventsCalls(h).length,1);
});

test('same game version cannot regress event cursor or chat messages',async t=>{
 let response=withEvent(9,[{id:'new'}]);const h=harness({visible:true,handler:path=>path==='/monopoly/rooms/'+A?response:undefined});t.after(()=>h.unmount());
 await h.flush();await h.model.open(A);await h.flush();response=withEvent(8,[{id:'old'}]);await h.model.refresh();await h.flush();
 assert.equal(h.model.room.version,1);assert.equal(h.model.room.event_version,9);assert.equal(h.model.room.messages[0].id,'new');assert.equal(eventsCalls(h).length,1,'snapshot updates do not restart held events');
});

test('aborted precommit chat GET with identical game version cannot overwrite postcommit events',async t=>{
 const post=deferred(),oldRead=deferred();let held=false,eventVersion=1;
 const h=harness({visible:true,handler:(path,init)=>init.method==='POST'?post.promise:path==='/monopoly/rooms/'+A?(held?oldRead.promise:withEvent(eventVersion,[{id:'m'+eventVersion}])):undefined});t.after(()=>h.unmount());
 await h.flush();await h.model.open(A);await h.flush();const mutation=h.model.mutate('chat',{text:'hello'});held=true;const stale=h.model.refresh();await h.flush();
 held=false;eventVersion=2;post.resolve(withEvent(2));await mutation;oldRead.resolve(withEvent(1,[{id:'old'}]));await stale;await h.flush();
 assert.equal(h.model.room.version,1);assert.equal(h.model.room.event_version,2);assert.equal(h.model.room.messages[0].id,'m2');
});

test('changed event with failing 503 snapshot backs off instead of hot spinning',async t=>{
 let fail=false;const h=harness({visible:true,handler:path=>path.includes('/events?')?{changed:true,event_version:2}:path==='/monopoly/rooms/'+A?(fail?Promise.reject(new ApiError('snapshot unavailable',503)):snapshot()):undefined});t.after(()=>h.unmount());
 await h.flush();fail=false;await h.model.open(A);fail=true;await h.flush();assert.equal(eventsCalls(h).length,1);
 await h.advance(1499);assert.equal(eventsCalls(h).length,1,'no100ms retry while snapshot failed');
 await h.advance(1);assert.equal(eventsCalls(h).length,2);await h.advance(2999);assert.equal(eventsCalls(h).length,2,'second retry exponentially delayed');
 await h.advance(1);assert.equal(eventsCalls(h).length,3);await h.advance(55500);assert.ok(eventsCalls(h).length<=8,'bounded attempts over60seconds');
 assert.equal(h.model.connected,false,'event HTTP success does not hide snapshot failure');assert.equal(h.model.room.event_version,1);
});

test('event endpoint503 uses bounded read-only fallback and no mutation retry',async t=>{
 const h=harness({visible:true,handler:path=>path.includes('/events?')?Promise.reject(new ApiError('events unavailable',503)):undefined});t.after(()=>h.unmount());
 await h.flush();await h.model.open(A);await h.flush();assert.equal(eventsCalls(h).length,1);assert.equal(roomCalls(h).length,2,'fallback GET runs once');
 await h.advance(1499);assert.equal(eventsCalls(h).length,1);await h.advance(1);assert.equal(eventsCalls(h).length,2);
 await h.advance(58500);assert.ok(eventsCalls(h).length<=8,'events failures cannot saturate12/min admission');assert.equal(h.calls.filter(c=>c.method==='POST').length,0,'fallback is read-only');
});

test('changed event while reading is occupied backs off without starving the authoritative read',async t=>{
 const firstEvent=deferred(),read=deferred();let held=false,first=true;
 const h=harness({visible:true,handler:path=>path.includes('/events?')?(first?(first=false,firstEvent.promise):path.endsWith('cursor=1')?{changed:true,event_version:2}:deferred().promise):path==='/monopoly/rooms/'+A&&held?read.promise:undefined});t.after(()=>h.unmount());
 await h.flush();await h.model.open(A);await h.flush();held=true;const reading=h.model.refresh();await h.flush();firstEvent.resolve({changed:true,event_version:2});await h.flush();
 assert.equal(roomCalls(h).length,2,'events do not duplicate an occupied GET');await h.advance(1499);assert.equal(eventsCalls(h).length,1);await h.advance(1);assert.equal(eventsCalls(h).length,2);assert.equal(roomCalls(h).length,2);
 read.resolve(withEvent(2));await reading;await h.flush();await h.advance(3000);
 assert.equal(h.model.room.event_version,2);assert.equal(eventsCalls(h).at(-1).path.endsWith('cursor=2'),true,'subscription catches up from authoritative response');assert.equal(roomCalls(h).length,2);
});

for(const destination of ['lobby','openB'])test('held visible events abort on navigation to '+destination+' and ignore late signal',async t=>{
 const oldEvent=deferred();const h=harness({visible:true,handler:path=>path.includes('/'+A+'/events?')?oldEvent.promise:undefined});t.after(()=>h.unmount());
 await h.flush();await h.model.open(A);await h.flush();const request=eventsCalls(h)[0];assert.ok(request);
 if(destination==='lobby')h.model.lobby();else await h.model.open(B);await h.flush();assert.equal(request.signal.aborted,true);
 const readsBefore=roomCalls(h).length;oldEvent.resolve({changed:true,event_version:999});await h.flush();await h.advance(2000);
 assert.equal(h.model.room?.id??null,destination==='openB'?B:null);assert.equal(roomCalls(h).length,readsBefore,'late A signal never starts GET A');
 if(destination==='openB')assert.equal(eventsCalls(h).filter(c=>c.path.includes('/'+B+'/events?')).length,1);
});

test('document hidden aborts held events and keeps network quiet until visible',async t=>{
 const event=deferred();let first=true;const h=harness({visible:true,handler:path=>path.includes('/events?')&&first?(first=false,event.promise):undefined});t.after(()=>h.unmount());
 await h.flush();await h.model.open(A);await h.flush();h.setHidden(true);assert.equal(eventsCalls(h)[0].signal.aborted,true);
 event.resolve({changed:false,event_version:1});await h.flush();await h.advance(10000);assert.equal(eventsCalls(h).length,1);
 h.setHidden(false);await h.flush();await h.advance(1000);assert.equal(eventsCalls(h).length,2,'visible wakes room subscription');
});

test('accepted POST releases busy and resolves before a slow reconciliation GET',async t=>{
 const late=deferred();let holding=false;
 const h=harness({handler:(path,init)=>init.method==='POST'?(holding=true,snapshot(A,2)):path==='/monopoly/rooms/'+A&&holding?late.promise:undefined});t.after(()=>h.unmount());
 await h.flush();await h.model.open(A);let done=false;const post=h.model.mutate('ready').then(result=>{done=true;return result;});await h.flush();
 assert.equal(done,true,'POST acknowledgement is independent of slow GET');assert.equal(h.model.busy,false);assert.equal(h.model.room.version,2);assert.equal(h.model.pending,null);
 late.resolve(snapshot(A,3));await post;await h.flush();assert.equal(h.model.room.version,3);
});

test('new modes, card trades, building auctions and contracts pass strict recovery validation',async t=>{
 const h=harness();t.after(()=>h.unmount());const valid=h.exports.validPending;
 assert.equal(valid({path:'/monopoly/rooms',body:{action:'create',key:KEY,version:1,mode:'friendly',capacity:4,nickname:'Иван'}}),true);
 for(const action of ['sell_group','start_build_auction'])assert.equal(valid({path:'/monopoly/rooms/'+A+'/actions',body:{action,key:KEY,version:1,tile:1}}),true);
 const contract={path:'/monopoly/rooms/'+A+'/actions',body:{action:'propose_contract',key:KEY,version:1,target:B,contract_tiles:[1,3],contract_turns:4,contract_fee:100}};
 assert.equal(valid(contract),true);
 for(const extra of [{contract_turns:0},{contract_turns:13},{contract_turns:true},{contract_tiles:[1,1]},{contract_fee:-1},{mode:'unknown'}])assert.equal(valid({...contract,body:{...contract.body,...extra}}),false);
 assert.equal(valid({path:'/monopoly/rooms/'+A+'/actions',body:{action:'trade',key:KEY,version:1,give_cards:['chance'],take_cards:['chest'],redeem_give:[1],redeem_take:[]}}),true);
 assert.equal(valid({path:'/monopoly/rooms/'+A+'/actions',body:{action:'trade',key:KEY,version:1,give_cards:['chance','chance']}}),false);
});
test('server mode metadata is exposed without inventing modes on legacy responses',async t=>{
 const metadata={tiles:[],colors:[],modes:[{id:'friendly',name:'Дружеская',description:'Домашний режим'}],config:{rules_version:2},rules_synopsis:['Аукцион при отказе']};
 const h=harness({handler:path=>path==='/monopoly/board'?metadata:undefined});t.after(()=>h.unmount());await h.flush();
 assert.deepEqual(h.model.modes,metadata.modes);assert.deepEqual(h.model.rulesSynopsis,metadata.rules_synopsis);assert.deepEqual(h.model.config,metadata.config);
});

test('verified profile name loads from authenticated me and Telegram-name commands remain retryable',async t=>{
 const h=harness({handler:path=>path==='/me'?{id:7,account_generation:'g1',name:'  Анна  Петрова  '}:undefined});t.after(()=>h.unmount());await h.flush();
 assert.equal(h.model.profileName,'Анна Петрова');
 const command={path:'/monopoly/rooms',body:{key:KEY,version:1,action:'create',use_telegram_name:true}};
 assert.equal(h.exports.validPending(command),true);
 assert.equal(h.exports.validPending({...command,body:{...command.body,use_telegram_name:'true'}}),false);
});

test('malformed stored JSON is discarded without pretending storage is unavailable',async()=>{
 const h=harness({stored:{[storageKey]:'{broken'}});await h.flush();assert.equal(h.model.persistent,true);assert.equal(h.model.pending,null);assert.equal(h.store.has(storageKey),false);h.unmount();
});
