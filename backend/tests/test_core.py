from io import BytesIO
from threading import Event
import numpy as np
import pytest
import soundfile as sf
from scipy import signal
from lab.audio import read_wav,wav_bytes,spectrum,envelope
from lab.analysis import analyze
from lab.blocks import coefficients,parameters,process
from lab.schema import Patch,Block,Edge,Weights,OptimizeRequest
from lab.graph import render,validate
from lab.transfer import describe,global_response
from lab.identify import generate
from lab.optimization import run_optimization
from lab.metrics import Objective

FS=44100

def patch(nodes,edges,duration=.2):
    return Patch(nodes=[Block(id=k,type=t,parameters=p) for k,t,p in nodes],edges=[Edge(id=f'{a}-{b}',source=a,target=b) for a,b in edges],duration=duration)

def sine(freq=440,duration=1):
    t=np.arange(round(FS*duration))/FS; return .5*np.sin(2*np.pi*freq*t)

@pytest.mark.parametrize('subtype',['PCM_16','PCM_24','PCM_32','FLOAT','DOUBLE'])
def test_wav_stereo(subtype):
    x=np.column_stack((sine(),-sine())); f=BytesIO(); sf.write(f,x,FS,format='WAV',subtype=subtype)
    rec=read_wav(f.getvalue(),'test.wav')
    assert rec.sample_rate==FS and rec.samples.shape==x.shape
    assert np.max(abs(rec.samples-x))<4e-5
    assert rec.original==f.getvalue()

def test_invalid_wav():
    with pytest.raises(ValueError): read_wav(b'bad','bad.wav')

def test_spectrum_envelope_pitch():
    x=sine(); f,a=spectrum(x,FS); assert abs(f[np.argmax(a)]-440)<3
    assert np.median(envelope(x,FS))==pytest.approx(.5/np.sqrt(2),rel=.03)
    result=analyze(x,FS,4)
    assert result['f0']==pytest.approx(440,abs=1)
    assert result['partials'][0]['frequency']==pytest.approx(440,abs=.1)
    assert result['inharmonicity'] is None

def test_decay_and_reconstruction():
    t=np.arange(FS*2)/FS; x=.6*np.exp(-t/.7)*(1-np.exp(-t/.005))*np.sin(2*np.pi*440*t)
    a=analyze(x,FS,4)
    assert a['partials'][0]['tau']==pytest.approx(.7,rel=.15)
    result=generate(x,FS,4,weights=Weights())
    p=Patch.model_validate(result['patch']); y=render(p)
    assert Objective(x,FS,Weights())(y)<.25
    assert any(n.type=='modal' for n in p.nodes)

def test_inharmonicity():
    t=np.arange(FS*2)/FS; B=.00015
    x=sum(.4/n*np.exp(-t/(1.5/n**.3))*(1-np.exp(-t/.003))*np.sin(2*np.pi*n*220*np.sqrt(1+B*n*n)*t) for n in range(1,7))
    a=analyze(x,FS,8)
    assert a['inharmonicity'] is not None
    assert a['inharmonicity']['B']==pytest.approx(B,rel=.2)

def test_filter_bode_matches_impulse():
    p=parameters('lowpass',{'fc':3000,'q':2**-.5},FS); b,a=coefficients('lowpass',p,FS)
    _,h=signal.freqz(b,a,worN=[3000],fs=FS)
    assert 20*np.log10(abs(h[0]))==pytest.approx(-3.0103,abs=.001)
    result=describe(Block(id='filter',type='lowpass',parameters=p),FS)
    assert result['stable'] and result['order']==2
    n=16384; impulse=np.r_[1.,np.zeros(n-1)]
    actual=process('lowpass',p,[impulse],FS,n)
    f=np.fft.rfftfreq(n,1/FS); _,expected=signal.freqz(b,a,worN=f,fs=FS)
    assert np.max(abs(np.fft.rfft(actual)-expected))<1e-10

def test_graph_global_parallel_and_serialization():
    p=patch([('in','input',{}),('a','gain',{'gain':2}),('b','gain',{'gain':3}),('sum','sum',{}),('out','output',{})],[('in','a'),('in','b'),('a','sum'),('b','sum'),('sum','out')])
    assert render(p)[0]==5
    g=global_response(p,'in'); assert g['magnitude'][0]==pytest.approx(20*np.log10(5))
    restored=Patch.model_validate_json(p.model_dump_json())
    assert np.array_equal(render(restored),render(p))

def test_graph_rejects_cycles_missing_duplicate_and_nyquist():
    p=patch([('a','gain',{}),('b','gain',{}),('out','output',{})],[('a','b'),('b','a'),('b','out')])
    with pytest.raises(ValueError,match='Boucle'): validate(p)
    p=patch([('sin','oscillator',{'frequency':30000}),('out','output',{})],[('sin','out')])
    with pytest.raises(ValueError,match='Nyquist'): render(p)
    p=patch([('sin','oscillator',{}),('out','output',{})],[])
    with pytest.raises(ValueError,match='entrées'): render(p)

def test_nonlinear_global_rejected():
    p=patch([('sin','oscillator',{}),('env','envelope',{}),('out','output',{})],[('sin','env'),('env','out')])
    with pytest.raises(ValueError,match='non linéaire'): global_response(p,'sin')

def test_optimization_reduces_real_error():
    p=patch([('sin','oscillator',{'frequency':440,'amplitude':.2}),('out','output',{})],[('sin','out')])
    x=sine(duration=.2)
    req=OptimizeRequest(patch=p,audio_id='test',max_iterations=5,parameter_ids=['sin:amplitude'])
    result=run_optimization(req,x,lambda _:None,Event())
    assert result['final']<result['initial']*.6
    assert result['final']<=result['initial']
    assert all(b<=a+1e-12 for a,b in zip(result['history'],result['history'][1:]))

def test_delay_and_adsr_early_release():
    n=1000; x=np.ones(n)
    y=process('delay',{'seconds':.01},[x],FS,n)
    assert np.all(y[:441]==0) and y[441]==1
    p={'attack':.1,'decay':.1,'sustain':.3,'gate':.005,'release':.01}
    y=process('adsr',p,[x],FS,n)
    assert np.max(y)<.051 and y[-1]==0

def test_silence():
    with pytest.raises(ValueError,match='silencieux'): analyze(np.zeros(FS),FS)

def test_nearby_weak_peak_does_not_replace_fundamental():
    t=np.arange(FS*2)/FS
    x=.5*np.sin(2*np.pi*440*t)+.015*np.sin(2*np.pi*420*t)+.12*np.sin(2*np.pi*880*t)
    assert analyze(x,FS,8)['f0']==pytest.approx(440,abs=1)

def test_three_known_harmonics():
    t=np.arange(FS)/FS
    x=sum(.5/n*np.sin(2*np.pi*440*n*t) for n in (1,2,3))
    a=analyze(x,FS,6)
    for f in (440,880,1320): assert min(abs(p['frequency']-f) for p in a['partials'])<1

def test_beating_modes_improve_reconstruction():
    from lab.modal_fit import refine
    from lab.identify import modal_patch
    t=np.arange(FS*2)/FS
    attack=1-np.exp(-t/.004)
    x=attack*(.4*np.exp(-t/.7)*np.sin(2*np.pi*440*t)+.22*np.exp(-t/1.8)*np.sin(2*np.pi*441.4*t+.4))
    a=analyze(x,FS,4);b,diagnostics=refine(x,FS,a,4)
    objective=Objective(x,FS,Weights())
    plain=objective(render(modal_patch(a,FS,2,len(a['partials']))))
    refined=objective(render(modal_patch(b,FS,2,len(b['partials']))))
    assert refined<plain*.5
    assert refined<.15
    assert any(d['modes']>1 and d['retained'] for d in diagnostics)

def test_white_noise_impact_reduces_attack_error_and_is_executable():
    from lab.impact import fit_impact
    from lab.identify import modal_patch
    fs=FS;duration=.7;t=np.arange(round(fs*duration))/fs
    features={'partials':[{'frequency':440,'amplitude':.15,'phase':0,'tau':.6,'decay_r2':1.}], 'attack':.003,'onset':.01}
    base=modal_patch(features,fs,duration,1);tone=render(base)
    noise=np.random.default_rng(17).normal(size=len(t))
    hp=process('highpass',{'fc':80.,'q':2**-.5},[noise],fs,len(t))
    lp=process('lowpass',{'fc':7000.,'q':2**-.5},[hp],fs,len(t))
    burst=process('envelope',{'attack':.0007,'tau':.025,'onset':.008},[lp],fs,len(t))
    target=tone+.6*burst;objective=Objective(target,fs,Weights())
    hybrid=fit_impact(base,target,features,objective)
    assert hybrid is not None
    assert any(n.type=='noise' for n in hybrid.nodes)
    assert any(n.id=='impact-env' for n in hybrid.nodes)
    assert objective.components(render(hybrid))['attack']<objective.components(tone)['attack']
    assert np.array_equal(render(hybrid),render(Patch.model_validate_json(hybrid.model_dump_json())))

def test_attack_metric_detects_missing_short_transient():
    x=sine(duration=.3);y=x.copy();x[:800]+=np.random.default_rng(1).normal(0,.3,800)
    terms=Objective(x,FS,Weights()).components(y)
    assert terms['attack']>terms['spectrogram']

def test_patch_rejects_nonfinite_coordinates():
    from pydantic import ValidationError
    with pytest.raises(ValidationError): Block(id='bad',type='gain',position={'x':float('nan'),'y':0})

def test_attack_calibration_matches_render_and_preserves_free_decay():
    from lab.attack_fit import calibrate_attack
    from lab.identify import modal_patch
    features={'partials':[{'frequency':440,'amplitude':.4,'phase':.3,'tau':.7,'decay_r2':1.}], 'attack':.024,'onset':.02}
    base=modal_patch(features,FS,.6,1)
    target=base.model_copy(deep=True)
    p=next(n.parameters for n in target.nodes if n.type=='modal')
    delta=.005
    p.update(onset=p['onset']+delta,attack=.003,
             amplitude=p['amplitude']*np.exp(-delta/p['tau']),
             phase=(p['phase']+2*np.pi*p['frequency']*delta+np.pi)%(2*np.pi)-np.pi)
    objective=Objective(render(target),FS,Weights())
    fitted,diagnostic=calibrate_attack(base,objective)
    actual=objective(render(fitted))
    assert actual==pytest.approx(diagnostic['error'],abs=1e-11)
    assert actual<1e-10 and actual<objective(render(base))
    assert next(n.parameters for n in fitted.nodes if n.type=='modal')['frequency']==440

def test_noise_seed_must_be_integer():
    with pytest.raises(ValueError,match='entier'):
        parameters('noise',{'seed':1.5},FS)
