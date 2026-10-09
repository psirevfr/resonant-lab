# Références audio temporaires

Le cache historique était partagé par tous les utilisateurs, limité à quatre
références et uniquement en mémoire. Une éviction ou un redémarrage faisait perdre
le WAV alors que son identifiant restait présent dans l'interface. C'est une cause
confirmée par le code et reproduite en test ; les processus de production précis
ayant provoqué chaque incident n'ont pas été observés.

Les nouveaux imports et démonstrations conservent désormais le WAV original dans
`.resonant-audio/`, à côté de la base effectivement configurée. Répertoire privé
0700, fichiers 0600, aucun montage statique, identifiants hexadécimaux générés et
refus des liens symboliques. L'index SQLite `audio_references` ne contient que les
métadonnées et le propriétaire : migration additive, aucun compte ni job supprimé.
Chaque rechargement hors cache vérifie le propriétaire ; une mauvaise identité
reçoit 404. Le cache mémoire reste limité à quatre références et 400 Mo (une grande
référence peut seule dépasser cette limite mémoire, comportement historique).

Configuration serveur facultative :

| Variable | Valeur par défaut | Signification |
|---|---:|---|
| RESONANT_AUDIO_TTL_SECONDS | 604800 | Rétention disque 7 jours depuis import |
| RESONANT_AUDIO_MAX_BYTES | 536870912 | Quota global de références validées 512 Mio |
| RESONANT_AUDIO_USER_MAX_BYTES | 268435456 | Quota par utilisateur 256 Mio |
| RESONANT_AUDIO_MIN_FREE_BYTES | 134217728 | Réserve disque avant écriture 128 Mio |

Une saturation refuse le nouvel import (HTTP 507), sans évincer les autres imports
encore valides. Les fichiers expirés sont nettoyés au prochain import. Après un crash,
les fichiers sans index sont nettoyés à l'import après une heure. Les fichiers en
cours d'écriture peuvent temporairement dépasser le quota de références validées ;
les limites d'upload/concurrence du proxy restent nécessaires. Ce stockage est une
référence de travail privée temporaire, pas une contribution ML ou un archivage
Drive. Aucun envoi tiers, aucune activation de consentement implicite.

Les références déjà perdues avant cette modification ne peuvent pas être récupérées :
réimporter une fois après mise à jour. Le code ne déplace pas les comptes ni la base.
Si la base est dans un répertoire non inscriptible ou protégé par systemd, autoriser
explicitement le sous-répertoire audio privé. Pour une sauvegarde durable, associer
la sauvegarde cohérente SQLite aux fichiers référencés. Retour arrière : l'ancien
code ignore la table additive et le dossier, mais retrouve sa limitation mémoire.

Validation : éviction après cinq nouveaux imports, perte totale du cache mémoire,
lecture par un processus Python distinct, isolation utilisateur, quota sans perte
des anciens fichiers, chemins invalides, expiration et liens symboliques. Tests
sur données synthétiques, sans réinitialisation de la base locale ou de production.
