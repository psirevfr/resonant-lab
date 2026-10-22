# Audit du 22 octobre 2026

L'audit porte sur le dépôt, des tests locaux avec données synthétiques, quelques
requêtes publiques et une inspection SSH de la VM via la console Google Cloud.
Ce n'est ni un test d'intrusion exhaustif, ni une garantie d'absence de faille.
Aucun calcul lourd, création de compte, mise à jour système ou redémarrage n'a été
lancé en production pendant l'inspection. Le push déclenche le CI/CD autorisé.

## PHP : exposition examinée

L'avis officiel du 21 octobre concerne CVE-2026-109618 et CVE-2026-109619, deux
exécutions de code à distance dans PHP. Correctifs amont : 8.2.35, 8.3.36,
8.4.27 et 8.5.12 ; tenir compte des correctifs rétroportés des distributions.
Source : https://www.php.net/archive/2026.php#2026-10-21-5

Résonant utilise FastAPI/Python et React/Vite. Aucun fichier PHP ni handler
FastCGI dans le dépôt. Sur la VM : aucun paquet PHP installé détecté par
`dpkg-query` (l'entrée php-crypt-gpg est not-installed), aucune directive
PHP/FastCGI dans la configuration effective `nginx -T`. L'application n'est donc
pas directement exposée à ces deux failles dans le périmètre constaté. Des
logiciels embarqués/conteneurs non inventoriés ne sont pas couverts.

## Constats et corrections

| Point | Preuve / correction |
|---|---|
| Dépendances | Avant : avis Vite (dont un élevé), certifi, python-jose et ecdsa. Vite 6.4.5, certifi 2026.10.19, remplacement de python-jose par PyJWT 2.15.1, retrait d'ecdsa. Aucun avis connu dans les versions verrouillées après correction. |
| Sessions | HS256 explicitement imposé, expiration obligatoire, taille de jeton bornée. Test de compatibilité avec le format des anciens jetons, refus alg=none, mauvaise signature, absence d'expiration, séparation visiteur/compte. Le secret n'est pas renouvelé. |
| Connexion | Quotas SQLite atomiques, persistants et communs aux processus ; 10 soumissions/pseudo/10 min, 40/IP/10 min. Bcrypt est aussi vérifié pour un pseudo inconnu afin de réduire les différences de temps. |
| Autres quotas | 5 inscriptions/IP/heure, 40 nouvelles sessions visiteur/IP/heure, 10 confirmations du mot de passe du compte/10 min. Une session visiteur existante reste utilisable. Réponse 429 avec Retry-After. |
| Confidentialité des quotas | Empreintes HMAC des identités, aucune IP/pseudo brute dans la table ; fenêtres au plus 1 h, suppression à la tentative suivante ou maintenance du worker ; 10 000 compteurs maximum. Pas une protection DDoS exhaustive. |
| Entrées malformées | Origines invalides ou de schéma différent refusées ; CSRF non ASCII refusé sans 500 ; erreurs de validation sans réexposition des mots de passe/entrées ; Range trop long ignoré sans conversion entière excessive. |
| Navigateur | nosniff, Referrer-Policy, Permissions-Policy sur les réponses, CSP pour base-uri/object-src/form-action/frame-ancestors, HSTS 180 jours sur HTTPS seulement. Les exports actifs restent des pièces jointes avec sandbox. La CSP ne bloque pas tous les scripts : ne pas la présenter comme une protection XSS complète. |
| Base privée | La base active de la VM était en 0644 : passée en 0600, sans modifier ses données. init_db applique désormais 0600. session.key et /etc/resonant-lab.env étaient déjà en 0600. |
| CI/CD | Action SSH épinglée au SHA officiel correspondant à v1.0.3 ; permissions GitHub contents:read. Secret SSH_HOST_FINGERPRINT prévu, à configurer pour réellement vérifier l'identité du serveur. setup/CI retirent l'ancienne implémentation JWT ; pip install seul ne désinstalle pas les anciennes bibliothèques. |
| Git | Scan des fichiers suivis, de 3 archives ZIP (133 entrées), du bundle et comparaison avec les valeurs privées présentes localement : aucune correspondance détectée. Renforcement du gitignore pour clés et credentials. Ce scan ne certifie pas tout l'historique. |

La limitation IP repose sur request.client, pas sur le X-Forwarded-For brut.
Uvicorn doit faire confiance uniquement au proxy local. Les quotas par pseudo
peuvent imposer une attente temporaire même au propriétaire lors d'une attaque.
Les seuils peuvent être ajustés après observation ; ils ne changent pas le DSP.

## Production : éléments effectivement observés

- Négociations TLS réelles : TLS 1.0 et 1.1 refusés ; TLS 1.2 et 1.3 acceptés,
  avec vérification du certificat.
- HTTPS fonctionne, `/mon-lab/` et `/login` renvoient 200 ; `/login/` redirige
  correctement vers HTTPS `/login` ; `/` vers `/mon-lab/`.
- Sans session ni clé, `/api/me` renvoie 401. `.env`, `.git/config`, `users.db`
  et `index.php` renvoient 404. Cookies observés Secure + HttpOnly + SameSite.
- Avant déploiement des corrections : HSTS/Referrer-Policy/nosniff HTML absents.
- Nginx proxy vers 127.0.0.1:8000 ; Uvicorn écoute bien en loopback. Nginx ne
  contient ni `limit_req`, ni `client_max_body_size` explicite (défaut Nginx 1 MiB,
  susceptible de bloquer les WAV avant les limites de l'application).
- Deux services actifs : resonant-lab et resonant-worker. resonant-web inactif.
- **Incohérence confirmée** : web dans `/home/romadem17/resonant-lab`, workers
  Uvicorn = 2, aucune référence à /etc/resonant-lab.env dans son unité ; worker
  dans `/home/romadem17/resonant-deploiement/resonant-lab` avec
  RESONANT_DB_PATH vers la base de cet ancien répertoire. Les deux bases existent.
  La base web possède compute_workers ; l'ancienne non. Les deux files sont vides
  au moment du contrôle. Aucun contenu utilisateur n'a été lu ni fusionné.
- La divergence explique pourquoi ce worker ne consomme pas les jobs du site.
  Deux processus web rendent également les caches d'exports indépendants : un
  export préparé par un processus peut être absent de l'autre. Le template du
  service réel fixe un seul processus web et aligne le worker sur le même dépôt.
- Ubuntu 22.04.5 : mises à jour disponibles et reboot-required présent (noyau).
  L'ancien numéro amont de Nginx 1.18 ne suffit pas à conclure à une vulnérabilité :
  vérifier les rétroportages Ubuntu.
- Ports 20201/20202 : otelopscol et fluent-bit (Google Ops Agent). Leur filtrage
  GCP n'a pas été vérifié. UFW n'est pas installé ; cela ne prouve pas l'absence
  du pare-feu réseau GCP.

## Validation exécutée

- Backend : `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q` :
  **132 tests réussis**, trois avertissements de dépréciation préexistants.
- Frontend : 24 tests réussis ; build TypeScript/Vite réussi avec Vite 6.4.5.
- pip check : aucune dépendance cassée. Audits pip-audit et npm audit : zéro avis
  connu après correction (base d'avis consultée pendant cette session).
- Navigateur intégré, compte synthétique/base temporaire : visiteur, rendu local,
  blocage de l'export, connexion dans l'iframe, maintien du montage et accès aux
  exports. Pas d'erreur console observée. Capture : securite-connexion-20261022.png.
- Tests supplémentaires : quotas concurrents/expiration, cookie changé/XFF forgé,
  token historique, jetons invalides, session/CSRF, erreurs sans entrées privées,
  en-têtes sur erreurs 413 et pièces jointes, permissions SQLite sans perte de compte,
  inventaire hôte sans divulguer nginx -T, cohérence des unités proposées.
- Syntaxe des scripts shell, compilation Python et git diff --check exécutés.

Aucun appareil Android/iOS physique, paiement, compte réel, upload privé,
Drive/Gemini, analyse de compromission exhaustive, test DDoS ou restauration réelle
n'est couvert. RESONANT_LAB_API_KEY n'était pas disponible dans l'environnement
local ; aucune API protégée de production n'a été appelée avec une clé recopiée.

## Bascule des services : préparation, pas installation automatique

Les fichiers deploy/resonant-lab.service et deploy/resonant-worker.service ciblent
maintenant le dépôt **réellement utilisé par le site**. Le CI ne les installe pas.
La modification de ces services et du chemin de base en production doit être
approuvée avant exécution. Ne pas activer resonant-web en parallèle.

1. Prévoir une courte maintenance. Conserver des copies root:root 0600 des unités
   actuelles et de `/etc/resonant-lab.env` dans un répertoire privé de sauvegarde.
2. Sauvegarder séparément les deux SQLite via scripts/backup_db.py, pas via une
   copie d'une base vivante. Vérifier l'intégrité et ne pas fusionner les comptes.
3. Vérifier l'absence de calcul en cours, arrêter web et worker. Le worker gère
   les interruptions comme des échecs terminaux, pas comme des reprises aveugles.
4. Dans /etc/resonant-lab.env, changer **seulement** RESONANT_DB_PATH en
   `/home/romadem17/resonant-lab/users.db`. Conserver les secrets. Le web chargera
   désormais le secret configuré : ses sessions actuelles utilisant session.key
   peuvent expirer lors de cette bascule. Ne pas écraser le fichier par l'exemple.
5. Installer les deux unités proposées, daemon-reload, redémarrer les deux services.
   Aucun reset SQLite. init_db réalise uniquement des ajouts compatibles.
6. Vérifier WorkingDirectory, chemin réel de base de chaque processus, un seul
   processus HTTP et heartbeat sur la base du site (`scripts/check_jobs.py --db ...`).
   Tester ensuite une petite génération synthétique, connexion et export.
7. Au prochain déploiement, redémarrer également le worker aligné pour charger
   le nouveau code numérique ; adapter le workflow après cette bascule.

Nginx : deploy/nginx-security.conf.example fournit les directives à fusionner
manuellement dans la configuration existante, notamment limite d'import et quotas.
Sauvegarder la configuration, `nginx -t`, puis reload approuvé. Conserver TLS,
ACME, en-têtes de proxy et éventuelle maintenance. Pas de règle PHP à ajouter.
Mises à jour Ubuntu/reboot : opération distincte à planifier, pas exécutée ici.

Retour arrière : remettre les unités/configurations sauvegardées et leur chemin de
base, daemon-reload puis redémarrage approuvé. Ne pas remplacer la base active par
une ancienne sauvegarde après de nouvelles écritures utilisateur. La table additive
auth_rate_limits peut rester. Pour revenir au code précédent utilisant python-jose,
réinstaller aussi son ancien verrou de dépendances ; le retrait des anciens paquets
empêche un retour par simple git checkout. Le rollback réintroduirait les anciens
risques de dépendances. Préférer un correctif en avant.

Outil reproductible : `sudo python3 scripts/check_host_security.py --nginx`, sur
la VM. Aucun secret, configuration brute, appel réseau, mise à jour ou redémarrage.
Un champ null/not_checked est un contrôle manquant, jamais une preuve de sécurité.
