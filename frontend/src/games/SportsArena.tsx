import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import {Crosshair,RotateCcw,Wind} from 'lucide-react';
import {readChallenge,replay,trajectory,type Shot,type Sport} from './arcade';
import type {Round} from './types';
import './sports-arena.css';

const names:Record<Sport,string>={darts:'Бросок в мишень',bowling:'Один точный бросок',basketball:'Попади в кольцо',football:'Удар по воротам'};
interface Props {game:Sport;round:Round;disabled:boolean;verification?:'server'|'fixture';lowPower?:boolean;onFinish:(shot:Shot)=>Promise<void>}
export default function SportsArena({game,round,disabled,onFinish,verification='server',lowPower=false}:Props){
 const challenge=readChallenge(round.state);
 const saved=round.state.shot as Partial<Shot>|undefined;
 const [aim,setAim]=useState({aim_x:typeof saved?.aim_x==='number'?saved.aim_x:0,aim_y:typeof saved?.aim_y==='number'?saved.aim_y:0,power:typeof saved?.power==='number'?saved.power:650});
 const [phase,setPhase]=useState<'aim'|'flight'|'done'>(round.status==='active'?'aim':'done'),[failure,setFailure]=useState(false),[prediction,setPrediction]=useState<Record<string,number|boolean>|null>(null);
 const timer=useRef<number|undefined>(undefined),proof=useRef<Shot|null>(null);
 const host=useRef<HTMLDivElement>(null),model=useRef({aim,phase,flight:0}),started=useRef(performance.now()),finishRef=useRef(onFinish);finishRef.current=onFinish;model.current.aim=aim;model.current.phase=phase;
 const terminal=round.status!=='active';
 useEffect(()=>()=>{if(timer.current!==undefined)clearTimeout(timer.current);},[]);
 useEffect(()=>{
  const element=host.current;if(!element||!challenge)return;
  let renderer:THREE.WebGLRenderer|undefined,frame=0,observer:ResizeObserver|undefined,cleanVisibility:(()=>void)|undefined;
  const scene=new THREE.Scene(),geometries:THREE.BufferGeometry[]=[],materials:THREE.Material[]=[];
  const geometry=<T extends THREE.BufferGeometry>(value:T)=>{geometries.push(value);return value;};
  const material=(color:number)=>{const m=new THREE.MeshStandardMaterial({color,roughness:.6});materials.push(m);return m;};
  const box=(x:number,y:number,z:number,w:number,h:number,d:number,color:number)=>{const mesh=new THREE.Mesh(geometry(new THREE.BoxGeometry(w,h,d)),material(color));mesh.position.set(x,y,z);mesh.receiveShadow=!lowPower;mesh.castShadow=!lowPower&&Math.min(w,h,d)>12;scene.add(mesh);return mesh;};
  const sphere=(radius:number,color:number)=>{const mesh=new THREE.Mesh(geometry(new THREE.SphereGeometry(radius,20,14)),material(color));scene.add(mesh);return mesh;};
  const hoop=(radius:number,color:number)=>{const mesh=new THREE.Mesh(geometry(new THREE.TorusGeometry(radius,10,8,48)),material(color));scene.add(mesh);return mesh;};
  try{
   renderer=new THREE.WebGLRenderer({antialias:!lowPower,alpha:false,powerPreference:'low-power'});renderer.setPixelRatio(Math.min(devicePixelRatio,lowPower?1:1.5));renderer.setClearColor(game==='football'?0x153d35:0x182b3e);element.appendChild(renderer.domElement);
   const camera=new THREE.PerspectiveCamera(game==='darts'?43:48,1,10,12000);camera.position.set(challenge.target_x,game==='bowling'?420:600,game==='darts'?1600:1400);camera.lookAt(challenge.target_x,game==='bowling'?-30:300,-1100);
   scene.fog=new THREE.Fog(game==='football'?0x153d35:0x182b3e,3800,8500);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.1;
   scene.add(new THREE.HemisphereLight(0xd3eaf3,0x293226,2.2));const key=new THREE.DirectionalLight(0xffe6c7,3);key.position.set(-1500,2500,500);scene.add(key);
   renderer.shadowMap.enabled=!lowPower;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
   key.castShadow=!lowPower;key.shadow.mapSize.set(1024,1024);Object.assign(key.shadow.camera,{left:-2400,right:2400,top:2400,bottom:-2400,near:100,far:7000});key.shadow.normalBias=3;
   const fill=new THREE.DirectionalLight(0x9ac4ff,1.2);fill.position.set(1800,1000,-1800);scene.add(fill);
   for(const x of [-1550,1550]){box(x,850,-1200,25,35,2200,0xe0e8f3);box(x,820,-1200,60,18,2200,0x637f94);}
   box(0,-140,-700,3300,40,4300,game==='football'?0x2c7655:game==='bowling'?0xa78055:0x5f5849);
   if(game==='football'){for(let i=0;i<12;i++)box(0,-118,-2250+i*350,3200,2,175,i%2?0x2a6f50:0x337e59);box(0,-114,-900,1300,4,7,0xd6dfce);box(-650,-114,-1400,7,4,1000,0xd6dfce);box(650,-114,-1400,7,4,1000,0xd6dfce);}else{for(let i=0;i<32;i++)box(-1600+i*100,-118,-700,98,2,4200,[0xb38b5d,0xbf976a,0xac8157,0xc49b69][i%4]);}
   if(game==='basketball'){const arc=hoop(700,0xe7dfc9);arc.rotation.x=-Math.PI/2;arc.position.set(0,-112,-1100);box(-600,-111,-1200,8,3,900,0xe7dfc9);box(600,-111,-1200,8,3,900,0xe7dfc9);box(0,-111,-750,1200,3,8,0xe7dfc9);}
   box(-1800,250,-900,180,900,4200,0x223344);box(1800,250,-900,180,900,4200,0x223344);box(0,550,-2600,3600,1400,100,0x223344);
   if(game==='football'||game==='basketball'){for(let row=0;row<4;row++)for(let col=0;col<18;col++)box(-1650+col*190,180+row*150,-2520-row*80,140,60,100,(row+col)%3?0x476c76:0xc4a779);}else{for(let i=0;i<8;i++)box(-1500+i*430,650,-2500,250,50,20,game==='bowling'?0xd8ae64:0x658285);}
   const tx=challenge.target_x,ty=challenge.target_y+300,tz=-1100;
   const pins:{group:THREE.Group;x:number;depth:number}[]=[];
   if(game==='darts'){
    box(tx,ty,tz-40,1200,1200,55,0x304956);
    for(const [r,c] of [[540,0xe4e6dc],[400,0x29493c],[270,0xd3d0b3],[150,0xac5242],[70,0xe5ba62]]){const disc=new THREE.Mesh(geometry(new THREE.CircleGeometry(r,64)),material(c));disc.position.set(tx,ty,tz+(540-r)/100);disc.receiveShadow=!lowPower;scene.add(disc);}
    for(const radius of [540,400,270,150,70]){const wire=new THREE.Mesh(geometry(new THREE.TorusGeometry(radius,2,6,64)),material(0xb5c2c7));wire.position.set(tx,ty,tz+8);scene.add(wire);}
    for(let i=0;i<20;i++){const angle=i*Math.PI/10;const wire=box(tx+Math.cos(angle)*305,ty+Math.sin(angle)*305,tz+9,470,2,2,0xa8b9b7);wire.rotation.z=angle;}
   }else if(game==='basketball'){
    box(tx,ty+120,tz-65,650,430,35,0xdce7e0);box(tx,ty+120,tz-40,250,180,10,0x263c44);
    const rim=hoop(110,0xf2a14d);rim.position.set(tx,ty,tz);rim.rotation.x=-Math.PI/2;
    for(let i=0;i<12;i++){const a=i*Math.PI/6;box(tx+Math.cos(a)*90,ty-90,tz+Math.sin(a)*90,5,180,5,0xdbe9e4);}
    box(tx,-5,tz-90,40,400,40,0x839496);
   }else if(game==='football'){
    box(tx-270,ty,tz,20,380,20,0xf0ece0);box(tx+270,ty,tz,20,380,20,0xf0ece0);box(tx,ty+190,tz,560,20,20,0xf0ece0);
    for(let i=0;i<12;i++)box(tx-270+i*49,ty,tz-70,3,380,3,0xa2c1b1);for(let i=0;i<8;i++)box(tx,ty-190+i*54,tz-70,540,3,3,0xa2c1b1);
   }else{
    const positions=[[0,0],[-65,65],[65,65],[-130,130],[0,130],[130,130],[-195,195],[-65,195],[65,195],[195,195]];
    const profile=[[0,0],[25,0],[32,25],[30,55],[18,80],[11,105],[19,125],[18,145],[0,153]].map(([x,y])=>new THREE.Vector2(x,y));
    positions.forEach(([x,z])=>{const group=new THREE.Group();group.position.set(tx+x,-110,tz+z);scene.add(group);const pin=new THREE.Mesh(geometry(new THREE.LatheGeometry(profile,20)),material(0xf5efe0));group.add(pin);const stripe=new THREE.Mesh(geometry(new THREE.CylinderGeometry(13,13,12,16)),material(0xc65643));stripe.position.y=106;group.add(stripe);pins.push({group,x,depth:z});});
    box(-560,-100,-600,35,40,3200,0x394b58);box(560,-100,-600,35,40,3200,0x394b58);
   }
   const ball=sphere(game==='darts'?18:game==='bowling'?60:48,game==='basketball'?0xd58b41:game==='bowling'?0x3863a6:0xece4ce);ball.castShadow=!lowPower;
   if(game==='bowling'){(ball.material as THREE.MeshStandardMaterial).roughness=.18;for(let i=0;i<3;i++){const hole=sphere(6,0x13243e);scene.remove(hole);hole.position.set(-14+i*13,34,44);ball.add(hole);}}
   if(game==='darts'){ball.scale.set(.45,.45,2.8);const flight=box(0,0,0,65,2,40,0x3975bc);scene.remove(flight);flight.position.z=42;ball.add(flight);const second=box(0,0,0,2,65,40,0x3975bc);scene.remove(second);second.position.z=42;ball.add(second);}
   if(game==='basketball'){for(let i=0;i<3;i++){const seam=hoop(48.5,0x442d20);seam.geometry.dispose();geometries.pop();seam.geometry=geometry(new THREE.TorusGeometry(48.5,1.6,5,48));scene.remove(seam);ball.add(seam);seam.rotation.set(i===0?Math.PI/2:0,i===1?Math.PI/2:0,0);}}
   if(game==='football'){for(let i=0;i<7;i++){const patch=new THREE.Mesh(geometry(new THREE.CircleGeometry(11,5)),material(0x26382f));const a=i*Math.PI*2/7;patch.position.set(Math.sin(a)*35,Math.cos(a)*35,31);patch.lookAt(patch.position.clone().multiplyScalar(3));ball.add(patch);}}
   const sight=hoop(32,0xf8d777);sight.position.set(tx,ty,tz+60);
   const dots=Array.from({length:12},()=>sphere(3,0xe1c779));
   let lastRender=0,lastSignature='';
   const resize=()=>{if(!renderer)return;renderer.setSize(element.clientWidth,element.clientHeight,false);camera.aspect=element.clientWidth/Math.max(1,element.clientHeight);camera.updateProjectionMatrix();lastSignature='';};observer=new ResizeObserver(resize);observer.observe(element);resize();
   const reduced=matchMedia('(prefers-reduced-motion: reduce)');
   const lost=()=>{cancelAnimationFrame(frame);frame=0;setFailure(true);};renderer.domElement.addEventListener('webglcontextlost',lost);
   const render=(time:number)=>{
    frame=0;if(document.hidden||!element.getClientRects().length)return;
    const state=model.current;
    if(time-lastRender<(lowPower?100:33)){frame=requestAnimationFrame(render);return;}
    const signature=JSON.stringify([state.aim,state.phase,element.clientWidth,element.clientHeight]);
    if((state.phase!=='flight'||reduced.matches)&&signature===lastSignature){frame=requestAnimationFrame(render);return;}
    lastSignature=signature;lastRender=time;
    const points=trajectory(challenge,{...state.aim,ticks:120});
    const t=state.phase==='flight'?(reduced.matches?60:Math.min(60,Math.floor((time-state.flight)/20))):state.phase==='done'?60:0;const point=points[t];
    const depth=(v:{z:number;y:number})=>game==='bowling'?700-(1800-points[60].y+challenge.target_y)*v.z/60:700-v.z*30;
    ball.position.set(point.x,game==='bowling'?-50:point.y+300,depth(point));ball.rotation.x=-t*.2;ball.rotation.z=t*.13;
    pins.forEach(pin=>{const dx=points[60].x-challenge.target_x-pin.x,dy=points[60].y-challenge.target_y-pin.depth;const hit=dx*dx+dy*dy<=(160+Math.trunc(state.aim.power/10))**2;const fall=state.phase==='aim'?0:Math.max(0,(t-51)/9);pin.group.rotation.x=hit?fall*1.35:0;pin.group.rotation.z=hit?fall*(pin.x<0?-.35:.35):0;});
    sight.position.set(points[60].x,game==='bowling'?-50:points[60].y+300,game==='bowling'?depth(points[60]):tz+30);sight.rotation.x=game==='bowling'?-Math.PI/2:0;sight.visible=state.phase==='aim';
    dots.forEach((dot,i)=>{const p=points[(i+1)*5];dot.visible=state.phase==='aim';dot.position.set(p.x,game==='bowling'?-50:p.y+300,depth(p));});
    if(!document.hidden&&element.getClientRects().length)renderer?.render(scene,camera);
    frame=requestAnimationFrame(render);
   };
   const resume=()=>{if(!frame&&!document.hidden)frame=requestAnimationFrame(render);};
   document.addEventListener('visibilitychange',resume);
   const visibleObserver=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting))resume();});visibleObserver.observe(element);
   const release=()=>{document.removeEventListener('visibilitychange',resume);renderer?.domElement.removeEventListener('webglcontextlost',lost);visibleObserver.disconnect();};
   cleanVisibility=release;frame=requestAnimationFrame(render);
  }catch{setFailure(true);}
  return()=>{cancelAnimationFrame(frame);cleanVisibility?.();observer?.disconnect();geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());scene.traverse(object=>{if(object instanceof THREE.DirectionalLight)object.shadow.dispose();});renderer?.dispose();renderer?.domElement.remove();};
 },[game,round.id,lowPower]);
 if(!challenge)return <p role="alert">Нужен раунд с локальной механикой. Вернитесь и начните новый.</p>;
 const shoot=()=>{
  if(phase!=='aim'||model.current.phase!=='aim'||disabled||terminal)return;
  const shot={...aim,ticks:Math.min(18000,Math.max(120,Math.floor((performance.now()-started.current)*.06)))};
  model.current.phase='flight';setPhase('flight');model.current.flight=performance.now();
  proof.current=shot;
  timer.current=window.setTimeout(()=>{setPrediction(replay(game,challenge,shot));setPhase('done');void finishRef.current(shot);},Math.max(1220,2050-(performance.now()-started.current)));
 };
 const inputLocked=phase!=='aim'||disabled||terminal;
 const aimPreview=replay(game,challenge,{...aim,ticks:120});
 const aimHint=typeof aimPreview.success==='boolean'?(aimPreview.success?'Траектория проходит через цель':'Маркер вне цели: измените прицел или силу'):'Прогноз: '+String(aimPreview.value)+(game==='bowling'?' из 10 кеглей':' очков мишени');
 return <section className="sports-arena" aria-label={names[game]}>
  <div className="sports-viewport" ref={host} onPointerDown={event=>{if(inputLocked)return;const rect=event.currentTarget.getBoundingClientRect();event.currentTarget.setPointerCapture(event.pointerId);setAim(a=>({...a,aim_x:Math.round(((event.clientX-rect.left)/rect.width-.5)*2000),aim_y:Math.round((.5-(event.clientY-rect.top)/rect.height)*1600)}));}} onPointerMove={event=>{if(inputLocked||!event.currentTarget.hasPointerCapture(event.pointerId))return;const r=event.currentTarget.getBoundingClientRect();setAim(a=>({...a,aim_x:Math.max(-1000,Math.min(1000,Math.round(((event.clientX-r.left)/r.width-.5)*2000))),aim_y:Math.max(-1000,Math.min(1000,Math.round((.5-(event.clientY-r.top)/r.height)*1600)))}));}}>
   {failure&&<div className="sports-fallback"><Crosshair size={52}/><p>3D недоступно. Прицел и сила работают через управление ниже.</p></div>}
  </div>
  <div className="sports-hud"><h3>{names[game]}</h3><span><Wind size={18}/>{challenge.wind<0?'←':'→'} {Math.abs(challenge.wind)}<small>боковой снос</small></span></div>
  <div className="sports-instruction" role="status">{terminal?(verification==='fixture'?'Тест завершён локально — без сервера':'Результат сохранён сервером'):phase==='flight'?(game==='darts'?'Дротик в полёте':game==='bowling'?'Шар на дорожке':'Мяч в полёте'):phase==='done'?'Бросок завершён · подтверждаем результат':game==='bowling'?'Цельтесь между кеглями. Сила влияет на сбитые кегли.':'Ведите прицел по сцене. Учтите силу и боковой снос.'}</div>
  {phase==='aim'&&!terminal&&<div className="sports-aim-feedback" role="status"><strong>{aimHint}</strong><span>Это расчёт при текущих настройках, не начисленная выплата. Один бросок на раунд.</span></div>}
  {prediction&&<p className="sports-local-result" role="status">Локальный результат: {typeof prediction.success==='boolean'?(prediction.success?'Попадание':'Промах'):String(prediction.value)+(game==='bowling'?' кеглей':' очков')}. {terminal?(verification==='fixture'?'Только тестовый расчёт.':'Подтверждён сервером.'):'Баланс изменится после проверки.'}</p>}
  {phase==='done'&&!terminal&&<button className="sports-reset" disabled={disabled} onClick={()=>{if(proof.current)void finishRef.current(proof.current);}}>Повторить подтверждение того же броска</button>}
  <div className="sports-controls"><fieldset disabled={inputLocked}><legend className="sr-only">Управление броском</legend>
   <label>Направление<input aria-label="Направление броска" type="range" min="-1000" max="1000" value={aim.aim_x} onChange={e=>setAim(a=>({...a,aim_x:Number(e.target.value)}))}/><small>Влево или вправо от центра</small></label>
   <label>{game==='bowling'?'Глубина удара':'Высота прицела'}<input aria-label="Высота прицела" type="range" min="-1000" max="1000" value={aim.aim_y} onChange={e=>setAim(a=>({...a,aim_y:Number(e.target.value)}))}/><small>{game==='bowling'?'Дальше или ближе по дорожке':'Ниже или выше цели'}</small></label>
   <label>Сила <b>{Math.round(aim.power/10)}%</b><input aria-label="Сила броска" type="range" min="100" max="1000" value={aim.power} onChange={e=>setAim(a=>({...a,power:Number(e.target.value)}))}/><small>Меняет дальность и точку попадания</small></label>
  </fieldset><button className="sports-shoot" disabled={inputLocked} onClick={shoot}>{phase==='flight'?'В полёте…':phase==='done'||terminal?'Бросок выполнен':game==='football'?'Ударить по мячу':game==='bowling'?'Катить шар':game==='darts'?'Бросить дротик':'Бросить мяч'}</button>{phase==='aim'&&<button className="sports-reset" disabled={inputLocked} onClick={()=>setAim({aim_x:0,aim_y:0,power:650})}><RotateCcw size={17}/>Сбросить прицел</button>}</div>
 </section>;
}
