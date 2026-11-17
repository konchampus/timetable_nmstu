// 20 Hz integer model; mirrored in backend/app/games/fishing_play.py.
export const tickRate=20,maxFishingTicks=600;
export interface FishingChallenge{gameplay_version:1;bite_tick:number;shoal_x:number;surge:number;rod_level:number;boss_tier?:number}
export interface FishingProof{cast_x:number;cast_tick:number;hook_tick:number|null;end_tick:number;events:{tick:number;held:boolean}[]}
export interface FishingState{tension:number;progress:number;slack:number;status:'fighting'|'caught'|'lost';reason:string}
export const initialFishing=():FishingState=>({tension:45,progress:0,slack:0,status:'fighting',reason:''});
export const biteTick=(c:FishingChallenge,x:number)=>c.bite_tick+Math.floor(Math.abs(x-c.shoal_x)/100);
export function fishingStep(state:FishingState,c:FishingChallenge,tick:number,held:boolean):FishingState{
 if(state.status!=='fighting')return state;
 const tier=c.boss_tier??0;
 const pull=[2,4,1,3][Math.floor((tick+c.surge)/16)%4]+tier;
 const tension=Math.max(0,state.tension+(held?2+pull:-6)),progress=Math.max(0,state.progress+(held&&tension>=28&&tension<=78?10+c.rod_level-2*tier:-3)),slack=tension<8?state.slack+1:0;
 let status:FishingState['status']='fighting',reason='';
 if(tension>=100){status='lost';reason='line_broke';}else if(slack>=20){status='lost';reason='slack_line';}else if(progress>=1000){status='caught';reason='landed';}
 return {tension:Math.min(100,tension),progress:Math.min(1000,progress),slack,status,reason};
}
export function replayFishing(c:FishingChallenge,p:FishingProof):FishingState{
 const bite=biteTick(c,p.cast_x),hook=p.hook_tick;
 if(hook===null||hook<bite||hook>bite+24)return {...initialFishing(),status:'lost',reason:'missed_hook'};
 let state=initialFishing(),held=false,index=0;
 for(let t=hook+1;t<=p.end_tick;t++){while(index<p.events.length&&p.events[index].tick<=t){held=p.events[index].held;index++;}state=fishingStep(state,c,t-hook,held);if(state.status!=='fighting'){if(t!==p.end_tick)throw new Error('Input continues after terminal tick');return state;}}
 if(p.end_tick!==maxFishingTicks)throw new Error('Fight is not finished');
 return {...state,status:'lost',reason:'fish_escaped'};
}
export function fishingChallenge(state:Record<string,unknown>):FishingChallenge|null{
 if(state.gameplay_version!==1||!['bite_tick','shoal_x','surge','rod_level'].every(key=>typeof state[key]==='number'&&Number.isInteger(state[key])))return null;
 if(state.boss_tier!==undefined&&(!Number.isInteger(state.boss_tier)||Number(state.boss_tier)<0||Number(state.boss_tier)>3))return null;
 return state as unknown as FishingChallenge;
}
