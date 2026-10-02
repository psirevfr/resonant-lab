"""Dimensionless relative errors on identically aligned, unnormalized signals."""
import numpy as np
from .audio import envelope, stft
from .schema import Weights

class Objective:
    def __init__(self,x,fs,weights: Weights):
        self.x=np.asarray(x); self.fs=fs; self.weights=weights.model_dump()
        self.fft=abs(np.fft.rfft(x)); self.env=envelope(x,fs)
        self.spec=stft(x,fs,nfft=1024,max_frames=160)[2]
        nonzero=np.flatnonzero(self.env>self.env.max()*.035)
        onset=int(nonzero[0]) if len(nonzero) else 0
        self.attack_slice=slice(max(0,onset-round(.005*fs)),min(len(x),onset+round(.12*fs)))
        self.attack_specs=[stft(x[self.attack_slice],fs,nfft=n,max_frames=100)[2] for n in (256,1024)]
    @staticmethod
    def relative(a,b): return float(np.linalg.norm(a-b)/max(np.linalg.norm(a),1e-12))
    def components(self,y):
        if len(y)!=len(self.x): raise ValueError('Les signaux comparés doivent avoir la même longueur.')
        terms={'time':self.relative(self.x,y),'spectral':self.relative(self.fft,abs(np.fft.rfft(y))),'spectrogram':self.relative(self.spec,stft(y,self.fs,nfft=1024,max_frames=160)[2]),'envelope':self.relative(self.env,envelope(y,self.fs))}
        terms['attack']=float(np.mean([self.relative(a,stft(y[self.attack_slice],self.fs,nfft=n,max_frames=100)[2]) for a,n in zip(self.attack_specs,(256,1024))]))
        terms['total']=sum(self.weights[k]*terms[k] for k in self.weights)/sum(self.weights.values())
        return terms
    def __call__(self,y): return self.components(y)['total']
