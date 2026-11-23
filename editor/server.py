#!/usr/bin/env python3
"""Loopback-only site editor with a restricted frontend file console.

The native launcher supplies RESONANT_EDITOR_TOKEN and performs the first GET
with X-Editor-Token. Preparing and publishing are separate explicit operations.
Only siteSettings.json, built frontend assets and the TypeScript cache can be
committed. Application/user databases and production environment are never used
by the preview. This module itself requires only the Python standard library.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import hmac
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import math
import os
from pathlib import Path
import re
import secrets
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

try:
    from .layout import LAYOUT_FILE, validate_layout
except ImportError:
    from layout import LAYOUT_FILE, validate_layout

SETTINGS_FILE = 'frontend/src/siteSettings.json'
ALLOWED_EXACT = {SETTINGS_FILE, LAYOUT_FILE, 'frontend/tsconfig.tsbuildinfo'}
MAX_BODY = 65_536
MAX_SOURCE = 262_144
SOURCE_SUFFIXES = {'.css', '.html', '.js', '.json', '.svg', '.ts', '.tsx'}
MAX_COMMAND_OUTPUT = 8_000_000
DEFAULT_SETTINGS = {
    'version': 1, 'brandName': 'résonant',
    'signature': 'r0m1 - étudiant en PSI', 'home': 'atelier',
    'labels': {'analyse': 'Analyse du son', 'atelier': 'Atelier Arduino'},
    'colors': {'background': '#111719', 'surface': '#18201f',
               'accent': '#b4ed79', 'text': '#dbe4e5'},
    'fontScale': 1, 'radius': 8,
    'welcome': 'Deux espaces pour donner vie à vos idées.'
}


class EditorError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def validate_settings(value):
    if type(value) is not dict or set(value) != set(DEFAULT_SETTINGS):
        raise EditorError('Format de réglages invalide.')
    if type(value['version']) is not int or value['version'] != 1:
        raise EditorError('Version des réglages non prise en charge.')

    def text(raw, limit, multiline=False):
        if not isinstance(raw, str) or not raw.strip() or len(raw) > limit:
            raise EditorError('Un texte est vide ou trop long.')
        if any(ord(c) < 32 and not (multiline and c == '\n') for c in raw):
            raise EditorError('Un texte contient un caractère interdit.')
        return raw.strip()

    if value['home'] not in ('atelier', 'analyse'):
        raise EditorError('Choisissez l’atelier ou l’analyse comme accueil.')
    labels = value['labels']
    colors = value['colors']
    if type(labels) is not dict or set(labels) != {'atelier', 'analyse'}:
        raise EditorError('Noms des espaces invalides.')
    if type(colors) is not dict or set(colors) != set(DEFAULT_SETTINGS['colors']):
        raise EditorError('Palette invalide.')
    if any(not isinstance(c, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', c)
           for c in colors.values()):
        raise EditorError('Les couleurs doivent utiliser le format #rrggbb.')
    scale = value['fontScale']
    if type(scale) not in (int, float) or not math.isfinite(scale) or not .9 <= scale <= 1.15:
        raise EditorError('La taille du texte doit être comprise entre 90 et 115 %.')
    if type(value['radius']) is not int or not 0 <= value['radius'] <= 18:
        raise EditorError('L’arrondi doit être compris entre 0 et 18.')
    return {
        'version': 1, 'brandName': text(value['brandName'], 40),
        'signature': text(value['signature'], 100), 'home': value['home'],
        'labels': {k: text(labels[k], 32) for k in ('atelier', 'analyse')},
        'colors': {k: colors[k].lower() for k in DEFAULT_SETTINGS['colors']},
        'fontScale': scale, 'radius': value['radius'],
        'welcome': text(value['welcome'], 240, multiline=True)
    }


def allowed_path(name):
    if not isinstance(name, str) or '\\' in name or '\x00' in name:
        return False
    parts = name.split('/')
    if any(p in ('', '.', '..') for p in parts):
        return False
    return name in ALLOWED_EXACT or name.startswith('frontend/dist/')


def github_identity(url):
    """Accept one GitHub repository, never URL credentials or other hosts."""
    match = re.fullmatch(r'git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)', url)
    if match:
        owner, repo = match.groups()
    else:
        try:
            parsed = urlsplit(url)
            if (parsed.scheme not in ('https', 'ssh') or parsed.hostname != 'github.com'
                    or parsed.password or parsed.query or parsed.fragment or parsed.port
                    or parsed.username not in ((None,) if parsed.scheme == 'https' else ('git',))):
                raise ValueError
            path = re.fullmatch(r'/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)', parsed.path)
            if not path:
                raise ValueError
            owner, repo = path.groups()
        except ValueError:
            raise EditorError('La destination doit être un dépôt GitHub sans identifiants dans l’URL.')
    if repo.endswith('.git'):
        repo = repo[:-4]
    if not owner or not repo or owner in ('.', '..') or repo in ('.', '..'):
        raise EditorError('Destination GitHub invalide.')
    return f'{owner}/{repo}'.lower()


def isolated_environment():
    # Deliberately no API keys, OAuth tokens, RESONANT_* production variables,
    # PYTHONPATH inherited from another checkout, or GIT_SSH_COMMAND overrides.
    keep = ('PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'TMPDIR',
            'SSH_AUTH_SOCK', 'SYSTEMROOT', 'TZ')
    env = {key: os.environ[key] for key in keep if key in os.environ}
    # Apps opened from Finder or Spotlight do not inherit shell startup files.
    if sys.platform == 'darwin':
        paths = ['/opt/homebrew/bin', '/usr/local/bin', *env.get('PATH', os.defpath).split(os.pathsep)]
        env['PATH'] = os.pathsep.join(dict.fromkeys(path for path in paths if os.path.isabs(path)))
    env.update({'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
                'VECLIB_MAXIMUM_THREADS': '1', 'GIT_TERMINAL_PROMPT': '0'})
    return env


def secret_values(repo):
    values = [v for k, v in os.environ.items()
              if len(v) >= 12 and any(word in k.upper() for word in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY'))]
    path = repo / '.env'
    if path.is_file() and path.stat().st_size <= MAX_BODY:
        for line in path.read_text(errors='replace').splitlines():
            if '=' not in line or line.lstrip().startswith('#'):
                continue
            key, value = line.split('=', 1)
            value = value.strip().strip('\"\'')
            if len(value) >= 12 and any(s in key.upper() for s in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY')):
                values.append(value)
    return tuple(set(values))


def sanitize(text, values=()):
    text = str(text)
    for value in values:
        text = text.replace(value, '[secret masqué]')
    text = re.sub(r'(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_-]{25,}|res_live_[A-Za-z0-9]{20,})', '[secret masqué]', text)
    return re.sub(r'(https?://)[^\s/@]+(?::[^\s/@]*)?@', r'\1[identifiants masqués]@', text)


def contains_secret(data, values):
    if re.search(rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_-]{25,}|res_live_[A-Za-z0-9]{20,}', data):
        return True
    return any(value.encode() in data for value in values)


class ProcessRunner:
    """Bounded subprocess groups, no shell; injectable in tests."""
    def __init__(self):
        self.lock = threading.Lock()
        self.processes = set()

    @staticmethod
    def stop(process):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)

    def close(self):
        with self.lock:
            processes = list(self.processes)
        for process in processes:
            self.stop(process)

    def run(self, args, *, cwd, env, timeout=20, on_line=None, cancel=None, raw=False):
        process = subprocess.Popen([str(a) for a in args], cwd=cwd, env=env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        with self.lock:
            self.processes.add(process)
        output = bytearray()
        pending = b''
        deadline = time.monotonic() + timeout
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    if cancel is not None and cancel.is_set():
                        raise EditorError('Opération arrêtée.', 409)
                    if time.monotonic() >= deadline:
                        raise EditorError('Cette opération a dépassé sa durée autorisée.', 409)
                    if not selector.select(.1):
                        continue
                    chunk = os.read(process.stdout.fileno(), 8192)
                    if not chunk:
                        break
                    output.extend(chunk)
                    if len(output) > MAX_COMMAND_OUTPUT:
                        raise EditorError('La sortie de l’opération est trop volumineuse.', 409)
                    if on_line:
                        pending += chunk
                        lines = pending.split(b'\n')
                        pending = lines.pop()
                        for line in lines:
                            on_line(line.decode(errors='replace'))
                        if len(pending) > 4096:
                            on_line(pending[:600].decode(errors='replace'))
                            pending = b''
            code = process.wait(timeout=2)
            if on_line and pending:
                on_line(pending.decode(errors='replace'))
            if code:
                raise EditorError('La commande a échoué (code '+str(code)+'). '+output[-1200:].decode(errors='replace'), 409)
            return bytes(output) if raw else output.decode(errors='replace')
        finally:
            if process.poll() is None:
                self.stop(process)
            if process.stdout:
                process.stdout.close()
            with self.lock:
                self.processes.discard(process)


class SiteEditor:
    def __init__(self, repo, token, *, runner=None, ui_root=None):
        given = Path(repo)
        if not given.is_absolute() or not given.is_dir():
            raise EditorError('Choisissez le dossier absolu du dépôt Résonant.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', token or ''):
            raise EditorError('Jeton local absent ou invalide.')
        self.repo = given.resolve()
        self.token = token
        self.cookie = os.environ.get('RESONANT_EDITOR_RESTART_COOKIE') or secrets.token_urlsafe(32)
        self.origin = ''
        self.cookie_name = 'resonant_editor'
        self.ui_root = Path(ui_root) if ui_root else Path(__file__).resolve().parent/'ui'
        self.runner = runner or ProcessRunner()
        self.env = isolated_environment()
        self.secrets = secret_values(self.repo)
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.job = {'id': None, 'status': 'idle', 'stage': '', 'log': [],
                    'error': None, 'readyToPublish': False}
        self.prepared_fingerprint = None
        self.prepared_review = None
        self.prepared_head = None
        self.restart_requested = False
        self.initial_editor_revision = self.editor_revision()
        self.preview_url = None
        self.preview_error = None
        self.preview_starting = False
        self.preview_ports = ()
        self.preview_secret = os.environ.get('RESONANT_EDITOR_RESTART_PREVIEW_SECRET') or secrets.token_urlsafe(48)
        self.preview_processes = []
        root = self.git('rev-parse', '--show-toplevel').strip()
        if Path(root).resolve() != self.repo:
            raise EditorError('Le dossier choisi doit être la racine du dépôt Git.')
        self.read_settings()

    def git(self, *args, timeout=20, on_line=None, raw=False):
        return self.runner.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                                '-c', 'commit.gpgsign=false', *args],
                               cwd=self.repo, env=self.env, timeout=timeout,
                               on_line=on_line, cancel=self.stop_event, raw=raw)

    def safe_path(self, relative):
        if not allowed_path(relative):
            raise EditorError('Ce fichier ne peut pas être modifié par l’éditeur.')
        return self.project_path(relative)

    def project_path(self, relative):
        path = self.repo / relative
        if not path.is_relative_to(self.repo) or '..' in path.parts:
            raise EditorError('Chemin hors du projet refusé.')
        cursor = path
        while cursor != self.repo:
            if cursor.is_symlink():
                raise EditorError('Un fichier du site utilise un lien symbolique non autorisé.')
            cursor = cursor.parent
        if not path.resolve().is_relative_to(self.repo):
            raise EditorError('Chemin hors du projet refusé.')
        return path

    def source_names(self):
        names = self.git('ls-files', '-z', '--', 'frontend/index.html', 'frontend/src').split('\0')
        return sorted({name for name in names if name and Path(name).suffix in SOURCE_SUFFIXES
                       and all(not part.startswith('.') for part in Path(name).parts)
                       and not re.search(r'secret|credential|token|password|api[-_]?key', Path(name).stem, re.I)})

    def source_file(self, name):
        if not isinstance(name, str) or name not in self.source_names():
            raise EditorError('Fichier source indisponible.', 404)
        path = self.project_path(name)
        if not path.is_file() or path.stat().st_nlink != 1:
            raise EditorError('Fichier source indisponible.', 404)
        with path.open('rb') as source:
            data = source.read(MAX_SOURCE + 1)
        if len(data) > MAX_SOURCE or b'\0' in data or contains_secret(data, secret_values(self.repo)):
            raise EditorError('Ce fichier est trop volumineux ou contient des données protégées.', 413)
        return path, data

    def open_source(self, name):
        with self.lock:
            _, data = self.source_file(name)
            try:
                return {'content': data.decode('utf-8'), 'revision': hashlib.sha256(data).hexdigest()}
            except UnicodeError:
                raise EditorError('Seuls les fichiers texte UTF-8 sont disponibles.', 415) from None

    def save_source(self, name, content, revision):
        if not isinstance(content, str) or '\0' in content:
            raise EditorError('Texte invalide.')
        try:
            data = content.encode('utf-8')
        except UnicodeError:
            raise EditorError('Texte UTF-8 invalide.') from None
        if len(data) > MAX_SOURCE or contains_secret(data, secret_values(self.repo)):
            raise EditorError('Le texte est trop volumineux ou contient un secret potentiel.', 413)
        with self.lock:
            if self.job['status'] == 'running':
                raise EditorError('Attendez la fin de l’opération en cours.', 409)
            path, previous = self.source_file(name)
            if revision != hashlib.sha256(previous).hexdigest():
                raise EditorError('Le fichier a changé depuis son ouverture. Rechargez-le avant d’enregistrer.', 409)
            if path.suffix == '.json':
                try:
                    parsed = json.loads(content)
                    if name == SETTINGS_FILE:
                        validate_settings(parsed)
                    elif name == LAYOUT_FILE:
                        validate_layout(parsed)
                except ValueError:
                    raise EditorError('Le fichier JSON est invalide.') from None
                if name in (SETTINGS_FILE, LAYOUT_FILE) and len(data) > MAX_BODY:
                    raise EditorError('Le document de présentation dépasse la taille autorisée.', 413)
            self.write_document(path, data, mode=path.stat().st_mode & 0o777)
            self.prepared_fingerprint = None
            self.job['readyToPublish'] = False
        return {'revision': hashlib.sha256(data).hexdigest()}

    def read_settings(self):
        path = self.safe_path(SETTINGS_FILE)
        if not path.is_file():
            return validate_settings(json.loads(json.dumps(DEFAULT_SETTINGS)))
        if path.stat().st_size > MAX_BODY:
            raise EditorError('Le fichier des réglages est trop volumineux.')
        try:
            return validate_settings(json.loads(path.read_text()))
        except (ValueError, UnicodeError):
            raise EditorError('Le fichier des réglages est invalide.')

    def read_layout(self):
        path=self.safe_path(LAYOUT_FILE)
        if not path.is_file():
            return {'version':1,'pages':[{'id':i,'name':'','parent':None,'blocks':[]} for i in ('analyse','atelier')],'bank':[],'plots':{}}
        try:
            if path.stat().st_size>MAX_BODY:raise ValueError('Mise en page trop volumineuse.')
            return validate_layout(json.loads(path.read_text()))
        except (ValueError, UnicodeError) as error:
            raise EditorError('Le fichier de mise en page est invalide.') from error

    @staticmethod
    def write_document(path, data, mode=0o644):
        path.parent.mkdir(parents=True,exist_ok=True)
        fd, temporary=tempfile.mkstemp(prefix='.site-document-',dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary,mode)
            os.replace(temporary,path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def save(self, value, layout=None, revision=None):
        settings=validate_settings(value)
        try:
            if layout is not None:validate_layout(layout)
        except ValueError as error:
            raise EditorError(str(error)) from error
        with self.lock:
            if self.job['status']=='running':
                raise EditorError('Attendez la fin de l’opération en cours.',409)
            if revision is not None and revision != self.presentation()['presentationRevision']:
                raise EditorError('La présentation vient d’être actualisée.', 409)
            documents={SETTINGS_FILE:settings}
            if layout is not None:documents[LAYOUT_FILE]=layout
            documents={self.safe_path(relative):document for relative,document in documents.items()}
            backups={}
            try:
                for path, document in documents.items():
                    backups[path]=path.read_bytes() if path.is_file() else None
                    encoded=(json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
                    self.write_document(path,encoded)
            except OSError:
                for path,previous in backups.items():
                    if previous is None:path.unlink(missing_ok=True)
                    else:self.write_document(path,previous)
                raise
            self.prepared_fingerprint=None
            self.job['readyToPublish']=False
            return {'ok':True,**self.presentation()}

    def remote(self):
        fetch = self.git('remote', 'get-url', '--all', 'origin').strip().splitlines()
        push = self.git('remote', 'get-url', '--push', '--all', 'origin').strip().splitlines()
        if len(fetch) != 1 or len(push) != 1:
            raise EditorError('Configurez une seule destination GitHub origin.')
        first, second = github_identity(fetch[0]), github_identity(push[0])
        if first != second:
            raise EditorError('Les destinations de lecture et publication GitHub doivent être identiques.')
        return first

    def terminal(self, command):
        commands = {
            'git status': ('status', '--short', '--branch'),
            'git log': ('log', '-8', '--oneline'),
            'git diff --stat': ('diff', '--stat'),
            'git diff --cached --stat': ('diff', '--cached', '--stat'),
        }
        if not isinstance(command, str) or len(command) > 80:
            raise EditorError('Commande invalide.')
        if command == 'help':
            return {'output': '\n'.join([*commands, 'python --version', 'node --version', 'clear'])}
        if command in commands:
            output = self.git(*commands[command], timeout=5)
        elif command in ('python --version', 'node --version'):
            tool = sys.executable if command.startswith('python') else shutil.which('node', path=self.env.get('PATH'))
            if not tool:
                raise EditorError('Node.js est introuvable.')
            output = self.runner.run([tool, '--version'], cwd=self.repo, env=self.env, timeout=5, cancel=self.stop_event)
        else:
            raise EditorError('Commande indisponible ici. Saisissez help.')
        return {'output': sanitize(output.strip(), self.secrets)[:12_000] or 'Aucun changement.'}

    def repository_state(self):
        branch = self.git('branch', '--show-current').strip()
        records = self.git('status', '--porcelain=v1', '-z', '--untracked-files=all').split('\0')
        dirty = set()
        i = 0
        while i < len(records):
            record = records[i]
            i += 1
            if not record:
                continue
            dirty.add(record[3:])
            if 'R' in record[:2] or 'C' in record[:2]:
                if i < len(records):
                    dirty.add(records[i])
                    i += 1
        try:
            behind, ahead = map(int, self.git('rev-list', '--left-right', '--count', 'origin/main...HEAD').split())
        except (EditorError, ValueError):
            ahead = behind = None
        return {'branch': branch, 'ahead': ahead, 'behind': behind,
                'dirty': sorted(dirty),
                'unauthorizedChanges': sorted(p for p in dirty if not allowed_path(p))}

    def history(self):
        base = self.git('rev-parse', '--verify', 'origin/main').strip()
        head = self.git('rev-parse', '--verify', 'HEAD').strip()
        pending = self.git('rev-list', base+'..'+head).splitlines()
        if len(pending) > 50:
            raise EditorError('Plus de 50 commits attendent une publication. Vérifiez-les dans Git.', 409)
        changes = {}
        for commit in pending:
            records = self.git('diff-tree', '--root', '-m', '--no-commit-id', '--no-renames',
                               '--full-index', '--raw', '-z', '-r', commit).split('\0')
            for header, name in zip(records[::2], records[1::2]):
                _, mode, _, blob, _ = header.lstrip(':').split()
                changes.setdefault(name, set())
                if mode != '000000':
                    if mode not in ('100644', '100755'):
                        raise EditorError('Un commit contient un lien ou un sous-module. Inspectez les commits dans Git.', 409)
                    changes[name].add(blob)
        return base, head, pending, changes

    def publication_review(self):
        state = self.repository_state()
        if state['branch'] != 'main' or state['behind'] != 0:
            raise EditorError('La branche main doit être à jour avant la vérification.', 409)
        remote = self.remote()
        base, head, pending, changes = self.history()
        for name in changes:
            if not self.reviewable_path(name):
                raise EditorError('Un fichier privé ou hors projet figure dans les commits. Inspectez l’historique dans Git.', 409)
        paths = sorted(name for name in changes if not allowed_path(name))
        review = hashlib.sha256(f'{remote}\n{base}\n{head}'.encode()).hexdigest()
        return {'review': review, 'count': len(pending), 'paths': paths}

    @staticmethod
    def reviewable_path(name):
        path = Path(name)
        if (not name or path.is_absolute() or path.as_posix() != name or '\\' in name
                or '..' in path.parts or any(ord(c) < 32 or c == '\ufffd' for c in name)):
            return False
        if name == '.github/workflows/deploy.yml':
            return True
        if any(part.startswith('.') for part in path.parts):
            return False
        if (path.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.db-wal', '.sqlite-wal', '.pem', '.key', '.p12', '.pfx', '.wav'}
                or any(part == 'node_modules' for part in path.parts)
                or re.search(r'(?:client_secret|credentials|(?:^|_)token(?:_|$)|^id_(?:rsa|ed25519))', path.stem, re.I)):
            return False
        return (allowed_path(name) or path.parts[0] in {'frontend','backend','docs','editor','deploy','scripts'}
                or name in {'README.md','requirements.txt','requirements.lock.txt','requirements copie.txt',
                            'test.sh','setup.sh','run.sh','run-web.sh','worker.sh'})

    def ensure_publishable(self, review=None):
        state = self.repository_state()
        if state['branch'] != 'main':
            raise EditorError('La publication nécessite la branche main.', 409)
        if state['unauthorizedChanges']:
            raise EditorError('Enregistrez les changements de code dans un commit local avant de les vérifier.', 409)
        if state['ahead'] is None or state['behind'] is None:
            raise EditorError('La référence origin/main est absente. Synchronisez le dépôt avant de publier.', 409)
        if state['behind']:
            raise EditorError('GitHub contient une version plus récente. Synchronisez le dépôt avant de publier.', 409)
        details = self.publication_review()
        if details['paths'] and not review:
            raise EditorError('Des commits de code attendent. Ouvrez Vérification pour examiner la version complète.', 409)
        if review is not None and review != details['review']:
            raise EditorError('Les commits ou la destination ont changé. Rouvrez Vérification.', 409)
        for name in state['dirty']:
            self.safe_path(name)
        return state

    def fingerprint(self, review=None):
        state = self.ensure_publishable(review)
        digest = hashlib.sha256()
        for value in (self.git('rev-parse', 'HEAD', 'origin/main'), self.git('ls-files', '-s', '-z'),
                      self.remote(), json.dumps(state, sort_keys=True)):
            digest.update(value.encode())
        files = set(state['dirty']) | {SETTINGS_FILE, LAYOUT_FILE}
        files.update(self.git('ls-files', '-z', '--', 'frontend/dist').split('\0'))
        for name in sorted(files - {''}):
            path = self.safe_path(name)
            digest.update(name.encode())
            digest.update(b'present' if path.is_file() else b'absent')
            if path.is_file():
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(65_536), b''):
                        digest.update(chunk)
        return digest.hexdigest()

    def scan_secrets(self, review=None):
        state = self.ensure_publishable(review)
        values = secret_values(self.repo)
        total = 0
        names = set(state['dirty'])
        names.update(self.git('ls-files', '-z', '--', *sorted(ALLOWED_EXACT), 'frontend/dist').split('\0'))
        for name in sorted(names - {''}):
            path = self.safe_path(name)
            if not path.is_file():
                continue
            total += path.stat().st_size
            if total > 128_000_000 or path.stat().st_size > 16_000_000:
                raise EditorError('La taille des fichiers à publier dépasse la limite de cet éditeur.', 409)
            if contains_secret(path.read_bytes(), values):
                raise EditorError('Un secret potentiel a été détecté dans un fichier à publier. Publication bloquée.', 409)
        # Also inspect older pending commits: deleting a key in the last commit
        # would otherwise still publish it through the preceding history.
        _, _, _, changes = self.history()
        for blob in {blob for blobs in changes.values() for blob in blobs}:
            data = self.git('cat-file', 'blob', blob, raw=True)
            total += len(data)
            if total > 128_000_000:
                raise EditorError('L’historique local à contrôler est trop volumineux.', 409)
            if contains_secret(data, values):
                raise EditorError('Un secret potentiel existe dans un commit local. Publication bloquée.', 409)

    def log(self, line):
        line = sanitize(line, self.secrets)[:600]
        with self.lock:
            self.job['log'].append(line)
            self.job['log'] = self.job['log'][-200:]

    def start_job(self, action, review=None):
        with self.lock:
            if self.job['status'] == 'running':
                raise EditorError('Une opération est déjà en cours.', 409)
            if action == 'publish':
                review = self.prepared_review
                if not self.prepared_fingerprint or self.fingerprint(review) != self.prepared_fingerprint:
                    self.prepared_fingerprint = None
                    self.job['readyToPublish'] = False
                    raise EditorError('Les fichiers ont changé. Préparez à nouveau la publication.', 409)
            else:
                self.ensure_publishable(review)
            self.job = {'id': secrets.token_hex(12), 'status': 'running',
                        'stage': 'Préparation' if action == 'prepare' else 'Publication',
                        'log': [], 'error': None, 'readyToPublish': False}
            prepared = self.prepared_fingerprint
            self.prepared_fingerprint = None
            thread = threading.Thread(target=self.run_job, args=(action, prepared, review), daemon=True)
            thread.start()
            return dict(self.job)

    def run_job(self, action, prepared, review):
        try:
            if action == 'prepare':
                self.log('Vérification des fichiers et des commits locaux…')
                self.scan_secrets(review)
                script = self.repo/'test.sh'
                if not script.is_file() or script.is_symlink():
                    raise EditorError('Le script de vérification du projet est absent ou invalide.', 409)
                with self.lock:
                    self.job['stage'] = 'Tests et construction'
                self.runner.run([str(script)], cwd=self.repo, env=self.env,
                                timeout=900, on_line=self.log, cancel=self.stop_event)
                self.scan_secrets(review)
                state = self.ensure_publishable(review)
                fingerprint = self.fingerprint(review)
                available = bool(state['dirty'] or state['ahead'])
                with self.lock:
                    self.prepared_fingerprint = fingerprint if available else None
                    self.prepared_review = review if available else None
                    self.prepared_head = self.git('rev-parse','HEAD').strip() if available else None
                    self.job['readyToPublish'] = available
                self.log('Vérifications réussies. Cliquez sur Publier pour mettre en ligne.' if available else 'Vérifications réussies. Aucune modification à publier.')
            else:
                self.log('Vérification de la branche distante GitHub…')
                self.git('fetch', '--no-tags', 'origin', 'main', timeout=30, on_line=self.log)
                if self.fingerprint(review) != prepared:
                    raise EditorError('Les fichiers ont changé. Préparez à nouveau la publication.', 409)
                destination = self.remote()
                base, head, _, _ = self.history()
                state = self.ensure_publishable(review)
                self.scan_secrets(review)
                if not state['dirty'] and not state['ahead']:
                    raise EditorError('Aucune modification à publier.', 409)
                self.git('add', '--', *[name for name in sorted(ALLOWED_EXACT) if (self.repo/name).exists() or name in state['dirty']], 'frontend/dist')
                staged = self.git('diff', '--cached', '--name-only', '-z').split('\0')
                if any(p and not allowed_path(p) for p in staged):
                    raise EditorError('L’index contient un fichier hors du périmètre de publication.', 409)
                self.scan_secrets(review)
                values = secret_values(self.repo)
                for name in filter(None, staged):
                    entry = self.git('ls-files', '-s', '--', name).strip()
                    if entry and (not entry.startswith(('100644 ', '100755 '))
                                  or contains_secret(self.git('show', ':'+name, raw=True), values)):
                        raise EditorError('Un fichier indexé présente un risque. Publication bloquée.', 409)
                if any(staged):
                    self.git('commit', '-m', 'feat: mettre à jour la présentation du site', timeout=60, on_line=self.log)
                    if self.git('rev-parse', 'HEAD^').strip() != head:
                        raise EditorError('La branche locale a bougé pendant la publication.', 409)
                    head = self.git('rev-parse', 'HEAD').strip()
                    if any(not allowed_path(name) for name in self.git('diff', '--name-only', '-z', head+'^', head).split('\0') if name):
                        raise EditorError('Le nouveau commit contient un fichier hors périmètre.', 409)
                    new_base, new_head, _, _ = self.history()
                    if (new_base, new_head) != (base, head) or self.remote() != destination:
                        raise EditorError('La version ou la destination a changé depuis la vérification.', 409)
                    self.scan_secrets(self.publication_review()['review'])
                if self.remote() != destination:
                    raise EditorError('La destination a changé depuis la vérification.', 409)
                self.log('Envoi vers GitHub…')
                self.git('push', 'origin', head+':refs/heads/main', timeout=180, on_line=self.log)
                self.log('Version envoyée sur GitHub. Le déploiement automatique peut maintenant être suivi sur GitHub Actions.')
            with self.lock:
                self.job['status'] = 'succeeded'
                self.job['stage'] = 'Prêt à publier' if self.job['readyToPublish'] else ('Vérifié' if action == 'prepare' else 'Terminé')
        except Exception as exc:
            error = sanitize(str(exc), self.secrets)[:600]
            with self.lock:
                self.prepared_fingerprint = None
                self.job.update(status='failed', stage='Arrêté', error=error, readyToPublish=False)
            self.log(error)

    def state(self):
        try:
            repo = self.repository_state()
        except Exception:
            repo = {'branch': '', 'ahead': None, 'behind': None, 'dirty': [],
                    'unauthorizedChanges': [], 'error': 'État Git indisponible.'}
        with self.lock:
            return {'repo':repo,**self.progress(),**self.presentation()}

    def presentation(self):
        settings,layout=self.read_settings(),self.read_layout()
        data=json.dumps([settings,layout],sort_keys=True,ensure_ascii=False).encode()
        return {'settings':settings,'savedSettings':settings,'layout':layout,
                'presentationRevision':hashlib.sha256(data).hexdigest()}

    def editor_revision(self):
        paths=[Path(__file__),Path(__file__).with_name('layout.py'),*self.ui_root.glob('*')]
        return self.source_revision(paths)

    @staticmethod
    def source_revision(paths):
        stamps=[]
        for path in sorted(paths):
            try:stamps.append((path.name,path.stat().st_mtime_ns))
            except OSError:continue
        return hashlib.sha256(repr(stamps).encode()).hexdigest()

    def progress(self):
        with self.lock:
            if self.job['readyToPublish'] and self.prepared_head!=self.git('rev-parse','HEAD').strip():
                self.prepared_fingerprint=None
                self.job['readyToPublish']=False
            try:revision=self.presentation()['presentationRevision']
            except EditorError:revision=None
            return {'previewUrl':self.preview_url,'previewError':self.preview_error,
                    'presentationRevision':revision,'editorChanged':self.editor_revision()!=self.initial_editor_revision,
                    'editorRevision':self.initial_editor_revision,
                    'job':{**self.job,'log':list(self.job['log'])}}

    @staticmethod
    def free_port():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    @staticmethod
    def wait_http(port, path, stop_event, process):
        for _ in range(100):
            if stop_event.is_set() or process.poll() is not None:
                return False
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=.3)
            try:
                connection.request('GET', path, headers={'Accept': 'text/html' if path == '/analyse' else 'application/json'})
                if connection.getresponse().status == 200:
                    return True
            except OSError:
                pass
            finally:
                connection.close()
            stop_event.wait(.2)
        return False

    def start_preview(self):
        with self.lock:
            if self.preview_starting or self.preview_url or self.stop_event.is_set():
                return
            self.preview_starting = True
            self.preview_error = None

        def launch():
            try:
                root = self.repo/'.local/site-editor'
                if root.parent.is_symlink() or root.is_symlink():
                    raise EditorError('Répertoire de prévisualisation invalide.')
                root.mkdir(parents=True, exist_ok=True, mode=0o700)
                python = self.repo/'.venv/bin/python'
                vite = self.repo/'frontend/node_modules/vite/bin/vite.js'
                node = shutil.which('node', path=self.env.get('PATH'))
                if not node:
                    raise EditorError('Node.js est introuvable. Installez-le puis réessayez.')
                if not python.is_file() or not vite.is_file():
                    raise EditorError('Les dépendances de Résonant sont manquantes. Lancez setup.sh puis réessayez.')
                previous_ports = os.environ.pop('RESONANT_EDITOR_RESTART_PORTS', '').split(',')
                if len(previous_ports) == 2 and all(p.isdecimal() and 1024<=int(p)<=65535 for p in previous_ports):
                    backend_port, frontend_port = map(int,previous_ports)
                else:
                    backend_port, frontend_port = self.free_port(), self.free_port()
                while frontend_port == backend_port:
                    frontend_port = self.free_port()
                env = dict(self.env, PYTHONPATH=str(self.repo/'backend'),
                           RESONANT_DB_PATH=str(root/'preview.sqlite'),
                           RESONANT_SESSION_SECRET=self.preview_secret,
                           RESONANT_PREVIEW_API_ORIGIN=f'http://127.0.0.1:{backend_port}')
                runtime_script=self.repo/'scripts/prepare_local_runtime.py'
                sources=lambda:self.source_revision([runtime_script,*(self.repo/'backend/lab').glob('*.py')])
                def rebuild():
                    self.runner.run([python,runtime_script],cwd=self.repo,env=env,timeout=20,cancel=self.stop_event)
                revision=sources()
                if runtime_script.is_file():
                    rebuild()
                commands = [([str(python), '-m', 'uvicorn', 'lab.app:app', '--host', '127.0.0.1', '--port', str(backend_port),
                              '--reload','--reload-dir',str(self.repo/'backend/lab')], self.repo),
                            ([node, str(vite), '--host', '127.0.0.1', '--port', str(frontend_port), '--strictPort'], self.repo/'frontend')]
                processes = []
                for args, cwd in commands:
                    if self.stop_event.is_set():
                        return
                    log_path = root/'preview.log'
                    fd = os.open(log_path, os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, 'ab') as log:
                        process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    with self.lock:
                        if self.stop_event.is_set():
                            ProcessRunner.stop(process)
                            return
                        self.preview_processes.append(process)
                    processes.append(process)
                if not self.wait_http(backend_port, '/api/health', self.stop_event, processes[0]) or not self.wait_http(frontend_port, '/analyse', self.stop_event, processes[1]):
                    raise EditorError('L’aperçu n’a pas pu démarrer. Vérifiez l’installation du projet.')
                with self.lock:
                    self.preview_ports = (backend_port,frontend_port)
                    self.preview_url = f'http://127.0.0.1:{frontend_port}/analyse?editor=1'
                def watch_runtime():
                    nonlocal revision
                    while not self.stop_event.wait(1.5):
                        current=sources()
                        if current==revision or not runtime_script.is_file():continue
                        try:rebuild()
                        except (OSError,EditorError):continue
                        revision=current
                threading.Thread(target=watch_runtime,daemon=True).start()
            except Exception as exc:
                with self.lock:
                    self.preview_error = sanitize(str(exc), self.secrets)[:240]
                    processes = list(self.preview_processes)
                    self.preview_processes.clear()
                for process in processes:
                    ProcessRunner.stop(process)
            finally:
                with self.lock:
                    self.preview_starting = False
        threading.Thread(target=launch, daemon=True).start()

    def close(self):
        self.stop_event.set()
        self.runner.close()
        with self.lock:
            processes = list(self.preview_processes)
            self.preview_processes.clear()
        for process in processes:
            ProcessRunner.stop(process)


class EditorHandler(BaseHTTPRequestHandler):
    server_version = 'ResonantEditor'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    @property
    def editor(self):
        return self.server.editor

    def log_message(self, *_):
        pass  # No request headers, cookies or tokens in console output.

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def host_valid(self):
        port = self.server.server_address[1]
        return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

    def token_valid(self):
        value = self.headers.get('X-Editor-Token', '')
        return len(value) <= 128 and hmac.compare_digest(value.encode(), self.editor.token.encode())

    def authenticated(self):
        if self.token_valid():
            return True
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', '')[:4096])
        except Exception:
            return False
        value = cookie.get(self.editor.cookie_name)
        return bool(value and hmac.compare_digest(value.value.encode(), self.editor.cookie.encode()))

    def send(self, status, body, kind='application/json; charset=utf-8', cookie=False):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src http://127.0.0.1:*; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'none'")
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Connection', 'close')
        if cookie:
            self.send_header('Set-Cookie', f'{self.editor.cookie_name}={self.editor.cookie}; Path=/; HttpOnly; SameSite=Strict')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def route(self):
        if len(self.path) > 2048 or not self.path.startswith('/') or self.path.startswith('//'):
            raise EditorError('Adresse invalide.')
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc:
            raise EditorError('Adresse invalide.')
        return parsed.path

    def do_GET(self):
        try:
            if not self.host_valid() or not self.authenticated():
                raise EditorError('Accès local non autorisé.', 403)
            path = self.route()
            if path == '/api/state':
                return self.send(200, self.editor.state())
            if path == '/api/progress':
                return self.send(200, self.editor.progress())
            if path == '/api/job':
                return self.send(200, self.editor.progress()['job'])
            if path == '/api/preview':
                if not self.token_valid():
                    raise EditorError('Accès local non autorisé.', 403)
                return self.send(200, {'previewUrl': self.editor.preview_url})
            if path == '/api/files':
                if not self.token_valid():
                    raise EditorError('Accès local non autorisé.', 403)
                return self.send(200, {'files': self.editor.source_names()})
            if path == '/api/publication-review':
                if not self.token_valid():
                    raise EditorError('Accès local non autorisé.', 403)
                return self.send(200, self.editor.publication_review())
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                     '/layout.js': ('layout.js', 'text/javascript; charset=utf-8'),
                     '/sync.js': ('sync.js', 'text/javascript; charset=utf-8'),
                     '/placement.js': ('placement.js', 'text/javascript; charset=utf-8'),
                     '/console.js': ('console.js', 'text/javascript; charset=utf-8'),
                     '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path not in files:
                raise EditorError('Ressource absente.', 404)
            name, kind = files[path]
            file = self.editor.ui_root/name
            if file.is_symlink() or not file.is_file():
                raise EditorError('Interface de l’éditeur absente.', 404)
            body = file.read_bytes()
            if name == 'index.html':
                body = body.replace(b'__EDITOR_TOKEN__', self.editor.token.encode())
            return self.send(200, body, kind, cookie=path == '/')
        except EditorError as exc:
            self.send(exc.status, {'error': sanitize(str(exc), self.editor.secrets)})
        except Exception:
            self.send(500, {'error': 'L’éditeur n’a pas pu terminer cette action.'})

    def read_json(self, max_body=MAX_BODY):
        if self.headers.get('Transfer-Encoding'):
            raise EditorError('Format de requête non pris en charge.')
        length = self.headers.get('Content-Length', '')
        if not re.fullmatch(r'\d{1,7}', length):
            raise EditorError('Taille de requête invalide.')
        if int(length) > max_body:
            raise EditorError('Requête trop volumineuse.', 413)
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise EditorError('Une requête JSON est requise.', 415)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate')
                result[key] = value
            return result
        try:
            value = json.loads(self.rfile.read(int(length)), object_pairs_hook=unique)
        except (ValueError, UnicodeError, OSError):
            raise EditorError('JSON invalide.')
        if type(value) is not dict:
            raise EditorError('Une demande JSON nommée est requise.')
        return value

    def do_POST(self):
        try:
            if not self.host_valid() or not self.token_valid() or self.headers.get('Origin') != self.editor.origin:
                raise EditorError('Action locale non autorisée.', 403)
            path = self.route()
            if path not in ('/api/save', '/api/prepare', '/api/publish', '/api/files/open', '/api/files/save', '/api/preview/retry', '/api/terminal', '/api/restart'):
                raise EditorError('Action inconnue.', 404)
            body = self.read_json(MAX_SOURCE * 6 + 4096 if path == '/api/files/save' else MAX_BODY)
            if path == '/api/files/open' and set(body) == {'name'}:
                return self.send(200, self.editor.open_source(body['name']))
            if path == '/api/files/save' and set(body) == {'name', 'content', 'revision'}:
                return self.send(200, self.editor.save_source(body['name'], body['content'], body['revision']))
            if path == '/api/preview/retry' and not body:
                self.editor.start_preview()
                return self.send(202, {'ok': True})
            if path.startswith(('/api/files/', '/api/preview/')):
                raise EditorError('Paramètres invalides.')
            if path == '/api/restart':
                with self.editor.lock:
                    if body or self.editor.job['status']=='running' or not self.editor.progress()['editorChanged']:
                        raise EditorError('L’éditeur ne peut pas être actualisé maintenant.',409)
                    self.editor.restart_requested=True
                    self.send(202, {'ok':True})
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                    return
            if path == '/api/save':
                if 'settings' not in body or set(body)-{'settings','layout','revision'}:
                    raise EditorError('Demande de sauvegarde invalide.')
                revision=body.get('revision')
                if revision is not None and (not isinstance(revision,str) or not re.fullmatch(r'[0-9a-f]{64}',revision)):
                    raise EditorError('Révision invalide.')
                return self.send(200,self.editor.save(body['settings'],body.get('layout'),revision))
            if path == '/api/terminal':
                if set(body) != {'command'}:
                    raise EditorError('Une commande est requise.')
                return self.send(200, self.editor.terminal(body['command']))
            if path == '/api/prepare' and set(body) == {'review'} and isinstance(body['review'], str):
                return self.send(202, {'job': self.editor.start_job('prepare', body['review'])})
            if body:
                raise EditorError('Cette action ne prend pas de paramètres.')
            return self.send(202, {'job': self.editor.start_job('prepare' if path == '/api/prepare' else 'publish')})
        except EditorError as exc:
            self.send(exc.status, {'error': sanitize(str(exc), self.editor.secrets)})
        except Exception:
            self.send(500, {'error': 'L’éditeur n’a pas pu terminer cette action.'})


def make_server(editor, port=0):
    class LocalServer(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True
    server = LocalServer(('127.0.0.1', port), EditorHandler)
    server.editor = editor
    editor.origin = f'http://127.0.0.1:{server.server_address[1]}'
    editor.cookie_name = 'resonant_editor_'+str(server.server_address[1])
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description='Éditeur local Résonant')
    parser.add_argument('--repo', required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('Port invalide.')
    editor = None
    server = None
    try:
        editor = SiteEditor(args.repo, os.environ.get('RESONANT_EDITOR_TOKEN', ''))
        server = make_server(editor, args.port)
        def stop(*_):
            editor.stop_event.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        editor.start_preview()
        print(json.dumps({'ready': True, 'url': editor.origin+'/'}), flush=True)
        server.serve_forever(poll_interval=.2)
        if editor.restart_requested and not editor.stop_event.is_set():
            port=server.server_address[1]
            server.server_close()
            editor.close()
            os.environ['RESONANT_EDITOR_RESTART_COOKIE']=editor.cookie
            os.environ['RESONANT_EDITOR_RESTART_PORTS']=','.join(map(str,editor.preview_ports))
            os.environ['RESONANT_EDITOR_RESTART_PREVIEW_SECRET']=editor.preview_secret
            os.execv(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--repo',str(editor.repo),'--port',str(port)])
        return 0
    except Exception as exc:
        # Never echo an inherited token or a credential-bearing Git URL.
        print(sanitize(str(exc), editor.secrets if editor else ()), file=sys.stderr)
        return 1
    finally:
        if server:
            server.server_close()
        if editor:
            editor.close()


if __name__ == '__main__':
    raise SystemExit(main())
