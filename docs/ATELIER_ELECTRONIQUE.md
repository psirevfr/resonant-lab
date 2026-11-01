# Atelier électronique — montage 3D et firmware Arduino

L’atelier affiche le circuit dans une scène WebGL orbitale : glisser fait tourner
la caméra, le clic droit la déplace et la molette zoome. Les cartes, prises,
breadboard et câbles sont modélisés localement avec des géométries 3D. Les
dimensions restent illustratives ; le brochage et les fiches constructeur
doivent guider la construction réelle.

## Architecture minimale retenue

Deux cartes actives seulement :

- Teensy 4.1 : reçoit le clavier MIDI USB Host et calcule la banque de
  sinusoïdes dans le sketch Arduino.
- Teensy Audio Shield Rev D ou D2 : se monte sur une Teensy 4.0/4.1. Son codec
  SGTL5000 réunit conversion audio, sortie casque 3,5 mm et sorties analogiques
  de niveau ligne. Il remplace le DAC séparé et le breakout jack.

Le reste est constitué du clavier MIDI, de la platine sans soudure, des
connexions USB et Dupont et d’un câble audio. Le shield emploie les connexions
internes empilées : DIN 7, BCLK 21, LRCLK 20, MCLK 23 et commande I²C sur SDA/SCL
18/19. Il n’y a pas de faisceau I²S volant entre deux cartes.

Sources fabricant : [Audio Shield Rev D/D2, compatibilité et brochage PJRC](https://www.pjrc.com/store/teensy3_audio.html),
[AudioControlSGTL5000](https://www.pjrc.com/teensy/gui/?info=AudioControlSGTL5000),
[Teensy 4.1](https://www.pjrc.com/store/teensy41.html),
[USB MIDI Host](https://www.pjrc.com/teensy/td_midi.html).

## Firmware généré

`frontend/src/firmware/teensySketch.ts` produit un sketch adapté aux modes
analysés : fréquence, amplitude, phase, décroissance, attaque et note MIDI de
référence. Il additionne les partiels dans le code et pilote le SGTL5000 via
`AudioControlSGTL5000`. Le premier volume casque est volontairement modéré.

La sortie de l’Audio Library est en 16 bits/44,1 kHz. Le code utilise jusqu’à
24 modes et 8 voix. Il ne reproduit pas encore tout le patch : bruit d’impact,
filtres, saturation, délai et inharmonicité propre à chaque note restent à
porter et à mesurer.

## Limites et vérifications matérielles

- Le sketch n’a pas été compilé avec Arduino IDE/Teensyduino ni testé sur une
  carte physique. Le code reste un prototype.
- Utiliser explicitement l’Audio Shield **Rev D ou D2** pour Teensy 4.x, pas la
  Rev C prévue pour Teensy 3.x.
- L’entrée USB Host de la Teensy 4.1 requiert le câble et le brochage des pads
  Host indiqués par PJRC. Elle est distincte du micro-USB de programmation.
- La prise casque de l’Audio Shield est amplifiée : commencer bas et ajuster le
  niveau avant de la brancher sur une entrée ligne. Les broches Line-Out sont
  une autre sortie, disponible sur le shield.
- La Teensy 4.1 n’accepte pas 5 V sur ses broches logiques. Ne jamais raccorder
  le secteur ou une sortie d’amplificateur à la breadboard.
- La scène 3D aide à comprendre l’agencement ; elle n’est pas un modèle CAO
  certifié et ne vérifie pas les collisions ni les tolérances mécaniques.
