# Résonant — laboratoire de synthèse physique

Application locale fonctionnelle pour passer d’une **note WAV isolée** à un graphe de synthèse explicite, modifiable et exportable. Python exécute réellement les blocs affichés ; React affiche l’analyse et permet l’édition du graphe. Aucune reconstruction neuronale, aucun échantillon original stocké dans les blocs, aucun score de confiance inventé.

Cette version 0.1 couvre le parcours import → analyse → choix d’un modèle → synthèse → comparaison → modification → optimisation → export. C’est une base scientifique expérimentale, **pas un inverseur universel d’instruments** : le modèle physique réel n’est généralement pas identifiable de façon unique à partir d’un enregistrement.

## Démarrage

Les dépendances sont déjà installées dans ce dossier. Dans un terminal :

```bash
cd /Users/teste/TRAVAIL/PREPA/TIPE/resonant-lab
./run.sh
```

Ouvrir **http://127.0.0.1:8000**. Arrêt : `Ctrl+C`. Si le port est déjà utilisé par le serveur de cette application, ouvrir simplement son adresse existante. Ne pas arrêter un autre service sans l’identifier.

Pour réinstaller sur une autre machine : Python **3.12+**, Node.js **20+**, npm, puis :

```bash
./setup.sh
./run.sh
```

Si `python3` désigne un ancien Python : `PYTHON_BIN=/chemin/vers/python3.12 ./setup.sh`. Le moteur n’utilise pas les paquets du Python système : ils sont isolés dans `.venv`. Les versions Python et JavaScript sont figées dans `requirements.lock.txt` et `frontend/package-lock.json`. La première installation exige Internet ; **le fonctionnement n’a ensuite besoin d’aucun service distant**, ni de police chargée depuis Internet.

## Parcours conseillé

1. Cliquer **Importer WAV** et choisir `../piano2.wav`, ou essayer la note modale intégrée.
2. Définir le début et la durée de la note à analyser (maximum 12 secondes).
3. **Analyser** : fondamentale estimée, partiels, enveloppe RMS, constante de décroissance de chaque mode, inharmonicité lorsque les critères sont satisfaits.
4. **Générer le modèle** : le moteur compare plusieurs architectures et sélectionne le meilleur score erreur + complexité. Les autres candidats restent accessibles dans **Analyse & modèles**. Les réglages permettent de désactiver la recherche détaillée, l’affinage des modes ou le bruit d’impact pour comparer leur apport. La recherche détaillée est plus lente et peut créer plusieurs modes voisins pour un seul pic spectral.
5. Le signal se calcule automatiquement. Écouter **A · Original** puis **B · Synthèse** ; les deux écoutent la même sélection mono et gardent la position lors du basculement. Le WAV d’origine stéréo reste intact côté serveur. Le mode **Aveugle** tire au sort l’identité de A et B ; ce n’est pas un protocole ABX statistique.
6. Cliquer un bloc et changer ses paramètres. Le signal, le spectre, le spectrogramme et les erreurs sont recalculés après une courte temporisation. Pour un filtre, le Bode et les coefficients affichés proviennent du même calcul que le traitement audio.
7. Cocher les paramètres à optimiser dans l’inspecteur, ou laisser le choix par défaut, puis **Optimiser**. La progression rapporte les évaluations réelles. L’arrêt conserve le meilleur modèle trouvé.
8. Exporter le modèle en **JSON / `.monpatch`**, le son en **WAV float**, le schéma en **SVG/PNG**, les paramètres en **CSV**, ou le **rapport HTML autonome**. Un lien de téléchargement reste visible après chaque export ; les huit derniers exports sont conservés dans un cache local en mémoire de 64 Mo au maximum (32 Mo par fichier). Ouvrir le rapport et utiliser son bouton d’impression pour enregistrer un PDF.

Le modèle automatique peut ne contenir aucun filtre : c’est normal. Une banque de modes suffit parfois et ajouter un filtre n’est alors pas justifié. Pour étudier un filtre, utiliser le patch manuel de départ, sélectionner un candidat filtré, ou ouvrir `examples/banc-lti.monpatch`.

## Édition manuelle et hybride

- Ajouter un composant par clic dans la bibliothèque ou par glisser-déposer.
- Relier sa sortie (port droit) à une entrée (port gauche).
- Déplacer les blocs, zoomer, déplacer le fond, utiliser la miniature ou **Fit View**.
- Sélectionner une connexion et appuyer sur Suppr/Retour arrière pour la retirer. Même action sur un bloc, ou bouton de suppression dans l’inspecteur.
- Dupliquer un bloc avec le bouton de l’inspecteur ; les connexions ne sont pas dupliquées.
- Il faut exactement une sortie. Les filtres/enveloppes/gains ont une entrée ; le produit en a deux ; le sommateur en accepte plusieurs. Les boucles, même contenant un délai, sont refusées.
- Le Bode global se calcule d’une source choisie vers la sortie, en annulant les autres sources. Une enveloppe variable dans le temps ou un bloc non linéaire exclut ce calcul.
- Dans **Optimisation**, mémoriser plusieurs versions pendant la session et revenir à une version pour l’écouter. Exporter les JSON pour les conserver au-delà de la session.

## Ce qui est implémenté

| Domaine | Fonctionnalités |
|---|---|
| Import | WAV PCM 16/24/32, float/double selon libsndfile ; mono/stéréo ; métadonnées, crête, RMS |
| Vues | Forme temporelle min/max, spectre Welch, STFT, enveloppe RMS, autocorrélation ; zoom, déplacement et lecture au curseur Plotly |
| Synthèse | Sinus, bruit blanc reproductible, impulsion, entrée LTI, mode amorti, gain, somme, produit/VCA, délai entier, quatre filtres du second ordre, résonateur, enveloppe exponentielle, ADSR, saturation tanh, sortie |
| Mathématiques | Équations, unités, H(s) des prototypes de filtres, H(z) réellement exécuté, Bode, réponse impulsionnelle, pôles/zéros, ordre, stabilité, gain DC |
| Identification | Pics spectraux, décroissance STFT, ajustement de modes proches et battements, isolement fréquentiel, calibration de l’attaque, impact bruité filtré, comparaison de familles explicites |
| Optimisation | Powell, L-BFGS-B, évolution différentielle ; variables sélectionnables, bornes, graine déterministe, annulation, historique du meilleur coût |
| Comparaison | Erreurs relatives temps, FFT, STFT, enveloppe et attaque à deux résolutions ; poids configurables ; A/B, boucle, volume, A/B à identité masquée |
| Export | JSON, WAV float sans normalisation, CSV, SVG, PNG, rapport HTML avec figures et impression PDF |

Les curseurs temporels des vues signal, enveloppe et spectrogramme partagent une position. Les onglets affichent une représentation à la fois ; le spectrogramme propose original, synthèse et résidu dans un sélecteur avec la même échelle dBFS. Le Bode a son propre curseur fréquentiel. Le spectre affiché utilise Welch ; le terme d’erreur spectrale utilise la FFT complète de la sélection (voir les équations).

## Architecture

```text
frontend/src/
  App.tsx                 état de session, orchestration des requêtes et parcours
  api.ts                  accès API, téléchargements
  types.ts                contrats TypeScript
  defaults.ts             patch manuel de départ
  report.ts               rapport autonome et figures
  components/
    Graph.tsx             éditeur React Flow
    Inspector.tsx         paramètres, équations, Bode et impulsion
    SignalPanel.tsx       comparaison des signaux et curseur temporel
    AnalysisPanel.tsx     mesures, candidats et hypothèses
    Player.tsx            lecture audio A/B
    Plot.tsx              adaptation Plotly
backend/lab/
  schema.py               contrat versionné et validation structurelle Pydantic
  blocks.py               registre des blocs, unités, paramètres et DSP
  graph.py                validation DAG et simulation topologique
  transfer.py             réponses numériques et composition LTI du graphe
  audio.py                WAV, rééchantillonnage et vues bornées
  media.py                lecture HTTP par plages d’octets pour le positionnement A/B
  analysis.py             fondamentale, partiels, décroissance, inharmonicité
  identify.py             construction et classement des candidats
  modal_fit.py            modes proches par projection complexe et ajustement borné
  attack_fit.py           calibration du début et de la montée, réponse libre conservée
  impact.py               branche de bruit filtré et enveloppé, ajustée sur le résidu
  metrics.py              erreurs normalisées et pondération
  optimization.py         optimisation bornée et arrêt contrôlé
  export.py               SVG et échappement du contenu
  app.py                  API FastAPI locale, caches et tâches d’optimisation
backend/tests/            tests numériques et API
scripts/make_fixtures.py   signaux synthétiques connus
```

Le registre `Definition` décrit le contrat abstrait d’un bloc (nombre d’entrées, paramètres, équation, domaine LTI), et `process` réalise son opérateur numérique. Pour ajouter un bloc : déclarer sa définition, son traitement, ses coefficients si LTI, puis des tests. La bibliothèque et l’inspecteur sont alimentés par ce registre ; il n’y a pas une seconde table de paramètres indépendante côté interface.

## Pourquoi cette stack ?

| Option | Atouts | Limites pour cette première version |
|---|---|---|
| TypeScript + React + Web Audio + WASM | Portabilité navigateur, audio interactif, calcul parallélisable | Portage ou réécriture des algorithmes d’identification ; intégration WASM supplémentaire |
| **Python + frontend React** | **SciPy/NumPy pour les modèles, filtres et optimiseurs ; séparation UI/calcul claire ; tests numériques simples** | Serveur local requis ; pas de DSP audio temps réel garanti |
| Rust/C++ + frontend | Bon contrôle de la mémoire et des performances temps réel | Complexité initiale et chaîne de compilation plus lourdes pour l’optimisation scientifique |

Le moteur utilise des tableaux NumPy et les filtres compilés de SciPy. L’optimisation tourne dans un thread dédié ; l’UI suit sa progression sans bloquer. Le rendu est hors ligne, recalculé après modification ; ce n’est pas un instrument à faible latence piloté par MIDI. Un moteur Rust/WASM pourra remplacer le simulateur à contrat de patch constant si cela devient nécessaire.

## Limites et interprétation

- Modèles candidats **définis à l’avance** : cette version sélectionne leur famille et leur taille d’après les données. Elle n’infère pas une topologie physique arbitraire.
- Cible : notes isolées, principalement tonales. Polyphonie, mélodies, pédale de sustain, transitoires complexes, réverbération de salle et battements proches restent imparfaitement modélisés.
- Un mode amorti est une interprétation mathématique d’un pic, pas la preuve qu’une corde ou une masse précise a été identifiée. Une FFT sert à l’analyse ; le signal final est recréé par les équations des blocs.
- L’inharmonicité est un ajustement descriptif avec critères explicites, sans probabilité de confiance. Le R² caractérise uniquement la régression de décroissance.
- Le gate ADSR ne peut pas être retrouvé univoquement à partir du WAV ; l’identification automatique utilise une attaque exponentielle et une décroissance par mode.
- Import borné à 128 Mo, 5 minutes et 30 millions d’échantillons ; les originaux restent intacts. Analyse/optimisation d’une sélection de 0,05 à 12 s. Rendu manuel jusqu’à 60 s, sous la limite de 100 millions d’échantillons × blocs actifs. Les vues longues sont réduites, sans modifier les données audio.
- Synthèse mono à 44,1/48/96 kHz. Les autres fréquences d’import sont rééchantillonnées avec filtrage polyphasé pour générer le modèle à 44,1 kHz.
- Les blocs disjoints de la sortie n’affectent pas l’audio. Pas de rétroaction dans les graphes v1.
- La saturation n’est pas suréchantillonnée. Les exports WAV float préservent les dépassements de ±1 ; l’interface les signale pour l’écoute.
- Audio et résultats vivent en mémoire (quatre originaux/rendus récents, budget mémoire des originaux). Un redémarrage du serveur efface cette session. Le JSON contient le modèle, pas le WAV source.
- Les curseurs sont interactifs mais il n’y a pas encore de montage multipiste, MIDI, export de circuit électronique, modèle de corde couplée, table d’harmonie ou simulation FEM.

## Validation

```bash
./test.sh
# Générer les WAV de référence :
PYTHONPATH=backend .venv/bin/python scripts/make_fixtures.py
```

Les 38 tests couvrent lecture WAV, analyse spectrale/fréquentielle, enveloppe, estimation d’inharmonicité, réponse impulsionnelle versus Bode, simulation, branches parallèles, rejet des graphes invalides, sérialisation, reconstruction et optimisation effective. Les tests API exécutent aussi import/démonstration → analyse → modèle → synthèse → exports.

Les dernières mesures sur les trois premières secondes de `piano.wav` et `piano2.wav` sont conservées dans `docs/piano-impact-validation.json`. Les modèles et WAV reconstruits sont `examples/piano-impact.*` et `examples/piano2-impact.*`. Le script `PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/validate_piano.py` reproduit génération détaillée et 181 évaluations Powell. Coûts finaux : **0,285568** et **0,125495**, avec les poids et bornes consignés dans le JSON. Le budget est épuisé sans convergence revendiquée. `docs/piano-validation.json` conserve la première mesure historique avec un modèle plus simple. **Une baisse d’erreur ne garantit pas une équivalence perceptuelle** : écouter le résultat et examiner les résidus. Les valeurs sont des erreurs relatives, pas des pourcentages de ressemblance.

## Développement

```bash
# Terminal 1, depuis la racine du projet
PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python -m uvicorn lab.app:app --reload --reload-dir backend --host 127.0.0.1 --port 8000
# Terminal 2
cd frontend
npm run dev
```

Interface de développement : http://127.0.0.1:5173, API documentée automatiquement : http://127.0.0.1:8000/docs. Pour compiler : `cd frontend && npm run build`. `run.sh` sert ensuite ce build avec un seul serveur.

Consulter [les modèles mathématiques](docs/MATHEMATIQUES.md) pour les équations, hypothèses, critères d’erreur et règles de sélection.

## Simplifier sans perdre le modèle précis

Après optimisation, **4. Simplifier** compare des modèles avec moins de générateurs et teste l’intérêt d’une saturation et d’un filtre de sortie. Dans les réglages, **Hausse d’erreur max. (%)** contrôle le compromis (20 par défaut, 0 pour refuser toute hausse du coût). Le choix minimise les blocs parmi les essais respectant ce plafond. Relancer une simplification dans cette comparaison conserve la même référence précise ; importer/générer un autre modèle démarre une nouvelle comparaison.

Le panneau indique les nombres de blocs/générateurs, les coûts et l’utilité de chaque source. **Comparer tous les candidats** permet d’essayer d’autres compromis ; les candidats hors budget sont identifiés. **Revenir à la version précise** restaure immédiatement le patch initial. Les mesures affichées décrivent la dernière comparaison, même après une édition manuelle. Elles sont réinitialisées si le WAV, la sélection ou les poids changent.

Sur les deux pianos fournis : 47 → 14 et 48 → 10 blocs, rendus environ 3,5× et 5,2× plus rapides, avec une hausse du coût de 16,0 % et 18,6 %. Les traitements de sortie testés ne justifiaient pas leur ajout dans les résultats retenus. Aucun maintien d’une fidélité perceptive identique n’est revendiqué. Voir [la validation détaillée](docs/VALIDATION.md) et `examples/*-compact.*`. Les versions précises `examples/*-impact.*` et la sauvegarde `backups/precision-v1-20261001.zip` sont conservées.

### Explorer des sources enrichies et filtrées

L’option **Explorer sources + saturations + filtres (plus lent)** étend désormais la simplification à des architectures complètes inspirées du patch VCV fourni : saturation asymétrique suréchantillonnée ×4, égaliseur paramétrique, passe-bas du premier ou du second ordre, passe-haut et branche parallèle d’harmoniques. Les sources et traitements sont ajustés ensemble. Les nouveaux blocs sont aussi disponibles dans la bibliothèque manuelle.

Le panneau **Recherche globale** détaille les essais et leurs coûts ; **Comparer tous les candidats** permet de les charger pour l’écoute, y compris les essais clairement marqués hors budget. L’ajout de filtres reste soumis au même critère de précision et de nombre total de blocs. La version précise et le modèle compact précédent sont conservés. Les équations, bornes et limites figurent dans `docs/MATHEMATIQUES.md` ; le patch VCV original n’est pas modifié.

### Ouvrir le site sur Mac

Dans le Finder, double-cliquer sur **Ouvrir Résonant.command**. Le lanceur démarre le serveur, attend qu’il soit prêt et ouvre `http://127.0.0.1:8000/` dans le navigateur. Garder la fenêtre Terminal ouverte pendant l’utilisation ; Ctrl+C arrête le serveur. Si Résonant est déjà actif, le lanceur réutilise cette instance. En cas d’échec, le diagnostic est affiché et conservé dans `.local/server.log`.
