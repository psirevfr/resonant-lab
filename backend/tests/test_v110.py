import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from lab.app import app
from lab.blocks import FILTER_TOPOLOGIES, process
from lab.compute import compute
from lab.graph import render
from lab.schema import Patch


layout_spec = importlib.util.spec_from_file_location('layout_schema',Path(__file__).resolve().parents[2]/'editor/layout.py')
layout_module = importlib.util.module_from_spec(layout_spec)
layout_spec.loader.exec_module(layout_module)


def test_layout_preserves_bank_and_checks_page_hierarchy():
    block={'id':'test-bloc','kind':'player','x':1,'y':2,'w':8,'h':2}
    root={'version':1,'pages':[{'id':'analyse','name':'','parent':None,'blocks':[]},
                               {'id':'atelier','name':'','parent':None,'blocks':[]},
                               {'id':'ecoute','name':'Écoute','parent':'analyse','custom':True,'blocks':[]}],
          'bank':[block], 'plots':{'wave':{'x':'Temps','xUnit':'ms','legend':True}}}
    assert layout_module.validate_layout(root)==root
    moved=copy.deepcopy(root)
    moved['pages'][2]['blocks'].append(moved['bank'].pop())
    assert layout_module.validate_layout(moved)['pages'][2]['blocks']==[block]
    moved['bank'].append(block)
    with pytest.raises(ValueError):layout_module.validate_layout(moved)
    root['pages'][2]['parent']='ecoute'
    with pytest.raises(ValueError):layout_module.validate_layout(root)


def test_unknown_public_page_has_a_real_404():
    assert TestClient(app).get('/p/page-absente').status_code==404


def test_adsr_releases_from_partial_attack_and_sustain():
    p={'attack':.01,'decay':.01,'sustain':.25,'gate':.005,'release':.01}
    y=process('adsr',p,[np.ones(30)],1000,30)
    assert y[[0,4,5,10,15]]==pytest.approx([0,.4,.5,.25,0])
    p['gate']=.025
    y=process('adsr',p,[np.ones(40)],1000,40)
    assert y[[10,20,25,30,36]]==pytest.approx([1,.25,.25,.125,0])


@pytest.mark.parametrize('kind',FILTER_TOPOLOGIES)
def test_ideal_filter_topology_has_the_documented_response(kind):
    x=np.r_[1., np.zeros(511)]
    params={'fc':1200,'q':.9}
    expected=process(FILTER_TOPOLOGIES[kind][0],params,[x],44100,len(x))
    assert process(kind,params,[x],44100,len(x))==pytest.approx(expected,abs=1e-12)


def test_subtractive_generation_paused_but_previous_graphs_render():
    fs=44100
    t=np.arange(2205)/fs
    x=.3*np.sin(2*np.pi*440*t)
    with pytest.raises(ValueError, match='additive'):
        compute('generate',{'audio_id':'synthetic','duration':.05,'synthesis':'subtractive'},x,fs)
    patch=Patch.model_validate({'duration':.05,'sample_rate':fs,'nodes':[
        {'id':'noise','type':'white_noise','parameters':{'seed':42,'amplitude':.3}},
        {'id':'gain','type':'gain','parameters':{'gain':1}},
        {'id':'out','type':'output'}], 'edges':[
        {'id':'n-g','source':'noise','target':'gain'},
        {'id':'g-o','source':'gain','target':'out'}]})
    assert render(patch).shape==x.shape
    assert np.isfinite(render(patch)).all()
