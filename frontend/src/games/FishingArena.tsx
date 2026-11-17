import {useEffect,useRef,useState,type CSSProperties} from 'react';
import {Fish,Pause,Play,RotateCw,Waves} from 'lucide-react';
import GameScene from './GameScene';
import {FishPortrait} from './FishingPanel';
import {biteTick,fishingChallenge,fishingStep,initialFishing,maxFishingTicks,replayFishing,type FishingProof,type FishingState} from './fishing-play';
import {points,stringValue,numberValue,type GameInfo,type Round} from './types';
import './fishing-arena.css';

type Phase='aim'|'waiting'|'bite'|'fighting'|'done';
const reasons:Record<string,string>={line_broke:'Леска оборвалась — слишком сильное натяжение.',slack_line:'Рыба сошла с крючка — леска долго была ослаблена.',missed_hook:'Рыба ушла: подсечка не попала в момент поклёвки.',fish_escaped:'Рыба ушла на глубину.'};
interface Props{startLabel?:string;startDisabledReason?:string;round:Round;info:GameInfo;disabled:boolean;lowPower:boolean;onFinish:(proof:FishingProof)=>Promise<void>;onStart:()=>void;onBite:()=>void;verification?:'server'|'fixture'}
export default function FishingArena({round,info,disabled,lowPower,onFinish,onStart,onBite,verification='server',startLabel,startDisabledReason}:Props){
 const challenge=fishingChallenge(round.state);
 const [phase,setPhase]=useState<Phase>(round.status==='active'?'aim':'done'),[castX,setCastX]=useState(0),[fight,setFight]=useState<FishingState>(initialFishing),[paused,setPaused]=useState(false),[holding,setHolding]=useState(false),[notice,setNotice]=useState('');
 const [tick,setTick]=useState(0);
 const phaseRef=useRef(phase),fightRef=useRef(fight),tickRef=useRef(0),held=useRef(false),pausedRef=useRef(false),submitted=useRef(false),lastFrame=useRef(0),accumulator=useRef(0),mounted=useRef(performance.now());
 const proof=useRef<FishingProof>({cast_x:0,cast_tick:0,hook_tick:null,end_tick:0,events:[]});
 const callbacks=useRef({onFinish,onBite});callbacks.current={onFinish,onBite};
 const surface=useRef<HTMLElement>(null);
 const active=round.status==='active';
 const transition=(next:Phase)=>{phaseRef.current=next;setPhase(next);};
 const finish=(state:FishingState,end:number)=>{
  if(submitted.current)return;submitted.current=true;held.current=false;setHolding(false);fightRef.current=state;setFight(state);transition('done');
  proof.current.end_tick=end;
  // Snapshot before sending: retry always submits the same input, not a new catch.
  const snapshot={...proof.current,events:proof.current.events.map(event=>({...event}))};
  try{replayFishing(challenge!,snapshot);}catch{setNotice('Локальный журнал не завершён. Обновите раунд; очки не начислялись.');return;}
  void callbacks.current.onFinish(snapshot);
 };
 useEffect(()=>{
  if(!challenge||!active)return;let frame=0;
  const advance=(now:number)=>{
   const delta=lastFrame.current?Math.min(100,now-lastFrame.current):0;lastFrame.current=now;
   if(!pausedRef.current&&!document.hidden&&phaseRef.current!=='aim'&&phaseRef.current!=='done'){
    accumulator.current+=delta;
    while(accumulator.current>=50&&String(phaseRef.current)!=='done'){
     accumulator.current-=50;tickRef.current++;const t=tickRef.current;setTick(t);
     const bite=biteTick(challenge,proof.current.cast_x);
     if(phaseRef.current==='waiting'&&t>=bite){transition('bite');callbacks.current.onBite();}
     if(phaseRef.current==='bite'&&t>bite+24){finish({...initialFishing(),status:'lost',reason:'missed_hook'},t);break;}
     if(phaseRef.current==='fighting'){
      const state=fishingStep(fightRef.current,challenge,t-proof.current.hook_tick!,held.current);fightRef.current=state;setFight(state);
      if(state.status!=='fighting'){finish(state,t);break;}
     }
     if(t>=maxFishingTicks){finish({...fightRef.current,status:'lost',reason:'fish_escaped'},t);break;}
    }
   }
   frame=requestAnimationFrame(advance);
  };
  const visibility=()=>{lastFrame.current=0;if(document.hidden){pausedRef.current=true;setPaused(true);release();}};
  const observer=new IntersectionObserver(entries=>{if(!entries.some(entry=>entry.isIntersecting)&&phaseRef.current!=='aim'&&phaseRef.current!=='done'){pausedRef.current=true;setPaused(true);release();}});if(surface.current)observer.observe(surface.current);
  document.addEventListener('visibilitychange',visibility);frame=requestAnimationFrame(advance);
  return()=>{cancelAnimationFrame(frame);observer.disconnect();document.removeEventListener('visibilitychange',visibility);};
 },[round.id,active]);
 const record=(value:boolean)=>{
  if(phaseRef.current!=='fighting'||pausedRef.current||disabled||held.current===value)return;
  const events=proof.current.events,t=tickRef.current+1;
  if(events.length>=127&&events[events.length-1]?.tick!==t){setNotice('Слишком частые переключения. Дождитесь конца вываживания.');return;}
  if(events[events.length-1]?.tick===t)events[events.length-1].held=value;else events.push({tick:t,held:value});
  held.current=value;setHolding(value);
 };
 function release(){
  // Releasing during a pause is a real input for the next simulated tick.
  if(held.current&&phaseRef.current==='fighting'){const t=tickRef.current+1,events=proof.current.events;if(events.at(-1)?.tick===t)events[events.length-1].held=false;else if(events.length<128)events.push({tick:t,held:false});held.current=false;setHolding(false);}
 }
 const cast=()=>{if(!active||disabled||phaseRef.current!=='aim')return;proof.current={cast_x:castX,cast_tick:Math.min(5400,Math.floor((performance.now()-mounted.current)/50)),hook_tick:null,end_tick:0,events:[]};tickRef.current=0;accumulator.current=0;lastFrame.current=0;transition('waiting');};
 const hook=()=>{if(disabled||pausedRef.current||!['waiting','bite'].includes(phaseRef.current))return;const t=tickRef.current;proof.current.hook_tick=t;const b=biteTick(challenge!,castX);if(t<b||t>b+24){finish({...initialFishing(),status:'lost',reason:'missed_hook'},Math.max(1,t));return;}fightRef.current=initialFishing();setFight(fightRef.current);transition('fighting');};
 const togglePause=()=>{release();pausedRef.current=!pausedRef.current;setPaused(pausedRef.current);lastFrame.current=0;};
 if(!challenge)return <p role="alert">Локальная рыбалка недоступна в этом раунде.</p>;
 const caught=round.status==='caught',finished=!active;
 const heading=phase==='aim'?'Выберите место заброса':phase==='waiting'?'Следите за поплавком':phase==='bite'?'Клюёт — подсекайте!':phase==='fighting'?'Не дайте леске оборваться':caught?'Рыба в садке':fight.reason?reasons[fight.reason]:reasons[stringValue(round.result,'reason')]??'Ловля завершена';
 const step=phase==='aim'?0:phase==='waiting'||phase==='bite'?1:phase==='fighting'?2:3;
 return <section ref={surface} className={'fishing-arena fishing-phase-'+phase} aria-label="Рыбалка с управлением">
   {round.state.fishing_mode==='boss'&&<div className="fishing-boss-live"><div><strong>{stringValue(round.state,'boss_title')||'Босс локации'}</strong><span>{caught?'Побеждён':active?'Силы: '+Math.max(0,100-Math.round(fight.progress/10))+'%':'Попытка завершена'}</span></div>{active&&<progress aria-label="Силы босса" max="1000" value={Math.max(0,1000-fight.progress)}/>}<p>Уровень сложности {challenge.boss_tier??1} / 3. Удерживайте и отпускайте кнопку чаще; награда появится в садке только после проверки.</p></div>}
   <ol className="fishing-phase-steps" aria-label="Этапы ловли">{['Заброс','Поклёвка','Вываживание','Итог'].map((name,index)=><li key={name} aria-current={index===step?'step':undefined}><span>{index+1}</span>{name}</li>)}</ol>
  <div className="fishing-live-stage"><GameScene game="fishing" round={round} info={info} lowPower={lowPower} liveFishing={{phase,castX,tension:fight.tension,progress:fight.progress}}/>
   <div className="fishing-live-hud"><span><Waves size={17}/>{stringValue(round.state,'location_title')||'Тихий берег'}{round.state.skin==='bear'?' · Медведь':''}</span><strong>Удочка {challenge.rod_level}</strong>{active&&phase!=='aim'&&phase!=='done'&&<button aria-label={paused?'Продолжить ловлю':'Пауза'} onClick={togglePause}>{paused?<Play size={18}/>:<Pause size={18}/>}</button>}</div>
   <div className="fishing-live-title" role="status"><h3>{paused?'Ловля на паузе':heading}</h3><p>{phase==='fighting'?'Удерживайте, чтобы тянуть. Отпускайте, чтобы ослабить леску.':phase==='waiting'?'Не тяните раньше времени. Подсечка — когда поплавок уйдёт под воду.':phase==='aim'?'Ближе к стае рыба клюнет быстрее.':phase==='bite'?'У вас чуть больше секунды.':'Улов и очки сохраняет сервер после проверки.'}</p></div>
  </div>
  {paused&&<button className="fishing-live-primary" onClick={togglePause}><Play size={20}/>Продолжить ловлю</button>}
  <div className="fishing-live-controls">
   {phase==='aim'&&<><label className="fishing-cast-control">Точка заброса<input aria-label="Точка заброса" type="range" min="-1000" max="1000" value={castX} disabled={disabled} onChange={e=>setCastX(Number(e.target.value))}/><span>Стая: {challenge.shoal_x<0?'левее':'правее'} берега</span></label><button className="fishing-live-primary" disabled={disabled} onClick={cast}>Забросить удочку</button></>}
   {(phase==='waiting'||phase==='bite')&&<button className="fishing-live-primary" disabled={disabled||paused||phase==='waiting'} onClick={hook}><Fish size={21}/>{phase==='bite'?'Клюёт! Нажмите: подсечь':'Ждём поклёвку…'}</button>}
   {phase==='fighting'&&<><div className="fishing-tension"><label htmlFor="line-tension">Натяжение <b>{fight.tension}%</b></label><div id="line-tension" role="meter" aria-label="Натяжение лески" aria-valuemin={0} aria-valuemax={100} aria-valuenow={fight.tension} aria-valuetext={fight.tension+'%, рабочая зона от 28 до 78%'} className="fishing-tension-track" style={{'--tension':fight.tension+'%'} as CSSProperties}/><div className="fishing-tension-axis"><span>Слабина</span><span>28–78%: тянем</span><span>Обрыв</span></div><p className="fishing-tension-command" role="status">{fight.tension>78?'Отпустите кнопку: леска может оборваться.':fight.tension<28?'Зажмите кнопку: подтяните леску.':holding?'Тянем рыбу. Перед красной зоной отпустите кнопку.':'Зажмите кнопку, чтобы подтянуть рыбу.'}</p></div><div className="fishing-landing"><label htmlFor="landing-progress">Рыба подтянута <b>{Math.round(fight.progress/10)}%</b></label><progress id="landing-progress" max="1000" value={fight.progress}/></div><button className={'fishing-live-primary fishing-reel'+(holding?' is-held':'')} disabled={disabled||paused} aria-pressed={holding} onContextMenu={event=>event.preventDefault()} onPointerDown={e=>{e.preventDefault();e.currentTarget.setPointerCapture(e.pointerId);record(true);}} onPointerUp={()=>record(false)} onPointerCancel={release} onLostPointerCapture={release} onKeyDown={e=>{if((e.key===' '||e.key==='Enter')&&!e.repeat){e.preventDefault();record(true);}}} onKeyUp={e=>{if(e.key===' '||e.key==='Enter'){e.preventDefault();record(false);}}} onBlur={release}>{holding?'Тянем — следите за натяжением':'Удерживать: тянуть рыбу'}</button></>}
   {phase==='done'&&<>{caught&&<div className="fishing-landed"><FishPortrait name={stringValue(round.result,'species')} rarity={stringValue(round.result,'rarity')}/><div><h3>{stringValue(round.result,'species')}</h3><p>{points(numberValue(round.result,'weight'))} кг · {points(numberValue(round.result,'value'))} очков в садке</p></div></div>}{!finished&&<button className="fishing-live-primary" disabled={disabled} onClick={()=>void callbacks.current.onFinish({...proof.current,events:proof.current.events.map(e=>({...e}))})}><RotateCw size={18}/>Подтвердить тот же заброс</button>}{finished&&<button className="fishing-live-primary" disabled={disabled||!!startDisabledReason} onClick={onStart}>{startLabel??'Новый заброс'} · бесплатно</button>}<p role="status">{verification==='fixture'?'Изолированный тест: настоящие очки и садок не изменяются.':finished?'Результат проверен сервером.':'Отправляем журнал ловли. Повтор не создаёт новый улов.'}</p></>}
   {finished&&startDisabledReason&&<p className="fishing-limit-reason" role="status">{startDisabledReason}</p>}
   {notice&&<p role="alert">{notice}</p>}<span className="sr-only">Прошло {tick} игровых тактов.</span>
  </div>
 </section>;
}
