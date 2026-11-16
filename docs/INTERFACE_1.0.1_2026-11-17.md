# Interface 1.0.1 — 17 novembre 2026

## Modifications

- Suppression de la vue « Rack · tous les modules », de son composant et de ses styles. Le schéma de synthèse ouvre directement le câblage libre.
- Sélection persistante des câbles, avec surbrillance et zone de clic élargie. Suppr ou Retour arrière retire la sélection quand le schéma a le focus. Les champs de saisie conservent leur comportement habituel. Une sélection seule ne modifie plus le modèle et ne relance pas son rendu.
- Sélectionner un câble ou le fond ferme l'inspecteur au lieu d'ouvrir un panneau vide. Sélectionner un module ouvre ses réglages.
- Retrait des légendes permanentes, compteurs de bordure et textes de manipulation dans les vues audio, schéma et montage. Les noms, valeurs, boutons, unités et attributions de bibliothèques restent présents. Les explications mathématiques sont disponibles dans des sections repliées ; les erreurs et avertissements importants restent visibles.
- Rémi est accessible par « Aide » dans la barre commune. Son accueil présente les deux espaces ; sa visite pointe neuf outils, en phrases courtes. Elle navigue entre l'atelier et l'analyse sans charger un exemple, lancer un calcul ou remplacer le projet. Les explications simples de chaque module restent accessibles dans l'inspecteur. La nouvelle présentation est proposée une fois par utilisateur/navigateur, puis réouvrable à tout moment.
- Pied de page commun : « © r0m1 - étudiant en PSI » et « Version 1.0.1 ». Version mise à jour dans le paquet frontend et son verrou ; versions des formats de modèles et projets inchangées.

## Vérifications exécutées

```bash
npm --prefix frontend run build
node frontend/tests/run.mjs
git diff --check
```

Build TypeScript/Vite réussi ; **62 tests frontend réussis**. L'avertissement Vite préexistant concernant le module Node `module` dans ngspice demeure. Aucun changement de dépendance.

Recette dans le navigateur intégré, serveur local isolé sur 127.0.0.1:8022, base de test distincte :

| Contrôle réel | Résultat |
|---|---|
| Schéma initial | 6 modules, 5 câbles, aucune vue Rack |
| Clic puis Suppr sur un câble | 4 câbles, 6 modules |
| Clic puis Retour arrière sur un autre câble | Suppression du seul câble ; aucun inspecteur vide |
| Retour arrière dans une valeur de filtre | Valeur éditée ; 5 câbles et 6 modules conservés après restauration de la fixture |
| Recharge | Suppression précédente retrouvée dans le brouillon |
| Rémi | Accueil, fermeture par Échap et réouverture testés |
| Visite | 9 étapes parcourues ; chaque cible effectivement mise en évidence dans les deux espaces |
| Fin de visite puis retour à l'analyse | 6 modules et 5 câbles conservés ; retour du focus sur Aide |
| Format étroit | 390 × 844, largeur du document 390 ; guide et signature lisibles |
| Ordinateur | 1280 × 720, pied de page commun visible |

Le format étroit est une émulation de taille, pas un essai sur téléphone physique. Les captures sont dans `docs/images/guide-1.0.1-mobile.jpg` et `docs/images/cablage-1.0.1.jpg`.

Pendant une reconstruction locale, une page déjà ouverte pointait vers un ancien fichier de vue 2D supprimé par le build. La recharge après fin du build a résolu cette erreur ; les neuf étapes ont ensuite été validées. Ne pas reconstruire les assets sous une session de recette en cours et présenter ce cas comme un défaut du moteur de circuit.

Le dernier ajustement de présentation place également les erreurs de l'inspecteur hors des sections repliées ; son build a été contrôlé. Aucun nouveau test de calcul piano, d'écoute, MIDI physique ou de production n'était nécessaire à ces changements d'interface et n'a été exécuté pour ce lot.

## Fichiers principaux et livraison

- `frontend/src/components/Graph.tsx` : câblage, sélection et suppression.
- `frontend/src/App.tsx`, `Inspector.tsx`, `AnalysisPanel.tsx`, `AudioInventory.tsx` : présentation audio.
- `frontend/src/LabShell.tsx`, `LabGuide.tsx`, `GuidedTour.tsx`, `guideContent.ts` : guide commun et visite.
- `ArduinoWorkshop.tsx`, `Project2D.tsx`, `CircuitScene3D.tsx` : retrait des légendes permanentes.
- `frontend/src/version.ts`, fichiers de paquet, styles et `frontend/dist` : version et assets compilés.

Les fichiers privés et la base de recette restent ignorés. Contrôle des changements et du bundle contre les secrets locaux reconnus : aucune occurrence détectée. Aucune modification de la base active, des comptes, des contrôles d'accès ou des services de production.

Livraison en commit local. Aucun push ou déploiement pour ce lot. Pour une livraison autorisée, publier sources et assets du même build ensemble selon la procédure du dépôt. Retour arrière : restaurer le commit précédent d'interface avec son build ; aucune migration SQLite à annuler. Le stockage des projets et modèles reste compatible.
