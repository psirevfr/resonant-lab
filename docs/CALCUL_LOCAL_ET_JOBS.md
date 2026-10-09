# Calculs locaux et diagnostic de la file — 9 octobre 2026

## État vérifié et limites du diagnostic

### Informations actualisées par l’opérateur

L’opérateur confirme la révocation des secrets exposés, leur retrait de l’historique
Git par rebase et le caractère volontaire de la réinitialisation SQLite de production.
Le job signalé a été purgé : son identifiant n’est plus requis pour poursuivre le travail
local. Ces confirmations sont reçues de l’opérateur ; aucun audit SSH n’a été exécuté.

La remise à zéro locale demandée a été réalisée : `users.db` renommé en
`users_archive.db` sans écrasement, empreinte du contenu conservée, `init_db()` exécuté,
et seul compte `bro` (`bro@resonant.local`) recréé avec un mot de passe haché vérifié.
Le schéma actuel n’a pas de rôle administrateur distinct : aucun champ de privilège
fictif n’a été ajouté. Au premier démarrage web, `compute_jobs` est recréée **vide**,
comme prévu par les migrations ; ce n’est pas une reprise d’anciens jobs.
La connexion réelle, la génération, l’optimisation et la simplification WebAssembly ont réussi avec cette nouvelle base (14 → 7 modules), sans création de job serveur. Capture : `compute-bro.png`. Le serveur temporaire de validation a ensuite été arrêté ; le compte et la base restent disponibles.
Les 18 tests backend ciblés auth/calcul et les 24 tests frontend ont été réexécutés.


Le checkout inspecté est basé sur `428f8cb`. Il contient React 19/Vite, FastAPI,
NumPy/SciPy, la file SQLite et le worker Python séparé. Les anciens rapports ne
suffisent pas à identifier les fichiers réellement déployés : ce checkout ne contient
plus les adaptateurs `artifact_store.py`/`gemini_reports.py`, ni le diagnostic API
précédemment annoncé. Les fichiers utilisateur non suivis ont été préservés.

**Cause du signalement avant purge : non confirmée, faute d'audit SSH et de chronologie conservée du job concerné.** Le rapport de déploiement mentionne Uvicorn et
`resonant-lab.service`, sans preuve d'un consommateur `python -m lab.worker`.
L'absence de ce consommateur, ou l'utilisation d'une autre base par celui-ci, reste
l'hypothèse principale. Un processus Uvicorn ne prend jamais les jobs de cette file.
Aucun service de production, secret ou compte n'a été modifié.

Une cause de l'absence de diagnostic est confirmée dans le code précédent : le frontend
annonçait une attente normale sans savoir si un worker répondait ; les jobs en attente
n'expiraient qu'après le TTL de file (24 heures par défaut). Une requête de suivi
réseau pouvait aussi rester sans réponse. Ces deux situations sont maintenant distinguées.

## Cartographie réelle avant/après

| Opération | Algorithme/dépendances | Avant | Après |
|---|---|---|---|
| Génération | Analyse FFT/STFT, projections modales, least_squares, candidats et fonction Objective ; NumPy/SciPy/Pydantic | Worker serveur | Même code Python dans le worker serveur **ou** un worker Python/WebAssembly choisi explicitement |
| Simplification | Sélection/groupes, ajustements, saturations ×4 et filtres, score à fréquence originale | Worker serveur | Même choix explicite serveur/appareil |
| Optimisation | Powell, L-BFGS-B ou differential_evolution, mêmes budgets/bornes/graines | Worker serveur | Même choix explicite serveur/appareil |
| Synthèse audio | `audioDsp.ts`, oscillateurs/enveloppes/filtres/saturations | Worker navigateur | Inchangé, audio transmis avant les analyses |
| Analyses du signal | Extraction initiale `/analyze` Python ; vues `signalView` TypeScript | Serveur pour extraction, navigateur pour vues | Inchangé ; extraction aussi intégrée à la génération locale |
| Export WAV | `encodeWav`, WAV float32 mono | Navigateur, avant toutes les vues | Navigateur, disponible avant les vues |
| Clavier | `/instrument/patch`, transposition puis rendu audio local, cache jusqu'à 8 voix | Hybride | Inchangé ; le réseau par nouvelle note reste une limite |

Aucune migration générale vers TypeScript ni approximation du solveur. `soundfile`
est importé uniquement dans les fonctions WAV qui l'utilisent ; les fonctions
numériques de `audio.py` sont identiques et exécutables sans libsndfile dans WASM.

## File : présence, chronologie et récupération

- Table additive `compute_workers(id, heartbeat)` : heartbeat du parent toutes les
  deux secondes, même au repos. Disponibilité fraîche pendant 30 secondes. Cela
  prouve que le consommateur répond sur **cette base**, pas qu'il peut terminer
  n'importe quel calcul. Ce délai de présence n'est pas un timeout de calcul.
- Colonne additive `compute_jobs.timings` : chargement et calcul mesurés ; aucun compte
  ni résultat existant supprimé par cette migration.
- Les anciennes prises atomiques, fences et verrous OS restent actifs. Un seul calcul
  global par défaut entre génération, optimisation et simplification.
- L'état d'un job en file contient `worker`, `queue_warning` et `queue_wait_ms`.
  Absence de worker : avertissement explicite immédiatement après consultation,
  job conservé en file. Worker frais et attente supérieure à 30 s : avertissement
  d'attente prolongée. Le TTL de file existant reste indépendant.
- Les leases expirées échouent ; aucune remise en file automatique. Les anciennes
  lignes running sans heartbeat ni started sont aussi récupérées à partir de created.
- Les logs corrèlent l'identifiant aux prises, au début/fin du calcul, au résultat et
  au temps mesuré. Aucun nom de fichier, paramètres audio, e-mail ou token journalisé.
- L'arrêt tente de tuer les enfants avant de retirer le heartbeat. Une base temporairement
  verrouillée ne doit pas empêcher l'arrêt des processus ; les leases nettoient ensuite
  les états non persistés.
- Un chemin SQLite configuré **relatif** est désormais refusé explicitement. Le chemin
  par défaut est absolu. Ne jamais corriger ce problème en créant une base vide : identifier
  d'abord la base contenant réellement les comptes/projets.

API privée : `GET /api/compute/status` indique `available` et l'âge du dernier heartbeat.
La clé API ne remplace pas la session du navigateur. Les endpoints de job continuent de
vérifier le propriétaire. Les réponses privées conservent les contrôles existants.

Les requêtes de suivi ont une limite réseau de 15 s, avec annulation de la requête et
message « suivi indisponible ». Le calcul n'est pas déclaré en échec ni annulé pour
cette raison. Reprises/idempotence, backoff, nettoyage et fréquence de suivi existants
sont conservés ; aucun pourcentage fictif ajouté.

Diagnostic CLI, **lecture seule**, sans imports backend/migrations :

```bash
.venv/bin/python scripts/check_jobs.py --db /chemin/absolu/base-active.sqlite --job IDENTIFIANT_DU_JOB
```

Une base ancienne sans `compute_workers` produit `worker_presence_supported=false` ;
ce résultat n'autorise pas à conclure que son ancien worker est absent.

## Exécution sur l'appareil

`lab.compute.compute` fournit un seul dispatcher pur pour les deux exécutions.
Le backend autorise et prépare une seule référence via `POST /api/compute/input` :
Float64 little-endian mono, fréquence dans `X-Sample-Rate`, aucun WAV avec perte intermédiaire.
Validation, limites et contrôle de propriété précèdent l'envoi. Ce transfert ne crée
pas de job et n'envoie aucune donnée à Google. Les arrondis d'extrait et le
rééchantillonnage SciPy restent ceux du serveur, sans normalisation ajoutée.

Un worker WebAssembly exécute ensuite génération/optimisation/simplification sans
aller-retour serveur par itération. Le code numérique source est le même ; les
bibliothèques binaires diffèrent : Python natif 3.12/NumPy 2.5.3/SciPy 1.18.1,
Pyodide 314.0.7/Python 3.14.2/NumPy 2.4.6/SciPy 1.18.0/Pydantic 2.12.5.
Cette différence impose des tests de tolérance ; aucune identité bit à bit promise.

L'interface garde **Serveur par défaut**, et propose « Cet appareil · Python / SciPy »
uniquement lorsque le runtime est préparé. Une erreur locale ne crée aucun job serveur :
le repli est explicite, en sélectionnant Serveur et en relançant. Le dépliage/validation
final du graphe reste une petite requête serveur. Ce parcours n'est donc pas un mode
entièrement hors ligne ni un remplacement de l'authentification.

Un seul worker local et une seule requête active. IDs de rendu, résultats obsolètes
ignorés, refus de double soumission, référence transférable <=10 Mo. Annulation par
`Worker.terminate`, recréation à la prochaine demande ; le runtime mémoire et ses caches
sont perdus, les fichiers restent soumis au cache navigateur. Changement de compte,
démontage et fermeture arrêtent le worker. Le résultat local n'est pas persistant après
fermeture/rechargement ; les jobs serveur, eux, restent retrouvables.

Les limites de durée, travail de graphe, tableaux d'analyse et précision sont préservées.
L'empreinte mémoire maximale sur mobile n'a pas été mesurée ; une allocation impossible
propose un repli explicite. Ni threads supplémentaires ni SharedArrayBuffer requis.

## Audio disponible plus tôt

Le worker audio transmet `audio-ready`, puis `analysis-ready`, avec le même ID.
Le moteur reste vivant jusqu'aux analyses ; référence et différence sont conservées.
Les contrôles HTML audio exigent actuellement un Blob WAV : l'encodage n'est donc pas
supprimé, mais l'écoute n'attend plus le spectrogramme. Lecture et export restent en
WAV float32 mono, sans écrêtage ni normalisation. Le rendu interne demeure Float64.

Les labels/raisons/positions des modules ne déclenchent plus un rendu lorsque le signal
ne change pas. La temporisation existante de 450 ms reste une limite à améliorer.
Le bruit TypeScript garde son générateur reproductible, différent de NumPy ; les tests
Python/WASM ci-dessous ne prouvent pas une identité de cette réalisation audio TypeScript.

## Mesures reproductibles et résultats

Référence synthétique de 0,15 s, 44,1 kHz, trois modes ; trois répétitions par opération.
Génération avec affinage, recherche détaillée et impact ; optimisation Powell, 3 itérations,
un paramètre ; simplification avec exploration saturations/filtres et protection des bandes.
Mêmes paramètres et critères pour Python natif et WASM. Pas de cache de résultats.
Les durées excluent transfert réseau, lecture et vérification des écarts, et incluent
validation et calcul. Premier passage indiqué séparément dans le JSON ; les passages
suivants utilisent un runtime initialisé, sans résultat numérique mis en cache.

Commandes depuis la racine :

```bash
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=backend .venv/bin/python scripts/benchmark_compute.py
node scripts/benchmark_wasm.mjs
```

Le benchmark WASM utilise **Node 22.15 sur macOS ARM64**, pas un navigateur ni la VM.
Il mesure la véritable compilation numérique WebAssembly. Métadonnées et trois durées
brutes sont dans `compute-benchmark.json`. Le CPU précis et le pic mémoire n'ont pas
été relevés (accès sysctl refusé).

| Médiane de calcul, même référence | Python natif | WebAssembly/Node |
|---|---:|---:|
| Génération | 0,481 s | 1,166 s |
| Optimisation | 0,023 s | 0,061 s |
| Simplification | 3,122 s | 8,968 s |

Initialisation WASM hors réseau : 5,83 s. Runtime à télécharger : environ 32,4 Mo
avant compression HTTP éventuelle. **WASM est plus lent que Python natif sur cette
machine**. Le bénéfice proposé est de décharger la petite VM et sa file ; aucun gain
face à la VM n'est démontré sans mesures de production. L'absence de transaction
longue et l'isolation du thread UI préservent la réactivité, sans prouver un gain de CPU.

Tolérances fixées avant comparaison : onde maximum/RMS <=1e-7, différence du coût
<=1e-8 ; même architecture exigée. Écarts maximums mesurés : génération 8,85e-11,
optimisation 3,11e-15, simplification 1,03e-15. Les trois tests passent, sans modifier
les tolérances ni paramètres DSP. Ces quelques cas ne garantissent pas toutes les entrées.

## Tests et compatibilité

- Référence avant changement : 67 tests backend réussis.
- Backend final : **81 tests exécutés et réussis**, trois avertissements de dépréciation préexistants. Commande : `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q`. Tests de migration additive concurrente, heartbeat au repos/arrêt, verrou temporaire, jobs legacy, permissions et validation inclus.
- Frontend : 24 tests exécutés, réussis (DSP/WAV et mocks du cycle de vie des workers,
  erreurs, IDs obsolètes, double soumission, annulation effective et timeout réseau).
- Python/WASM réel : trois opérations, trois répétitions, écarts validés.
- Navigateur intégré : vraie génération, optimisation, simplification (14 → 7 modules),
  annulation locale, worker absent visible, annulation du job synthétique en file,
  audio disponible et analyses affichées. Utilisateur synthétique via serveur de test
  dédié sur localhost ; ce test n'est pas une validation du login de production.
- TypeScript et build Vite exécutés. Tests auth/jobs natifs inclus dans la suite backend.
- Aucun test Android, iPhone/iPad, Firefox/Safari physique ni ordinateur modeste.
  Pas de mesure physique d'écoute, de CPU/heap du navigateur ou d'upload Drive.
- La balise Google n'existe ni dans la source ni dans le dist de ce checkout ; aucun
  jeton inventé. Le nom LAB, le rack, les commandes de compte sont préservés.

Le scan local trouve zéro fichier .env/token/base privé suivi et aucun des six secrets
locaux connus dans le bundle. `security-local-check.json` ne contient aucun secret.
Ce scan ne valide pas tout l'historique ni la révocation des anciens secrets : révocation désormais confirmée par l’opérateur, sans audit des fournisseurs exécuté ici. Le caractère volontaire de la réinitialisation de production est confirmé par l’opérateur ; son contenu actuel et les sauvegardes ne sont pas audités depuis la VM. Aucun fichier de base actif restauré ou supprimé.

### Mesure réelle dans le navigateur intégré

Cas distinct du benchmark : note de démonstration 261,63 Hz, sélection 0,15 s,
3 partiels, affinage/recherche détaillée/impact activés. Une génération locale :
6,156 s au total, dont 2,899 s d'initialisation, 3,231 s dans le worker numérique,
18 ms de récupération de la référence. Ce cas n'est pas directement comparable à
la référence 440 Hz du tableau. Logs corrélés dans `compute-browser-check.json`.

Pour le rendu de ce modèle, l'audio a été livré en **35,9 ms**, les analyses en
68,9 ms : environ **33 ms d'attente d'analyses évitée pour l'écoute**, sur ce seul
rendu. Cela n'inclut ni la génération ni la temporisation React de 450 ms.
Pas de promesse de gain identique sur tous les sons/appareils.

Captures synthétiques : `compute-local.png`, `worker-absent.png`.

## Préparation du déploiement et retour arrière

Aucune action ci-dessous n'a été exécutée sur la VM.

1. Identifier l'unité réellement utilisée et le consommateur CPU. Vérifier utilisateur,
   répertoire, interpréteur et `EnvironmentFile`. Ne pas publier les variables d'environnement
   ni des journaux bruts. Le fichier privé commun est `/etc/resonant-lab.env`.
2. Vérifier le chemin absolu de la base active pour **les deux processus**, les permissions,
   l'espace libre et les sauvegardes existantes. Faire une sauvegarde SQLite cohérente
   avec `scripts/backup_db.py`, destination privée neuve. Aucune réinitialisation.
3. Préparer une release distincte, préserver la précédente ; installer les dépendances
   verrouillées. Le code et le frontend doivent être mis à jour ensemble pour les nouveaux
   endpoints et phases audio. Ne pas livrer le serveur de test comme service.
4. Préparer le runtime sur une machine adaptée ou, explicitement, via
   `RESONANT_SETUP_LOCAL_COMPUTE=1 ./setup.sh`. Sinon le mode serveur continue de fonctionner.
   Commande dédiée : `.venv/bin/python scripts/prepare_local_runtime.py --download`.
   Refaire la préparation après changement d'une source numérique. Vérifier le manifeste
   et la disponibilité ; le dossier `.local/compute-runtime` n'est pas suivi dans Git.
   Pour produire hors VM, transférer ce dossier généré et `frontend/dist` issus de la
   même release. Ne jamais transférer tout `.local` ni un dossier contenant des tokens.
5. Mettre en maintenance selon le proxy existant, laisser finir/annuler les calculs utiles,
   arrêter web et worker, puis appliquer les migrations additives avec leur environnement
   chargé : `init_db(); init_jobs()`. Les démarrages le font également.
6. Utiliser les unités déjà préparées `deploy/resonant-web.service` et
   `deploy/resonant-worker.service` (romadem17, répertoire de déploiement prévu).
   Si `resonant-lab.service` lance seulement Uvicorn, il faut un consommateur dédié.
   Ne pas conserver deux superviseurs HTTP concurrents. Cette bascule exige l'autorisation
   de l'opérateur et une vérification de l'unité réellement installée.
7. Démarrer d'abord le worker, puis le web. Vérifier `/api/compute/status`, un job synthétique
   léger complet, les assets, connexion/déconnexion, le mode local et l'annulation.
   Ne retirer la maintenance qu'après validation. N'augmenter aucun timeout Nginx.
8. Drive/Gemini : configuration des services, état de révocation et test synthétique
   d'archivage restent à réaliser avec accès/configuration appropriés. Ils ne font pas
   partie du dispatcher numérique ni de sa capacité CPU.

Retour arrière : maintenance, arrêt des deux services, restauration du **code et dist**
précédents coordonnés et de la configuration vérifiée, sans écraser la base active.
La table/colonne additive peut rester : l'ancien code les ignore. Les jobs interrompus
restent échoués, aucune relance automatique. Pour désactiver seulement le chemin local,
rester en mode Serveur et retirer le runtime de la release après arrêt ; ne pas modifier
la qualité. Garder la sauvegarde pour une restauration séparée, contrôlée et autorisée.

## Points restant à confirmer par l'opérateur

Accès SSH ou rapport `check_jobs`, identifiant du job bloqué, service consommateur et
base réellement utilisés ; caractère volontaire de la réinitialisation ; sauvegardes ;
configuration et état Drive/Gemini sur VM. La révocation et la réinitialisation volontaire sont maintenant confirmées par l’opérateur.
