# Atelier principal et calcul sur l’appareil — livraison P0 et fondations P1

> Mise à jour : la [livraison maquette et catalogue du 4 novembre](MAQUETTE_ET_CATALOGUE_2026-11-04.md) ajoute la platine 830, le déplacement direct, les propriétés compactes, le catalogue de 29 familles et le câblage par double-clic. Les descriptions de la breadboard 10 colonnes et du déplacement avec Maj ci-dessous décrivent la version initiale.

Date : 3 novembre 2026. Travail local, sans déploiement ni modification de données de production. La mission globale P0–P3 reste en cours : cette livraison ne fournit pas encore un émulateur Arduino.

## État initial vérifié

Le dépôt utilisait React 19.3.0, Vite 6.4.5, Three.js 0.187.0, React Flow 12.12.0 et FastAPI 0.141.1. L’entrée était `App.tsx`, avec l’atelier électronique imbriqué dans le parcours audio. Les vues Teensy existantes étaient illustratives. Un premier prototype RC natif, ses tests et sa documentation étaient déjà modifiés localement : ils ont été conservés.

Le clavier avait un chemin de préparation/transposition serveur et identifiait ses voix essentiellement par numéro de note. Cela ne permettait pas d’isoler correctement deux sources ou deux canaux jouant la même note. Le firmware pouvait privilégier les partiels d’analyse au lieu des modes du graphe sélectionné.

Deux commits documentaires étaient déjà locaux et non poussés au début du travail. Aucune instruction `AGENTS.md` n’a été trouvée dans le périmètre examiné.

## Ce qui fonctionne maintenant

| Domaine | Implémentation réelle |
|---|---|
| Navigation | `/atelier` principal, `/analyse` secondaire. `/mon-lab/` reste accessible et mène à l’atelier via le shell. Menu avec deux entrées, état actif, Échap, focus initial, boucle de tabulation et retour du focus. |
| Conservation | Les deux espaces restent montés après leur première ouverture ; leurs documents sont distincts. Brouillons et sauvegarde explicite dans le stockage navigateur, par identifiant de session/compte. Avertissement à la fermeture si le montage n’est pas enregistré. |
| Atelier autonome | Projet vide, nouveau/ouvrir, exemples diviseur, RC et LED, sans import WAV. Bibliothèque, propriétés, code, nomenclature et instruments fermés au départ. |
| Édition | Ajout/suppression de composants ; valeurs ; positions 2D et 3D distinctes ; rotation 3D ; fils entre broches dans les deux vues ; suppression de fils ; annuler/rétablir. Déplacement 3D avec Maj + glisser ou coordonnées dans les propriétés. |
| Connectivité | Un seul projet versionné fournit composants, broches et fils aux deux vues et au solveur. Les positions ne créent pas de connexion implicite. |
| Breadboard | Modèle pédagogique de 10 colonnes : A–E par colonne, F–J séparés, quatre rails continus de dix contacts. Les groupes électriques sont effectivement fusionnés dans la netlist. Ce modèle n’est pas une breadboard commerciale 830 points. |
| Simulation | ngspice 46 WebAssembly, dans un Worker local. Netlist générée uniquement à partir des composants autorisés. R, C, alimentation DC/échelon, masse et LED simplifiée. Arduino Uno est explicitement visuel et bloque la simulation. |
| Mesures | Vecteurs réels ngspice, temps simulé, tension par réseau relative à la masse, min/max/valeur finale, panneau redimensionnable. Résultat lié à la révision ; édition = mesure obsolète. Changer l’excitation ou la fenêtre invalide la trace. |
| Sauvegarde | JSON version 1 validé : composants, paramètres, fils, positions, code et référence audio éventuelle. Import limité à 2 Mo. Export via la protection de téléchargement existante, avec connexion demandée au visiteur. |
| Audio | Analyse, génération, optimisation et simplification passent par le Worker Python/SciPy local. Le sélecteur serveur a disparu ; aucun repli automatique ni restauration automatique d’ancienne soumission serveur. Les résultats serveur historiques réussis restent récupérables. |
| MIDI | Route commune clic/clavier ordinateur/MIDI : source, canal, note 0–127, vélocité, sustain CC64, bend ±2 demi-tons, Note On de vélocité nulle, répétitions, limite de huit voix, déconnexion, perte de capture et extinction globale. Accès MIDI sur action explicite, sans SysEx. |
| Passerelle | « Créer un montage à partir de ce modèle » conserve le graphe sélectionné entier. Confirmation avant remplacement d’un montage existant et sauvegarde de celui-ci. Aucune prétention de traduction électrique complète. |
| Firmware existant | Extraction depuis les oscillateurs/modes du graphe sélectionné, sans remplacement par les partiels d’analyse ni troncature silencieuse à 24. Les omissions DSP restent explicitement signalées. |

## Lieu réel des calculs

| Opération | Lieu |
|---|---|
| Identification, optimisation SciPy, simplification | Appareil utilisateur, Python/Pyodide en Worker, mêmes fonctions Python partagées. |
| Analyse scientifique de la sélection | Appareil utilisateur, ajout de `analyze` au dispatcher partagé. |
| Synthèse du graphe, analyses de rendu, WAV | Moteur local existant conservé. |
| Préparation et transposition du clavier | TypeScript local ; aucun appel serveur par note. |
| Circuit R/C/LED | ngspice WebAssembly en Worker, pas le backend. |
| Sessions, import/référence audio, découpe/rééchantillonnage pour le transfert, validation de patch, exports protégés, certaines descriptions/Bode | Backend existant conservé. Le site n’est donc pas entièrement hors ligne. |

Les anciennes API de calcul et le prototype RC natif sont conservés pour compatibilité et tests, mais ne sont pas utilisés par les actions de calcul de cette interface. Ce changement ne désactive pas administrativement un éventuel service de production existant.

## Ressources et isolation

La scène 3D est démontée lorsqu’on quitte l’atelier. Son rendu est demandé lors d’un changement de vue/caméra/placement ; il n’existe plus de boucle de dessin permanente à l’arrêt. ResizeObserver, géométries, matériaux, textures, contrôles et contexte sont nettoyés.

Le solveur de circuit dispose d’un Worker dédié par simulation, terminé au résultat, à l’erreur, à l’annulation ou après 15 s. Aucune commande SPICE, chemin ou inclusion fournis par un import ne sont exécutés. Limites : 48 composants, 200 fils, 24 réseaux mesurés, 1 µs à 100 ms, 4 Mo de trace, 4 000 points au plus avant affichage de 513 points. Une erreur ne produit pas de courbe fictive. Les limites définissent le périmètre de ce nouveau simulateur, pas une réduction des paramètres du moteur DSP.

La bibliothèque du solveur est chargée au premier lancement d’une simulation. Le build produit un Worker de circuit d’environ 7,19 Mo avant compression. Le port tiers annonce une mémoire initiale de 256 Mo : les appareils modestes doivent encore être validés. Le fichier `/proc/meminfo` créé dans MEMFS décrit un budget virtuel pour ngspice ; il ne mesure pas la RAM réelle de l’utilisateur.

L’atelier ne charge pas le gros bundle d’analyse audio avant la première visite de `/analyse`, et ne démarre pas Pyodide pour un circuit. Aucun appel LLM, Gemini ou Drive n’est nécessaire à ces parcours.

## Validation exécutée

Machine locale macOS arm64 ; Python 3.12.14, NumPy 2.5.3, SciPy 1.18.1, Node 22.15.0. Recette UI dans le navigateur Chromium intégré, base synthétique temporaire sous `/tmp/resonant-workspaces-20261103`, sans compte ni données de production.

Commandes :

```bash
./test.sh
node frontend/tests/run.mjs
npm run build --prefix frontend
PYTHONPATH=backend .venv/bin/python scripts/prepare_local_runtime.py
git diff --cached --check -- ':!frontend/dist' ':!frontend/public/third-party'
```

- Suite complète : **142 tests backend réussis**, puis **32 tests frontend réussis** et build réussi. Après ajout du test de cycle de vie du Worker de circuit, la suite frontend relancée compte **33 tests réussis**. TypeScript/Vite relancés après les dernières corrections.
- Les calculs ngspice WASM sont réellement exécutés dans les tests, pas remplacés par des courbes préparées. Le test du Worker client utilise en revanche un faux Worker pour vérifier terminaison et rejet des promesses ; il ne mesure pas un arrêt CPU sur appareil physique.
- Diviseur 5 V, 1 kΩ/1 kΩ : erreur absolue testée < `1e-8 V` par rapport à 2,5 V. Passage à 1 kΩ/2 kΩ : erreur < `1e-6 V` par rapport à 10/3 V. Tolérances de lecture décimale des vecteurs, sans modification des tolérances ngspice.
- RC 1 kΩ, 1 µF, échelon 5 V : interpolation de la trace à 1 ms comparée à `5 × (1 − exp(−1))`, tolérance absolue `0,005 V` pour la discrétisation/export de la trace.
- Groupes de contacts, coupure centrale, modification de connexion, imports invalides et conservation des paramètres/fils testés.
- Préparation/transposition locale comparée aux fixtures Python pour notes 0, 69, 81 et 127, attaque et phase comprises : erreur maximale exigée < `2e-9` sur ces cas.
- Événements clic/MIDI injectés à note 69 et vélocité 100 : même signal déterministe, fixture 440 Hz vérifiée avec erreur < `1e-10`. Sustain, canaux, sources, bend, Note Off, vélocité nulle, extinction et messages invalides couverts. Ces tests n’incluent pas la sortie acoustique d’un périphérique physique ni tout le chemin Web Audio.
- Test de non-régression : patch de 38 modes conservé malgré une analyse de 13 partiels. Cela ne valide ni la compilation ni les capacités CPU du firmware Teensy.
- Les tests DSP/WAV existants sont restés verts. Aucune tolérance DSP modifiée.

Recette navigateur réellement effectuée : création sans WAV ; diviseur 2,5000 V ; édition dans la vue 2D à 2 kΩ puis mesure 3,3333 V ; enregistrement/rechargement conservant quatre composants, quatre fils et la valeur modifiée ; aller-retour analyse/atelier ; menu fermé par Échap avec focus rendu au bouton ; bibliothèque mobile ; simulation dans le vrai Worker navigateur.

À 1280×800, outils fermés, la scène mesure 1280×658 px, soit environ **88 %** de la surface sous l’en-tête de 54 px. Viewports 1920×1080, 1024×768 et 390×844 également vérifiés, sans débordement global. Ce sont des tailles de viewport sur ordinateur, pas des essais sur tablette ou téléphone physiques.

Analyse locale supplémentaire sur 0,25 s de la note modale synthétique : 261,63 Hz, quatre partiels. Un lancement à froid a rapporté 5 289,9 ms au total, 2 972,5 ms d’initialisation, 2 292,5 ms de calcul Worker, 18,4 ms de préparation/transfert. Mesures de contextes séparées, un seul essai : **test de fonctionnement, pas benchmark comparatif ni gain annoncé**. La base temporaire n’avait toujours aucune table de jobs après cet essai.

Captures synthétiques : `docs/screenshots/atelier-desktop.png`, `atelier-mobile.png`, `diviseur-2d.png`. Aucun secret ni projet privé dans ces images.

Avertissements : dépréciations FastAPI `on_event` et TestClient/httpx ; branche Node `module` externalisée par Vite dans le port ngspice. Le Worker navigateur a néanmoins exécuté le circuit avec succès. Ces avertissements n’ont pas été présentés comme des erreurs corrigées.

## Dépendances et licences

Ajout exact : `@o.z/ngspice-wasm@0.0.0`, résolution/intégrité dans `package-lock.json`. C’est un port tiers, non affilié à ngspice. Aucun code ni ressource propriétaire Tinkered, ni code CircuitJS GPL, n’a été copié. Symboles et géométries sont propres au projet ; Three.js et React Flow étaient déjà présents.

Les notices reçues du paquet, y compris leurs espaces de fin de ligne, sont conservées sous `frontend/public/third-party/` et copiées dans le build. **Le contrôle de redistribution n’est pas terminé** : le LICENSE du wrapper contient littéralement un texte de remplacement, et la recette amont mentionne KLU/FFTW sans attester les options exactes du binaire publié. Le manifeste npm « BSD-3-Clause » seul ne suffit pas à conclure sur toutes les bibliothèques liées. Avant publication, produire un binaire reproductible depuis des sources figées, inventorier les options réellement liées, fournir sources/notices/reconstruction requises et remplacer ce paquet expérimental si sa provenance reste insuffisante. Ne pas publier automatiquement cet artefact comme dépendance auditée.

Sources : [port tiers et recette](https://github.com/z-wasm/ngspice-wasm), [licences ngspice](https://ngspice.sourceforge.io/devel.html). Les captures des références ne sont pas utilisées comme ressources de l’application.

## Limites et point de reprise

**P1 à compléter :** insertion physique des pattes dans les trous avec changement de réseau explicite et annulable ; rotation des symboles 2D ; jonctions/labels avancés ; suppression de fils par sélection 3D ; sondes libres et différentielles ; mesures RMS/crête-à-crête, déclenchement et export des acquisitions ; sauvegarde multi-projets liée au compte ; restauration après connexion d’une session visiteur et gestion des conflits multi-onglets. Le stockage actuel est local au navigateur, non chiffré et ne synchronise pas les appareils ; l’export authentifié ne constitue pas une protection DRM contre l’inspection des données déjà calculées localement.

**P2 non réalisé :** compilation Arduino, import/exécution de binaire AVR, périphériques, bouton numérique, ADC du potentiomètre, PWM synchronisé, moniteur série, Blink véritable. L’Uno est marqué visuel ; aucun Blink animé ni pseudo-interpréteur de texte n’a été livré. Prochaine tranche : choisir ATmega328P/Uno et un moteur AVR compatible, vérifier licence/périphériques et exécuter un binaire de test avant d’exposer une commande de compilation. L’entrée USB MIDI hôte du futur montage exige un matériel compatible ; elle n’est pas fournie par cette carte visuelle.

**P3 non réalisé :** composants personnalisés, transistors/logique/capteurs, import SPICE, catalogue étendu et traduction de tout le DSP en matériel/firmware. La passerelle préserve le graphe et indique ces limites ; elle ne fabrique pas un montage matériel équivalent. Le clavier utilise encore des notes pré-rendues et mises en cache ; le bend rééchantillonne le même tampon et modifie également sa chronologie. Une chaîne AudioWorklet et une recette de timbre sur plusieurs notes restent distinctes de la correction de routage.

Non testés : clavier MIDI physique, Android/iPhone/iPad physiques, Safari/Firefox, panne réelle de GPU, endurance mémoire, compilation firmware, hardware réel et intégrations de production. Aucun gain de vitesse universel ni équivalence avec Tinkered/Falstad n’est revendiqué.

## Livraison, déploiement et retour arrière

La livraison reste locale. Un push sur `main` déclencherait le déploiement automatique existant : il n’est pas effectué puisque la mission actuelle exclut un déploiement sans autorisation. Aucun secret, fichier systemd, Nginx ou base privée n’a été modifié pour cette tranche. Le contrôle des fichiers modifiés (motifs de clés privées, clés Resonant et Gemini) n’a trouvé aucune correspondance ; `.env`, bases privées, runtime local et `node_modules` sont ignorés. Ce contrôle ciblé ne constitue pas un audit de sécurité exhaustif.

Avant une mise en ligne autorisée : lever le point de provenance/licences du moteur WASM ; sauvegarder SQLite avec l’outil existant ; construire dans un répertoire séparé (`npm ci`, build, préparation du runtime local), puis exécuter les tests. Le backend doit servir les routes `/atelier` et `/analyse` ainsi que les assets du même build. Remplacer les artefacts de façon atomique et conserver les anciennes ressources suffisamment longtemps pour les onglets ouverts : un remplacement en place pendant la recette a montré le risque de chunk différé manquant. Le shell possède désormais un message de rechargement au lieu d’un écran blanc.

Aucune migration SQLite n’est nécessaire pour ces changements. Conserver les sauvegardes JSON de projets et les anciens artefacts. Pour revenir en arrière : remettre un ensemble backend/frontend cohérent connu, sans restaurer SQLite sur les nouvelles données et sans réinitialiser les comptes. Les brouillons atelier restent dans le stockage navigateur mais une ancienne interface ne saura pas les éditer : exporter leur JSON avant retour arrière. Refaire ensuite routes, session, import léger, calcul local et WAV, sans test de charge en production.
