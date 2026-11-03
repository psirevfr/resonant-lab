# Atelier de simulation électronique — audit Lot 0 et première tranche Lot 1

> État historique du 1er novembre. La [livraison du 3 novembre](REFONTE_ATELIER_2026-11-03.md) remplace l’intégration imbriquée par les espaces `/atelier` et `/analyse`, avec un nouveau projet libre et un solveur WebAssembly sur l’appareil. Le prototype RC natif ci-dessous est conservé pour compatibilité, sans être le chemin de la nouvelle interface.

**Date :** 1er novembre 2026
**Dépôt examiné :** branche locale `main`; deux commits documentaires antérieurs étaient déjà non poussés au début des changements de simulation.
**Portée :** audit du code, vérification des références, puis tranche RC locale. Aucun changement de production ni essai sur matériel n’a été effectué.

## Résumé

L’atelier matériel existant demeure un configurateur illustratif piloté par le patch audio. Il ne transforme pas encore le patch complet en circuit électrique. Le nouveau workbench RC introduit un projet commun très limité pour un circuit pédagogique, sans encore unifier le schéma de synthèse, la breadboard du montage Teensy et les composants électriques.

Le moteur retenu est **ngspice natif**, lancé comme sous-processus isolé depuis le backend local et piloté par un adaptateur au modèle de projet Résonant. Ngspice documente également un mode bibliothèque avec contrôle et callbacks. Le binaire local **ngspice 47** a maintenant été installé après autorisation de l’utilisateur.

La première tranche Lot 1 est maintenant implémentée : projet RC versionné, valeurs éditables, schéma 2D, montage de breadboard 3D, simulation transitoire ngspice réelle, oscilloscope issu des vecteurs du solveur et sauvegarde/rechargement navigateur. La topologie est volontairement fixe et bornée ; ce n’est pas encore un éditeur de circuits générique.

## Première tranche Lot 1 — résultat reproductible

- Projet JSON version 1 : source échelon 0→5 V, résistance série R1 et condensateur C1 vers la masse. Les valeurs R/C alimentent le schéma 2D, les étiquettes du montage Three.js, la requête API et le calcul de référence affiché.
- Le navigateur ne transmet ni netlist ni commande SPICE. Le backend n’accepte qu’un modèle Pydantic fermé, rejette les champs supplémentaires, borne R, C et `R × C`, génère une netlist fixe et l’exécute sans shell.
- `POST /api/circuit/simulate` hérite du contrôle de session existant, applique une limite de 30 simulations/minute/utilisateur et n’autorise qu’une simulation à la fois. Le processus dispose d’un délai maximal de 5 s ; le fichier de trace est limité à 2 Mo et la sortie à 20 000 points, décimée à 513 points pour l’affichage. Si ngspice manque, l’API répond 503 sans inventer de courbe.
- Enregistrer/recharger conserve le projet sur l’appareil via `localStorage`. Aucune donnée de projet n’est envoyée à Drive ou Gemini.
- Le panneau de portée trace V(in) et V(out), identifie l’analyse comme transitoire et compare τ théorique à τ mesurée dans la trace. Ce premier scope n’offre pas encore le placement libre de sondes.

### Mesures obtenues

Pour `R = 1 kΩ`, `C = 1 µF`, ngspice 47 a retourné :

| Mesure | Valeur |
|---|---:|
| τ théorique (`R × C`) | 1,000000 ms |
| τ mesurée au franchissement de 63,212 % de 5 V | 1,000002 ms |
| Coupure théorique | 159,154943 Hz |
| Points calculés / affichés | 530 / 513 |

Le circuit diviseur de référence 5 V, 1 kΩ / 1 kΩ a aussi été exécuté avec ngspice : `V(out) = 2,500000 V`, courant de source en valeur absolue `2,500 mA`. Ces valeurs analytiques servent de contrôles numériques ; elles ne valident pas encore une construction physique.

### Tests exécutés

- `PYTHONPATH=backend .venv/bin/pytest backend/tests/test_circuit_sim.py -q` : **7 réussis** avec ngspice 47 installé.
- `./test.sh` : **139 tests backend réussis**, **24 tests frontend réussis**, build Vite/TypeScript réussi.
- Les tests couvrent : diviseur 2,5 V, réponse RC 1 ms, petite constante de temps et bornes du nombre de points, validation des entrées, refus d’une netlist arbitraire et réponse 503 en l’absence du moteur.
- Avertissements existants pendant la suite : FastAPI `on_event` déprécié et dépréciation `TestClient`/httpx. Aucun test de production ni test de charge n’a été exécuté.

Le parcours navigateur manuel de toutes les actions (clic simulation, édition, enregistrement puis rechargement) reste à faire. Le build compile ces vues ; l’API et le moteur ont été validés par TestClient et des exécutions ngspice locales.

## État vérifié dans le dépôt

| Domaine | État constaté |
|---|---|
| Intégration | L’onglet `Montage physique` est branché dans `frontend/src/App.tsx` et reçoit `patch` et `analysis`. |
| Vue 2D | Le schéma existant MIDI → Teensy → shield reste fixe. Le nouveau schéma RC SVG prend R/C du projet commun. |
| Vue 3D | `CircuitScene3D.tsx` reste un modèle illustratif de l’instrument. `RCCircuit3D.tsx` ajoute une breadboard RC Three.js où valeurs et étiquettes reflètent le projet RC, mais ses trous et fils ne sont pas encore une netlist éditable. |
| Catalogue | `hardwareParts` est une liste codée en dur de la Teensy, du clavier, du shield, de la breadboard, de fils et câbles. Il n’y a ni empreinte de broche normalisée ni modèle électrique associé. |
| Simulation | L’API `/api/circuit/simulate` simule uniquement une réponse RC transitoire réelle via ngspice. Aucun solveur générique ni analyse du montage Teensy n’existe encore. |
| Persistance | Le prototype sauvegarde/recharge ses deux valeurs R/C et son nom via `localStorage`. Il ne sauvegarde pas encore pins, réseaux, placements éditables ni sondes. |
| Lien avec le patch | Le patch est résumé par type de bloc, mais le firmware est construit par `buildTeensySketch(patch, analysis)`. Lorsqu’une analyse est disponible, `modelModes()` prend les partiels de l’analyse, au lieu de traduire les modes du patch choisi. Le cas précédemment testé de 38 modes dans le patch et 13 partiels d’analyse aboutit donc à un firmware de 13 modes. |
| Dépendances | `frontend/package.json` ne référence pas de moteur de circuit. ngspice 47 est présent via Homebrew sur cette machine, pas livré dans le dépôt ; Docker n’est pas disponible dans le PATH examiné. |

### Conséquence produit

La scène actuelle est un guide visuel de montage possible, pas le rendu d’un circuit qui peut être édité et simulé. Le firmware généré est un prototype de synthèse additive ; il ne modélise pas le circuit électrique affiché et ne reproduit pas encore tous les blocs du patch.

## Évaluation des moteurs consultés

### ngspice — recommandé comme référence numérique

Le projet ngspice documente une bibliothèque partagée permettant d’envoyer une netlist, de contrôler la simulation et de recevoir des résultats par callbacks. Ngspice n’apporte pas l’éditeur graphique : Résonant doit posséder son modèle de projet et ses vues. Le projet indique que la majeure partie du code est sous licence BSD modifiée, avec des exceptions/composants sous d’autres licences ; un binaire et toutes ses options doivent donc être audités précisément avant redistribution.

### CircuitJS1 — intéressant pour l’interface pédagogique, licence à arbitrer

Le dépôt officiel décrit un simulateur navigateur, un mode iframe/intégration et une interface JavaScript. Son README place le logiciel sous GPL version 2 ou ultérieure. L’incorporer ou distribuer son code dans le produit Résonant aurait des conséquences de licence à examiner. Je ne l’ai donc ni copié ni ajouté. L’intégration d’une page distante ne fournirait pas à elle seule la synchronisation requise entre le modèle Résonant, les réseaux, la vue 3D et la sauvegarde.

### ngspice WebAssembly tiers — candidat d’expérimentation seulement

Le dépôt `z-wasm/ngspice-wasm` indique que c’est une compilation non affiliée au projet ngspice. Il documente notamment l’absence de `dlopen`, de signaux POSIX et de multithreading, ainsi que le système de fichiers MEMFS en mémoire. Cela peut convenir à un essai limité dans un Worker navigateur, mais ne constitue pas encore une base de production vérifiée. Il faudrait pinner une révision, contrôler les sources et licences incluses, compiler un artefact reproductible, comparer ses résultats à ngspice natif et mesurer la taille/latence avant adoption.

## Décisions pour la suite des lots

1. **Modèle commun versionné** comme source de vérité : identités des composants, types, valeurs, broches, réseaux électriques, référence de masse, coordonnées 2D, emplacement physique, sondes et lien vers le patch source. Les positions et connexions sont des propriétés distinctes.
2. **Premier circuit** est réalisé pour l’exemple RC. Il reste à relier ultérieurement un projet réel de breadboard à la simulation plutôt qu’à un dessin topologique fixe.
3. **Moteur réel : ngspice** est invoqué comme processus fils avec netlist générée côté serveur. Avant d’utiliser le service au-delà du petit circuit borné, isoler davantage les calculs (processus/worker dédié, contrôle mémoire et arrêt effectif) et tester les limites serveur.
4. **Local d’abord, pas de déploiement automatique.** Le binaire est installé seulement dans l’environnement local. Une production sans ngspice retourne explicitement 503 ; aucun service ou workflow de déploiement n’a été modifié.
5. **Vues communes** sont réalisées seulement pour R/C : les valeurs se synchronisent entre contrôles, schéma, étiquettes 3D et requête solveur. Les coordonnées restent non éditables et les réseaux de trous ne déterminent pas la connectivité.
6. **Mesures issues du simulateur** : la trace réelle est affichée en scope. Les sondes sont fixes sur `vin` et `vout`, sans acquisition libre, déclenchement ou tension différentielle.
7. **Sauvegarde/rechargement** est réalisé localement pour le prototype avec un schéma versionné. Le rattachement au compte Mon Lab et aux permissions reste à concevoir.

Ce choix évite de faire dépendre le produit d’un code GPL copié. Il n’entraîne pas une licence juridique complète : les modules réellement inclus et les avis de redistribution devront être vérifiés avec les artefacts et options sélectionnés.

## Limites avant staging ou déploiement

Le prototype marche localement parce que ngspice 47 est installé sur cette machine. Cette dépendance native n’est pas provisionnée par le dépôt, `setup.sh` ni le workflow de déploiement. L’API reste disponible mais renvoie 503 si le binaire est absent. Avant un déploiement, il faut une décision et une procédure de provisionnement/référence pour staging, puis des tests de sécurité et de charge bornés. Rien n’a été poussé ni déployé.

**Prochaine étape recommandée :** compléter le projet commun avec des composants/pins/réseaux éditables et définir précisément la connectivité électrique de la breadboard, puis créer une interface de moteur pour ngspice. Tester les erreurs topologiques et les circuits de référence avant d’ajouter les autres composants. Évaluer ensuite un worker WebAssembly distinct, contre ngspice natif.

## Plan par lots

| Lot | Résultat vérifiable |
|---|---|
| 0 — audit et architecture | Réalisé ici : état, contraintes de licence, choix moteur, circuit de référence et limites documentés. |
| 1 — tranche verticale | Première tranche RC locale réalisée : schéma et scène 3D, simulation réelle, scope fixe, valeurs éditables et sauvegarde locale. Connectivité libre, sondes libres et tests manuels navigateur restent à terminer. |
| 2 — édition et breadboard | Pins, règles de connectivité, rails et coupure centrale validés par tests. |
| 3 — instruments | Sondes, acquisition et mesures dérivées des vrais vecteurs simulés. |
| 4 — catalogue | Composants ajoutés seulement avec modèles et tests numériques de référence. |
| 5 — traduction Résonant | Couverture explicite des blocs pris en charge et rapport d’omissions, sans substituer les partiels de l’analyse au patch sélectionné. |
| 6 — DSP et firmware | Noyau portable uniquement si la comparaison et les contraintes Teensy le justifient ; compilation et essai matériel séparément attestés. |
| 7–8 — extensions et recette | Moteur local/WASM, sécurité, compatibilité, accessibilité, performances et documentation. |

## Sources techniques consultées

- [ngspice — bibliothèque partagée et callbacks](https://ngspice.sourceforge.io/shared.html)
- [ngspice — informations développeur et licences](https://ngspice.sourceforge.io/devel.html)
- [CircuitJS1 — dépôt officiel, intégration et licence GPL-2.0-or-later](https://github.com/pfalstad/circuitjs1/blob/master/README.md)
- [CircuitJS — interface JavaScript documentée](https://www.falstad.com/circuit/doc/js-interface.html)
- [ngspice-wasm — dépôt tiers et limitations déclarées](https://github.com/z-wasm/ngspice-wasm)
