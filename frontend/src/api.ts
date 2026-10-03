export class ApiError extends Error{constructor(message:string,public status:number){super(message)}}
let csrfPromise:Promise<string>|null=null;
async function readResponse(response:Response){
 if(!response.ok){let error;try{error=await response.json()}catch{throw new ApiError(`Serveur : ${response.status}`,response.status)}throw new ApiError(typeof error.detail==='string'?error.detail:'Demande invalide. Vérifiez les paramètres.',response.status)}
 return response;
}
async function csrf(){
 if(!csrfPromise)csrfPromise=fetch('/api/me',{credentials:'same-origin'}).then(readResponse).then(r=>r.json()).then(u=>u.csrf_token??'').catch(e=>{csrfPromise=null;throw e});
 return csrfPromise;
}
export async function request(path:string,body?:unknown,signal?:AbortSignal,extra:Record<string,string>={}){
 const headers:Record<string,string>={...extra};
 if(body!==undefined){if(!(body instanceof FormData))headers['Content-Type']='application/json';headers['X-CSRF-Token']=await csrf()}
 const response=await fetch('/api'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers,body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body),signal});
 if(response.status===401||response.status===403)csrfPromise=null;
 return readResponse(response);
}
export async function api<T>(path:string,body?:unknown,signal?:AbortSignal,extra:Record<string,string>={}):Promise<T>{return (await request(path,body,signal,extra)).json()}
export async function download(data:Blob|string,name:string,type='application/json') {
 const form=new FormData();form.append('file',data instanceof Blob?data:new Blob([data],{type}),name);
 const file=await api<{url:string;name:string}>('/exports',form);
 const a=document.createElement('a');a.href=file.url;a.download=file.name;document.body.append(a);a.click();a.remove();return file;
}
export async function exportBlob(path:string,body:unknown){return (await request(path,body)).blob()}
