# Apprentissage acoustique de Résonant

Dans **Analyse du son → Réglages → Mémoire d’apprentissage**, activer **Apprendre sur cet appareil**. Le navigateur conserve au plus 128 essais par compte ou session visiteur. Chaque entrée contient l’empreinte des échantillons de la sélection, leur fréquence d’échantillonnage, le profil, la piste essayée et son score. L’historique se désactive ou s’efface depuis le même menu. Les essais, les empreintes et les scores restent dans le navigateur. Le chargement de la référence WAV utilise le parcours déjà en place.

L’analyse de l’extrait estime ses partiels et son enveloppe. Le worker garde une seule analyse en mémoire. Une génération peut la réutiliser si les échantillons, la fréquence d’échantillonnage et le nombre maximal de partiels sont identiques. La fermeture du worker efface ce cache.

L’étape facultative s’ajoute après la recherche habituelle de montages sobres. Un bandit contextuel choisit une piste parmi une enveloppe ADSR commune et une décroissance exponentielle commune. Il distingue une impulsion courte, une note décroissante et un son entretenu. À profil égal, il combine la récompense moyenne observée et une prime d’exploration décroissante. Les tentatives identiques sur le même extrait pour la même piste ne renforcent qu’une fois la décision. Une analyse seule n’a pas de récompense, car elle ne donne pas d’erreur de synthèse.

Chaque candidat est reconstruit avec les blocs du site et recalculé à la fréquence d’origine du modèle. Pour remplacer le modèle sélectionné, il doit respecter le même budget de blocs et les critères de fidélité existants, avec la même tolérance numérique de 1e-12. L’erreur temporelle, le spectre, le spectrogramme, l’attaque, l’enveloppe et les bandes de fréquences restent chacun contrôlés. Une diminution de l’erreur ou du nombre de blocs rapporte une récompense. Un rejet est enregistré à zéro.

La génération soustractive est retirée. Les anciens graphes comportant du bruit, des filtres et des enveloppes restent exécutables. La comparaison avec le WAV, le clavier, la simplification et le plan de montage restent accessibles.

## Mesures reproductibles

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=backend \
  .venv/bin/python scripts/benchmark_adaptive.py --piano ../piano.wav

.venv/bin/python scripts/prepare_local_runtime.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=backend \
  .venv/bin/python scripts/generation_reference.py
node scripts/validate_generation_wasm.mjs .local/adaptive-wasm-validation.json
```

Mesures sur le Mac de développement, à 44,1 kHz en mono. La génération compare une exécution avec affinage et une avec la méthode habituelle, avec quatre partiels maximum et les mêmes autres réglages. Les profils archet et cuivre sont des signaux synthétiques de test. Le piano local est un extrait de 0,8 s du WAV du projet.

| Extrait | Coût habituel | Coût avec essai adaptatif | Blocs habituel → adaptatif | Analyse à froid → réutilisée |
|---|---:|---:|---:|---:|
| Percussion synthétique | 0,76507 | 0,54226 | 7 → 7 | 9,40 → 0,035 ms |
| Piano synthétique | 0,02386 | 0,02386 | 6 → 6 | 50,24 → 0,121 ms |
| Archet synthétique | 0,25631 | 0,01041 | 6 → 6 | 84,80 → 0,221 ms |
| Cuivre synthétique | 0,22246 | 0,00821 | 6 → 6 | 82,87 → 0,252 ms |
| Piano local | 0,44764 | 0,44764 | 10 → 10 | 22,43 → 0,119 ms |

Les temps d’analyse sont les médianes de trois mesures de l’étape de calcul, hors chargement du WAV. L’optimisation d’une enveloppe ajoute un essai. Les mesures n’établissent pas d’accélération de la génération entière ni de fidélité perceptive sur tout un instrument.

Sur le test ADSR de parité, l’écart maximal par échantillon entre Python et Pyodide était de 2,22e-12 avec une tolérance de 1e-7. L’écart d’objectif était de 5,81e-13 avec une tolérance de 1e-8. Le choix de la piste et son acceptation concordaient.

## Du clavier au montage

Le modèle reste jouable par transposition. Calibrer le timbre sur le clavier entier demande des enregistrements à plusieurs notes, vélocités et durées. Les percussions apériodiques demandent des références par frappe ou articulation. Le plan donne les blocs à réaliser. La conformité du montage, la traduction complète du DSP dans le firmware et les mesures sur carte restent à valider.

Sources méthodologiques. [Sélection de modèles pour les bandits contextuels](https://papers.nips.cc/paper_files/paper/2019/hash/433371e69eb202f8e7bc8ec2c8d48021-Abstract.html) et [apprentissage de paramètres pour des modules DSP explicites](https://arxiv.org/abs/2001.04643).
