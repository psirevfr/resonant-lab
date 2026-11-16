export type LabSpace='atelier'|'analyse';
export type GuideStep={space:LabSpace;target:string;title:string;text:string};
export const guideSteps:GuideStep[]=[
 {space:'atelier',target:'components',title:'Ajoutez vos composants',text:'Ouvrez Composants, puis choisissez une pièce. Aucun fichier audio n’est nécessaire.'},
 {space:'atelier',target:'workshop-scene',title:'Construisez votre montage',text:'Placez les pièces et reliez leurs broches. Passez de 2D à 3D pour voir le même montage autrement.'},
 {space:'atelier',target:'simulate',title:'Testez et mesurez',text:'Simuler teste les composants pris en charge. Instruments montre les tensions. Enregistrer garde votre montage sur cet appareil.'},
 {space:'analyse',target:'reference',title:'Partez d’un son',text:'Importez un fichier WAV, puis choisissez la note que vous voulez reproduire.'},
 {space:'analyse',target:'generate',title:'Recréez le son',text:'Générer cherche un modèle. Optimiser affine ses réglages ; Simplifier cherche à utiliser moins de modules.'},
 {space:'analyse',target:'graph',title:'Ajustez le modèle',text:'Les câbles montrent le chemin du son. Cliquez sur un module pour le régler. Pour retirer un câble, sélectionnez-le puis appuyez sur Suppr.'},
 {space:'analyse',target:'player',title:'Écoutez et comparez',text:'Écoutez l’original puis le modèle pour comparer le résultat.'},
 {space:'analyse',target:'export',title:'Gardez votre résultat',text:'Exporter enregistre le son ou le modèle. Un compte est nécessaire pour télécharger.'},
 {space:'analyse',target:'create-circuit',title:'Passez au montage',text:'Créer un montage envoie le modèle vers l’atelier. Les éléments à adapter au matériel y sont indiqués.'}
];
