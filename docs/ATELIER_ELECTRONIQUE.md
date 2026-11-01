# Atelier électronique — code Arduino et maquette matérielle

L’onglet **Montage physique** reprend une organisation d’atelier matériel :
palette de composants, vues circuit 3D et schéma, panneau de résultats, puis vue
du sketch Arduino. Le patch et l’analyse alimentent le plan. Cette interface est
un outil Resonant Lab; elle n’embarque pas l’application tierce Tinkered.

## Cible matérielle minimale

- Teensy 4.1 programmée avec Arduino IDE et Teensyduino : calcul de la banque de
  sinusoïdes et hôte USB MIDI.
- Un breakout DAC I²S PCM5102A : conversion numérique vers sortie ligne.
- Les connexions passives, breadboard et câbles adaptés.

Le nombre de partiels ne devient pas un nombre de générateurs physiques : le
sketch additionne jusqu’à 24 sinusoïdes à l’intérieur du microcontrôleur. Le
clavier USB MIDI se branche au port USB Host de la Teensy. Le câble USB de
programmation est distinct.

## Génération du sketch

`frontend/src/firmware/teensySketch.ts` construit un sketch `.ino` à partir des
résultats disponibles : fréquence, amplitude, phase, décroissance par partiel,
attaque, note MIDI de référence et paramètres du patch. Sans résultat d’analyse,
il utilise les oscillateurs directement présents dans le patch. L’export est
soumis à la connexion au compte, comme les autres téléchargements.

Le sketch d’illustration utilise une banque additive, une table sinus, jusqu’à
8 voix MIDI, l’audio de la bibliothèque PJRC à 44,1 kHz/16 bits et une sortie
I²S vers le DAC. Le câble I²S de Teensy 4.x utilise BCLK 21, LRCLK 20 et TX 7.
Références : [Teensy 4.1](https://www.pjrc.com/store/teensy41.html),
[MIDI USB Host](https://www.pjrc.com/teensy/td_midi.html),
[bibliothèque Audio PJRC](https://www.pjrc.com/teensy/td_libs_Audio.html),
[PCM5102A](https://www.ti.com/product/PCM5102A).

## Limites actuelles — ne pas considérer le montage prêt à construire

- Le sketch n’a pas été compilé avec Arduino CLI/Teensyduino ni testé sur une
  carte physique.
- Le moteur audio courant de Resonant Lab n’a pas encore été entièrement porté.
  Le sketch ne traduit pas encore le bruit d’impact, les filtres, les
  saturations, les délais et les autres traitements. Il reproduit une banque de
  modes sinusoïdaux mesurés, pas nécessairement tout le son.
- La transposition applique un rapport tempéré identique à chaque partiel.
  L’inharmonicité et les évolutions du spectre note par note ne sont donc pas
  identifiées.
- Le relâchement MIDI utilise 200 ms par défaut si le patch n’a pas de paramètre
  ADSR adapté. Il n’est pas estimé par l’analyse acoustique actuelle.
- La Teensy Audio Library actuelle sort en 16 bits/44,1 kHz. Ce résultat n’est
  pas une copie numérique du moteur navigateur Float64 et n’est pas validé comme
  équivalent.
- Les dessins de câblage sont conceptuels. Vérifier le breakout, les broches,
  les tensions et l’alimentation réelle avant toute connexion.

## Passage vers Tinkered

L’atelier peut télécharger le sketch Arduino et un brief texte contenant les
mesures et contraintes matérielles. Tinkered documente l’import d’un firmware
existant, mais aucune API publique d’intégration ou d’import automatisé n’a été
identifiée. Le bouton ouvre le service externe sans lui transmettre de données;
l’utilisateur choisit ensuite de lui fournir le sketch et le brief.

## Sécurité électrique

La Teensy 4.1 n’accepte pas 5 V sur ses broches logiques. Le plan utilise une
alimentation USB basse tension; ne jamais raccorder le secteur ni une sortie
d’amplificateur à la breadboard. Si le clavier consomme trop, utiliser un hub
USB alimenté et vérifier les règles de masse avant branchement.
