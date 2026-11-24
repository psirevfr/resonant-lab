# Apprentissage acoustique de Résonant

À l’entrée du site, **Accepter** ou **Refuser** détermine la participation à la mémoire collective. Le laboratoire est utilisable avant et après le choix. L’accord est enregistré dans SQLite pour le compte ou la session visiteur. Une nouvelle session visiteur, qui expire après 24 heures, demande un nouvel accord. **Confidentialité** permet de changer de décision et de retirer les contributions de l’identité en cours. Un retrait supprime ses observations collectives et invalide les justificatifs en cours, y compris après un nouvel accord. Les observations antérieures à cet écran de consentement sont exclues des statistiques.

Après accord, chaque génération locale évalue automatiquement une piste d’affinage. Si elle améliore le montage selon les critères numériques, le site transmet le profil, la piste et la récompense avec un justificatif propre à la session. La mémoire collective exclut le WAV, le nom du fichier, le montage et l’empreinte calculée dans le navigateur. Le serveur garde un identifiant de déduplication dérivé avec une clé serveur. Il conserve au plus une observation par extrait et par piste, 24 par propriétaire et 10 000 au total pendant 60 jours. Les échecs réseau temporaires sont retentés dans l’onglet en cours. Une panne prolongée, un quota atteint ou la fermeture de l’onglet peut empêcher l’envoi. Les contributions d’une ancienne session visiteur expirent avec la rétention.

**Analyse du son → Réglages → Mémoire d’apprentissage** propose aussi une mémoire privée facultative. Le navigateur conserve au plus 128 essais par compte ou session visiteur, y compris les essais rejetés, avec l’empreinte locale de l’extrait. L’utilisateur peut effacer cet historique depuis le même réglage. Le chargement de la référence WAV suit le parcours audio existant.

Les scores déclarés par les navigateurs indiquent quelles pistes explorer. À partir de cinq identités distinctes pour un couple profil/piste, chaque identité compte pour une voix sur la base de la moyenne de ses essais transmis. Les statistiques collectives guident les premiers essais sans compter comme des observations privées. Une empreinte locale répartit les extraits entre la piste connue et l’exploration, réservée à l’un des quatre groupes. Si les deux pistes ont déjà été mesurées dans la mémoire privée, leurs observations locales guident le choix. Le serveur vérifie le consentement et le justificatif. La validation numérique de chaque candidat se fait sur l’appareil. La sélection des seuls essais positifs introduit un biais de sélection. Leur récompense moyenne mesure l’ampleur des améliorations transmises et donne une indication pour l’exploration. L’estimation de la probabilité de succès demande également le nombre d’échecs.

L’analyse de l’extrait estime ses partiels et son enveloppe. Le worker garde une seule analyse en mémoire. Une génération peut la réutiliser si les échantillons, la fréquence d’échantillonnage et le nombre maximal de partiels sont identiques. La fermeture du worker efface ce cache.

L’étape facultative s’ajoute après la recherche habituelle de montages sobres. Un bandit contextuel choisit une piste parmi une enveloppe ADSR commune et une décroissance exponentielle commune. Il distingue une impulsion courte, une note décroissante et un son entretenu. À profil égal, il combine la récompense moyenne observée et une prime d’exploration décroissante. Les tentatives identiques sur le même extrait pour la même piste ne renforcent qu’une fois la décision. Une analyse seule n’a pas de récompense, car elle ne donne pas d’erreur de synthèse.

Chaque candidat est reconstruit avec les blocs du site et recalculé à la fréquence d’origine du modèle. Pour remplacer le modèle sélectionné, il doit respecter le même budget de blocs et les critères de fidélité existants, avec la même tolérance numérique de 1e-12. L’erreur temporelle, le spectre, le spectrogramme, l’attaque, l’enveloppe et les bandes de fréquences restent chacun contrôlés. Une diminution de l’erreur ou du nombre de blocs rapporte une récompense. Un rejet vaut zéro dans la mémoire privée si elle est activée.

## Vocabulaire des rapports

Les rapports emploient les termes du cours « L’intelligence artificielle », p. 2 à 9, selon le mécanisme décrit. Une **observation** est un essai mesuré. Le profil du son est une **caractéristique** qualitative de l’observation. La **récompense** est une donnée quantitative qui mesure le gain retenu. Dans l’**apprentissage par renforcement** utilisé ici, le bandit contextuel met à jour les statistiques des pistes essayées. En phase d’**inférence**, il choisit une piste pour un nouvel extrait. La **validation du modèle** compare ensuite le candidat au WAV avec les critères de fidélité fixés.

La **généralisation** de cette stratégie doit être évaluée sur des **données de test** distinctes des sons qui ont alimenté la mémoire d’apprentissage. Regrouper les extraits d’un même enregistrement ou instrument lors de cette séparation limite le **biais** et le risque de **surapprentissage**. Une moyenne sur les observations positives renseigne sur les cas retenus. Une mesure de généralisation nécessite un ensemble de test complet.

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


## Optimiser un montage retouché

**Comparer les trois** évalue JeanJacky (Powell), Jean Neymar (L-BFGS-B) et l’évolution différentielle avec un budget par méthode. Le montage initial reste admissible et la sortie conserve la meilleure erreur mesurée. Les paramètres sont pris sur le trajet connecté à la sortie. Les modules modifiés et leurs filtres passent en tête. Les cases de l’inspecteur permettent de limiter volontairement ce travail. Les graines de bruit restent constantes.

**Tester un égaliseur après saturation** propose au plus un filtre paramétrique sur une branche pertinente. Le filtre est conservé s’il réduit le coût pondéré de plus de 1 % par rapport au meilleur montage sans ce nouveau filtre. **Simplifier** reprend le montage affiché. Pour un montage retouché, il compare les allègements sur le signal réellement calculé avec les tolérances choisies.

## Synchronisation de l’éditeur

L’aperçu dans Résonant Editor et le lanceur local `./run.sh` récupèrent les statistiques agrégées toutes les cinq minutes. Chaque groupe comprend au moins cinq identités. Le cache séparé reste utilisable pendant 24 heures si le site ne répond plus. Les statistiques de production guident les nouveaux essais locaux compatibles. Les observations locales, les réglages, les brouillons, les projets et les commits résident dans leurs propres fichiers.

En mode **Modifier**, un clic dans l’aperçu ouvre **Bloc sélectionné**. Les libellés et les couleurs modifiables s’actualisent dans l’aperçu. **Enregistrer** les inscrit dans le document de présentation. **Réinitialiser** rétablit les valeurs du site et **Annuler** permet de revenir au réglage précédent. Les libellés dynamiques et les déplacements entre groupes restent accessibles par **Ouvrir le code**. Les données de sélection servent uniquement à l’aperçu et le canal de messages est limité au port de l’éditeur.

L’aperçu local suit les sources du site et reconstruit l’archive de calcul WebAssembly lorsque les sources numériques changent. Les changements de présentation sur disque sont fusionnés avec les modifications en cours. Lorsqu’un même réglage est modifié de part et d’autre, la saisie en cours reste dans le brouillon et la version externe reste enregistrée jusqu’à la sauvegarde suivante. Un changement de l’éditeur lui-même entraîne sa relance lorsque le brouillon et les calculs sont au repos.

Dans Résonant Editor, **Publier** affiche les changements locaux et les commits à envoyer. La confirmation lance le contrôle des fichiers, les tests et la compilation, puis crée un commit local si nécessaire et envoie la version complète sur `origin/main`. **Vérification** permet aussi d’exécuter les contrôles séparément sans accès réseau. Si `main` a avancé sur GitHub et contient des changements absents du dépôt local, la publication s’arrête. Les fichiers ignorés restent sur le Mac et l’éditeur bloque les données privées détectées dans les changements ou les commits en attente.

Après la réception par GitHub, le lien **GitHub Actions** donne l’état du déploiement. Le workflow déploie les fichiers compilés dans `frontend/dist` et reconstruit l’archive WebAssembly. Le serveur initialise les tables de mémoire collective et de consentement au démarrage par migration additive.

Si le Trousseau ne possède pas encore d’identifiant GitHub utilisable, la publication peut ouvrir une fenêtre macOS qui demande le nom d’utilisateur et un jeton GitHub disposant du droit d’écriture. Git reçoit le jeton par son mécanisme d’identification et le Trousseau peut le conserver pour les prochaines publications. Si le lot inclut le workflow de déploiement, le jeton doit aussi avoir le droit de modifier ce workflow.

Si le jeton enregistré est refusé, **Publier → Utiliser un autre jeton pour cet envoi** ouvre la fenêtre macOS et utilise le nouveau jeton pour cette seule tentative. Après un refus d’autorisation, l’éditeur peut réessayer la version déjà vérifiée tant que les fichiers et la branche locale restent identiques. Le Trousseau garde ses identifiants existants.
