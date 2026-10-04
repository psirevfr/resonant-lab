# Stabilisation et finalisation — rapport local

## Diagnostic vérifié

Le dépôt utilise React 19, TypeScript 5.8.3, Vite 6.4.3 et FastAPI 0.141.1, avec NumPy/SciPy et SQLite. Les versions exactes sont verrouillées dans les fichiers de dépendances. Aucune instruction AGENTS.md ni configuration du superviseur de production/Nginx n’a été trouvée. L’ancienne génération calculait dans la requête HTTP ; l’optimisation utilisait un exécuteur thread et des jobs exclusivement en mémoire, sans propriétaire persistant. Ce mécanisme ne satisfaisait donc pas les exigences de redémarrage et d’isolation CPU : il a été remplacé par une seule file SQLite commune.

Le navigateur disposait d’un `audioEngine.ts`, mais son ancien moteur additionnait des sinusoïdes sans respecter les traitements et connexions. Le moteur local exécute désormais réellement le graphe dans un Web Worker, et conserve l’export WAV local. Aucun déplacement du rendu normal vers le serveur n’a été introduit.

## Modifications par priorité et fichiers

- **P0** : `backend/lab/job_store.py` (persistance, quotas, idempotence, autorisations propriétaire, leases), `worker.py` (supervision et processus CPU séparés), `app.py` (contrats jobs et caches privés), `optimization.py` et `compact.py` (validation avant calcul). Une simplification sans modes compatibles est refusée avant mise en file.
- **P0 frontend** : `frontend/src/hooks/useComputeJob.ts`, `api.ts`, `App.tsx` : double soumission bloquée, état immédiat, polling 3 s / 15 s onglet caché, backoff maximal 30 s, AbortController et nettoyage, reprise locale par utilisateur, erreurs réseau séparées des échecs du calcul. Une expiration de résultat libère l’interface. Les jobs conservés sont retrouvables depuis Mon Lab.
- **Audio local** : `audioEngine.ts`, `audioWorker.ts`, `audioDsp.ts`, `components/Keyboard.tsx`. Les filtres, enveloppes/ADSR, produits, sommes, délais, bruit et saturations sont évalués selon le graphe. Le WAV mono float32 préserve les dépassements de ±1. Le navigateur ne reçoit jamais de clé API serveur.
- **P1** : `backend/lab/auth.py`, `pages.py`, `backend/static/auth.css`, `auth.js` : session avec secret privé persistant, révocation serveur, contrôle d’origine et CSRF, formulaires pseudo/mot de passe accessibles et responsifs. Inscription conservée ; aucun parcours de récupération fictif.
- **P1 compte** : `components/Account.tsx` et routes `/api/me`, `/api/account`, `/api/logout` : profil réel, changement d’e-mail avec mot de passe actuel, calculs privés, déconnexion effective. Les paramètres avancés et le changement de mot de passe restent différés. Le profil se met à jour après enregistrement ; Échap ferme le panneau et rend le focus.
- **P2** : en-tête partagé dans `App.tsx` et pages d’authentification : libellé exact **LAB**, marque Résonant et navigation conservées.
- **Exploitation/tests** : `run.sh`, `run-web.sh`, `worker.sh`, `deploy/*`, `scripts/backup_db.py`, `scripts/client_fixtures.py`, `test.sh`, tests backend et `frontend/tests/*`. Le lanceur local démarre les deux processus ; les modèles systemd les supervisent séparément.

## Contrat API final

Toutes les routes ci-dessous sont sous `/api`. Les appels navigateur utilisent la session et le jeton CSRF pour les écritures. Une clé API serveur correspond à un utilisateur existant ; elle ne permet pas d’accéder aux jobs d’autrui ni aux pages privées sans session.

`POST /api/generate`, `/api/optimize` et `/api/compact` valident les entrées puis renvoient **202**, sans attendre le calcul. Les corps de demande scientifique restent ceux du schéma existant. Exemple abrégé :

```json
{"id":"identifiant-opaque","kind":"generate","status":"queued","created":1791000000,"started":null,"finished":null,"progress":{},"error":null,"cancel_requested":false,"status_url":"/api/jobs/identifiant-opaque","result_url":"/api/jobs/identifiant-opaque/result"}
```

`GET /api/jobs` liste les 20 derniers jobs conservés du propriétaire ; `GET /api/jobs/{id}` fournit les métadonnées ; `GET /api/jobs/{id}/result` fournit le modèle/candidats ou l’ancien résultat d’optimisation/simplification lorsque le statut est `succeeded`, sinon 409. Un job absent ou appartenant à un autre utilisateur renvoie 404. Les dates sont des secondes Unix, les chemins restent relatifs au même domaine.

Statuts réels : `queued`, `running`, `succeeded`, `failed`, `cancelled`. `POST /api/jobs/{id}/cancel` annule immédiatement une attente, ou demande l’arrêt du processus actif ; aucun résultat annulé n’est exposé. L’erreur publique ne contient ni traceback ni chemin serveur. Seule l’optimisation fournit sa progression mesurée ; la génération utilise un indicateur indéterminé.

L’en-tête **Idempotency-Key** (1–100 caractères) est lié au propriétaire et à la demande. Répéter la même demande avec la même clé récupère le même job, y compris après perte de la réponse et disparition du cache WAV. Une demande différente avec cette clé renvoie 409. La garantie dure le temps de conservation du job : après nettoyage, une nouvelle soumission peut recalculer. Sans clé, deux requêtes distinctes peuvent produire deux jobs. File pleine : 429 avec Retry-After 15, maximum 6 jobs actifs au total et 2 par propriétaire par défaut.

## Worker et reprise

Lancement local `./run.sh` ; lancement supervisé `./worker.sh` et `./run-web.sh`, avec environnement partagé. La concurrence initiale est **un calcul lourd**, commune aux trois traitements. Prise SQLite atomique, transactions courtes, sous-processus spawn, threads BLAS limités, timeout 600 s, heartbeat toutes les 2 s et lease 30 s. Aucun nouveau service Redis/Celery.

Après interruption, les jobs en file sont disponibles ; les calculs interrompus sont marqués en échec, sans relance automatique. Les résultats/états survivent au redémarrage et à la fermeture de l’onglet. Les WAV originaux en cache ne survivent pas au serveur : le résultat mathématique reste récupérable, mais une nouvelle importation peut être nécessaire pour comparer ou relancer une optimisation. Conservation par défaut : 24 h d’attente, 7 jours de résultats ; entrées effacées au statut terminal. Les durées et réglages sont documentés dans [DEPLOIEMENT.md](DEPLOIEMENT.md).

## Validation et limites

La commande `./test.sh` exécute les tests Python/API dans des bases temporaires, génère de petites références DSP puis exécute les tests Node, TypeScript et Vite. Les calculs lourds de production ne sont jamais déclenchés par ces tests. Les cas couvrent notamment soumission sans calcul HTTP, entrées invalides, propriétaires, quotas, prise concurrente entre processus, timeout, annulation, résultat, leases, nettoyage, authentification/CSRF/révocation et compatibilité DSP/WAV. Dernier passage exécuté : **62 tests Python réussis, 18 tests Node réussis, TypeScript et build Vite réussis**. `bash -n run.sh run-web.sh worker.sh test.sh` réussit également. Un démarrage réel de `./run.sh` sur le port de test 8002 a répondu 200 à la route de santé ; SIGTERM a arrêté le serveur et terminé le lanceur après attente des enfants. Le scan des fichiers texte suivis et du bundle ne trouve aucune clé au format de production divulgué. Trois avertissements de dépréciation FastAPI/Starlette subsistent ; aucun outil de lint n’est configuré.

Contrôles navigateur locaux exécutés : double clic → un seul job queued dans SQLite ; rechargement → reprise du suivi ; démarrage worker → résultat chargé ; export WAV téléchargé et contrôlé. Mise à jour de l’e-mail du compte fictif, fermeture par Échap, déconnexion et connexion au clavier, liste des résultats après reconnexion : vérifiés. Coupure volontaire du serveur de test : message d’indisponibilité réseau distinct d’un échec, puis récupération automatique du résultat après redémarrage. Formulaire de connexion contrôlé à 390 × 844 pixels. Aucun message console de niveau erreur observé pendant le parcours normal avant la coupure volontaire. La capture `connexion-20261003.jpg` illustre la nouvelle connexion locale, sans données privées. Les scénarios UI de session expirée et d’échec confirmé du calcul n’ont pas été simulés dans le navigateur ; les contrats backend correspondants sont testés, mais cette partie de la validation visuelle reste à compléter. Les tests automatisés ne constituent pas un contrôle complet de tous les navigateurs ou lecteurs d’écran. Aucun test de charge, connexion matérielle MIDI, inspection VM/Nginx ou déploiement distant n’a été réalisé ; `RESONANT_LAB_API_KEY` est absent de l’environnement. L’intégration réelle des services sur la VM reste à vérifier après un déploiement autorisé.

Le bruit blanc local est déterministe dans le navigateur mais utilise une séquence différente de NumPy : les réalisations ne sont pas identiques échantillon par échantillon. Les vues FFT locales ont une résolution différente des vues scientifiques Python ; elles ne doivent pas être utilisées pour prétendre à une parité numérique des mesures. Les modèles et les traitements déterministes font l’objet de tests croisés Python/TypeScript. La précision perceptive sur tout le clavier et toutes les familles de piano reste expérimentale.

L’asynchronisme ne promet ni une puissance CPU supplémentaire ni la disparition de tous les 504. Les routes d’analyse/rendu scientifique restent synchrones, la file est bornée mais le stockage doit être surveillé, et une absence de worker laisse les demandes attendre jusqu’à leur expiration. La base a été retirée du suivi Git sans supprimer le fichier local ; les anciennes révisions restent un risque de confidentialité à traiter séparément. La clé divulguée dans la conversation doit être renouvelée par l’opérateur ; elle n’a pas été recopiée par ces modifications.

Procédure de sauvegarde, migration additive, mise à jour coordonnée, vérification et retour arrière : [DEPLOIEMENT.md](DEPLOIEMENT.md).
