import {memo,useCallback,useEffect,useId,useLayoutEffect,useRef,useState} from 'react';
import type {PointerEvent as ReactPointerEvent,KeyboardEvent} from 'react';
import {LocateFixed,Minus,Plus,Scan} from 'lucide-react';
import Board from './Board';
import Dice from './Dice';
import type {State,Tile} from './useMonopoly';
import {BOARD_SIDE,constrain,fitCamera,focusCell,zoomAt,gestureMoved,type Camera,type Viewport} from './board-camera';
import './play-board.css';

const StableBoard=memo(Board),StableDice=memo(Dice);

type Props={tiles:Tile[];state:State;selected:number|null;onSelect:(id:number)=>void;you:string;rolling?:boolean};
type Touch={x:number;y:number};
export default function PlayableBoard({tiles,state,selected,onSelect,you,rolling=false}:Props){
 const viewport=useRef<HTMLDivElement>(null),guide=useId();
 const [size,setSize]=useState<Viewport>({width:0,height:0});
 const [camera,setCamera]=useState<Camera>({x:0,y:0,scale:1});
 const [viewMode,setViewMode]=useState<'overview'|'follow'|'manual'>('overview');const modeRef=useRef(viewMode);
 const changeMode=(mode:'overview'|'follow'|'manual')=>{modeRef.current=mode;setViewMode(mode);};
 const sizeRef=useRef(size),cameraRef=useRef(camera),touches=useRef(new Map<number,Touch>());
 const gesture=useRef<{camera:Camera;center:Touch;distance:number}|null>(null),moved=useRef(false),suppressClick=useRef(false);
 const active=state.players.find(p=>p.id===state.turn&&!p.out)??state.players.find(p=>p.id===you&&!p.out);
 const activePosition=active?.pos??0;
 const apply=useCallback((next:Camera)=>{const bounded=constrain(next,sizeRef.current);cameraRef.current=bounded;setCamera(bounded);},[]);
 useLayoutEffect(()=>{
  const el=viewport.current;if(!el)return;
  const resize=()=>{const rect=el.getBoundingClientRect();const next={width:Math.round(rect.width),height:Math.round(rect.height)};if(next.width&&next.height){sizeRef.current=next;setSize(old=>old.width===next.width&&old.height===next.height?old:next);}};
  resize();const observer=new ResizeObserver(resize);observer.observe(el);return()=>observer.disconnect();
 },[]);
 // Only real movement/turn/viewport changes move the camera; polling and chat never do.
 useLayoutEffect(()=>{if(size.width&&size.height)apply(modeRef.current==='overview'?fitCamera(size):focusCell(activePosition,size));},[activePosition,active?.id,state.roll_sequence,size.width,size.height,apply]);
 const resetGesture=()=>{
  const points=[...touches.current.values()];if(!points.length){gesture.current=null;return;}
  const center=points.length===1?points[0]:{x:(points[0].x+points[1].x)/2,y:(points[0].y+points[1].y)/2};
  gesture.current={camera:{...cameraRef.current},center,distance:points.length>1?Math.hypot(points[0].x-points[1].x,points[0].y-points[1].y):0};
 };
 const local=(e:{clientX:number;clientY:number})=>{const rect=viewport.current!.getBoundingClientRect();return {x:e.clientX-rect.left,y:e.clientY-rect.top};};
 function down(e:ReactPointerEvent<HTMLDivElement>){
  if(e.pointerType==='mouse'&&e.button!==0)return;
  if(touches.current.size===0){moved.current=false;suppressClick.current=false;}
  touches.current.set(e.pointerId,local(e));resetGesture();
  // Capture the actual hit element so a stationary tap still reaches its property button.
  (e.target as Element).setPointerCapture?.(e.pointerId);
 }
 function move(e:ReactPointerEvent<HTMLDivElement>){
  if(!touches.current.has(e.pointerId)||!gesture.current)return;
  touches.current.set(e.pointerId,local(e));const points=[...touches.current.values()],start=gesture.current;
  const center=points.length===1?points[0]:{x:(points[0].x+points[1].x)/2,y:(points[0].y+points[1].y)/2};
  const dx=center.x-start.center.x,dy=center.y-start.center.y;
  const distance=points.length>1?Math.hypot(points[0].x-points[1].x,points[0].y-points[1].y):0;
  if(gestureMoved(dx,dy,start.distance,distance))moved.current=true;
  if(!moved.current)return;
  suppressClick.current=true;changeMode('manual');
  const zoomed=distance&&start.distance?zoomAt(start.camera,start.camera.scale*distance/start.distance,sizeRef.current,start.center):start.camera;
  apply({...zoomed,x:zoomed.x+dx,y:zoomed.y+dy});
 }
 function up(e:ReactPointerEvent<HTMLDivElement>){
  if(!touches.current.has(e.pointerId))return;
  touches.current.delete(e.pointerId);if(moved.current)suppressClick.current=true;resetGesture();
 }
 const zoom=(factor:number)=>{if(modeRef.current==='overview'&&factor>1){changeMode('follow');apply(focusCell(activePosition,sizeRef.current));}else{changeMode('manual');apply(zoomAt(cameraRef.current,cameraRef.current.scale*factor,sizeRef.current));}};
 useEffect(()=>{
  const el=viewport.current;if(!el)return;
  const wheel=(e:WheelEvent)=>{e.preventDefault();changeMode('manual');if(e.ctrlKey||e.metaKey){const r=el.getBoundingClientRect();apply(zoomAt(cameraRef.current,cameraRef.current.scale*Math.exp(-e.deltaY*.008),sizeRef.current,{x:e.clientX-r.left,y:e.clientY-r.top}));}else apply({...cameraRef.current,x:cameraRef.current.x-e.deltaX,y:cameraRef.current.y-e.deltaY});};
  el.addEventListener('wheel',wheel,{passive:false});return()=>el.removeEventListener('wheel',wheel);
 },[apply]);
 function keys(e:KeyboardEvent<HTMLDivElement>){
  suppressClick.current=false;
  if(e.target!==e.currentTarget)return;
  if(['+','=','-','0','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))e.preventDefault();
  if(e.key==='+'||e.key==='=')zoom(1.25);else if(e.key==='-')zoom(.8);else if(e.key==='0'){changeMode('overview');apply(fitCamera(sizeRef.current));}
  else if(e.key.startsWith('Arrow')){changeMode('manual');const delta={ArrowLeft:[48,0],ArrowRight:[-48,0],ArrowUp:[0,48],ArrowDown:[0,-48]}[e.key];if(delta)apply({...cameraRef.current,x:cameraRef.current.x+delta[0],y:cameraRef.current.y+delta[1]});}
 }
 const ownPosition=state.players.find(p=>p.id===you&&!p.out)?.pos??activePosition;
 return <section className="mono-playable" aria-label="Игровое поле с масштабом и перемещением">
  <div className="mono-map-controls">
   <button type="button" aria-pressed={viewMode==='overview'} onClick={()=>{changeMode('overview');apply(fitCamera(sizeRef.current));}}><Scan size={17}/>Всё поле</button>
   <button type="button" aria-pressed={viewMode==='follow'} onClick={()=>{changeMode('follow');apply(focusCell(ownPosition,sizeRef.current));}}><LocateFixed size={17}/>Моя фишка</button>
   <div className="mono-map-zoom"><button type="button" aria-label="Отдалить поле" onClick={()=>zoom(.8)}><Minus size={19}/></button><button type="button" aria-label="Приблизить поле" onClick={()=>zoom(1.25)}><Plus size={19}/></button></div>
  </div>
  <p id={guide} className="mono-map-guide">Перемещайте поле пальцем или мышью. Два пальца или кнопки + и − меняют масштаб. Стрелки — перемещение,0 — всё поле.</p>
  <div ref={viewport} className="mono-map-viewport" tabIndex={0} role="group" aria-label="Перемещаемое поле" aria-describedby={guide} onKeyDown={keys} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onLostPointerCapture={up} onClickCapture={e=>{if(suppressClick.current){e.preventDefault();e.stopPropagation();}}}>
   <div className="mono-map-world" style={{width:BOARD_SIDE,height:BOARD_SIDE,transform:'translate3d('+camera.x+'px,'+camera.y+'px,0) scale('+camera.scale+')',visibility:size.width?'visible':'hidden'}}>
    <StableBoard tiles={tiles} state={state} selected={selected} onSelect={onSelect} rolling={rolling} playable/>
   </div>
   {state.phase!=='lobby'&&<div className="mono-map-roll"><span>Последний бросок</span><StableDice values={state.dice} rollId={state.roll_sequence} rolling={rolling}/></div>}
   <span className="mono-map-hint" aria-hidden="true">{viewMode==='overview'?'Всё поле · «+» для деталей':'Тяните поле · '+Math.round(camera.scale*100)+'%'}</span>
  </div>
 </section>;
}
