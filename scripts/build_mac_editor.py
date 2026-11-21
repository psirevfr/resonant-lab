#!/usr/bin/env python3
"""Build a native local editor app inside this checkout's ignored .local folder.

Requires macOS command-line developer tools. Does not install in /Applications,
publish, sign with an account, or contact the production server.
"""
import argparse
from pathlib import Path
import platform
import plistlib
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def app_info(root):
    return {
        'CFBundleName':'Résonant Éditeur',
        'CFBundleDisplayName':'Résonant Éditeur',
        'CFBundleIdentifier':'local.resonant.editor',
        'CFBundleExecutable':'ResonantEditor',
        'CFBundlePackageType':'APPL',
        'CFBundleShortVersionString':'1.1.0',
        'CFBundleVersion':'1',
        'LSMinimumSystemVersion':'13.0',
        'NSHighResolutionCapable':True,
        'NSPrincipalClass':'NSApplication',
        'NSAppTransportSecurity':{'NSAllowsLocalNetworking':True},
        'ResonantRepositoryPath':str(Path(root).resolve()),
        'NSHumanReadableCopyright':'© r0m1 - étudiant en PSI',
    }


def build(root=ROOT):
    root=Path(root).resolve()
    if platform.system()!='Darwin':raise RuntimeError('La création de l’application nécessite macOS.')
    source=root/'editor/macos/ResonantEditor.swift'
    if not source.is_file():raise RuntimeError('Le lanceur Swift est absent du projet.')
    local=root/'.local'
    if local.is_symlink():raise RuntimeError('Le dossier .local ne doit pas être un lien symbolique.')
    local.mkdir(exist_ok=True)
    app=local/'Resonant Editor.app'
    for folder in (app,app/'Contents',app/'Contents/MacOS',local/'swift-module-cache'):
        if folder.is_symlink():raise RuntimeError('Un dossier de construction est un lien symbolique.')
        folder.mkdir(exist_ok=True)
    executable=app/'Contents/MacOS/ResonantEditor'
    if any(p.is_symlink() for p in (executable,app/'Contents/Info.plist',app/'Contents/PkgInfo')):raise RuntimeError('Un fichier de construction est un lien symbolique.')
    architecture='arm64' if platform.machine()=='arm64' else 'x86_64'
    subprocess.run(['xcrun','swiftc','-swift-version','5','-parse-as-library','-O','-target',architecture+'-apple-macosx13.0','-module-cache-path',str(local/'swift-module-cache'),'-framework','AppKit','-framework','WebKit','-framework','Security',str(source),'-o',str(executable)],cwd=root,check=True)
    with (app/'Contents/Info.plist').open('wb') as file:plistlib.dump(app_info(root),file)
    executable.chmod(0o755)
    (app/'Contents/PkgInfo').write_bytes(b'APPL????')
    # Ad-hoc signing is local and requires no certificate or Apple account.
    subprocess.run(['codesign','--force','--sign','-',str(app)],check=True,capture_output=True)
    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:print(build())
    except (OSError,RuntimeError,subprocess.CalledProcessError) as error:
        raise SystemExit('Construction interrompue : '+str(error)) from None
