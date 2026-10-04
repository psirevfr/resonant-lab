import importlib.util
from pathlib import Path
import re
import sqlite3
import pytest

spec=importlib.util.spec_from_file_location('rotate_api_key',Path(__file__).resolve().parents[2]/'scripts/rotate_api_key.py')
rotation=importlib.util.module_from_spec(spec);spec.loader.exec_module(rotation)


def configuration(tmp_path,secret='a'*48):
    db=tmp_path/'users.sqlite';env=tmp_path/'private.env'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE users (id INTEGER PRIMARY KEY,username TEXT UNIQUE,api_key TEXT)')
        c.executemany('INSERT INTO users VALUES (?,?,?)',[(1,'owner','old-test-value'),(2,'other','other-test-value')])
    env.write_text(f'RESONANT_DB_PATH={db}\nRESONANT_SESSION_SECRET={secret}\nRESONANT_LAB_API_KEY=old-test-value\nRESONANT_CONCURRENCY=1\n')
    return db,env


def test_rotation_updates_only_owner_and_private_configuration(tmp_path):
    db,env=configuration(tmp_path)
    rotation.rotate(env,'owner')
    key=rotation.setting(env.read_text(),'RESONANT_LAB_API_KEY')
    assert re.fullmatch(r'res_live_[a-f0-9]{64}',key)
    assert rotation.setting(env.read_text(),'RESONANT_SESSION_SECRET')=='a'*48
    assert env.stat().st_mode&0o777==0o600
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT api_key FROM users WHERE id=1').fetchone()[0]==key
        assert c.execute('SELECT api_key FROM users WHERE id=2').fetchone()[0]=='other-test-value'
    rotation.rotate(env,'owner')
    assert rotation.setting(env.read_text(),'RESONANT_LAB_API_KEY')!=key


def test_rotation_rejects_unknown_user_without_changes(tmp_path):
    db,env=configuration(tmp_path);before=env.read_text()
    with pytest.raises(ValueError):rotation.rotate(env,'unknown')
    assert env.read_text()==before
    with sqlite3.connect(db) as c:assert c.execute('SELECT api_key FROM users WHERE id=1').fetchone()[0]=='old-test-value'


def test_rotation_file_failure_rolls_back_database(tmp_path,monkeypatch):
    db,env=configuration(tmp_path);before=env.read_text()
    def fail(*args):raise OSError('simulated')
    monkeypatch.setattr(rotation,'private_write',fail)
    with pytest.raises(OSError):rotation.rotate(env,'owner')
    assert env.read_text()==before
    with sqlite3.connect(db) as c:assert c.execute('SELECT api_key FROM users WHERE id=1').fetchone()[0]=='old-test-value'


def test_rotation_bootstraps_session_secret_without_exposing_it(tmp_path):
    db,env=configuration(tmp_path,'REPLACE_WITH_PRIVATE_SECRET')
    rotation.rotate(env,'owner')
    secret=rotation.setting(env.read_text(),'RESONANT_SESSION_SECRET')
    assert len(secret)>=32 and not secret.startswith('REPLACE_WITH_')


def test_rotation_refuses_to_write_a_secret_into_versioned_example():
    example=Path(__file__).resolve().parents[2]/'deploy/resonant.env.example'
    before=example.read_text()
    with pytest.raises(ValueError):rotation.rotate(example,'owner')
    assert example.read_text()==before
