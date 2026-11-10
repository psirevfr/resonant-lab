# Simplification audio explicite — livraison locale du 10 novembre 2026

## Périmètre livré

Dans **Analyse du son**, la recherche compare désormais des chaînes sinus → saturation asymétrique suréchantillonnée ×4 → filtre → enveloppe commune, ainsi que des branches bruit blanc → filtre(s) → enveloppe → sommateur. L’amplitude du bruit est un paramètre visible de sa source. Aucun amplificateur physique n’est prétendu caché dans ce réglage.

Les architectures nouvelles utilisent les blocs DSP existants. Les critères de qualité, le suréchantillonnage, la double précision et les graines restent inchangés. Une étape d’ajustement pleine fréquence propose des paramètres ; elle n’est acceptée que si l’objectif complet s’améliore. La sélection finale conserve le budget global et, lorsque l’option est activée, les contrôles d’attaque/bandes. La version précise demeure disponible. Cela recherche le meilleur compromis parmi les candidats explorés, pas un minimum global démontré.

Les noms du catalogue sont les titres principaux du rack et du graphe, les rôles restent secondaires. Les câbles indiquent le type réel et l’identifiant. L’inventaire expose les paramètres effectifs (y compris les valeurs par défaut), les blocs déconnectés et des indications matérielles. Un ancien « mode amorti » est présenté comme sinus + enveloppe avec compensation de phase.

Deux défauts supplémentaires sont corrigés : une chaîne à enveloppe partagée peut être simplifiée à nouveau après sauvegarde/rechargement ; la transposition MIDI retrouve l’enveloppe au-delà des filtres/saturations lorsqu’elle est non ambiguë. Un chemin de dérivation sans la même enveloppe empêche cette inférence. La borne basse de fréquence est appliquée avant la compensation de phase.

## Architecture et fichiers

- `backend/lab/nonlinear_fit.py` : deux architectures supplémentaires, ajustement conjoint et raffinement pleine fréquence borné (45 évaluations principales maximum ; les appels résiduels réels sont comptés).
- `backend/lab/texture.py`, `compact.py` : recherche explicite de bruit filtré, dissociation exploration/protection de qualité, diagnostics et reprise d’un modèle partagé sauvegardé.
- `schema.py`, `compute.py` : option `test_noise`, version `shared-python-v2-sobriety`.
- `instrument.py`, `frontend/src/instrumentLocal.ts` : transposition cohérente des chaînes partagées.
- `frontend/src/audioInventory.ts`, `components/AudioInventory.tsx`, `Graph.tsx`, `Rack.tsx`, `App.tsx`, `types.ts`, `style.css` : visibilité des modules et réglages.
- `scripts/prepare_local_runtime.py` : version du paquet numérique ; aucun nouveau service.
- Tests de sobriété, inventaire et fixtures de transposition ; trois scripts de référence/benchmark/validation WASM. Build `frontend/dist` régénéré.

Le calcul interactif reste dans le worker Pyodide de l’appareil. Les modules Python sont partagés avec les tests natifs ; leur emplacement dans `backend/` ne signifie pas que ces calculs ont été remis sur le serveur. Aucun changement de base, session, consentement, secret ou production. Aucune dépendance/licence ajoutée.

## Mesures comparables

Mesures natives réalisées le 5 novembre : macOS 26.6.2 arm64, Python 3.12.14, NumPy 2.5.3, SciPy 1.18.1. Même environnement, mêmes entrées/empreintes, 44 100 Hz, poids par défaut, budget +20 %, protection des bandes et exploration activées. `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`. Trois simplifications par cas ; médianes ci-dessous. Référence : code du commit `1785be9`. Les résultats bruts, dont première exécution et répétitions suivantes, sont dans `sobriety-benchmark.json`. Le chargement de l’interpréteur est exclu ; aucun gain de cache exact n’est revendiqué. Le modèle précis et le processeur Mac ne sont pas identifiés plus finement.

| Entrée | Durée | Blocs retenus avant → après | Sources avant → après | Objectif avant → après | Recherche médiane avant → après |
|---|---:|---:|---:|---:|---:|
| Saturation + enveloppe connues | 0,25 s | 8 → 5 | 4 → 1 | 3,836e-4 → 1,004e-7 | 6,34 → 10,56 s |
| Banque harmonique exacte | 0,25 s | 12 → 12 | 8 → 8 | 2,826e-16 → identique | 6,13 → 11,95 s |
| Piano | 0,35 s | 12 → 12 | 5 → 5 | 0,359104 → identique | 7,42 → 15,01 s |
| Piano 2 | 0,35 s | 16 → 16 | 7 → 7 | 0,134467 → identique | 8,43 → 16,68 s |

Le premier cas part d’une banque de 18 blocs avant toute simplification. Le gain 8 → 5 compare les deux versions de l’algorithme, pas 18 → 5. L’objectif n’est pas un pourcentage de ressemblance perceptive.

**Pas de réduction supplémentaire démontrée sur les deux extraits de piano. La recherche coûte davantage de temps.** Sur le premier cas, le rendu du candidat passe même d’environ 0,507 ms à 2,35 ms (médianes de cinq rendus natifs), en raison notamment de la saturation ×4. Le gain démontré concerne la représentation en blocs et l’objectif du cas synthétique, pas la consommation électrique ni l’efficacité CPU.

Reproduction depuis la racine :

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/benchmark_sobriety.py --repetitions 3 --piano-directory .. --output .local/sobriety-benchmark-after.json
# Pour l’avant : même commande avec --source-root <copie du backend du commit 1785be9>
```

Les WAV piano restent locaux, non ajoutés au rapport. Les extraits courts ne valident pas toute la décroissance, toutes les notes ni les appareils mobiles.

## Validations réellement exécutées

```bash
PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/pytest backend/tests -q
PYTHONPATH=backend .venv/bin/python scripts/client_fixtures.py
node frontend/tests/run.mjs
npm run build --prefix frontend
PYTHONPATH=backend OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/sobriety_reference.py
.venv/bin/python scripts/prepare_local_runtime.py
node scripts/validate_sobriety_wasm.mjs
git diff --check
```

- **150 tests Python réussis**, trois avertissements de dépréciation FastAPI/Starlette déjà présents.
- **61 tests frontend réussis**, y compris la comparaison Python/JavaScript des notes MIDI 0, 69, 81, 127 sur les chaînes partagées ajoutées aux fixtures. Tolérance absolue DSP existante : 2e-9.
- Build TypeScript/Vite réussi. Aucun contrôle lint séparé défini dans `package.json`.
- Deux calculs réels Pyodide sous Node : nouvelle recherche et reprise du résultat sérialisé. Seuils fixés dans le script : erreur maximale et RMS ≤1e-7, écart d’objectif ≤1e-8, mêmes types de blocs. Écart maximal observé 5,28e-13 ; RMS maximal 3,30e-13 ; écart d’objectif maximal 8,64e-13. Voir `sobriety-wasm-validation.json`. Ce n’est pas une identité bit à bit.
- Pyodide : Python 3.14.2, NumPy 2.4.6, SciPy 1.18.0. Initialisation mesurée ~5,82 s ; calcul synthétique ~26,08 s, reprise ~0,17 s. Un seul passage : pas un benchmark comparatif du navigateur.
- Recette navigateur intégrée achevée le 10 novembre sur `localhost:8020/analyse`, base de test isolée dans `/tmp`, sans compte : note modale de démonstration, sélection de 0,25 s, génération puis simplification. Résultat **11 → 10 blocs, 4 → 4 sources**, objectif affiché **0,0119 → 0,0108**, plafond 0,0143. Le message terminal confirme le calcul local et le modèle chargé. Inventaire ouvert : quatre sinus, quatre enveloppes exponentielles, une somme, une sortie, paramètres et indications matérielles visibles. Aucun message console d’erreur relevé dans les contrôles effectués. Une première tentative avait rencontré un ADSR déconnecté dans le projet ; cette seconde recette est isolée et aboutit normalement.
- Télémétrie du navigateur pour cette recette (un seul passage, pas une comparaison avant/après) : génération 6 636,4 ms au total, dont initialisation 2 716,4 ms et calcul 3 902,5 ms ; simplification 32 438,3 ms au total, dont calcul worker 32 425,1 ms, initialisation réutilisée 0 ms. Après simplification : audio disponible en 38,4 ms, rendu 25,0 ms, analyses achevées à 88,7 ms. Ces durées sont mesurées dans leur propre contexte, sans soustraction serveur/navigateur.

Non exécutés : essai sur clavier MIDI physique, Android/iPhone/tablette, écoute perceptive contrôlée, mesure électrique d’un montage réel, tests de production. Le bruit du moteur JavaScript reste déterministe mais différent de NumPy : aucune équivalence échantillon par échantillon entre ces réalisations n’est revendiquée.

## Limites et prochaine tranche

Les blocs sont des fonctions numériques, pas une nomenclature de pièces à acheter. Un AOP nécessite alimentation, résistances, polarisation et éventuellement d’autres composants. Un filtre de bruit ne recrée pas automatiquement des partiels stables ; un modèle non linéaire numérique n’est pas un circuit analogique validé. L’inventaire le précise. Aucun gain d’énergie établi.

Prochaine étape : étudier les résidus de notes de piano complètes pour proposer des architectures plus pertinentes. Ensuite, dimensionner une topologie matérielle explicite et valider sa réponse avant de promettre une nomenclature reproductible. Les architectures présentes restent utilisables sans cette étape.

## Livraison et retour arrière

Version locale uniquement ; aucun push déclenchant la production. Pour une future livraison autorisée, sauvegarder les projets normalement, installer ensemble le code et le build correspondant, puis régénérer le paquet Python local avec `scripts/prepare_local_runtime.py` (ajouter `--download` uniquement si le runtime manque). Vérifier la version de l’algorithme et recharger la page pour remplacer les workers ouverts. Aucune migration de base nécessaire.

Retour arrière : remettre le code et le build précédents ensemble, reconstruire leur paquet numérique, puis recharger le navigateur. Les projets n’utilisent que des types DSP déjà existants ; l’ancienne recherche peut cependant refuser de resimplifier une architecture à enveloppe partagée. Conserver le modèle précis pour reprendre dans cette version.
