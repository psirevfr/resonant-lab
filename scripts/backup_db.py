"""Consistent, non-overwriting SQLite backup, including committed WAL pages."""
import argparse
import os
from pathlib import Path
import sqlite3


def backup(source, destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if not source.is_file():raise ValueError('Base source absente.')
    # Reserve the output first: never replace an existing backup or database.
    fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(fd)
    try:
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=5) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst,pages=256,sleep=.1)
                if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('Contrôle de sauvegarde échoué.')
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination')
    args=p.parse_args();backup(args.source,args.destination)
    print('Sauvegarde SQLite terminée et vérifiée.')
