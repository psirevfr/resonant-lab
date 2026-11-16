"""Reproducible group search only; no private audio samples in the report.

Optional piano requires its already generated reference patch, same duration/fs.
First and subsequent runs are separated; this is not an end-to-end benchmark.
"""
import argparse,json,platform,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/tests')]
import numpy as np,scipy
from test_harmonic_groups import fixture
from lab.schema import Patch,Weights
from lab.graph import render
from lab.metrics import Objective
from lab.texture import band_errors
from lab.instrument import physical_count
from lab.harmonic_groups import harmonic_candidates
from lab.audio import read_wav,excerpt

parser=argparse.ArgumentParser()
parser.add_argument('--patch');parser.add_argument('--wav');parser.add_argument('--output',required=True)
args=parser.parse_args()
if bool(args.patch)!=bool(args.wav):parser.error('--patch et --wav doivent être fournis ensemble')
inputs=[('synthetic',*fixture())]
if args.patch:
    p=Patch.model_validate_json(Path(args.patch).read_text())
    x=excerpt(read_wav(Path(args.wav).read_bytes(),'benchmark.wav'),0,p.duration,p.sample_rate)
    inputs.append(('piano',p,x))
report={'environment':platform.platform(),'processor':platform.processor(),'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'scope':'Recherche du groupe et ajustement uniquement, sans chargement, génération ni rendu audio navigateur. Trois répétitions, aucun cache de résultat.','cases':[]}
for name,p,x in inputs:
    obj=Objective(x,p.sample_rate,Weights())
    def metrics(q):
        y=render(q)
        return {'blocks':physical_count(q),'sources':sum(n.type in ('modal','oscillator','noise','impulse') for n in q.nodes),'errors':obj.components(y),'bands':band_errors(x,y,p.sample_rate),'max_sample_error':float(np.max(abs(x-y)))}
    ref=metrics(p);case={'name':name,'duration':p.duration,'sample_rate':p.sample_rate,'reference':ref,'runs':[]}
    for i in range(3):
        start=time.perf_counter();proposals=harmonic_candidates(p,x,Weights());seconds=time.perf_counter()-start
        rows=[]
        for q in proposals:
            c=metrics(q)
            c['generation_strict']=all(c['errors'][k]<=v+1e-12 for k,v in ref['errors'].items()) and all(c['bands'][k]<=v+1e-12 for k,v in ref['bands'].items())
            c['simplification_budget_20pct']=c['errors']['total']<=ref['errors']['total']*1.2+1e-12 and c['errors']['attack']<=max(ref['errors']['attack']*1.2,.01)+1e-12 and all(c['bands'][k]<=max(v*1.2,.03)+1e-12 for k,v in ref['bands'].items())
            rows.append(c)
        case['runs'].append({'index':i,'seconds':seconds,'candidates':rows})
    report['cases'].append(case)
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps([{'case':c['name'],'seconds':[r['seconds'] for r in c['runs']],'proposals':len(c['runs'][0]['candidates'])} for c in report['cases']]))
