# Environnement Python de la VM

Le journal GitHub du 9 octobre 2026 à 22:59 confirme une `.venv` Python 3.10,
incompatible avec le verrou numérique validé (NumPy 2.5.3 requiert Python 3.12+).
Le refus SSH précédent est résolu dans ce journal. Le calcul Pyodide n'a pas
encore été préparé : l'installation Python échoue auparavant.

Le workflow vérifie désormais l'interpréteur avant le pull et toute installation.
Ce contrôle a été exécuté en local avec Python 3.12 ; le rejet de 3.10 est simulé.
Il ne met pas à niveau l'interpréteur et ne prouve pas l'état actuel de la VM.

## Vérification préalable sur la VM

```bash
cd ~/resonant-lab
.venv/bin/python --version
python3.12 --version
```

Si `python3.12` manque, installer Python 3.12 et son support venv par une procédure
adaptée à l'Ubuntu réel, puis vérifier ces commandes. Ne pas remplacer le Python
système. Aucune installation de dépôt tiers ni migration distante n'a été effectuée.

## Bascule manuelle, seulement une fois Python 3.12 disponible

Vérifier le chemin réellement utilisé par `resonant-lab` via `systemctl cat`, faire
une sauvegarde cohérente de SQLite et réserver une fenêtre de maintenance. Les
commandes suivantes supposent le dépôt `~/resonant-lab` et ce service unique, comme
dans le workflow actuel. Ne pas les appliquer à un autre checkout sans adaptation.

```bash
cd ~/resonant-lab
python3.12 --version
test ! -e .venv-python310-backup
sudo systemctl stop resonant-lab
mv .venv .venv-python310-backup
python3.12 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check pip==26.2.1
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip check
.venv/bin/python scripts/prepare_local_runtime.py --download
.venv/bin/python -c 'import json; from pathlib import Path; assert json.loads(Path(".local/compute-runtime/manifest.json").read_text())["ready"]'
sudo systemctl start resonant-lab
sudo systemctl status resonant-lab --no-pager
```

Exécuter les commandes étape par étape et arrêter si l'une échoue. La recréation
se fait au chemin final `.venv` : ne pas déplacer un environnement nouvellement
créé depuis un autre chemin, car ses scripts contiennent des chemins absolus.
Ne pas exécuter `init_db()` pour réinitialiser les comptes ; ne supprimer aucune
base, clé ni donnée utilisateur.

## Retour arrière si la bascule échoue

Service arrêté, déplacer la nouvelle `.venv` vers un nom de diagnostic encore
inexistant, puis remettre `.venv-python310-backup` au chemin original `.venv`.
Si le code a également changé, revenir à une révision compatible avec Python 3.10,
sans réinitialiser le dépôt ni remplacer SQLite. Redémarrer et vérifier les journaux.
L'ancien environnement seul ne garantit pas la compatibilité du nouveau code.

Après succès, relancer l'action GitHub. Vérifier connexion, fichiers runtime et
calcul synthétique local ; la disponibilité HTTP seule ne valide pas le laboratoire.
