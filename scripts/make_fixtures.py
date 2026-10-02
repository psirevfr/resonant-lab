"""Generate known WAV fixtures without downloading any audio."""
from pathlib import Path
import numpy as np
from scipy import signal
from lab.audio import wav_bytes
from lab.blocks import coefficients,parameters
from lab.schema import Patch,Block,Edge

out=Path(__file__).resolve().parents[1]/'examples'
out.mkdir(exist_ok=True)
fs=44100; t=np.arange(fs*2)/fs
fixtures={'sine-440':.5*np.sin(2*np.pi*440*t),'harmonics-440':sum(.4/n*np.sin(2*np.pi*440*n*t) for n in (1,2,3))}
env=(1-np.exp(-t/.005))*np.exp(-t/.8)
b,a=coefficients('lowpass',parameters('lowpass',{'fc':1200,'q':.70710678},fs),fs)
fixtures['harmonics-filter-envelope']=signal.lfilter(b,a,fixtures['harmonics-440'])*env
fixtures['inharmonic-modal']=sum(.4/n*np.exp(-t/(1.5/n**.3))*(1-np.exp(-t/.003))*np.sin(2*np.pi*n*220*np.sqrt(1+.00015*n*n)*t) for n in range(1,7))
for name,x in fixtures.items(): (out/(name+'.wav')).write_bytes(wav_bytes(x,fs))
p=Patch(name='Banc LTI : passe-bas',duration=2,nodes=[Block(id='in',type='input',label='Entrée impulsionnelle',position={'x':0,'y':0}),Block(id='filter',type='lowpass',label='Passe-bas 1200 Hz',parameters={'fc':1200,'q':.70710678},position={'x':260,'y':0}),Block(id='out',type='output',label='Sortie',position={'x':520,'y':0})],edges=[Edge(id='in-filter',source='in',target='filter'),Edge(id='filter-out',source='filter',target='out')])
(out/'banc-lti.monpatch').write_text(p.model_dump_json(indent=2))
print(f'{len(fixtures)} WAV et un modèle LTI écrits dans {out}')
