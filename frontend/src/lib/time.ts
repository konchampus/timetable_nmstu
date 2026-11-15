import type {Lesson,Schedule} from './types';
const zone='Asia/Yekaterinburg';
export const weekdays=['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'];
export const shortDays=['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
export function localDate(now:Date=new Date()):string{const parts=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);const part=(type:string)=>parts.find(item=>item.type===type)?.value??'';return part('year')+'-'+part('month')+'-'+part('day');}
export function minuteOfDay(now:Date=new Date()):number{const parts=new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(now).split(':').map(Number);return parts[0]*60+parts[1];}
export function toMinutes(time:string):number{const [h,m]=time.split(':').map(Number);return h*60+m;}
export function dayIndex(date:string):number{return (new Date(date+'T12:00:00+05:00').getUTCDay()+6)%7;}
export function shiftDate(date:string,days:number):string{const value=new Date(date+'T12:00:00Z');value.setUTCDate(value.getUTCDate()+days);return value.toISOString().slice(0,10);}
export function dateLabel(date:string):string{return new Intl.DateTimeFormat('ru-RU',{timeZone:zone,weekday:'short',day:'numeric',month:'long'}).format(new Date(date+'T12:00:00+05:00'));}
export function weekFor(date:string,_schedule:Schedule):1|2{const noon=Date.parse(date+'T12:00:00+05:00');const anchor=Date.parse('2024-08-19T00:00:00Z');const week=Math.ceil((noon-anchor)/604800000);return week%2===0?2:1;}
export function lessonsFor(schedule:Schedule,date:string,week?:1|2):Lesson[]{return schedule.lessons.filter(item=>item.week===(week??weekFor(date,schedule))&&item.weekday===dayIndex(date)).sort((a,b)=>toMinutes(a.start)-toMinutes(b.start)||a.title.localeCompare(b.title,'ru'));}
export function nearest(schedule:Schedule,now:Date):{lesson:Lesson;date:string;current:boolean}|null{const today=localDate(now),minute=minuteOfDay(now);for(let offset=0;offset<15;offset++){const date=shiftDate(today,offset);for(const lesson of lessonsFor(schedule,date)){if(offset===0&&toMinutes(lesson.end)<=minute)continue;return {lesson,date,current:offset===0&&toMinutes(lesson.start)<=minute};}}return null;}
export function nextStarting(schedule:Schedule,now:Date):{date:string;lessons:Lesson[]}|null{
 const today=localDate(now),minute=minuteOfDay(now);
 for(let offset=0;offset<15;offset++){
  const date=shiftDate(today,offset);
  const candidates=lessonsFor(schedule,date).filter(lesson=>offset>0||toMinutes(lesson.start)>minute);
  if(candidates.length)return {date,lessons:candidates.filter(lesson=>lesson.start===candidates[0].start)};
 }
 return null;
}
export function duration(minutes:number):string{const safe=Math.max(0,Math.ceil(minutes));return safe<60?safe+' мин':Math.floor(safe/60)+' ч'+(safe%60?' '+safe%60+' мин':'');}
