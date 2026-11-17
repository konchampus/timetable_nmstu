import {useEffect,useMemo,useState} from 'react';
import type {FishingLocation,FishingPlayMode,GameplayLimits} from './types';

export default function useFishingLimits(limits:GameplayLimits|undefined,location:FishingLocation|undefined,mode:FishingPlayMode){
  const [,tick]=useState(0);
  // Use a monotonic delta from a server timestamp, not the phone's wall clock.
  const anchor=useMemo(()=>({server:Date.parse(limits?.server_now??''),local:performance.now()}),[limits?.server_now]);
  const next=Date.parse(limits?.next_cast_at??'');
  const seconds=()=>Number.isFinite(next)&&Number.isFinite(anchor.server)?Math.max(0,Math.ceil((next-anchor.server-(performance.now()-anchor.local))/1000)):0;
  const remaining=seconds();
  useEffect(()=>{
    if(!Number.isFinite(next)||!Number.isFinite(anchor.server)||seconds()===0)return;
    const timer=window.setInterval(()=>{tick(value=>value+1);if(seconds()===0)clearInterval(timer);},1000);
    return()=>clearInterval(timer);
  },[next,anchor]);
  let reason='';
  if(limits){
    if(mode==='boss'){
      if(!location?.boss)reason='У этой локации пока нет босса. Выберите обычную ловлю.';
      else if(limits.claimed_bosses.includes(location.boss.id))reason='Награда этого босса уже получена. Новый вызов — после сброса дня.';
      else if(limits.boss_attempts_remaining<=0)reason='Попытки боссов на сегодня закончились.';
    }else if(limits.regular_catches_remaining<=0)reason='Дневной лимит обычного улова исчерпан. Продажа и коллекция остаются доступны.';
    else if(limits.regular_attempts_remaining<=0)reason='Обычные попытки на сегодня закончились.';
    if(!reason&&remaining>0)reason='Следующий заброс через '+remaining+' сек. Лимит общий для всех локаций.';
  }else if(mode==='boss')reason='Для вызова босса обновите состояние игры: сервер ещё не подтвердил лимиты.';
  const resetLabel=limits&&Number.isFinite(Date.parse(limits.resets_at))?new Intl.DateTimeFormat('ru-RU',{timeZone:'Asia/Yekaterinburg',hour:'2-digit',minute:'2-digit'}).format(new Date(limits.resets_at)):'';
  return {remaining,reason,resetLabel};
}
