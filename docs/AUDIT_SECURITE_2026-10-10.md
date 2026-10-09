# Audit ciblé du 10 octobre 2026

Audit du dépôt et de l'environnement local. Ce rapport ne certifie pas l'absence
de toute vulnérabilité, ni la configuration réelle de la VM.

## Corrections

- CSV : neutralisation des cellules textuelles pouvant être interprétées comme
  formules par un tableur. Les valeurs numériques restent numériques.
- Entrées : rejet de NaN et des infinis pour les sélections audio et les positions
  de début des demandes de calcul.
- API privée : `Cache-Control: no-store` et `X-Content-Type-Options: nosniff`,
  y compris sur les réponses d'erreur.
- Runtime : refus des liens symboliques, des fichiers hors liste autorisée et des
  manifestes invalides. La disponibilité vérifie les fichiers requis et leur taille.
  Ceci ne constitue pas une vérification cryptographique de chaque fichier à chaque
  requête. Le worker conserve sa vérification SHA-256 du paquet numérique.
- CI : arrêt au premier échec, pull en avance rapide uniquement, déploiements
  sérialisés, interpréteur `.venv` explicite, contrôle des dépendances et de la
  disponibilité du runtime avant redémarrage. Service et chemin existants conservés.
- Dépendances : `source-map-js` 1.2.1 → 1.2.2 ; pip 25.0.1 → 26.2.1.
  Le déploiement et setup utilisent désormais pip 26.2.1 et `requirements.lock.txt`.
- Extrait WAV : sélection avant conversion mono, sans modification des échantillons.

## Validation exécutée

- `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q` : **90 réussis**,
  trois avertissements de dépréciation préexistants. Neuf nouveaux cas couvrent
  CSV, nombres non finis, cache privé, runtime absent/corrompu/symlink et précision.
- `node frontend/tests/run.mjs` : **24 réussis**.
- `npm run build` dans frontend : TypeScript et Vite réussis ; assets produits inchangés.
- `npm audit --json` en ligne : un avis élevé sur source-map-js avant correction ;
  `npm update source-map-js --ignore-scripts --no-fund` : zéro avis après correction.
- `.venv/bin/python -m pip check` : aucune incompatibilité.
- pip-audit exécuté dans un environnement temporaire isolé sur les versions
  installées (`pip freeze --all`, `--no-deps --disable-pip`). Les réponses de la base
  d'avis comprennent des doublons ; après mise à jour pip, deux avis distincts restent.
- `bash -n` sur setup et le script distant du workflow ; `git diff --check` : réussis.
- Préparation locale du runtime : `ready: true`. Aucun téléchargement de données
  utilisateur ni modification de la base effectué pour l'audit.

Mesure de l'extraction sur Mac ARM64, WAV synthétique stéréo float64 de 60 secondes,
extrait de 0,2 seconde à partir de 0,1 seconde, cinq répétitions, horloge perf_counter,
allocations tracemalloc (hors allocation initiale du WAV) :

| Mesure | Avant | Après |
|---|---:|---:|
| Durée médiane | 30,808 ms | 0,074 ms |
| Pic d'allocation | 21 238 894 octets | 141 376 octets |

Le test sur données stéréo aléatoires vérifie l'égalité exacte des échantillons,
sans rééchantillonnage. Cette mesure ne démontre pas un gain global du solveur.

## Risques restants et solutions proposées

1. **Authentification sans limitation de tentatives applicative** : ajouter des
   limites de connexion/inscription et des limites de corps HTTP au proxy ; vérifier
   l'adresse client réellement transmise par Nginx avant de choisir la clé de quota.
2. **Avis Python sans correctif annoncé par l'audit** : ecdsa/CVE-2024-23342 concerne
   signature ECDSA et opérations privées ; python-jose/CVE-2026-85394 concerne
   confusion de clés asymétriques/HMAC. Ici les algorithmes JWT sont limités à HS256,
   avec un secret aléatoire privé ; aucune signature ECDSA n'est utilisée. Ne pas
   réutiliser une clé publique comme secret. Une migration JWT minimale et testée
   permettrait de supprimer ces dépendances plutôt que conserver ces avis.
3. **CPU serveur restant** : analyse, import et anciennes routes render/instrument
   exécutent encore des traitements côté web. Le mode local ne décharge donc pas
   totalement la VM. Porter l'analyse au worker local et limiter/superviser les
   routes de compatibilité avant toute revendication de scalabilité globale.
4. **Permissions CI** : SSH et secrets GitHub non accessibles à cet audit. Vérifier
   fingerprint SSH, droits sudo restreints et épinglage de l'action tierce à un SHA.
   Le déploiement n'est pas atomique : une installation échouée peut laisser des
   dépendances partiellement mises à jour, même si le redémarrage est empêché.
   Préférer ensuite des releases préparées séparément et une bascule réversible.
5. **Multi-processus et stockage** : les WAV importés restent en mémoire du processus
   web. Plusieurs processus web ou un redémarrage nécessitent une réimportation ;
   la persistance des jobs ne rend pas ces références persistantes.
6. **Interface** : le bundle principal mesure environ 5,38 Mo avant compression.
   Différer Plotly peut réduire le téléchargement initial ; appareils mobiles,
   lecteur audio et consommation mémoire globale non revalidés dans cette session.

Pas de scan intrusif, charge, panne ou appel lourd en production. Nginx, TLS,
pare-feu, sauvegardes, services actifs, secrets effectivement révoqués et intégrations
Google restent non vérifiés sur la VM. Le push autorisé déclenche le workflow ; son
succès doit être contrôlé dans GitHub Actions et sur le serveur.
