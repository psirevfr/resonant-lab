"""Local generation benchmark; reports metrics and hashes, never audio samples."""
import argparse,sys,json,time,platform,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',default='backend');p.add_argument('--wav',default='../piano.wav');p.add_argument('--duration',type=float,default=3);p.add_argument('--repetitions',type=int,default=3);p.add_argument('--output',required=True);args=p.parse_args()
if not 1<=args.repetitions<=5:p.error('1 à 5 répétitions')
sys.path.insert(0,str(Path(args.source_root).resolve()))
import numpy as np,scipy
from lab.audio import read_wav,excerpt
from lab.identify import generate
from lab.schema import Patch,Weights
from lab.instrument import physical_count
x=excerpt(read_wav(Path(args.wav).read_bytes(),'piano.wav'),0,args.duration,44100)
report={'platform':platform.platform(),'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'input_sha256':hashlib.sha256(x.tobytes()).hexdigest(),'duration':args.duration,'sample_rate':44100,'max_partials':24,'detailed':True,'include_impact':True,'refine_modes':True,'penalty':.0001,'weights':Weights().model_dump(),'runs':[]}
for i in range(args.repetitions):
 start=time.perf_counter();r=generate(x,44100,24,.0001,Weights(),True,True,True);elapsed=time.perf_counter()-start
 q=Patch.model_validate(r['patch']);c=next(c for c in r['candidates'] if c['patch']==r['patch'])
 entry={'seconds':elapsed,'blocks':physical_count(q),'error':c['errors'],'types':[n.type for n in q.nodes],'name':q.name,'candidates':[{'name':c['patch']['name'],'blocks':physical_count(Patch.model_validate(c['patch'])),'errors':c['errors'],'rejection_reasons':c.get('rejection_reasons',[])} for c in r['candidates']]}
 report['runs'].append(entry);print(i,elapsed,entry['blocks'],entry['error']['total'],flush=True)
 Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
