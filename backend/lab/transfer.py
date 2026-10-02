"""Exact digital responses for executable LTI blocks and compatible DAGs."""
import numpy as np
from scipy import signal
from .blocks import REGISTRY, parameters, coefficients
from .graph import validate
from .schema import Patch, Block

def response(kind,p,fs,f):
    if kind=='delay': return np.exp(-2j*np.pi*f*round(fs*p['seconds'])/fs)
    b,a=coefficients(kind,p,fs)
    return signal.freqz(b,a,worN=f,fs=fs)[1]

def pack(f,h):
    return {'frequency':f.tolist(),'magnitude':(20*np.log10(np.maximum(abs(h),1e-12))).tolist(),'phase':np.rad2deg(np.unwrap(np.angle(h))).tolist()}

def describe(node: Block, fs: int):
    d=REGISTRY.get(node.type)
    if d is None: raise ValueError('Bloc inconnu.')
    p=parameters(node.type,node.parameters,fs)
    result={'lti':d.lti,'equation':d.equation,'description':d.description,'parameters':p}
    if not d.lti: return result
    b,a=coefficients(node.type,p,fs)
    f=np.geomspace(1,fs*.499,600)
    result.update(pack(f,response(node.type,p,fs,f)))
    if node.type=='delay':
        order=len(b)-1; poles=[{'real':0.,'imag':0.,'multiplicity':order}] if order else []
        zeros=[]; impulse=np.zeros(min(order+32,fs*2+32)); impulse[order]=1
        digital=f'H(z) = z^(−{order})'
    else:
        # Equal degree in z: pad trailing coefficients to account for delays/zeros at origin.
        order=max(len(a),len(b))-1
        az=np.pad(a,(0,order+1-len(a))); bz=np.pad(b,(0,order+1-len(b)))
        poles=[{'real':float(z.real),'imag':float(z.imag)} for z in np.roots(az)]
        zeros=[{'real':float(z.real),'imag':float(z.imag)} for z in np.roots(bz)]
        impulse=signal.lfilter(b,a,np.r_[1.,np.zeros(2047)])
        def poly(c): return ' + '.join(f'{v:.9g}'+(f' z^(−{k})' if k else '') for k,v in enumerate(c))
        digital=f'H(z) = ({poly(b)}) / ({poly(a)})'
    dc=response(node.type,p,fs,np.array([0.]))[0]
    result.update({'digital':digital,'b':b.tolist() if len(b)<100 else None,'a':a.tolist(), 'order':order,'poles':poles,'zeros':zeros,'stable':all(np.hypot(z['real'],z['imag'])<1 for z in poles),'dc_gain':float(abs(dc)), 'impulse_time':(np.arange(len(impulse))/fs).tolist(),'impulse':impulse.tolist()})
    return result

def global_response(patch: Patch, source_id: str):
    nodes,inc,_,order,output=validate(patch)
    if source_id not in order or inc[source_id]: raise ValueError('Choisir un générateur ou une entrée active comme point d’injection.')
    f=np.geomspace(1,patch.sample_rate*.499,600); responses={}
    for key in order:
        node=nodes[key]
        if key==source_id: responses[key]=np.ones(len(f),dtype=complex); continue
        if not inc[key]: responses[key]=np.zeros(len(f),dtype=complex); continue
        if not REGISTRY[node.type].lti: raise ValueError(f'{node.label or node.type} est variable dans le temps ou non linéaire : Bode global non défini.')
        p=parameters(node.type,node.parameters,patch.sample_rate)
        responses[key]=sum(responses[s] for s in inc[key])*response(node.type,p,patch.sample_rate,f)
    return {**pack(f,responses[output]),'description':f'Transfert de {source_id} vers {output}, les autres sources étant mises à zéro. Sommes et branches calculées sur le graphe réel.'}
