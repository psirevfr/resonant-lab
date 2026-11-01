# Revue sécurité — 1 novembre 2026

## Mise à jour PHP

L’avis PHP du 21 octobre traite deux vulnérabilités critiques d’exécution de code
à distance, CVE-2026-109618 et CVE-2026-109619, touchant les installations PHP
qui servent des requêtes. Les versions amont corrigées sont 8.2.35, 8.3.36,
8.4.27 et 8.5.12 ; les distributions Linux peuvent publier des correctifs
rétroportés. PHP 8.2 arrive en fin de support le 31 décembre 2026. Référence :
<https://www.php.net/archive/2026.php#2026-10-21-5>.

L’avis du 23 octobre signale un scénario rare lié au suivi de progression des
uploads de session et recommande de désactiver `session.upload_progress.enabled`
jusqu’au correctif régulier si l’application change dynamiquement
`session.serialize_handler` avant `session_start()`. Le projet Resonant n’utilise
pas PHP et ne configure pas de sessions PHP.

Le 26 octobre, PHP a mis à jour ses paquets Windows pour Brotli 1.2.1 (CVE-2026-111497).
Cet avis concerne les bundles Windows PHP avec cURL et décompression HTTP
automatique activée ; il ne démontre pas une vulnérabilité du backend Python ni
des paquets Ubuntu de cette VM. La bibliothèque Brotli du système n’a pas été
inventoriée pendant cette revue.

## Résultats vérifiés

- Le dépôt est une application FastAPI/Python et React/Vite. Il ne contient pas
  de code PHP applicatif ni de configuration `fastcgi_pass`.
- Une requête publique dans le navigateur le 1 novembre a reçu `/login` en HTTP
  200 avec HSTS (`max-age=15552000`), `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: same-origin`, une Permissions-Policy fermée pour caméra,
  microphone et géolocalisation, et une CSP limitée aux directives
  `base-uri`, `object-src`, `frame-ancestors` et `form-action`.
- Le même en-tête révèle `Server: nginx/1.18.0 (Ubuntu)`. Cela divulgue une
  version, mais ne prouve pas qu’elle soit vulnérable : Ubuntu peut rétroporter
  les correctifs. La directive `server_tokens off` préparée dans
  `deploy/nginx-lab-security.conf` n’est pas confirmée active en production.
- `/index.php` a renvoyé 404. Cela confirme que ce chemin ne sert pas de page
  PHP ; à lui seul, ce résultat ne prouve pas qu’aucun runtime PHP n’existe sur
  la VM.
- Le dernier inventaire SSH de l’hôte, daté du 22 octobre, ne détectait pas de
  runtime PHP installé ni de handler PHP/FastCGI dans la configuration Nginx.
  L’inventaire système n’a pas pu être répété le 1 novembre, faute de console SSH
  disponible dans l’environnement courant. Les conteneurs ou autres hôtes ne
  sont pas couverts.

**Conclusion circonscrite :** aucun code PHP du site n’est présent dans le dépôt,
et les observations disponibles ne montrent pas de route PHP fonctionnelle. Les
CVE PHP du 21 octobre ne sont donc pas reliées au code web constaté. L’absence
actuelle de PHP sur toute l’infrastructure n’est pas certifiée tant que
l’inventaire root de la VM n’a pas été refait.

## Autres contrôles et limites

- Le build TypeScript/Vite courant réussit. La dernière exécution recensée avant
  cette refonte comptait 24 tests frontend et 132 tests backend réussis; la suite
  frontend n’a pas été rejouée après la nouvelle interface matérielle. Le
  backend n’a pas changé dans cette refonte. `pip check` ne signalait pas de
  dépendance cassée lors de la passe précédente.
- `npm audit` n’a pas pu atteindre `registry.npmjs.org` dans cet environnement.
  `pip-audit` n’est pas installé dans le venv. Aucun résultat d’audit distant des
  vulnérabilités de dépendances n’est revendiqué pour cette revue.
- Les tests backend ont produit trois avertissements de dépréciation existants
  (événements de cycle de vie FastAPI et `starlette.testclient`).
- La page locale a affiché la nouvelle interface, mais l’API de développement a
  répondu 500 ; le parcours complet de génération dans ce navigateur n’a pas été
  validé. Ce résultat local n’est pas un test de production.
- Les contrôles de configuration VM, de base de données, de comptes, de jobs, de
  sauvegarde et de pare-feu GCP du 22 octobre ne sont pas requalifiés comme des
  contrôles du 1 novembre. Aucun appel API protégé ni changement de production
  n’a été effectué pendant cette revue.

## Actions préparées / à vérifier

1. Reprendre l’inventaire sur la VM : paquets PHP installés, services PHP-FPM,
   processus/conteneurs, virtual hosts et directives Nginx. Si aucun PHP ne sert
   de requêtes, ne pas installer PHP pour cette application.
2. Réduire la divulgation de version avec `server_tokens off`, après sauvegarde,
   `nginx -t` et rechargement contrôlé. Les snippets `deploy/nginx-limits.conf`
   et `deploy/nginx-lab-security.conf` restent des fichiers de dépôt tant que
   leur installation effective n’est pas vérifiée.
3. Terminer la bascule déjà approuvée des services web/worker vers la même base
   après confirmation des sauvegardes prévues. Cette revue n’a pas exécuté cette
   bascule.
4. Refaire `npm audit` et `pip-audit` depuis un environnement ayant accès aux
   index officiels, puis conserver les rapports datés.
