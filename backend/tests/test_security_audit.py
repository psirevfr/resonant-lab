import importlib
import json
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from lab.app import app
from lab.schema import AnalyzeRequest,RenderRequest


def test_private_api_responses_are_not_cacheable():
    response=TestClient(app).get('/api/blocks')
    assert response.status_code==200
    assert response.headers['cache-control']=='no-store'
    assert response.headers['x-content-type-options']=='nosniff'


@pytest.mark.parametrize('value',['nan','inf','-inf'])
def test_nonfinite_segment_rejected(value):
    client=TestClient(app)
    audio=client.post('/api/demo').json()
    assert client.get(f'/api/audio/{audio["id"]}/segment?start={value}').status_code==422
    assert client.get(f'/api/audio/{audio["id"]}/segment?duration={value}').status_code==422


def test_nonfinite_start_rejected_by_schema():
    for model in (AnalyzeRequest,RenderRequest):
        with pytest.raises(ValidationError) as error:model.model_validate({'audio_id':'test','start':float('inf'),'patch':{'nodes':[{'id':'out','type':'output'}]}})
        assert any(e['loc']==('start',) for e in error.value.errors())


def test_excerpt_keeps_exact_samples_after_selecting_before_mono():
    import numpy as np
    from lab.audio import Recording,excerpt
    samples=np.random.default_rng(4).normal(size=(44100,2))
    record=Recording('synthetic',samples,44100,'DOUBLE',b'')
    assert np.array_equal(excerpt(record,.1,.2),record.mono[4410:13230])


def test_runtime_symlinks_and_corrupt_manifest_fail_closed(tmp_path,monkeypatch):
    module=importlib.import_module('lab.app')
    directory=tmp_path/'runtime';directory.mkdir()
    monkeypatch.setattr(module,'COMPUTE_RUNTIME',directory)
    secret=tmp_path/'private';secret.write_text('private-test-content')
    (directory/'numpy.whl').symlink_to(secret)
    manifest=directory/'manifest.json'
    manifest.write_text(json.dumps({'ready':True,'files':{'numpy.whl':{'bytes':20}}}))
    client=TestClient(app)
    response=client.get('/compute-runtime/numpy.whl')
    assert response.status_code==404 and 'private-test-content' not in response.text
    assert client.get('/api/compute/config').json()=={'available':False}
    manifest.write_text('{broken')
    assert client.get('/api/compute/config').json()=={'available':False}
    assert client.get('/compute-runtime/manifest.json').status_code==404
    manifest.unlink();manifest.symlink_to(secret)
    assert client.get('/compute-runtime/manifest.json').status_code==404


def test_missing_runtime_file_does_not_announce_available(tmp_path,monkeypatch):
    module=importlib.import_module('lab.app');monkeypatch.setattr(module,'COMPUTE_RUNTIME',tmp_path)
    names=['numerical.zip','pyodide.mjs','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json']
    files={name:{'bytes':1} for name in names}
    for name in names:(tmp_path/name).write_bytes(b'x')
    manifest={'ready':True,'files':files,'runtime_version':'314.0.7','algorithm_version':'test','source_sha256':'test','download_bytes':6}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    client=TestClient(app)
    assert client.get('/api/compute/config').json()['available']
    (tmp_path/'pyodide.asm.wasm').unlink()
    assert not client.get('/api/compute/config').json()['available']


def test_csv_formula_injection_is_neutralized():
    patch={'nodes':[{'id':'=1+1','type':'oscillator'},{'id':'out','type':'output'}],
           'edges':[{'id':'e','source':'=1+1','target':'out'}],'duration':.05}
    response=TestClient(app).post('/api/export/csv',json=patch)
    assert response.status_code==200,response.text
    assert "'=1+1," in response.text
