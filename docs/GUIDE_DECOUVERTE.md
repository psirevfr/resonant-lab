# Rémi, guide de découverte

Petit personnage SVG local, sans dépendance externe, voix automatique ni appel IA.
Après chargement du compte, la première visite de ce navigateur ouvre une fenêtre
de découverte. La fermeture mémorise un indicateur local par identifiant de compte
(`resonant-guide-v2:<id>`), sans mot de passe ni clé. Le bouton « Help · Guide »
reste accessible dans l'en-tête pour reprendre la visite depuis le début. Si le
stockage navigateur est bloqué, la visite reste utilisable et peut réapparaître.

Une fenêtre d'introduction précède une visite interactive en six étapes sur la vraie
interface : référence, génération, rack, inspecteur, lecture et export. Un deuxième
onglet présente les 21 modules du catalogue réel. L'inspecteur propose également
« En mots simples » pour le module sélectionné. Les textes distinguent bruit,
saturation, filtre et enveloppe ; ils ne promettent ni copie parfaite ni piano
universel à partir d'une seule note.

La fenêtre d'introduction utilise un dialogue natif : arrière-plan inactif, focus contenu, fermeture
par Échap, bouton de fermeture explicite et retour du focus au bouton Help.
Présentation adaptée aux petits écrans, sans animation du personnage.

Validation exécutée : TypeScript/Vite réussis ; 24 tests frontend réussis ; concordance
des 21 types du catalogue et des explications vérifiée. Dans le navigateur intégré,
sur base temporaire et compte fictif : ouverture automatique, navigation jusqu'à
l'étape 6, onglet modules et explication bruit blanc, fermeture Échap et focus Help,
réouverture du guide. Capture `guide-remi.png`. Aucun test sur appareil mobile physique.
Serveur de test arrêté après validation ; aucune modification des comptes existants.

## Visite interactive

Rémi se place près de la zone expliquée ; le reste de l'écran est assombri et la
zone cadrée reste utilisable. Cadrage déclenché seulement par la visite, jamais par
un survol, sans changer le zoom du navigateur. La position se recalcule au défilement
et au redimensionnement ; les observateurs et événements sont nettoyés à la sortie.

L'utilisateur peut charger une note synthétique puis lancer une vraie génération
locale de 0,25 s, trois partiels, sans affinement détaillé. Ces paramètres sont ceux
de l'exercice, explicitement annoncés, et ne modifient pas la qualité du modèle de
l'utilisateur. Aucun calcul serveur en file ni repli automatique : si le runtime
local manque, le guide affiche l'erreur et permet de poursuivre sans calcul.
Le chargement de la note utilise l'API de démonstration existante ; la génération
utilise le moteur Pyodide existant. Pas de lecture automatique.

Le montage et la référence ouverts sont mémorisés en RAM dès l'entrée dans la visite,
même si l'exemple est passé. Une sortie anticipée ou normale restaure les réglages,
le mode de calcul et les résultats précédents. Le guide demande d'attendre ou
d'annuler la démonstration avant de quitter pendant un calcul. Cette protection
est limitée à l'onglet vivant : fermer/recharger l'onglet pendant l'exercice perd
le snapshot RAM ; elle ne remplace pas un enregistrement de projet.

Validation navigateur local sur compte fictif : génération réelle, neuf modules
observés ; modification d'amplitude ; progression jusqu'à l'export ; restauration
du montage initial de six modules et de l'absence de référence. Parcours sans
exemple : modification du filtre 3500 → 3000 Hz puis sortie anticipée, retour vérifié
à 3500 Hz. Aucun log d'erreur JavaScript dans ces parcours. Capture
`guide-interactif.png`. TypeScript/Vite et les 24 tests frontend réexécutés.
Annulation de la génération locale et restauration ensuite vérifiées. Le cadrage
retrouve le rack quand l’onglet Analyse était initialement affiché.
Pas de test physique mobile ni de démonstration sur la production.
