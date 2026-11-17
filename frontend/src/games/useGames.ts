import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, mutationKey } from '../lib/api';
import type { GameId, GameInfo, Inventory, Leaderboard, Round, Wallet, FishingLocationId, FishingSkinId } from './types';
export interface PendingMutation { path: string; body: Record<string, unknown>; title: string; roundId?: string; }
interface Data { catalog: GameInfo[]; wallet: Wallet | null; inventory: Inventory | null; rounds: Round[]; history: Round[]; }
const mergeRounds = (previous: Round[], incoming: Round[]) => {
  const map = new Map(previous.map(round => [round.id, round]));
  for (const round of incoming) { const old = map.get(round.id); if (!old || round.version > old.version) map.set(round.id, round); }
  return [...map.values()].sort((a,b) => b.created_at.localeCompare(a.created_at));
};
export function useGames(onBalanceChange?: (balance: number) => void) {
  const [data, setData] = useState<Data>({catalog:[],wallet:null,inventory:null,rounds:[],history:[]});
  const dataRef=useRef(data);dataRef.current=data;
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false);const [walletFresh,setWalletFresh]=useState(false);
  const [historyLoading,setHistoryLoading]=useState(false),[hasMoreHistory,setHasMoreHistory]=useState(false);const historyOffset=useRef(0),historyLock=useRef(false);
  const [pending, setPending] = useState<PendingMutation | null>(null);
  const [error, setError] = useState(''); const [notice,setNotice]=useState('');
  const pendingRef = useRef<PendingMutation | null>(null); const lock = useRef(false); const generation = useRef(0); const alive=useRef(true);
  const storageKey=useRef<string|null>(null);const identityRequest=useRef<Promise<boolean>|null>(null);
  const [identityReady,setIdentityReady]=useState(false),[persistentRecovery,setPersistentRecovery]=useState(true);
  const savePending=useCallback((request:PendingMutation|null)=>{try{if(storageKey.current){if(request)sessionStorage.setItem(storageKey.current,JSON.stringify(request));else sessionStorage.removeItem(storageKey.current);}}catch{setPersistentRecovery(false);}},[]);
  const identify=useCallback(async()=>{
    if(storageKey.current)return true;if(identityRequest.current)return identityRequest.current;
    identityRequest.current=(async()=>{try{
      const user=await api<{id:number;account_generation:string}>('/me');if(!alive.current)return false;
      if(!Number.isSafeInteger(user.id)||typeof user.account_generation!=='string'||!user.account_generation.trim())throw new Error('Сервер не подтвердил безопасное восстановление аккаунта. Обновите приложение и попробуйте снова.');
      storageKey.current='magtu-games-pending:'+String(user.id)+':'+user.account_generation;setIdentityReady(true);
      try{const saved=sessionStorage.getItem(storageKey.current);if(saved){const value:unknown=JSON.parse(saved);
        if(value&&typeof value==='object'&&'path' in value&&typeof value.path==='string'&&/^\/games\/(rounds(?:\/[a-zA-Z0-9-]+\/actions)?|daily|fishing\/(sell|upgrade))$/.test(value.path)&&'body' in value&&value.body&&typeof value.body==='object'&&'key' in value.body&&typeof value.body.key==='string'&&value.body.key.length<=100&&'title' in value&&typeof value.title==='string'){
          const request:PendingMutation={path:value.path,body:value.body as Record<string,unknown>,title:value.title,...('roundId' in value&&typeof value.roundId==='string'?{roundId:value.roundId}:{})};pendingRef.current=request;setPending(request);setError('Сохранена операция без подтверждённого ответа. Повторите её с прежним ключом; новое списание не создастся.');
        }else sessionStorage.removeItem(storageKey.current);
      }}catch{setPersistentRecovery(false);}
      return true;
    }catch(cause){if(alive.current)setError(errorMessage(cause));return false;}finally{identityRequest.current=null;}})();return identityRequest.current;
  },[]);
  const balanceCallback=useRef(onBalanceChange);balanceCallback.current=onBalanceChange;
  const refresh = useCallback(async () => {
    if(!await identify()){if(alive.current)setLoading(false);return;}
    const epoch=++generation.current;
    const results=await Promise.allSettled([
      api<{items:GameInfo[]}>('/games/catalog'),api<Wallet>('/games/wallet'),api<Inventory>('/games/fishing/inventory'),
      api<{items:Round[]}>('/games/rounds/active'),api<{items:Round[]}>('/games/history?limit=30&offset=0'),
    ] as const);
    if(!alive.current||epoch!==generation.current)return;
    const [catalog,wallet,inventory,active,history]=results;
    const missing=active.status==='fulfilled'?dataRef.current.rounds.filter(round=>round.status==='active'&&!active.value.items.some(item=>item.id===round.id)&&!(history.status==='fulfilled'&&history.value.items.some(item=>item.id===round.id))):[];
    const recovered=await Promise.allSettled(missing.map(round=>api<Round>('/games/rounds/'+encodeURIComponent(round.id))));
    if(!alive.current||epoch!==generation.current)return;
    const recoveredRounds=recovered.flatMap(result=>result.status==='fulfilled'?[result.value]:[]);
    setData(old=>({catalog:catalog.status==='fulfilled'?(JSON.stringify(old.catalog)===JSON.stringify(catalog.value.items)?old.catalog:catalog.value.items):old.catalog,
      wallet:wallet.status==='fulfilled'?wallet.value:old.wallet,inventory:inventory.status==='fulfilled'?inventory.value:old.inventory,
      rounds:mergeRounds(old.rounds,[...(history.status==='fulfilled'?history.value.items:[]),...(active.status==='fulfilled'?active.value.items:[]),...recoveredRounds]),
      history:history.status==='fulfilled'?mergeRounds(old.history,history.value.items):old.history}));
    if(history.status==='fulfilled'){historyOffset.current=Math.max(historyOffset.current,history.value.items.length);setHasMoreHistory(history.value.items.length===30);}
    setWalletFresh(wallet.status==='fulfilled');
    if(wallet.status==='fulfilled')balanceCallback.current?.(wallet.value.balance);
    const failure=[...results,...recovered].find(result=>result.status==='rejected');
    if(failure?.status==='rejected')setError(errorMessage(failure.reason)+' Часть данных могла устареть. Обновите состояние.');
    else if(!pendingRef.current)setError('');
    setLoading(false);
  },[identify]);
  useEffect(()=>{alive.current=true;void refresh();const resume=()=>{if(!document.hidden&&!lock.current)void refresh();};document.addEventListener('visibilitychange',resume);window.addEventListener('online',resume);return()=>{alive.current=false;++generation.current;document.removeEventListener('visibilitychange',resume);window.removeEventListener('online',resume);};},[refresh]);
  const execute=useCallback(async (request:PendingMutation):Promise<Round|null>=>{
    if(lock.current)return null;
    const isReplay=pendingRef.current!==null;
    lock.current=true;setBusy(true);setWalletFresh(false);setError('');setNotice('');++generation.current;
    pendingRef.current=request;setPending(request);savePending(request);
    const controller=new AbortController();const timeout=window.setTimeout(()=>controller.abort(),22000);
    let completed:Round|null=null;
    try {
      const response=await api<Round|{balance:number;reward?:number;sold?:number;rod_level?:number}>(request.path,{method:'POST',body:JSON.stringify(request.body),signal:controller.signal});
      if(!alive.current)return null;
      pendingRef.current=null;setPending(null);savePending(null);
      if(!isReplay){setData(old=>({...old,wallet:old.wallet?{...old.wallet,balance:response.balance}:null}));balanceCallback.current?.(response.balance);}
      if('id' in response){completed=response;setData(old=>({...old,rounds:mergeRounds(old.rounds,[response])}));}
      else if(response.reward!==undefined)setNotice('Ежедневный бонус: '+response.reward+' очков.');
      else if(response.sold!==undefined)setNotice('Продано рыб: '+response.sold+'. Баланс обновлён.');
      else if(response.rod_level!==undefined)setNotice('Удочка улучшена до уровня '+response.rod_level+'.');
      await refresh();
    } catch(cause:unknown) {
      if(!alive.current)return null;
      const status=cause instanceof ApiError?cause.status:0;
      // These are authoritative rejections before any write, not an unknown outcome.
      // Keeping them pending would lock all games until tomorrow's quota reset.
      const quotaRejected=status===429&&cause instanceof ApiError&&['fishing_cooldown','boss_claimed','boss_daily_limit','fishing_catch_daily_limit','fishing_attempt_daily_limit','sports_daily_limit'].includes(cause.code??'');
      const retryable=status===401||status===408||(status===429&&!quotaRejected)||(status===409&&cause instanceof ApiError&&['busy','retry_transaction','transaction_retry'].includes(cause.code??''));
      if(status>=400&&status<500&&!retryable) {
        pendingRef.current=null;setPending(null);savePending(null);
        await refresh();
        if(status===409&&request.roundId){try{const round=await api<Round>('/games/rounds/'+encodeURIComponent(request.roundId));setData(old=>({...old,rounds:mergeRounds(old.rounds,[round])}));}catch{ /* Refresh banner retains recovery action. */ }}
        setError(errorMessage(cause)+(status===409?' Состояние обновлено. Посмотрите раунд и выберите действие заново.':''));
      } else setError(errorMessage(cause)+(status===429?' Подождите секунду перед повтором.':'')+' Результат запроса неизвестен. Повторите сохранённую операцию: ключ и параметры останутся прежними, повторного списания не будет.');
    } finally {clearTimeout(timeout);lock.current=false;if(alive.current)setBusy(false);}
    return completed;
  },[refresh,savePending]);
  const mutate=useCallback((path:string,body:Record<string,unknown>,title:string,roundId?:string)=>{
    if(lock.current||pendingRef.current||!storageKey.current)return Promise.resolve(null);
    const request={path,body:{...body,key:mutationKey()},title,roundId};return execute(request);
  },[execute]);
  const retry=useCallback(()=>pendingRef.current?execute(pendingRef.current):Promise.resolve(null),[execute]);
  const loadMoreHistory=useCallback(async()=>{
    if(historyLock.current||lock.current)return;historyLock.current=true;setHistoryLoading(true);
    try{const page=await api<{items:Round[]}>('/games/history?limit=30&offset='+historyOffset.current);if(!alive.current)return;historyOffset.current+=page.items.length;setHasMoreHistory(page.items.length===30);setData(old=>({...old,history:mergeRounds(old.history,page.items),rounds:mergeRounds(old.rounds,page.items)}));}
    catch(cause){if(alive.current)setError(errorMessage(cause)+' Старые раунды не загрузились. Нажмите «Ещё раунды» повторно.');}
    finally{historyLock.current=false;if(alive.current)setHistoryLoading(false);}
  },[]);
  const loadRound=useCallback(async(id:string)=>{
    try{const round=await api<Round>('/games/rounds/'+encodeURIComponent(id));if(alive.current){setData(old=>({...old,rounds:mergeRounds(old.rounds,[round])}));if(!lock.current)await refresh();}return round;}
    catch(cause){if(alive.current)setError(errorMessage(cause)+' Не удалось открыть раунд. Попробуйте ещё раз.');return null;}
  },[refresh]);
  const action=useCallback((round:Round,action:string,cell?:number)=>mutate('/games/rounds/'+encodeURIComponent(round.id)+'/actions',{action,version:round.version,...(cell!==undefined?{cell}:{})},'Действие: '+action,round.id),[mutate]);
  const start=useCallback((game:GameId,bet:number,choice?:string,mines?:number,gameplayVersion?:1,fishing?:{location:FishingLocationId;skin:FishingSkinId;fishing_mode?:'regular'|'boss'})=>mutate('/games/rounds',{game,bet,...(game==='fishing'&&fishing?fishing:{}),...(choice?{choice}:{}),...(mines!==undefined?{mines}:{}),...(gameplayVersion?{gameplay_version:gameplayVersion}:{})},'Новый раунд'),[mutate]);
  return {...data,loading,busy,pending,error,notice,identityReady,persistentRecovery,walletFresh,historyLoading,hasMoreHistory,loadMoreHistory,refresh,mutate,retry,loadRound,action,start};
}
export function errorMessage(cause:unknown){if(cause instanceof ApiError&&cause.status===401)return 'Telegram-сессия истекла. Откройте приложение заново из бота.';if(cause instanceof Error&&cause.name==='AbortError')return 'Сервер не ответил вовремя.';return cause instanceof Error?cause.message:'Нет связи с сервером.';}
export function useLeaderboard(kind:'wealth'|'fishing') {
  const [board,setBoard]=useState<Leaderboard|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[revision,setRevision]=useState(0);
  useEffect(()=>{let current=true;setLoading(true);setBoard(null);setError('');api<Leaderboard>('/games/leaderboard?kind='+kind).then(value=>{if(current)setBoard(value);}).catch(cause=>{if(current)setError(errorMessage(cause));}).finally(()=>{if(current)setLoading(false);});return()=>{current=false;};},[kind,revision]);
  return {board,error,loading,retry:()=>setRevision(value=>value+1)};
}
