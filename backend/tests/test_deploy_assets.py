"""Deployment helper tests use disposable repositories, never production files."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

spec=importlib.util.spec_from_file_location('deploy_assets',Path(__file__).resolve().parents[2]/'scripts/deploy_assets.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)


def repository(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    subprocess.run(['git','init','-q',str(root)],check=True)
    folder=root/'frontend/dist/assets';folder.mkdir(parents=True)
    return root,folder


def tracked(root,folder,name='App-AbCd1234.js',content='public code'):
    file=folder/name;file.write_text(content)
    subprocess.run(['git','add','--',str(file.relative_to(root))],cwd=root,check=True)
    return file


def untrack(root,file):
    subprocess.run(['git','rm','--cached','-q','--',str(file.relative_to(root))],cwd=root,check=True)


def test_retains_old_lazy_chunk_and_never_overwrites_a_current_chunk(tmp_path):
    root,folder=repository(tmp_path);old=tracked(root,folder)
    assert assets.before(root,now=100)['cached']==1
    old.unlink();assets.restore(root,now=101)
    assert old.read_text()=='public code'
    old.write_text('new current contents')
    assets.restore(root,now=102)
    assert old.read_text()=='new current contents'


def test_removes_only_known_unchanged_untracked_files_before_next_pull(tmp_path):
    root,folder=repository(tmp_path);old=tracked(root,folder)
    assets.before(root,now=100);untrack(root,old)
    unknown=folder/'unknown-ZyXw9876.js';unknown.write_text('untracked private data')
    plain=folder/'credentials.json';plain.write_text('do not touch')
    r=assets.before(root,now=101)
    assert r['temporarily_removed']==1 and not old.exists()
    assert unknown.read_text()=='untracked private data' and plain.read_text()=='do not touch'
    # This is the EXIT trap recovery path even if git merge fails.
    assets.restore(root,now=102)
    assert old.read_text()=='public code'
    cache=root/'.local/deploy-assets/files'
    assert not (cache/unknown.name).exists() and not (cache/plain.name).exists()


def test_preserves_locally_modified_old_file(tmp_path):
    root,folder=repository(tmp_path);old=tracked(root,folder)
    assets.before(root,now=100);untrack(root,old);old.write_text('local modification')
    assets.before(root,now=101);assets.restore(root,now=102)
    assert old.read_text()=='local modification'


def test_retention_is_bounded_by_age_bytes_and_file_count(tmp_path):
    root,folder=repository(tmp_path)
    a=tracked(root,folder,'a-AbCd1234.js','a'*5)
    b=tracked(root,folder,'b-AbCd1234.css','b'*5)
    c=tracked(root,folder,'c-AbCd1234.js','c'*5)
    r=assets.before(root,now=100,max_bytes=10,max_files=1)
    assert r['cached']==1 and r['bytes']==5
    for p in (a,b,c):untrack(root,p);p.unlink()
    r=assets.restore(root,now=102,max_age=1)
    assert r['cached']==0 and r['restored']==0
    assert not list((root/'.local/deploy-assets/files').iterdir())


def test_rejects_manifest_traversal_and_public_symlinks(tmp_path):
    root,folder=repository(tmp_path);file=tracked(root,folder)
    assets.before(root,now=100)
    manifest=root/'.local/deploy-assets/manifest.json'
    state=json.loads(manifest.read_text());meta=next(iter(state['files'].values()))
    manifest.write_text(json.dumps({'version':1,'files':{'../../escape-AbCd1234.js':meta}}))
    with pytest.raises(ValueError):assets.restore(root,now=101)
    manifest.unlink();file.unlink();secret=root/'private.txt';secret.write_text('not public')
    file.symlink_to(secret)
    with pytest.raises(ValueError):assets.before(root,now=102)
    assert secret.read_text()=='not public'


def test_does_not_archive_locally_modified_tracked_assets(tmp_path):
    root,folder=repository(tmp_path);file=tracked(root,folder)
    file.write_text('uncommitted private content')
    with pytest.raises(ValueError):assets.before(root,now=100)
    assert file.read_text()=='uncommitted private content'
    assert not list((root/'.local/deploy-assets/files').iterdir())


def test_rejects_symlinked_cache_directory(tmp_path):
    root,folder=repository(tmp_path);tracked(root,folder)
    other=tmp_path/'elsewhere';other.mkdir()
    (root/'.local').symlink_to(other,target_is_directory=True)
    with pytest.raises(ValueError):assets.before(root,now=100)
    assert not list(other.iterdir())


def test_corrupt_cached_bytes_are_never_published(tmp_path):
    root,folder=repository(tmp_path);old=tracked(root,folder)
    assets.before(root,now=100);old.unlink()
    (root/'.local/deploy-assets/files'/old.name).write_text('wrong bytes')
    assets.restore(root,now=101)
    assert not old.exists()


def test_workflow_script_is_valid_shell_and_guards_update_and_health(tmp_path):
    workflow=Path(__file__).resolve().parents[2]/'.github/workflows/deploy.yml'
    text=workflow.read_text();block=text.split('          script: |\n',1)[1]
    shell='\n'.join(line[14:] for line in block.splitlines())+'\n'
    file=tmp_path/'deploy.sh';file.write_text(shell)
    subprocess.run(['sh','-n',str(file)],check=True)
    assert shell.index('trap cleanup_assets EXIT')<shell.index('git merge --ff-only')
    assert shell.index('restore --root',shell.index('git merge --ff-only'))<shell.index('pip install')
    assert 'systemctl is-active --quiet resonant-lab' in shell
    assert '--max-time 3 http://127.0.0.1:8000/api/health' in shell
    assert '"version")=="1.1.0"' in shell
