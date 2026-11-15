# Recherche hybride des modes aigus — 15 novembre 2026

## Ce qui change réellement

La génération et la simplification peuvent maintenant conserver les modes graves et les branches existantes (dont l’impact), puis remplacer seulement un groupe de modes aigus par une chaîne explicite :

- bruit blanc, amplification, passe-haut, enveloppe ;
- ou bruit blanc, amplification, peigne, passe-haut, enveloppe.

Le moteur essaie des coupures à 2 000 et 6 000 Hz dans la plus grande famille de modes directement sommés, avec au moins quatre modes remplaçables et au moins un mode conservé dans cette famille. Réinjections du peigne 0,95/0,99, trois décroissances fixes et la médiane mesurée du groupe ; graine de bruit 42 constante. Le gain est proposé par projection temporelle et niveaux d’énergie résiduelle, puis comparé avec l’objectif complet. Au plus quatre propositions finales sont émises, sans cacher de sinusoïdes dans un nouveau bloc.

Cette recherche rapide est limitée à une route unique vers la sortie, composée de sommes et de gains unité. Les filtres, saturations ou routes dupliquées en aval ne sont **pas** supposés transparents : ces familles sont ignorées par cette recherche particulière. Les autres méthodes restent disponibles. Les branches non remplacées sont conservées, sans reconstruire arbitrairement tout le modèle.

La génération tente ensuite de retirer un à un des oscillateurs directement sommés du meilleur modèle admissible. Chaque retrait est évalué sur le graphe réel, avec tous les critères et bandes de la référence. Les retraits refusés ne modifient pas le modèle. La référence reste accessible.

La génération stricte conserve son seuil numérique de 1e-12 par critère et bande. La simplification utilise la **tolérance explicitement choisie** et la protection d’attaque/bandes existante. Activer le bruit dans les réglages de simplification active aussi cette recherche hybride. Aucun changement des tolérances DSP, de la normalisation, des itérations de référence ou du suréchantillonnage.

## Résultat sur le piano : pas de gain inventé

Extrait identique à la validation précédente : début 0, durée 3 s, mono 44 100 Hz, même empreinte. La note entière d’environ 9,83 s n’est pas testée ici. Référence générée précédemment : 40 modes amortis, attaque ajustée et impact ; 87 blocs après retrait du gain unité.

| Proposition | Blocs | Modes amortis | Erreur globale | Génération stricte | Simplification +20 %, bandes protégées |
|---|---:|---:|---:|---|---|
| Référence | 87 | 40 | 0,297896353 | Conservée | Référence |
| Aigus remplacés par bruit filtré | 79 | 34 | 0,302584203 | Refusée | Refusée : bande aiguë |
| Aigus remplacés par bruit + peigne filtré | 80 | 34 | 0,302502779 | Refusée | Admissible |
| Meilleur montage de la recette de simplification | 20 | 9 | 0,331168254 | Non équivalent à la référence | Retenu |

Sur cette note, le groupe remplacé se situe au-dessus de 2 kHz. Le candidat à peigne augmente le score global d’environ 1,55 %. Le montage à 20 blocs l’augmente de **11,17 %**, sous le plafond demandé de 20 %, et respecte les contrôles d’attaque et de bandes de cette recette. Ces pourcentages concernent la fonction d’erreur, **pas une perte perceptive mesurée**, ni un pourcentage de ressemblance du son. La bande présence reste mal reproduite même par la référence ; la protection contre une régression ne garantit pas une erreur absolue faible.

**Le montage à 20 blocs était déjà trouvé au commit a95be03**, avec exactement les mêmes erreurs et bandes dans ce test. Il comporte 9 sinus avec 9 enveloppes, une somme et une sortie : il n’est pas un succès nouveau du bruit + peigne. Le nouvel ajout enrichit les alternatives et teste des retraits supplémentaires ; il ne démontre pas encore de réduction supplémentaire sur ce piano à fidélité inchangée.

Le résultat compact est disponible localement dans `.local/piano-hybrid-validation.monpatch`, exclu de Git. Les rapports versionnés ne contiennent aucun échantillon audio.

## Conditions et temps mesurés

Rapports : `hybrid-piano-before.json`, `hybrid-piano-benchmark.json`.

- macOS arm64, Python 3.12.14, NumPy 2.5.3, SciPy 1.18.1 ; OpenBLAS et OpenMP limités à un thread. CPU exact et RAM non relevés.
- Référence et entrée chargées avant le chronométrage ; mêmes poids par défaut.
- Recherche des branches hybrides seule : trois répétitions séquentielles, 0,237 / 0,230 / 0,230 s. Ce n’est ni la génération complète ni un temps navigateur.
- Recette entière de simplification : `tolerance=0.2`, `test_shaping=False`, `protect_texture=True`, `test_noise=True`. La recherche de saturation est désactivée **pour ce test uniquement** ; le réglage par défaut du site n’est pas modifié.
- Avant a95be03 : 11,664 s ; après : 12,034 s. Un passage entier par version, séquentiel après les tests : diagnostic ponctuel, **pas une preuve de gain de vitesse**. Le résultat choisi est identique.
- La tentative précédente avec recherche non linéaire activée n’a pas produit de résultat final conservé avant l’interruption de session. Elle n’est pas comptée comme réussie. Le parcours complet avec tous les réglages activés n’a donc pas été validé sur ce piano dans cette tranche.

## Validation

- Suite backend finale : **163 tests réussis en 58,49 s**, trois avertissements de dépréciation FastAPI/Starlette déjà présents. Journal local `.local/hybrid-suite-final.log`.
- 62 tests frontend exécutés, 62 réussis. Aucun fichier frontend ou dépendance frontend modifié ; pas de nouveau build Vite nécessaire ni exécuté dans cette tranche.
- Tests ajoutés : remplacement d’aigus sur une référence synthétique connue, conservation du mode grave et de l’impulsion existante, précision et sérialisation, collisions d’identifiants, absence de hauteur fondamentale, refus des chemins non linéaires ou filtrés en aval, refus des routes dupliquées, intégration à la simplification, suppression vérifiée d’une source inutile dans la génération.
- Pour le cas synthétique exactement représentable, tolérance absolue fixée à 2e-12 avant comparaison. Cette réussite contrôlée ne représente pas la reconstruction du piano.
- Exécution réelle Python/WebAssembly sous Node : génération synthétique et recherche hybride, comparaison avec Python natif. Seuils max/RMS 1e-7 et objectif 1e-8, inchangés ; voir `hybrid-wasm-validation.json`. L’erreur de la branche hybride reste inférieure à 2e-16 sur le passage consigné. Ce n’est pas une identité bit à bit.
- La dernière archive locale est reconstruite avec le module `hybrid` dans la liste explicite des sources autorisées et la version `shared-python-v4-hybrid`.

Commandes exécutées :

```sh
PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest backend/tests -q
node frontend/tests/run.mjs
.venv/bin/python scripts/prepare_local_runtime.py
PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/generation_reference.py
node scripts/validate_generation_wasm.mjs docs/hybrid-wasm-validation.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/benchmark_hybrid.py \
  --patch .local/piano-generation-reference.json --wav ../piano.wav \
  --output docs/hybrid-piano-benchmark.json --simplify --no-shaping \
  --selected-patch .local/piano-hybrid-validation.monpatch
git diff --check
```

Pour reproduire le benchmark, fournir le modèle de référence correspondant au même extrait WAV ; le script ne régénère pas ce modèle. La mesure « avant » a utilisé les modules numériques du commit a95be03 dans une copie locale isolée, sans modification de la base ni du dépôt de travail.

Non exécutés : comparaison perceptive contrôlée, piano dans un navigateur physique avec cette nouvelle recherche, MIDI physique, téléphones/tablettes, tests de production, compilation du peigne sur microcontrôleur, réalisation électrique. Le bruit JavaScript conserve sa réalisation différente de NumPy ; la parité échantillon par échantillon n’est pas revendiquée entre ces deux bruits.

## Fichiers, livraison et limites matérielles

- `backend/lab/hybrid.py` : propositions ciblées et reconnaissance des routes compatibles.
- `backend/lab/generation_search.py`, `identify.py` : sélection stricte et élagage vérifié.
- `backend/lab/compact.py` : intégration aux règles existantes de simplification.
- `backend/lab/compute.py`, `scripts/prepare_local_runtime.py` : version et archive locale.
- `backend/tests/test_hybrid.py`, scripts de benchmark et de comparaison WebAssembly : validation reproductible.

Aucune nouvelle dépendance, aucune migration de données, aucun secret, aucune modification d’authentification. Commit local ; pas de push ni de déploiement automatique.

Pour déployer après autorisation : livrer les sources ensemble, reconstruire l’archive locale et son manifeste, vérifier `ready` et `shared-python-v4-hybrid`, appliquer la procédure existante puis recharger la page après sauvegarde du travail. Le frontend actuel sait déjà afficher et rendre ces blocs. Retour arrière : restaurer a95be03 et reconstruire son archive numérique ; aucun retour de base de données nécessaire. Les mêmes types de blocs existent déjà dans a95be03, les projets hybrides restent donc lisibles, mais leur recherche automatique disparaît.

Le compteur mesure des fonctions DSP explicites, pas des pièces électroniques. La réduction de coût, de consommation et de surface demeure non mesurée. Le peigne nécessite toujours une mémoire de retard et n’est pas reproduit par le sketch Teensy actuel. Le montage à 20 blocs n’est pas une nomenclature physique validée.

Point de reprise : mieux ajuster les décroissances et l’inharmonicité des groupes tonals avant leur substitution, puis valider une réalisation matérielle et son coût réel. Les aigus du piano testés ne peuvent pas être considérés automatiquement comme du bruit diffus. L’objectif de forte réduction à fidélité inchangée reste ouvert.
