"""The local file console uses disposable tracked sources."""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from editor import server


@pytest.fixture
def project(tmp_path):
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
