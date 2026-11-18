import type { ReactNode } from 'react';
import AssetArt from './AssetArt';

export type PropertyArtProps = {
  tile: { id: number; name: string; group: string; kind: string; art?: string };
  color?: string;
  className?: string;
};

// Authored here for this board. No logos, image downloads, SVG ids or font dependencies.
// Large, different primary contours survive the overview; secondary details enrich cards.
const paper = '#fffaf0';
const water = '#d5ecef';
const glass = '#dce9f4';
const gold = '#efd39a';
const blush = '#efd5c7';
const leaf = '#dce8d7';

function Fish({ x, y, size = 1 }: { x: number; y: number; size?: number }) {
  return <g transform={'translate(' + x + ' ' + y + ') scale(' + size + ')'}>
    <path d="M0 0c8-10 21-10 30 0-9 10-22 10-30 0Zm0 0-9-7V7l9-7Z" fill={water}/>
    <path d="M16-6c-3 4-3 8 0 12m-6-12 5-5 4 4"/>
    <circle cx="23" cy="-1" r="1.3" fill="currentColor" stroke="none"/>
  </g>;
}
function Windows({ x, y, cols = 3, rows = 2 }: { x: number; y: number; cols?: number; rows?: number }) {
  return <g fill={glass} strokeWidth="1.4">{Array.from({ length: cols * rows }, (_, n) =>
    <rect key={n} x={x + n % cols * 12} y={y + Math.floor(n / cols) * 13} width="7" height="7"/>)}</g>;
}
function Waves({ y = 82 }: { y?: number }) {
  return <path d={'M12 ' + y + 'q8-5 16 0t16 0t16 0t16 0t16 0t16 0'} strokeWidth="2"/>;
}

function Scene({ id }: { id: number }): ReactNode {
  switch (id) {
    // Рыбная лавка: striped fishmonger's counter, hanging catch, ice tray.
    case 1: return <>
      <path d="M21 42h78v38H21z" fill={paper}/><path d="m16 42 9-21h70l9 21Z" fill={blush}/>
      <path d="m35 22-3 19m20-19-1 19m19-19 1 19m17-19 3 19" stroke={paper} strokeWidth="7"/>
      <path d="M27 49v9m21-9v9m21-9v9"/><Fish x={33} y={56} size={.45}/><Fish x={65} y={56} size={.45}/>
      <path d="m27 67 5 15h56l5-15Z" fill={glass}/><path d="m35 72 6 4 5-5 6 6 6-6 7 6 6-5 9 3" stroke="white" strokeWidth="3"/>
      <Fish x={49} y={72} size={.55}/>
    </>;
    // Карповый пруд: organic shore, reeds, jetty and a single carp.
    case 3: return <>
      <path d="M17 55c-7-19 14-30 36-25 16-15 49-2 48 16 19 21-6 42-37 38-26 12-53-8-47-29Z" fill={water}/>
      <path d="M20 60V24m7 34V18m-13 7v13m20-16v14" stroke="#779978"/>
      <path d="M18 25v-7m9 2v-8m7 12v-7" stroke={gold} strokeWidth="5"/>
      <path d="m79 72 23-13v10L79 82Z" fill={blush}/><path d="m85 69 6 9m1-13 6 9M82 80v8m16-16v9"/>
      <Fish x={44} y={53} size={1.2}/><path d="M36 69q17 9 35 0M49 32h12" stroke="white"/>
    </>;
    // Ателье: oversized scissors and dressmaker's form, not another shirt.
    case 6: return <>
      <path d="M79 17v8m-10 1h20l-3 13 9 25H63l9-25-3-13Z" fill={blush}/><path d="M79 64v20m-11 0h23M71 39h15"/>
      <circle cx="28" cy="67" r="10" fill={paper}/><circle cx="48" cy="75" r="10" fill={paper}/>
      <path d="m34 60 24-37-8 43 5 1L25 28l14 38" fill={glass}/><circle cx="41" cy="57" r="2" fill={gold}/>
      <path d="M64 76h10v8H64z" fill={gold}/>
    </>;
    // Джинсовая фабрика: sawtooth roof and unmistakeable denim legs.
    case 8: return <>
      <path d="M17 80V44l18-13v13l18-13v13h17v36Z" fill={paper}/><path d="M20 41V21h10v14" fill={blush}/>
      <Windows x={23} y={54} cols={3} rows={2}/>
      <path d="M76 26h26l5 53H92l-4-30-3 30H70Z" fill={glass}/><path d="M76 35h26m-13-8v16m-11-6 5 8m17-8-5 8M73 73h11m10 0h11" strokeWidth="1.5"/>
      <path d="M21 14q9-8 17-2" opacity=".4"/>
    </>;
    // Дом моды: house-shaped showroom with a central couture gown.
    case 9: return <>
      <path d="M25 82V36l35-19 35 19v46Z" fill={paper}/><path d="M19 37 60 13l41 24M31 42h58"/>
      <path d="M52 41h16l-3 13 17 24H38l17-24Z" fill={blush}/><path d="m55 54 10 0m-5 1v23"/>
      <path d="M31 47v28m58-28v28M43 24h34" strokeWidth="1.5"/><circle cx="60" cy="31" r="3" fill={gold}/>
    </>;
    // Пекарня: a scored loaf and arched brick oven.
    case 11: return <>
      <path d="M47 81V43a27 27 0 0 1 54 0v38Z" fill={blush}/><path d="M56 77V46a18 18 0 0 1 36 0v31Z" fill={paper}/>
      <path d="M62 73q-2-13 8-18-2 8 5 11-1-12 7-16 13 16 3 23Z" fill={gold}/>
      <path d="M15 64c1-15 31-24 43-12 7 6 5 18-1 22l-29 9c-8 2-15-8-13-19Z" fill={gold}/>
      <path d="m26 57 8 10m2-15 8 11m3-14 7 10M56 35l-7-5m20-10v-8m20 13 6-5" strokeWidth="2"/>
    </>;
    // Кофейня: large cup, steam, saucer and terrace table.
    case 13: return <>
      <path d="M23 41h48v22a21 21 0 0 1-42 0Z" fill={paper}/><path d="M71 46h7c19 0 16 22-8 19" fill={blush}/>
      <ellipse cx="47" cy="41" rx="24" ry="6" fill={blush}/><path d="M25 77q22 12 48 0M37 29c-9-10 8-11 1-21m15 21c-9-10 8-11 1-21"/>
      <path d="M79 81h25m-13-1V59m-12 0h26"/><path d="M93 58V29m-17 0 17-14 17 14Z" fill={gold}/>
      <path d="m82 82-4 7m24-7 4 7"/>
    </>;
    // Ресторан: domed service cloche, cutlery and linen.
    case 14: return <>
      <path d="M19 71h84v13H19z" fill={paper}/><path d="M28 67a30 30 0 0 1 60 0Z" fill={glass}/>
      <path d="M23 68h70M58 37v-5m-4 0h8M34 58q3-10 13-14"/><path d="m25 84-4 7m76-7 4 7"/>
      <path d="M14 23v16q0 6 6 6v20m-6-36h12m-6-6v15m6-15v16M104 23q-12 17 0 22v20Z" fill={gold}/>
      <path d="m46 72 12 13 12-13" fill={blush}/>
    </>;
    // Радиостанция: tall braced broadcast mast with concentric waves.
    case 16: return <>
      <path d="m40 83 20-62 20 62Zm7-20h26M51 49h18M45 78l26-29m-22 0 26 29" fill={paper}/>
      <circle cx="60" cy="19" r="5" fill={gold}/><path d="M45 15q-10 9 0 18m30-18q10 9 0 18M35 8q-19 16 0 33m50-33q19 16 0 33"/>
      <path d="M82 65h23v18H82z" fill={blush}/><path d="m87 72 4 4 4-7 5 6" strokeWidth="1.5"/>
    </>;
    // Киностудия: twin-reel camera and freestanding studio light.
    case 18: return <>
      <circle cx="40" cy="30" r="13" fill={glass}/><circle cx="67" cy="29" r="14" fill={glass}/>
      <circle cx="40" cy="30" r="4" fill={paper}/><circle cx="67" cy="29" r="4" fill={paper}/>
      <rect x="25" y="43" width="56" height="28" rx="4" fill={blush}/><path d="m81 51 16-9v30L81 63Z" fill={gold}/>
      <path d="M53 71v7m-16 9 16-13 15 13M18 50V28m-8 0h17l-3 10H13Zm0 22-7 22m7-22 6 22"/>
      <path d="M35 53h24m-24 8h13" strokeWidth="1.5"/>
    </>;
    // Медиахолдинг: stepped HQ, newsroom screen and roof dish.
    case 19: return <>
      <path d="M22 83V45h19V22h40v61Z" fill={glass}/><path d="M81 48h18v35H81" fill={paper}/>
      <Windows x={47} y={34} cols={2} rows={3}/><path d="M25 55h15v20H25Z" fill={blush}/><path d="m29 62 7 4-7 4Z" fill={gold}/>
      <path d="M63 21v-8m0 2c8 1 15-3 18-10l-19-3c-3 4-2 9 1 13Zm8-5 7 10" fill={paper}/>
      <path d="M86 58h8m-8 9h8m-8 9h8" strokeWidth="1.5"/>
    </>;
    // Студия игр: gamepad silhouette, pixel sprite and developer monitor.
    case 21: return <>
      <rect x="28" y="15" width="64" height="38" rx="3" fill={glass}/><path d="M60 53v8m-13 0h26"/>
      <path d="M48 24h8v6h8v-6h8v15h-8v-4h-8v4h-8Z" fill={gold}/>
      <path d="M37 59h46c10 1 21 26 10 28-6 2-13-9-17-10H44c-4 1-11 12-17 10-11-2 0-27 10-28Z" fill={blush}/>
      <path d="M40 64v14m-7-7h14" strokeWidth="3"/><circle cx="78" cy="67" r="2.5" fill="currentColor"/><circle cx="85" cy="74" r="2.5" fill="currentColor"/>
    </>;
    // Облачный сервис: cloud crowns a connected three-rack server bank.
    case 23: return <>
      <path d="M34 43a12 12 0 0 1-2-24 20 20 0 0 1 37-6c17-6 30 7 24 19 13 4 7 16-3 16H36Z" fill={glass}/>
      <path d="M60 47v10m-28 0h56M32 57v6m56-6v6"/>
      {[21,49,77].map(x=><g key={x}><rect x={x} y="63" width="22" height="24" rx="2" fill={paper}/><path d={'M'+(x+5)+' 70h12m-12 6h12'} strokeWidth="1.5"/><circle cx={x+6} cy="82" r="1.5" fill={gold}/></g>)}
      <path d="m51 29 7 7 12-13" strokeWidth="3"/>
    </>;
    // Технопарк: low connected campus, central chip sculpture and trees.
    case 24: return <>
      <path d="M15 79V43h27v36m36 0V34h27v45" fill={glass}/><path d="M42 61h36v18H42Z" fill={paper}/>
      <Windows x={21} y={50} cols={2}/><Windows x={83} y={42} cols={2}/>
      <rect x="49" y="22" width="23" height="23" rx="3" fill={gold}/><path d="M54 16v6m12-6v6m-12 23v6m12-6v6m-23-23h6m-6 12h6m23-12h6m-6 12h6M55 28h11v11H55Z"/>
      <path d="M19 89h82M37 83v6m46-6v6"/><circle cx="37" cy="79" r="5" fill={leaf}/><circle cx="83" cy="79" r="5" fill={leaf}/>
    </>;
    // Рыбный порт: trawler, gantry crane and quay bollard.
    case 26: return <>
      <path d="m16 62 64 0-12 17H29Z" fill={blush}/><path d="M36 62V44h27v18M42 44V32h13v12" fill={paper}/>
      <path d="M25 60V25m0 5h33M87 75V17h17m-17 4L70 36h28M77 30v16m-3 0q0 8 6 4"/>
      <path d="M42 49h7v8h-7m12-8h6v8h-6" fill={glass}/><Waves/><path d="M92 85V69m-5 0h10" strokeWidth="4"/>
    </>;
    // Океанская ферма: elliptical floating pens with visible net cages.
    case 27: return <>
      <path d="M22 49v23q20 15 40 0V49m1 4v19q18 13 36 0V53" fill={water}/>
      <ellipse cx="42" cy="47" rx="23" ry="10" fill={paper}/><ellipse cx="81" cy="51" rx="21" ry="9" fill={paper}/>
      <path d="M25 49q17 10 34 0m7 3q15 8 30 0m-67 3v20m9-18v21m10-21v20m9-22v18m12-14v16m10-14v16m10-17v15" strokeWidth="1.2"/>
      <path d="M14 32h29V21H28v11m-8 0v10m17-10v6M98 40V22l10 5-10 6" fill={gold}/><Waves y={85}/>
      <Fish x={34} y={47} size={.55}/>
    </>;
    // Морской комбинат: processing conveyor, cold store and fish crates.
    case 29: return <>
      <path d="M15 79V35h53v44" fill={glass}/><path d="m11 35 31-18 31 18Z" fill={paper}/>
      <path d="M22 43h20v27H22Z" fill={paper}/><path d="M32 47v19m-7-15 14 11m0-11-14 11"/>
      <path d="M52 48h15v14h31v14H52Z" fill={blush}/><path d="M51 76h51m-48 0v8m43-8v8"/>
      <Fish x={73} y={61} size={.58}/><path d="M75 31h22v19H75z" fill={gold}/><path d="m75 35 22 11m0-11L75 46" strokeWidth="1.5"/>
    </>;
    // Текстильный завод: textile loom with warp threads and cloth roll.
    case 31: return <>
      <path d="M24 18h62v64H24Z" fill={paper}/><path d="M31 25h48v40H31Z" fill={blush}/>
      <path d="M37 25v41m8-41v41m8-41v41m8-41v41m8-41v41M31 42h48m-48 7h48m-48 7h48" strokeWidth="1.4"/>
      <path d="m18 52 35-18 33 7-34 19Z" fill={gold}/><path d="M32 65h48v18H32" fill={glass}/><ellipse cx="32" cy="74" rx="7" ry="9" fill={paper}/>
      <path d="M94 84V40m-7 0h14m-14 7h14m-14 6h14" strokeWidth="3"/>
    </>;
    // Модный квартал: three distinctly roofed boutiques on a pedestrian lane.
    case 32: return <>
      <path d="M12 76V37h27v39m1 0V26h36v50m1 0V40h30v36" fill={paper}/>
      <path d="m10 37 15-14 16 14m-3-11h40m-1 14 15-10 17 10" fill={blush}/>
      <path d="M17 47h17v21H17m30-31h22v14H47m35-1h19v20H82" fill={glass}/>
      <path d="M50 76V57h17v19m-37-24-5-4-5 4 5 4Zm57 3h10v12H87Z" fill={gold}/>
      <path d="M14 85h92M44 83l-7 8m39-8 7 8"/>
    </>;
    // Неделя моды: perspective runway, couture model and paired spotlights.
    case 34: return <>
      <path d="m46 48 28 0 27 38H19Z" fill={blush}/><path d="m55 53-6 27m16-27 6 27" stroke={paper} strokeWidth="3"/>
      <circle cx="60" cy="20" r="6" fill={gold}/><path d="M55 28h10l-2 13 10 17H47l10-17Zm1 30-2 12m10-12 2 12" fill={paper}/>
      <path d="m16 22 16 11-8 11L8 33Zm88 0-16 11 8 11 16-11ZM19 40v40m82-40v40" fill={glass}/>
      <path d="m31 37 13 15m45-15L76 52" opacity=".4"/>
    </>;
    // Ювелирный дом: faceted gem above an open velvet presentation box.
    case 37: return <>
      <path d="M27 55V29q33-18 66 0v26Z" fill={blush}/><path d="m21 58 39-11 39 11v25H21Z" fill={paper}/>
      <path d="m21 58 39 12 39-12M60 70v13"/><path d="m43 24 9-12h17l9 12-18 23Z" fill={glass}/>
      <path d="M43 24h35M52 12l8 35 9-35M43 24l17-7 18 7" strokeWidth="1.5"/>
      <ellipse cx="60" cy="60" rx="14" ry="5" fill={gold}/><path d="M32 63v11m56-11v11" strokeWidth="1.5"/>
    </>;
    // Люксовый бутик: structured handbag, silk scarf and tall display plinth.
    case 39: return <>
      <path d="M29 39h57l5 39H24Z" fill={blush}/><path d="M42 40V29a15 15 0 0 1 30 0v11" strokeWidth="4"/>
      <path d="M31 43v30m52-30v30M28 53h60" strokeWidth="1.5"/><rect x="53" y="50" width="10" height="8" rx="1" fill={gold}/>
      <path d="m83 29 15 7-7 39-9-15 3-14-12-9Z" fill={glass}/><path d="m86 35 8 8-7 15" strokeWidth="1.4"/>
      <path d="M20 79h78v8H20Z" fill={paper}/>
    </>;
    // Северный аэропорт: aircraft in plan view and runway threshold.
    case 5: return <>
      <path d="M39 87 49 13h22l10 74Z" fill={glass}/><path d="M60 18v8m0 49v8M45 83v-9m7 9v-9m16 9v-9m7 9v-9" stroke={paper} strokeWidth="3"/>
      <path d="M57 18q3-8 6 0l3 26 28 15v7l-29-8-1 16 10 8v5l-14-4-14 4v-5l10-8-1-16-29 8v-7l28-15Z" fill={paper}/>
      <path d="M57 29h6M16 32h16m-12-9v18"/>
    </>;
    // Восточный аэропорт: control tower overlooking a glazed terminal.
    case 15: return <>
      <path d="M27 78V37h16v41" fill={paper}/><path d="m19 26 3 15h26l3-15Z" fill={glass}/><path d="M17 26h36M35 25V14m-7 0h14m-14 18h14"/>
      <path d="M48 80V55l47-12 12 12v25Z" fill={glass}/><path d="m48 55 59 0M59 57v21m12-21v21m12-21v21m12-21v21"/>
      <path d="M13 86h95m-48-4 8 8m15-8 8 8" strokeWidth="1.5"/>
    </>;
    // Южный аэропорт: open arched hangar and nose-on propeller plane.
    case 25: return <>
      <path d="M16 81V45a44 30 0 0 1 88 0v36Z" fill={blush}/><path d="M25 80V46a35 23 0 0 1 70 0v34Z" fill={paper}/>
      <path d="M20 43h80m-70-9h60M34 27h52" strokeWidth="1.4"/>
      <path d="M27 64h66l-9 7H36Z" fill={glass}/><ellipse cx="60" cy="61" rx="10" ry="15" fill={gold}/>
      <path d="M60 42V28m-9 49-4 7m22-7 4 7M47 61h26m-13-13v26"/><circle cx="60" cy="61" r="3" fill={paper}/>
    </>;
    // Западный аэропорт: satellite concourse, jet bridges and radar dish.
    case 35: return <>
      <path d="M50 42h20v43H50Z" fill={paper}/><ellipse cx="60" cy="38" rx="29" ry="17" fill={glass}/>
      <path d="M34 40q26 17 52 0M39 30v13m13-18v23m15-23v23m14-18v13" strokeWidth="1.3"/>
      <path d="M37 49 20 64l7 7 22-17m34-5 17 15-7 7-22-17" fill={blush}/>
      <path d="M60 21V11m-13-4q13 17 26 0Zm13 1 10-6M55 65h10m-10 8h10" fill={gold}/>
    </>;
    // Электростанция: cooling towers and a transformer lightning cabinet.
    case 12: return <>
      <path d="M15 81c10-19 11-36 6-51h25c-5 15-4 32 6 51Zm39 0c8-16 9-28 5-41h22c-4 13-3 25 5 41Z" fill={paper}/>
      <path d="M21 30h25m13 10h22M28 22c-8-9 9-11 1-20m38 30c-8-9 9-11 1-20" opacity=".5"/>
      <rect x="82" y="54" width="24" height="29" rx="2" fill={gold}/><path d="m97 59-9 12h8l-5 8 11-13h-9Z" fill="currentColor" stroke="none"/>
      <path d="M22 72h24m15 1h19" strokeWidth="1.4"/>
    </>;
    // Водоканал: elevated reservoir, pipe valve and settling basin.
    case 28: return <>
      <path d="M23 37h30l-4 17H27Z" fill={glass}/><ellipse cx="38" cy="35" rx="17" ry="8" fill={water}/>
      <path d="m29 54-7 29m25-29 7 29m-28-9h25m-26-9h24M38 27V15m-5 0h10"/>
      <path d="M55 83V65h25" strokeWidth="5"/><circle cx="69" cy="59" r="7" fill={paper}/><path d="M69 52v14m-7-7h14"/>
      <path d="M77 66h29v16H77Z" fill={glass}/><ellipse cx="91.5" cy="66" rx="14.5" ry="6" fill={water}/><path d="M82 66h19m-10-3v6" strokeWidth="1.4"/>
    </>;
    default: return null;
  }
}

/** Decorative art: labels and interaction belong to the parent cell/card. */
export default function PropertyArt({ tile, color, className }: PropertyArtProps) {
  const scene = Scene({ id: tile.id });
  if (!scene) {
    const kind = tile.art ?? (({ 0: 'start', 10: 'jail', 20: 'parking', 30: 'jail' } as Record<number, string>)[tile.id] ?? tile.kind);
    return <AssetArt kind={kind} color={color} className={className}/>;
  }
  return <svg viewBox="0 0 120 100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet"
    role="presentation" aria-hidden="true" focusable="false"
    className={['monopoly-asset-art', 'monopoly-property-art', className].filter(Boolean).join(' ')}
    style={{ display: 'block', ...(color ? { color } : {}) }}>
    <ellipse cx="60" cy="87" rx="46" ry="5" fill="currentColor" opacity=".09"/>
    <g fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">{scene}</g>
  </svg>;
}
