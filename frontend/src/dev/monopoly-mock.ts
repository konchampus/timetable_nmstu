import fixture from './monopoly.fixture.json';
import type {Room,State,Tile,Mode} from '../games/monopoly/useMonopoly';
// Isolated visual fixtures only. Never imported by the application entry or used as rules.
const HOST='11111111-1111-4111-8111-111111111111',GUEST='22222222-2222-4222-8222-222222222222';
const modes:Mode[]=[
 {id:'classic',name:'Классика',title:'Классика',description:'Классическая экономика. Без таймера партии.',official:false},
 {id:'timed20',name:'20 минут',title:'20 минут',description:'Онлайн-пресет: победитель по капиталу.',duration_minutes:20,official:false},
 {id:'timed40',name:'40 минут',title:'40 минут',description:'Онлайн-пресет: победитель по капиталу.',duration_minutes:40,official:false},
 {id:'timed60',name:'60 минут',title:'60 минут',description:'Онлайн-пресет: победитель по капиталу.',duration_minutes:60,official:false},
 {id:'friendly',name:'Дружеская',title:'Дружеская',description:'Классическая экономика + договоры об аренде. Домашние правила.',official:false},
];
export function monopolyMock(profileName='Демо-пользователь'){
 const params=new URLSearchParams(location.search),scenario=params.get('mono'),colors=['#2254ff','#d54757','#16876a','#b36b13','#8556bd','#087e9b'];
 const state=structuredClone(fixture.state) as State;
 state.mode=params.get('mode')==='friendly'||scenario==='contract'||scenario==='contracts'?'friendly':'classic';state.turn_number=6;state.contract_offer=null;state.contracts=[];
 const r:Room={id:'33333333-3333-4333-8333-333333333333',title:'Демо · вечер с друзьями',public:true,capacity:4,count:2,status:'lobby',version:1,event_version:1,code:'a'.repeat(20),host:HOST,you:params.get('you')==='guest'?GUEST:HOST,state,deadline:null,server_now:new Date().toISOString(),messages:[{id:'demo-message',player:GUEST,text:'Привет! Соберём рыбную отрасль?',at:new Date().toISOString()}]};
 if(scenario&&scenario!=='waiting'){
  r.status='playing';state.phase='playing';state.properties['1'].owner=HOST;state.properties['3'].owner=HOST;state.properties['6'].owner=GUEST;state.players[0].cards=['chance'];state.players[1].cards=['chest'];
 }
 if(scenario==='auction')state.auction={tile:5,bid:150,bidder:GUEST,passed:[],actor:HOST};
 if(scenario==='debt'){state.players[0].cash=0;state.properties['37'].owner=HOST;state.debt={player:HOST,amount:100,creditor:GUEST};}
 if(scenario==='contract')state.contract_offer={id:crypto.randomUUID(),offerer:GUEST,target:HOST,tiles:[6],turns:4,fee:80};
 if(scenario==='contracts')state.contracts=[{id:crypto.randomUUID(),owner:HOST,beneficiary:GUEST,tiles:[1,3],expires_turn:12,fee:60}];
 if(scenario==='trade')state.trade={from:GUEST,target:HOST,give:[6],take:[1],cash:0,ask:50,give_cards:['chest'],take_cards:[],redeem_give:[],redeem_take:[]};
 if(scenario==='finished'){state.phase='finished';r.status='finished';state.winner=HOST;state.winners=[HOST];state.finish_reason='bankruptcy';}
 let exists=Boolean(scenario);const cache=new Map<string,Room>();
 return (path:string,method:string,body:Record<string,any>)=>{
  if(!path.startsWith('/monopoly/'))return null;
  if(path==='/monopoly/board')return {tiles:fixture.tiles,colors,rules_version:2,modes,config:{},rules_synopsis:['1500 в начале и 200 за Старт.','Отказ от покупки запускает аукцион для всех.','Игровые деньги не связаны с общим балансом.']};
  if(path==='/monopoly/rooms'&&method==='GET')return {items:exists?[{...r,mine:true}]:[]};
  if(path.endsWith('/events'))return {event_version:r.event_version,changed:false};
  if(method==='GET')return r;
  if(cache.has(body.key))return cache.get(body.key);
  const me=state.players.find(p=>p.id===r.you)!;
  if(path==='/monopoly/rooms'){exists=true;r.title=body.title||r.title;me.name=body.use_telegram_name?profileName:body.nickname||'Капитан';me.color=body.color||colors[0];state.mode=body.mode||'classic';}
  else if(body.action==='ready')me.ready=!me.ready;
  else if(body.action==='color')me.color=body.color;
  else if(body.action==='chat')r.messages!.push({id:crypto.randomUUID(),player:r.you,text:body.text,at:new Date().toISOString()});
  else if(body.action==='start'){r.status='playing';state.phase='playing';}
  else if(body.action==='roll'){state.roll_sequence=(state.roll_sequence??0)+1;state.dice=[1,1];state.rolled=true;state.pending=8;me.pos=8;state.log.push('Демо: бросок1+1. Это не серверная партия.');}
  else if(body.action==='buy'){if(state.pending!==null){state.properties[state.pending].owner=r.you;me.cash-=(fixture.tiles as Tile[])[state.pending].price;state.pending=null;}}
  else if(body.action==='auction'){state.auction={tile:state.pending??5,bid:0,bidder:null,passed:[],actor:r.you};state.pending=null;}
  else if(body.action==='end'){state.turn=GUEST;state.rolled=false;state.turn_number=(state.turn_number??0)+1;}
  else if(body.action==='trade')state.trade={from:r.you,target:body.target,give:body.give,take:body.take,cash:body.cash,ask:body.ask,give_cards:body.give_cards??[],take_cards:body.take_cards??[],redeem_give:body.redeem_give??[],redeem_take:body.redeem_take??[]};
  else if(['cancel_trade','reject_trade'].includes(body.action))state.trade=null;
  else if(body.action==='accept_trade'&&state.trade){const t=state.trade,a=state.players.find(p=>p.id===t.from)!,b=state.players.find(p=>p.id===t.target)!;a.cash+=t.ask-t.cash;b.cash+=t.cash-t.ask;
   for(const [ids,owner,recipient,cards,redeem] of [[t.give,a,b,t.give_cards??[],t.redeem_give??[]],[t.take,b,a,t.take_cards??[],t.redeem_take??[]]] as const){for(const id of ids){const asset=state.properties[id];asset.owner=recipient.id;if(asset.mortgaged){recipient.cash-=Math.ceil((fixture.tiles as Tile[])[id].price*(redeem.includes(id)?.55:.05));if(redeem.includes(id))asset.mortgaged=false;}}for(const card of cards){owner.cards=owner.cards.filter(c=>c!==card);recipient.cards.push(card);}}
   state.trade=null;state.log.push('Демо: обмен принят. Реальные правила проверяются только сервером.');
  }
  else if(body.action==='mortgage'){const tile=(fixture.tiles as Tile[])[body.tile];state.properties[body.tile].mortgaged=true;me.cash+=Math.floor(tile.price/2);}
  else if(body.action==='redeem'){const tile=(fixture.tiles as Tile[])[body.tile];state.properties[body.tile].mortgaged=false;me.cash-=Math.ceil(tile.price*.55);}
  else if(body.action==='propose_contract')state.contract_offer={id:crypto.randomUUID(),offerer:r.you,target:body.target,tiles:body.contract_tiles,turns:body.contract_turns,fee:body.contract_fee};
  else if(['cancel_contract','reject_contract'].includes(body.action))state.contract_offer=null;
  else if(body.action==='accept_contract'&&state.contract_offer){const o=state.contract_offer;state.contracts!.push({id:o.id,owner:o.offerer,beneficiary:o.target,tiles:o.tiles,expires_turn:(state.turn_number??0)+o.turns,fee:o.fee});me.cash-=o.fee;state.players.find(p=>p.id===o.offerer)!.cash+=o.fee;state.contract_offer=null;}
  else if(body.action==='resign'){me.out=true;state.phase='finished';r.status='finished';state.winner=state.players.find(p=>!p.out)?.id??null;}
  else if(body.action==='leave')exists=false;
  if(state.debt&&state.players.find(p=>p.id===state.debt!.player)!.cash>=state.debt.amount){const debtor=state.players.find(p=>p.id===state.debt!.player)!;debtor.cash-=state.debt.amount;if(state.debt.creditor)state.players.find(p=>p.id===state.debt!.creditor)!.cash+=state.debt.amount;state.debt=null;}
  r.version++;r.event_version=(r.event_version??0)+1;r.server_now=new Date().toISOString();cache.set(body.key,structuredClone(r));return r;
 };
}
