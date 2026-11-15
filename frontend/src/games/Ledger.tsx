import {useCallback,useEffect,useRef,useState} from 'react';
import {Coins,RotateCw} from 'lucide-react';
import {api,messageOf} from '../lib/api';
import {points} from './types';

type LedgerKind='start_bonus'|'daily'|'bet'|'payout'|'fishing_sale'|'rod_upgrade';
interface Entry {id:string;round_id:string|null;kind:LedgerKind;amount:number;balance_after:number;created_at:string}
const names:Record<LedgerKind,string>={start_bonus:'Стартовые очки',daily:'Ежедневный бонус',bet:'Ставка в раунде',payout:'Выплата за раунд',fishing_sale:'Продажа улова',rod_upgrade:'Улучшение удочки'};
const time=(value:string)=>new Intl.DateTimeFormat('ru-RU',{timeZone:'Asia/Yekaterinburg',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(value));

export default function Ledger(){
 const [entries,setEntries]=useState<Entry[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[more,setMore]=useState(false);
 const epoch=useRef(0),offset=useRef(0),lock=useRef(false),alive=useRef(true);
 const load=useCallback(async(reset=false)=>{
  if(lock.current)return;lock.current=true;setBusy(true);setError('');const version=++epoch.current;
  try{
   const response=await api<{items:Entry[]}>('/games/ledger?limit=30&offset='+(reset?0:offset.current));
   if(!alive.current||version!==epoch.current)return;
   offset.current=(reset?0:offset.current)+response.items.length;setMore(response.items.length===30);
   setEntries(previous=>{if(reset)return response.items;const ids=new Set(previous.map(item=>item.id));return [...previous,...response.items.filter(item=>!ids.has(item.id))];});
  }catch(cause){if(alive.current&&version===epoch.current)setError(messageOf(cause));}
  finally{lock.current=false;if(alive.current&&version===epoch.current)setBusy(false);}
 },[]);
 useEffect(()=>{alive.current=true;void load(true);return()=>{alive.current=false;};},[load]);
 return <section className="games-inventory" aria-label="Журнал игровых очков">
  <div className="games-section-header"><h2>Движение очков</h2><button className="games-icon-button" disabled={busy} aria-label="Обновить журнал очков" onClick={()=>void load(true)}><RotateCw size={18}/></button></div>
  <p className="games-muted">Начисления и списания из серверного журнала. Это игровые очки без денежной стоимости. Время Магнитогорска.</p>
  {error&&<p role="alert" className="games-alert">{error}<button className="games-back" disabled={busy} onClick={()=>void load(entries.length===0)}>Повторить загрузку</button></p>}
  <div className="games-fish-list" role="list">{entries.map(entry=><div key={entry.id} role="listitem"><Coins size={23}/><span><strong>{names[entry.kind]}</strong><small>{time(entry.created_at)}{entry.round_id?' · раунд '+entry.round_id.slice(0,8):''}</small></span><b>{entry.amount>0?'+':''}{points(entry.amount)}<small>Баланс после: {points(entry.balance_after)}</small></b></div>)}</div>
  {busy&&<p role="status">Загружаем журнал…</p>}
  {!busy&&!error&&entries.length===0&&<p className="games-muted">В журнале пока нет операций.</p>}
  {more&&<button className="games-button games-button-soft" disabled={busy} onClick={()=>void load()}>Ещё операции</button>}
 </section>;
}
