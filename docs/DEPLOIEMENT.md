# Mise à jour asynchrone de Résonant Lab

Cette procédure prépare le déploiement ; aucune modification de production n’a été effectuée par Codex. Les unités sont configurées pour romadem17 dans /home/romadem17/resonant-deploiement/resonant-lab ; le chemin externe de la base doit encore être vérifié sur la VM. Le gestionnaire actuellement utilisé sur la VM n’est pas accessible dans le dépôt.

## Deux processus, une base

Le serveur HTTP et le worker doivent utiliser **le même chemin absolu RESONANT_DB_PATH**, sur un disque local persistant et accessible au même utilisateur. Conserver un seul processus Uvicorn : les références audio et les téléchargements temporaires restent dans des caches mémoire par processus. Ne pas utiliser `--reload` en production.

- `./run.sh` : lancement local du serveur ET du worker, arrêt des deux avec Ctrl+C.
- `./run-web.sh` : serveur seul, pour un superviseur.
- `./worker.sh` : worker seul, pour un superviseur.

Ne pas superviser simultanément `run.sh` et un deuxième worker dédié. Les prises atomiques et verrous limitent les calculs même avec plusieurs workers, mais des superviseurs inutiles compliquent l’exploitation.

`deploy/resonant-web.service` et `deploy/resonant-worker.service` sont des modèles systemd. Vérifier la présence des scripts et de `.venv` dans le chemin configuré avant installation. Si PM2 est déjà utilisé, conserver ce gestionnaire : enregistrer deux applications séparées exécutant les scripts web et worker, avec une seule instance chacune, sans mode cluster, et les mêmes variables privées ; utiliser les mécanismes existants de sauvegarde et de démarrage PM2. Ne pas installer systemd et PM2 pour superviser les mêmes processus.

Copier `deploy/resonant.env.example` hors du dépôt, par exemple `/etc/resonant-lab.env`, propriétaire administrateur et groupe du service si nécessaire, permissions 600 (ou 640 avec groupe strictement limité). Remplacer le secret d’exemple par une valeur aléatoire privée d’au moins 32 caractères. Ne jamais placer ce fichier dans le frontend ni dans Git. La clé API de production, si utilisée par des outils serveur, se lit uniquement depuis `RESONANT_LAB_API_KEY` ; elle ne sert pas de session navigateur et n’est pas nécessaire au worker.

## Sauvegarder avant la mise à jour

Une base utilisateur est actuellement présente dans l’historique Git : elle ne doit plus être utilisée comme artefact de livraison. Conserver la base active hors du checkout et ne jamais la remplacer avec celle d’une archive ou d’une release. L’exclusion `.gitignore` empêche les nouveaux fichiers, mais ne retire pas rétroactivement un fichier déjà suivi ; le fichier local a été conservé et son suivi Git retiré ; le traitement de l’historique Git reste une opération distincte. Ne pas publier de sauvegarde contenant des utilisateurs, des hashes ou des clés API.

**Avant tout git pull ou remplacement du checkout actif**, identifier la base réellement utilisée et sauvegarder son contenu. Le retrait de `users.db` du suivi Git peut supprimer cette copie lors de la mise à jour d’un ancien checkout. Préparer la nouvelle release dans un répertoire distinct, puis utiliser son script de sauvegarde avec le Python de l’installation existante, vers un fichier neuf hors du dépôt :

```bash
.venv/bin/python /chemin/nouvelle-release/scripts/backup_db.py /chemin/base-active.sqlite /chemin/prive/backup-avant-update.sqlite
```

Le script utilise l’API SQLite backup, prend en compte les pages WAL validées, refuse tout écrasement et vérifie l’intégrité. Il ne supprime pas la source. Les sauvegardes et leur stockage doivent rester privés. Vérifier aussi la capacité disque disponible pour les entrées et résultats persistants.

## Ordre de mise à jour

1. Mettre temporairement le site en maintenance au niveau du proxy existant pour éviter des soumissions pendant la transition. Laisser finir les calculs utiles ou demander leur annulation via l’interface. L’arrêt du nouveau worker marque les calculs en cours comme interrompus ; il ne les relance pas automatiquement.
2. Arrêter les anciens processus web et calcul avec leur superviseur. Sauvegarder la base et conserver la release précédente et sa configuration privée.
3. Installer la nouvelle release dans un répertoire distinct. Lancer `./setup.sh` pour les dépendances verrouillées et le build frontend ; ne pas copier la base de cette release sur la base active.
4. Configurer le chemin externe de la base, le secret de session stable et les limites communes. Avec cet environnement chargé, appliquer les ajouts idempotents :

```bash
PYTHONPATH=backend .venv/bin/python -c 'from lab.auth import init_db; from lab.job_store import init_jobs; init_db(); init_jobs()'
```

   Les tables `compute_jobs`, `compute_settings` et `revoked_sessions` sont ajoutées, ainsi que `users.api_key` si absent. Aucun utilisateur ni mot de passe n’est supprimé. Les démarrages web et worker exécutent également ces initialisations.
5. Démarrer le worker puis le serveur avec le superviseur retenu. Pour systemd, après adaptation et installation des fichiers : `systemctl daemon-reload`, puis démarrer et activer les deux services. Le redémarrage automatique est prévu en cas d’échec ; les enfants de calcul appartiennent au groupe du service.
6. Vérifier la santé, la connexion et la consultation des jobs, puis rouvrir le proxy. Mettre backend ET frontend à jour dans la même fenêtre : les anciennes interfaces attendent un modèle directement, alors que les trois routes de calcul renvoient maintenant un job 202. L’HTML utilise `Cache-Control: no-store` ; demander aux onglets déjà ouverts de recharger.

Les anciens jetons signés avec l’ancien secret devront être renouvelés par une connexion. Les comptes bcrypt existants restent compatibles, y compris ceux dont les anciens mots de passe sont plus courts que le minimum actuel d’inscription.

## Réglages et ressources

| Variable | Défaut | Effet |
|---|---:|---|
| `RESONANT_CONCURRENCY` | 1 | Calculs simultanés globaux, génération + optimisation + simplification ; plage 1–4 |
| `RESONANT_JOB_TIMEOUT` | 600 | Secondes maximales par processus, lancement et attente de slot compris ; plage 1–3600 |
| `RESONANT_MAX_JOBS` | 6 | Jobs queued/running au total ; également 2 par utilisateur |
| `RESONANT_QUEUE_TTL_SECONDS` | 86400 | Attente maximale en file avant échec ; minimum 60 s |
| `RESONANT_JOB_RETENTION_SECONDS` | 604800 | Conservation des jobs terminaux/résultats ; minimum 3600 s |
| `RESONANT_SQLITE_WAL` | 0 | WAL uniquement si explicitement activé après évaluation |

La concurrence est stockée dans SQLite et commune aux workers. Une modification incompatible pendant un calcul est refusée. Garder 1 sur e2-micro. Les enfants limitent les bibliothèques BLAS/OMP à un thread. Aucune transaction SQLite ne reste ouverte pendant la synthèse ou l’optimisation ; timeout de verrouillage 5 s. Le mode journal existant est conservé par défaut. WAL peut faciliter les lectures simultanées sur disque local, mais exige la gestion des fichiers associés et ne convient pas à un système de fichiers réseau arbitraire.

Le worker nettoie toutes les dix secondes ; les routes de jobs nettoient aussi. Après perte brutale d’un superviseur, une lease sans heartbeat depuis 30 s devient un échec terminal. Un watchdog enfant et des verrous de slots OS réduisent les risques de calcul orphelin ; une publication tardive est rejetée par le jeton de prise en charge. Les jobs en file persistent après redémarrage. Les entrées audio sont effacées au passage terminal, les résultats après la durée de rétention. L’espace SQLite libéré est réutilisable ; la taille physique du fichier ne diminue pas automatiquement. Planifier une maintenance disque séparée, sauvegardée et hors calcul avant tout VACUUM.

L’asynchronisme enlève la dépendance à la connexion HTTP ; il ne réduit pas le coût mathématique du calcul. L’analyse, les routes scientifiques de rendu et l’import restent synchrones : tous les 504 ne sont pas éliminés. Ne pas augmenter les timeouts pour masquer un calcul sans limites. Les réglages Nginx à 300 s évoqués dans le rapport et l’hypothèse de réduction CPU de la VM n’ont pas été vérifiés. Examiner sur la VM les métriques CPU/mémoire, processus, journaux web/worker/proxy et la configuration Nginx effective avant de conclure.

## Vérifications après déploiement

- `GET /api/health` doit répondre ; ne pas transmettre une clé à cette route publique.
- Connexion avec un compte existant ; `/api/me` et `Mon Lab` correspondent au propriétaire, déconnexion révoque la session.
- Worker vivant, même base que le web ; file drainée et logs d’échecs maîtrisés. Les détails sensibles ne doivent pas apparaître dans les journaux.
- Avec autorisation explicite pour un calcul en production seulement : courte demande, réponse 202 rapide, transitions et résultat ; rechargement de l’onglet, rendu local et téléchargement WAV.
- L’absence de clé `RESONANT_LAB_API_KEY` a empêché les contrôles API distants pendant ce travail. Pour un outil serveur autorisé, limiter l’en-tête `X-API-Key` au domaine exact fourni et refuser les redirections interdomaines. Aucune clé ne doit être envoyée à un outil tiers.
- Vérifier mobile/clavier et absence de requête `/api/render` pendant l’édition normale. Contrôler les limites disque et mémoire au cours d’un usage ordinaire, sans test de charge non autorisé.

## Retour arrière

Arrêter les nouvelles admissions, terminer/annuler les jobs, arrêter les deux processus, puis sauvegarder à nouveau la base. Restaurer la release précédente, ses assets et sa configuration privée. Garder la base courante : les ajouts sont non destructifs et les tables utilisateur restent lisibles par l’ancien code. **Ne pas restaurer aveuglément l’ancienne base**, ce qui effacerait les comptes et modifications postérieurs à la sauvegarde.

Une ancienne release sans jobs ne saura pas suivre les jobs existants : exporter les modèles réussis avant retour, les conserver en base, et informer les utilisateurs de la fin du suivi. Elle réintroduit éventuellement les requêtes de calcul longues et les défauts de sécurité antérieurs ; préférer une release connue sûre et compatible. Un retour aux anciens secrets de session ne doit pas réintroduire un secret public. Si une restauration complète de base s’avère indispensable, elle demande une décision explicite tenant compte de la perte de données récentes. Aucun retour arrière n’a été exécuté ici.

## Configuration finale de la VM romadem17

Les deux unités fournies sont configurées pour l’utilisateur `romadem17`, avec `WorkingDirectory=/home/romadem17/resonant-deploiement/resonant-lab` et des `ExecStart` dans ce répertoire. Elles lisent `/etc/resonant-lab.env`. Le fichier est lu par systemd : il peut rester `root:root`, mode 600, sans être lisible par nginx ni par le navigateur. Les scripts et `.venv` doivent être exécutables par `romadem17`, la base et son répertoire doivent être accessibles en écriture à ce compte.

`setup.sh` vérifie Python 3.12+ et Node 20+, crée/utilise `.venv`, vérifie son isolation et sa version, installe les dépendances verrouillées avec son propre Python, lance `pip check`, puis `npm ci --include=dev` et le build TypeScript/Vite. Cela conserve les dépendances nécessaires au build même avec `NODE_ENV=production`. Tout échec arrête le script. Aucune migration utilisateur n’y est lancée et les exemples ne sont plus écrasés par défaut ; `RESONANT_SETUP_FIXTURES=1 ./setup.sh` les régénère explicitement. Lancer setup comme `romadem17`, sans sudo, pour éviter des fichiers de build appartenant à root.

### Rotation réelle de la clé API

L’exemple versionné contient seulement un emplacement `RESONANT_LAB_API_KEY`. Une clé réelle ne doit pas être commise dans ce fichier. `scripts/rotate_api_key.py` génère 32 octets aléatoires avec `secrets`, écrit la clé dans le fichier privé (remplacement atomique, permissions 600), et remplace `users.api_key` pour **un seul compte applicatif existant**. L’ancienne clé de ce compte cesse alors de fonctionner ; aucun compte n’est créé. Le pseudo applicatif n’est pas forcément `romadem17`.

Après sauvegarde, configuration de la base existante hors checkout, et migration additive décrite plus haut :

```bash
cd /home/romadem17/resonant-deploiement/resonant-lab
# Uniquement si le fichier n’existe PAS déjà : ne pas écraser une configuration existante.
sudo install -m 600 deploy/resonant.env.example /etc/resonant-lab.env
sudoedit /etc/resonant-lab.env
# Corriger RESONANT_DB_PATH avant la rotation. Remplacer le pseudo ci-dessous.
sudo .venv/bin/python scripts/rotate_api_key.py --username 'PSEUDO_RESONANT_EXISTANT'
```

Sur une configuration existante, sauter `install` et conserver les réglages privés. Le secret de session existant est préservé ; s’il est encore l’emplacement d’exemple, un secret sécurisé est créé. Le script n’affiche aucune clé, y compris sur erreur, et ne lit pas celle exposée dans la conversation. Ne pas utiliser `cat` sur le fichier dans des journaux partagés. Les outils API autorisés devront recevoir la nouvelle valeur via leur environnement privé. Les services doivent être redémarrés après changement d’environnement ; une clé API SQLite renouvelée est prise en compte directement par les requêtes suivantes.

Faire la rotation en maintenance, sans appel API concurrent, avec sauvegarde préalable de la base et de l’environnement. SQLite et le système de fichiers ne forment pas une transaction atomique commune : une coupure machine au moment critique peut laisser deux valeurs incohérentes. Les erreurs ordinaires d’écriture annulent la transaction ; une erreur de commit tente de restaurer l’environnement. En cas de coupure, refaire une rotation pendant la maintenance pour rétablir une valeur commune. Les sauvegardes contenant l’ancienne clé restent privées et ne doivent pas être restaurées sans tenir compte de sa révocation.

### Maintenance Nginx 503

Fusionner `deploy/nginx-maintenance.conf` dans le bloc HTTPS existant. Remplacer son `location /` ou fusionner le garde-fichier dans le bloc actuel ; ne pas créer deux blocs `location /`. Conserver les certificats, ports et timeouts actuels. S’il existe des emplacements `/api` ou d’autres routes proxifiées distinctes, y ajouter également le garde-fichier, sinon ces routes restent ouvertes. Ne pas perturber l’emplacement des challenges ACME. Le snippet utilise une redirection interne vers une page statique avec statut **503** et `Retry-After: 120`, conformément aux directives [error_page](https://nginx.org/en/docs/http/ngx_http_core_module.html#error_page) et [if](https://nginx.org/en/docs/http/ngx_http_rewrite_module.html#if).

```bash
cd /home/romadem17/resonant-deploiement/resonant-lab
# Une fois le snippet fusionné dans la configuration existante :
sudo nginx -t && sudo systemctl reload nginx
sudo ./deploy/maintenance.sh on
# Vérifier un statut 503 et la page, sans clé API :
curl --silent --output /dev/null --write-out '%{http_code}\n' https://resonant-lab.servepics.com/
# Installer / relancer les services, contrôler ensuite l’API sur 127.0.0.1:8000.
sudo ./deploy/maintenance.sh off
```

Le script prépare `/var/lib/resonant-maintenance/maintenance.html` puis crée ou retire uniquement le marqueur `maintenance.flag`. Une fois Nginx configuré, les bascules ne nécessitent pas de reload. Désactiver la maintenance uniquement après vérification du web et du worker. Un 503 ferme les nouvelles requêtes ; il n’arrête pas les calculs déjà lancés ni les requêtes déjà acceptées. Les vérifications `nginx -t` et systemd sur la VM restent à exécuter par l’opérateur : aucun accès SSH ni déploiement n’a été utilisé pour cette préparation.

Validation de cette préparation : `PYTHON_BIN="$PWD/.venv/bin/python" NODE_ENV=production ./setup.sh` exécuté localement avec succès (pip, pip check, npm ci, TypeScript et Vite). Le lancement avec le Python système trop ancien est correctement refusé. Les tests de rotation utilisent uniquement des bases et secrets fictifs temporaires : renouvellement, isolation du compte, conservation du secret de session, refus d’un pseudo absent, rollback sur erreur d’écriture et refus d’écrire un secret dans le dépôt. Aucun secret réel n’a été généré dans l’exemple ni aucune clé de production modifiée. La nouvelle clé réelle sera créée par la commande de rotation sur la VM. `bash -n` et `git diff --check` réussissent ; Nginx et systemd ne sont pas disponibles localement pour leur validation native.
