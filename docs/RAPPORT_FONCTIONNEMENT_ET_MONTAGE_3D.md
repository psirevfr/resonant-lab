# Rapport — fonctionnement de Résonant et atelier de montage 3D

**État du dépôt examiné :** commit `38386f3` (`feat: ajouter une scène 3D interactive au montage physique`), branche `main` synchronisée avec `origin/main` au moment du relevé.
**Parcours manuel décrit :** 1er novembre 2026, environnement local de validation isolé. Ce rapport décrit le dépôt et cet essai ; il ne constitue pas une certification de la production ni du matériel physique.

## 1. À quoi sert le site

Résonant est un laboratoire expérimental qui transforme une note audio mono en un modèle de synthèse explicite. Il sert à mesurer un son, proposer des architectures de synthèse, écouter et modifier leurs paramètres, comparer les résultats, puis exporter le modèle et le son.

Le modèle est une approximation calculée à partir du signal. Il ne révèle pas nécessairement l’instrument ou le circuit qui a produit l’enregistrement : plusieurs modèles différents peuvent expliquer des mesures proches.

## 2. Parcours général

1. **Importer un son** — l’application accepte un fichier WAV et permet de sélectionner la portion à étudier. L’import conservé comme référence n’est pas remplacé par le modèle.
2. **Analyser** — l’analyse mesure notamment une fondamentale lorsqu’elle est identifiable, les partiels (fréquence, amplitude, phase), leur décroissance, l’attaque et une éventuelle inharmonicité. Elle fournit aussi des avertissements sur ses hypothèses.
3. **Générer un modèle** — des familles candidates explicites sont construites et comparées par leur erreur et leur complexité : modes amortis, bruit filtré et, selon les options, modes rapprochés ou impact bruité. Le résultat est un graphe de blocs et de connexions, pas une copie cachée du WAV.
4. **Écouter et comparer** — le rendu du graphe est effectué dans un Web Worker du navigateur. L’interface présente l’original et la synthèse, ainsi que des vues temporelles et spectrales. Les calculs scientifiques lourds peuvent utiliser le worker Python serveur ou, si le runtime est disponible et choisi, Pyodide/SciPy dans le navigateur.
5. **Modifier, optimiser et simplifier** — les blocs et paramètres sont éditables. Les optimisations utilisent les algorithmes disponibles (Powell, L-BFGS-B ou évolution différentielle). La simplification compare des compromis entre nombre de blocs et erreur, sans garantir une équivalence perceptuelle.
6. **Jouer et exporter** — le clavier du site peut piloter le modèle ; l’export WAV et les exports de modèle/rapport sont disponibles suivant les fonctions de l’interface et les règles de compte.

## 3. Architecture en bref

| Partie | Rôle |
|---|---|
| React + Vite | Interface, éditeur de graphe, analyse, comparaison et atelier matériel. |
| FastAPI + Python, NumPy/SciPy | Import/validation audio, mesures, construction des candidats, optimisation et simplification. |
| SQLite et worker séparé | File persistante pour les opérations serveur longues, avec états, propriété et récupération des résultats. |
| Web Worker audio TypeScript | Exécution du graphe audio local et préparation du WAV, sans bloquer l’interface. |
| Web Worker Pyodide, si runtime préparé | Exécution locale des traitements Python portés, sans transformer le rendu audio local en génération scientifique. |
| Three.js / WebGL | Visualisation orbitale du matériel proposé dans l’atelier de montage physique. |

La génération scientifique, le rendu audio et la représentation du montage sont trois traitements distincts. Un résultat audio produit localement ne signifie pas à lui seul que l’analyse ou la génération a été locale.

## 4. Nouvel ajout : atelier de montage physique 3D

L’onglet **Montage physique** transforme les caractéristiques du modèle choisi en une proposition d’instrument matériel minimal. L’objectif est de calculer les sinusoïdes dans le firmware, plutôt que d’ajouter un générateur matériel par partiel.

### Matériel représenté

- **Teensy 4.1**, programmée avec Arduino IDE et Teensyduino : reçoit les notes MIDI USB et calcule la banque additive dans le code.
- **Teensy Audio Shield Rev D/D2** avec codec SGTL5000 : conversion audio et sorties casque/ligne sur une seule carte empilée sur la Teensy.
- **Clavier MIDI USB class-compliant**, relié au port USB Host de la Teensy via le câble adapté.
- **Breadboard**, fils et câbles USB/audio représentés pour situer le montage.

Le nombre de cartes actives est maintenu bas : une carte de calcul et un shield audio. Les oscillateurs du modèle sont des opérations logicielles, pas des composants séparés sur la breadboard. La scène permet de faire tourner la caméra, déplacer le point de vue, zoomer, sélectionner des éléments et afficher/masquer les liaisons. Des panneaux associés donnent le schéma, le brochage, la nomenclature, les limites de compatibilité et un sketch Arduino téléchargeable.

### Ce que signifie « montage 3D » ici

La scène WebGL est construite à partir de géométries 3D dessinées dans l’application. Elle sert à comprendre l’agencement et les grandes liaisons. Ce n’est pas un assemblage de modèles CAO certifiés : les dimensions, collisions et tolérances mécaniques ne sont pas validées. Il faut suivre les fiches constructeur pour réaliser le montage réel.

### Sketch généré

Le firmware prototype produit une banque de sinusoïdes amorties à partir des partiels disponibles, gère une polyphonie limitée, les notes MIDI et la sortie Teensy Audio. Il expose le code à copier ou télécharger.

Le prototype ne porte pas encore l’ensemble du graphe Résonant : notamment le bruit/impact, les filtres, la saturation, le délai et la transposition avec inharmonicité propre à chaque note. La sortie visée est celle de la Teensy Audio Library à 16 bits / 44,1 kHz ; elle n’est donc pas une copie numérique exacte du rendu Float64 du navigateur. Le sketch n’a pas été compilé avec Arduino IDE/Teensyduino ni essayé sur une Teensy physique. Il faut le considérer comme une base de travail, pas comme un montage déjà validé.

## 5. Essai manuel du parcours piano

Le test a utilisé l’application locale et une base temporaire isolée sous `/tmp`; aucune requête de génération ni modification de données n’a été envoyée à la production.

| Étape | Résultat observé |
|---|---|
| Import | `examples/piano-impact.wav` chargé : 3 s, mono, 48 kHz, format float. |
| Analyse | Réussie. Fondamentale estimée : **439,41 Hz** ; **13 partiels** résolus ; attaque mesurée : **7,27 ms** ; inharmonicité descriptive estimée à **B ≈ 8,63 × 10⁻⁴**. |
| Génération locale | Pyodide/SciPy sélectionné dans le navigateur ; le modèle a été généré sans soumettre de job de calcul serveur. Modèle retenu affiché : **38 modes / résonances isolées · attaque ajustée**, avec **84 nœuds et 83 connexions**. |
| Écoute synthétisée | La lecture du son B a démarré puis s’est terminée à 3 s dans l’interface. Le chemin de lecture a fonctionné ; aucune appréciation objective d’identité sonore n’en découle. |
| Atelier matériel | La scène WebGL a affiché Teensy 4.1, Audio Shield, breadboard, clavier MIDI et câbles. Rotation à la souris et réinitialisation de la caméra ont fonctionné. Nomenclature, schéma et code étaient consultables. |

Une tentative sur le serveur Vite de développement (`5173`) a été rejetée par la protection CSRF, car le navigateur et l’API étaient sur des origines différentes. Le même parcours a ensuite réussi via l’application servie sur `8000` en même origine. Ce constat concerne cet environnement local de test ; il ne démontre pas une panne de la production.

### Limite mise en évidence par le test

Le modèle sélectionné contenait 38 modes, tandis que l’analyse du WAV fournissait 13 partiels. Le sketch est généré depuis les partiels de l’analyse lorsqu’ils sont disponibles ; il ne représente donc pas automatiquement tous les nœuds du modèle choisi. Dans ce parcours, le code utilisait 13 modes, et non les 38 oscillateurs du graphe. Le firmware est une projection additive partielle, pas une traduction fidèle de tout le patch.

À la largeur testée de 1280 px, les panneaux latéraux rendaient la colonne de scène assez étroite pour examiner confortablement les objets. La scène restait interactive, mais l’affichage mérite une adaptation responsive avant de considérer l’ergonomie 3D comme achevée.

## 6. Ce qui est validé et ce qui ne l’est pas

**Validé manuellement dans ce parcours :** import du WAV, analyse, génération Pyodide, lecture de la synthèse, ouverture et interaction avec la scène 3D, accès à la nomenclature et au prototype de code.

**Non validé par cet essai :** tests automatiques complets, fidélité perceptuelle « quasi identique », compilation du firmware, essais sur Teensy/Audio Shield/clavier physique, bruit et effets sur le matériel, réponse réelle de toutes les notes/vélocités, performance sur téléphone/tablette, et déploiement résultant du dernier push.

Pour valider la réalisation matérielle, il reste à compiler le sketch avec les versions Arduino IDE/Teensyduino et bibliothèques documentées, vérifier le câblage d’après PJRC, essayer d’abord à faible volume, enregistrer la sortie de la carte, puis mesurer son écart avec la référence et le moteur logiciel. Le code doit ensuite être étendu pour les traitements manquants avant de revendiquer une reproduction complète du modèle.

## 7. Repères dans le dépôt

- Fonctionnement et limites générales : [`README.md`](../README.md)
- Algorithmes audio et hypothèses : [`MATHEMATIQUES.md`](MATHEMATIQUES.md)
- Atelier électronique : [`ATELIER_ELECTRONIQUE.md`](ATELIER_ELECTRONIQUE.md)
- Scène WebGL : `frontend/src/components/CircuitScene3D.tsx`
- Interface atelier et nomenclature : `frontend/src/components/ElectronicsStudio.tsx`
- Génération du sketch : `frontend/src/firmware/teensySketch.ts`
- Analyse affichée : `frontend/src/components/AnalysisPanel.tsx`
