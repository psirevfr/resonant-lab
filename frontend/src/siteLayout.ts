import {createContext,useContext} from 'react';
import source from './siteLayout.json';

export const blockLibrary={
 inventory:'Inventaire audio',compact:'Résultats de simplification',status:'État du rendu',metrics:'Mesures de fidélité',transfer:'Transfert du réseau',
 knobs:'Potentiomètres',reference:'Importer et analyser',graph:'Câblage libre',player:'Lecteur audio',keyboard:'Piano MIDI',
 signals:'Graphiques du signal',settings:'Réglages audio',hardware:'Plan de montage',workshop:'Atelier électronique',
 text:'Texte',image:'Image',link:'Bouton de direction',
};
export type BlockKind=keyof typeof blockLibrary;
export type ElementStyle={text?:string;color?:string;background?:string};
export type LayoutBlock=ElementStyle&{id:string;kind:BlockKind;x:number;y:number;w:number;h:number;target?:string};
export type LayoutPage={id:string;name:string;parent:string|null;custom?:boolean;blocks:LayoutBlock[]};
export type PlotStyle={title?:string;x?:string;xUnit?:string;y?:string;yUnit?:string;y2?:string;y2Unit?:string;legend?:boolean;color?:string;traces?:{name?:string;color?:string}[]};
export type SiteLayout={version:1;pages:LayoutPage[];bank:LayoutBlock[];plots:Record<string,PlotStyle>;elements?:Record<string,ElementStyle>};
export const siteLayout=source as SiteLayout;
export const LayoutContext=createContext<SiteLayout>(siteLayout);
export const useSiteLayout=()=>useContext(LayoutContext);
export function pagePath(id:string){return id==='analyse'||id==='atelier'?'/'+id:'/p/'+id}
export function layoutPage(path:string,layout:SiteLayout){return layout.pages.find(page=>pagePath(page.id)===path.replace(/\/$/,''))}
