#!/usr/bin/env python3
"""Self-host a pinned Python/WASM runtime and ONLY allowlisted numerical sources."""
import argparse,hashlib,json
from pathlib import Path
from urllib.request import urlopen
import zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='314.0.7'
BASE=f'https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/'
MODULES=('__init__','schema','audio','blocks','graph','analysis','metrics','identify','modal_fit','attack_fit','impact','compact','instrument','texture','shared_envelopes','nonlinear_fit','optimization','compute')
CORE=('pyodide.mjs','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json')


def download(name,target,digest=None):
    if '/' in name or '\\' in name:raise ValueError('Invalid runtime filename')
    if target.is_file() and (digest is None or hashlib.sha256(target.read_bytes()).hexdigest()==digest):return
    with urlopen(BASE+name,timeout=60) as response:data=response.read(100_000_000)
    if digest and hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Runtime integrity mismatch')
    tmp=target.with_suffix(target.suffix+'.tmp');tmp.write_bytes(data);tmp.replace(target)


def prepare(destination,network=False):
    destination.mkdir(parents=True,exist_ok=True)
    if network:download('pyodide-lock.json',destination/'pyodide-lock.json')
    selected=set();lock=None
    if (destination/'pyodide-lock.json').is_file():
        lock=json.loads((destination/'pyodide-lock.json').read_text())
        def select(name):
            name=name.replace('_','-').lower()
            if name in selected:return
            selected.add(name)
            for dependency in lock['packages'][name]['depends']:select(dependency)
        for name in ('numpy','scipy','pydantic'):select(name)
        if network:
            for name in CORE:download(name,destination/name)
            for name in sorted(selected):
                p=lock['packages'][name];download(p['file_name'],destination/p['file_name'],p['sha256'])
    # Deterministic archive, no repository sweep, no auth/app/credentials/user data.
    archive=destination/'numerical.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in MODULES:
            data=(ROOT/'backend/lab'/f'{name}.py').read_bytes()
            info=zipfile.ZipInfo(f'lab/{name}.py',date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
    allowed=set(CORE)|{'numerical.zip'}|{lock['packages'][name]['file_name'] for name in selected}
    files={name:{'bytes':(destination/name).stat().st_size,'sha256':hashlib.sha256((destination/name).read_bytes()).hexdigest()} for name in sorted(allowed) if (destination/name).is_file()}
    ready=lock is not None and allowed<=set(files) and all(files[lock['packages'][n]['file_name']]['sha256']==lock['packages'][n]['sha256'] for n in selected)
    manifest={'runtime_version':VERSION,'algorithm_version':'shared-python-v1','source_sha256':files['numerical.zip']['sha256'],'files':files,'download_bytes':sum(f['bytes'] for f in files.values()),'ready':ready}
    temp=destination/'manifest.json.tmp';temp.write_text(json.dumps(manifest,sort_keys=True));temp.replace(destination/'manifest.json')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');parser.add_argument('--destination',type=Path,default=ROOT/'.local/compute-runtime')
    args=parser.parse_args();m=prepare(args.destination,args.download)
    print(json.dumps({'ready':m['ready'],'runtime_version':VERSION,'download_bytes':m['download_bytes'],'source_sha256':m['source_sha256']}))
