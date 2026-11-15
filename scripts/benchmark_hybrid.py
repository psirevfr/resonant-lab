"""Local high-band search benchmark; no private waveforms written to the report."""
import argparse,json,time,hashlib,platform,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import numpy as np,scipy
from lab.schema import Patch,Weights
from lab.audio import read_wav,excerpt
from lab.analysis import pitch
from lab.graph import render
from lab.hybrid import high_band_candidates
from lab.metrics import Objective
from lab.texture import band_errors
from lab.instrument import physical_count
from lab.compact import tidy,simplify
parser=argparse.ArgumentParser();parser.add_argument('--patch',required=True);parser.add_argument('--wav',required=True);parser.add_argument('--output',required=True);parser.add_argument('--selected-patch',help='Fichier local facultatif du modèle retenu (ne pas le versionner avec des données privées)');parser.add_argument('--simplify',action='store_true');parser.add_argument('--no-shaping',action='store_true',help='Désactiver seulement la recherche non linéaire pour cette recette, sans changer le défaut du site');args=parser.parse_args()
p=tidy(Patch.model_validate_json(Path(args.patch).read_text()))
x=excerpt(read_wav(Path(args.wav).read_bytes(),'benchmark.wav'),0,p.duration,p.sample_rate)
obj=Objective(x,p.sample_rate,Weights());f0=pitch(x,p.sample_rate)[0]
def metrics(q):
 y=render(q)
 return {'name':q.name,'blocks':physical_count(q),'modes':sum(n.type=='modal' for n in q.nodes),'errors':obj.components(y),'bands':band_errors(x,y,p.sample_rate)}
ref=metrics(p)
report={'environment':platform.platform(),'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'scope':'Recherche des branches hybrides seule, hors génération/chargement, sauf section simplify si demandée.','duration':p.duration,'fs':p.sample_rate,'input_sha256':hashlib.sha256(x.tobytes()).hexdigest(),'patch_sha256':hashlib.sha256(p.model_dump_json().encode()).hexdigest(),'reference':ref,'runs':[]}
for i in range(3):
 start=time.perf_counter();qs=high_band_candidates(p,x,obj,f0);seconds=time.perf_counter()-start
 rows=[metrics(q) for q in qs]
 for c in rows:
  c['strict']=all(c['errors'][k]<=ref['errors'][k]+1e-12 for k in ref['errors']) and all(c['bands'][k]<=ref['bands'][k]+1e-12 for k in ref['bands'])
 report['runs'].append({'seconds':seconds,'candidates':rows})
 print('hybrid',i,seconds,flush=True)
 Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
if args.simplify:
 start=time.perf_counter();r=simplify(p,x,Weights(),tolerance=.2,test_shaping=not args.no_shaping,protect_texture=True,test_noise=True)
 report['simplify']={'seconds':time.perf_counter()-start,'settings':{'tolerance':.2,'test_shaping':not args.no_shaping,'protect_texture':True,'test_noise':True},'selected':metrics(Patch.model_validate(r['patch'])),'limit':r['limit'],'candidates':[{'name':c['patch']['name'],'modules':c['modules'],'errors':c['errors'],'bands':c['bands'],'within_tolerance':c['within_tolerance'],'rejection_reasons':c['rejection_reasons']} for c in r['candidates'] if c['patch']['name'].startswith('Hybride')]}
 if args.selected_patch:Path(args.selected_patch).write_text(Patch.model_validate(r['patch']).model_dump_json(indent=2))
 print('simplify',report['simplify']['seconds'],report['simplify']['selected']['blocks'],report['simplify']['selected']['errors']['total'],flush=True)
 Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
