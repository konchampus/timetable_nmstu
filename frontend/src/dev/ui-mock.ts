import {catalog,demoUser,group,teacher,initialNotes,inventory,makeRound,schedule} from './ui-fixtures';
import type {GameId,Round} from '../games/types';
import {isSport,replay,readChallenge} from '../games/arcade';
import type {Note} from '../lib/types';
export const audit={requests:[] as {method:string;path:string;handled:boolean}[],errors:[] as string[]};
export function installMock(){
 const params=new URLSearchParams(location.search);let user=structuredClone(demoUser),notes=structuredClone(initialNotes);let rounds:Round[]=params.get('active')==='1'?(['basketball','blackjack','mines','fishing'] as GameId[]).map(makeRound):[];
 let favorites=[group],daily=true;
 window.Telegram={WebApp:{initData:'query_id=UI_LAB_NOT_VALID_FOR_SERVER&user=%7B%22id%22%3A999999%7D&hash=DEMO_ONLY',colorScheme:params.get('theme')==='dark'?'dark':'light',version:'demo',ready(){},expand(){},onEvent(){},offEvent(){},close(){},requestWriteAccess(cb){cb(false);}}};
 const json=(value:unknown,status=200)=>Promise.resolve(new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}}));
 window.fetch=async(input,init={})=>{
  const url=new URL(typeof input==='string'?input:input instanceof URL?input.href:input.url,location.origin),p=url.pathname.replace(/^\/api/,''),method=(init.method??(input instanceof Request?input.method:'GET')).toUpperCase();
  const row={method,path:url.pathname+url.search,handled:true};audit.requests.push(row);
  if(url.origin!==location.origin||!url.pathname.startsWith('/api/')){row.handled=false;return json({detail:'UI lab: неизвестный URL отклонён локально'},503);}
  let body:Record<string,any>={};try{body=JSON.parse(String(init.body??'{}'));}catch{return json({detail:'Некорректный demo JSON'},400);}
  if(params.get('error')==='schedule'&&p==='/schedule')return json({detail:'Демо: источник расписания временно недоступен'},503);
  if(p==='/auth/telegram'&&method==='POST')return json({token:'UI_LAB_MEMORY_TOKEN_NOT_VALID'});
  if(p==='/me'&&method==='GET')return json(user);
  if(p==='/me'&&method==='DELETE')return Promise.resolve(new Response(null,{status:204}));
  if(p==='/settings'&&method==='PUT'){user={...user,settings:{...user.settings,...body,version:user.settings.version+1}};return json(user.settings);}
  if(p==='/schedule')return json({...schedule,entity:url.searchParams.get('entity')===teacher.id?teacher:group});
  if(p==='/search')return json({items:url.searchParams.get('q')?.includes('нет')?[]:[group,teacher]});
  if(p==='/favorites')return json({items:favorites});
  if(p.startsWith('/favorites/')){favorites=method==='DELETE'?[]:[group];return json({});}
  if(p==='/recent')return json({items:[teacher]});
  if(p.startsWith('/recent/'))return json({});
  if(p==='/notes'&&method==='GET'){const q=url.searchParams.get('q')??'',kind=url.searchParams.get('kind');return json({items:notes.filter(n=>(!kind||n.kind===kind)&&(n.title+n.text).includes(q))});}
  if(p==='/notes'&&method==='POST'){const note={...initialNotes[0],...body,id:'demo-note-'+(notes.length+1),version:1} as Note;notes.unshift(note);return json(note);}
  if(p.startsWith('/notes/')){const old=notes.find(n=>n.id===p.split('/').pop());if(method==='DELETE'){notes=notes.filter(n=>n!==old);return json({});}const note={...old,...body,version:(old?.version??0)+1} as Note;notes=notes.map(n=>n===old?note:n);return json(note);}
  if(p==='/games/catalog')return json({items:catalog});
  if(p==='/games/wallet')return json({balance:1200,inventory_value:120,daily_available:daily,rod_level:3});
  if(p==='/games/fishing/inventory')return json(inventory);
  if(p==='/games/rounds/active')return json({items:rounds.filter(r=>r.status==='active')});
  if(p==='/games/history')return json({items:rounds.filter(r=>r.status!=='active')});
  if(p==='/games/ledger')return json({items:[]});
  if(p==='/games/leaderboard')return json({items:[{rank:1,nickname:'Демо-игрок',score:1200}],self:{rank:null,score:1200}});
  if(p==='/games/daily'){daily=false;return json({balance:1200,reward:100});}
  if(params.get('quota')==='1'&&p==='/games/rounds'&&method==='POST'&&body.game==='fishing')return json({detail:{code:'fishing_attempt_daily_limit',message:'Демо: обычные попытки на сегодня закончились'}},429);
  if(p==='/games/rounds'&&method==='POST'){const r=makeRound(body.game);rounds=[r,...rounds.filter(old=>old.game!==r.game)];return json(r);}
  if(p.startsWith('/games/rounds/')){const id=p.split('/')[3],old=rounds.find(r=>r.id===id);if(!old)return json({detail:'Нет демо-раунда'},404);if(method==='GET')return json(old);const outcome=isSport(old.game)&&body.shot?replay(old.game,readChallenge(old.state)!,body.shot):{value:3,success:true,player_total:18,dealer_total:17};const won=outcome.success!==false&&outcome.value!==0;const r:Round={...old,version:old.version+1,status:won?'won':'lost',payout:won?20:0,result:outcome,state:{...old.state,...(body.shot?{shot:body.shot}:{}),dealer:['10D','7C']}};rounds=rounds.map(o=>o.id===id?r:o);return json(r);}
  row.handled=false;return json({detail:'UI lab: API не замокирован; запрос заблокирован локально'},503);
 };
 // Defense in depth: these paths must never provide an alternate backend transport.
 XMLHttpRequest.prototype.open=function(){throw new Error('UI lab: XMLHttpRequest blocked');};
 navigator.sendBeacon=()=>false;
 window.addEventListener('error',event=>audit.errors.push(event.message));
 window.addEventListener('unhandledrejection',event=>audit.errors.push(String(event.reason)));
 const original=console.error;console.error=(...args:unknown[])=>{audit.errors.push(args.map(String).join(' '));original(...args);};
}
