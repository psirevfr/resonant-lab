#!/usr/bin/env python3
"""Reproducible, local-only topology benchmark. No database or API calls.

Compare two source directories with the same Python environment and fixtures.
Optional piano files stay local; output contains hashes/metrics, never samples.
"""
import argparse,hashlib,json,platform,sys,time
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[1]/'backend')
parser.add_argument('--piano-directory',type=Path)
parser.add_argument('--repetitions',type=int,default=3)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if not 1<=args.repetitions<=10:parser.error('repetitions: 1 à 10')
sys.path.insert(0,str(args.source_root.resolve()))
import numpy as np,scipy
from lab.schema import Patch,Block,Weights
from lab.graph import render
from lab.blocks import process
from lab.identify import link
from lab.compact import simplify
from lab.instrument import physical_count
root=Path(__file__).resolve().parents[1]
fs=44100;duration=.25;n=round(fs*duration);t=np.arange(n)/fs
carrier=.4*np.sin(2*np.pi*300*t)
shaped=process('asymmetric_saturation',{'drive':4,'bias':0,'mix':1,'level':.3},[carrier],fs,n)
shaped=process('lowpass1',{'fc':2400},[shaped],fs,n)
env=np.exp(-t/.3)*-np.expm1(-t/.003);x=shaped*env
D=np.array([env*f(2*np.pi*300*h*t) for h in range(1,9) for f in (np.sin,np.cos)]).T
z=np.linalg.lstsq(D,x,rcond=None)[0]
modes=[Block(id=f'm{i}',type='modal',parameters={'frequency':300*(i+1),'amplitude':float(np.hypot(*z[2*i:2*i+2])),'phase':float(np.arctan2(z[2*i+1],z[2*i])),'tau':.3,'attack':.003,'onset':0}) for i in range(8)]
p=Patch(duration=duration,nodes=modes+[Block(id='s',type='sum'),Block(id='o',type='output')],edges=[link(m.id,'s') for m in modes]+[link('s','o')])
cases=[('saturation-enveloppe-connue',p,x)]
exact=p.model_copy(deep=True)
for i,m in enumerate(exact.nodes[:-2]):m.parameters.update(amplitude=.3/(i+1),phase=0)
cases.append(('banque-harmonique-exacte',exact,render(exact)))
if args.piano_directory:
    from lab.audio import read_wav,excerpt
    for name in ('piano','piano2'):
        model=Patch.model_validate_json((root/'examples'/f'{name}-global.monpatch').read_text());model.duration=.35
        samples=excerpt(read_wav((args.piano_directory/f'{name}.wav').read_bytes(),name+'.wav'),0,model.duration,model.sample_rate)
        cases.append((name,model,samples))
report={'platform':platform.platform(),'machine':platform.machine(),'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'repetitions':args.repetitions,'weights':Weights().model_dump(),'tolerance':.2,'protect_texture':True,'test_shaping':True,'test_noise':True,'cases':{}}
for name,model,samples in cases:
    runs=[]
    for repeat in range(args.repetitions):
        start=time.perf_counter();r=simplify(model,samples,Weights(),tolerance=.2,test_shaping=True,protect_texture=True)
        runs.append(time.perf_counter()-start)
    final=Patch.model_validate(r['patch'])
    render_seconds=[]
    for _ in range(5):
        start=time.perf_counter();render(final);render_seconds.append(time.perf_counter()-start)
    report['cases'][name]={'duration':model.duration,'sample_rate':model.sample_rate,'input_sha256':hashlib.sha256(samples.tobytes()).hexdigest(),'model_sha256':hashlib.sha256(model.model_dump_json().encode()).hexdigest(),'seconds':runs,'render_seconds':render_seconds,'initial_blocks':physical_count(model),'final_blocks':r['final_blocks'],'generators':r['final_generators'],'baseline':r['baseline'],'error':r['final'],'limit':r['limit'],'bands':r['final_bands'],'patch_types':[b.type for b in final.nodes],'accepted':r['final']<=r['limit']}
    print(name,json.dumps(report['cases'][name]),flush=True)
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
