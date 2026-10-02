"""Reproducible comparison on supplied WAVs; never writes over a source recording."""
from pathlib import Path
import json
from time import monotonic
from threading import Event
from lab.audio import read_wav,excerpt,wav_bytes
from lab.identify import generate
from lab.schema import Patch,OptimizeRequest
from lab.graph import render
from lab.optimization import run_optimization

root=Path(__file__).resolve().parents[1]
results=[]
for name in ('piano.wav','piano2.wav'):
    path=root.parent/name
    if not path.exists():continue
    rec=read_wav(path.read_bytes(),name);fs=rec.sample_rate
    x=excerpt(rec,0,3);clock=monotonic()
    identified=generate(x,fs)
    chosen=Patch.model_validate(identified['patch'])
    optimized=run_optimization(OptimizeRequest(patch=chosen,audio_id='validation',max_iterations=15),x,lambda _:None,Event())
    final=Patch.model_validate(optimized['patch'])
    stem=name.removesuffix('.wav')
    (root/'examples'/f'{stem}-impact.monpatch').write_text(final.model_dump_json(indent=2))
    (root/'examples'/f'{stem}-impact.wav').write_bytes(wav_bytes(render(final),fs))
    row={'file':name,'selection_start':0,'duration':3,'fs':fs,'weights':{'time':.1,'spectral':.25,'spectrogram':.5,'envelope':.15,'attack':.25},'complexity_penalty':.0001,'f0':identified['analysis']['f0'],'B':identified['analysis']['inharmonicity'],'candidates':[{'name':c['patch']['name'],'errors':c['errors'],'score':c['score'],'blocks':len(c['patch']['nodes'])} for c in identified['candidates']],'selected':chosen.name,'optimization':{k:v for k,v in optimized.items() if k not in ('patch','history')},'seconds':round(monotonic()-clock,3)}
    results.append(row);print(json.dumps(row),flush=True)
(root/'docs'/'piano-impact-validation.json').write_text(json.dumps(results,indent=2))
