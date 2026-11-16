// Integer ballistic model. Keep parity with backend/app/games/arcade.py.
export const sports = ['darts','bowling','basketball','football'] as const;
export type Sport = typeof sports[number];
export interface Challenge {gameplay_version:1; wind:number; target_x:number; target_y:number}
export interface Shot {aim_x:number; aim_y:number; power:number; ticks:number}
export const isSport = (value:string):value is Sport => sports.some(game=>game===value);
export function readChallenge(state:Record<string,unknown>):Challenge|null {
 if(state.gameplay_version!==1||![state.wind,state.target_x,state.target_y].every(value=>typeof value==='number'&&Number.isInteger(value)))return null;
 return {gameplay_version:1,wind:state.wind as number,target_x:state.target_x as number,target_y:state.target_y as number};
}
export function trajectory(challenge:Challenge,shot:Shot) {
 return Array.from({length:61},(_,t)=>({x:Math.trunc(shot.aim_x*t/60)+Math.trunc(challenge.wind*t*t/3600),y:Math.trunc(shot.aim_y*t/60)+Math.trunc((shot.power-650)*t/30)+Math.trunc(2400*t*(60-t)/3600),z:t}));
}
export function replay(game:Sport,challenge:Challenge,shot:Shot):Record<string,number|boolean> {
 const point=trajectory(challenge,shot)[60],dx=point.x-challenge.target_x,dy=point.y-challenge.target_y,distance=dx*dx+dy*dy;
 let result:Record<string,number|boolean>;
 if(game==='darts'){const rings=[[70,50],[150,25],[270,20],[400,10],[540,5]];result={value:rings.find(([radius])=>distance<=radius*radius)?.[1]??0};}
 else if(game==='bowling'){const pins=[[0,0],[-65,65],[65,65],[-130,130],[0,130],[130,130],[-195,195],[-65,195],[65,195],[195,195]];result={value:pins.filter(([x,y])=>(dx-x)**2+(dy-y)**2<=(160+Math.trunc(shot.power/10))**2).length};}
 else result={success:game==='basketball'?distance<=110**2:Math.abs(dx)<=260&&Math.abs(dy)<=180};
 return {...result,impact_x:point.x,impact_y:point.y,gameplay_version:1};
}
