"""Descriptive monophonic analysis; no claim of unique physical identification."""
import numpy as np
from scipy import signal, optimize
from .audio import envelope, resample, stft
from .blocks import exponential

def pitch(x,fs):
    y=resample(x,fs,11025); y=y[:min(len(y),11025)]
    y=y-y.mean()
    ac=signal.correlate(y,y,mode='full',method='fft')[len(y)-1:]
    ac=ac/max(ac[0],1e-20)
    lo=5; hi=min(len(ac)-2,551)
    peaks,_=signal.find_peaks(ac[lo:hi]); peaks=peaks+lo
    if not len(peaks): return None,ac[:hi],11025
    best=ac[peaks].max()
    valid=peaks[ac[peaks]>=max(.15,.88*best)]
    if best<.15 or not len(valid): return None,ac[:hi],11025
    k=int(valid[0]); a,b,c=ac[k-1:k+2]; shift=.5*(a-c)/(a-2*b+c) if abs(a-2*b+c)>1e-15 else 0
    return float(11025/(k+shift)),ac[:hi],11025

def analyze(x: np.ndarray, fs: int, max_partials: int=12):
    if np.sqrt(np.mean(x*x))<1e-7: raise ValueError('Signal silencieux : identification impossible.')
    t=np.arange(len(x))/fs; env=envelope(x,fs)
    onset_index=int(np.flatnonzero(env>env.max()*.035)[0]); onset=onset_index/fs
    peak_index=int(np.argmax(env)); attack=max(0.0001,min(.1,(peak_index-onset_index)/fs/3))
    active=x[onset_index:]
    f0,ac,acfs=pitch(active,fs)
    nfft=2**int(np.ceil(np.log2(min(len(active),fs*4)*4)))
    segment=active[:fs*4]; win=signal.windows.hann(len(segment),sym=False)
    mag=abs(np.fft.rfft(segment*win,nfft)); freqs=np.fft.rfftfreq(nfft,1/fs)
    peaks,props=signal.find_peaks(mag,prominence=mag.max()*.008,distance=max(1,int(12/(fs/nfft))))
    peaks=peaks[(freqs[peaks]>=20)&(freqs[peaks]<min(16000,fs*.47))]
    peaks=sorted(peaks,key=lambda k:mag[k],reverse=True)[:max_partials]
    if not peaks: raise ValueError('Aucun partiel résolu : utiliser une sélection plus longue.')
    sf,st,sm=stft(active,fs,nfft=min(8192,len(active)),max_frames=100)
    partials=[]
    # Project onto damped sine/cosine bases; refine each frequency locally.
    fit_n=min(len(active),fs*3); ft=np.arange(fit_n)/fs; target=active[:fit_n]
    for k in sorted(peaks):
        lm=np.log(np.maximum(mag[k-1:k+2],1e-30)); denom=lm[0]-2*lm[1]+lm[2]
        delta=.5*(lm[0]-lm[2])/denom if abs(denom)>1e-15 else 0
        freq=(k+np.clip(delta,-.5,.5))*fs/nfft
        row=int(np.argmin(abs(sf-freq))); track=sm[max(0,row-1):row+2].max(axis=0)
        valid=(track>track.max()*.04)&(st>max(.04,attack*3))
        if valid.sum()>3:
            slope,intercept=np.polyfit(st[valid],np.log(np.maximum(track[valid],1e-15)),1)
            tau=float(np.clip(-1/slope if slope < -1/30 else 30,.02,30))
            predicted=intercept+slope*st[valid]
            fit_r2=float(1-np.sum((np.log(track[valid])-predicted)**2)/max(np.sum((np.log(track[valid])-np.log(track[valid]).mean())**2),1e-15))
        else: tau=1.; fit_r2=None
        e=exponential(ft,attack,tau)
        def project(f,full=False):
            s=e*np.sin(2*np.pi*f*ft); c=e*np.cos(2*np.pi*f*ft)
            gram=np.array([[s@s,s@c],[s@c,c@c]])
            co=np.linalg.lstsq(gram,np.array([s@target,c@target]),rcond=None)[0]
            return (co,s,c) if full else -float(co@np.array([s@target,c@target]))
        width=max(.5,fs/nfft*2)
        result=optimize.minimize_scalar(project,bounds=(max(1,freq-width),min(fs*.49,freq+width)),method='bounded',options={'xatol':.001,'maxiter':22})
        freq=float(result.x); co,_,_=project(freq,True)
        partials.append({'frequency':freq,'amplitude':float(np.clip(np.hypot(*co),0,4)),'phase':float(np.arctan2(co[1],co[0])),'tau':tau,'decay_r2':fit_r2})
    # Assign partial indices only when compatible with an approximately harmonic series.
    if f0:
        for part in partials: part['harmonic']=max(1,round(part['frequency']/f0))
        first=[p for p in partials if p['harmonic']==1 and abs(p['frequency']/f0-1)<.08]
        if first: f0=max(first,key=lambda p:p['amplitude'])['frequency']
    inharmonicity=None
    if f0 and len(partials)>=4:
        matched=[p for p in partials if abs(p['frequency']/(max(1,round(p['frequency']/f0))*f0)-1)<.04]
        ns=np.array([max(1,round(p['frequency']/f0)) for p in matched]); ys=np.array([p['frequency'] for p in matched])
        if len(set(ns))>=4:
            fit=optimize.least_squares(lambda v:(ns*v[0]*np.sqrt(1+v[1]*ns**2)-ys),[f0,1e-5],bounds=([f0*.94,0],[f0*1.02,.01]))
            rmse=float(np.sqrt(np.mean(fit.fun**2))); base_rmse=float(np.sqrt(np.mean((ns*(ns@ys)/(ns@ns)-ys)**2)))
            if fit.x[1]>1e-7 and rmse<max(1.,f0*.005) and base_rmse>rmse*1.5:
                inharmonicity={'B':float(fit.x[1]),'f0_ideal':float(fit.x[0]),'rmse_hz':rmse,'harmonic_rmse_hz':base_rmse,'count':len(ns),'method':'Moindres carrés bornés : fₙ=n f₀ √(1+B n²). Indice descriptif, pas intervalle de confiance.'}
    ef_idx=np.linspace(0,len(env)-1,min(800,len(env)),dtype=int)
    warnings=['Analyse mono par moyenne des canaux ; hypothèse de note isolée quasi stationnaire.', 'La décomposition modale est une proposition parcimonieuse, pas une preuve de la structure de l’instrument.', 'Sustain, release et instant de relâchement ne sont pas identifiables de façon unique sans information de jeu.']
    if f0 is None: warnings.append('Aucune périodicité fiable : fondamentale non estimée.')
    return {'f0':f0,'partials':partials,'onset':onset,'attack':attack,'inharmonicity':inharmonicity,'envelope':{'time':t[ef_idx].tolist(),'amplitude':env[ef_idx].tolist()},'autocorrelation':{'lag':(np.arange(len(ac))/acfs).tolist(),'value':ac.tolist()},'warnings':warnings,'method':'Autocorrélation normalisée, pics FFT interpolés, projection sur modes amortis et régression log-amplitude STFT.'}
