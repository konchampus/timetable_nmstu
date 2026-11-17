import {useEffect,useRef,useState} from 'react';
import {Music2,Pause,Play,Volume2} from 'lucide-react';
import './location-music.css';

interface Props {active:boolean;soundEnabled:boolean;src?:string|null}
export default function LocationMusic({active,soundEnabled,src}:Props){
  const audio=useRef<HTMLAudioElement>(null),generation=useRef(0);
  const allowed=useRef(false);
  const [playing,setPlaying]=useState(false),[failure,setFailure]=useState('');
  const [volume,setVolume]=useState(()=>{try{const value=localStorage.getItem('companion:location-music-volume');return value!==null&&Number.isFinite(Number(value))?Math.max(0,Math.min(1,Number(value))):.2;}catch{return .2;}});
  // Backslashes and control characters can turn an apparently relative URL into
  // a cross-origin request in browser URL parsing. Only local site files qualify.
  const source=src?.startsWith('/')&&!src.startsWith('//')&&!/[\\\x00-\x20]/.test(src)&&new URL(src,location.origin).origin===location.origin?src:null;
  allowed.current=!!source&&active&&soundEnabled&&!document.hidden;
  const pause=()=>{generation.current++;audio.current?.pause();setPlaying(false);};
  useEffect(()=>{if(!active||!soundEnabled)pause();},[active,soundEnabled]);
  useEffect(()=>{setFailure('');pause();},[source]);
  useEffect(()=>{
    const visibility=()=>{if(document.hidden)pause();};
    document.addEventListener('visibilitychange',visibility);
    return()=>{generation.current++;audio.current?.pause();document.removeEventListener('visibilitychange',visibility);};
  },[]);
  useEffect(()=>{if(audio.current)audio.current.volume=volume;try{localStorage.setItem('companion:location-music-volume',String(volume));}catch{/* Browser storage is optional. */}},[volume]);
  const toggle=async()=>{
    const element=audio.current;if(!element||!allowed.current)return;
    if(!element.paused){pause();return;}
    const attempt=++generation.current;setFailure('');
    try{await element.play();if(attempt!==generation.current||!allowed.current)element.pause();}
    catch(error){if(attempt===generation.current&&(!(error instanceof DOMException)||error.name!=='AbortError')){setFailure('Не удалось включить трек. Проверьте аудиофайл и попробуйте ещё раз.');setPlaying(false);}}
  };
  const unavailable=!source||!active||!soundEnabled;
  const hint=!src?'Трек не подключён: фонограмма пока не добавлена.':!source?'Нужен локальный путь к аудиофайлу на этом сайте.':!soundEnabled?'Включите звук в настройках игры, затем нажмите воспроизведение.':!active?'Плеер на паузе, пока локация закрыта.':'Музыка включается только по нажатию. При сворачивании ставится на паузу.';
  return <section className="location-music" aria-label="Музыка Пруда Карпа">
    <div className="location-music-track"><Music2 size={21}/><div><strong>Пыяла <span>АИГЕЛ</span></strong><small>Альбом «Пыяла» · Пруд Карпа</small></div></div>
    <div className="location-music-controls"><button type="button" aria-label={playing?'Приостановить музыку':'Включить музыку'} aria-pressed={playing} disabled={unavailable} onClick={()=>void toggle()}>{playing?<Pause size={18}/>:<Play size={18}/>}<span>{playing?'Пауза':'Включить'}</span></button><label><Volume2 size={17}/><span className="sr-only">Громкость музыки</span><input aria-label="Громкость музыки" type="range" min="0" max="1" step="0.05" value={volume} disabled={!source} onChange={event=>setVolume(Number(event.target.value))}/><output>{Math.round(volume*100)}%</output></label></div>
    <p role="status">{failure||hint}</p>
    <audio ref={audio} src={source??undefined} preload="none" loop onPlay={()=>{if(!allowed.current)audio.current?.pause();else setPlaying(true);}} onPause={()=>setPlaying(false)} onError={()=>{if(source){setFailure('Аудиофайл недоступен или формат не поддерживается.');setPlaying(false);}}}/>
  </section>;
}
