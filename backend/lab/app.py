"""Local-only API. Audio remains in RAM, with bounded session caches."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from threading import Event, RLock
from uuid import uuid4
import csv
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .schema import Patch,Block,RenderRequest,AnalyzeRequest,GenerateRequest,OptimizeRequest,CompactRequest,InstrumentRequest
from .blocks import catalog,parameters
from .audio import read_wav,wav_bytes,excerpt,view
from .analysis import analyze
from .identify import generate
from .compact import simplify
from .instrument import expand_modes,prepare,transpose
from .graph import render,validate
from .metrics import Objective
from .transfer import describe,global_response
from .optimization import run_optimization
from .export import graph_svg
from .media import wav_response


app=FastAPI(title='Résonant Lab',version='0.1.0')
recordings=OrderedDict(); renders=OrderedDict(); jobs=OrderedDict(); downloads=OrderedDict(); lock=RLock()
executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='identification')

@app.exception_handler(ValueError)
async def invalid(_,exc): return JSONResponse(status_code=422,content={'detail':str(exc)})

def get_recording(key):
    with lock:
        if key not in recordings: raise HTTPException(404,'Audio absent de la session ; réimporter le WAV.')
        return recordings[key]

def store_audio(record):
    key=uuid4().hex
    with lock:
        recordings[key]=record
        while len(recordings)>4 or (len(recordings)>1 and sum(r.samples.nbytes+len(r.original) for r in recordings.values())>400_000_000): recordings.popitem(last=False)
    return key

def target_audio(req):
    n=round(req.patch.duration*req.patch.sample_rate)
    if not req.audio_id: return None
    rec=get_recording(req.audio_id)
    if req.start+req.patch.duration > len(rec.samples)/rec.sample_rate+2/req.patch.sample_rate: raise ValueError('La durée du modèle dépasse la sélection disponible dans le WAV.')
    x=excerpt(rec,req.start,req.patch.duration,req.patch.sample_rate)
    return np.pad(x,(0,max(0,n-len(x))))[:n]

@app.get('/api/health')
def health(): return {'status':'ok','version':'0.1.0'}

@app.get('/api/blocks')
def blocks(): return catalog()

@app.post('/api/audio')
def upload(file: UploadFile=File(...)):
    data=file.file.read(128*1024*1024+1); rec=read_wav(data,Path(file.filename or 'audio.wav').name); key=store_audio(rec)
    return {'id':key,'metadata':rec.metadata(),'view':view(rec.mono,rec.sample_rate)}

@app.post('/api/demo')
def demo():
    fs=44100; t=np.arange(fs*3)/fs
    x=sum(a*np.exp(-t/tau)*(1-np.exp(-t/.005))*np.sin(2*np.pi*f*t) for a,f,tau in [(0.45,261.63,1.5),(.23,523.6,.8),(.12,786.8,.5),(.07,1051.6,.35)])
    rec=read_wav(wav_bytes(x,fs),'Note modale de démonstration.wav'); key=store_audio(rec)
    return {'id':key,'metadata':rec.metadata(),'view':view(x,fs)}

@app.get('/api/audio/{key}/wav')
def original(key:str,request:Request): return wav_response(get_recording(key).original,request.headers.get('range'))

@app.get('/api/audio/{key}/segment')
def segment(key:str,request:Request,start:float=0,duration:float=3):
    if start<0 or duration<=0 or duration>60: raise ValueError('Sélection invalide.')
    rec=get_recording(key); x=excerpt(rec,start,duration)
    return wav_response(wav_bytes(x,rec.sample_rate),request.headers.get('range'))

@app.post('/api/analyze')
def analysis(req:AnalyzeRequest):
    rec=get_recording(req.audio_id); x=excerpt(rec,req.start,req.duration)
    return analyze(x,rec.sample_rate,req.max_partials)

@app.post('/api/generate')
def identify(req:GenerateRequest):
    rec=get_recording(req.audio_id); fs=rec.sample_rate if rec.sample_rate in (44100,48000,96000) else 44100
    x=excerpt(rec,req.start,req.duration,fs)
    return generate(x,fs,req.max_partials,req.complexity_penalty,req.weights,req.refine_modes,req.include_impact,req.detailed)

@app.post('/api/patch/expand')
def expand(req:Patch):return expand_modes(req).model_dump()

@app.post('/api/instrument/prepare')
def prepare_instrument(req:Patch):return prepare(req).model_dump()

@app.post('/api/instrument/note')
def instrument_note(req:InstrumentRequest):
    if req.patch.duration>12:raise ValueError('Instrument limité à 12 secondes par note.')
    p,muted=transpose(req.patch,req.note,req.reference_note,req.velocity,req.gate,req.track_filters)
    return Response(wav_bytes(render(p),p.sample_rate),media_type='audio/wav',headers={'X-Muted-Partials':str(len(muted))})

@app.post('/api/instrument/patch')
def instrument_patch(req:InstrumentRequest):
    p,muted=transpose(req.patch,req.note,req.reference_note,req.velocity,req.gate,req.track_filters)
    return {'patch':p.model_dump(),'muted':muted}

@app.post('/api/compact')
def compact(req:CompactRequest):
    x=target_audio(req)
    if x is None:raise ValueError('Importez un WAV de référence avant de simplifier.')
    return simplify(req.patch,x,req.weights,req.tolerance,req.test_shaping,req.protect_texture)

@app.post('/api/render')
def simulate(req:RenderRequest):
    x=target_audio(req); y=render(req.patch); key=uuid4().hex
    with lock:
        renders[key]=wav_bytes(y,req.patch.sample_rate)
        while len(renders)>4: renders.popitem(last=False)
    return {'id':key,'view':view(y,req.patch.sample_rate),'reference':view(x,req.patch.sample_rate) if x is not None else None,'difference':view(x-y,req.patch.sample_rate) if x is not None else None,'errors':Objective(x,req.patch.sample_rate,req.weights).components(y) if x is not None else None,'clipping':bool(np.max(abs(y))>1),'sample_rate':req.patch.sample_rate}

@app.get('/api/render/{key}/wav')
def rendered(key:str,request:Request):
    with lock:
        if key not in renders: raise HTTPException(404,'Rendu expiré ; générer à nouveau.')
        return wav_response(renders[key],request.headers.get('range'))

class TransferRequest(BaseModel):
    node: Block
    sample_rate: int=44100

@app.post('/api/transfer')
def transfer(req:TransferRequest):
    if req.sample_rate not in (44100,48000,96000): raise ValueError('Fréquence d’échantillonnage non prise en charge.')
    return describe(req.node,req.sample_rate)

class GlobalRequest(BaseModel):
    patch: Patch
    source_id: str

@app.post('/api/transfer/global')
def global_transfer(req:GlobalRequest): return global_response(req.patch,req.source_id)

@app.post('/api/patch/validate')
def validate_patch(patch:Patch):
    validate(patch)
    normalized=patch.model_copy(deep=True)
    for node in normalized.nodes: node.parameters=parameters(node.type,node.parameters,patch.sample_rate)
    return normalized.model_dump()

@app.post('/api/export/svg')
def svg(patch:Patch):
    validate(patch); return Response(graph_svg(patch),media_type='image/svg+xml')

@app.post('/api/export/csv')
def csv_export(patch:Patch):
    validate(patch); out=StringIO(); writer=csv.writer(out); writer.writerow(['block_id','type','parameter','value','unit'])
    definitions=catalog()
    for node in patch.nodes:
        for k,v in parameters(node.type,node.parameters,patch.sample_rate).items(): writer.writerow([node.id,node.type,k,v,definitions[node.type]['parameters'][k]['unit']])
    return Response(out.getvalue(),media_type='text/csv')

@app.post('/api/exports')
def prepare_download(file: UploadFile=File(...)):
    """Give browser-created reports/images a normal, bounded local download URL."""
    types={'.monpatch':'application/json','.json':'application/json','.wav':'audio/wav',
           '.svg':'image/svg+xml','.png':'image/png','.csv':'text/csv','.html':'text/html'}
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in types: raise ValueError('Format d’export inconnu.')
    data=file.file.read(32_000_001)
    if len(data)>32_000_000: raise ValueError('Export limité à 32 Mo.')
    key=uuid4().hex; name='resonant'+suffix
    with lock:
        downloads[key]=(name,types[suffix],data)
        while len(downloads)>8 or sum(len(d[2]) for d in downloads.values())>64_000_000:
            downloads.popitem(last=False)
    return {'url':f'/api/exports/{key}','name':name}

@app.get('/api/exports/{key}')
def download_export(key:str):
    with lock:
        if key not in downloads: raise HTTPException(404,'Export expiré ; préparez à nouveau le fichier.')
        name,media_type,data=downloads[key]
    return Response(data,media_type=media_type,headers={
        'Content-Disposition':f'attachment; filename="{name}"',
        'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

@app.post('/api/optimize')
def optimize(req:OptimizeRequest):
    if not req.audio_id: raise ValueError('Importer une référence pour optimiser.')
    validate(req.patch); x=target_audio(req)
    with lock:
        if any(j['status'] in ('queued','running') for j in jobs.values()): raise HTTPException(409,'Une optimisation est déjà en cours.')
        key=uuid4().hex; event=Event(); jobs[key]={'status':'queued','cancel':event,'progress':{}}
        while len(jobs)>12: jobs.popitem(last=False)
    def progress(data):
        with lock: jobs[key]['progress']=data
    def work():
        with lock: jobs[key]['status']='running'
        try:
            result=run_optimization(req,x,progress,event)
            with lock: jobs[key].update(status='completed',result=result)
        except Exception as exc:
            with lock: jobs[key].update(status='failed',error=str(exc))
    executor.submit(work)
    return {'id':key}

@app.get('/api/jobs/{key}')
def job(key:str):
    with lock:
        if key not in jobs: raise HTTPException(404,'Tâche inconnue.')
        return {k:v for k,v in jobs[key].items() if k!='cancel'}

@app.post('/api/jobs/{key}/cancel')
def cancel_job(key:str):
    with lock:
        if key not in jobs: raise HTTPException(404,'Tâche inconnue.')
        jobs[key]['cancel'].set()
    return {'ok':True}

DIST=Path(__file__).resolve().parents[2]/'frontend'/'dist'
if DIST.exists():
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/')
    def index(): return FileResponse(DIST/'index.html')
    @app.get('/favicon.svg')
    def favicon(): return FileResponse(DIST/'favicon.svg')
    
    
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

from lab.auth import (
    init_db,
    get_db,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_user
)

app = FastAPI(title="Résonant")

@app.on_event("startup")
def startup_event():
    init_db()

# Style CSS regroupé pour alléger le code
CSS = "<style>body{font-family:sans-serif; max-width:600px; margin:auto; padding:2rem; line-height:1.5;} input,button{width:100%; padding:10px; margin-bottom:15px; box-sizing:border-box;} button{background:#0066cc; color:white; border:none; cursor:pointer; font-weight:bold; border-radius:5px;} a{color:#0066cc; text-decoration:none;}</style>"


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = get_current_user(request)
    if user:
        return f"{CSS}<h1>Bienvenue, {user['username']} !</h1><p>Tu es connecté.</p><a href='/dashboard'>➡️ Espace Membre</a> | <a href='/logout' style='color:red;'>Déconnexion</a>"
    return f"{CSS}<h1>Résonant</h1><p>Ce site héberge la plateforme. Connecte-toi pour y accéder.</p><a href='/login'><button style='width:auto;'>Se connecter</button></a> <a href='/register'>Créer un compte</a>"


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return f"{CSS}<h2>Inscription</h2><form method='post' action='/register'><input type='text' name='username' placeholder='Pseudo' required /><input type='email' name='email' placeholder='Email' required /><input type='password' name='password' placeholder='Mot de passe' required /><button type='submit'>Créer mon compte</button></form><p align='center'><a href='/login'>Déjà membre ? Se connecter</a></p>"


@app.post("/register")
def register(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Pseudo ou email déjà utilisé.")
    
    cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", (username, email, hash_password(password)))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/login?registered=true", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    msg = "<p style='color:green;'>Compte créé avec succès ! Tu peux te connecter.</p>" if request.query_params.get("registered") else ""
    return f"{CSS}<h2>Connexion</h2>{msg}<form method='post' action='/login'><input type='text' name='username' placeholder='Pseudo' required /><input type='password' name='password' placeholder='Mot de passe' required /><button type='submit'>Se connecter</button></form><p align='center'><a href='/register'>Pas de compte ? S'inscrire</a></p>"


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Identifiants incorrects.")
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=create_access_token(data={"sub": user["username"]}), httponly=True, secure=True, samesite="lax")
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(current_user: dict = Depends(require_user)):
    return f"{CSS}<h1>Espace Membre</h1><p>Bienvenue <strong>{current_user['username']}</strong> ! Tu as désormais accès aux fonctionnalités de Résonant.</p><p><a href='/logout' style='color:red;'>Se déconnecter</a></p>"
