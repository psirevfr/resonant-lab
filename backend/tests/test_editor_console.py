"""The local file console uses disposable tracked sources."""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from editor import server


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


def test_mac_preview_path_includes_standard_node_installations(monkeypatch):
    monkeypatch.setattr(server.sys, 'platform', 'darwin')
    monkeypatch.setenv('PATH', '/usr/bin')
    assert server.isolated_environment()['PATH'].split(':') == ['/opt/homebrew/bin', '/usr/local/bin', '/usr/bin']


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
    with pytest.raises(server.EditorError, match='Vérification'):
        project.ensure_publishable()
    review = project.publication_review()
    assert review['count'] == 2
    assert review['paths'] == ['frontend/src/style.css', 'test.sh']

    project.run_job('prepare', None, review['review'])
    assert project.job['readyToPublish']
    assert network == []
    git('commit', '--allow-empty', '-m', 'Unexpected new HEAD')
    with pytest.raises(server.EditorError, match='changé'):
        project.ensure_publishable(review['review'])


def test_review_blocks_private_history_and_deleted_secrets(project):
    git = prepare_history(project)
    path = project.repo / 'frontend/src/style.css'
    path.write_text('/* local-test-value-1234 */')
    git('commit', '-am', 'Historical secret')
    path.write_text('body {}')
    git('commit', '-am', 'Removed secret')
    with pytest.raises(server.EditorError, match='secret'):
        project.scan_secrets(project.publication_review()['review'])
    (project.repo/'frontend/src/user.sqlite').write_bytes(b'PRIVATE')
    git('add', 'frontend/src/user.sqlite')
    git('commit', '-m', 'Private file')
    with pytest.raises(server.EditorError, match='privé'):
        project.publication_review()


def test_terminal_only_allows_diagnostic_commands(project):
    assert 'git status' in project.terminal('help')['output']
    assert 'style.css' in project.terminal('git status')['output']
    with pytest.raises(server.EditorError, match='indisponible'):
        project.terminal('git status; git push')
