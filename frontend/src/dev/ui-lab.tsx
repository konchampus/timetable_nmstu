/// <reference types="vite/client" />
import {createRoot} from 'react-dom/client';
import {installMock,audit} from './ui-mock';
import './ui-lab.css';
const params=new URLSearchParams(location.search);
const root=document.getElementById('root')!;
const wait=(ms=180)=>new Promise(resolve=>setTimeout(resolve,ms));
if(import.meta.env.DEV){
 if(params.has('frame')){
  installMock();
  const banner=document.createElement('div');banner.className='ui-lab-banner';banner.textContent='Демо, без сервера/реальных очков';document.body.prepend(banner);
  await import('../styles.css');await import('../player-ui.css');
  const {default:App}=await import('../App');createRoot(root).render(<App/>);
  const measure=()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,section:document.querySelector('main[data-section]')?.getAttribute('data-section'),game:document.querySelector('.games')?.getAttribute('data-game'),theme:document.documentElement.dataset.theme,overflow:[...document.querySelectorAll<HTMLElement>('body *')].filter(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.right>innerWidth+1&&getComputedStyle(el).position!=='fixed'&&!!el.getClientRects().length;}).slice(0,15).map(el=>({tag:el.tagName,class:el.className,right:Math.round(el.getBoundingClientRect().right)})),errors:[...audit.errors],requestCount:audit.requests.length,blocked:audit.requests.filter(r=>!r.handled)});
  const click=(selector:string,text:string)=>{const button=[...document.querySelectorAll<HTMLElement>(selector)].find(el=>el.textContent?.trim()===text);if(!button)throw new Error('Не найден UI control '+text);button.click();};
  const sample=async(label:string,results:unknown[])=>{await wait(350);results.push({label,...measure()});};
  window.addEventListener('message',async event=>{
   if(event.origin!==location.origin||event.source!==parent||event.data?.type!=='ui-lab-suite')return;
   const results:unknown[]=[];try{
    await wait(500);await sample('Сегодня',results);
    click('nav button','Неделя');await sample('Неделя',results);
    click('nav button','Поиск');await sample('Поиск: избранное/история',results);
    const input=document.querySelector<HTMLInputElement>('.search-field input')!;const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!;setter.call(input,'Демо');input.dispatchEvent(new Event('input',{bubbles:true}));await wait(650);await sample('Поиск: результаты',results);
    click('nav button','Профиль');await sample('Профиль',results);
    click('button','Приватность и удаление данных');await sample('Профиль: приватность',results);
    click('button','Заметки и домашние задания');await sample('Заметки',results);
    document.querySelector<HTMLButtonElement>('.note-open')?.click();await sample('Заметки: редактор',results);
    click('button','Сохранить запись');await sample('Заметки: сохранено в памяти',results);
    click('nav button','Игры');await wait(700);await sample('Каталог 12 игр',results);
    for(const title of ['Слоты','Рыбалка','Кости','Дартс','Боулинг','Баскетбол','Футбол','Монетка','Рулетка','Блэкджек','Сапёр','Колесо']){
      const tile=[...document.querySelectorAll<HTMLButtonElement>('.games-tile')].find(el=>el.querySelector('strong')?.textContent===title);if(!tile)throw new Error('Нет плитки '+title);tile.click();await sample('Игра: '+title,results);if(params.get('active')==='1'&&title==='Блэкджек'){click('button','Остановиться');await sample('Блэкджек: завершён локально',results);}if(params.get('active')==='1'&&title==='Сапёр'){document.querySelector<HTMLButtonElement>('.games-cashout button')?.click();await sample('Сапёр: выплата локально',results);}click('.games-back','Все игры');await wait();
    }
    // Inspect the new location even when the main matrix uses saved active rounds.
    click('.games-tabs button','Играть');await wait();
    const fishingTile=[...document.querySelectorAll<HTMLButtonElement>('.games-tile')].find(el=>el.querySelector('strong')?.textContent==='Рыбалка')!;fishingTile.click();await wait(500);
    if(params.get('active')!=='1'){
      document.querySelector<HTMLButtonElement>('.destination-carp')!.click();await wait();
      const play=document.querySelector<HTMLButtonElement>('.location-music button');
      const audio=document.querySelector<HTMLAudioElement>('.location-music audio');
      if(!play?.disabled||audio?.getAttribute('src')||!audio?.paused)throw new Error('Плеер без фонограммы должен быть отключён');
      if(!document.querySelector('.fishing-boss')?.textContent?.includes('Старый Карп'))throw new Error('Нет босса Пруда Карпа');
      for(const button of document.querySelectorAll<HTMLElement>('.fishing-world button'))if(getComputedStyle(button).userSelect!=='none')throw new Error('Выделение текста кнопки рыбалки не отключено');
      await sample('Пруд Карпа: босс, плеер без файла, кнопки без выделения',results);
    }
    click('.games-back','Все игры');
    click('.games-tabs button','История');await sample('История и журнал',results);
    click('.games-tabs button','Рейтинг');await sample('Рейтинг',results);
   }catch(error){results.push({suiteError:String(error),...measure()});}
   parent.postMessage({type:'ui-lab-results',results},location.origin);
  });
  setInterval(()=>parent!==window&&parent.postMessage({type:'ui-lab-measure',...measure()},location.origin),2000);
 }else{
  root.innerHTML='<header class="ui-lab-toolbar"><strong>Демо, без сервера/реальных очков</strong><label>CSS viewport <select id="width"><option>1280</option><option>390</option><option>360</option></select></label><label>Тема <select id="theme"><option value="light">light</option><option value="dark">dark</option></select></label><label><input id="active" type="checkbox">Активные раунды</label><label><input id="error" type="checkbox">Ошибка расписания</label><button id="reload">Применить</button><button id="suite">Проверить переходы + 12 игр</button><button id="matrix">Матрица 1280/390/360 light/dark</button></header><iframe title="Реальный App: изолированное демо" id="app-frame"></iframe><details class="ui-lab-report"><summary>Измерения и ошибки</summary><pre id="report"></pre></details>';
  const frame=document.querySelector<HTMLIFrameElement>('#app-frame')!;const output=document.querySelector('#report')!;
  const select=(id:string)=>(document.getElementById(id) as HTMLSelectElement).value;
  const load=()=>{output.removeAttribute('data-complete');const url=new URL(location.href);url.searchParams.set('frame','1');url.searchParams.set('theme',select('theme'));if((document.getElementById('active') as HTMLInputElement).checked)url.searchParams.set('active','1');else url.searchParams.delete('active');if((document.getElementById('error') as HTMLInputElement).checked)url.searchParams.set('error','schedule');else url.searchParams.delete('error');frame.style.width=select('width')+'px';frame.src=url.href;};
  document.querySelector('#reload')!.addEventListener('click',load);
  document.querySelector('#suite')!.addEventListener('click',()=>{output.textContent='Проверяем реальные DOM переходы…';frame.contentWindow?.postMessage({type:'ui-lab-suite'},location.origin);});
  document.querySelector('#matrix')!.addEventListener('click',async()=>{
   const all:unknown[]=[];for(const active of [true,false])for(const width of ['1280','390','360'])for(const theme of ['light','dark']){
    (document.getElementById('width') as HTMLSelectElement).value=width;(document.getElementById('theme') as HTMLSelectElement).value=theme;(document.getElementById('active') as HTMLInputElement).checked=active;
    load();await new Promise<void>(resolve=>frame.addEventListener('load',()=>resolve(),{once:true}));await wait(900);
    const result=await new Promise<unknown>(resolve=>{const onResult=(event:MessageEvent)=>{if(event.origin===location.origin&&event.source===frame.contentWindow&&event.data?.type==='ui-lab-results'){window.removeEventListener('message',onResult);resolve(event.data);}};window.addEventListener('message',onResult);frame.contentWindow?.postMessage({type:'ui-lab-suite'},location.origin);});all.push({width,theme,active,result});
   }
   await fetch('/__ui-report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(all)});output.textContent=JSON.stringify(all,null,2);output.setAttribute('data-matrix-complete','true');
  });
  window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==frame.contentWindow)return;if(event.data?.type==='ui-lab-results'){output.textContent=JSON.stringify(event.data,null,2);output.setAttribute('data-complete','true');}else if(event.data?.type==='ui-lab-measure')document.body.dataset.overflow=String(event.data.scrollWidth>event.data.width);});
  if(['1280','390','360'].includes(params.get('width')??''))(document.getElementById('width') as HTMLSelectElement).value=params.get('width')!;
  if(params.get('theme')==='dark')(document.getElementById('theme') as HTMLSelectElement).value='dark';
  (document.getElementById('active') as HTMLInputElement).checked=params.get('active')==='1';
  (document.getElementById('error') as HTMLInputElement).checked=params.get('error')==='schedule';
  load();
 }
}else root.textContent='UI lab доступен только в Vite dev mode.';
