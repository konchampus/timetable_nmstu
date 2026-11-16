/// <reference types="vite/client" />
// Development-only visual/mechanics fixture. Never authenticates or touches a real wallet.
import {createRoot} from 'react-dom/client';
import {useState} from 'react';
import SportsArena from './SportsArena';
import FishingArena from './FishingArena';
import FishingSetup from './FishingSetup';
import GameGuide from './GameGuide';
import GameScene from './GameScene';
import {Cards,Minefield} from './Games';
import {isSport,replay,readChallenge} from './arcade';
import {fishingChallenge,replayFishing} from './fishing-play';
import {gameIds,type GameId,type GameInfo,type Inventory,type Round,type FishingLocationId,type FishingSkinId} from './types';
import fixture from './fishing-world.fixture.json';
import '../styles.css';
import './games.css';
import './player-games.css';
import './game-session.css';
import './arcade-lab.css';
// Generated JSON has heterogeneous payout keys; TS infers absent keys as undefined.
const catalog=fixture.catalog as unknown as GameInfo[];
const levels=fixture.levels as Inventory[];
const makeRound=(game:GameId,id:number,level=1,location='shore',skin='angler'):Round=>({
  id:'local-fixture-'+id,game,status:'active',bet:game==='fishing'?0:10,payout:0,balance:0,version:1,created_at:new Date().toISOString(),
  state:game==='fishing'?{gameplay_version:1,bite_tick:90,shoal_x:-250,surge:7,rod_level:level,location,skin,location_title:levels[0].locations?.find(item=>item.id===location)?.title??'Тихий берег'}:
    game==='blackjack'?{player:['AS','7H'],dealer:['10D','?'],player_total:18,dealer_total:10}:
    game==='mines'?{cells:[0,1,6],values:{0:0,1:1,6:2},mines_count:3,multiplier:1.2}:
    {gameplay_version:1,wind:-85,target_x:120,target_y:-70},result:null,
});
function Lab(){
  const params=new URLSearchParams(location.search),query=params.get('game');
  const initial=gameIds.find(item=>item===query)??'basketball';
  const initialLevel=/^[1-5]$/.test(params.get('level')??'')?Number(params.get('level')):1;
  const initialLocation=levels[initialLevel-1].locations?.find(item=>item.id===params.get('location')&&item.unlocked)?.id??'shore';
  const initialSkin=params.get('skin')==='bear'&&initialLevel>=3?'bear':'angler';
  const [game,setGame]=useState<GameId>(initial),[revision,setRevision]=useState(1);
  const [round,setRound]=useState(()=>makeRound(initial,1));
  const [input,setInput]=useState<unknown>(null),[level,setLevel]=useState(initialLevel),[started,setStarted]=useState(initial!=='fishing');
  const [selection,setSelection]=useState<{location:FishingLocationId;skin:FishingSkinId}>({location:initialLocation,skin:initialSkin});
  const info=catalog.find(item=>item.id===game)!;
  const reset=(g:GameId)=>{setRevision(v=>v+1);setGame(g);setRound(makeRound(g,revision+1,level,selection.location,selection.skin));setInput(null);setStarted(g!=='fishing');};
  const startFishing=()=>{setRevision(v=>v+1);setRound(makeRound('fishing',revision+1,level,selection.location,selection.skin));setInput(null);setStarted(true);};
  return <main className="arcade-lab">
    <header className="arcade-lab-heading"><h1>Визуальный стенд игр</h1><p>Изолированное демо. Без аккаунта, сервера и настоящих очков. Локации и цены взяты из публичных правил; сохранение в БД здесь не проверяется.</p></header>
    <nav className="arcade-lab-nav" aria-label="Тестовая игра">{gameIds.map(g=><button key={g} aria-pressed={game===g} onClick={()=>reset(g)}>{g}</button>)}<button onClick={()=>reset(game)}>Новый тестовый раунд</button></nav>
    <section className="games" data-game={game}>
      <h2 className="arcade-lab-title">{info.title}</h2>
      <GameGuide key={game} info={info} round={started?round:null} busy={false}/>
      {game==='fishing'?<section className="fishing-world">
        {!started&&<><label className="games-field arcade-lab-level">Уровень удочки в демо<select value={level} onChange={e=>{setLevel(Number(e.target.value));setSelection({location:'shore',skin:'angler'});}}>{[1,2,3,4,5].map(value=><option key={value} value={value}>{value}</option>)}</select></label><FishingSetup inventory={levels[level-1]} location={selection.location} skin={selection.skin} disabled={false} locked={false} onChange={setSelection}/><div className="fishing-stage"><GameScene game="fishing" round={null} info={info} lowPower={false} fishingPreview={selection}/></div><button className="games-button arcade-lab-start" onClick={startFishing}>Начать демо ловли · без сервера</button></>}
        {started&&<FishingArena key={round.id} round={round} info={info} disabled={false} lowPower={false} verification="fixture" onBite={()=>{}} onStart={()=>reset('fishing')} onFinish={async proof=>{const outcome=replayFishing(fishingChallenge(round.state)!,proof);setInput(proof);setRound(old=>({...old,status:outcome.status==='caught'?'caught':'lost',version:2,state:{...old.state,fishing:proof,fight:outcome},result:outcome.status==='caught'?{species:'Карп',rarity:'rare',weight:1.25,value:60,fixture:true}:{reason:outcome.reason,escaped:true,fixture:true}}));}}/>}
      </section>:isSport(game)?<SportsArena key={round.id} game={game} round={round} disabled={false} lowPower={false} verification="fixture" onFinish={async shot=>{setInput(shot);const result=replay(game,readChallenge(round.state)!,shot);setRound(old=>({...old,status:result.success===false||result.value===0?'lost':'won',version:2,state:{...old.state,shot},result}));}}/>:
        game==='blackjack'?<div className="game-board-stage"><Cards round={round}/><p className="games-muted">Превью карт. Ходы и выплаты доступны только в настоящем серверном раунде.</p></div>:
        game==='mines'?<div className="game-board-stage"><Minefield round={round} disabled onReveal={()=>{}}/><p className="games-muted">Превью поля. Клетки здесь отключены, настоящий раунд не создан.</p></div>:<GameScene game={game} round={null} info={info} lowPower={false}/>}
    </section>
    <output className="arcade-lab-output" aria-label="Параметры тестовой игры">{input?JSON.stringify({input,result:round.result}):'Демонстрационные данные. Игра ещё не завершена.'}</output>
  </main>;
}
if(import.meta.env.DEV){
  const url=new URL(location.href);
  const mobile=url.searchParams.get('viewport')==='mobile';
  url.searchParams.delete('viewport');
  createRoot(document.getElementById('root')!).render(mobile?<div className="arcade-mobile-frame"><iframe title="Игровой интерфейс: viewport 390 px" src={url.href}/></div>:<Lab/>);
}
