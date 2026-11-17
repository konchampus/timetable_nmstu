import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { Fish, Layers3 } from 'lucide-react';
import { label, numbers, numberValue, stringValue, strings, type GameId, type GameInfo, type Round } from './types';

export interface LiveFishing {phase:string;castX:number;tension:number;progress:number}
interface Props { game: GameId; round: Round | null; info: GameInfo; lowPower: boolean; liveFishing?:LiveFishing; fishingPreview?:{location:string;skin:string}; }
const INK = 0x22334b, INDIGO = 0x3865b4, WHITE = 0xf4f6fa, GOLD = 0xc5a466;
const rouletteOrder = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26];
const redNumbers = new Set([1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]);
export default function GameScene({ game, round, info, lowPower, liveFishing, fishingPreview }: Props) {
  const live=useRef(liveFishing);live.current=liveFishing;
  const fishingLocation=round?.status==='active'||liveFishing?stringValue(round?.state??null,'location')||'shore':fishingPreview?.location??(stringValue(round?.state??null,'location')||'shore');
  const fishingSkin=round?.status==='active'||liveFishing?stringValue(round?.state??null,'skin')||'angler':fishingPreview?.skin??(stringValue(round?.state??null,'skin')||'angler');
  const host = useRef<HTMLDivElement>(null);
  const redraw = useRef<(()=>void)|null>(null);
  const [failed, setFailed] = useState(false);const [attempt,setAttempt]=useState(0);
  useEffect(() => {
    const container = host.current; if (!container) return;
    let disposed = false; let frame = 0; let visible = true; let started = false; let contextLost = false;
    let renderer: THREE.WebGLRenderer | undefined;
    let environment: THREE.WebGLRenderTarget | undefined;
    let observer: IntersectionObserver | undefined;
    let resizeObserver: ResizeObserver | undefined;
    const scene = new THREE.Scene();
    const textures: THREE.Texture[] = [];
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const result = round?.result ?? null;
    const settled = !!round && round.status !== 'active';
    const hasTransition = !!round && (settled || game === 'blackjack' || game === 'mines');
    const animated: ((time: number, progress: number) => void)[] = [];
    const material = (color: THREE.ColorRepresentation, roughness = 0.45, metalness = 0.08) => new THREE.MeshStandardMaterial({ color, roughness, metalness });
    function mesh(geometry: THREE.BufferGeometry, color: THREE.ColorRepresentation, parent: THREE.Object3D = scene, x = 0, y = 0, z = 0) {
      const object = new THREE.Mesh(geometry, material(color)); object.position.set(x,y,z); object.castShadow = !lowPower; object.receiveShadow = !lowPower; parent.add(object); return object;
    }
    function box(parent: THREE.Object3D, x: number, y: number, z: number, w: number, h: number, d: number, color: THREE.ColorRepresentation) { return mesh(new RoundedBoxGeometry(w,h,d,lowPower?1:2,Math.min(w,h,d)*0.12), color, parent,x,y,z); }
    function sphere(parent: THREE.Object3D, x: number, y: number, z: number, radius: number, color: THREE.ColorRepresentation) { return mesh(new THREE.SphereGeometry(radius,24,16),color,parent,x,y,z); }
    function text(text: string, foreground = '#343864', background = '#f3f3fc', width = 256, height = 256) {
      const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
      const ctx = canvas.getContext('2d'); if (!ctx) return material(WHITE);
      ctx.fillStyle = background; ctx.fillRect(0,0,width,height); ctx.fillStyle = foreground;
      ctx.font = '600 ' + Math.min(height * 0.49, width / Math.max(text.length * 0.62, 2)) + 'px system-ui';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text,width/2,height/2,width-12);
      const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; textures.push(texture);
      return new THREE.MeshStandardMaterial({map:texture,roughness:0.65});
    }
    function pips(value:number){
      const canvas=document.createElement('canvas');canvas.width=256;canvas.height=256;const ctx=canvas.getContext('2d');if(!ctx)return text(String(value));
      ctx.fillStyle='#f3f3fc';ctx.fillRect(0,0,256,256);ctx.fillStyle='#343864';
      const layout:Record<number,number[][]>={1:[[0,0]],2:[[-1,-1],[1,1]],3:[[-1,-1],[0,0],[1,1]],4:[[-1,-1],[-1,1],[1,-1],[1,1]],5:[[-1,-1],[-1,1],[0,0],[1,-1],[1,1]],6:[[-1,-1],[-1,0],[-1,1],[1,-1],[1,0],[1,1]]};
      for(const [x,y] of layout[value]??[]){ctx.beginPath();ctx.arc(128+x*65,128+y*65,19,0,Math.PI*2);ctx.fill();}
      const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;textures.push(texture);return new THREE.MeshStandardMaterial({map:texture,roughness:0.35});
    }
    function slotSymbol(symbol:string){
      const canvas=document.createElement('canvas');canvas.width=256;canvas.height=256;const ctx=canvas.getContext('2d');if(!ctx)return text(label(symbol));ctx.fillStyle='#f3f3fc';ctx.fillRect(0,0,256,256);
      const circle=(x:number,y:number,r:number,color:string)=>{ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();};
      if(symbol==='cherry'){ctx.strokeStyle='#65836b';ctx.lineWidth=9;ctx.beginPath();ctx.moveTo(83,160);ctx.quadraticCurveTo(94,81,155,53);ctx.quadraticCurveTo(134,108,171,164);ctx.stroke();circle(82,171,40,'#b85f77');circle(169,173,40,'#a94d67');circle(70,155,10,'#d991a3');}
      else if(symbol==='lemon'){ctx.fillStyle='#d7b76a';ctx.beginPath();ctx.ellipse(128,135,75,52,-0.5,0,Math.PI*2);ctx.fill();ctx.fillStyle='#8da47b';ctx.beginPath();ctx.ellipse(162,70,32,12,-0.7,0,Math.PI*2);ctx.fill();}
      else if(symbol==='bell'){ctx.fillStyle='#c8a16c';ctx.beginPath();ctx.moveTo(66,182);ctx.quadraticCurveTo(86,166,85,119);ctx.quadraticCurveTo(85,64,128,64);ctx.quadraticCurveTo(174,64,172,119);ctx.quadraticCurveTo(170,162,191,182);ctx.closePath();ctx.fill();circle(128,193,15,'#937345');circle(128,59,11,'#c8a16c');}
      else if(symbol==='diamond'){ctx.fillStyle='#798acd';ctx.beginPath();ctx.moveTo(50,105);ctx.lineTo(86,65);ctx.lineTo(170,65);ctx.lineTo(207,105);ctx.lineTo(128,205);ctx.closePath();ctx.fill();ctx.strokeStyle='#b6c4ee';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(50,105);ctx.lineTo(207,105);ctx.moveTo(86,65);ctx.lineTo(128,205);ctx.lineTo(170,65);ctx.stroke();}
      else{ctx.font='italic 800 178px system-ui';ctx.fillStyle='#a75970';ctx.textAlign='center';ctx.fillText('7',125,193);}
      const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;textures.push(texture);return new THREE.MeshStandardMaterial({map:texture,roughness:0.4});
    }
    function plate(parent: THREE.Object3D, value: string, x: number, y: number, z: number, w = 1, h = 1, foreground?: string, background?: string) {
      const p = new THREE.Mesh(new THREE.PlaneGeometry(w,h),text(value,foreground,background)); p.position.set(x,y,z); parent.add(p); return p;
    }
    function ring(parent: THREE.Object3D, radius: number, tube: number, color: number, x=0,y=0,z=0) { return mesh(new THREE.TorusGeometry(radius,tube,12,64),color,parent,x,y,z); }
    function fish(parent: THREE.Object3D, x: number, y: number, z: number, color: number) {
      const group = new THREE.Group(); group.position.set(x,y,z); parent.add(group);
      const body = sphere(group,0,0,0,0.23,color); body.scale.set(1.8,0.8,0.65);
      const tail = mesh(new THREE.ConeGeometry(0.21,0.35,3),color,group,-0.46,0,0); tail.rotation.z = -Math.PI/2;
      const finColor=new THREE.Color(color).multiplyScalar(0.76).getHex();const dorsal=sphere(group,-.03,.16,0,.115,finColor);dorsal.scale.set(1,.5,.16);const fin=sphere(group,.12,-.1,.07,.085,finColor);fin.scale.set(1,.3,.5);sphere(group,.23,.07,.12,.035,INK);const eyeShine=sphere(group,.244,.085,.15,.011,WHITE);eyeShine.scale.setScalar(.54);return group;
    }
    try {
      renderer = new THREE.WebGLRenderer({alpha:true,antialias:!lowPower,powerPreference:'low-power'});
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, lowPower ? 1 : 1.6)); renderer.setClearColor(0x000000,0);
      renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      renderer.shadowMap.enabled = !lowPower;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      if (!lowPower) {
        const studio = new RoomEnvironment();
        const pmrem = new THREE.PMREMGenerator(renderer);
        environment = pmrem.fromScene(studio, 0.04);
        scene.environment = environment.texture;
        scene.environmentIntensity = 0.65;
        studio.dispose(); pmrem.dispose();
      }
      renderer.domElement.setAttribute('aria-hidden','true'); container.appendChild(renderer.domElement); setFailed(false);
      const camera = new THREE.PerspectiveCamera(34,1,0.1,80); camera.position.set(0,3.4,8.9); camera.lookAt(0,0.4,0);
      scene.add(new THREE.HemisphereLight(0xe8edff,0x555669,3));
      const light = new THREE.DirectionalLight(0xfff3df,3.2); light.position.set(-3,7,5); scene.add(light);
      light.castShadow = !lowPower;
      light.shadow.mapSize.set(1024,1024);
      Object.assign(light.shadow.camera,{left:-7,right:7,top:7,bottom:-7,near:0.5,far:25});
      light.shadow.normalBias = 0.035; light.shadow.bias = -0.0003;
      const ground = new THREE.Mesh(new THREE.PlaneGeometry(80,80),new THREE.ShadowMaterial({color:0x243954,opacity:0.18}));
      ground.position.y = -0.91; ground.rotation.x = -Math.PI/2; ground.receiveShadow = !lowPower; scene.add(ground);
      const rim = new THREE.DirectionalLight(0xb4baff,2); rim.position.set(4,2,-4); scene.add(rim);
      const root = new THREE.Group(); scene.add(root);
      const pedestal = mesh(new THREE.CylinderGeometry(2.55,2.7,0.18,64),0xe0e3f4,root,0,-0.8,0);
      if (game === 'fishing') {
        camera.position.set(3.5,3.3,7.3); camera.lookAt(-.25,-.15,-1); pedestal.visible = false;light.intensity=2.1;rim.intensity=.7;
        const locationPalette:Record<string,{water:number;sky:number;leaves:number[]}>= {
          shore:{water:0x246c72,sky:0x91b8ae,leaves:[0x456d56,0x618365,0x365e50]},
          carp:{water:0x496c70,sky:0x9eb3b3,leaves:[0x54766a,0x6a8275,0x3d665d]},
          river:{water:0x225f66,sky:0x86a9a4,leaves:[0x547a3c,0x71834a,0x3d663d]},
          mountain:{water:0x287c91,sky:0x9db5ca,leaves:[0x315e56,0x416b64,0x2d4e51]},
          golden:{water:0x4f7970,sky:0xd9b77c,leaves:[0xc39a42,0xa77a32,0x8d8646]},
        };
        const palette=locationPalette[fishingLocation]??locationPalette.shore;
        scene.background=new THREE.Color(palette.sky);scene.fog=new THREE.Fog(palette.sky,fishingLocation==='carp'?7:13,fishingLocation==='carp'?18:27);
        if(fishingLocation==='golden'){light.color.set(0xffdc96);light.intensity=2.4;}
        const water = mesh(new THREE.PlaneGeometry(19,15,1,1),palette.water,root,0,-0.63,-1.65);water.rotation.x=-Math.PI/2;(water.material as THREE.MeshStandardMaterial).roughness=0.26;
        const shore=box(root,0,-0.34,-4.7,9,0.8,1,0xd3c5ad);shore.rotation.x=-0.12;
        const farBank=box(root,0,-0.14,-4.05,8,0.46,.7,0x82917a);
        for(let i=0;i<12;i++){const x=-5+i*.9;const rock=sphere(root,x,-.34,-3.78,.4+i%3*.08,i%2?0x7f8a80:0x9a9c89);rock.scale.set(1.3,.55,.8);}
        for(let i=0;i<9;i++){const x=-6+i*1.4,h=1.4+(i%3)*.4;mesh(new THREE.CylinderGeometry(.05,.09,h,8),0x665b43,root,x,h/2-.2,-5.3);if(fishingLocation==='mountain'){mesh(new THREE.ConeGeometry(.85,h,8),palette.leaves[i%3],root,x,h-.25,-5.3);}else{const crown=sphere(root,x,h-.2,-5.3,.85,palette.leaves[i%3]);crown.scale.set(1,1.3,.85);}}
        if(fishingLocation==='mountain')for(let i=0;i<5;i++){const x=-8+i*4;const peak=mesh(new THREE.ConeGeometry(3,5+i%2,5),0x8296a4,root,x,1.8,-10);peak.rotation.y=i*.4;mesh(new THREE.ConeGeometry(.85,1.5,5),0xe5edf0,root,x,4.2+(i%2)*.5,-10);}
        if(fishingLocation==='river')for(let i=0;i<18;i++){const x=-4+i*.45,z=-3.1+(i%3)*.18;const reed=mesh(new THREE.CylinderGeometry(.025,.04,.9+(i%4)*.12,5),0x72824c,root,x,.1,z);reed.rotation.z=(i%3-1)*.14;mesh(new THREE.CapsuleGeometry(.055,.2,3,5),0x87663f,root,x,.65+(i%4)*.06,z);}
        if(fishingLocation==='golden')for(let i=0;i<10;i++){const leaf=mesh(new THREE.CircleGeometry(.14,6),palette.leaves[i%3],root,-3+i*.6,-.6,-1.5+(i%3)*.7);leaf.rotation.x=-Math.PI/2;leaf.rotation.z=i*.6;}
        box(root,-2,-.65,2.1,6,.65,1.6,0x75866a);
        for(let i=0;i<6;i++){const x=-3.1+i*.25,base=i%2?.23:.05;const reed=mesh(new THREE.CylinderGeometry(.018,.032,.55+i%3*.13,5),0x658d68,root,x,-.37+(0.55+i%3*.13)/2,.8+i%3*.18);reed.rotation.z=(i-2.5)*.105;const seed=mesh(new THREE.CapsuleGeometry(.055,.14,3,5),0x987b52,root,x,-.04+base,.82+i%3*.18);seed.rotation.z=.12;}
        for(let i=0;i<7;i++)box(root,-1.6+i*.22,-.27,1.0,.20,.12,1.9,i%2?0x9a765a:0x82624f);box(root,-1.5,-.56,1.5,.12,.8,.12,0x65523c);box(root,-.3,-.56,1.5,.12,.8,.12,0x65523c);
        // Story landmarks are public scenery, never a preview of the hidden catch.
        if(fishingLocation==='shore'){
          const bucket=new THREE.Group();bucket.position.set(-2.5,-.14,1.6);root.add(bucket);
          mesh(new THREE.CylinderGeometry(.23,.19,.36,20,1,true),0x7b9299,bucket);
          const bucketWater=mesh(new THREE.CircleGeometry(.21,24),0x345e65,bucket,0,.1,0);bucketWater.rotation.x=-Math.PI/2;
          ring(bucket,.22,.018,0xaebfc1,0,.18,0).rotation.x=-Math.PI/2;
          const handle=ring(bucket,.22,.015,0xaebfc1,0,.21,0);handle.scale.y=1.25;
          const kettle=new THREE.Group();kettle.position.set(-3.1,-.18,1.65);root.add(kettle);
          const pot=sphere(kettle,0,.08,0,.18,0xb98555);pot.scale.y=.85;
          mesh(new THREE.CylinderGeometry(.11,.13,.04,16),0x8e623c,kettle,0,.22,0);
          sphere(kettle,0,.26,0,.035,INK);const spout=mesh(new THREE.CylinderGeometry(.025,.06,.2,12),0xb98555,kettle,.2,.11,0);spout.rotation.z=-.8;
          ring(kettle,.13,.023,0x805b3b,-.17,.12,0);
        }
        if(fishingLocation==='carp'){
          const sign=new THREE.Group();sign.position.set(-2.6,-.1,1.7);sign.rotation.y=.2;root.add(sign);
          box(sign,0,.28,0,.07,.6,.07,0x6e7566);box(sign,0,.62,.02,1.2,.36,.09,0x435c55);
          plate(sign,'ПРУД КАРПА',0,.62,.073,1.08,.28,'#e1e8d7','#435c55');
          for(const x of [-2.25,-.2]){mesh(new THREE.CylinderGeometry(.06,.08,.9,9),0x6b7768,root,x,-.3,.1);sphere(root,x,.18,.1,.075,0x879b7b);}
        }
        if(fishingLocation==='river'){
          for(let i=0;i<3;i++){
            const marker=new THREE.Group();marker.position.set(-2.8+i*2.3,-.1,-3.3);root.add(marker);
            const stone=sphere(marker,0,0,0,.43,0x7b8d83);stone.scale.set(1.3,.65,.8);
            box(marker,0,.5,0,.055,.8,.055,0x6f6046);
            box(marker,0,.82,.04,.85,.32,.07,0x344e48);
            plate(marker,['f(n)','f(n−1)','return'][i],0,.82,.082,.75,.25,'#e3eee1','#344e48');
          }
        }
        if(fishingLocation==='mountain'){
          const boat=new THREE.Group();boat.position.set(2.15,-.46,-2.5);boat.rotation.set(.08,-.5,-.13);root.add(boat);
          box(boat,0,0,0,1.5,.12,.5,0x64564a);
          for(const side of [-1,1]){box(boat,0,.15,side*.27,1.5,.3,.07,0x816b54);box(boat,side*.73,.12,0,.07,.24,.54,0x75634e);}
          box(boat,.15,.23,0,.23,.055,.5,0x958065);
          const brokenRib=box(boat,-.35,.25,.07,.07,.5,.06,0xa18c72);brokenRib.rotation.z=.75;
        }
        if(fishingLocation==='golden'){
          const terminal=new THREE.Group();terminal.position.set(-2.6,-.18,1.8);terminal.rotation.y=.25;root.add(terminal);
          box(terminal,0,0,0,.76,.14,.6,0x626760);
          box(terminal,0,.4,-.1,.68,.6,.18,0x6e756c);
          box(terminal,0,.41,.004,.57,.43,.04,0x162b2d);
          plate(terminal,'catch()',0,.43,.03,.52,.3,'#e7cd87','#162b2d');
          for(let row=0;row<3;row++)for(let col=0;col<6;col++)box(terminal,-.24+col*.095,.09,.08+row*.065,.07,.018,.045,0xa6a995);
          const cable=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-2.9,-.1,1.65),new THREE.Vector3(-3.25,-.28,1.85),new THREE.Vector3(-3.5,-.29,2.1)]),new THREE.LineBasicMaterial({color:0x394a43}));root.add(cable);
        }
        const rodGroup=new THREE.Group();root.add(rodGroup);const rod=mesh(new THREE.CylinderGeometry(.022,.045,2.5,9),0x845d40,rodGroup,-.7,1.04,.38);rod.rotation.z=-.52;mesh(new THREE.CylinderGeometry(.11,.095,.38,12),0x343b42,rodGroup,-1.13,.28,.45).rotation.x=Math.PI/2;const grip=mesh(new THREE.CylinderGeometry(.07,.09,.48,10),0xbd8b55,rodGroup,-1.15,.25,.38);grip.rotation.z=-.52;
        if(fishingSkin==='bear'){
          const bear=new THREE.Group();bear.position.set(-1.45,.08,1.25);bear.rotation.y=.4;root.add(bear);
          const fur=0x775039,muzzle=0xcda578;
          const body=sphere(bear,0,.27,0,.4,fur);body.scale.set(.88,1.15,.8);
          sphere(bear,0,.84,.04,.32,fur);const snout=sphere(bear,0,.77,.3,.18,muzzle);snout.scale.set(1.15,.75,.75);
          sphere(bear,0,.82,.43,.065,0x292b2a);
          for(const side of [-1,1]){sphere(bear,side*.24,1.08,.04,.12,fur);sphere(bear,side*.24,1.09,.1,.065,muzzle);sphere(bear,side*.13,.91,.31,.026,0x202525);const foot=sphere(bear,side*.24,-.07,.25,.18,fur);foot.scale.set(1,.7,1.3);const paw=sphere(bear,side*.29,.48,.27,.15,fur);paw.scale.set(.8,1.5,.8);}
          const vest=box(bear,0,.27,.28,.5,.47,.13,0x37675c);vest.rotation.x=-.08;
          animated.push((t)=>{const tension=live.current?.tension??0;bear.rotation.x=-tension/1800+Math.sin(t*1.2)*.008;});
        }
        const bobber = new THREE.Group(); bobber.position.set(.92,-.19,.48); root.add(bobber);sphere(bobber,0,0,0,.13,0xf3ede4);sphere(bobber,0,.09,0,.085,0xd77676);mesh(new THREE.CylinderGeometry(.008,.008,.13,5),INK,bobber,0,.19,0);
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-.08,2.12,.38),new THREE.Vector3(.92,-.1,.48)]),new THREE.LineBasicMaterial({color:0xe8eee6}));root.add(line);
        const ripple=ring(root,.3,.012,0xd9f0e9,.92,-.56,.48);ripple.rotation.x=-Math.PI/2;
        const rippleTwo=ring(root,.49,.009,0xcdeaf1,.92,-.555,.48);rippleTwo.rotation.x=-Math.PI/2;
        const swimmer=fish(root,1.42,-.76,-.45,0x365c61);const catchSpecies=stringValue(result,'species'),catchRarity=stringValue(result,'rarity');const fishColors:Record<string,number>={common:0x91a8a2,uncommon:0x849562,rare:0x5d98a1,epic:0x9c78ad,legendary:GOLD};const catchSilhouette:Record<string,number>={'Плотва':1,'Карась':1.12,'Карп':1.3,'Щука':1.52,'Сом':1.23,'Золотая рыба':.92,'Золотой карп':1.45};const catchingFish=settled&&round?.status==='caught'?fish(root,.92,.12,.48,fishColors[catchRarity]??0x91a8a2):null;swimmer.visible=!settled;swimmer.scale.setScalar(.7);if(catchingFish){catchingFish.visible=false;catchingFish.scale.x=catchSilhouette[catchSpecies]??1;}
        animated.push((t,p)=>{const local=live.current;const after=local?local.phase==='bite'||local.phase==='fighting':!!round?.available_at&&Date.now()>=Date.parse(round.available_at);
          if(local){bobber.position.x=.92+local.castX/600;bobber.position.z=.48-local.progress/1000;rodGroup.rotation.x=-local.tension/500;const vertices=line.geometry.attributes.position as THREE.BufferAttribute;const tip=rodGroup.localToWorld(new THREE.Vector3(-.08,2.12,.38));vertices.setXYZ(0,tip.x,tip.y,tip.z);vertices.setXYZ(1,bobber.position.x,bobber.position.y,bobber.position.z);vertices.needsUpdate=true;line.geometry.computeBoundingSphere();ripple.position.x=bobber.position.x;rippleTwo.position.x=bobber.position.x;}const bite=after?0.095*Math.max(0,Math.sin(t*8)):0;bobber.position.y=-.19+Math.sin(t*1.8)*.035-bite;if(catchingFish){catchingFish.visible=p>.08;catchingFish.position.y=.12+p*.62+Math.sin(t*4)*.025;catchingFish.rotation.z=Math.sin(t*5)*.045;}ripple.scale.setScalar(.8+(t%2.8)*.33);rippleTwo.scale.setScalar(.8+((t+1.35)%2.8)*.33);swimmer.position.x=1.3+Math.sin(t*.38)*.72;swimmer.rotation.y=Math.cos(t*.38)*.24;rodGroup.rotation.z=after?Math.sin(t*8)*.012:Math.sin(t*1.3)*.009;});
      } else if (game === 'slots') {
        box(root,0,0.65,0,3.9,2.65,0.8,INK); box(root,0,0.65,0.46,3.55,1.65,0.16,GOLD);
        box(root,0,-0.46,0.48,3.55,0.35,0.2,0x172436);
        for(const x of [-1.7,1.7])for(let i=0;i<6;i++)sphere(root,x,-0.12+i*0.33,0.57,0.035,GOLD);
        for(const x of [-0.55,0,0.55]){const button=mesh(new THREE.CylinderGeometry(0.14,0.16,0.07,24),x===0?GOLD:INDIGO,root,x,-0.43,0.65);button.rotation.x=Math.PI/2;}
        box(root,0,-0.7,0.1,4.1,0.16,1.2,INK);
        const symbols = strings(result?.symbols); const sequence = ['cherry','lemon','bell','diamond','seven'];
        for (let index=0;index<3;index++) {
          const reel = new THREE.Group(); reel.position.set((index-1)*1.1,0.65,0.65); root.add(reel);
          mesh(new THREE.CylinderGeometry(0.71,0.71,0.97,32),WHITE,reel).rotation.z=Math.PI/2;
          for (let side=0;side<5;side++) {
            const angle=side*Math.PI*2/5; const symbol = sequence[side];
            const tile=new THREE.Mesh(new THREE.PlaneGeometry(0.9,0.76),slotSymbol(symbol));tile.position.set(0,Math.sin(angle)*0.72,Math.cos(angle)*0.72);tile.rotation.x=-angle;reel.add(tile);
          }
          const target = Math.max(0,sequence.indexOf(symbols[index] ?? 'diamond')) * Math.PI*2/5;
          animated.push((_t,p)=>{reel.rotation.x=target+(settled?(1-p)*Math.PI*(8+index*2):0);});
        }
        plate(root,'МГТУ • PLAY',0,1.7,0.44,2.6,0.35,'#e9eaff','#343864');
        box(root,2.13,0.8,0,0.08,1.4,0.08,GOLD); sphere(root,2.13,1.52,0,0.16,0xc47780);
      } else if (game === 'dice') {
        const die = new THREE.Mesh(new THREE.BoxGeometry(1.55,1.55,1.55),[pips(1),pips(6),pips(2),pips(5),pips(3),pips(4)]); die.position.y=0.25; die.castShadow=!lowPower; root.add(die);
        mesh(new THREE.CylinderGeometry(2.05,2.1,0.08,64),0x344d65,root,0,-0.65,0);
        ring(root,2.08,0.06,GOLD,0,-0.59,0).rotation.x=-Math.PI/2;
        const face=numberValue(result,'value',3);const x=face===2?Math.PI/2:face===5?-Math.PI/2:0;const y=face===1?-Math.PI/2:face===6?Math.PI/2:face===4?Math.PI:0;
        animated.push((_t,p)=>{die.rotation.set(x+(settled?(1-p)*Math.PI*4:0),y+(settled?(1-p)*Math.PI*6:0),0);die.position.y=0.25+(settled?Math.sin(p*Math.PI)*1.1:0);});
        ring(root,1.65,0.025,INDIGO,0,-0.68,0).rotation.x=-Math.PI/2;
      } else if (game === 'coin') {
        const coin = new THREE.Mesh(new THREE.CylinderGeometry(1.13,1.13,0.15,64),[material(GOLD,0.24,0.7),text(settled?label(stringValue(result,'side')):'МГТУ','#65563e','#d6ad68'),text('PLAY','#65563e','#d6ad68')]); root.add(coin); coin.position.y=0.55;
        animated.push((_t,p)=>{coin.rotation.set(Math.PI/2+(1-p)*Math.PI*8,0,0.08);coin.position.y=0.55+Math.sin(p*Math.PI)*1.2;});
        const edge = ring(coin,1.04,0.018,0xf2ddb4,0,0.08,0); edge.rotation.x=Math.PI/2;
        const reverseEdge=ring(coin,1.04,0.018,0xf2ddb4,0,-0.08,0);reverseEdge.rotation.x=Math.PI/2;
        if(!lowPower)for(let i=0;i<64;i++){const a=i*Math.PI/32;const notch=box(coin,Math.cos(a)*1.13,0,Math.sin(a)*1.13,0.018,0.12,0.024,0x9b7b43);notch.rotation.y=-a;}
        coin.castShadow=!lowPower;
      } else if (game === 'roulette' || game === 'wheel') {
        const wheel = new THREE.Group(); wheel.rotation.x=-Math.PI/2; wheel.position.y=-0.15; root.add(wheel);
        const entries = game==='roulette'?rouletteOrder.map(String):Object.keys(info.probabilities);
        const segments = entries.length ? entries : ['?'];let cumulative=0;const total=game==='roulette'?segments.length:segments.reduce((sum,key)=>sum+(info.probabilities[key]??0),0);
        const arcs=segments.map(entry=>{const start=cumulative;const span=Math.PI*2*(game==='roulette'?1:info.probabilities[entry]??0)/Math.max(total,0.00001);cumulative+=span;return {entry,start,span};});
        mesh(new THREE.CylinderGeometry(2.22,2.3,0.22,80),0x574339,root,0,-0.25,0);
        ring(root,2.12,0.07,GOLD,0,-0.1,0).rotation.x=-Math.PI/2;
        ring(root,2.29,0.035,0x9c7b52,0,-0.22,0).rotation.x=-Math.PI/2;
        arcs.forEach(({entry,start:angle,span:step},index)=>{
          const color=game==='roulette'?(entry==='0'?0x668a77:redNumbers.has(Number(entry))?0xa96572:INK):[INDIGO,0x8690d4,INK,0xad93be,0xd3b079][index%5];
          const wedge = mesh(new THREE.CircleGeometry(1.96,Math.max(3,Math.floor(64/segments.length)),angle,step),color,wheel); wedge.position.z=0.01;
          const tile=plate(wheel,game==='wheel'?'×'+Number(entry):entry,Math.cos(angle+step/2)*1.62,Math.sin(angle+step/2)*1.62,0.025,game==='roulette'?0.26:0.7,game==='roulette'?0.22:0.33,'#ffffff',new THREE.Color(color).getStyle()); tile.rotation.z=angle+step/2-Math.PI/2;
        });
        const hub=mesh(new THREE.CylinderGeometry(0.32,0.4,0.38,40),GOLD,root,0,0.15,0);
        const pointer = mesh(new THREE.ConeGeometry(0.12,0.38,3),WHITE,root,0,0.1,2.12); pointer.rotation.x=-Math.PI/2;
        const target=game==='roulette'?String(numberValue(result,'number')):String(numberValue(result,'multiplier'));
        const targetArc=arcs.find(({entry})=>Number(entry)===Number(target))??arcs[0];
        animated.push((_t,p)=>{wheel.rotation.z=-targetArc.start-targetArc.span/2-Math.PI/2+(settled?(1-p)*Math.PI*10:0);hub.rotation.y=(1-p)*Math.PI*4;});
      } else if (game === 'blackjack') {
        pedestal.visible=false; mesh(new THREE.CylinderGeometry(2.8,2.8,0.25,64),0x285c50,root,0,-0.7,0);
        ring(root,2.72,0.14,0x243e38,0,-0.53,0).rotation.x=-Math.PI/2;
        ring(root,2.48,0.013,GOLD,0,-0.56,0).rotation.x=-Math.PI/2;
        for(let i=0;i<3;i++){const chip=mesh(new THREE.CylinderGeometry(0.18,0.18,0.055,32),i===2?GOLD:INDIGO,root,1.5,-0.52+i*0.06,0.15);ring(chip,0.145,0.008,WHITE,0,0.03,0).rotation.x=-Math.PI/2;}
        const player=strings(round?.state.player); const dealer=strings(round?.state.dealer);
        const card = (value: string,x: number,y: number,z: number) => {
          const group=new THREE.Group();group.position.set(x,y,z);root.add(group);group.rotation.x=-Math.PI/2;
          box(group,0,0,0,0.76,1.08,0.04,value==='?'?INDIGO:WHITE);
          plate(group,value==='?'?'•':value,0,0,0.025,0.65,0.94,/[HD]$/.test(value)?'#ad5d6e':'#343864',value==='?'?'#5964d9':'#f3f3fc');return group;
        };
        const cards=[...(dealer.length?dealer:['?','?']).map((value,i)=>card(value,(i-(Math.max(dealer.length,2)-1)/2)*0.85,-0.49,-0.8)),...(player.length?player:['?','?']).map((value,i)=>card(value,(i-(Math.max(player.length,2)-1)/2)*0.85,-0.42,0.9))];
        animated.push((_t,p)=>{cards.forEach((c,i)=>{
          const dealt=THREE.MathUtils.clamp(p*1.8-i*0.09,0,1);
          c.position.y=-0.45+Math.sin(dealt*Math.PI)*0.35;
          const row=i<Math.max(dealer.length,2)?-0.8:0.9;
          c.position.z=row+(1-dealt)*0.7;
          c.rotation.z=(1-dealt)*0.24;
        });});
      } else if (game === 'mines') {
        pedestal.visible=false;
        const cells=numbers(round?.state.cells), revealedMines=numbers(result?.mines);
        for(let i=0;i<25;i++) {
          const opened=cells.includes(i), mine=revealedMines.includes(i);
          const tile=box(root,(i%5-2)*0.66,-0.2,(Math.floor(i/5)-2)*0.66,0.57,opened||mine?0.08:0.28,0.57,mine?0xa96572:opened?0xb9c3e7:INDIGO);
          if(opened) {
            const gem=mesh(new THREE.OctahedronGeometry(0.16),0xe3e7ff,root,tile.position.x,0.03,tile.position.z);
            animated.push((t,p)=>{gem.rotation.y=t*0.5;gem.scale.setScalar(0.15+0.85*p);});
          }
          if(mine) {
            const bomb=new THREE.Group();bomb.position.set(tile.position.x,0.02,tile.position.z);root.add(bomb);
            sphere(bomb,0,0,0,0.15,INK);
            for(const angle of [0,Math.PI/2]){const spike=box(bomb,0,0,0,0.4,0.045,0.045,GOLD);spike.rotation.y=angle;}
            animated.push((_t,p)=>{bomb.position.y=0.02+Math.sin(p*Math.PI)*0.25;bomb.scale.setScalar(Math.max(0.1,p));});
          }
        }
      } else if (game === 'darts') {
        camera.position.set(0,1.4,8.5);camera.lookAt(0,0.5,0);
        const board = new THREE.Group();board.position.y=0.7;root.add(board);
        for(let i=5;i>=1;i--) {mesh(new THREE.CircleGeometry(i*0.34,64),i%2?INK:0xe5e0d8,board,0,0,(6-i)*0.005);}
        ring(board,1.02,0.07,0xa66a77,0,0,0.06);ring(board,0.59,0.045,0x6c9b89,0,0,0.07);
        mesh(new THREE.CircleGeometry(0.13,32),0xa66a77,board,0,0,0.09);
        for(let i=0;i<20;i++){const a=i*Math.PI/10;const edge=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(Math.cos(a)*0.15,Math.sin(a)*0.15,0.08),new THREE.Vector3(Math.cos(a)*1.7,Math.sin(a)*1.7,0.08)]),new THREE.LineBasicMaterial({color:0xc5c6d8}));board.add(edge);}
        const dart=new THREE.Group();root.add(dart);mesh(new THREE.CylinderGeometry(0.025,0.055,0.7,8),GOLD,dart).rotation.x=Math.PI/2;box(dart,0,0,0.32,0.2,0.15,0.12,INDIGO);
        const zones=[20,1,18,4,13,6,10,15,2,17,3,19,7,16,8,11,14,9,12,5];
        zones.forEach((value,index)=>{const a=Math.PI/2-index*Math.PI/10;plate(board,String(value),Math.cos(a)*1.52,Math.sin(a)*1.52,0.09,0.16,0.17,'#eeeeff','#343864');});
        const score=numberValue(result,'value');const radius=score>=50?0:score===25?0.19:score===0?1.95:0.8;const theta=Math.PI/2-Math.max(0,zones.indexOf(score))*Math.PI/10;
        animated.push((_t,p)=>{dart.visible=settled;dart.position.set(Math.cos(theta)*radius,0.7+Math.sin(theta)*radius,0.35+(1-p)*5);});
      } else if (game === 'bowling') {
        pedestal.visible=false;box(root,0,-0.6,0,2.6,0.2,5.8,0xc1ab90);
        for(const x of [-1.43,1.43]) box(root,x,-0.52,0,0.18,0.12,5.9,INK);
        const pins:THREE.Group[]=[];
        for(let row=0;row<4;row++) for(let col=0;col<=row;col++) {
          const pin=new THREE.Group();pin.position.set((col-row/2)*0.43,-0.28,-1+row*-0.35);root.add(pin);pins.push(pin);
          mesh(new THREE.CylinderGeometry(0.08,0.14,0.45,16),WHITE,pin,0,0,0);sphere(pin,0,0.31,0,0.095,WHITE);mesh(new THREE.CylinderGeometry(0.07,0.07,0.08,16),0xad6d7e,pin,0,0.2,0);
        }
        const ball=sphere(root,0,-0.1,2.1,0.35,INDIGO);for(let i=0;i<3;i++) sphere(ball,-0.1+i*0.08,0.21,0.24,0.035,INK);
        animated.push((_t,p)=>{ball.position.z=2.1-(settled?p*3.2:0);ball.rotation.x=-p*12;pins.forEach((pin,i)=>{pin.rotation.z=settled&&i<numberValue(result,'value')?Math.max(0,p-0.65)*4*(i%2?-1:1):0;});});
      } else if (game === 'basketball') {
        pedestal.visible=false;box(root,0,-0.66,0,4.3,0.14,4.9,0xbca083);
        box(root,0,1.05,-1.7,0.1,3.3,0.1,INK);box(root,0,2.2,-1.5,1.7,1.15,0.1,WHITE);
        const mark=ring(root,0.32,0.022,INDIGO,0,2.13,-1.42);mark.scale.set(1.35,1,1);
        const hoop=ring(root,0.46,0.045,0xc67e58,0,1.85,-0.95);hoop.rotation.x=Math.PI/2;
        for(let i=0;i<10;i++){const a=i*Math.PI/5;const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(Math.cos(a)*0.43,1.85,-0.95+Math.sin(a)*0.43),new THREE.Vector3(Math.cos(a)*0.25,1.2,-0.95+Math.sin(a)*0.25)]),new THREE.LineBasicMaterial({color:WHITE}));root.add(line);}
        const ball=sphere(root,0,0.05,1.8,0.32,0xc28a5b);ring(ball,0.325,0.012,INK);ring(ball,0.325,0.012,INK).rotation.y=Math.PI/2;
        animated.push((_t,p)=>{
          if(!settled){ball.position.set(0,0.05,1.8);return;}
          const shot=Math.min(1,p/0.72), landing=Math.max(0,(p-0.72)/0.28);
          const success=result?.success===true;
          const y=p<=0.72?0.05+1.8*shot+Math.sin(shot*Math.PI)*1.7:1.85-2.1*landing+Math.sin(landing*Math.PI)*0.18;
          ball.position.set(success?0:shot*1.25,y,p<=0.72?1.8-2.75*shot:-0.95-landing*0.55);
          ball.rotation.z=p*6;
        });
      } else if (game === 'football') {
        pedestal.visible=false;box(root,0,-0.66,0,4.8,0.13,5,0x77968a);
        for(const x of [-1.35,1.35])box(root,x,0.25,-1.7,0.09,1.8,0.09,WHITE);box(root,0,1.13,-1.7,2.8,0.09,0.09,WHITE);
        for(let i=0;i<10;i++)box(root,-1.35+i*0.3,0.25,-2,0.012,1.8,0.012,0xc3d4cb);for(let i=0;i<7;i++)box(root,0,-0.6+i*0.28,-2,2.7,0.012,0.012,0xc3d4cb);
        const ball=sphere(root,0,-0.3,1.7,0.27,WHITE);for(let i=0;i<6;i++){const patch=mesh(new THREE.CircleGeometry(0.085,5),INK,ball,Math.sin(i)*0.14,Math.cos(i)*0.14,0.232);patch.lookAt(patch.position.clone().multiplyScalar(2));}
        animated.push((_t,p)=>{ball.position.set(settled&&result?.success!==true?p*2:0,-0.3+Math.sin(p*Math.PI)*0.9,1.7-(settled?p*3.4:0));ball.rotation.x=-p*10;});
      }
      const resize=()=>{if(!renderer||disposed)return;const width=container.clientWidth,height=container.clientHeight;if(!width||!height||document.hidden||contextLost)return;renderer.setSize(width,height,false);camera.aspect=width/height;camera.zoom=game==='fishing'?1:Math.min(1,camera.aspect/1.12);camera.updateProjectionMatrix();renderer.render(scene,camera);};
      const startTime=performance.now();let last=0;
      const render=(now:number)=>{
        frame=0;if(disposed||contextLost||!renderer||document.hidden||!visible||!container.getClientRects().length)return;
        const staticFrame=motion.matches||lowPower;const elapsed=(now-startTime)/1000;
        if(now-last>=(lowPower?100:1000/30)||staticFrame){const progress=hasTransition?Math.min(1,elapsed/1.65):1;animated.forEach(fn=>fn(staticFrame?0:elapsed,staticFrame?1:1-Math.pow(1-progress,3)));renderer.render(scene,camera);last=now;}
        if(!staticFrame&&(game==='fishing'||(game==='mines'&&round!==null&&Array.isArray(round.state.cells)&&round.state.cells.length>0)||(hasTransition&&elapsed<1.8)))frame=requestAnimationFrame(render);
      };
      const resume=()=>{if(!frame&&!disposed&&!contextLost&&!document.hidden&&visible)frame=requestAnimationFrame(render);};
      redraw.current=resume;
      const visibility=()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else resume();};
      const lost=(event:Event)=>{event.preventDefault();contextLost=true;cancelAnimationFrame(frame);frame=0;setFailed(true);};
      renderer.domElement.addEventListener('webglcontextlost',lost);
      document.addEventListener('visibilitychange',visibility);motion.addEventListener('change',resume);
      resizeObserver=new ResizeObserver(resize);resizeObserver.observe(container);resize();
      observer=new IntersectionObserver(entries=>{visible=entries.some(entry=>entry.isIntersecting);if(visible)resume();else{cancelAnimationFrame(frame);frame=0;}},{rootMargin:'80px'});observer.observe(container);
      started=true;resume();
      return ()=>{disposed=true;redraw.current=null;cancelAnimationFrame(frame);observer?.disconnect();resizeObserver?.disconnect();document.removeEventListener('visibilitychange',visibility);motion.removeEventListener('change',resume);renderer?.domElement.removeEventListener('webglcontextlost',lost);dispose();};
    } catch { setFailed(true); }
    function dispose(){scene.traverse(object=>{if(object instanceof THREE.Mesh||object instanceof THREE.Line){object.geometry.dispose();const materials=Array.isArray(object.material)?object.material:[object.material];materials.forEach(item=>item.dispose());}});textures.forEach(texture=>texture.dispose());environment?.dispose();scene.traverse(object=>{if(object instanceof THREE.DirectionalLight)object.shadow.dispose();});renderer?.dispose();renderer?.forceContextLoss();renderer?.domElement.remove();}
    if(!started)dispose();return ()=>{disposed=true;cancelAnimationFrame(frame);observer?.disconnect();resizeObserver?.disconnect();};
  }, [game, round, info, lowPower, attempt, fishingLocation, fishingSkin]);
  useEffect(()=>{redraw.current?.();},[liveFishing?.castX,liveFishing?.phase,liveFishing?.tension,liveFishing?.progress]);
  return <div className="games-scene" ref={host} role="group" aria-label={'Трёхмерная сцена: '+info.title}>
    {failed && <div className="games-scene-fallback">{game==='fishing'?<Fish size={56}/>:<Layers3 size={56}/>}<strong>{info.title}</strong><span>Режим без 3D. Все действия доступны ниже.</span><button className="games-button games-button-soft" onClick={()=>setAttempt(value=>value+1)}>Повторить загрузку 3D</button></div>}
    <span className="games-scene-caption">{lowPower?'Экономичный режим · ':''}{liveFishing?'Живое управление · подсечка и натяжение':round?.status==='active'?'Сохранённая игра':round?'Показан прошлый раунд. Новый запуск создаст новый раунд.':'Это превью. Начните раунд в панели управления.'}</span>
  </div>;
}
