# Rémi, guide de découverte

Petit personnage SVG local, sans dépendance externe, voix automatique ni appel IA.
Après chargement du compte, la première visite de ce navigateur ouvre une fenêtre
de découverte. La fermeture mémorise un indicateur local par identifiant de compte
(`resonant-guide-v1:<id>`), sans mot de passe ni clé. Le bouton « Help · Guide »
reste accessible dans l'en-tête pour reprendre la visite depuis le début. Si le
stockage navigateur est bloqué, la visite reste utilisable et peut réapparaître.

Six étapes : accueil, référence WAV, analyse/génération, modules et câbles,
écoute/optimisation/simplification, calcul local/serveur et clavier. Un deuxième
onglet présente les 21 modules du catalogue réel. L'inspecteur propose également
« En mots simples » pour le module sélectionné. Les textes distinguent bruit,
saturation, filtre et enveloppe ; ils ne promettent ni copie parfaite ni piano
universel à partir d'une seule note.

La fenêtre utilise un dialogue natif : arrière-plan inactif, focus contenu, fermeture
par Échap, bouton de fermeture explicite et retour du focus au bouton Help.
Présentation adaptée aux petits écrans, sans animation du personnage.

Validation exécutée : TypeScript/Vite réussis ; 24 tests frontend réussis ; concordance
des 21 types du catalogue et des explications vérifiée. Dans le navigateur intégré,
sur base temporaire et compte fictif : ouverture automatique, navigation jusqu'à
l'étape 6, onglet modules et explication bruit blanc, fermeture Échap et focus Help,
réouverture du guide. Capture `guide-remi.png`. Aucun test sur appareil mobile physique.
Serveur de test arrêté après validation ; aucune modification des comptes existants.
