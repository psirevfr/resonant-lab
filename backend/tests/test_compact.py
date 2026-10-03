import numpy as np
import pytest
from fastapi.testclient import TestClient
from lab.app import app
from lab.compact import simplify,tidy,joint_fit,shaping
from lab.schema import Patch,Block,Weights
from lab.identify import link
from lab.graph import render,validate
from lab.metrics import Objective
from lab.audio import wav_bytes


def redundant():
    return Patch(duration=.12,nodes=[Block(id=k,type='modal',parameters={'frequency':440,'amplitude':.2,'tau':.2,'attack':0,'onset':0,'phase':0}) for k in ('a','b')]+[Block(id='sum',type='sum'),Block(id='gain',type='gain',parameters={'gain':1}),Block(id='out',type='output')],edges=[link('a','sum'),link('b','sum'),link('sum','gain'),link('gain','out')])


def test_redundant_sources_really_removed_and_input_unchanged():
    p=redundant();before=p.model_dump();x=render(p)
    r=simplify(p,x,Weights(),tolerance=0,test_shaping=False)
    q=Patch.model_validate(r['patch'])
    assert p.model_dump()==before==r['original']
    assert r['final_blocks']==3 and r['final_generators']==1
    assert r['final']<=r['limit']
    assert np.allclose(x,render(q),atol=1e-10)
    assert np.array_equal(render(q),render(Patch.model_validate_json(q.model_dump_json())))
    assert r['utilities'][0]['error_increase_without']>.1
    assert any(c['reference'] for c in r['candidates'])


def test_zero_budget_preserves_distinct_modes_and_baseline():
    p=redundant();p.nodes[1].parameters.update(frequency=783,phase=.7,tau=.09)
    x=render(p);r=simplify(p,x,Weights(),tolerance=0,test_shaping=False)
    assert r['final']<=r['limit']
    assert r['final_generators']==2
    assert np.allclose(render(Patch.model_validate(r['patch'])),x,atol=1e-10)
    assert any(not c['within_tolerance'] for c in r['candidates'])


def test_tidy_preserves_gain_and_sound():
    p=redundant();p.nodes[1].parameters['frequency']=700;p.nodes[-2].parameters['gain']=.8
    q=tidy(p)
    assert any(n.type=='gain' for n in q.nodes)
    assert np.array_equal(render(p),render(q))
    p.nodes[-2].parameters['gain']=1
    q=tidy(p);assert len(q.nodes)==len(p.nodes)-1
    assert np.array_equal(render(p),render(q))


def test_high_frequency_fit_and_input_bounds():
    p=redundant();p.nodes[0].parameters['frequency']=21900
    p.nodes[1].parameters['frequency']=21800
    x=render(p)
    fitted=joint_fit(p,x,Objective(x,p.sample_rate,Weights()),1)
    validate(fitted)
    for tol in (-1,float('nan'),2):
        with pytest.raises(ValueError):simplify(p,x,Weights(),tolerance=tol)
    with pytest.raises(ValueError):simplify(p,x[:-1],Weights())
    p.nodes[0].parameters['onset']=.01
    with pytest.raises(ValueError,match='communs'):simplify(p,x,Weights())


def test_shaping_score_is_actual_executed_graph():
    from lab.blocks import process
    p=tidy(redundant());y=render(p)
    x=process('lowpass',{'fc':1100,'q':.8},[np.tanh(4*y)],p.sample_rate,len(y))*.7
    obj=Objective(x,p.sample_rate,Weights())
    q=shaping(p,obj)
    assert q is not None
    assert obj(render(q))<obj(y)
    assert {'saturation','lowpass','gain'}.issubset(n.type for n in q.nodes)


def test_compact_api_validates_and_returns_reversible_patch():
    c=TestClient(app);p=redundant()
    assert c.post('/api/compact',json={'patch':p.model_dump()}).status_code==422
    a=c.post('/api/audio',files={'file':('reference.wav',wav_bytes(render(p),p.sample_rate),'audio/wav')}).json()
    req={'patch':p.model_dump(),'audio_id':a['id'],'tolerance':0,'test_shaping':False}
    response=c.post('/api/compact',json=req)
    assert response.status_code==200,response.text
    r=response.json();assert r['original']==p.model_dump()
    assert r['final']<=r['limit'] and r['final_blocks']<len(p.nodes)
    assert c.post('/api/compact',json={**req,'tolerance':-1}).status_code==422
