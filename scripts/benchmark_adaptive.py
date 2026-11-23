"""Compare the identical baseline with/without the optional local trial."""
import argparse
import json
from pathlib import Path
from statistics import median

import numpy as np

from lab.audio import excerpt, read_wav
from lab.blocks import adsr_envelope
from lab.compute import AnalysisCache, compute


def fixtures(fs):
    def time(seconds):
        return np.arange(round(seconds*fs))/fs
    t=time(.22)
    yield 'percussion synthétique', .15*np.exp(-t/.028)*np.random.default_rng(53).normal(size=t.size)+.2*np.exp(-t/.05)*np.sin(2*np.pi*180*t)
    t=time(.8)
    yield 'piano synthétique', .4*(-np.expm1(-t/.005))*np.exp(-t/.19)*(np.sin(2*np.pi*440*t)+.15*np.sin(2*np.pi*881*t))
    t=time(1.5)
    for name,attack,partial in [('archet synthétique',.11,.28),('cuivre synthétique',.07,.45)]:
        tone=np.sin(2*np.pi*330*t)+partial*np.sin(2*np.pi*660*t+.13)
        yield name, .3*adsr_envelope(t,attack,.19,.73,1.13,.3,fs)*tone


def benchmark(name, x, fs):
    req={'audio_id':'benchmark','duration':len(x)/fs,'max_partials':4,
         'refine_modes':False,'include_impact':False,'detailed':False}
    cache=AnalysisCache()
    cold=[];warm=[]
    for _ in range(3):
        cold.append(compute('analyze',req,x,fs,cache=AnalysisCache())['compute_metrics']['algorithm_ms'])
        compute('analyze',req,x,fs,cache=cache)
        warm.append(compute('analyze',req,x.copy(),fs,cache=cache)['compute_metrics']['algorithm_ms'])
    plain=compute('generate',req,x,fs,cache=cache)
    trial=compute('generate',req,x,fs,cache=cache,learning={'version':1})
    return {'source':name, 'seconds':len(x)/fs, 'analysis_ms':{'cold':median(cold),'cached':median(warm)},
            'generation_ms':{'plain':plain['compute_metrics']['algorithm_ms'],
                             'trial':trial['compute_metrics']['algorithm_ms']},
            'error':{key:value['candidates'][0]['errors']['total'] for key,value in [('plain',plain),('trial',trial)]},
            'modules':{key:value['candidates'][0]['modules'] for key,value in [('plain',plain),('trial',trial)]},
            'profile':trial['learning']['profile'],'strategy':trial['learning']['strategy'],
            'accepted':trial['learning']['accepted']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--piano',type=Path,help='Facultatif, WAV local. Seules les mesures sont affichées.')
    args=parser.parse_args()
    fs=44100
    clips=list(fixtures(fs))
    if args.piano:
        rec=read_wav(args.piano.read_bytes(),'WAV piano local')
        level=np.max(np.abs(rec.samples),axis=1)
        onset=int(np.argmax(level>=.08*level.max()))
        clips.append(('piano local',excerpt(rec,max(0.,onset/rec.sample_rate-.02),.8,fs)))
    for name,x in clips:
        print(json.dumps(benchmark(name,x,fs),ensure_ascii=False,allow_nan=False),flush=True)
