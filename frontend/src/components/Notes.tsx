import {useEffect,useRef,useState} from 'react';
import {ArrowLeft,Check,NotebookPen,Plus,Trash2,X} from 'lucide-react';
import {api,ApiError,messageOf,mutationKey} from '../lib/api';
import type {Lesson,Note} from '../lib/types';

export interface NoteContext {lesson:Lesson;date:string;source_entity:string|null}
interface Draft {title:string;text:string;kind:'note'|'homework';date:string;lesson_id:string|null;source_entity:string|null;subject:string;done:boolean}
interface SaveIntent {path:string;method:'POST'|'PUT';body:string}
const blank:Draft={title:'',text:'',kind:'note',date:'',lesson_id:null,source_entity:null,subject:'',done:false};
const pageSize=30;

export default function Notes({context,onBack,onDirtyChange}:{context:NoteContext|null;onBack:()=>void;onDirtyChange:(dirty:boolean)=>void}){
 const [items,setItems]=useState<Note[]>([]);
 const [draft,setDraft]=useState<Draft>(context?{...blank,title:context.lesson.title,subject:context.lesson.title,date:context.date,lesson_id:context.lesson.id,source_entity:context.source_entity}:blank);
 const [editing,setEditing]=useState<Note|null>(null),[open,setOpen]=useState(Boolean(context));
 const [error,setError]=useState(''),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
 const [query,setQuery]=useState(''),[kind,setKind]=useState<'all'|'note'|'homework'>('all');
 const [deleting,setDeleting]=useState<string|null>(null),[hasMore,setHasMore]=useState(false),[revision,setRevision]=useState(0);
 const [baseline,setBaseline]=useState(()=>JSON.stringify(draft)),[requestId,setRequestId]=useState(mutationKey);
 const [uncertain,setUncertain]=useState(false);
 const intent=useRef<SaveIntent|null>(null),mutationLock=useRef(false),loadLock=useRef(false);
 const requestEpoch=useRef(0),offset=useRef(0),mounted=useRef(true);
 const dirty=open&&(JSON.stringify(draft)!==baseline||uncertain||busy);
 useEffect(()=>{onDirtyChange(dirty);return ()=>onDirtyChange(false);},[dirty,onDirtyChange]);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;++requestEpoch.current;};},[]);
 useEffect(()=>{const warn=(event:BeforeUnloadEvent)=>{if(dirty){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[dirty]);

 function listPath(start:number){const params=new URLSearchParams({q:query,limit:String(pageSize),offset:String(start)});if(kind!=='all')params.set('kind',kind);return '/notes?'+params.toString();}
 useEffect(()=>{
  const epoch=++requestEpoch.current,controller=new AbortController();
  offset.current=0;loadLock.current=false;setHasMore(false);setLoading(true);setItems([]);
  const timer=window.setTimeout(()=>{
   const params=new URLSearchParams({q:query,limit:String(pageSize),offset:'0'});if(kind!=='all')params.set('kind',kind);
   api<{items:Note[]}>('/notes?'+params.toString(),{signal:controller.signal}).then(response=>{
    if(epoch!==requestEpoch.current||!mounted.current)return;
    setItems(response.items);offset.current=response.items.length;setHasMore(response.items.length===pageSize);
   }).catch(cause=>{if(epoch===requestEpoch.current&&!controller.signal.aborted)setError(messageOf(cause));})
   .finally(()=>{if(epoch===requestEpoch.current&&!controller.signal.aborted)setLoading(false);});
  },250);
  return()=>{clearTimeout(timer);controller.abort();};
 },[query,kind,revision]);

 async function loadMore(){
  if(loadLock.current||loading||mutationLock.current)return;
  loadLock.current=true;setLoading(true);const epoch=requestEpoch.current;
  try{
   const response=await api<{items:Note[]}>(listPath(offset.current));
   if(epoch!==requestEpoch.current||!mounted.current)return;
   offset.current+=response.items.length;setHasMore(response.items.length===pageSize);
   setItems(previous=>{const known=new Set(previous.map(note=>note.id));return [...previous,...response.items.filter(note=>!known.has(note.id))];});
  }catch(cause){if(epoch===requestEpoch.current&&mounted.current)setError(messageOf(cause));}
  finally{if(epoch===requestEpoch.current&&mounted.current){loadLock.current=false;setLoading(false);}}
 }
 function mayDiscard(){return !dirty||window.confirm(uncertain?'Ответ на сохранение не получен: запись уже могла сохраниться на сервере. Выйти без подтверждения?':'Есть несохранённые изменения. Закрыть без сохранения?');}
 function begin(value:Draft,note:Note|null){
  if(mutationLock.current||!mayDiscard())return;
  intent.current=null;setUncertain(false);setEditing(note);setDraft(value);setBaseline(JSON.stringify(value));setRequestId(mutationKey());setOpen(true);setError('');
 }
 function edit(note:Note){begin({title:note.title,text:note.text,kind:note.kind,date:note.date??'',lesson_id:note.lesson_id,source_entity:note.source_entity,subject:note.subject??'',done:note.done},note);}
 async function save(){
  if(mutationLock.current||!draft.title.trim())return;
  mutationLock.current=true;setBusy(true);setError('');
  if(!intent.current){
   const body={title:draft.title.trim(),text:draft.text,kind:draft.kind,date:draft.date||null,lesson_id:draft.lesson_id,source_entity:draft.source_entity,subject:draft.subject.trim()||null,...(editing?{version:editing.version,done:draft.done}:{request_id:requestId})};
   intent.current={path:'/notes'+(editing?'/'+editing.id:''),method:editing?'PUT':'POST',body:JSON.stringify(body)};
  }
  const request=intent.current;
  try{
   const saved=await api<Note>(request.path,{method:request.method,body:request.body});
   if(!mounted.current)return;
   intent.current=null;setUncertain(false);setItems(previous=>[saved,...previous.filter(note=>note.id!==saved.id)]);
   setOpen(false);setEditing(null);setDraft(blank);setBaseline(JSON.stringify(blank));setRequestId(mutationKey());setRevision(value=>value+1);
  }catch(cause){
   if(!mounted.current)return;
   const unknown=!(cause instanceof ApiError)||cause.status===0||cause.status>=500||cause.status===408;
   setUncertain(unknown);
   if(!unknown)intent.current=null;
   setError(unknown?'Ответ сервера не получен. Повторите сохранение: отправятся те же поля и тот же request_id. До ответа редактирование приостановлено.':cause instanceof ApiError&&cause.status===409?'Запись или её версия уже изменились. Ваш текст оставлен в редакторе; скопируйте его перед загрузкой актуальной записи.':messageOf(cause));
  }finally{mutationLock.current=false;if(mounted.current)setBusy(false);}
 }
 async function toggle(note:Note){
  if(mutationLock.current)return;mutationLock.current=true;setBusy(true);setError('');
  try{const {id,updated_at,lesson_status,...fields}=note;void updated_at;void lesson_status;const updated=await api<Note>('/notes/'+id,{method:'PUT',body:JSON.stringify({...fields,done:!note.done})});if(mounted.current)setItems(previous=>previous.map(value=>value.id===id?updated:value));}
  catch(cause){if(mounted.current)setError(messageOf(cause));}
  finally{mutationLock.current=false;if(mounted.current)setBusy(false);}
 }
 async function remove(note:Note){
  if(mutationLock.current)return;mutationLock.current=true;setBusy(true);setError('');
  try{await api('/notes/'+note.id+'?version='+note.version,{method:'DELETE'});if(mounted.current){setItems(previous=>previous.filter(value=>value.id!==note.id));setDeleting(null);setRevision(value=>value+1);}}
  catch(cause){if(mounted.current)setError(messageOf(cause));}
  finally{mutationLock.current=false;if(mounted.current)setBusy(false);}
 }
 return <section>
  <div className="page-title"><div><button className="back-link" onClick={onBack}><ArrowLeft size={17}/>Назад</button><h1>Заметки и ДЗ</h1><p>Только ваши записи. Не видны участникам.</p></div><button className="icon-button" aria-label="Создать заметку" disabled={busy} onClick={()=>begin(blank,null)}><Plus size={22}/></button></div>
  {error&&<div className="error-message" role="alert"><p>{error}</p>{!open&&<button className="text-button" onClick={()=>{setError('');setRevision(value=>value+1);}}>Обновить записи</button>}</div>}
  {open?<form className="note-editor" onSubmit={event=>{event.preventDefault();void save();}}>
   <div className="section-title"><h2>{editing?'Редактировать':'Новая запись'}</h2><button type="button" className="icon-button" aria-label="Закрыть редактор" disabled={busy} onClick={()=>{if(mayDiscard()){intent.current=null;setUncertain(false);setOpen(false);}}}><X size={20}/></button></div>
   <fieldset disabled={busy||uncertain}>
    <legend className="sr-only">Содержимое записи</legend>
    <label className="field">Заголовок<input autoFocus required maxLength={200} value={draft.title} onChange={event=>setDraft({...draft,title:event.target.value})}/></label>
    <div className="form-pair"><label className="field">Тип<select value={draft.kind} onChange={event=>setDraft({...draft,kind:event.target.value as Draft['kind']})}><option value="note">Заметка</option><option value="homework">Домашнее задание</option></select></label><label className="field">Дата<input type="date" value={draft.date} onChange={event=>setDraft({...draft,date:event.target.value})}/></label></div>
    <label className="field">Предмет<input value={draft.subject} maxLength={200} onChange={event=>setDraft({...draft,subject:event.target.value})}/></label>
    <label className="field">Текст<textarea rows={7} maxLength={5000} value={draft.text} onChange={event=>setDraft({...draft,text:event.target.value})}/><small>{draft.text.length} / 5000</small></label>
    {editing&&<label className="check-row"><input type="checkbox" checked={draft.done} onChange={event=>setDraft({...draft,done:event.target.checked})}/>Выполнено</label>}
   </fieldset>
   <button className="primary-button" type="submit" disabled={busy||!draft.title.trim()}>{busy?'Сохраняем…':uncertain?'Повторить то же сохранение':'Сохранить запись'}</button>
  </form>:<>
   <div className="form-pair"><label className="field compact-field">Найти запись<input type="search" maxLength={100} value={query} onChange={event=>setQuery(event.target.value)} placeholder="Предмет, заголовок или текст"/></label><label className="field compact-field">Тип записей<select value={kind} onChange={event=>setKind(event.target.value as typeof kind)}><option value="all">Все записи</option><option value="note">Заметки</option><option value="homework">Домашние задания</option></select></label></div>
   {!loading&&items.length===0&&<div className="empty-state"><NotebookPen size={32}/><h3>{query||kind!=='all'?'Записей не найдено':'Пока чистый лист'}</h3><p>{query||kind!=='all'?'Измените запрос или тип записей. Поиск идёт по всем вашим записям.':'Добавьте запись здесь или откройте значок заметки у пары.'}</p><button className="secondary-button" onClick={()=>begin(blank,null)}>Создать заметку</button></div>}
   <div className="notes-list">{items.map(note=><article className={'note-item'+(note.done?' is-done':'')} key={note.id}>
    <div className="note-title"><button className="icon-button" aria-label={note.done?'Отметить невыполненным':'Отметить выполненным'} disabled={busy} onClick={()=>void toggle(note)}><span className="check-circle">{note.done&&<Check size={14}/>}</span></button><button className="note-open" disabled={busy} onClick={()=>edit(note)}><h3>{note.title}</h3><small>{note.kind==='homework'?'ДЗ':'Заметка'}{note.date?' · '+note.date:''}</small></button><button className="icon-button" aria-label={'Удалить '+note.title} disabled={busy} onClick={()=>setDeleting(note.id)}><Trash2 size={17}/></button></div>
    {note.subject&&<p className="muted">{note.subject}</p>}{note.lesson_status==='changed'&&<p className="warning-message">Занятие изменено или не найдено в последнем полученном шаблоне. Запись сохранена.</p>}{note.lesson_id&&note.lesson_status==='unknown'&&<p className="muted">Связь с занятием пока не подтверждена: нет актуального снимка исходного расписания.</p>}<p className="note-copy">{note.text}</p>
    {deleting===note.id&&<div className="confirmation-inline"><span>Удалить запись без возможности восстановления?</span><button className="danger-button" disabled={busy} onClick={()=>void remove(note)}>Удалить</button><button className="text-button" disabled={busy} onClick={()=>setDeleting(null)}>Отмена</button></div>}
   </article>)}</div>
   {loading&&<p role="status">Загружаем записи…</p>}
   {hasMore&&<button className="secondary-button" disabled={loading||busy} onClick={()=>void loadMore()}>Ещё записи</button>}
  </>}
 </section>;
}
