# Atelier de simulation électronique — audit initial (Lot 0)

**Date :** 1er novembre 2026
**Dépôt examiné :** `main`, commit local `9f3fe34` plus le commit 3D `38386f3`; la branche locale avait déjà un commit non poussé au début de cet audit.
**Portée :** lecture du code local et vérification documentaire des moteurs possibles. Aucun changement de production ni essai sur matériel n’a été effectué.

## Résumé

L’atelier existant est un configurateur illustratif de matériel, piloté par le patch audio pour présenter une nomenclature et produire un prototype de firmware. Il ne représente pas encore un projet électrique commun et ne simule aucun circuit. Le schéma SVG, la scène Three.js, la nomenclature et le sketch sont essentiellement des vues/contenus différents ; déplacer un composant n’édite pas un réseau électrique.

Le meilleur socle étudié pour une simulation électronique vérifiable est **ngspice natif**, lancé hors du processus web et piloté par un adaptateur au modèle de projet Résonant. Ngspice documente un mode bibliothèque avec contrôle et callbacks, mais celui-ci impose une intégration native ; pour une première coupe locale, une invocation isolée du solveur est plus simple à valider. Le binaire `ngspice` n’est pas installé dans l’environnement inspecté (`command -v ngspice` ne retourne aucun chemin). Il n’y a donc pas ici de moteur réel disponible pour exécuter et valider la tranche Lot 1.

Le livrable de ce lot est cet audit et la décision technique proposée. Je n’ai pas ajouté de faux oscilloscope ni réécrit un solveur général maison pour masquer l’absence de moteur.

## État vérifié dans le dépôt

| Domaine | État constaté |
|---|---|
| Intégration | L’onglet `Montage physique` est branché dans `frontend/src/App.tsx` et reçoit `patch` et `analysis`. |
| Vue 2D | `ElectronicsStudio.tsx` contient un SVG de câblage fixe pour MIDI → Teensy → shield → sortie audio. Les valeurs et coordonnées ne proviennent pas d’un projet électrique éditable. |
| Vue 3D | `CircuitScene3D.tsx` dessine des géométries Three.js illustratives et des fils prédéfinis. Il n’y a pas de connectivité électrique encodée dans la scène. |
| Catalogue | `hardwareParts` est une liste codée en dur de la Teensy, du clavier, du shield, de la breadboard, de fils et câbles. Il n’y a ni empreinte de broche normalisée ni modèle électrique associé. |
| Simulation | Aucun ngspice, CircuitJS, analyse SPICE, solveur de circuit, génération de netlist, mesure électrique ou oscilloscope n’est utilisé par le code de l’atelier. |
| Persistance | L’atelier ne sauvegarde ni projet électronique ni broches, réseaux, positions de composants ou sondes. |
| Lien avec le patch | Le patch est résumé par type de bloc, mais le firmware est construit par `buildTeensySketch(patch, analysis)`. Lorsqu’une analyse est disponible, `modelModes()` prend les partiels de l’analyse, au lieu de traduire les modes du patch choisi. Le cas précédemment testé de 38 modes dans le patch et 13 partiels d’analyse aboutit donc à un firmware de 13 modes. |
| Dépendances | `frontend/package.json` ne référence pas de moteur de circuit. Aucun exécutable ngspice ni Docker n’est disponible dans le PATH examiné. |

### Conséquence produit

La scène actuelle est un guide visuel de montage possible, pas le rendu d’un circuit qui peut être édité et simulé. Le firmware généré est un prototype de synthèse additive ; il ne modélise pas le circuit électrique affiché et ne reproduit pas encore tous les blocs du patch.

## Évaluation des moteurs consultés

### ngspice — recommandé comme référence numérique

Le projet ngspice documente une bibliothèque partagée permettant d’envoyer une netlist, de contrôler la simulation et de recevoir des résultats par callbacks. Ngspice n’apporte pas l’éditeur graphique : Résonant doit posséder son modèle de projet et ses vues. Le projet indique que la majeure partie du code est sous licence BSD modifiée, avec des exceptions/composants sous d’autres licences ; un binaire et toutes ses options doivent donc être audités précisément avant redistribution.

### CircuitJS1 — intéressant pour l’interface pédagogique, licence à arbitrer

Le dépôt officiel décrit un simulateur navigateur, un mode iframe/intégration et une interface JavaScript. Son README place le logiciel sous GPL version 2 ou ultérieure. L’incorporer ou distribuer son code dans le produit Résonant aurait des conséquences de licence à examiner. Je ne l’ai donc ni copié ni ajouté. L’intégration d’une page distante ne fournirait pas à elle seule la synchronisation requise entre le modèle Résonant, les réseaux, la vue 3D et la sauvegarde.

### ngspice WebAssembly tiers — candidat d’expérimentation seulement

Le dépôt `z-wasm/ngspice-wasm` indique que c’est une compilation non affiliée au projet ngspice. Il documente notamment l’absence de `dlopen`, de signaux POSIX et de multithreading, ainsi que le système de fichiers MEMFS en mémoire. Cela peut convenir à un essai limité dans un Worker navigateur, mais ne constitue pas encore une base de production vérifiée. Il faudrait pinner une révision, contrôler les sources et licences incluses, compiler un artefact reproductible, comparer ses résultats à ngspice natif et mesurer la taille/latence avant adoption.

## Décisions proposées pour le Lot 1

1. **Modèle commun versionné** comme source de vérité : identités des composants, types, valeurs, broches, réseaux électriques, référence de masse, coordonnées 2D, emplacement physique, sondes et lien vers le patch source. Les positions et connexions sont des propriétés distinctes.
2. **Première tranche bornée :** circuit RC série avec source échelon de 5 V, `R = 1 kΩ`, `C = 1 µF`. Sa réponse transitoire permet une première mesure d’oscilloscope ; la constante de temps attendue est `τ = RC = 1 ms`, et la coupure petit signal `fc = 1/(2πRC) ≈ 159,15 Hz`. Le diviseur 5 V / 1 kΩ / 1 kΩ du cahier des charges sera aussi un test DC de référence (2,5 V, 2,5 mA).
3. **Moteur réel : ngspice**, invoqué derrière un adaptateur isolé depuis un worker/processus de calcul, avec génération de netlist uniquement à partir du schéma validé. Aucun texte de netlist arbitraire, commande shell ou accès fichier libre provenant du navigateur. Limites CPU/mémoire/durée et annulation avant toute utilisation côté service.
4. **Local d’abord et pas de déploiement automatique.** Vérifier le chemin natif sur machine de développement/staging ; garder l’interface sans disponibilité simulée quand le moteur manque. Étudier le portage WASM séparément après comparaison au natif.
5. **Vues 2D et 3D alimentées par le même état :** le schéma montre symbole et réseaux ; la vue breadboard montre le placement matériel et ses groupes de trous connectés. Une modification de valeur se reflète dans toutes les vues ; déplacer une patte sur une autre bande de breadboard change effectivement le réseau.
6. **Mesures issues du simulateur :** transmettre les vecteurs de nœuds retournés par ngspice à un oscilloscope avec unité, durée simulée, pas et source de calcul. Pas de courbe synthétique si le moteur échoue.
7. **Sauvegarde/rechargement :** format versionné et données d’exemple synthétiques avant rattachement à Mon Lab. Les droits et propriétaires existants doivent être conservés.

Ce choix évite de faire dépendre le produit d’un code GPL copié. Il n’entraîne pas une licence juridique complète : les modules réellement inclus et les avis de redistribution devront être vérifiés avec les artefacts et options sélectionnés.

## Blocage avant l’intégration exécutable

La tranche verticale spécifiée exige un vrai solveur ; or aucun moteur n’est disponible dans l’environnement local. Installer ou compiler ngspice demande une nouvelle dépendance native et une chaîne de distribution. Ajouter cette dépendance aveuglément à `setup.sh`, au build Vite ou au workflow de déploiement serait incorrect : le déploiement GitHub Actions est configuré pour agir sur la production, que le brief demande de ne pas toucher.

**Décision recommandée :** valider ngspice natif comme moteur de référence et installer/préparer ce binaire uniquement en local ou en staging. Aucun choix GPL n’est nécessaire pour la tranche initiale. Après cette validation, l’implémentation peut commencer par modèle RC versionné → netlist générée → simulation transitoire ngspice → courbe d’oscilloscope et mesure τ → vues 2D/3D synchronisées → sauvegarde/rechargement. Le projet WebAssembly sera une étape distincte, mesurée contre cette référence.

## Plan par lots

| Lot | Résultat vérifiable |
|---|---|
| 0 — audit et architecture | Réalisé ici : état, contraintes de licence, choix proposé, test de référence et blocage identifiés. |
| 1 — tranche verticale | Projet RC commun, simulation ngspice réelle, édition synchronisée, courbe/mesure, vues 2D/3D et sauvegarde/rechargement locale. |
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
