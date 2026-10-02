# Validation de l’affinage — 1 octobre 2026

## Mesures reproductibles

Trois premières secondes des WAV fournis, mono 48 kHz, poids temps/spectre/STFT/enveloppe/attaque = 0,1/0,25/0,5/0,15/0,25 ; pénalité de complexité 0,0001.

| Référence | Modèle retenu | Erreur à la génération | Après 181 évaluations Powell |
|---|---|---:|---:|
| piano.wav | 40 modes isolés, attaque ajustée et impact | 0,297070 | 0,285568 |
| piano2.wav | 39 modes détaillés, attaque ajustée et impact | 0,133579 | 0,125495 |

Budget atteint sans convergence revendiquée. Ces coûts relatifs ne sont pas des pourcentages de ressemblance. Le résidu reste audible potentiellement ; aucune équivalence perceptive à 100 % n’est établie. Les paramètres, bornes et candidats sont conservés dans `piano-impact-validation.json`, les modèles et WAV dans `../examples/`.

## Vérifications

- 29 tests Python/API réussis : analyse, modes proches, impact sur bruit de graine différente, cohérence du coût d’attaque avec le rendu exporté, filtres/Bode, optimisation, graphes invalides, exports et plages d’octets audio.
- Compilation TypeScript et build Vite réussis après la dernière modification du rapport.
- Navigateur : import de piano2, génération détaillée, édition du filtre d’impact (800 → 1 200 Hz), modification simultanée de H(z) et du coût (0,1336 → 0,1347), restauration puis optimisation (0,1336 → 0,1255, 181 évaluations).
- Lecture A/B : sources mono de même durée ; après pause à 0,111495 s, basculement conservant exactement cette position. Les deux sources exposent une plage de lecture 0–3 s après correction HTTP Range.
- Téléchargements effectifs du JSON, du PNG (5 100 × 2 250 pixels) et du rapport HTML via le navigateur intégré. Modèle téléchargé relu, validé et rendu par le moteur.
- Rapport final : 47 blocs, 19 figures SVG, trois spectrogrammes incorporés ; affichage vérifié sans débordement horizontal et images toutes chargées. Paramètres et JSON accessibles dans les sections dépliables. Export PDF par impression disponible ; aucun fichier PDF n’a été produit lors de cette vérification.
- Aucune erreur de console observée sur la dernière session du build de production.

Le serveur d’application reste local, accessible à `http://127.0.0.1:8000/`. Si le processus est interrompu, relancer `./run.sh`. Le serveur temporaire de vérification du rapport a été arrêté.

## Simplification à budget d’erreur — 1 octobre 2026

Mesures sur les mêmes sélections et avec les mêmes poids, à partir des modèles précis déjà optimisés. Hausse maximale du coût pondéré : 20 %. Chaque candidat est évalué par le moteur réel à 48 kHz. Le minimum de blocs est choisi parmi les essais admissibles, puis le nombre de paramètres, puis le coût. Il ne s’agit pas d’un optimum global prouvé.

| WAV | Blocs | Générateurs | Paramètres | Coût précis → compact | Rendu précis → compact |
|---|---:|---:|---:|---:|---:|
| piano2 | 47 → 14 | 40 → 12 | 244 → 72 | 0,125495 → 0,145617 | 82,9 → 23,6 ms |
| piano | 48 → 10 | 41 → 8 | 250 → 48 | 0,285568 → 0,338792 | 81,1 → 15,4 ms |

Temps de rendu : médiane de 9 exécutions après échauffement, 3 s mono à 48 kHz, sur cette machine ; ce n’est pas une garantie sur d’autres systèmes. La recherche prend environ 12–13 s. Le nombre de générateurs comprend la source de bruit éventuelle. Aucun oscillateur n’est masqué dans un bloc composite.

L’essai saturation tanh + passe-bas du second ordre + gain est effectué sur les budgets de 4, 8 et 12 modes. Il n’a pas justifié ses trois blocs supplémentaires pour les modèles finalement retenus. Les branches de bruit d’impact sont aussi comparées lorsque la référence en contient une. Elles ne sont pas retenues dans ces deux compromis ; le coût d’attaque passe respectivement de 0,124125 à 0,145266 et de 0,364917 à 0,416706. Le bouton de restauration conserve les branches d’impact originales dans leur totalité. Une écoute reste nécessaire pour choisir le compromis acceptable.

Reproduction :

```bash
PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python experiments/compact/validate.py
```

Résultats détaillés et contributions par ablation : `compact-validation.json`. Modèles et sons : `../examples/piano-compact.*` et `../examples/piano2-compact.*`. Les fichiers `*-impact.*` restent inchangés. Sauvegarde des sources de la version précise : `../backups/precision-v1-20261001.zip`.

La simplification ajoute des tests de suppression effective de sources redondantes, préservation d’un gain utile, refus d’une hausse de coût avec un budget nul, sérialisation identique, bornes et hautes fréquences, cohérence du traitement de sortie avec le graphe, et API réversible.

Vérification de cette extension : **35 tests Python/API réussis**, compilation TypeScript et build Vite réussis. Dans le navigateur, import du modèle précis de piano2, simplification à 14 blocs (coût affiché 0,1456), comparaison des candidats et restauration à 47 blocs (coût 0,1255) vérifiés. Les quatre fichiers précis `*-impact.monpatch/.wav` ont été comparés octet par octet à la sauvegarde : inchangés.

Le budget nul a également été vérifié dans l’interface avec piano2 : 47 → 47 blocs, 40 → 40 générateurs, coût 0,1255 inchangé et message « Aucune réduction retenue ». Le budget de 20 % est rétabli pour l’écoute du compromis compact.

## Architectures non linéaires globales — 2 octobre 2026

Le patch VCV fourni a été inspecté (JSON conservé dans `experiments/nonlinear/vcv-source.json`), sans le modifier. La recherche ne se limite plus à ajouter une saturation après une banque figée : sources, saturation et filtres sont ajustés ensemble, avec 14 topologies et vérification systématique du coût à 48 kHz. Les deux sélections sont toujours les trois premières secondes, avec les mêmes poids et modèles précis de départ.

| Cas piano2 | Sources | Blocs totaux | Erreur pondérée |
|---|---:|---:|---:|
| Modèle précis | 40 | 47 | 0,125495 |
| Compact précédent, toujours retenu | 12 | 14 | 0,145617 |
| Saturation + passe-bas | 2 | 6 | 0,318632 |
| Saturation + passe-haut + EQ + passe-bas | 2 | 8 | 0,244495 |
| Saturation + passe-haut + EQ + passe-bas | 3 | 9 | 0,228121 |
| Direct + branche harmonique filtrée | 6 | 12 | 0,166170 |
| Direct + branche harmonique filtrée | 8 | 14 | 0,157648 |

Le filtrage supplémentaire améliore effectivement certains essais à très peu de sources, mais aucune de ces architectures ne remplace le modèle compact à 14 blocs dans le budget de +20 % (plafond 0,150594). Pour piano, la branche parallèle à 8 sources atteint 0,337301 avec 14 blocs ; le compact de 10 blocs à 0,338792 conserve donc l’avantage sur le nombre de blocs sous le plafond de 0,342681. Cela ne prouve pas qu’une meilleure synthèse non linéaire soit impossible : les topologies et budgets d’optimisation sont limités.

La recherche complète prend environ 44 s par fichier sur cette machine. Données détaillées : `global-processing-validation.json`. Script : `PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python experiments/nonlinear/validate.py`. Les résultats retenus sont enregistrés séparément dans `examples/*-global.*` ; les fichiers `*-compact.*` et `*-impact.*` restent conservés. Sauvegarde avant extension : `backups/compact-v1-20261001.zip`.

Validation : 38 tests Python/API réussis, compilation TypeScript et build Vite réussis. Les nouveaux tests couvrent création des harmoniques paires, déterminisme, entrée nulle, stabilité et gain des nouveaux filtres, accord Bode/rendu, graphes des quatre familles, sérialisation identique et cohérence entre les coûts annoncés et les rendus complets. Après ajustement des bornes de recherche, les trois tests non linéaires ont été relancés avec succès.

Parcours navigateur vérifié sur le build de production : bibliothèque à 21 blocs, import de piano2 et du modèle précis, recherche globale (14 topologies affichées), chargement du candidat à trois sources et trois filtres (9 blocs, 29 paramètres, coût réellement rendu 0,2281), téléchargement effectif du modèle, puis retour au meilleur compromis à 14 blocs. Aucune erreur de console observée. L’essai téléchargé est conservé dans `examples/piano2-trois-sources-filtres.monpatch`, avec son WAV reproductible.

Sobriété visuelle et CPU sont distinctes : le candidat à 9 blocs utilise la saturation ×4 ; sa médiane de rendu sur 9 exécutions après échauffement est **32,63 ms**, contre **23,32 ms** pour le compact à 14 blocs, sur 3 s de signal. Il réduit donc le nombre de sources et de blocs, mais n’améliore ni la précision ni le temps CPU dans cet essai. Les deux versions restent disponibles.
