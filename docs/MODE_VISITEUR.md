# Laboratoire libre, exports réservés aux comptes

L'entrée `/mon-lab/` sert l'interface sans demander de connexion. Un cookie
`visitor_token` signé, HttpOnly, SameSite=Lax et Secure hors loopback identifie une
session privée de 24 heures. Les visiteurs ne sont pas des lignes de la table users :
ils ont un propriétaire négatif distinct dans `visitor_sessions`. Le jeton utilise
un domaine de claims distinct (`purpose=visitor`) et ne peut pas servir de jeton
de compte, même s'il existe un compte nommé « visitor ».

Les analyses, imports, graphes, rendus locaux, clavier et calculs restent disponibles.
Les résultats serveur sont privés à leur propriétaire et conservés avec les règles
de jobs existantes. « Mon Lab → Mes calculs » est aussi disponible aux visiteurs.
Les modèles calculés localement restent dans l'onglet, comme auparavant ; cette
modification n'ajoute pas de sauvegarde automatique des modèles locaux après reload.
Quand le runtime est disponible, le mode visiteur sélectionne le calcul local par
défaut. Le choix serveur reste explicite et la concurrence CPU n'est pas augmentée.

## Connexion au moment d'exporter

Le bouton Exporter ouvre un panneau proposant connexion ou inscription. Les pages
d'authentification existantes sont présentées dans une iframe de même origine, avec
CSRF et gestionnaires de mots de passe conservés. Pas de changement de page du
laboratoire ni dépendance aux popups. CSP frame-ancestors self et X-Frame-Options
SAMEORIGIN empêchent l'encadrement par une autre origine.

Après une connexion réussie, les références audio et jobs visiteur sont rattachés
atomiquement au compte ; l'ancien cookie visiteur devient inutilisable. Les caches
du processus sont mis à jour et un autre processus peut recharger les références
depuis leur stockage privé. Les montages, analyses, résultats et audio en mémoire
du navigateur restent ouverts. CSRF est actualisé ; le suivi de job est transféré
au compte lorsqu'il n'y a pas déjà un suivi de compte en cours. Les collisions de
clés d'idempotence sont renommées sans perdre les jobs, consultables par leur ID.
Une réponse de soumission perdue lors d'une collision peut nécessiter de reprendre
le job depuis Mes calculs plutôt que répéter l'ancienne clé.

Les exports SVG/CSV, leur préparation et récupération ainsi que les routes WAV
de téléchargement et les anciens rendus audio serveur demandent un compte réel.
Le rendu actuel du site reste côté navigateur et accessible aux visiteurs. Les
PNG des graphiques utilisent aussi la préparation d'export protégée ; aucun bouton
Plotly de téléchargement direct ne reste disponible en mode visiteur.

Cette restriction protège les exports officiels, pas contre une capture du son,
des captures d'écran ou l'extraction par outils de développement. Un modèle rendu
localement et un son écoutable impliquent que les données sont accessibles à
l'appareil utilisateur. Ce mécanisme ne constitue donc pas une protection DRM.

## Ressources et rétention

- Deux jobs serveur visiteurs actifs au total, sans empêcher la capacité restante
  des comptes ; le plafond global existant et la limite par propriétaire restent.
- WAV visiteur : 32 Mo, quatre millions d'échantillons au total mono/stéréo ; compte :
  limites historiques 128 Mio / trente millions. Refus avant décodage complet.
  Un seul import à la fois par processus web, sinon 429 ; aucun changement de précision.
- Corps HTTP bornés avant JSON / spooling multipart : 2,1 Mo hors fichiers,
  33 Mo pour préparer un export et 128 Mio + 1 Mo pour importer un WAV. Les corps
  sans Content-Length sont également comptés, avec réponse 413 à dépassement.
- Références visiteurs temporaires purgées après 24 heures au prochain import,
  références des comptes selon la rétention audio existante. Quotas disque inchangés.
- Une session expirée n'est pas rattachée arbitrairement à un compte : réimporter
  la référence si nécessaire. Le cookie et le secret de signature doivent rester
  stables entre processus et redémarrages. Aucun consentement ML/Drive/Gemini activé.

La VM n'a pas fait l'objet d'un test de charge. Les limites proxy de requêtes et de
connexions restent à vérifier dans Nginx : les limites applicatives ne bloquent pas
un flood réseau ni la création abusive de comptes. Prévoir par exemple un quota IP
pour `/api/`, avec burst permettant les requêtes normales, et des limites spécifiques
aux connexions/inscriptions. Ne pas appliquer le quota API aux fichiers du runtime.

## Validation et déploiement

106 tests backend réussis (`PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q`), trois avertissements de dépréciation existants.
24 tests frontend réussis (`node frontend/tests/run.mjs`) et build TypeScript/Vite réussi (`npm --prefix frontend run build`).

Tests backend : entrée publique, cookies et CSRF, isolation de visiteurs, lecture
de jobs, refus des exports, transfert après connexion, invalidation de l'ancien
cookie, confusion de rôles, expiration, capacité de file, requêtes volumineuses
déclarées et chunked, auth intégrée et collision d'idempotence.

Navigateur intégré, compte fictif et base temporaire : analyse libre, génération
locale réelle (0,2 s, trois partiels, neuf modules), demande de connexion à l'export,
connexion intégrée, conservation du montage/du nom/de la référence/de l'analyse,
préparation JSON après connexion et téléchargement PNG protégé. Aucune erreur
console dans le parcours vérifié. Captures : `visiteur-export.png` et
`visiteur-connecte.png`. Pas de test physique mobile ou de compte de production.

Migration additive via init_db, sans réinitialiser SQLite ni créer de compte
visiteur. Backend et frontend doivent être mis à jour ensemble ; conserver une
sauvegarde cohérente et le secret de session existant. Le workflow effectue le
redémarrage autorisé ; vérifier son succès et le parcours visiteur après déploiement.
Le retour à l'ancien code conserve les tables ajoutées mais referme le laboratoire
aux visiteurs ; leurs références ne sont alors plus accessibles via l'ancienne UI.
