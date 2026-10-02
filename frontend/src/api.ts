export async function api<T>(path:string,body?:unknown,signal?:AbortSignal):Promise<T> {
 const response=await fetch('/api'+path,{method:body===undefined?'GET':'POST',headers:body instanceof FormData?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body),signal});
 if(!response.ok){let error;try{error=await response.json()}catch{throw Error(`Serveur : ${response.status}`)}throw Error(typeof error.detail==='string'?error.detail:JSON.stringify(error.detail??error));}
 return response.json();
}
export async function download(data:Blob|string,name:string,type='application/json') {
 const form=new FormData();form.append('file',data instanceof Blob?data:new Blob([data],{type}),name);
 const file=await api<{url:string;name:string}>('/exports',form);
 const a=document.createElement('a');a.href=file.url;a.download=file.name;document.body.append(a);a.click();a.remove();return file;
}
export async function exportBlob(path:string,body:unknown){const r=await fetch('/api'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok){const e=await r.json();throw Error(e.detail)}return r.blob()}
