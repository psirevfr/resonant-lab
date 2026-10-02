"""Fit nearby damped modes to complex narrow-band trajectories.

No stored waveform: the result contains only frequencies, decay constants,
amplitudes and phases of explicit differential-equation modes.
"""
import numpy as np
from scipy import signal, optimize
from .blocks import exponential

def fit_group(x,fs,partial,onset,attack,max_modes=3,local_penalty=.006,bandwidth=None):
    frequency=partial['frequency']; t=np.arange(len(x))/fs-onset
    # Demodulate then anti-alias before reducing the trajectory to about 200 Hz.
    down=max(1,round(fs/200))
    track=signal.resample_poly(2*x*np.exp(-2j*np.pi*frequency*t),1,down)
    tt=np.arange(len(track))*down/fs-onset
    valid=(tt>=max(.018,attack*2))&(tt<min(4,len(x)/fs-onset-.015))
    all_times=tt.copy()
    sos=signal.butter(3,bandwidth,fs=fs/down,output='sos') if bandwidth and len(track)>24 else None
    if sos is not None:track=signal.sosfiltfilt(sos,track)
    tt=tt[valid]; z=track[valid]
    if len(tt)<12: return [partial],None
    scale=max(np.linalg.norm(z),1e-12)
    spread=min(5.,max(.5,frequency*.012))
    results=[]
    for count in range(1,max_modes+1):
        offsets=np.linspace(-min(1.2,spread*.7),min(1.2,spread*.7),count) if count>1 else np.array([0.])
        taus=np.geomspace(max(.04,partial['tau']*.2),min(20,partial['tau']*2),count) if count>1 else np.array([partial['tau']])
        init=np.r_[offsets,np.log(taus)]
        def solve(v,full=False):
            if sos is None:
                basis=exponential(tt[:,None],attack,np.exp(v[count:])[None,:])*np.exp(2j*np.pi*tt[:,None]*v[:count])
            else:
                positive=np.maximum(0,all_times)[:,None]
                raw=exponential(positive,attack,np.exp(v[count:])[None,:])*np.exp(2j*np.pi*positive*v[:count])*(all_times[:,None]>=0)
                basis=signal.sosfiltfilt(sos,raw,axis=0)[valid]
            co=np.linalg.lstsq(basis,z,rcond=1e-8)[0]
            residual=(basis@co-z)/scale
            return (co,residual) if full else np.r_[residual.real,residual.imag]
        fitted=optimize.least_squares(solve,init,bounds=(np.r_[np.full(count,-spread),np.full(count,np.log(.015))],np.r_[np.full(count,spread),np.full(count,np.log(30))]),max_nfev=100,ftol=1e-7,xtol=1e-7,gtol=1e-7)
        co,residual=solve(fitted.x,True)
        error=float(np.linalg.norm(residual)**2)
        modes=[]
        for i in range(count):
            amp=float(abs(co[i]));phase=float(np.angle(co[i])+np.pi/2);phase=(phase+np.pi)%(2*np.pi)-np.pi
            if amp>4: break  # reject cancellation with enormous opposing modes
            modes.append({'frequency':float(frequency+fitted.x[i]),'amplitude':amp,'phase':phase,'tau':float(np.exp(fitted.x[count+i])),'decay_r2':None})
        if len(modes)==count:
            results.append((error+local_penalty*count,modes,error))
    if not results:return [partial],None
    _,modes,error=min(results,key=lambda r:r[0])
    return modes,{'center_hz':frequency,'modes':len(modes),'relative_squared_error':error,'max_modes':max_modes,'bandwidth_hz':bandwidth,'method':f'Projection complexe sur 1 à {max_modes} modes amortis voisins ; sélection SSE relative + {local_penalty:g} × nombre de modes. Filtrage d’isolement identique appliqué aux mesures et aux bases mathématiques.'}

def refine(x,fs,features,max_groups=12,max_modes=3,local_penalty=.006,bandwidth=None):
    ranked=sorted(features['partials'],key=lambda p:p['amplitude']**2*p['tau'],reverse=True)[:max_groups]
    # Nearby analysis peaks belong to one trajectory rather than duplicate groups.
    groups=[]
    for partial in ranked:
        if all(abs(partial['frequency']-p['frequency'])>12 for p in groups): groups.append(partial)
    modes=[];diagnostics=[]
    for partial in groups:
        fitted,diag=fit_group(x,fs,partial,features['onset'],features['attack'],max_modes,local_penalty,bandwidth)
        if diag and diag['relative_squared_error'] < .35:
            modes.extend(fitted)
        if diag: diagnostics.append({**diag,'retained':bool(diag['relative_squared_error'] < .35)})
    # Leave space for sum/gain/output and the optional five-block impact branch.
    from .graph import MAX_RENDER_WORK
    limit=max(1,min(120,MAX_RENDER_WORK//len(x)-8))
    if len(modes)>limit:
        modes=sorted(modes,key=lambda p:p['amplitude']**2*p['tau'],reverse=True)[:limit]
    return {**features,'partials':modes or [ranked[0]]},diagnostics
