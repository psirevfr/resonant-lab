import numpy as np
from fastapi.testclient import TestClient
from lab.app import app
from lab.compute import compute
from lab.analysis import analyze

def test_workspace_routes_and_legacy_entry():
    client=TestClient(app)
    for path in ('/atelier','/analyse','/mon-lab/'):
        response=client.get(path)
        assert response.status_code==200
        assert '<div id="root">' in response.text
        assert response.headers['cache-control']=='no-store'

def test_analysis_shared_local_dispatch_matches_reference():
    fs=44100;t=np.arange(4410)/fs;x=np.sin(2*np.pi*440*t)*np.exp(-t/.3)
    request={'audio_id':'synthetic','start':0,'duration':.1,'max_partials':4}
    local=compute('analyze',request,x,fs);expected=analyze(x,fs,4)
    assert local['partials']==expected['partials']
    assert local['f0']==expected['f0']

def test_local_analysis_input_does_not_submit_job():
    client=TestClient(app);source=client.post('/api/demo').json()
    response=client.post('/api/compute/input',json={'kind':'analyze','request':{'audio_id':source['id'],'duration':.1}})
    assert response.status_code==200
    assert response.headers['content-type']=='application/octet-stream'
    assert len(response.content)==4410*8
    assert client.get('/api/jobs').json()==[]
