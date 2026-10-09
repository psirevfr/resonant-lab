// Deadline for job transport only; never a timeout or cancellation of the calculation.
export async function withDeadline<T>(parent:AbortSignal,run:(signal:AbortSignal)=>Promise<T>,timeout=15000):Promise<T>{
 if(parent.aborted)throw parent.reason??new DOMException('Suivi interrompu','AbortError');
 const controller=new AbortController();
 const aborted=()=>controller.abort(parent.reason);
 parent.addEventListener('abort',aborted,{once:true});
 let rejectAbort:(()=>void)|undefined;
 const interrupted=new Promise<never>((_,reject)=>{
  rejectAbort=()=>reject(controller.signal.reason??new DOMException('Suivi interrompu','AbortError'));
  controller.signal.addEventListener('abort',rejectAbort,{once:true});
 });
 const timer=setTimeout(()=>controller.abort(new DOMException('Suivi réseau expiré','TimeoutError')),timeout);
 try{return await Promise.race([run(controller.signal),interrupted])}finally{
  clearTimeout(timer);parent.removeEventListener('abort',aborted);
  if(rejectAbort)controller.signal.removeEventListener('abort',rejectAbort);
 }
}
