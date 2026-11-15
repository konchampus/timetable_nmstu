let token: string | null = null;
export function hasSession():boolean {return token!==null;}
export class ApiError extends Error { constructor(message:string,public status:number,public code?:string){super(message);this.name='ApiError';} }
export function mutationKey():string {return crypto.randomUUID();}
export function clearSession(purgePending=false):void {token=null;if(purgePending){try{for(let index=sessionStorage.length-1;index>=0;index--){const key=sessionStorage.key(index);if(key?.startsWith('magtu-games-pending:'))sessionStorage.removeItem(key);}}catch{ /* A disabled browser store contains no accessible recovery envelope. */ }}}
export async function api<T>(path:string,init:RequestInit={}):Promise<T>{
 const controller=new AbortController(); const abort=()=>controller.abort(); init.signal?.addEventListener('abort',abort,{once:true}); if(init.signal?.aborted)controller.abort();
 const timeout=window.setTimeout(()=>controller.abort(),25000);
 try {
  const requestToken=token; const headers=new Headers(init.headers); if(init.body&&!headers.has('Content-Type'))headers.set('Content-Type','application/json'); if(token)headers.set('Authorization','Bearer '+token);
  const response=await fetch('/api'+path,{...init,headers,signal:controller.signal,cache:'no-store',credentials:'omit',redirect:'error'});
  if(!response.ok){let message='Не удалось выполнить запрос. Попробуйте ещё раз.',code:string|undefined;try{const body:unknown=await response.json();if(body&&typeof body==='object'&&'detail' in body){const detail=(body as {detail:unknown}).detail;if(typeof detail==='string')message=detail;else if(detail&&typeof detail==='object'&&'message' in detail&&typeof detail.message==='string'){message=detail.message;if('code' in detail&&typeof detail.code==='string')code=detail.code;}else if(Array.isArray(detail))message='Проверьте заполненные поля.';}}catch{message='Сервис временно недоступен. Попробуйте позже.';} if(response.status===401&&path!=='/auth/telegram'&&requestToken!==null&&token===requestToken){token=null;window.dispatchEvent(new Event('companion:session-expired'));}throw new ApiError(message,response.status,code);}
  if(response.status===204)return undefined as T;
  return await response.json() as T;
 }catch(error){if(error instanceof ApiError)throw error;if(error instanceof DOMException&&error.name==='AbortError')throw new ApiError('Запрос прерван или истекло время ожидания. Для игровой операции используйте повтор с тем же ключом.',0);throw new ApiError('Нет связи с сервером. Проверьте подключение и повторите действие.',0);}
 finally{clearTimeout(timeout);init.signal?.removeEventListener('abort',abort);}
}
export async function authenticate(initData:string):Promise<void>{const result=await api<{token:string}>('/auth/telegram',{method:'POST',body:JSON.stringify({init_data:initData})});token=result.token;}
export const messageOf=(error:unknown):string=>error instanceof Error?error.message:'Не удалось выполнить действие.';
