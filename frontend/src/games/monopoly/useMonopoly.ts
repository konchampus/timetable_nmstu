import {useCallback,useEffect,useRef,useState} from 'react';
import {api,ApiError,messageOf,mutationKey} from '../../lib/api';
import {parseMonopolyLink} from '../monopoly-link';
export interface Tile {id:number;name:string;kind:string;price:number;group:string;build:number;rents:number[];art?:string;}
export interface Player {id:string;name:string;cash:number;pos:number;jailed:boolean;jail:number;cards:string[];out:boolean;ready:boolean;color:string;}
export interface Property {owner:string|null;houses:number;mortgaged:boolean;}
export type ModeId='classic'|'timed20'|'timed40'|'timed60'|'friendly';
export interface Mode {id:ModeId;name?:string;title?:string;description:string;duration_minutes?:number|null;official?:boolean;house_rules?:boolean;}
export interface ContractOffer {id:string;offerer:string;target:string;tiles:number[];turns:number;fee:number;}
export interface Contract {id:string;owner:string;beneficiary:string;tiles:number[];expires_turn:number;fee:number;}
export interface Trade {from:string;target:string;give:number[];take:number[];cash:number;ask:number;give_cards?:string[];take_cards?:string[];redeem_give?:number[];redeem_take?:number[];}
export interface State {rules_version:number;players:Player[];phase:'lobby'|'playing'|'finished';turn:string;properties:Record<string,Property>;dice:number[];doubles:number;rolled:boolean;extra:boolean;pending:number|null;auction:{tile:number;bid:number;bidder:string|null;passed:string[];actor:string;kind?:'building'|'property';building?:'house'|'hotel';placements?:Record<string,number[]>;selected?:Record<string,number>}|null;debt:{player:string;amount:number;creditor:string|null}|null;trade:Trade|null;log:string[];winner:string|null;jail_move?:number;roll_sequence?:number;mode?:ModeId;duration_minutes?:number|null;game_deadline?:string|null;starter_rolls?:unknown;finish_reason?:string;scores?:Record<string,number>;winners?:string[];turn_number?:number;contract_offer?:ContractOffer|null;contracts?:Contract[];}
export interface RoomSummary {id:string;title:string;public:boolean;capacity:number;status:State['phase'];count:number;version:number;mine?:boolean;}
export interface ChatMessage {id:string;player:string;text:string;at:string;}
export interface Room extends RoomSummary {code:string;host:string;you:string;state:State;deadline:string|null;server_now:string;received_at?:number;event_version?:number;messages?:ChatMessage[];}
export interface Pending {path:string;body:Record<string,unknown>;}
export function inviteCode():string {
 return parseMonopolyLink().code;
}

const UUID_SOURCE='[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}';
const UUID=new RegExp('^'+UUID_SOURCE+'$','i');
const COMMAND_PATH=new RegExp('^/monopoly/rooms/('+UUID_SOURCE+')/(actions|join)$');
const ACTIONS=new Set(['create','join','ready','start','leave','color','roll','end','buy','auction','bid','pass','build','sell','mortgage','redeem','bail','jail_card','trade','accept_trade','reject_trade','cancel_trade','bankrupt','resign','timeout','chat','start_build_auction','sell_group','propose_contract','accept_contract','reject_contract','cancel_contract']);
const RECOVERY_MESSAGE='Есть неподтверждённое действие. Повторите его с тем же ключом, чтобы узнать результат.';
const record=(value:unknown):value is Record<string,unknown>=>!!value&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype;
const integer=(value:unknown,min:number,max=Number.MAX_SAFE_INTEGER)=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=min&&value<=max;
/** Storage is untrusted: only replay a complete, known command, never a path prefix. */
export function validPending(value:unknown):value is Pending {
 if(!record(value)||Object.keys(value).sort().join(',')!=='body,path'||typeof value.path!=='string'||!record(value.body))return false;
 const body=value.body,route=COMMAND_PATH.exec(value.path);
 if(value.path!=='/monopoly/rooms'&&(!route||route[0]!==value.path))return false;
 if(typeof body.key!=='string'||body.key.length!==36||!UUID.test(body.key)||!integer(body.version,1)||typeof body.action!=='string'||!ACTIONS.has(body.action))return false;
 if(value.path==='/monopoly/rooms'?!['create','join'].includes(body.action):route?.[2].toLowerCase()==='join'?body.action!=='join':['create','join'].includes(body.action))return false;
 const fields:Record<string,(v:unknown)=>boolean>={
  key:v=>typeof v==='string'&&v.length===36&&UUID.test(v),version:v=>integer(v,1),action:v=>typeof v==='string'&&ACTIONS.has(v),
  title:v=>typeof v==='string'&&v.length>=1&&v.length<=60,nickname:v=>typeof v==='string'&&v.length>=1&&v.length<=30,
  use_telegram_name:v=>typeof v==='boolean',public:v=>typeof v==='boolean',capacity:v=>integer(v,2,6),code:v=>typeof v==='string'&&v.length<=24&&[...v].every(c=>'0123456789abcdefABCDEF'.includes(c)),
  tile:v=>v===null||integer(v,0,39),amount:v=>integer(v,0,1000000),target:v=>v===null||typeof v==='string'&&v.length===36&&UUID.test(v),
  give:v=>Array.isArray(v)&&v.length<=28&&v.every(n=>integer(n,0,39)),take:v=>Array.isArray(v)&&v.length<=28&&v.every(n=>integer(n,0,39)),
  mode:v=>typeof v==='string'&&['classic','timed20','timed40','timed60','friendly'].includes(v),duration_minutes:v=>v===null||integer(v,20,60)&&[20,40,60].includes(v as number),
  give_cards:v=>Array.isArray(v)&&v.length<=2&&v.every(c=>c==='chance'||c==='chest')&&new Set(v).size===v.length,take_cards:v=>Array.isArray(v)&&v.length<=2&&v.every(c=>c==='chance'||c==='chest')&&new Set(v).size===v.length,
  redeem_give:v=>Array.isArray(v)&&v.length<=28&&v.every(n=>integer(n,0,39)),redeem_take:v=>Array.isArray(v)&&v.length<=28&&v.every(n=>integer(n,0,39)),
  contract_tiles:v=>Array.isArray(v)&&v.length>=1&&v.length<=28&&v.every(n=>integer(n,0,39))&&new Set(v).size===v.length,contract_turns:v=>integer(v,1,12),contract_fee:v=>integer(v,0,1000000),
  cash:v=>integer(v,0,1000000),ask:v=>integer(v,0,1000000),color:v=>typeof v==='string'&&v.length===7&&/^#[a-f0-9]{6}$/i.test(v),text:v=>typeof v==='string'&&v.length<=500,
 };
 return Object.entries(body).every(([key,v])=>Object.hasOwn(fields,key)&&fields[key](v));
}

export function useMonopoly(visible:boolean){
 const [room,setRoom]=useState<Room|null>(null),[rooms,setRooms]=useState<RoomSummary[]>([]),[tiles,setTiles]=useState<Tile[]>([]),[colors,setColors]=useState<string[]>([]);
 const [profileName,setProfileName]=useState('');
 const [modes,setModes]=useState<Mode[]>([]),[config,setConfig]=useState<Record<string,unknown>>({}),[rulesSynopsis,setRulesSynopsis]=useState<string[]>([]);
 const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[pending,setPending]=useState<Pending|null>(null),[ready,setReady]=useState(false),[connected,setConnected]=useState(false),[persistent,setPersistent]=useState(true);
 const alive=useRef(false),lifecycle=useRef(0),navigation=useRef(0),working=useRef<object|null>(null);
 const pendingRef=useRef<Pending|null>(null),storage=useRef<string|null>(null),roomRef=useRef<Room|null>(null),initialized=useRef(false);
 const requests=useRef(new Set<AbortController>()),events=useRef<AbortController|null>(null),reading=useRef<AbortController|null>(null),initializing=useRef<Promise<boolean>|null>(null);
 const current=useCallback((life:number,epoch?:number)=>alive.current&&lifecycle.current===life&&(epoch===undefined||navigation.current===epoch),[]);
 const request=useCallback(async<T,>(path:string,controller:AbortController,init:RequestInit={}):Promise<T>=>{
  requests.current.add(controller);
  try{return await api<T>(path,{...init,signal:controller.signal});}finally{requests.current.delete(controller);}
 },[]);
 const navigate=useCallback(()=>{navigation.current+=1;reading.current?.abort();events.current?.abort();reading.current=null;return navigation.current;},[]);
 const apply=useCallback((next:Room,life:number,epoch:number)=>{
  if(!current(life,epoch))return;
  const previous=roomRef.current;
  if(previous?.id===next.id&&(previous.version>next.version||(previous.event_version??0)>(next.event_version??0)))return;
  const value={...next,received_at:next.received_at??Date.now(),messages:next.messages??(previous?.id===next.id?previous.messages:[])};
  roomRef.current=value;setRoom(value);
 },[current]);
 const save=useCallback((value:Pending|null,life:number,key:string|null)=>{
  if(!current(life)||storage.current!==key)return;
  pendingRef.current=value;setPending(value);
  try{if(key){if(value)sessionStorage.setItem(key,JSON.stringify(value));else sessionStorage.removeItem(key);}}catch{setPersistent(false);}
 },[current]);
 const initialize=useCallback((life:number):Promise<boolean>=>{
  if(initialized.current)return Promise.resolve(true);
  if(initializing.current)return initializing.current;
  setLoading(true);
  const controller=new AbortController();
  const task=(async()=>{
   try{
    const [me,board]=await Promise.all([request<{id:number;account_generation:string;name?:string}>('/me',controller),request<{tiles:Tile[];colors:string[];modes?:Mode[];config?:Record<string,unknown>;rules_synopsis?:string[]}>('/monopoly/board',controller)]);
    if(!current(life))return false;
    const key='magtu-monopoly-pending:'+me.id+':'+me.account_generation;
    storage.current=key;pendingRef.current=null;setPending(null);
    let restored=false;
    try{
     const raw=sessionStorage.getItem(key);
     if(raw){let value:unknown;try{value=JSON.parse(raw);}catch{value=null;}
      if(validPending(value)){save(value,life,key);restored=true;}else sessionStorage.removeItem(key);
     }
    }catch{setPersistent(false);}
    setProfileName(typeof me.name==='string'?me.name.trim().replace(/\s+/g,' ').slice(0,30):'');setTiles(board.tiles);setColors(board.colors);setModes(board.modes??[]);setConfig(board.config??{});setRulesSynopsis(board.rules_synopsis??[]);initialized.current=true;setReady(true);
    setError(restored?RECOVERY_MESSAGE:'');return true;
   }catch(e){controller.abort();if(current(life)){setConnected(false);setError(messageOf(e));}return false;}
   finally{if(current(life)){initializing.current=null;setLoading(false);}}
  })();
  initializing.current=task;return task;
 },[current,request,save]);
 const refresh=useCallback(async()=>{
  const life=lifecycle.current,epoch=navigation.current;
  if(!current(life)||!await initialize(life)||!current(life,epoch)||reading.current)return;
  const controller=new AbortController();reading.current=controller;
  const selected=roomRef.current;
  try{
   if(selected){const result=await request<Room>('/monopoly/rooms/'+selected.id,controller);if(!controller.signal.aborted)apply({...result,received_at:Date.now()},life,epoch);}
   else{const result=await request<{items:RoomSummary[]}>('/monopoly/rooms',controller);if(current(life,epoch))setRooms(result.items);}
   if(current(life,epoch)){setConnected(true);setError(pendingRef.current?RECOVERY_MESSAGE:'');}
  }catch(e){if(current(life,epoch)&&!controller.signal.aborted){setConnected(false);setError(messageOf(e));}}
  finally{if(current(life)&&reading.current===controller)reading.current=null;}
 },[apply,current,initialize,request]);
 useEffect(()=>{
  alive.current=true;const life=++lifecycle.current;
  initialized.current=false;initializing.current=null;working.current=null;reading.current=null;
  void refresh();
  return()=>{if(lifecycle.current!==life)return;alive.current=false;lifecycle.current+=1;navigation.current+=1;for(const controller of requests.current)controller.abort();requests.current.clear();};
 },[refresh]);
 useEffect(()=>{
  if(!visible)return;
  const sync=()=>{if(!document.hidden)void refresh();else events.current?.abort();};
  // Discovery and bootstrap recovery need no held room subscription.
  const timer=window.setInterval(()=>{if(!roomRef.current)sync();},5000);
  window.addEventListener('focus',sync);document.addEventListener('visibilitychange',sync);
  return()=>{clearInterval(timer);window.removeEventListener('focus',sync);document.removeEventListener('visibilitychange',sync);};
 },[visible,refresh]);
 useEffect(()=>{
  const id=room?.id;if(!visible||!id)return;
  const life=lifecycle.current;let stopped=false,failures=0,timer:ReturnType<typeof setTimeout>|undefined,wake:(()=>void)|undefined;
  const pause=(ms:number)=>new Promise<void>(resolve=>{wake=resolve;timer=setTimeout(()=>{wake=undefined;resolve();},ms);});
  void(async()=>{
   while(!stopped&&current(life)&&roomRef.current?.id===id){
    if(document.hidden){await pause(1000);continue;}
    const epoch=navigation.current,controller=new AbortController();events.current=controller;
    const cursor=roomRef.current?.event_version??0;
    try{
     const signal=await request<{event_version:number;changed:boolean}>('/monopoly/rooms/'+id+'/events?cursor='+cursor,controller);
     if(stopped||!current(life)||roomRef.current?.id!==id)break;
     if(!current(life,epoch)||controller.signal.aborted){await pause(50);continue;}
     if(!Number.isSafeInteger(signal.event_version)||signal.event_version<0||typeof signal.changed!=='boolean')throw new Error('Некорректный сигнал комнаты');
     if(signal.changed||signal.event_version!==cursor){
      await refresh();
      if(stopped||!current(life)||roomRef.current?.id!==id)break;
      if(!current(life,epoch)||controller.signal.aborted){await pause(100);continue;}
      // A failed/contended read must not turn a changed cursor into a hot loop.
      if((roomRef.current?.event_version??0)<signal.event_version){failures++;await pause(Math.min(15000,1500*2**Math.min(failures-1,4)));continue;}
     }
     if(stopped||!current(life,epoch)||roomRef.current?.id!==id)break;
     failures=0;setConnected(true);
     // Admission floor also protects an older/mock server returning immediate heartbeats.
     await pause(100);
    }catch(e){
     if(stopped||!current(life)||roomRef.current?.id!==id)break;
     if(controller.signal.aborted){await pause(50);continue;}
     failures++;setConnected(false);
     // No extra retrying mutations: read-only fallback only, with bounded backoff.
     if(current(life,epoch))await refresh();
     if(stopped||!current(life)||roomRef.current?.id!==id)break;
     await pause(Math.min(15000,1500*2**Math.min(failures-1,4)));
    }finally{if(events.current===controller)events.current=null;}
   }
  })();
  return()=>{stopped=true;events.current?.abort();events.current=null;if(timer!==undefined)clearTimeout(timer);wake?.();};
 },[visible,room?.id,current,refresh,request]);
 const send=useCallback(async(operation:Pending):Promise<Room|null>=>{
  if(!alive.current||!initialized.current||working.current)return null;
  if(!validPending(operation)){setError('Некорректное действие. Обновите страницу.');return null;}
  const life=lifecycle.current,key=storage.current,token={},epoch=navigate();
  working.current=token;setBusy(true);setError('');save(operation,life,key);
  const controller=new AbortController();
  try{
   const result=await request<Room>(operation.path,controller,{method:'POST',body:JSON.stringify(operation.body)});
   const received={...result,received_at:Date.now()};
   if(!current(life)||storage.current!==key)return null;
   save(null,life,key);
   if(current(life,epoch)){
    if(operation.body.action==='leave'){navigate();roomRef.current=null;setRoom(null);}
    else apply(received,life,epoch);
    setConnected(true);
    // A replay is the historical POST response; GET is the authoritative present.
    // Keep the POST result even if the follow-up GET fails or membership was lost.
    reading.current?.abort();reading.current=null;
    // Reconciliation is read-only and must not hold an acknowledged action busy.
    void refresh();
   }
   return received;
  }catch(e){
   if(current(life)&&storage.current===key){
    // Timeout/rate-limit/auth responses cannot disprove an earlier committed attempt.
    const rejected=e instanceof ApiError&&[400,403,404,405,409,410,422].includes(e.status);
    if(rejected)save(null,life,key);
    if(e instanceof ApiError&&e.status===409&&current(life,epoch)){reading.current?.abort();reading.current=null;await refresh();}
    if(current(life,epoch)){setError(messageOf(e));setConnected(false);}
   }
   return null;
  }finally{if(current(life)&&working.current===token){working.current=null;setBusy(false);}}
 },[apply,current,navigate,refresh,request,save]);
 const mutate=useCallback(async(action:string,body:Record<string,unknown>={},path?:string)=>{
  if(!alive.current||!initialized.current||pendingRef.current||working.current)return null;
  return send({path:path??('/monopoly/rooms/'+roomRef.current?.id+'/actions'),body:{...body,action,key:mutationKey(),version:roomRef.current?.version??1}});
 },[send]);
 const retry=()=>pendingRef.current?send(pendingRef.current):Promise.resolve(null);
 const open=async(id:string)=>{
  if(!alive.current||!initialized.current||pendingRef.current||working.current||id.length!==36||!UUID.test(id))return;
  const life=lifecycle.current,epoch=navigate(),controller=new AbortController();reading.current=controller;
  setBusy(true);
  try{const next=await request<Room>('/monopoly/rooms/'+id,controller);if(current(life,epoch)){apply({...next,received_at:Date.now()},life,epoch);setError('');setConnected(true);}}
  catch(e){if(current(life,epoch)&&!controller.signal.aborted){setError(messageOf(e));setConnected(false);}}
  finally{if(current(life,epoch)){if(reading.current===controller)reading.current=null;setBusy(false);}}
 };
 const lobby=()=>{if(!alive.current)return;navigate();roomRef.current=null;setRoom(null);if(!working.current)setBusy(false);setError(pendingRef.current?RECOVERY_MESSAGE:'');};
 return {room,rooms,tiles,colors,profileName,modes,config,rulesSynopsis,loading,busy,error,pending,ready,connected,persistent,mutate,retry,refresh,open,lobby};
}
