# Génération sobre — validation du 14 novembre 2026

## Résultat et périmètre

La génération depuis un WAV recherche désormais systématiquement des alternatives à la banque de sinusoïdes : enveloppes partagées, une/deux sources suivies de saturation et filtres, fondamentale avec bruit amplifié et filtre en peigne. Le calcul de l’application reste dans son worker Python/WebAssembly sur l’appareil utilisateur. Le rendu audio et le WAV restent locaux. Les calculs Python natifs ci-dessous sont des références et benchmarks de développement, pas un retour du calcul serveur dans l’interface.

**Le test piano ne démontre pas encore une réduction importante du montage à fidélité conservée.** Sur les trois premières secondes de la note fournie, seul le gain unité a pu être retiré : 88 → 87 blocs, mêmes erreurs mesurées. Les candidats bruit + peigne à 10 blocs sont rejetés. Ils restent consultables pour comparaison manuelle ; les sélectionner volontairement ne les rend pas équivalents à la référence.

Un bloc est une fonction DSP explicite, pas un composant électronique à acheter. Les modes amortis sont comptés comme sinus + enveloppe et développés dans le rack. Les alimentations, résistances de polarisation, convertisseurs et autres pièces d’une réalisation matérielle ne sont pas inclus dans ce compteur. Aucun gain de prix, de surface ou d’énergie n’a été mesuré.

## Fonctionnement livré

1. Les anciennes familles de génération et leurs exigences d’ajustement sont conservées. Leur meilleure proposition selon erreur + λ × complexité constitue la référence.
2. Le nettoyage retire les gains unité et les sommes à une entrée. Les regroupements d’enveloppes sont également nettoyés.
3. Quatre propositions à une/deux sources explorent saturation asymétrique suréchantillonnée ×4, passe-bas ou passe-haut/égaliseur, puis enveloppe. Recherche additionnelle bornée ; les critères du modèle de référence ne sont pas réduits.
4. Deux familles à bruit sont explorées : impulsion de bruit enveloppée avant le peigne, ou bruit entretenu enveloppé après les filtres. Réinjections 0,8/0,95/0,99, deux coupures et trois gains issus de l’énergie résiduelle sont comparés. C’est une recherche heuristique finie, pas une optimisation exhaustive du circuit.
5. Chaque proposition finale est rendue à la fréquence complète puis comparée à la référence sur chaque terme de l’objectif (temps, spectre, spectrogramme, enveloppe, attaque, total) et chaque bande. Aucun terme ne doit augmenter au-delà de 1e-12 absolu, marge numérique et non tolérance perceptive. Le nombre de blocs départage les propositions admissibles en premier.
6. Les causes de rejet, scores et référence sont disponibles dans « Analyse & modèles ». La référence reste dans `reference_patch` et dans les candidats. Le minimum trouvé est celui de cette liste explorée, pas un minimum global démontré.

Les options de bruit et tolérance de la **simplification** restent distinctes. Un texte dans les réglages précise que la recherche de génération compare toujours les nouvelles familles. Les seuils DSP, la normalisation et le suréchantillonnage existants ne sont pas abaissés.

## Filtre en peigne réellement exécuté

Nouveau bloc `comb`, libellé « Filtre en peigne résonant » :

```
D + α = fs / f, D entier, 0 ≤ α < 1
 y[n] = (1−g)x[n] + g[(1−α)y[n−D] + αy[n−D−1]]
```

État initial nul, 0 ≤ g ≤ 0,9999, fréquence nominale de 20 Hz à la limite permise par Nyquist. Le facteur (1−g) est explicite et donne un gain continu unité. L’interpolation linéaire affecte les résonances aiguës : la fréquence affichée est un espacement nominal, pas une promesse d’harmoniques exactes.

Implémentations Python et JavaScript en double précision. Python calcule des tranches dont les dépendances sont déjà connues, sans convolution dense d’ordre fs/f. Le Bode utilise la formule du transfert ; l’inspecteur ne lance pas une recherche dense des milliers de pôles possibles. Il explique le critère de stabilité, au lieu d’afficher une liste de pôles inventée. Le suivi MIDI transpose aussi la fréquence nominale, avec bornage explicite.

Repère théorique : [Stanford CCRMA — Feedback Comb Filters](https://ccrma.stanford.edu/~jos/pasp/Feedback_Comb_Filters.html). Le code est indépendant.

Le peigne nécessite une mémoire de retard, une sommation et une réinjection : **un ALI seul ne suffit pas**. L’inventaire matériel et l’export Teensy signalent cette limite. Le sketch actuel ne reproduit pas ce nouveau filtre ; aucun montage complet équivalent n’est déclaré validé.

## Mesure piano reproductible

Données détaillées sans échantillons audio : `generation-piano-benchmark.json`.

- Même extrait mono, début 0, durée 3 s, 44 100 Hz. L’enregistrement fourni dure environ 9,83 s : la fin de note n’est pas couverte par ce benchmark.
- Même empreinte d’entrée, 24 partiels d’analyse maximum, affinement des modes, recherche détaillée et impact activés, λ=0,0001, poids inchangés.
- macOS 26.6.2 arm64 ; Python 3.12.14, NumPy 2.5.3, SciPy 1.18.1. Le modèle exact de CPU et la RAM n’ont pas pu être lus dans cet environnement ; pas de résultat multiappareil revendiqué.
- Trois répétitions séquentielles par version, sans cache de résultat. Première exécution puis deux suivantes dans le même processus. Imports/chargement WAV exclus du chronométrage ; cela n’est pas un démarrage navigateur à froid. OPENBLAS_NUM_THREADS=1 et OMP_NUM_THREADS=1.

| Mesure | Référence d593876 | Nouvelle génération |
|---|---:|---:|
| Première exécution | 8,133 s | 48,516 s |
| Exécutions suivantes | 8,108 / 8,204 s | 47,882 / 48,011 s |
| Médiane des trois | 8,133 s | 48,011 s |
| Blocs explicites retenus | 88 | 87 |
| Erreur totale | 0,2978963529752091 | 0,2978963529752091 |
| Modes amortis retenus | 40 | 40 |

Le même modèle « résonances isolées · attaque ajustée + impact » reste retenu. La recherche coûte environ 5,9 fois plus de temps sur cette machine. **Ce lot améliore la recherche de structures, pas la vitesse de génération.** Les métriques identiques ne constituent ni une preuve d’identité perceptive ni une reproduction à 100 % du piano.

| Alternative piano | Blocs | Erreur totale | Décision automatique |
|---|---:|---:|---|
| Fondamentale + bruit entretenu + peigne | 10 | 0,715728 | Rejetée : tous les termes et bandes moins fidèles |
| Fondamentale + bruit pincé + peigne | 10 | 0,716430 | Rejetée : tous les termes et bandes moins fidèles |

Le bruit filtré ne remplace donc pas, dans ces candidats testés, les modes mesurés de cette note. Rien n’est forcé pour afficher artificiellement un petit nombre de modules.

## Validation exécutée

Commandes depuis la racine du dépôt :

```sh
PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest backend/tests -q
PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest backend/tests/test_generation_compact.py -q
PYTHONPATH=backend .venv/bin/python scripts/client_fixtures.py
node frontend/tests/run.mjs
npm --prefix frontend run build
.venv/bin/python scripts/prepare_local_runtime.py
PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/generation_reference.py
node scripts/validate_generation_wasm.mjs
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/benchmark_generation.py --output .local/generation-after-final.json
git diff --check
```

- **157 tests backend réussis** en 56,43 s. Trois avertissements préexistants de dépréciation FastAPI/Starlette. Après le dernier nettoyage de la somme à une entrée, les **7 tests ciblés** ont été rejoués avec succès ; le test de génération vérifie désormais cette absence de somme inutile.
- **62 tests frontend réussis**, incluant le filtre en peigne face à Python et les fixtures de transposition 0/69/81/127 sur une chaîne contenant ce filtre. Les tolérances DSP existantes restent à 2e-9 absolu.
- Build TypeScript/Vite réussi ; pas de script lint distinct défini. Avertissement existant du paquet ngspice concernant le module Node `module` externalisé, sans changement de cette dépendance.
- 27 comparaisons de récurrence peigne / `scipy.signal.lfilter`, aux fréquences d’échantillonnage 44 100/48 000/96 000 Hz : seuil fixé 2e-12, maximum mesuré 4,003e-16. Cas de gain élevé, fréquence basse, graine fixe, fin de signal, entrée non finie et boucle longue couverts par les tests.
- Python/WebAssembly réellement exécuté sous Node, incluant une génération synthétique et les deux propositions peigne. Seuils déclarés avant comparaison : onde max/RMS 1e-7, objectif 1e-8. Résultat final : max 4,270e-12, RMS 1,540e-12, objectif 2,632e-14 ; peigne seul max 2,711e-20. Même famille sélectionnée. Voir `generation-wasm-validation.json`. Ce n’est pas une identité bit à bit.
- Pyodide : Python 3.14.2, NumPy 2.4.6, SciPy 1.18.0 ; un passage final, initialisation 5,528 s et calcul 10,779 s. Ces chiffres ne sont pas le benchmark piano ni un résultat de téléphone physique.
- Navigateur intégré, serveur isolé `127.0.0.1:8021`, base temporaire, session visiteur : démonstration modale, extrait 0,15 s, 4 partiels, sans affinement ni impact. Génération locale terminée, modèle chargé, candidats avec rejets affichés. Sélection manuelle du candidat bruit pincé : dix blocs visibles, peigne avec Bode/stabilité, inspecteur ouvert puis fermé. Aucun message console d’erreur/avertissement dans le contrôle effectué. Cette recette précédait uniquement le dernier retrait de somme redondante, ensuite testé en Python et Pyodide.

Non exécutés : écoute perceptive contrôlée, note piano entière dans le navigateur, clavier MIDI physique, Android/iPhone/tablette, montage réel et mesure électrique, compilation du peigne sur microcontrôleur, production. Le bruit JavaScript reste une réalisation déterministe différente de NumPy ; on ne compare pas directement ces deux bruits échantillon par échantillon.

## Principaux fichiers

- `backend/lab/generation_search.py`, `identify.py` : exploration et sélection avec garde-fous de qualité.
- `backend/lab/blocks.py`, `transfer.py` : DSP et réponse du peigne.
- `frontend/src/audioDsp.ts` : même récurrence dans le rendu local.
- `backend/lab/instrument.py`, `frontend/src/instrumentLocal.ts` : transposition cohérente.
- `frontend/src/audioInventory.ts`, `components/Inspector.tsx`, `components/LabGuide.tsx`, `types.ts`, `App.tsx` : explications, limites et réglages lisibles.
- `frontend/src/firmware/teensySketch.ts` : avertissement d’incompatibilité matérielle du peigne.
- `backend/lab/compute.py`, `scripts/prepare_local_runtime.py` : version `shared-python-v3-comb`, ajout explicite du seul module numérique à l’archive autorisée.
- `backend/tests/test_generation_compact.py`, fixtures et scripts de validation/benchmark : tests reproductibles sans audio privé versionné.
- `frontend/dist` : build actualisé selon la convention de déploiement du dépôt.

Aucune dépendance ni licence nouvelle, aucune migration SQLite, aucun changement d’authentification ou secret.

## Livraison et reprise

Commit local uniquement ; pas de push, car `main` déclenche le déploiement automatique et la consigne récente exige une autorisation de production. Aucun service distant ni donnée de production modifié.

Lors d’un déploiement autorisé, livrer ensemble sources numériques, catalogue et build frontend. Régénérer `.local/compute-runtime/numerical.zip` et son manifeste avec `scripts/prepare_local_runtime.py` (ajouter `--download` seulement si les dépendances Pyodide manquent), vérifier `ready` et `algorithm_version`, puis appliquer la procédure existante de redémarrage. Tester localement une génération courte, le rendu du peigne et son inspecteur après rechargement du navigateur. Ne pas réinitialiser la base.

Retour arrière : rétablir le commit précédent, son build et son archive numérique, sans restaurer une ancienne base par-dessus les données. Les projets contenant `comb` ne sont pas lisibles par l’ancien catalogue : en garder les fichiers et utiliser la référence sans peigne avant retour arrière. Une session ouverte peut conserver son ancien worker : rechargement nécessaire après sauvegarde du travail.

Point de reprise : décomposer le résidu du piano et mesurer ce qui relève des modes stables, de l’inharmonicité et du bruit diffus ; chercher une architecture hybride avec moins de modes et une décroissance fréquentielle mieux adaptée. Établir son coût réel en pièces et son firmware avant de la proposer comme montage reproductible. Réduire ensuite le coût de recherche par réutilisation sûre des calculs. L’objectif d’un piano quasi identique avec très peu de composants reste ouvert.
