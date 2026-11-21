import { defineConfig,loadEnv,type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({mode})=>{
 const previewApi=loadEnv(mode,'.','RESONANT_PREVIEW_API_ORIGIN').RESONANT_PREVIEW_API_ORIGIN;
 if(previewApi&&!/^http:\/\/(127\.0\.0\.1|localhost):[0-9]{1,5}$/.test(previewApi))throw Error('Adresse API locale invalide.');
 const apiOrigin=previewApi||'http://127.0.0.1:8000';
 // A Vite page normally bypasses the backend HTML route which issues the
 // visitor cookie. Keep real session/CSRF checks in the isolated editor preview.
 const previewSession:Plugin={name:'resonant-local-preview-session',configureServer(server){
  if(!previewApi)return;
  server.middlewares.use(async(req,res,next)=>{
   const request=req as unknown as {method?:string;headers:{accept?:string;cookie?:string}};
   if(request.method!=='GET'||!request.headers.accept?.includes('text/html'))return next();
   try{
    const response=await fetch(previewApi+'/analyse',{redirect:'error',signal:AbortSignal.timeout(5000),headers:request.headers.cookie?{cookie:request.headers.cookie}:{}});
    const cookie=response.headers.get('set-cookie');
    if(cookie)res.setHeader('Set-Cookie',cookie);
    if(!response.ok){res.statusCode=503;res.end('La session de prévisualisation n’est pas disponible. Réessayez.');return;}
    next();
   }catch{res.statusCode=503;res.end('Le backend de prévisualisation n’est pas disponible.');}
  });
 }};
 return {plugins:[react(),previewSession],server:{proxy:{'/api':{target:apiOrigin,changeOrigin:false},'/compute-runtime':{target:apiOrigin,changeOrigin:false}}},build:{chunkSizeWarningLimit:5500}};
});
