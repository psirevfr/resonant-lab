import type {Patch} from './types';
export type Kind='resistor'|'capacitor'|'voltage'|'ground'|'breadboard'|'led'|'uno';
export type Pin={component:string;pin:string};
export type Part={id:string;type:Kind;label:string;value:number;x:number;y:number;px:number;z:number;rotation:number};
export type CircuitProject={version:1;id:string;name:string;revision:number;parts:Part[];wires:{id:string;from:Pin;to:Pin}[];code:string;source?:{patch:Patch;signature:string;limitations:string[]}};
const baseDefinitions:Record<Kind,{name:string;category:string;pins:string[];value:number;unit:string;status:string;limit:string}>={
 resistor:{name:'Résistance',category:'Passifs',pins:['1','2'],value:1000,unit:'Ω',status:'simulé',limit:'Résistance idéale, 1 Ω à 10 MΩ.'},
 capacitor:{name:'Condensateur',category:'Passifs',pins:['1','2'],value:1e-6,unit:'F',status:'simulé',limit:'Condensateur idéal, 1 pF à 1 mF.'},
 voltage:{name:'Alimentation',category:'Sources',pins:['+','-'],value:5,unit:'V',status:'simulé',limit:'Source idéale DC ou échelon 0→V, ±24 V.'},
 ground:{name:'Masse',category:'Sources',pins:['0'],value:0,unit:'',status:'simulé',limit:'Référence électrique commune 0 V.'},
 breadboard:{name:'Breadboard · 10 colonnes',category:'Supports',pins:[],value:0,unit:'',status:'connectivité',limit:'A–E et F–J isolés au centre ; quatre rails continus de 10 contacts. Modèle pédagogique, pas une référence 830 points.'},
 led:{name:'LED rouge',category:'Semi-conducteurs',pins:['A','K'],value:0,unit:'',status:'modèle simplifié',limit:'Diode ngspice IS=1e-20, N=2, RS=10 Ω. Aucun modèle thermique ou photométrique.'},
 uno:{name:'Arduino Uno',category:'Cartes',pins:['5V','GND','D13','D2','A0'],value:0,unit:'',status:'visuel uniquement',limit:'Compilation et exécution AVR non intégrées dans cette tranche. Bloque la simulation électrique.'},
};
export const definitions=Object.fromEntries(Object.entries(baseDefinitions).map(([id,d])=>[id,{...d,id,version:1,license:'Résonant : géométrie et symbole originaux',provenance:'Modèles idéaux R/C/V ; LED diode IS=1e-20 N=2 RS=10',engines:['resistor','capacitor','voltage','ground','breadboard','led'].includes(id)?['ngspice-46']:[],model:({resistor:'R',capacitor:'C',voltage:'V',led:'D LED_RED',ground:'node 0',breadboard:'contact groups'} as Record<string,string>)[id]??null}])) as Record<Kind,typeof baseDefinitions[Kind]&{id:string;version:number;license:string;provenance:string;engines:string[];model:string|null}>;
export const boardPins=()=>[...'abcdefghij'].flatMap(row=>Array.from({length:10},(_,i)=>row+(i+1))).concat(['pL','nL','pR','nR'].flatMap(row=>Array.from({length:10},(_,i)=>row+(i+1))));
export const pins=(part:Part)=>part.type==='breadboard'?boardPins():definitions[part.type].pins;
export function pinOffset(part:Part,pin:string):[number,number]{
 if(part.type==='breadboard'){const m=/^([a-j]|pL|nL|pR|nR)(10|[1-9])$/.exec(pin)!;const rows=['pL','nL',...'abcde',...'fghij','pR','nR'];return [(Number(m[2])-5.5)*6,(rows.indexOf(m[1])-6.5)*5+(m[1]>='f'&&m[1]<='j'?3:0)]}
 const list=pins(part),i=list.indexOf(pin);return [(i-(list.length-1)/2)*22,0];
}
export function pinPoint(part:Part,pin:string):[number,number]{const [x,z]=pinOffset(part,pin),angle=part.rotation*Math.PI/180;return [part.px+x*Math.cos(angle)-z*Math.sin(angle),part.z+x*Math.sin(angle)+z*Math.cos(angle)]}
export function contactGroup(pin:string){const m=/^([a-j])(10|[1-9])$/.exec(pin);if(m)return (m[1]<='e'?'upper':'lower')+m[2];const rail=/^(pL|nL|pR|nR)(10|[1-9])$/.exec(pin);return rail?rail[1]:pin}
export function emptyProject():CircuitProject{return {version:1,id:crypto.randomUUID(),name:'Nouveau montage',revision:0,parts:[],wires:[],code:''}}
export function newPart(type:Kind,index:number):Part{return {id:crypto.randomUUID(),type,label:definitions[type].name,value:definitions[type].value,x:100+(index%4)*180,y:100+Math.floor(index/4)*130,px:-60+(index%4)*45,z:Math.floor(index/4)*35,rotation:0}}
export function example(kind:'divider'|'rc'|'led'):CircuitProject{
 const p=emptyProject();p.name=kind==='divider'?'Diviseur de tension':kind==='rc'?'Circuit RC':'LED et résistance';
 const add=(type:Kind,x:number,y:number,value?:number)=>{const a=newPart(type,p.parts.length);Object.assign(a,{x,y,px:x/5-80,z:y/5-35,...(value===undefined?{}:{value})});p.parts.push(a);return a};
 const v=add('voltage',80,180),r=add('resistor',300,100),b=add(kind==='rc'?'capacitor':kind==='led'?'led':'resistor',520,180),g=add('ground',300,320);
 const wire=(a:Part,ap:string,b:Part,bp:string)=>p.wires.push({id:crypto.randomUUID(),from:{component:a.id,pin:ap},to:{component:b.id,pin:bp}});
 wire(v,'+',r,'1');wire(r,'2',b,kind==='led'?'A':'1');wire(b,kind==='led'?'K':'2',g,'0');wire(v,'-',g,'0');return p;
}
export function validateProject(value:unknown):CircuitProject{
 if(!value||typeof value!=='object')throw Error('Projet invalide.');const p=value as CircuitProject;
 if(p.version!==1||typeof p.id!=='string'||p.id.length>80||typeof p.name!=='string'||p.name.length>100||!Number.isInteger(p.revision)||p.revision<0||!Array.isArray(p.parts)||p.parts.length>48||!Array.isArray(p.wires)||p.wires.length>200||typeof p.code!=='string'||p.code.length>100000)throw Error('Format de projet invalide ou limites dépassées.');
 const ids=new Set<string>();for(const part of p.parts){if(!part||typeof part.id!=='string'||part.id.length>80||ids.has(part.id)||!Object.hasOwn(definitions,part.type)||typeof part.label!=='string'||part.label.length>100||![part.value,part.x,part.y,part.px,part.z,part.rotation].every(Number.isFinite)||[part.x,part.y,part.px,part.z].some(v=>Math.abs(v)>10000)||Math.abs(part.rotation)>3600)throw Error('Composant invalide.');ids.add(part.id)}
 const endpoint=(e:Pin)=>p.parts.some(part=>part.id===e?.component&&pins(part).includes(e.pin));const wireIds=new Set<string>();for(const w of p.wires){if(!w||typeof w.id!=='string'||w.id.length>80||wireIds.has(w.id)||!endpoint(w.from)||!endpoint(w.to))throw Error('Connexion invalide.');wireIds.add(w.id)}
 // Construct the accepted shape rather than retaining unknown imported fields.
 const result:CircuitProject={version:1,id:p.id,name:p.name,revision:p.revision,parts:p.parts.map(part=>({id:part.id,type:part.type,label:part.label,value:part.value,x:part.x,y:part.y,px:part.px,z:part.z,rotation:part.rotation})),wires:p.wires.map(w=>({id:w.id,from:{component:w.from.component,pin:w.from.pin},to:{component:w.to.component,pin:w.to.pin}})),code:p.code};
 if(p.source){const patch=p.source.patch;if(!patch||!Array.isArray(patch.nodes)||patch.nodes.length>128||!Array.isArray(patch.edges)||patch.edges.length>512||JSON.stringify(patch).length>500000||typeof patch.name!=='string'||!Number.isFinite(patch.sample_rate)||!Number.isFinite(patch.duration))throw Error('Référence audio invalide.');result.source={patch:structuredClone(patch),signature:JSON.stringify(patch),limitations:['Référence conservée. La traduction électrique et le firmware complet restent à implémenter.']}}
 return result;
}
export function fromPatch(patch:Patch):CircuitProject{const p=emptyProject();p.name=(patch.name+' · proposition').slice(0,100);const a=newPart('uno',0);a.label='Processeur DSP à choisir';p.parts=[a];p.source={patch:structuredClone(patch),signature:JSON.stringify(patch),limitations:['Graphe intégral conservé ('+patch.nodes.length+' blocs). Aucun circuit ou firmware équivalent n’est généré dans cette tranche.','Teensy/codec et traitements DSP nécessitent une traduction dédiée. La carte affichée est un repère visuel.']};return p}
