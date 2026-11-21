#!/usr/bin/env python3
"""Retain a bounded set of public, versioned Vite chunks during an in-place update.

Only tracked hashed JS/CSS and files named in this helper's private manifest are
managed. No database, upload, unknown public file or symbolic link is copied.
This reduces lazy-import failures; it is not an atomic release mechanism.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

MAX_AGE=7*24*3600
MAX_BYTES=128*1024*1024
MAX_FILES=512
NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,159}-[A-Za-z0-9_-]{8}\.(?:js|css)')


def directory(path):
    if path.is_symlink():raise ValueError('Symbolic deployment directory rejected.')
    path.mkdir(exist_ok=True)
    if not path.is_dir():raise ValueError('Invalid deployment directory.')


def locations(root):
    root=Path(root).resolve()
    for parent in (root/'frontend',root/'frontend/dist',root/'frontend/dist/assets',root/'.local',root/'.local/deploy-assets',root/'.local/deploy-assets/files'):
        directory(parent)
    (root/'.local/deploy-assets').chmod(0o700)
    (root/'.local/deploy-assets/files').chmod(0o700)
    return root/'frontend/dist/assets',root/'.local/deploy-assets/files',root/'.local/deploy-assets/manifest.json'


def regular(path):
    if path.is_symlink():raise ValueError('Symbolic deployment file rejected.')
    return path.is_file()


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def atomic_copy(source,target,*,private=False):
    if target.is_symlink():raise ValueError('Symbolic deployment file rejected.')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as out:
            temporary=Path(out.name)
            with source.open('rb') as incoming:
                for block in iter(lambda:incoming.read(1024*1024),b''):out.write(block)
        temporary.chmod(0o600 if private else 0o644)
        os.replace(temporary,target)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def load_manifest(path):
    if not regular(path):return {}
    if path.stat().st_size>256*1024:raise ValueError('Oversized asset manifest.')
    data=json.loads(path.read_text())
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('files'),dict) or len(data['files'])>MAX_FILES:raise ValueError('Invalid asset manifest.')
    for name,meta in data['files'].items():
        if not NAME.fullmatch(name) or not isinstance(meta,dict):raise ValueError('Invalid cached asset name.')
        if not isinstance(meta.get('bytes'),int) or not 0<=meta['bytes']<=MAX_BYTES:raise ValueError('Invalid cached asset size.')
        if not isinstance(meta.get('seen_at'),(int,float)) or not math.isfinite(meta['seen_at']):raise ValueError('Invalid asset date.')
        if not isinstance(meta.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',meta['sha256']):raise ValueError('Invalid asset digest.')
    return data['files']


def save_manifest(path,entries):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as f:
            temporary=Path(f.name)
            json.dump({'version':1,'files':entries},f,sort_keys=True,allow_nan=False)
        temporary.chmod(0o600);os.replace(temporary,path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def tracked_assets(root):
    result=subprocess.run(['git','ls-files','-z','--','frontend/dist/assets'],cwd=root,check=True,capture_output=True)
    paths=result.stdout.decode().split('\0');names=set()
    for raw in paths:
        path=Path(raw)
        if path.parent==Path('frontend/dist/assets') and NAME.fullmatch(path.name):names.add(path.name)
    return names


def ensure_clean_assets(root):
    result=subprocess.run(['git','diff','--name-only','-z','--','frontend/dist/assets'],cwd=root,check=True,capture_output=True)
    if result.stdout:raise ValueError('Tracked assets have local changes; deployment stopped.')


def bounded(entries,now,max_age,max_bytes,max_files):
    keep={};size=0
    for name,meta in sorted(entries.items(),key=lambda item:(-item[1]['seen_at'],item[0])):
        if now-meta['seen_at']<=max_age and len(keep)<max_files and size+meta['bytes']<=max_bytes:
            keep[name]=meta;size+=meta['bytes']
    return keep


def prune(entries,cache,now,max_age,max_bytes,max_files):
    valid={name:meta for name,meta in entries.items() if regular(cache/name) and (cache/name).stat().st_size==meta['bytes']}
    keep=bounded(valid,now,max_age,max_bytes,max_files)
    for name in entries.keys()-keep.keys():
        if regular(cache/name):(cache/name).unlink()
    return keep


def before(root,*,now=None,max_age=MAX_AGE,max_bytes=MAX_BYTES,max_files=MAX_FILES):
    now=time.time() if now is None else now
    root=Path(root).resolve();assets,cache,manifest=locations(root)
    previous=load_manifest(manifest);tracked=tracked_assets(root)
    ensure_clean_assets(root)
    entries=prune(previous,cache,now,max_age,max_bytes,max_files)
    fresh={}
    for name in sorted(tracked):
        source=assets/name
        if not regular(source) or source.stat().st_size>max_bytes:continue
        fresh[name]={'seen_at':now,'bytes':source.stat().st_size,'sha256':digest(source)}
    entries=bounded({**entries,**fresh},now,max_age,max_bytes,max_files)
    # Evict before copying, so a large release cannot fill the disk first and
    # only then discover the retention limit. One atomic-copy temporary remains.
    for name in previous.keys()-entries.keys():
        if regular(cache/name):(cache/name).unlink()
    for name in fresh.keys()&entries.keys():
        atomic_copy(assets/name,cache/name,private=True)
    save_manifest(manifest,entries)
    removed=0
    # Known restored files must be absent before a future checkout can track the
    # same names. Preserve a locally modified file rather than deleting it.
    for name,meta in previous.items():
        path=assets/name
        if name not in tracked and regular(path) and digest(path)==meta['sha256']:
            path.unlink();removed+=1
    return {'cached':len(entries),'bytes':sum(v['bytes'] for v in entries.values()),'temporarily_removed':removed}


def restore(root,*,now=None,max_age=MAX_AGE,max_bytes=MAX_BYTES,max_files=MAX_FILES):
    now=time.time() if now is None else now
    root=Path(root).resolve();assets,cache,manifest=locations(root)
    entries=prune(load_manifest(manifest),cache,now,max_age,max_bytes,max_files)
    restored=0
    for name,meta in entries.items():
        source=cache/name;target=assets/name
        if target.is_symlink():raise ValueError('Symbolic public asset rejected.')
        if target.exists():continue
        if digest(source)!=meta['sha256']:continue
        atomic_copy(source,target);restored+=1
    save_manifest(manifest,entries)
    return {'cached':len(entries),'restored':restored}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('before','restore'))
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    print(json.dumps((before if args.phase=='before' else restore)(args.root)))
