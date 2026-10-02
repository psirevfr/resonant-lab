"""WAV I/O, bounded views and mono analysis without altering original samples."""
from io import BytesIO
from dataclasses import dataclass
from math import gcd
import numpy as np
import soundfile as sf
from scipy import signal, ndimage

@dataclass
class Recording:
    name: str
    samples: np.ndarray
    sample_rate: int
    subtype: str
    original: bytes
    @property
    def mono(self): return self.samples.mean(axis=1)
    def metadata(self):
        return {'name':self.name,'sample_rate':self.sample_rate,'channels':self.samples.shape[1],'duration':len(self.samples)/self.sample_rate,'subtype':self.subtype,'peak':float(np.max(abs(self.samples))),'rms':float(np.sqrt(np.mean(self.samples**2))),'frames':len(self.samples)}

def read_wav(data: bytes, name: str) -> Recording:
    if len(data)>128*1024*1024: raise ValueError('Fichier limité à 128 Mo.')
    try:
        with sf.SoundFile(BytesIO(data)) as f:
            if f.format not in ('WAV','WAVEX','RF64'): raise ValueError('Importer un fichier WAV.')
            if f.channels>2 or f.samplerate<8000 or f.samplerate>192000: raise ValueError('WAV mono/stéréo, de 8 à 192 kHz requis.')
            if f.frames/f.samplerate>300 or f.frames*f.channels>30_000_000: raise ValueError('Import limité à 5 minutes et 30 millions d’échantillons.')
            if f.frames<32: raise ValueError('Fichier trop court.')
            x=f.read(dtype='float64',always_2d=True); fs=f.samplerate; subtype=f.subtype
    except (sf.LibsndfileError, RuntimeError) as exc: raise ValueError('WAV invalide ou non pris en charge.') from exc
    if not np.isfinite(x).all(): raise ValueError('Le fichier contient des valeurs non finies.')
    return Recording(name,x,fs,subtype,data)

def wav_bytes(x,fs):
    file=BytesIO(); sf.write(file,x,fs,format='WAV',subtype='FLOAT'); return file.getvalue()

def resample(x,source,target):
    if source==target: return x.copy()
    d=gcd(source,target); return signal.resample_poly(x,target//d,source//d)

def excerpt(recording,start,duration,fs=None):
    first=round(start*recording.sample_rate); last=min(len(recording.samples),first+round(duration*recording.sample_rate))
    if first>=len(recording.samples) or last-first<32: raise ValueError('La sélection est hors du fichier ou trop courte.')
    x=recording.mono[first:last]
    return resample(x,recording.sample_rate,fs) if fs else x.copy()

def envelope(x,fs):
    return np.sqrt(np.maximum(ndimage.uniform_filter1d(x*x,size=max(1,round(.01*fs)),mode='constant'),0))

def spectrum(x,fs,nfft=16384):
    n=min(len(x),nfft)
    f,psd=signal.welch(x,fs=fs,nperseg=n,noverlap=n//2,scaling='spectrum')
    return f,np.sqrt(np.maximum(psd,0))

def stft(x,fs,nfft=1024,max_frames=220):
    n=min(nfft,len(x)); hop=max(n//4, int(np.ceil(len(x)/max_frames)))
    # Long files: independent sparse windows, no huge intermediate spectrogram.
    starts=np.arange(0,max(1,len(x)-n+1),hop)
    frames=np.stack([x[s:s+n] for s in starts]); window=signal.windows.hann(n,sym=False)
    z=np.fft.rfft(frames*window,axis=1).T/max(window.sum(),1)
    return np.fft.rfftfreq(n,1/fs),(starts+n/2)/fs,np.abs(z)

def view(x,fs):
    x=np.asarray(x); step=max(1,int(np.ceil(len(x)/1600)))
    starts=np.arange(0,len(x),step)
    low=np.minimum.reduceat(x,starts); high=np.maximum.reduceat(x,starts)
    times=np.repeat(starts/fs,2); wave=np.column_stack((low,high)).ravel()
    ef=envelope(x,fs)
    f,mag=spectrum(x,fs)
    stride=max(1,len(f)//2200)
    sfreq,stime,smag=stft(x,fs)
    freq_stride=max(1,len(sfreq)//300)
    return {'time':times.tolist(),'wave':wave.tolist(),'envelope_time':(starts/fs).tolist(),'envelope':ef[starts].tolist(),'frequency':f[::stride].tolist(),'spectrum':(20*np.log10(np.maximum(mag[::stride],1e-7))).tolist(),'spectrogram':{'time':stime.tolist(),'frequency':sfreq[::freq_stride].tolist(),'db':(20*np.log10(np.maximum(smag[::freq_stride],1e-7))).tolist()},'peak':float(np.max(abs(x))),'rms':float(np.sqrt(np.mean(x*x))),'duration':len(x)/fs}
