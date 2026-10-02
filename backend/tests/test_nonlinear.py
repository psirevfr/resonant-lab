import numpy as np
import pytest
from scipy import signal
from lab.blocks import process,parameters,coefficients
from lab.schema import Patch,Block,Weights
from lab.identify import link
from lab.graph import render
from lab.metrics import Objective
from lab.nonlinear_fit import architecture,fit_architecture,search


def source():
    return Patch(duration=.15,nodes=[Block(id='m',type='modal',parameters={'frequency':400,'amplitude':.4,'phase':0,'tau':.3,'attack':.003,'onset':0}),Block(id='out',type='output')],edges=[link('m','out')])


def test_asymmetry_creates_even_harmonics_and_is_deterministic():
    fs=48000;n=48000;t=np.arange(n)/fs;x=.5*np.sin(2*np.pi*400*t)
    def result(bias):return process('asymmetric_saturation',parameters('asymmetric_saturation',{'drive':6,'bias':bias,'level':1},fs),[x],fs,n)
    symmetric=result(0);asymmetric=result(.8)
    # An integer-cycle interior excludes resampler boundary transients.
    a=abs(np.fft.rfft(asymmetric[1200:-1200]));s=abs(np.fft.rfft(symmetric[1200:-1200]));idx=round(800*len(asymmetric[1200:-1200])/fs)
    assert a[idx]>100*s[idx]+1
    assert np.array_equal(asymmetric,result(.8))
    zero=process('asymmetric_saturation',parameters('asymmetric_saturation',{},fs),[np.zeros(n)],fs,n)
    assert np.max(abs(zero))==0


def test_new_filters_transfer_and_stability():
    fs=48000
    for kind,values in [('peak_eq',{'fc':1800,'q':2,'db':12}),('lowpass1',{'fc':1800})]:
        p=parameters(kind,values,fs);b,a=coefficients(kind,p,fs)
        assert np.max(abs(np.roots(a)))<1
        h=signal.freqz(b,a,worN=[1800],fs=fs)[1][0]
        assert 20*np.log10(abs(h))==pytest.approx(12 if kind=='peak_eq' else -3.0103,abs=.001)
        impulse=np.r_[1.,np.zeros(4095)]
        assert np.allclose(process(kind,p,[impulse],fs,len(impulse)),signal.lfilter(b,a,impulse))
    b,a=coefficients('peak_eq',{'fc':3000,'q':.7,'db':0},fs)
    assert np.allclose(b,a)


def test_architectures_execute_serialize_and_fit_jointly():
    base=source();original=base.model_dump()
    for style in ('couleur','resonance','pre-filtre','parallele'):
        p=architecture(base,style);y=render(p)
        assert len(y)==round(p.sample_rate*p.duration)
        assert np.array_equal(y,render(Patch.model_validate_json(p.model_dump_json())))
        assert sum(n.type=='modal' for n in p.nodes)==1
    assert base.model_dump()==original
    p=architecture(base,'couleur');target=render(p)
    fitted,info=fit_architecture(p,target,Weights(),budget=35)
    assert np.isfinite(Objective(target,p.sample_rate,Weights())(render(fitted)))
    candidates,diagnostics=search([base],target,Weights(),Objective(target,p.sample_rate,Weights()),budget=35)
    assert len(candidates)==3
    for q,d in zip(candidates,diagnostics):
        assert d['full_rate_error']==pytest.approx(Objective(target,p.sample_rate,Weights())(render(q)))
        assert d['full_rate_error']<=d['seed_error']+1e-12
