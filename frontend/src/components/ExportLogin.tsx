import {useEffect,useRef,useState} from 'react';
import {api,resetSession} from '../api';
export interface LabUser{id:number;username:string;email:string;guest?:boolean}

export function ExportLogin({onClose,onConnected}:{onClose:()=>void;onConnected:(user:LabUser)=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 const [checking,setChecking]=useState(false),[message,setMessage]=useState(''),[authPath,setAuthPath]=useState('');
 const connected=useRef(onConnected);connected.current=onConnected;
 useEffect(()=>{dialog.current?.showModal();return()=>{dialog.current?.close()}},[]);
 useEffect(()=>{
  if(!checking)return;
  let stopped=false,timer:ReturnType<typeof setTimeout>;
  const control=new AbortController();
  async function check(){
   try{const user=await api<LabUser>('/me',undefined,control.signal);if(!stopped&&!user.guest){resetSession();connected.current(user);return}}
   catch{if(!stopped)setMessage('Connexion non confirmée. Vous pouvez réessayer ou continuer le laboratoire.')}
   if(!stopped)timer=setTimeout(check,document.hidden?5000:1500);
  }
  void check();return()=>{stopped=true;control.abort();clearTimeout(timer)};
 },[checking]);
 function login(path:string){setAuthPath(path+'?embed=1');setChecking(true);setMessage('Votre montage reste ouvert pendant la connexion.')}
 return <dialog ref={dialog} className="export-login" aria-labelledby="export-login-title" onCancel={e=>{e.preventDefault();onClose()}}>
 <h2 id="export-login-title">Un compte pour exporter</h2><p>Vous pouvez analyser, générer et écouter librement. Pour télécharger vos fichiers, connectez-vous ou créez un compte.</p><p>Votre montage et vos résultats restent ouverts pendant la connexion.</p>
 <div className="guide-navigation"><button className="primary" onClick={()=>login('/login')}>Connexion</button><button onClick={()=>login('/register')}>Créer un compte</button></div>
 {message&&<p role="status">{message}</p>}<button className="export-login-close" onClick={onClose}>Continuer sans exporter</button>
 {authPath&&<iframe className="export-auth-frame" src={authPath} title="Connexion au compte Résonant"/>}
 </dialog>
}
