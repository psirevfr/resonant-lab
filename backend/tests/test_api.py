from fastapi.testclient import TestClient
from lab.app import app
from lab.schema import Patch
from lab.graph import render

client=TestClient(app)

def test_end_to_end():
    demo=client.post('/api/demo'); assert demo.status_code==200
    audio=demo.json(); assert audio['metadata']['channels']==1
    req={'audio_id':audio['id'],'duration':.5,'max_partials':4}
    a=client.post('/api/analyze',json=req); assert a.status_code==200, a.text
    assert a.json()['f0']>200
    g=client.post('/api/generate',json=req); assert g.status_code==200,g.text
    patch=g.json()['patch']
    r=client.post('/api/render',json={'patch':patch,'audio_id':audio['id']}); assert r.status_code==200,r.text
    assert r.json()['errors']['total']>=0
    assert client.get('/api/render/'+r.json()['id']+'/wav').content[:4]==b'RIFF'
    assert client.post('/api/patch/validate',json=patch).status_code==200
    assert '<svg' in client.post('/api/export/svg',json=patch).text
    assert 'block_id' in client.post('/api/export/csv',json=patch).text
    assert client.get('/api/audio/'+audio['id']+'/wav').status_code==200
    assert len(render(Patch.model_validate(patch)))==22050

def test_bad_upload_and_weights():
    assert client.post('/api/audio',files={'file':('bad.wav',b'bad','audio/wav')}).status_code==422
    assert client.get('/api/audio/missing/wav').status_code==404

def test_exports_include_effective_defaults_and_reproduce_audio():
    import csv
    import io
    import numpy as np
    patch={'nodes':[{'id':'noise','type':'noise'},{'id':'out','type':'output'}],
           'edges':[{'id':'wire','source':'noise','target':'out'}],'duration':.1}
    response=client.post('/api/patch/validate',json=patch)
    assert response.status_code==200,response.text
    saved=response.json()
    assert saved['nodes'][0]['parameters']['seed']==42
    assert np.array_equal(render(Patch.model_validate(saved)),render(Patch.model_validate(patch)))
    rows=list(csv.DictReader(io.StringIO(client.post('/api/export/csv',json=patch).text)))
    assert any(row['parameter']=='seed' and float(row['value'])==42 for row in rows)

def test_download_attachment_is_exact_and_cache_is_bounded():
    from lab.app import downloads
    downloads.clear()
    content=b'{"version":1}'
    first=client.post('/api/exports',files={'file':('../../unsafe.monpatch',content,'application/json')})
    assert first.status_code==200
    response=client.get(first.json()['url'])
    assert response.content==content
    assert response.headers['content-disposition']=='attachment; filename="resonant.monpatch"'
    assert response.headers['x-content-type-options']=='nosniff'
    for _ in range(8): client.post('/api/exports',files={'file':('test.csv',b'a,b','text/csv')})
    assert len(downloads)==8
    assert client.get(first.json()['url']).status_code==404
    assert client.post('/api/exports',files={'file':('test.exe',b'bad')}).status_code==422

def test_audio_byte_ranges_allow_ab_seeking():
    audio=client.post('/api/demo').json()
    patch={'nodes':[{'id':'tone','type':'oscillator'},{'id':'out','type':'output'}],
           'edges':[{'id':'wire','source':'tone','target':'out'}],'duration':.1}
    rendered=client.post('/api/render',json={'patch':patch}).json()
    urls=[f'/api/audio/{audio["id"]}/wav',f'/api/audio/{audio["id"]}/segment?duration=.1',
          f'/api/render/{rendered["id"]}/wav']
    for url in urls:
        full=client.get(url)
        assert full.headers['accept-ranges']=='bytes'
        part=client.get(url,headers={'Range':'bytes=100-199'})
        assert part.status_code==206 and part.content==full.content[100:200]
        assert part.headers['content-range']==f'bytes 100-199/{len(full.content)}'
        tail=client.get(url,headers={'Range':'bytes=-80'})
        assert tail.status_code==206 and tail.content==full.content[-80:]
        assert client.get(url,headers={'Range':f'bytes={len(full.content)}-'}).status_code==416
