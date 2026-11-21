"""Bundle construction is isolated to a disposable checkout; no app is launched."""
import importlib.util
from pathlib import Path
import plistlib
import subprocess
import pytest

spec=importlib.util.spec_from_file_location('build_mac_editor',Path(__file__).resolve().parents[2]/'scripts/build_mac_editor.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def checkout(tmp_path):
    root=tmp_path/'checkout';source=root/'editor/macos/ResonantEditor.swift'
    source.parent.mkdir(parents=True);source.write_text('// disposable compiler input')
    return root


def test_build_produces_local_bundle_with_restricted_network_configuration(tmp_path,monkeypatch):
    root=checkout(tmp_path);calls=[]
    monkeypatch.setattr(builder.platform,'system',lambda:'Darwin')
    monkeypatch.setattr(builder.platform,'machine',lambda:'arm64')
    def run(command,**kwargs):
        calls.append(command)
        if command[:2]==['xcrun','swiftc']:
            Path(command[command.index('-o')+1]).write_text('disposable executable')
        return subprocess.CompletedProcess(command,0)
    monkeypatch.setattr(builder.subprocess,'run',run)
    app=builder.build(root)
    assert app==root/'.local/Resonant Editor.app'
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    assert info['ResonantRepositoryPath']==str(root.resolve())
    assert info['LSMinimumSystemVersion']=='13.0'
    assert info['NSAppTransportSecurity']=={'NSAllowsLocalNetworking':True}
    assert 'API_KEY' not in repr(info) and 'TOKEN' not in repr(info)
    assert (app/'Contents/MacOS/ResonantEditor').stat().st_mode&0o111
    assert 'arm64-apple-macosx13.0' in calls[0]
    assert calls[0][calls[0].index('-module-cache-path')+1]==str(root/'.local/swift-module-cache')
    assert calls[1]==['codesign','--force','--sign','-',str(app)]


def test_unsupported_host_does_not_create_an_application(tmp_path,monkeypatch):
    root=checkout(tmp_path);monkeypatch.setattr(builder.platform,'system',lambda:'Linux')
    with pytest.raises(RuntimeError):builder.build(root)
    assert not (root/'.local').exists()


def test_build_refuses_to_follow_a_local_output_symlink(tmp_path,monkeypatch):
    root=checkout(tmp_path);elsewhere=tmp_path/'elsewhere';elsewhere.mkdir()
    (root/'.local').symlink_to(elsewhere,target_is_directory=True)
    monkeypatch.setattr(builder.platform,'system',lambda:'Darwin')
    with pytest.raises(RuntimeError):builder.build(root)
    assert not list(elsewhere.iterdir())


def test_build_refuses_a_symlinked_bundle_without_touching_target(tmp_path,monkeypatch):
    root=checkout(tmp_path);(root/'.local').mkdir()
    elsewhere=tmp_path/'elsewhere';elsewhere.mkdir()
    (root/'.local/Resonant Editor.app').symlink_to(elsewhere,target_is_directory=True)
    monkeypatch.setattr(builder.platform,'system',lambda:'Darwin')
    with pytest.raises(RuntimeError):builder.build(root)
    assert not list(elsewhere.iterdir())
