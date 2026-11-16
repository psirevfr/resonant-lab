# Substitution de groupes harmoniques — 15 novembre 2026

## Fonctionnement livré

Une nouvelle recherche propose de remplacer **un groupe de modes**, en gardant les autres branches, par quatre fonctions visibles : oscillateur sinusoïdal → saturation asymétrique suréchantillonnée ×4 → filtre passe-bas du premier ordre → enveloppe exponentielle / VCA. Aucun échantillon enregistré ni oscillateur caché n'est embarqué.

Cette recherche complète les essais de bruit filtré et de peigne. Elle est intégrée à la génération et, lorsque les traitements non linéaires sont activés, à la simplification. L'exécution utilise les mêmes sources Python dans le worker local Pyodide ; aucun calcul serveur supplémentaire n'est requis. Version : `shared-python-v5-harmonic`.

Les groupes doivent comporter au moins quatre modes, directement additionnés avec une route unique de gain unité vers la sortie. Les débuts et attaques sont communs. Un seul mode est choisi par harmonique ; au plus 32 rangs sont examinés. L'écart de fréquence autorisé pour **proposer** le groupe est au plus 2 Hz et un quart de cycle sur la durée du son. Ce filtre d'éligibilité n'est pas une tolérance de qualité. Un seul groupe est ajusté, puis au plus trois propositions sont comparées.

Les autres sources, transitoires et connexions sont conservés. Une saturation ou un filtre situé après la somme empêche cette substitution : la soustraction des branches ne représenterait plus le même problème. Aucun de ces cas n'est approximé silencieusement.

La génération conserve ses contraintes par terme d'erreur et par bande, sans dégradation au-delà du seuil numérique préexistant de 1e-12. La simplification conserve son budget explicite, ses protections d'attaque et de bandes lorsqu'elles sont activées. Aucun seuil, ordre de filtre ou suréchantillonnage n'a changé. Les nouvelles propositions figurent dans les diagnostics existants.

## Mesures reproductibles

Machine : macOS 26.6.2 ARM64 ; Python 3.12.14, NumPy 2.5.3, SciPy 1.18.1 ; threads BLAS/OMP limités à un. Trois répétitions de la **nouvelle recherche seule**, sans cache de résultat : première invocation puis deux suivantes. Cela ne mesure ni une accélération globale ni un temps jusqu'au son dans le navigateur.

| Entrée | Référence | Meilleure proposition | Résultat |
|---|---|---|---|
| Signal synthétique connu, 0,15 s / 44,1 kHz, avec un mode indépendant et un transitoire | 21 blocs ; erreur 0,00036877225 | 9 blocs ; erreur 4,59e-8 ; erreur absolue maximale d'échantillon 4,71e-8 | Admissible en simplification à budget 20 %, refusée par la génération stricte sur une bande |
| Piano fourni, trois premières secondes / 44,1 kHz, modèle de référence à 40 modes | 88 blocs avant nettoyage, dont gain identité | Aucune proposition : aucun groupe éligible | Modèle inchangé par cette recherche |

Les 9 blocs comprennent les autres branches conservées ; le groupe de huit modes est remplacé par les quatre traitements explicites. Les mesures détaillées sont dans `harmonic-benchmark.json`.

Temps de recherche synthétique : 0,174 / 0,161 / 0,163 s. Sur le piano : 0,00696 / 0,00709 / 0,00701 s, uniquement pour constater l'absence de groupe éligible. **Aucune réduction supplémentaire ni accélération du piano n'est démontrée.** La génération/simplification complète du piano n'a pas été relancée pour ce lot ; le résultat précédent de 20 blocs avec budget de 20 % n'est pas une nouvelle mesure.

L'amélioration d'erreur synthétique ne suffit pas à prétendre une équivalence exacte : une bande presque silencieuse reste moins bonne selon le critère strict. La proposition est donc rejetée dans ce mode. Les tolérances n'ont pas été assouplies pour la faire passer.

## Validation

Tolérance de la fixture de substitution fixée avant test : erreur maximale d'échantillon <1e-6. Mesure obtenue : 4,71e-8. Vérifications : branches conservées, sérialisation reproductible, identifiants sans collision, modes non comptés deux fois, groupes désaccordés ou décalés exclus, routes non unitaires exclues, intégration et maintien des garde-fous.

Comparaison réellement exécutée avec Pyodide sous Node, pas avec un téléphone ou un navigateur physique : écart maximal natif/WASM du nouveau candidat 1,81e-12 ; écart de fonction objectif 5,24e-12, sous les seuils préexistants respectifs de 1e-7 et 1e-8. La génération, le peigne et le candidat bruité restent couverts par le même contrôle (`harmonic-wasm-validation.json`). Les durées de ce contrôle ne constituent pas une comparaison de vitesse entre appareils.

Résultats exécutés : suite backend complète **169 tests réussis**, puis **7 tests ciblés réussis** après ajout du contrôle de non-duplication ; **62 tests frontend réussis**. Trois avertissements de dépréciation préexistants sur la suite backend.

Commandes de recette :

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
node frontend/tests/run.mjs
.venv/bin/python scripts/prepare_local_runtime.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend .venv/bin/python scripts/generation_reference.py
node scripts/validate_generation_wasm.mjs docs/harmonic-wasm-validation.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/benchmark_harmonic_groups.py \
  --patch .local/piano-generation-reference.json --wav ../piano.wav \
  --output docs/harmonic-benchmark.json
git diff --check
```

Le benchmark nécessite le modèle de référence du même extrait. Aucun audio privé n'est inclus dans les rapports. Sans les deux arguments privés, il reste exécutable sur la fixture synthétique seule.

Non effectués : écoute comparative contrôlée, simulation électrique/mesure matérielle, recette visuelle navigateur, MIDI physique, tablette/téléphone, tests ou déploiement de production. Aucun changement frontend : pas de nouveau build Vite pour ce lot.

## Fichiers et livraison

- `backend/lab/harmonic_groups.py` : éligibilité, ajustement du résidu et remplacement partiel.
- `backend/lab/generation_search.py`, `compact.py` : propositions soumises aux garde-fous existants.
- `backend/lab/compute.py`, `scripts/prepare_local_runtime.py` : version et liste explicite des sources distribuées.
- `backend/tests/test_harmonic_groups.py` et scripts de benchmark/parité : recette et preuves.

Aucune nouvelle dépendance ni licence, migration, modification d'authentification ou de secret. Les sources privées restent exclues de Git. Livraison locale uniquement.

Après autorisation de déploiement : livrer les fichiers ensemble, reconstruire le runtime avec `scripts/prepare_local_runtime.py`, vérifier `ready` et la version v5, puis suivre la procédure existante et recharger après sauvegarde du projet. Aucun nouveau téléchargement de dépendances n'est nécessaire si le runtime est déjà complet. Retour arrière : restaurer le commit `1f457d2` et reconstruire son archive v4. Les modèles produits utilisent des blocs déjà pris en charge ; aucune restauration SQLite n'est requise.

## Limites et reprise

Le nombre de blocs mesure des fonctions DSP, **pas** une nomenclature de pièces électroniques. La saturation numérique suréchantillonnée n'est pas à elle seule un schéma d'AOP validé. Coût, consommation et encombrement réels restent à mesurer. L'enveloppe est exponentielle ; ce n'est pas un ADSR arbitraire.

Prochain travail : rechercher des excitations résonantes compatibles avec les battements et décroissances du piano, sans supprimer son inharmonicité ; comparer chaque candidat aux mêmes critères puis établir un schéma matériel et une nomenclature vérifiés. Ce lot ne promet pas la reproduction exacte du piano avec un seul oscillateur.
