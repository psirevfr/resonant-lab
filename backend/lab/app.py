"""Private API with bounded caches and temporary, owner-scoped WAV references."""
from collections import OrderedDict
from io import StringIO
from pathlib import Path
from threading import RLock,BoundedSemaphore
from uuid import uuid4
import math
import csv
import numpy as np

from fastapi import Security, HTTPException, status, Depends
from fastapi.security.api_key import APIKeyHeader
import sqlite3
from fastapi import FastAPI, APIRouter, Depends, UploadFile, File, HTTPException, Request, Form, status
from fastapi.responses import Response, JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from html import escape

# Imports de ton application
from .schema import Patch,Block,RenderRequest,AnalyzeRequest,GenerateRequest,OptimizeRequest,CompactRequest,InstrumentRequest
from .blocks import catalog,parameters
from .audio import read_wav,wav_bytes,excerpt,view
from .analysis import analyze
from .identify import generate
from .compact import validate_simplification
from .instrument import expand_modes,prepare,transpose
from .graph import render,validate
from .metrics import Objective
from .transfer import describe,global_response
from .optimization import run_optimization
from .export import graph_svg
from .media import wav_response

# Imports de l'authentification
from .auth import (
    init_db, get_db, hash_password, verify_password,
    create_access_token, get_current_user, require_user, require_api_user, check_origin, csrf_token, revoke_session,
    get_visitor,create_visitor,claim_visitor,require_account,rate_limit,valid_csrf
)

app=FastAPI(title='Résonant Lab',version='0.1.0')

from . import job_store
from . import audio_store
from .request_limits import RequestLimits
from .security_headers import SecurityHeaders
app.add_middleware(RequestLimits)
app.add_middleware(SecurityHeaders)

@app.get('/api/dev/status')
def developer_status(user:dict=Depends(require_api_user)):
    return {'status':'online','authenticated_as':user['username']}

api_router=APIRouter(dependencies=[Depends(require_api_user)])

recordings=OrderedDict(); renders=OrderedDict(); downloads=OrderedDict(); lock=RLock()
upload_guard=BoundedSemaphore(1)

@app.exception_handler(ValueError)
async def invalid(_,exc): return JSONResponse(status_code=422,content={'detail':str(exc)})

# Validation errors must not echo submitted passwords, audio or non-JSON NaN.
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def invalid_fields(_,exc):
    errors=[{k:e[k] for k in ('type','loc','msg') if k in e} for e in exc.errors()]
    return JSONResponse(status_code=422,content={'detail':errors})

def get_recording(key,owner):
    with lock:
        if key in recordings and recordings[key][0]==owner:return recordings[key][1]
    record=audio_store.load(key,owner)
    if record is None:raise HTTPException(404,'Référence audio absente ou expirée ; réimporter le WAV.')
    cache_audio(key,record,owner)
    return record

def store_audio(record,owner):
    key=audio_store.save(record,owner)
    cache_audio(key,record,owner)
    return key

def cache_audio(key,record,owner):
    with lock:
        recordings[key]=(owner,record)
        while len(recordings)>4 or (len(recordings)>1 and sum(r.samples.nbytes+len(r.original) for _,r in recordings.values())>400_000_000): recordings.popitem(last=False)

def target_audio(req,owner):
    n=round(req.patch.duration*req.patch.sample_rate)
    if not req.audio_id: return None
    rec=get_recording(req.audio_id,owner)
    if req.start+req.patch.duration > len(rec.samples)/rec.sample_rate+2/req.patch.sample_rate: raise ValueError('La durée du modèle dépasse la sélection disponible dans le WAV.')
    x=excerpt(rec,req.start,req.patch.duration,req.patch.sample_rate)
    return np.pad(x,(0,max(0,n-len(x))))[:n]

@app.get('/api/health')
def health(): return {'status':'ok','version':'0.1.0'}

@api_router.get('/api/blocks')
def blocks(): return catalog()

@api_router.post('/api/audio')
def upload(file: UploadFile=File(...),user:dict=Depends(require_api_user)):
    if not upload_guard.acquire(blocking=False):raise HTTPException(429,'Un import audio est en cours. Réessayez dans quelques secondes.',headers={'Retry-After':'3'})
    try:
        limit=32_000_000 if user.get('guest') else 128*1024*1024
        data=file.file.read(limit+1)
        if len(data)>limit:raise HTTPException(413,'WAV visiteur limité à 32 Mo.' if user.get('guest') else 'WAV limité à 128 Mo.')
        rec=read_wav(data,Path(file.filename or 'audio.wav').name,4_000_000 if user.get('guest') else 30_000_000);key=store_audio(rec,user['id'])
        return {'id':key,'metadata':rec.metadata(),'view':view(rec.mono,rec.sample_rate)}
    finally:upload_guard.release()

@api_router.post('/api/demo')
def demo(user:dict=Depends(require_api_user)):
    fs=44100; t=np.arange(fs*3)/fs
    x=sum(a*np.exp(-t/tau)*(1-np.exp(-t/.005))*np.sin(2*np.pi*f*t) for a,f,tau in [(0.45,261.63,1.5),(.23,523.6,.8),(.12,786.8,.5),(.07,1051.6,.35)])
    rec=read_wav(wav_bytes(x,fs),'Note modale de démonstration.wav'); key=store_audio(rec,user["id"])
    return {'id':key,'metadata':rec.metadata(),'view':view(x,fs)}

@api_router.get('/api/audio/{key}/wav',dependencies=[Depends(require_account)])
def original(key:str,request:Request,user:dict=Depends(require_api_user)): return wav_response(get_recording(key,user["id"]).original,request.headers.get('range'))

@api_router.get('/api/audio/{key}/segment')
def segment(key:str,request:Request,start:float=0,duration:float=3,user:dict=Depends(require_api_user)):
    if not math.isfinite(start) or not math.isfinite(duration) or start<0 or duration<=0 or duration>60: raise ValueError('Sélection invalide.')
    rec=get_recording(key,user["id"]); x=excerpt(rec,start,duration)
    return wav_response(wav_bytes(x,rec.sample_rate),request.headers.get('range'))

@api_router.post('/api/analyze')
def analysis(req:AnalyzeRequest,user:dict=Depends(require_api_user)):
    rec=get_recording(req.audio_id,user["id"]); x=excerpt(rec,req.start,req.duration)
    return analyze(x,rec.sample_rate,req.max_partials)

def submit(kind,req,request,user):
    data=req.model_dump();idem=request.headers.get('idempotency-key')
    job_store.maintain()
    previous=job_store.replay(user['id'],kind,data,idem)
    if previous:return previous
    if kind=='generate':
        rec=get_recording(req.audio_id,user['id'])
        fs=rec.sample_rate if rec.sample_rate in (44100,48000,96000) else 44100
        if req.start+req.duration>len(rec.samples)/rec.sample_rate+1/fs:raise ValueError('Sélection hors du WAV.')
        x=excerpt(rec,req.start,req.duration,fs)
    else:
        validate(req.patch)
        if req.patch.duration>12:raise ValueError('Calcul limité à 12 secondes.')
        x=target_audio(req,user['id']);fs=req.patch.sample_rate
        if x is None:raise ValueError('Importez une référence pour ce calcul.')
        if kind=='optimize':
            from .optimization import validate_request
            validate_request(req)
        else:validate_simplification(req.patch,req.tolerance)
    return job_store.enqueue(user['id'],kind,data,x,fs,idem)

@api_router.post('/api/generate',status_code=202)
def identify(req:GenerateRequest,request:Request,user:dict=Depends(require_api_user)):
    return submit('generate',req,request,user)

@api_router.post('/api/patch/expand')
def expand(req:Patch):return expand_modes(req).model_dump()

@api_router.post('/api/instrument/prepare')
def prepare_instrument(req:Patch):return prepare(req).model_dump()

@api_router.post('/api/instrument/note',dependencies=[Depends(require_account)])
def instrument_note(req:InstrumentRequest):
    if req.patch.duration>12:raise ValueError('Instrument limité à 12 secondes par note.')
    p,muted=transpose(req.patch,req.note,req.reference_note,req.velocity,req.gate,req.track_filters)
    return Response(wav_bytes(render(p),p.sample_rate),media_type='audio/wav',headers={'X-Muted-Partials':str(len(muted))})

@api_router.post('/api/instrument/patch')
def instrument_patch(req:InstrumentRequest):
    p,muted=transpose(req.patch,req.note,req.reference_note,req.velocity,req.gate,req.track_filters)
    return {'patch':p.model_dump(),'muted':muted}

@api_router.post('/api/compact',status_code=202)
def compact(req:CompactRequest,request:Request,user:dict=Depends(require_api_user)):
    return submit('compact',req,request,user)

@api_router.post('/api/render',dependencies=[Depends(require_account)])
def simulate(req:RenderRequest,user:dict=Depends(require_api_user)):
    x=target_audio(req,user["id"]); y=render(req.patch); key=uuid4().hex
    with lock:
        renders[key]=(user["id"],wav_bytes(y,req.patch.sample_rate))
        while len(renders)>4: renders.popitem(last=False)
    return {'id':key,'view':view(y,req.patch.sample_rate),'reference':view(x,req.patch.sample_rate) if x is not None else None,'difference':view(x-y,req.patch.sample_rate) if x is not None else None,'errors':Objective(x,req.patch.sample_rate,req.weights).components(y) if x is not None else None,'clipping':bool(np.max(abs(y))>1),'sample_rate':req.patch.sample_rate}

@api_router.get('/api/render/{key}/wav',dependencies=[Depends(require_account)])
def rendered(key:str,request:Request,user:dict=Depends(require_api_user)):
    with lock:
        if key not in renders or renders[key][0]!=user["id"]: raise HTTPException(404,'Rendu expiré ; générer à nouveau.')
        return wav_response(renders[key][1],request.headers.get('range'))

class TransferRequest(BaseModel):
    node: Block
    sample_rate: int=44100

@api_router.post('/api/transfer')
def transfer(req:TransferRequest):
    if req.sample_rate not in (44100,48000,96000): raise ValueError('Fréquence d’échantillonnage non prise en charge.')
    return describe(req.node,req.sample_rate)

class GlobalRequest(BaseModel):
    patch: Patch
    source_id: str

@api_router.post('/api/transfer/global')
def global_transfer(req:GlobalRequest): return global_response(req.patch,req.source_id)

@api_router.post('/api/patch/validate')
def validate_patch(patch:Patch):
    validate(patch)
    normalized=patch.model_copy(deep=True)
    for node in normalized.nodes: node.parameters=parameters(node.type,node.parameters,patch.sample_rate)
    return normalized.model_dump()

@api_router.post('/api/export/svg',dependencies=[Depends(require_account)])
def svg(patch:Patch):
    validate(patch); return Response(graph_svg(patch),media_type='image/svg+xml')

@api_router.post('/api/export/csv',dependencies=[Depends(require_account)])
def csv_export(patch:Patch):
    validate(patch); out=StringIO(); writer=csv.writer(out); writer.writerow(['block_id','type','parameter','value','unit'])
    definitions=catalog()
    for node in patch.nodes:
        for k,v in parameters(node.type,node.parameters,patch.sample_rate).items(): writer.writerow([csv_cell(node.id),csv_cell(node.type),csv_cell(k),v,csv_cell(definitions[node.type]['parameters'][k]['unit'])])
    return Response(out.getvalue(),media_type='text/csv')

@api_router.post('/api/exports',dependencies=[Depends(require_account)])
def prepare_download(file: UploadFile=File(...),user:dict=Depends(require_api_user)):
    types={'.monpatch':'application/json','.json':'application/json','.wav':'audio/wav',
           '.svg':'image/svg+xml','.png':'image/png','.csv':'text/csv','.html':'text/html'}
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in types: raise ValueError('Format d’export inconnu.')
    data=file.file.read(32_000_001)
    if len(data)>32_000_000: raise ValueError('Export limité à 32 Mo.')
    key=uuid4().hex; name='resonant'+suffix
    with lock:
        downloads[key]=(name,types[suffix],data,user["id"])
        while len(downloads)>8 or sum(len(d[2]) for d in downloads.values())>64_000_000:
            downloads.popitem(last=False)
    return {'url':f'/api/exports/{key}','name':name}

@api_router.get('/api/exports/{key}',dependencies=[Depends(require_account)])
def download_export(key:str,user:dict=Depends(require_api_user)):
    with lock:
        if key not in downloads or downloads[key][3]!=user["id"]: raise HTTPException(404,'Export expiré ; préparez à nouveau le fichier.')
        name,media_type,data,_=downloads[key]
    return Response(data,media_type=media_type,headers={
        'Content-Disposition':f'attachment; filename="{name}"',
        'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

@api_router.post('/api/optimize',status_code=202)
def optimize(req:OptimizeRequest,request:Request,user:dict=Depends(require_api_user)):
    return submit('optimize',req,request,user)

@api_router.post('/api/compute/input')
def local_compute_input(body:dict,user:dict=Depends(require_api_user)):
    from .compute import MODELS,validate_input
    kind=body.get('kind');data=body.get('request')
    if not isinstance(kind,str) or kind not in MODELS or not isinstance(data,dict):raise ValueError('Demande de calcul local invalide.')
    r=MODELS[kind].model_validate(data)
    if kind=='generate':
        rec=get_recording(r.audio_id,user['id']);fs=rec.sample_rate if rec.sample_rate in (44100,48000,96000) else 44100
        if r.start+r.duration>len(rec.samples)/rec.sample_rate+1/fs:raise ValueError('Sélection hors du WAV.')
        x=excerpt(rec,r.start,r.duration,fs)
    else:
        fs=r.patch.sample_rate;x=target_audio(r,user['id'])
        if x is None:raise ValueError('Référence requise.')
    validate_input(kind,data,x,fs)
    return Response(np.asarray(x,dtype='<f8').tobytes(),media_type='application/octet-stream',headers={'X-Sample-Rate':str(fs),'Cache-Control':'no-store'})

@api_router.get('/api/compute/config')
def local_compute_config(user:dict=Depends(require_api_user)):
    data=runtime_manifest()
    if not data or not data.get('ready'):return {'available':False}
    required={'numerical.zip','pyodide.mjs','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json'}
    if not required<=set(data['files']):return {'available':False}
    for name,metadata in data.get('files',{}).items():
        path=runtime_path(name)
        if path is None or path.stat().st_size!=metadata.get('bytes'):return {'available':False}
    if not all(k in data for k in ('runtime_version','algorithm_version','source_sha256','download_bytes')):return {'available':False}
    return {'available':data.get('ready',False),'runtime_version':data['runtime_version'],'algorithm_version':data['algorithm_version'],'source_sha256':data['source_sha256'],'download_bytes':data['download_bytes']}

@api_router.get('/api/compute/status')
def compute_status(user:dict=Depends(require_api_user)):
    return job_store.worker_status()

@api_router.get('/api/jobs')
def recent_jobs(user:dict=Depends(require_api_user)):
    job_store.maintain();return job_store.recent(user['id'])

@api_router.get('/api/jobs/{key}')
def job(key:str,user:dict=Depends(require_api_user)):
    job_store.maintain();return job_store.read(key,user['id'])

@api_router.get('/api/jobs/{key}/result')
def job_result(key:str,user:dict=Depends(require_api_user)):
    result=job_store.read(key,user['id'],True)
    if result['status']!='succeeded':raise HTTPException(409,'Le résultat n’est pas disponible.')
    return result['result']

@api_router.post('/api/jobs/{key}/cancel')
def cancel_job(key:str,user:dict=Depends(require_api_user)):
    return job_store.cancel(key,user['id'])

@api_router.get('/api/me')
def me(request:Request,user:dict=Depends(require_api_user)):
    token=request.cookies.get('visitor_token','') if user.get('guest') else request.cookies.get('access_token','')
    return {**user,'csrf_token':csrf_token(token) if token else None}

# Inclusion des routes protégées de l'API
app.include_router(api_router)

# Chargement du dossier statique (Frontend React/Vue)
COMPUTE_RUNTIME=Path(__file__).resolve().parents[2]/'.local'/'compute-runtime'
def csv_cell(value):
    text=str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text

def runtime_path(filename):
    if not isinstance(filename,str) or '/' in filename or '\\' in filename:return None
    if filename not in ('manifest.json','numerical.zip','pyodide.mjs','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json') and not filename.endswith('.whl'):return None
    path=COMPUTE_RUNTIME/filename
    if path.is_symlink() or not path.is_file() or path.resolve().parent!=COMPUTE_RUNTIME.resolve():return None
    return path

def runtime_manifest():
    import json
    path=runtime_path('manifest.json')
    if path is None:return None
    try:
        data=json.loads(path.read_text())
        if not isinstance(data,dict) or not isinstance(data.get('files'),dict):return None
        if not all(isinstance(v,dict) for v in data['files'].values()):return None
        return data
    except (OSError,ValueError):return None

# Never mount the directory: an accidentally copied secret must not become public.
@app.api_route('/compute-runtime/{filename}',methods=['GET','HEAD'],include_in_schema=False)
def compute_runtime_file(filename:str):
    data=runtime_manifest()
    if data is None:raise HTTPException(404,'Runtime absent.')
    if filename!='manifest.json' and filename not in data.get('files',{}):raise HTTPException(404,'Ressource absente.')
    if filename!='manifest.json' and filename not in ('numerical.zip','pyodide.mjs','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json') and not filename.endswith('.whl'):
        raise HTTPException(404,'Ressource absente.')
    path=runtime_path(filename)
    if path is None:raise HTTPException(404,'Ressource absente.')
    return FileResponse(path,headers={'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'})
DIST=Path(__file__).resolve().parents[2]/'frontend'/'dist'
if DIST.exists():
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/favicon.svg')
    def favicon(): return FileResponse(DIST/'favicon.svg')


# ===================================================================
# GESTION DES PAGES ET AUTHENTIFICATION
# ===================================================================

@app.on_event("startup")
def startup_event():
    init_db();job_store.init_jobs();job_store.maintain()

from .pages import auth_form,signed_out
import hmac
import re
import secrets

STATIC=Path(__file__).resolve().parents[1]/'static'

@app.get('/auth.css')
def auth_css():return FileResponse(STATIC/'auth.css')

@app.get('/auth.js')
def auth_js():return FileResponse(STATIC/'auth.js')

def secure_cookie(request):
    # Production is HTTPS; loopback development can use plain HTTP.
    return request.url.hostname not in ('127.0.0.1','localhost','::1') or request.url.scheme=='https'

def form_response(request,mode,error='',username='',email='',status=200):
    nonce=secrets.token_urlsafe(32)
    response=HTMLResponse(auth_form(mode,nonce,error,username,email,bool(request.query_params.get('registered')),request.query_params.get('embed')=='1'),status_code=status,headers={'Cache-Control':'no-store'})
    response.set_cookie('resonant_form',nonce,httponly=True,secure=secure_cookie(request),samesite='strict',max_age=1800)
    return response

def check_form(request,csrf):
    check_origin(request)
    nonce=request.cookies.get('resonant_form','')
    if not nonce or not valid_csrf(csrf,nonce):raise HTTPException(403,'Formulaire expiré. Rechargez la page.')

def valid_email(email):
    return len(email)<=254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) is not None

@app.get('/')
def home():return RedirectResponse('/mon-lab/',status_code=303)

@app.get('/login',response_class=HTMLResponse)
def login_page(request:Request):
    if get_current_user(request):return RedirectResponse('/auth/complete' if request.query_params.get('embed')=='1' else '/mon-lab/',status_code=303)
    return form_response(request,'login')

@app.post('/login')
def login(request:Request,username:str=Form(...),password:str=Form(...),csrf:str=Form(...)):
    check_form(request,csrf)
    rate_limit(request,'login-ip',limit=40)
    rate_limit(request,'login-user',subject=username[:64].casefold(),limit=10)
    conn=get_db()
    try:user=conn.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
    finally:conn.close()
    from .auth import dummy_password_hash
    matched=verify_password(password,user['hashed_password'] if user else dummy_password_hash())
    if not user or not matched:
        return form_response(request,'login','Pseudo ou mot de passe incorrect.',username=username[:64],status=400)
    old_owner=claim_visitor(request,user['id'])
    if old_owner is not None:
        with lock:
            for key,(owner,record) in list(recordings.items()):
                if owner==old_owner:recordings[key]=(user['id'],record)
            for key,(owner,data) in list(renders.items()):
                if owner==old_owner:renders[key]=(user['id'],data)
            for key,(name,media,data,owner) in list(downloads.items()):
                if owner==old_owner:downloads[key]=(name,media,data,user['id'])
    response=RedirectResponse('/auth/complete' if request.query_params.get('embed')=='1' else '/mon-lab/',status_code=303)
    response.set_cookie('access_token',create_access_token({'sub':user['username']}),httponly=True,secure=secure_cookie(request),samesite='lax',max_age=86400)
    response.delete_cookie('resonant_form');response.delete_cookie('visitor_token');return response

@app.get('/register',response_class=HTMLResponse)
def register_page(request:Request):
    if get_current_user(request):return RedirectResponse('/auth/complete' if request.query_params.get('embed')=='1' else '/mon-lab/',status_code=303)
    return form_response(request,'register')

@app.post('/register')
def register(request:Request,username:str=Form(...),email:str=Form(...),password:str=Form(...),csrf:str=Form(...)):
    check_form(request,csrf);username=username.strip();email=email.strip()
    rate_limit(request,'register-ip',limit=5,window=3600)
    error=None
    if not re.fullmatch(r'[\w .-]{3,64}',username):error='Pseudo : 3 à 64 lettres, chiffres, espaces, points ou tirets.'
    elif not valid_email(email):error='Adresse e-mail invalide.'
    if error:return form_response(request,'register',error,username,email,422)
    try:hashed=hash_password(password)
    except ValueError as exc:return form_response(request,'register',str(exc),username,email,422)
    conn=get_db()
    try:
        conn.execute('INSERT INTO users(username,email,hashed_password) VALUES (?,?,?)',(username,email,hashed));conn.commit()
    except sqlite3.IntegrityError:
        return form_response(request,'register','Pseudo ou e-mail déjà utilisé.',username,email,400)
    finally:conn.close()
    return RedirectResponse('/login?registered=true'+('&embed=1' if request.query_params.get('embed')=='1' else ''),status_code=303)

@app.get('/auth/complete',response_class=HTMLResponse)
def auth_complete(user:dict=Depends(require_user)):
    return HTMLResponse('<!doctype html><html lang="fr"><meta charset="utf-8"><link rel="stylesheet" href="/auth.css"><body class="auth-embedded"><main class="auth-shell"><section class="auth-card"><h2>Connexion réussie</h2><p>Votre laboratoire va retrouver les options d’export.</p></section></main></body></html>',headers={'Cache-Control':'no-store'})

@app.get('/logout')
def logout_confirmation():return RedirectResponse('/mon-lab/',status_code=303)

@app.post('/api/logout',dependencies=[Depends(require_account)])
def logout(request:Request,user:dict=Depends(require_api_user)):
    revoke_session(request);response=JSONResponse({'ok':True});response.delete_cookie('access_token');response.headers['Cache-Control']='no-store';return response

@app.get('/dashboard')
def dashboard():return RedirectResponse('/mon-lab/',status_code=303)

@app.get('/mon-lab')
def mon_lab_redirect():return RedirectResponse('/mon-lab/',status_code=308)

@app.get('/mon-lab/',response_class=HTMLResponse)
def mon_lab(request:Request):
    if (DIST/'index.html').exists():
        response=FileResponse(DIST/'index.html',headers={'Cache-Control':'no-store'})
        if not get_current_user(request) and not get_visitor(request):
            rate_limit(request,'visitor-ip',limit=40,window=3600)
            response.set_cookie('visitor_token',create_visitor(),httponly=True,secure=secure_cookie(request),samesite='lax',max_age=86400)
        return response
    return HTMLResponse('Interface non compilée. Exécutez le build frontend.',status_code=503)

class AccountUpdate(BaseModel):
    email:str
    current_password:str

@app.post('/api/account',dependencies=[Depends(require_account)])
def update_account(req:AccountUpdate,request:Request,user:dict=Depends(require_api_user)):
    rate_limit(request,'account-password',subject=str(user['id']),limit=10)
    email=req.email.strip()
    if not valid_email(email):raise HTTPException(422,'Adresse e-mail invalide.')
    conn=get_db()
    try:
        row=conn.execute('SELECT hashed_password FROM users WHERE id=?',(user['id'],)).fetchone()
        if not row or not verify_password(req.current_password,row['hashed_password']):raise HTTPException(403,'Mot de passe actuel incorrect.')
        try:conn.execute('UPDATE users SET email=? WHERE id=?',(email,user['id']));conn.commit()
        except sqlite3.IntegrityError:raise HTTPException(409,'Cette adresse est déjà utilisée.')
    finally:conn.close()
    return {'id':user['id'],'username':user['username'],'email':email}
