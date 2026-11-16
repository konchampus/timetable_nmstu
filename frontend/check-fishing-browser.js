async page => {
 const snap=()=>page.locator('body').ariaSnapshot();
 const before=await snap();
 if(!before.includes('button "fishing"'))throw new Error('Fishing selector absent');
 await page.getByRole('button',{name:'fishing',exact:true}).click();
 await snap();
 await page.getByRole('button',{name:'Начать демо ловли · без сервера',exact:true}).click();
 let state=await snap();
 if(!state.includes('Забросить удочку'))throw new Error('Cast control absent');
 await page.getByRole('button',{name:'Забросить удочку',exact:true}).click();
 await snap();
 await page.getByRole('button',{name:'Клюёт! Нажмите: подсечь',exact:true}).waitFor();
 state=await snap();if(!state.includes('Клюёт'))throw new Error('Not in bite state');
 await page.getByRole('button',{name:'Клюёт! Нажмите: подсечь',exact:true}).click();
 state=await snap();if(!state.includes('Натяжение'))throw new Error('Fight did not start');
 const reel=page.getByRole('button',{name:/Удерживать: тянуть рыбу|Тянем — следите за натяжением/});
 await reel.focus();await snap();
 let transitions=0;
 for(let i=0;i<55;i++){
  state=await snap();if(!state.includes('Натяжение'))break;
  await page.keyboard.down('Space');await snap();transitions++;
  await page.waitForFunction(()=>{const m=document.querySelector('[role=meter]');return !m||Number(m.getAttribute('aria-valuenow'))>=65;},{},{timeout:5000});
  state=await snap();await page.keyboard.up('Space');await snap();transitions++;
  if(!state.includes('Натяжение'))break;
  await page.waitForFunction(()=>{const m=document.querySelector('[role=meter]');return !m||Number(m.getAttribute('aria-valuenow'))<=35;},{},{timeout:5000});
 }
 const final=await snap();
 if(!final.includes('Рыба в садке'))throw new Error('No successful landing: '+final);
 const result=await page.getByRole('status',{name:'Параметры тестовой игры'}).innerText();
 await page.screenshot({path:'fishing-mobile-caught.png',scale:'css'});
 const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
 return {test:'real keyboard fishing control in isolated fixture',transitions,final,result,overflow};
}
