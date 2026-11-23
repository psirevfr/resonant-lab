from threading import Event

import pytest
from fastapi.testclient import TestClient

from lab import learning_store
from lab.app import app
from lab.compact import simplify
from lab.graph import render
from lab.optimization import run_optimization, validate_request
from lab.schema import Block, Edge, OptimizeRequest, Patch, Weights


def test_collective_memory_needs_several_independent_contributors_and_can_be_withdrawn():
    for owner in range(1, 6):
        ticket = learning_store.make_ticket(owner, b'fixture', 44100)
        report = learning_store.LearningReport(ticket=ticket, profile='sustained', strategy='adsr', reward=owner/5)
        assert learning_store.accept(owner, report)
        assert not learning_store.accept(owner, report)
    assert learning_store.summary() == {'sustained': {'adsr': {'contributors': 5, 'mean': .6}}}
    for i in range(1, 35):
        ticket = learning_store.make_ticket(1, b'new test clip'+bytes([i]), 44100)
        learning_store.accept(1, report.model_copy(update={'ticket':ticket, 'reward':0.}))
    assert learning_store.summary()['sustained']['adsr']['contributors'] == 5
    learning_store.reset(1)
    assert learning_store.summary() == {}


def test_collective_endpoint_accepts_only_an_opted_in_receipt_for_this_session():
    client = TestClient(app)
    audio = client.post('/api/demo').json()
    body = {'kind':'generate','request':{'audio_id':audio['id'],'duration':.05}}
    assert 'x-acoustic-ticket' not in client.post('/api/compute/input',json=body).headers
    ticket = client.post('/api/compute/input',json={**body,'contribute':True}).headers['x-acoustic-ticket']
    report = {'ticket':ticket,'strategy':'adsr','profile':'sustained','reward':.35}
    assert client.post('/api/acoustic-learning',json=report).json() == {'recorded':True}
    assert client.post('/api/acoustic-learning',json=report).json() == {'recorded':False}
    assert client.post('/api/acoustic-learning',json={**report,'samples':[1]}).status_code == 422
    other = learning_store.make_ticket(2,b'no',44100)
    assert client.post('/api/acoustic-learning',json={**report,'ticket':other}).status_code == 403
    assert client.get('/api/acoustic-learning').json() == {'history':{}}
    assert client.post('/api/acoustic-learning/reset',json={}).json() == {'ok':True}


def make_patch(filters=True):
    types={'osc':'oscillator','sat':'saturation','gain':'gain','out':'output'}
    if filters:
        types={'osc':'oscillator','sat':'saturation','eq':'peak_eq','gain':'gain','out':'output'}
    nodes=[Block(id=key,type=value) for key,value in types.items()]
    return Patch(duration=.05,nodes=nodes,edges=[Edge(id=a+'-'+b,source=a,target=b)
                                                for a,b in zip(types,list(types)[1:])])


def test_manual_saturation_and_eq_are_included_by_each_solver():
    patch=make_patch()
    ideal=patch.model_copy(deep=True)
    ideal.nodes[1].parameters={'drive':2.6}
    ideal.nodes[2].parameters={'fc':1320,'q':1.2,'db':-8}
    patch.nodes.append(Block(id='isolated',type='oscillator'))
    req=OptimizeRequest(patch=patch,method='compare',focus_ids=['sat'],max_iterations=8)
    result=run_optimization(req,render(ideal),lambda _:None,Event())
    assert result['parameters'][0]=='sat:drive'
    assert {'eq:fc','eq:q','eq:db','osc:phase'} <= set(result['parameters'])
    assert all(not key.startswith('isolated:') for key in result['parameters'])
    assert {row['method'] for row in result['methods']}=={'Powell','L-BFGS-B','differential_evolution'}
    assert all(row['evaluations']>0 for row in result['methods'])
    assert result['final'] < result['initial']
    assert result['final']==min(row['error'] for row in result['methods'])
    assert Patch.model_validate(result['patch']).edges==patch.edges
    with pytest.raises(ValueError,match='indisponible'):
        validate_request(req.model_copy(update={'parameter_ids':['isolated:phase']}))


def test_simplification_scores_the_manually_modified_chain():
    patch=make_patch(filters=False)
    patch.nodes[1].parameters={'drive':3.6}
    x=render(patch)
    compact=simplify(patch,x,Weights(),tolerance=0,preserve_chain=True,protect_texture=True)
    assert compact['original']==patch.model_dump()
    assert compact['final_blocks']==3
    assert [node['type'] for node in compact['patch']['nodes']]==['oscillator','saturation','output']
    assert render(Patch.model_validate(compact['patch'])) == pytest.approx(x,abs=1e-12)


def test_compensation_is_proposed_only_without_an_existing_filter():
    from lab.optimization import compensation_patch

    assert compensation_patch(make_patch(filters=True)) is None
    p, source, eq = compensation_patch(make_patch(filters=False))
    assert source=='sat'
    assert p.nodes[-1].id==eq
    assert render(p)==pytest.approx(render(make_patch(filters=False)),abs=1e-12)


def test_compensation_can_be_retained_when_the_added_eq_improves_the_best_fit():
    nodes=[Block(id='a',type='oscillator',parameters={'frequency':440,'amplitude':.6}),
           Block(id='b',type='oscillator',parameters={'frequency':1370,'amplitude':.6}),
           Block(id='mix',type='sum'),Block(id='sat',type='saturation',parameters={'drive':4}),
           Block(id='out',type='output')]
    connections=[('a','mix'),('b','mix'),('mix','sat')]
    def graph(parts, links):
        return Patch(duration=.08,nodes=parts,edges=[Edge(id=a+b,source=a,target=b) for a,b in links])
    original=graph(nodes,connections+[('sat','out')])
    ideal=graph(nodes+[Block(id='eq',type='peak_eq',parameters={'fc':1810,'q':2,'db':-18})],
                connections+[('sat','eq'),('eq','out')])
    request=OptimizeRequest(patch=original,method='compare',compensate=True,max_iterations=16)
    result=run_optimization(request,render(ideal),lambda _:None,Event())
    assert result['compensation_retained']
    assert result['final'] < .99 * min(row['error'] for row in result['methods'] if row['stage']=='montage')
    assert len(result['patch']['nodes'])==len(nodes)+1
