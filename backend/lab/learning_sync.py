"""Read-only synchronization of compatible aggregate statistics for local labs."""
import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
from urllib.request import HTTPRedirectHandler, Request, build_opener

PUBLIC_SUMMARY = 'https://resonant-lab.servepics.com/api/acoustic-learning/public-summary'
SUMMARY_VERSION = 'envelope-bandit-v1'
REFRESH_SECONDS = 300
MAX_AGE = 86_400
MAX_BYTES = 4096


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_summary(data):
    if (type(data) is not dict or set(data) != {'version', 'history'}
            or data['version'] != SUMMARY_VERSION or type(data['history']) is not dict):
        raise ValueError('Statistiques acoustiques incompatibles.')
    for profile, strategies in data['history'].items():
        if profile not in ('sustained', 'decaying', 'transient') or type(strategies) is not dict:
            raise ValueError('Profil acoustique invalide.')
        for strategy, row in strategies.items():
            if (strategy not in ('adsr', 'decay') or type(row) is not dict
                    or set(row) != {'contributors', 'mean'}
                    or type(row['contributors']) is not int or not 5 <= row['contributors'] <= 10_000
                    or type(row['mean']) not in (int, float) or not 0 < row['mean'] <= 1
                    or not math.isfinite(row['mean'])):
                raise ValueError('Score acoustique invalide.')
    return data


def snapshot_path():
    raw = os.getenv('RESONANT_LEARNING_SYNC_DIR')
    if not raw:
        return None
    directory = Path(raw)
    if (not directory.is_absolute() or directory.resolve() != directory
            or directory.is_symlink()):
        return None
    return directory/'community-summary.json'


def read_snapshot(path):
    if path is None:
        return None
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return None
        data = json.loads(raw)
        if (type(data) is not dict or set(data) != {'received', 'summary'}
                or type(data['received']) is not int or not 0 <= time.time()-data['received'] <= MAX_AGE):
            return None
        return validate_summary(data['summary'])['history']
    except (OSError, ValueError, RecursionError):
        return None


def sync_once(path):
    request = Request(PUBLIC_SUMMARY, headers={'Accept': 'application/json'})
    with build_opener(NoRedirect).open(request, timeout=8) as response:
        if response.status != 200 or response.headers.get_content_type() != 'application/json':
            raise ValueError('Réponse de synchronisation incompatible.')
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Statistiques acoustiques trop volumineuses.')
    data = validate_summary(json.loads(raw))
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, mode='w', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump({'received': int(time.time()), 'summary': data}, stream, allow_nan=False)
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def synchronize(path, stop):
    while not stop.is_set():
        try:
            sync_once(path)
        except (OSError, ValueError, RecursionError):
            pass  # A failed or obsolete production deployment leaves the last snapshot in place.
        stop.wait(REFRESH_SECONDS)
