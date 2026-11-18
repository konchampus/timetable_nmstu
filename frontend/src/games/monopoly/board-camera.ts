export const BOARD_SIDE=704;
export const CELL_SIDE=BOARD_SIDE/11;
export interface Viewport {width:number;height:number;}
export interface Camera {x:number;y:number;scale:number;}
export function cellPosition(id:number):[number,number]{
 const i=((Math.trunc(id)%40)+40)%40;
 if(i<=10)return [10-i,10];if(i<=20)return [0,20-i];if(i<=30)return [i-20,0];return [10,i-30];
}
export function gestureMoved(dx:number,dy:number,initialDistance:number,distance:number){return Math.hypot(dx,dy)>5||Math.abs(distance-initialDistance)>5;}
export function fitScale(v:Viewport){return Math.max(.1,Math.min(v.width,v.height)/BOARD_SIDE);}
export function constrain(camera:Camera,v:Viewport):Camera {
 const scale=Math.max(fitScale(v),Math.min(2.5,camera.scale));const side=BOARD_SIDE*scale;
 const axis=(offset:number,extent:number)=>side<=extent?(extent-side)/2:Math.max(extent-side,Math.min(0,offset));
 return {scale,x:axis(camera.x,v.width),y:axis(camera.y,v.height)};
}
export function focusCell(id:number,v:Viewport,scale=Math.max(1,fitScale(v))):Camera {
 const [col,row]=cellPosition(id);
 return constrain({scale,x:v.width/2-(col+.5)*CELL_SIDE*scale,y:v.height/2-(row+.5)*CELL_SIDE*scale},v);
}
export function fitCamera(v:Viewport):Camera {return constrain({x:0,y:0,scale:fitScale(v)},v);}
export function zoomAt(camera:Camera,scale:number,v:Viewport,anchor={x:v.width/2,y:v.height/2}):Camera {
 const next=Math.max(fitScale(v),Math.min(2.5,scale));
 const ratio=next/camera.scale;
 return constrain({scale:next,x:anchor.x-(anchor.x-camera.x)*ratio,y:anchor.y-(anchor.y-camera.y)*ratio},v);
}
