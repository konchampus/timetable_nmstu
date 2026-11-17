import {Clock3,ShieldCheck,Swords,Trophy} from 'lucide-react';
import {points,type FishingLocation,type FishingPlayMode,type Inventory} from './types';
import useFishingLimits from './useFishingLimits';
import {FishPortrait} from './FishingPanel';
import './fishing-bosses.css';

export default function FishingBossPanel({location,inventory,mode,onModeChange,disabled,locked}:{location:FishingLocation|undefined;inventory:Inventory;mode:FishingPlayMode;onModeChange?:(mode:FishingPlayMode)=>void;disabled:boolean;locked:boolean}){
  const limits=inventory.limits,boss=location?.boss;
  const {remaining,reason,resetLabel}=useFishingLimits(limits,location,mode);
  const claimed=!!boss&&!!limits?.claimed_bosses.includes(boss.id);
  const canChallenge=!!boss&&!!location?.unlocked&&inventory.rod_level>=boss.min_rod_level&&!!limits&&limits.boss_attempts_remaining>0&&!claimed;
  return <div className="fishing-progression">
    {limits&&<section className="fishing-daily" aria-label="Лимиты рыбалки">
      <div><ShieldCheck size={18}/><strong>Ловля без бесконечного фарма</strong></div>
      <dl><div><dt>Улов сегодня</dt><dd>{limits.regular_catches_remaining} / {limits.regular_daily_limit} осталось</dd></div><div><dt>Обычные попытки</dt><dd>{limits.regular_attempts_remaining} / {limits.regular_attempt_daily_limit}</dd></div><div><dt>Вызовы боссов</dt><dd>{limits.boss_attempts_remaining} / {limits.boss_daily_limit}</dd></div></dl>
      <p><Clock3 size={15}/>Перерыв между забросами {limits.cast_cooldown_seconds} сек. Сброс дня — {resetLabel||'00:00'} МСК+2. Смена локации лимиты не обновляет.</p>
    </section>}
    {boss&&<section className="fishing-boss" aria-label={'Босс: '+boss.title}>
      <div className="fishing-boss-heading"><div><Swords size={19}/><h4>{boss.title}</h4></div><span>{claimed?'Побеждён сегодня':'Сложность '+boss.tier+' / 3'}</span></div>
      <div className="fishing-boss-story"><FishPortrait name={boss.reward_species} rarity={inventory.species?.find(item=>item.name===boss.reward_species)?.rarity??'rare'}/><div><p>{boss.description}</p><strong><Trophy size={16}/>{boss.reward_species} · {points(boss.reward_value)} очков при продаже</strong></div></div>
      <p>Босс сильнее обычной рыбы: рывки быстрее, подтягивание медленнее. Награда за каждого босса — один раз за день. Неудача расходует попытку, но не очки.</p>
    </section>}
    {onModeChange&&<fieldset className="fishing-mode" disabled={disabled||locked}><legend>Режим следующего заброса</legend><div><label><input type="radio" name="fishing-play-mode" value="regular" checked={mode==='regular'} onChange={()=>onModeChange('regular')}/><span>Обычная ловля</span></label>{boss&&<label><input type="radio" name="fishing-play-mode" value="boss" checked={mode==='boss'} disabled={!canChallenge} onChange={()=>onModeChange('boss')}/><span>{claimed?'Босс побеждён сегодня':'Вызов босса'}</span></label>}</div></fieldset>}
    {!locked&&reason&&<p className="fishing-limit-reason" role="status">{remaining>0?<Clock3 size={17}/>:<ShieldCheck size={17}/>}<span>{reason}</span></p>}
  </div>;
}
