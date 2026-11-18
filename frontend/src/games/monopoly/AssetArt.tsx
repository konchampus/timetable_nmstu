import type { CSSProperties, ReactNode } from 'react';

type AssetArtProps = {
  kind: string;
  color?: string;
  className?: string;
};

const wash = <ellipse cx="60" cy="49" rx="49" ry="39" fill="currentColor" opacity=".075" stroke="none" />;
const ground = <path d="M17 83h86" stroke="currentColor" opacity=".22" strokeWidth="1.5" />;

function Scene({ kind }: { kind: string }): ReactNode {
  switch (kind.toLowerCase()) {
    case 'fish':
      return <>
        {wash}
        <path d="M17 74c10-5 19-5 28 0s18 5 27 0 18-5 29 0" stroke="#8dcbd1" strokeWidth="2" />
        <path d="M26 49c9-13 25-20 42-16 8 2 15 7 20 16-5 9-12 14-20 16-17 4-33-3-42-16Z" fill="#dff2ef" />
        <path d="M27 49 12 37v24l15-12Z" fill="#f6d8c4" />
        <path d="M54 34c4-7 9-10 16-10l-2 12M54 64c4 7 9 10 16 10l-2-12" fill="#f6d8c4" />
        <circle cx="77" cy="45" r="2.4" fill="currentColor" stroke="none" />
        <path d="M63 41c3 5 3 11 0 16m8-15c3 4 3 10 0 14m8-12c2 3 2 7 0 10" stroke="#72afb6" strokeWidth="1.5" />
        <path d="M89 49h6" strokeWidth="1.5" />
        <circle cx="25" cy="27" r="3" fill="#fff" stroke="#8dcbd1" />
        <circle cx="99" cy="34" r="2" fill="#fff" stroke="#8dcbd1" />
      </>;
    case 'clothing':
      return <>
        {wash}
        <path d="M40 27 51 22c2 6 5 9 9 9s7-3 9-9l11 5 13 14-10 9-7-7v32H44V43l-7 7-10-9 13-14Z" fill="#f3dfd3" />
        <path d="M51 22c2 6 5 9 9 9s7-3 9-9M60 32v42m-2-36 2 3 2-3" />
        <path d="M44 43 37 50m39-7 7 7M45 74h30" strokeWidth="1.5" />
        <path d="M24 83h72M51 16l9-6 9 6-9 6-9-6Z" fill="#e3eff8" />
        <path d="M60 22v5" />
        <path d="m92 24 2 4 4 2-4 2-2 4-2-4-4-2 4-2 2-4Z" fill="#fff1c8" stroke="#ddb85b" strokeWidth="1.5" />
      </>;
    case 'airport':
      return <>
        {wash}
        <path d="M15 81h90" stroke="#9bb5cf" strokeWidth="2" />
        <path d="M24 81h13m10 0h13m10 0h13m10 0h13" stroke="#fff" strokeWidth="2" />
        <path d="M25 39c4-8 11-12 20-10 7-10 24-10 31 1 12-2 19 4 20 12H25" fill="#fff" stroke="#a9bfd7" />
        <path d="M57 28 51 51l-20 8c-3 1-2 5 1 5l25-4 8 17 5-1-2-18 19-7c4-2 3-6-1-6l-20 4-9-22c-1-3-5-2-6 1Z" fill="#d8e9f7" />
        <path d="M17 70h22m42 0h22" stroke="#9bb5cf" strokeWidth="1.5" />
        <circle cx="27" cy="70" r="2" fill="#f1cb7c" stroke="none" />
      </>;
    case 'technology':
      return <>
        {wash}
        <rect x="29" y="22" width="62" height="44" rx="5" fill="#e5e5f7" />
        <path d="M35 57h50" stroke="#b7b6d9" strokeWidth="1.5" />
        <path d="m41 52 10-11 9 6 15-15" stroke="#6d8fc3" strokeWidth="3" />
        <circle cx="75" cy="32" r="3" fill="#f5d698" stroke="#d4a949" strokeWidth="1.5" />
        <path d="M55 66v8m10-8v8M47 76h26" />
        <rect x="76" y="52" width="19" height="29" rx="4" fill="#fff" />
        <path d="M82 58h7m-7 5h7m-7 5h4" stroke="#91a7c8" strokeWidth="1.5" />
        <circle cx="85.5" cy="76" r="1.4" fill="currentColor" stroke="none" />
        <path d="M22 83h76" stroke="currentColor" opacity=".22" strokeWidth="1.5" />
      </>;
    case 'food':
      return <>
        {wash}
        <path d="M25 40h70v40H25z" fill="#fff" />
        <path d="M21 40 28 26h64l7 14H21Z" fill="#fae3c8" />
        <path d="M28 27v13m16-13v13m16-13v13m16-13v13m16-13v13" stroke="#fff" strokeWidth="7" />
        <path d="M25 40h70m-70 0c2 7 11 7 13 0 2 7 11 7 13 0 2 7 11 7 13 0 2 7 11 7 13 0 2 7 11 7 13 0 2 7 11 7 15 0" strokeWidth="2" />
        <rect x="34" y="53" width="21" height="27" rx="2" fill="#e7f2e8" />
        <path d="M65 60h19v20H65z" fill="#fff0d2" />
        <path d="M65 66c1-6 5-9 9-9s8 3 9 9H65Zm1 1h17l-2 4H68l-2-4Zm2 5h13v4H68v-4Z" fill="#dca368" stroke="#b87b48" strokeWidth="1.5" />
        <path d="M42 56v20m-4-9h9" stroke="#96b99c" strokeWidth="1.5" />
        <path d="M21 82h78" stroke="currentColor" opacity=".22" strokeWidth="1.5" />
      </>;
    case 'media':
      return <>
        {wash}
        <path d="M30 35h60v43H30z" fill="#eee6f7" />
        <path d="M37 43h46v27H37z" fill="#fff" />
        <path d="m56 48 17 9-17 9V48Z" fill="#edc98b" stroke="#c39a53" />
        <path d="M36 29h48v7H36z" fill="#f7e0ce" />
        <path d="m36 29 8-9h48l-8 9m-28-9-8 9m24-9-8 9m24-9-8 9" />
        <path d="M46 78v7m28-7v7m-34 0h40" />
        <circle cx="94" cy="28" r="5" fill="#f7d98f" />
        <path d="M96 17v-4m10 15h4m-23-9-3-3" stroke="#d6ae53" strokeWidth="1.5" />
      </>;
    case 'energy':
      return <>
        {wash}
        <circle cx="87" cy="29" r="10" fill="#f9e7b2" stroke="#d9b858" />
        <path d="M87 12v-5m0 44v-5M70 29h-5m44 0h-5m-29-12-4-4m31 31-4-4m0-23 4-4M74 41l-4 4" stroke="#d9b858" strokeWidth="1.5" />
        <path d="m18 77 19-12 19 7 17-14 27 19v7H18z" fill="#dfeee3" />
        <path d="M41 61 45 31m0 3-13 7m13-7 12 6m-12-6-1-15-10 11m11-11 10 11" stroke="#769a80" />
        <circle cx="45" cy="34" r="3" fill="#fff" stroke="#769a80" />
        <path d="m67 66 23-8 8 14-23 8-8-14Z" fill="#dce9f6" />
        <path d="m74 64 8 13m1-16 8 13m-17-2 20-7" stroke="#8fa8c2" strokeWidth="1.3" />
        <path d="M17 83h88" stroke="currentColor" opacity=".22" strokeWidth="1.5" />
      </>;
    case 'luxury':
      return <>
        {wash}
        <path d="M60 20 88 38 76 72H44L32 38 60 20Z" fill="#e7e1f5" />
        <path d="m32 38 28 6 28-6M44 72l16-28 16 28M60 20v24" stroke="#9b8aba" />
        <path d="M35 77h50v6H35z" fill="#f5e5c4" />
        <path d="M42 83h36" strokeWidth="3" />
        <path d="m95 22 2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5Z" fill="#fff1c8" stroke="#d8b762" strokeWidth="1.5" />
        <path d="m23 34 1.5 3.5L28 39l-3.5 1.5L23 44l-1.5-3.5L18 39l3.5-1.5L23 34Z" fill="#fff1c8" stroke="#d8b762" strokeWidth="1.3" />
      </>;
    case 'start':
      return <>
        {wash}
        <path d="M23 79c0-25 16-44 37-44s37 19 37 44" stroke="#93b9a1" strokeWidth="8" />
        <path d="M23 79c0-25 16-44 37-44s37 19 37 44" stroke="#fff" strokeWidth="2" strokeDasharray="4 7" />
        <path d="M59 35V16m0 1h30L77 27l12 8H59" fill="#f6dfb4" />
        <path d="m67 72 8 7-8 7m8-7H48c-7 0-11-4-11-10" stroke="#fff" strokeWidth="2.5" />
        <circle cx="60" cy="35" r="4" fill="#fff" />
      </>;
    case 'chance':
      return <>
        {wash}
        <path d="M36 22h48a5 5 0 0 1 5 5v48a5 5 0 0 1-5 5H36a5 5 0 0 1-5-5V27a5 5 0 0 1 5-5Z" fill="#fff" />
        <path d="M37 30h46" stroke="#e9d8b5" strokeWidth="2" strokeDasharray="3 4" />
        <path d="m60 39 4 9 10 1-7 7 2 10-9-5-9 5 2-10-7-7 10-1 4-9Z" fill="#f8e3ab" stroke="#cba54e" />
        <path d="m94 25 2.5 5.5L102 33l-5.5 2.5L94 41l-2.5-5.5L86 33l5.5-2.5L94 25Z" fill="#fff1c8" stroke="#d8b762" strokeWidth="1.5" />
        <circle cx="25" cy="65" r="4" fill="#d9e9f6" stroke="#8eacc7" />
      </>;
    case 'chest':
      return <>
        {wash}
        <path d="M28 46h64v34H28z" fill="#e9b979" />
        <path d="M27 46c1-13 8-20 19-20h28c11 0 18 7 19 20H27Z" fill="#f0cf9d" />
        <path d="M28 46h64m-64 6h64m-55-26v20m46-20v20" />
        <path d="M55 52h10v14H55z" fill="#f8e7b5" />
        <path d="M60 52v14" stroke="#c49b50" strokeWidth="1.5" />
        <path d="M22 80h76" stroke="currentColor" opacity=".22" strokeWidth="1.5" />
        <ellipse cx="40" cy="77" rx="8" ry="3" fill="#f7df9e" stroke="#c89e4e" />
        <path d="M33 73v4m14-4v4m-11-7c0-3 8-3 8 0v3h-8v-3Z" fill="#f7df9e" stroke="#c89e4e" strokeWidth="1.5" />
        <path d="m89 20 2 4 4 2-4 2-2 4-2-4-4-2 4-2 2-4Z" fill="#fff1c8" stroke="#d8b762" strokeWidth="1.5" />
      </>;
    case 'jail':
      return <>
        {wash}
        <path d="M28 25h64v57H28z" fill="#e8e9ed" />
        <path d="M24 25h72v8H24z" fill="#d8dbe2" />
        <path d="M35 40h50v42H35z" fill="#f8f8f6" />
        <path d="M42 40v42m12-42v42m12-42v42m12-42v42" stroke="#8d97a5" strokeWidth="3" />
        <path d="M35 48h50M35 74h50" stroke="#b4bbc5" strokeWidth="1.5" />
        <circle cx="60" cy="60" r="5" fill="#f2d89c" stroke="#bd9853" />
        <path d="M58 60h4m-2-2v4" stroke="#8f7440" strokeWidth="1.5" />
        <path d="M23 83h74" stroke="currentColor" opacity=".22" strokeWidth="1.5" />
      </>;
    case 'tax':
      return <>
        {wash}
        <path d="M38 20h44l7 8v52H31V28l7-8Z" fill="#fff" />
        <path d="M38 20v9h-7m51-9v9h7" stroke="#cbd0d9" />
        <path d="M44 42h31m-31 8h22m-22 8h31" stroke="#bdc5cf" strokeWidth="2" />
        <circle cx="49" cy="70" r="4" fill="#f7dfc1" stroke="#d6a16e" />
        <circle cx="72" cy="70" r="4" fill="#f7dfc1" stroke="#d6a16e" />
        <path d="m72 66-23 8" stroke="#d6a16e" strokeWidth="2" />
        <path d="M97 32v29" stroke="#98b5cc" strokeWidth="2" />
        <path d="m91 55 6 7 6-7" stroke="#98b5cc" strokeWidth="2" />
      </>;
    case 'parking':
      return <>
        {wash}
        <path d="M26 23h54a8 8 0 0 1 8 8v38H26V23Z" fill="#e1edf7" />
        <path d="M88 43h7v25h-7" fill="#d3dce6" />
        <text x="53" y="57" textAnchor="middle" fontSize="32" fontWeight="700" fontFamily="Arial, sans-serif" fill="currentColor" stroke="none">P</text>
        <path d="M36 73h50" stroke="#8998a9" strokeWidth="3" />
        <path d="M34 73v5m53-5v5" />
        <path d="M42 63h31l7 7H36l6-7Z" fill="#f3d6ba" />
        <path d="M44 66h8m11 0h8" stroke="#fff" strokeWidth="2" />
        <circle cx="45" cy="71" r="3" fill="#6c7784" /><circle cx="70" cy="71" r="3" fill="#6c7784" />
        <path d="M22 83h76" stroke="currentColor" opacity=".22" strokeWidth="1.5" />
      </>;
    case 'water':
      return <>
        {wash}
        <path d="M25 53h70m-63 0v17m56-17v17" stroke="#7db8c2" strokeWidth="4" />
        <path d="M34 50V37h52v13M39 37v-7h42v7" fill="#dceff0" />
        <path d="M45 30c4-6 10-9 17-9s13 3 17 9" />
        <path d="M50 43c4-4 9-6 14-6s10 2 14 6" stroke="#8fc3c8" strokeWidth="1.5" />
        <path d="M60 47c-6-9-12-14-12-21a12 12 0 1 1 24 0c0 7-6 12-12 21Z" fill="#d1ebec" />
        <path d="M57 28c0-3 2-5 5-6" stroke="#fff" strokeWidth="2" />
        <path d="M29 72h10m42 0h10" stroke="#fff" strokeWidth="2" />
        <path d="M20 83c9-4 17-4 26 0s17 4 26 0 17-4 28 0" stroke="#7db8c2" strokeWidth="2" />
      </>;
    case 'hotel':
      return <>
        {wash}
        <path d="M30 79V29l30-10 30 10v50H30Z" fill="#f4e5d8" />
        <path d="M25 30 60 17l35 13" />
        <path d="M39 37h9v9h-9zm23 0h9v9h-9zm-23 19h9v9h-9zm23 0h9v9h-9z" fill="#d9e8f4" />
        <path d="M76 37h8v28h-8z" fill="#f7efdb" />
        <path d="M52 79V66h16v13" fill="#d8ad79" />
        <path d="M24 80h72" stroke="#a88a72" strokeWidth="2" />
        <path d="M48 30h24" stroke="#b99269" strokeWidth="2" />
        <path d="m60 25 1.5 3.5L65 30l-3.5 1.5L60 35l-1.5-3.5L55 30l3.5-1.5L60 25Z" fill="#fff" stroke="#d4b36c" strokeWidth="1" />
        <path d="M18 83h84" stroke="currentColor" opacity=".22" strokeWidth="1.5" />
      </>;
    case 'house':
      return <>
        {wash}
        <path d="m23 48 37-30 37 30v33H23V48Z" fill="#f4e5d6" />
        <path d="M18 49 60 15l42 34" stroke="#b97f66" strokeWidth="5" />
        <path d="M75 30V20h9v18" fill="#e8d5c9" />
        <path d="M33 52h17v14H33zm37 0h17v14H70z" fill="#dcecf3" />
        <path d="M41 52v14m-8-7h17m29-7v14m-9-7h17" stroke="#8daaba" strokeWidth="1.5" />
        <path d="M52 81V64h16v17" fill="#d7a779" />
        <circle cx="64" cy="73" r="1.5" fill="#fff" stroke="none" />
        <path d="M22 82h76" stroke="currentColor" opacity=".22" strokeWidth="1.5" />
        <path d="M24 74c5-5 9-5 14 0m44 0c5-5 9-5 14 0" stroke="#86ad88" strokeWidth="1.5" />
      </>;
    case 'token':
      return <>
        {wash}
        <ellipse cx="60" cy="81" rx="27" ry="7" fill="#d8dce5" />
        <path d="M43 75c2-9 8-14 17-14s15 5 17 14H43Z" fill="currentColor" />
        <path d="M52 58c0-5 3-9 8-11-6-3-9-8-9-14a9 9 0 1 1 18 0c0 6-3 11-9 14 5 2 8 6 8 11" fill="#f5dfad" />
        <circle cx="60" cy="31" r="10" fill="currentColor" />
        <path d="M50 58h20m-28 17h36" stroke="#bd9554" strokeWidth="1.5" />
        <path d="M20 84h80" stroke="currentColor" opacity=".22" strokeWidth="1.5" />
        <path d="m31 27 2 4 4 2-4 2-2 4-2-4-4-2 4-2 2-4Z" fill="#fff1c8" stroke="#d8b762" strokeWidth="1.3" />
      </>;
    case 'city':
    default:
      return <>
        {wash}
        <path d="M19 80V51h17v29m0-42h19v42m0-29h18v29m0-44h18v44m0-22h12v22H19" fill="#e5e5f2" />
        <path d="M41 49h5m-5 8h5m-5 8h5m18-9h6m-6 8h6m-6 8h6m12-29h6m-6 8h6m-6 8h6m-6 8h6" stroke="#a6a7c4" strokeWidth="2" />
        <path d="M44 38v-9m9 9V24m24 7V17m18 15V22" stroke="#8f90ad" strokeWidth="1.5" />
        <circle cx="84" cy="28" r="7" fill="#f8e8b8" stroke="#dfbe67" />
        <path d="M16 82c13-6 24-6 37 0s24 6 37 0 15-3 19 0" stroke="#88ad8e" strokeWidth="2" />
      </>;
  }
}

/** Original, decorative property illustrations for the Monopoly board and cards. */
export default function AssetArt({ kind, color, className }: AssetArtProps) {
  const style: CSSProperties = {
    display: 'block',
    ...(color ? { color } : {}),
  };

  return (
    <svg
      viewBox="0 0 120 100"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMid meet"
      role="presentation"
      aria-hidden="true"
      focusable="false"
      className={['monopoly-asset-art', className].filter(Boolean).join(' ')}
      style={style}
    >
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {ground}
        <Scene kind={kind} />
      </g>
    </svg>
  );
}
