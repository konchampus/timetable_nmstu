export function parseMonopolyLink(search=location.search,telegramStart?:string):{requested:boolean;code:string}{
 const q=new URLSearchParams(search);const tg=telegramStart??(window.Telegram?.WebApp as unknown as {initDataUnsafe?:{start_param?:string}}|undefined)?.initDataUnsafe?.start_param;
 const direct=q.get('monopoly');const candidates=[direct,tg,q.get('tgWebAppStartParam')];
 for(const raw of candidates){const code=(raw??'').replace(/^mono_/i,'').toLowerCase();if(/^[a-f0-9]{20}$/.test(code))return {requested:true,code};}
 return {requested:q.get('game')==='monopoly',code:''};
}
