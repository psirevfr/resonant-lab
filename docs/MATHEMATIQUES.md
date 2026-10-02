# Modèles, mesures et hypothèses

## Données

Les échantillons lus par libsndfile sont convertis en flottants sans normalisation additionnelle. Pour la comparaison et l’analyse, `x[n]` est la moyenne arithmétique des canaux. Des canaux en opposition de phase peuvent donc s’annuler : c’est une limite de cette réduction mono, pas un défaut du lecteur WAV. L’original binaire stéréo est conservé séparément.

L’enveloppe affichée est la racine de la moyenne glissante centrée de `x²`, sur 10 ms. Aux bords, le prolongement est nul. Le graphe temporel utilise des minima et maxima par intervalle, pour ne pas masquer les crêtes. Le spectre affiché est la racine d’un spectre de puissance Welch, fenêtré Hann, au plus 16 384 points par fenêtre. Les niveaux sont exprimés en `20 log10(amplitude)` avec une référence numérique de 1 ; le niveau d’un sinus RMS diffère de sa crête.

La STFT d’affichage utilise des fenêtres Hann de 1 024 échantillons et au plus environ 220 trames, éventuellement espacées sur un fichier long. Elle n’a donc pas vocation à conserver chaque transitoire d’un long enregistrement. La STFT de mesure des décroissances utilise des fenêtres plus longues (jusqu’à 8 192 points).

## Fondamentale et partiels

1. Le début est le premier dépassement de 3,5 % du maximum de l’enveloppe RMS.
2. La fondamentale initiale est obtenue par autocorrélation FFT après rééchantillonnage polyphasé à 11 025 Hz, sur au plus une seconde. Les retards testés correspondent approximativement à 20–2 205 Hz. Un pic doit atteindre au moins 0,15 ; le premier pic supérieur à 88 % du maximum admissible est choisi puis interpolé par parabole. Ce seuil est une règle algorithmique, **pas une probabilité**.
3. La FFT Hann sur au plus quatre secondes détecte des pics au-dessus d’une proéminence relative de 0,008, séparés d’au moins environ 12 Hz. Les fréquences sont interpolées sur le logarithme du module. La recherche se limite à 20 Hz–min(16 kHz, 0,47 fs).
4. Les partiels les plus élevés en module spectral sont conservés jusqu’au maximum demandé, puis leurs amplitudes et phases sont estimées temporellement. Des pics de bruit ou des résonances non harmoniques peuvent rester dans cette liste.
5. L’estimation de fondamentale est rapprochée du **partiel de plus grande amplitude** parmi les pics proches de l’estimation initiale (±8 %), et non du premier pic dans l’ordre des fréquences. Cette règle évite qu’un faible pic voisin remplace le pic dominant.

Aucune garantie d’absence d’erreur d’octave n’est donnée pour des sons polyphoniques, très courts ou sans fondamentale. Une périodicité insuffisante produit une fondamentale indéterminée, pas un résultat inventé.

## Modèle modal

Pour chaque mode, avec `u=t−t₀` :

```text
x_k(t) = 0,                                             u < 0
x_k(t) = A_k exp(−u/τ_k) (1−exp(−u/a_k)) sin(2π f_k u+φ_k), u ≥ 0
```

Quand `a=0`, le facteur d’attaque vaut 1. Les échantillons sont calculés directement à `t=n/fs`. Après extinction du terme d’attaque, le mode satisfait :

```text
q″ + (2/τ) q′ + ((2πf)² + 1/τ²) q = 0.
```

C’est la réponse libre d’un oscillateur amorti, avec fréquence **amortie** f. L’attaque ajoute une seconde exponentielle : l’équation homogène ci-dessus n’est pas revendiquée pendant l’attaque. Aucune masse, raideur ou force de marteau n’est inférée univoquement.

La constante τ est estimée à partir de la pente de `log |STFT|` autour du pic, après l’attaque et au-dessus de 4 % du maximum de sa trajectoire. `τ=−1/pente`, bornée entre 0,02 et 30 s. Une pente non décroissante est ramenée à 30 s ; un nombre insuffisant de trames entraîne un défaut à 1 s. Ces bornes et défauts sont des contraintes de modèle, pas des mesures certaines. R² = `1−SSE/SST` décrit cette régression seulement.

L’attaque est initialisée au tiers du temps allant du début estimé au pic RMS et bornée entre 0,1 et 100 ms. Il s’agit d’une **heuristique de forme d’enveloppe**, pas du temps d’attaque physiologique mesuré de l’instrument.

Pour chaque fréquence f, on projette le signal sur deux bases amorties `e(t)sin(2πft)` et `e(t)cos(2πft)` par moindres carrés 2×2. On en déduit `A=hypot(c_s,c_c)` et `φ=atan2(c_c,c_s)`. Une minimisation scalaire bornée affine f autour du pic spectral. Cette première estimation sépare les pics espacés. Les candidats affinés ci-dessous permettent ensuite plusieurs composantes voisines par pic.

## Modes proches et attaque

Chaque groupe est démodulé en complexe : `z(t) ≈ LP[2 x(t) exp(−j 2π f_c(t−t₀))]`. Le rééchantillonnage polyphasé réduit la trajectoire à environ 200 Hz avec filtrage antirepliement. On ajuste une somme de bases amorties complexes. Pour chaque essai de fréquences et constantes τ, les coefficients complexes sont résolus par moindres carrés ; les paramètres non linéaires utilisent des moindres carrés bornés.

Trois profils sont comparés : 1 à 3 modes voisins avec pénalité locale 0,006 par mode ; en recherche détaillée, 1 à 5 modes avec pénalité 0,0005 et 1 à 3 modes avec isolement Butterworth à 12 Hz autour de la porteuse. Dans ce dernier cas, **le même filtre est appliqué aux observations et aux bases du modèle** pendant l’ajustement. Ce filtrage sert seulement à l’analyse : le graphe final reste une somme d’oscillateurs explicites. L’écart fréquentiel est borné à ±min(5 Hz, max(0,5 Hz, 0,012 f_c)), τ à 15 ms–30 s. On rejette les groupes de SSE relative ≥0,35 et les solutions comportant une amplitude >4. La taille est limitée par le budget mémoire et 128 blocs par patch. Les profils et les anciens candidats sont ensuite comparés avec le même coût global.

Pour chaque candidat affiné, une recherche commune du début (décalages −5, −2, 0, +2, +5, +10 ms) et de la constante d’attaque (0,5 à 40 ms, plus la valeur initiale) conserve aussi la réponse libre. Un déplacement `Δ` du début transforme `A → A exp(−Δ/τ)` et `φ → φ+2πfΔ` ; ainsi le changement concerne la mise en vibration, sans déplacer artificiellement la phase de toute la décroissance. Les essais utilisent un tampon de calcul temporaire. Le JSON ne conserve que les paramètres des oscillateurs.

Une branche d’impact optionnelle ajoute un **bruit blanc gaussien de graine 42**, passe-haut à 80 Hz, passe-bas à 800/2 500/7 000/14 000 Hz, puis enveloppe exponentielle de montée 0,7 ms et de constante 8/25/70/150 ms. Son début vaut le début détecté moins 2 ms, borné à zéro. Son amplitude est mise à l’échelle du résidu des 120 premières millisecondes et testée à 25/50/75/100 %. On compare le graphe complet, pas seulement le résidu. La branche est conservée si le classement erreur + complexité la justifie. Elle représente une composante transitoire bruitée ; elle n’identifie pas une collision marteau-corde unique, ni la réalisation aléatoire exacte du bruit original.

## Inharmonicité

L’ajustement utilise `f_n = n f₀ √(1+B n²)` avec `0 ≤ B ≤ 0,01`, sur des pics proches d’une série harmonique (écart relatif initial < 4 %). Il exige au moins quatre indices harmoniques distincts. Le résultat n’est publié que si :

- `B > 10⁻⁷` ;
- la RMSE est inférieure à `max(1 Hz, 0,005 f₀)` ;
- la RMSE du modèle parfaitement harmonique est supérieure à 1,5 fois celle du modèle inharmonique.

Le rapport expose le nombre de pics et les deux erreurs. Il n’affiche pas de « confiance ». La fondamentale idéale ajustée est distincte du premier partiel mesuré. Les oscillateurs du graphe gardent les fréquences mesurées : B est actuellement descriptif, pas un paramètre global de corde qui force ces fréquences.

## Filtres et discrétisation

Le prototype de second ordre possède le dénominateur :

```text
D(s) = s² + (Ω/Q)s + Ω².
```

Numérateurs : passe-bas `Ω²`, passe-haut `s²`, passe-bande `(Ω/Q)s`, notch `s²+Ω²`. Pour préserver la fréquence caractéristique numérique fc :

```text
Ω = 2 fs tan(π fc/fs)
s = 2 fs (1−z⁻¹)/(1+z⁻¹).
```

Les coefficients b et a calculés par `scipy.signal.bilinear` sont utilisés **à la fois** dans `lfilter` et `freqz`. La formule H(s) décrit le prototype pré-gauchi, et non une prétendue réponse analogique identique à toutes les fréquences. fc doit être strictement inférieure à Nyquist. Q > 0.

```text
H(z) = (b₀+b₁z⁻¹+b₂z⁻²)/(1+a₁z⁻¹+a₂z⁻²).
```

Les pôles et zéros sont les racines des polynômes en z après mise au même degré ; la stabilité causale impose |pôle| < 1. Le diagramme de Bode évalue `H(exp(j2πf/fs))`, amplitude en dB et phase déroulée en degrés. Un zéro exact est plafonné à −240 dB pour le tracé. Le gain DC est calculé à f=0. À Q=1/√2, un passe-bas vaut −3,0103 dB à fc.

Le résonateur discret utilise `r=exp(−1/(fsτ))` et `θ=2πf/fs` :

```text
H(z)=(1−r)/(1−2r cos(θ)z⁻¹+r²z⁻²).
```

Son gain à la résonance n’est pas normalisé. Le délai vaut `H(z)=z⁻ᴺ`, `N=round(fs T)` : la durée effective est donc N/fs.

## Graphe et Bode global

Le moteur valide un graphe orienté sans cycle, calcule un ordre topologique puis applique le traitement de chaque ancêtre de la sortie. Les tampons inutiles sont libérés dès que leurs derniers consommateurs ont été calculés. Une erreur de connexion empêche le rendu ; aucun son ancien n’est présenté comme un nouveau rendu valide.

Le transfert global se définit entre une source injectée et la sortie. Cette source vaut 1 dans le domaine fréquentiel et les autres sources valent 0. Les sommateurs additionnent les transferts des branches ; les blocs SISO multiplient leur transfert par celui de leur entrée. Cela représente correctement les chemins parallèles et les cascades du DAG LTI.

Une enveloppe est linéaire mais **variable dans le temps**. Le produit de deux signaux et tanh sont non linéaires. Aucun Bode LTI n’est affiché pour ces opérateurs ni pour un réseau actif qui les contient. Un oscillateur autonome n’est pas présenté comme un filtre à fonction de transfert.

## Erreurs et choix des candidats

Pour des signaux alignés sur la même sélection, au même fs, sans ajustement de niveau caché :

```text
E_time = ||x−y||₂ / max(||x||₂, ε)
E_spectral = || |FFT(x)|−|FFT(y)| ||₂ / max(|| |FFT(x)| ||₂, ε)
E_STFT = || |STFT(x)|−|STFT(y)| ||_F / max(|| |STFT(x)| ||_F, ε)
E_envelope = || RMS(x)−RMS(y) ||₂ / max(||RMS(x)||₂, ε)
E_attack = moyenne des erreurs relatives de modules STFT sur l’attaque, fenêtres 256 et 1 024
E = (α E_time + β E_spectral + γ E_STFT + δ E_envelope + η E_attack)/(α+β+γ+δ+η)
```

L’attaque est évaluée de 5 ms avant le début détecté à 120 ms après, tronquée aux limites de la sélection. Les poids par défaut sont `(0,1 ; 0,25 ; 0,5 ; 0,15 ; 0,25)` pour temps, spectre, STFT, enveloppe et attaque.

`ε=10⁻¹²`. Les poids sont positifs ou nuls, et leur somme doit être strictement positive. La STFT du coût utilise 1 024 points et au plus environ 160 trames. Le coût n’est pas un score perceptuel, et peut dépasser 1. Les phases affectent E_time davantage que les coûts de module.

Candidats : 1 mode, jusqu’à 4 modes, le nombre maximal de modes détectés, le candidat complet avec un passe-bas à 2 ou 6 kHz (si compatible avec Nyquist), et un bruit blanc filtré/enveloppé ; les profils affinés et les variantes avec attaque ajustée décrits plus haut ; enfin une variante avec impact sur le meilleur candidat tonal. Les modes sont sélectionnés par l’indicateur `A²τ`. Le candidat bruit initialise fc à deux fois le centroïde énergétique avec bornage ; c’est une heuristique évaluée, pas un filtre prétendument identifié.

```text
complexité = nombre de blocs + 0,25 × nombre de paramètres explicites
score = E + λ × complexité
```

Les familles et heuristiques sont finies et déclarées. Le choix est automatique mais n’explore pas toutes les topologies possibles. L’utilisateur peut choisir un autre candidat que le premier.

## Optimisation et reproductibilité

Les méthodes disponibles passent par une même fonction objectif et le même moteur de graphe. Les paramètres cochés sont variables ; à défaut, douze paramètres sont utilisés au maximum : d’abord le gain et la branche d’impact, puis amplitudes et constantes τ des modes dans l’ordre du graphe. L’utilisateur peut cocher d’autres variables pour cibler le résidu. Les paramètres strictement positifs sont explorés dans `[0,5v ; 2v]` intersecté avec leurs bornes physiques ; les autres utilisent les bornes du registre. Les variables sont ramenées à [0,1]. Les graines de bruit ne sont pas optimisées.

Le budget total est `min(400, 12 × nombre d’itérations demandé + 1)` évaluations. Le nombre d’itérations est également passé à l’optimiseur. La courbe représente le meilleur coût conservé après chaque **évaluation**, pas un faux compteur d’itérations. On peut arrêter le calcul, et le meilleur modèle est toujours gardé. Convergence, arrêt et budget épuisé sont distingués.

Pour reproduire : conserver le `.monpatch`, le WAV original, la sélection, les poids et les versions des dépendances. Le rapport les rassemble (le WAV lui-même doit être conservé séparément). Le bruit a une graine fixe. Le JSON exporte fs, durée, tous les paramètres effectifs (y compris les défauts) et connexions ; aucun fragment du WAV n’est caché dans un bloc.

## Références techniques

- [SciPy — traitement du signal](https://docs.scipy.org/doc/scipy/reference/signal.html)
- [SciPy — transformation bilinéaire](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.bilinear.html)
- [SciPy — optimisation](https://docs.scipy.org/doc/scipy/reference/optimize.html)
- [React Flow — éditeur de graphes](https://reactflow.dev/learn)
- [FastAPI — serveur local](https://fastapi.tiangolo.com/)
- [CircuitJS — référence ergonomique du projet](https://www.falstad.com/circuit/circuitjs.html)

## Modèle compact à budget d’erreur

La simplification est une étape optionnelle après identification/optimisation. Elle garde le patch d’entrée intact et recherche le moins de blocs sous la contrainte `J(candidat) ≤ (1 + tolérance) J(référence) + 10⁻¹²`. Le budget vaut 20 % par défaut, réglable à 0 pour refuser une hausse de coût. Ce pourcentage porte sur le critère numérique, pas sur une distance perceptive calibrée.

Chaque mode fournit deux colonnes, sinus et cosinus, multipliées par son enveloppe. Une sélection gloutonne par groupes de deux colonnes maximise la diminution de l’erreur quadratique après réajustement conjoint des coefficients. Les budgets évalués sont 1, 2, 3, 4, 6, 8, 10, 12 et 16 modes (bornés par le nombre initial). Fréquences (±3 Hz), amplitudes, phases et décroissances sont ensuite réajustées ensemble ; l’attaque est recalibrée. L’analyse utilise si possible un sous-échantillonnage polyphasé, avec marge par rapport au mode le plus élevé. **Toutes les décisions finales utilisent le rendu complet à la fréquence originale et les mêmes poids de coût.**

Quelques budgets testent en plus une saturation tanh, un passe-bas et un gain réels, ainsi qu’une branche d’impact si le patch initial en possède une. Ils sont représentés par des blocs ordinaires exportables, sans onde enregistrée ni banque de modes cachée. Gains unité, sommes à entrée unique et modes strictement identiques alimentant la même somme peuvent être éliminés/fusionnés. L’utilité affichée est `J(source coupée) − J(candidat retenu)`, sans réajustement ; elle peut être négative en présence d’interférences. Elle n’est pas une probabilité.

Limites : recherche heuristique, jusqu’à 16 modes sélectionnés, début/attaque communs requis, sélection de 12 s maximum, matrice d’analyse plafonnée à 8 millions de coefficients. Le modèle initial reste candidat, même lorsqu’aucune réduction ne respecte le budget. La saturation n’est pas suréchantillonnée. Le coût pondéré peut masquer une dégradation d’une composante ; l’interface conserve donc les erreurs séparées et l’écoute A/B.

## Recherche globale inspirée du patch VCV (2 octobre 2026)

Le patch fourni `TIPE_piano_v8_cible_wav_hautes_freq.vcv` a été lu sans modification. Il contient neuf sources Bogaudio Sine, leurs VCA, une enveloppe commune, une branche de bruit avec enveloppe propre, deux groupes de mixage, un passe-bas MUS-X du premier ordre et un MUS-X configuré « Diode Clipper (Symmetric) », suréchantillonnage ×4. Ces données inspirent la topologie ; le DSP ajouté n’est pas une émulation exacte de MUS-X ni une conversion automatique du patch VCV.

Trois nouveaux blocs exécutables, éditables et exportables :

- **Saturation asymétrique ×4** : `g [(1−m)x + m(tanh(dx+b)−tanh(b))]`. Les paramètres sont drive, asymétrie, mélange et niveau. Interpolation et décimation polyphasées ×4 ; aucune source interne. L’entrée nulle donne une sortie nulle. L’asymétrie crée notamment des harmoniques paires ; un passe-haut peut contrôler la composante continue induite par un signal non nul. Le suréchantillonnage réduit le repliement sans prétendre le supprimer totalement.
- **Égaliseur paramétrique** : biquad obtenu par transformation bilinéaire pré-gauchie de `(s²+AΩs/Q+Ω²)/(s²+Ωs/(AQ)+Ω²)`, `A=10^(G/40)`. Gain G dB à fc, gain unité aux extrémités. Bode et rendu partagent les mêmes coefficients.
- **Passe-bas 6 dB/oct** : `Ω/(s+Ω)` avec pré-gauchissement, filtre de premier ordre.

Pour les budgets de 1, 2, 3 et 4 sources, la recherche compare saturation → passe-bas ; saturation → passe-haut → égaliseur → passe-bas ; et préfiltrage → saturation → égaliseur → passe-bas. Avec 6 et 8 sources, elle teste une branche parallèle réutilisant une source existante, puis saturation, passe-haut et passe-bas, ajoutée au signal direct. Ainsi, 14 topologies sont proposées lorsque le modèle initial fournit tous ces budgets.

Fréquences (±2 Hz), phases, amplitudes et décroissances des sources sont réajustées **avec** drive, asymétrie, niveau, coupures, Q et gain d’égalisation. Une grille initiale de drives/asymétries précède une recherche Powell bornée à 220 évaluations supplémentaires par topologie. Le mélange est fixé à 1 pendant cette recherche mais reste éditable manuellement. Les buffers d’analyse peuvent être réduits jusqu’à un facteur 4, avec marge par rapport aux sources ; la génération d’harmoniques au-delà de leur bande est une limite de cette proposition approchée. Le candidat initial et le candidat ajusté sont tous deux réévalués au taux original : seul le meilleur entre eux rejoint les comparaisons finales. Le choix global reste soumis au budget d’erreur initial.

Cette recherche est heuristique : un résultat défavorable ne démontre pas l’impossibilité de synthétiser le son autrement. Le nombre de blocs n’est pas une mesure exacte du temps CPU, notamment pour la saturation ×4. La garde de charge de rendu compte cette dernière avec un poids de 8. L’utilité des traitements à une entrée est mesurée en les contournant ; celle des sources en les coupant, sans réajuster le reste.
