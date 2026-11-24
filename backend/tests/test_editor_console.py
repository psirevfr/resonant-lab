"""The local file console uses disposable tracked sources."""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from editor import git_askpass, server


@pytest.fixture
def project(tmp_path):
    tmp_path = tmp_path / 'checkout'
    source = tmp_path / 'frontend/src'
    source.mkdir(parents=True)
    (source / 'style.css').write_text('body { color: black; }\n')
    (source / '.env').write_text('test only')
    (source / 'private_token.json').write_text('{}')
    (tmp_path / '.env').write_text('GEMINI_API_KEY=local-test-value-1234\n')
    for args in [('init', '-q'), ('add', 'frontend')]:
        subprocess.run(['git', *args], cwd=tmp_path, check=True)
    editor = server.SiteEditor(tmp_path, 'x'*32)
    try:
        yield editor
    finally:
        editor.close()


def test_console_updates_tracked_source_and_invalidates_publication(project):
    name = 'frontend/src/style.css'
    original = project.open_source(name)
    project.prepared_fingerprint = 'from-previous-build'
    project.job['readyToPublish'] = True
    update = project.save_source(name, 'body { color: green; }\n', original['revision'])
    assert project.open_source(name) == {**update, 'content': 'body { color: green; }\n'}
    assert project.prepared_fingerprint is None
    assert not project.job['readyToPublish']
    assert not server.allowed_path(name)


def test_console_detects_external_changes(project):
    name = 'frontend/src/style.css'
    revision = project.open_source(name)['revision']
    (project.repo / name).write_text('/* external edit */')
    with pytest.raises(server.EditorError) as exc:
        project.save_source(name, '/* console */', revision)
    assert exc.value.status == 409
    assert (project.repo / name).read_text() == '/* external edit */'


def test_console_rejects_private_untracked_and_linked_files(project):
    assert project.source_names() == ['frontend/src/style.css']
    for name in ['.env', 'frontend/src/.env', 'frontend/src/private_token.json',
                 'frontend/src/../index.html', 'frontend/src/untracked.ts']:
        with pytest.raises(server.EditorError):
            project.open_source(name)
    path = project.repo / 'frontend/src/style.css'
    path.unlink()
    path.symlink_to(project.repo / '.env')
    with pytest.raises(server.EditorError):
        project.open_source('frontend/src/style.css')


def test_console_rejects_secrets_and_oversized_content(project):
    file = 'frontend/src/style.css'
    original = project.open_source(file)
    for content in ['local-test-value-1234', 'a' * (server.MAX_SOURCE+1)]:
        with pytest.raises(server.EditorError):
            project.save_source(file, content, original['revision'])
    assert project.open_source(file) == original


def test_console_preserves_presentation_schema(project):
    import json

    path = project.repo / server.SETTINGS_FILE
    original = dict(server.DEFAULT_SETTINGS)
    path.write_text(json.dumps(original))
    subprocess.run(['git', 'add', server.SETTINGS_FILE], cwd=project.repo, check=True)
    revision = project.open_source(server.SETTINGS_FILE)['revision']
    with pytest.raises(server.EditorError):
        project.save_source(server.SETTINGS_FILE, '{}', revision)
    with pytest.raises(server.EditorError):
        project.save_source(server.SETTINGS_FILE, '{', revision)
    project.save_source(server.SETTINGS_FILE, json.dumps({**original, 'brandName':'Essai'}), revision)
    assert project.read_settings()['brandName'] == 'Essai'


def test_selected_element_styles_are_versioned_and_restricted(project):
    element = 'e-' + 'a'*24
    presentation = project.presentation()
    layout = presentation['layout']
    layout['elements'] = {element:{'text':'<b>Texte & couleur</b>', 'color':'#123456', 'background':'#fedcba'}}
    layout['pages'][0]['blocks'] = [{'id':'titre', 'kind':'text', 'x':0, 'y':0, 'w':12, 'h':1,
                                     'text':'Titre', 'color':'#ffffff'}]
    project.save(presentation['settings'], layout, revision=presentation['presentationRevision'])
    assert project.read_layout() == layout
    for invalid in ({'color':'red; background:url(https://example.invalid)'}, {'html':'<script>'}, {'background':False}):
        layout['elements'][element] = invalid
        with pytest.raises(ValueError, match='Mise en page'):
            server.validate_layout(layout)


def test_mac_preview_path_includes_standard_node_installations(monkeypatch):
    monkeypatch.setattr(server.sys, 'platform', 'darwin')
    monkeypatch.setenv('PATH', '/usr/bin')
    assert server.isolated_environment()['PATH'].split(':') == ['/opt/homebrew/bin', '/usr/local/bin', '/usr/bin']


def test_native_credential_prompt_only_answers_github_https(monkeypatch, capsys):
    assert git_askpass.credential_kind("Username for 'https://github.com': ") == 'Username'
    prompt = "Password for 'https://tester@github.com/example/repo.git': "
    assert git_askpass.credential_kind(prompt) == 'Password'
    for host in ('http://github.com', 'https://github.com.example.invalid',
                 'https://github.com:444', 'https://user:value@github.com'):
        assert git_askpass.credential_kind(f"Password for '{host}': ") is None
    monkeypatch.setattr(git_askpass.sys, 'argv', ['git_askpass', prompt])
    def native_dialog(args, **kwargs):
        assert args == ['/usr/bin/osascript', '-', 'Password']
        assert 'with hidden answer' in kwargs['input']
        return subprocess.CompletedProcess(args, 0, stdout='synthetic-answer\n', stderr='')
    monkeypatch.setattr(git_askpass.subprocess, 'run', native_dialog)
    assert git_askpass.main() == 0
    assert capsys.readouterr().out == 'synthetic-answer\n'


def prepare_history(project):
    def git(*args):
        return project.git('-c', 'user.name=Test', '-c', 'user.email=test@local.invalid', *args)
    git('symbolic-ref', 'HEAD', 'refs/heads/main')
    with (project.repo/'.git/info/exclude').open('a') as ignored:
        ignored.write('\n/.env\n')
    git('commit', '-m', 'Base')
    git('remote', 'add', 'origin', 'https://github.com/example/resonant.git')
    git('update-ref', 'refs/remotes/origin/main', 'HEAD')
    return git


def test_review_allows_explicitly_reviewed_code_history(project, monkeypatch):
    git = prepare_history(project)
    path = project.repo / 'frontend/src/style.css'
    path.write_text('body { color: green; }')
    git('commit', '-am', 'Style')
    (project.repo/'test.sh').write_text('#!/bin/sh\nexit 0\n')
    git('add', 'test.sh')
    git('update-index', '--chmod=+x', 'test.sh')
    git('commit', '-m', 'Test script')
    (project.repo/'test.sh').chmod(0o755)

    normal_git = project.git
    network = []
    monkeypatch.setattr(project, 'git', lambda *args, **kw:
                        network.append(args) or '' if args[0] in ('fetch', 'push') else normal_git(*args, **kw))
    review = project.publication_review()
    assert review['count'] == 2
    assert review['paths'] == ['frontend/src/style.css', 'test.sh']

    project.run_job('prepare', None, review['review'])
    assert project.job['readyToPublish']
    assert network == []
    git('commit', '--allow-empty', '-m', 'Unexpected new HEAD')
    with pytest.raises(server.EditorError, match='changé'):
        project.start_job('publish', review['review'])


def test_review_blocks_private_history_and_deleted_secrets(project):
    git = prepare_history(project)
    path = project.repo / 'frontend/src/style.css'
    path.write_text('/* local-test-value-1234 */')
    git('commit', '-am', 'Historical secret')
    path.write_text('body {}')
    git('commit', '-am', 'Removed secret')
    with pytest.raises(server.EditorError, match='secret'):
        project.verify_release(project.publication_review()['review'])
    (project.repo/'frontend/src/user.sqlite').write_bytes(b'PRIVATE')
    git('add', 'frontend/src/user.sqlite')
    git('commit', '-m', 'Private file')
    with pytest.raises(server.EditorError, match='privé'):
        project.publication_review()


def local_origin(project, monkeypatch):
    git = prepare_history(project)
    remote = project.repo.parent/'remote.git'
    git('clone', '--bare', '.', str(remote))
    git('remote', 'set-url', 'origin', str(remote))
    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@local.invalid')
    monkeypatch.setattr(project, 'remote', lambda: 'example/resonant')
    return git, remote


def test_publish_checks_build_and_pushes_all_reviewed_changes(project, monkeypatch):
    git, remote = local_origin(project, monkeypatch)
    base = git('rev-parse', 'HEAD').strip()
    style = project.repo/'frontend/src/style.css'
    style.write_text('body { color: green; }')
    git('commit', '-am', 'Styles already committed')
    (project.repo/'docs').mkdir()
    (project.repo/'docs/usage.md').write_text('Reviewed documentation')
    style.write_text('body { color: orange; }')
    git('add', 'frontend/src/style.css')
    style.write_text('body { color: yellow; }')
    script = project.repo/'test.sh'
    script.write_text('#!/bin/sh\nset -eu\nmkdir -p frontend/dist\ncp frontend/src/style.css frontend/dist/style.css\n')
    script.chmod(0o755)
    git('tag', '-a', 'local-tag', '-m', 'Local')
    git('config', 'push.followTags', 'true')

    review = project.publication_review()
    assert review['count'] == 1
    assert review['paths'] == ['docs/usage.md', 'frontend/src/style.css', 'test.sh']
    project.run_job('publish', None, review['review'])
    assert project.job['status'] == 'succeeded', project.job
    head = git('rev-parse', 'HEAD').strip()
    assert head == git('--git-dir', str(remote), 'rev-parse', 'main').strip()
    assert git('rev-list', '--count', base+'..'+head).strip() == '2'
    assert project.job['publication']['commit'] == head[:12]
    assert git('--git-dir', str(remote), 'show', 'main:frontend/dist/style.css') == 'body { color: yellow; }'
    assert git('--git-dir', str(remote), 'show', 'main:docs/usage.md') == 'Reviewed documentation'
    assert git('--git-dir', str(remote), 'tag') == ''
    assert not git('status', '--porcelain')


def test_workflow_refusal_can_retry_the_same_commit_with_a_fresh_token(project, monkeypatch):
    from threading import Event

    git, remote = local_origin(project, monkeypatch)
    base = git('rev-parse', 'HEAD').strip()
    script = project.repo/'test.sh'
    script.write_text('#!/bin/sh\nprintf run >> .git/test-runs\n')
    script.chmod(0o755)
    workflow = project.repo/'.github/workflows/deploy.yml'
    workflow.parent.mkdir(parents=True)
    workflow.write_text('name: example\n')
    original_git = project.git
    attempts = []
    completed = Event()

    def fake_git(*args, **kwargs):
        if 'push' in args:
            attempts.append(args)
            if 'credential.helper=' not in args:
                raise server.EditorError('remote rejected: refusing to allow a Personal Access Token '
                                         'to update workflow without workflow scope', 409)
        return original_git(*args, **kwargs)

    monkeypatch.setattr(project, 'git', fake_git)
    project.run_job('publish', None, project.publication_review()['review'])
    assert project.job['needsCredential'] and 'Workflows' in project.job['error']
    head = git('rev-parse', 'HEAD').strip()
    assert head != base
    assert git('--git-dir', str(remote), 'rev-parse', 'main').strip() == base
    assert (project.repo/'.git/test-runs').read_text() == 'run'
    future_edit = project.repo/'README.md'
    future_edit.write_text('A change after the failed push')
    with pytest.raises(server.EditorError, match='changé'):
        project.start_job('publish', new_credential=True)
    future_edit.unlink()

    run_job = project.run_job
    def notify_completion(*args):
        try:
            run_job(*args)
        finally:
            completed.set()
    monkeypatch.setattr(project, 'run_job', notify_completion)
    project.start_job('publish', project.publication_review()['review'], new_credential=True)
    assert completed.wait(5)
    assert project.job['status'] == 'succeeded', project.job
    assert len(attempts) == 2
    assert 'credential.helper=' in attempts[-1]
    assert head+':refs/heads/main' in attempts[-1]
    assert git('--git-dir', str(remote), 'rev-parse', 'main').strip() == head
    assert (project.repo/'.git/test-runs').read_text() == 'run'


def test_publish_rejects_changes_after_review_and_during_tests(project, monkeypatch):
    git, remote = local_origin(project, monkeypatch)
    base = git('rev-parse', 'HEAD').strip()
    (project.repo/'README.md').write_text('Reviewed')
    review = project.publication_review()
    (project.repo/'README.md').write_text('Changed after review')
    with pytest.raises(server.EditorError, match='changé'):
        project.start_job('publish', review['review'])

    script = project.repo/'test.sh'
    script.write_text('#!/bin/sh\nprintf unexpected > README.md\n')
    script.chmod(0o755)
    project.run_job('publish', None, project.publication_review()['review'])
    assert project.job['status'] == 'failed'
    assert 'pendant les tests' in project.job['error']
    assert git('--git-dir', str(remote), 'rev-parse', 'main').strip() == base


def test_publish_keeps_remote_changes_and_does_not_send_private_files(project, monkeypatch):
    git, remote = local_origin(project, monkeypatch)
    script = project.repo/'test.sh'
    script.write_text('#!/bin/sh\nexit 0\n')
    script.chmod(0o755)
    (project.repo/'docs').mkdir()
    private = project.repo/'docs/private.sqlite3-shm'
    private.write_text('private data')
    with pytest.raises(server.EditorError, match='privé'):
        project.publication_review()
    private.unlink()
    (project.repo/'README.md').write_text('local-test-value-1234')
    project.run_job('publish', None, project.publication_review()['review'])
    assert project.job['status'] == 'failed'
    assert 'secret' in project.job['error']

    git('add', 'test.sh')
    git('commit', '-m', 'Local change')
    (project.repo/'README.md').unlink()
    base = git('rev-parse', 'origin/main').strip()
    external = git('commit-tree', base+'^{tree}', '-p', base, '-m', 'Remote change').strip()
    git('push', str(remote), external+':refs/heads/main')
    git('update-ref', 'refs/remotes/origin/main', base)
    project.run_job('publish', None, project.publication_review()['review'])
    assert project.job['status'] == 'failed'
    assert 'plus récente' in project.job['error']
    assert git('--git-dir', str(remote), 'rev-parse', 'main').strip() == external


def test_terminal_only_allows_diagnostic_commands(project):
    assert 'git status' in project.terminal('help')['output']
    assert 'style.css' in project.terminal('git status')['output']
    with pytest.raises(server.EditorError, match='indisponible'):
        project.terminal('git status; git push')


def test_editor_detects_disk_edits_and_rejects_stale_saves(project):
    before=project.presentation()
    project.save({**before['settings'],'brandName':'Nouveau nom'})
    after=project.presentation()
    assert before['presentationRevision']!=after['presentationRevision']
    assert project.progress()['presentationRevision']==after['presentationRevision']
    with pytest.raises(server.EditorError) as conflict:
        project.save({**before['settings'],'radius':9},revision=before['presentationRevision'])
    assert conflict.value.status==409
    assert project.read_settings()['brandName']=='Nouveau nom'
    updated=project.save({**after['settings'],'radius':9},revision=after['presentationRevision'])
    assert updated['settings']['radius']==9
