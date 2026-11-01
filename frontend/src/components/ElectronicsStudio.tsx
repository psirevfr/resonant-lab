import {useMemo,useState} from 'react';
import {Activity,AlertTriangle,AudioWaveform,Box,Cable,Check,ChevronDown,Clipboard,Code2,Component,Cpu,Download,ExternalLink,FileCode2,Info,Minus,Plus,RotateCcw,Search,Usb,Volume2} from 'lucide-react';
import type {Analysis,Patch} from '../types';
import {buildTeensySketch} from '../firmware/teensySketch';

type PartId='midi'|'teensy'|'dac'|'jack'|'line-cable'|'breadboard'|'wires'|'usb-host'|'usb-data';
type StudioView='circuit'|'schematic'|'firmware';
type HardwarePart={id:PartId;category:string;qty:string;name:string;role:string;detail:string;link?:string};

const hardwareParts:HardwarePart[]=[
 {id:'teensy',category:'Calculateur',qty:'1',name:'Teensy 4.1 · Arduino IDE',role:'Génère et additionne les sinusoïdes en logiciel.',detail:'Microcontrôleur programmable avec Arduino IDE et Teensyduino. Le DSP du patch tourne dans le code; aucun module analogique par partiel.',link:'https://www.pjrc.com/store/teensy41.html'},
 {id:'midi',category:'Entrée MIDI',qty:'1',name:'Clavier MIDI USB class-compliant',role:'Envoie les notes et vélocités au port USB Host.',detail:'Connexion directe au port USB Host de la Teensy. En cas de courant insuffisant, utiliser un hub USB alimenté.',link:'https://www.pjrc.com/teensy/td_midi.html'},
 {id:'usb-host',category:'Entrée MIDI',qty:'1',name:'Câble USB Host pour Teensy',role:'Relie la prise USB-A femelle aux pastilles Host.',detail:'Câblage distinct du câble USB de programmation. Isoler correctement les conducteurs et vérifier le brochage PJRC.',link:'https://www.pjrc.com/store/cable_usb_host_t36.html'},
 {id:'dac',category:'Sortie audio',qty:'1',name:'Breakout DAC PCM5102A · I²S',role:'Convertit l’audio numérique en sortie ligne.',detail:'Choisir un breakout documenté compatible avec les niveaux logiques 3,3 V de la Teensy.',link:'https://www.ti.com/product/PCM5102A'},
 {id:'jack',category:'Sortie audio',qty:'1',name:'Breakout jack 3,5 mm · L/R/GND',role:'Raccorde la sortie ligne à un équipement audio.',detail:'La sortie vise une entrée ligne. Elle ne remplace pas un amplificateur casque ou haut-parleur.'},
 {id:'breadboard',category:'Support',qty:'1',name:'Breadboard sans soudure · 830 points',role:'Supporte le DAC et les connexions temporaires.',detail:'La Teensy 4.1 est une grande carte; vérifier son support mécanique et les rails d’alimentation avant placement.'},
 {id:'wires',category:'Support',qty:'1 jeu',name:'Fils Dupont mâle-mâle',role:'Relient alimentation, I²S, masse et jack.',detail:'Les broches 21/20/7 transportent l’I²S; relier une masse commune. Longueur courte conseillée.'},
 {id:'usb-data',category:'Programmation',qty:'1',name:'Câble micro-USB de données',role:'Téléverse le sketch depuis l’ordinateur.',detail:'Le câble de programmation USB est différent de l’entrée clavier branchée sur le port USB Host.'},
 {id:'line-cable',category:'Sortie audio',qty:'1',name:'Câble audio vers entrée ligne',role:'Relie le jack à une entrée ligne externe.',detail:'Ne pas connecter directement une sortie d’amplificateur ou une alimentation secteur.'}
];

const dspTypes=new Set(['oscillator','modal','noise','input','impulse','sum','multiply','gain','output','envelope','adsr','saturation','asymmetric_saturation','delay','lowpass','highpass','bandpass','notch','peak_eq','lowpass1','resonator']);
const dspNames:Record<string,string>={oscillator:'Sinusoïdes',modal:'Modes modaux',noise:'Bruit',input:'Entrée',impulse:'Impact',sum:'Somme',multiply:'VCA',gain:'Gain',output:'Sortie',envelope:'Enveloppe',adsr:'ADSR',saturation:'Saturation',asymmetric_saturation:'Saturation suréchantillonnée',delay:'Délai',lowpass:'Passe-bas',highpass:'Passe-haut',bandpass:'Passe-bande',notch:'Coupe-bande',peak_eq:'Égaliseur',lowpass1:'Passe-bas simple',resonator:'Résonateur'};
const boardPoint=(col:number,row:number)=>({x:145+col*7.5+row*10,y:207-col*1.2+row*8.8});

function CircuitDrawing({zoom,selected,wiring,onSelect}:{zoom:number;selected:PartId;wiring:boolean;onSelect:(id:PartId)=>void}){
 const holes=useMemo(()=>{
  const rows=[0,1,2,3,4,7,8,9,10,11];
  const terminal=rows.flatMap(row=>Array.from({length:63},(_,col)=>({...boardPoint(col,row),rail:''})));
  const rails=Array.from({length:200},(_,i)=>{const group=Math.floor(i/50),col=i%50+6.5,row=group<2?group-1:12+group-2;return {...boardPoint(col,row),rail:group%2===0?'positive':'negative'}});
  return [...terminal,...rails];
 },[]);
 const select=(id:PartId)=>({onClick:()=>onSelect(id),onKeyDown:(e:React.KeyboardEvent<SVGGElement>)=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(id)}}});
 return <svg viewBox="0 0 900 480" role="img" aria-labelledby="board-title board-description" style={{transform:'scale('+zoom+')'}}>
  <title id="board-title">Montage proposé à partir du patch Résonant</title>
  <desc id="board-description">Une Teensy compatible Arduino additionne les modes sinusoïdaux, reçoit un clavier MIDI USB et transmet l’audio I²S au DAC PCM5102A puis à une sortie ligne.</desc>
  <defs>
   <linearGradient id="boardTop" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#f2f0e8"/><stop offset="1" stopColor="#c5c9c3"/></linearGradient>
   <linearGradient id="boardSide" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#9ba49f"/><stop offset="1" stopColor="#525f5c"/></linearGradient>
   <linearGradient id="pcb" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#48a978"/><stop offset="1" stopColor="#195440"/></linearGradient>
   <linearGradient id="dacPcb" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#507bb2"/><stop offset="1" stopColor="#203b68"/></linearGradient>
   <filter id="shadow" x="-.2" y="-.3" width="1.5" height="1.7"><feDropShadow dx="0" dy="9" stdDeviation="7" floodColor="#000" floodOpacity=".42"/></filter>
  </defs>
  <path d="M128 196 648 110 824 333 304 421Z" fill="#101820" opacity=".55" transform="translate(0 34)"/>
  <path d="M128 196 648 110 824 333 304 421Z" fill="url(#boardSide)" stroke="#68756f" strokeWidth="3"/>
  <path d="M128 196 648 110 824 333 304 421Z" fill="url(#boardTop)" stroke="#edf0e9" strokeWidth="3"/>
  <path d="M146 207 651 124 670 149 165 232Z" fill="#d53f3f" opacity=".8"/><path d="M280 383 785 300 804 324 299 407Z" fill="#3578c9" opacity=".75"/>
  {holes.map((p,i)=><circle key={i} cx={p.x} cy={p.y} r={p.rail?1.55:1.12} fill={p.rail==='positive'?'#c74742':p.rail==='negative'?'#3978ba':'#747d77'} stroke="#f7f6ef" strokeWidth=".55"/>)}
  <text x="151" y="181" fill="#9a3837" fontSize="12" fontWeight="700">+5 V HÔTE USB</text><text x="301" y="441" fill="#285c9c" fontSize="12" fontWeight="700">MASSE COMMUNE</text>
  {wiring&&<g fill="none" strokeLinecap="round" strokeLinejoin="round" filter="url(#shadow)">
   <path d="M370 287 C405 313 455 330 546 353" stroke="#f4bb44" strokeWidth="4"/><path d="M364 297 C405 324 462 341 540 361" stroke="#65bed0" strokeWidth="4"/><path d="M357 305 C404 332 456 350 533 370" stroke="#e579ad" strokeWidth="4"/><path d="M354 315 C410 342 470 365 548 389" stroke="#d84b42" strokeWidth="4"/><path d="M349 323 C407 351 464 375 541 397" stroke="#303d47" strokeWidth="4"/>
   <path d="M591 376 C663 394 713 397 761 383" stroke="#d84b42" strokeWidth="4"/><path d="M584 384 C653 410 710 413 758 400" stroke="#d7d9de" strokeWidth="4"/><path d="M579 392 C650 426 712 425 760 414" stroke="#303d47" strokeWidth="4"/><path d="M194 263 C148 256 94 225 83 177 C65 98 126 77 251 73 C431 67 582 77 671 151" stroke="#eea15a" strokeWidth="5"/><path d="M107 168 127 168 127 183 107 183Z" fill="#202b35" stroke="#87949d" strokeWidth="2"/>
  </g>}
  <g {...select('teensy')} className={'board-part '+(selected==='teensy'?'chosen':'')} role="button" tabIndex={0} aria-label="Sélectionner la Teensy 4.1">
   <path d="M203 239 362 213 411 276 252 302Z" fill="url(#pcb)" stroke="#b0d1a6" strokeWidth="3" filter="url(#shadow)"/><path d="M250 246 353 229 382 266 279 283Z" fill="#172b31" stroke="#89978e" strokeWidth="2"/><rect x="297" y="241" width="42" height="24" rx="3" transform="rotate(-10 318 253)" fill="#111a22" stroke="#bec5cb" strokeWidth="2"/><text x="255" y="293" fill="#f2f7e9" fontSize="13" fontWeight="800" transform="rotate(-10 255 293)">TEENSY 4.1</text><rect x="194" y="255" width="20" height="15" rx="3" fill="#a6a8a3" stroke="#303b40" strokeWidth="2" transform="rotate(-10 204 263)"/><text x="177" y="232" fill="#eaf6df" fontSize="11" fontWeight="700">USB HOST</text>
  </g>
  <g {...select('dac')} className={'board-part '+(selected==='dac'?'chosen':'')} role="button" tabIndex={0} aria-label="Sélectionner le DAC PCM5102A">
   <path d="M506 321 622 302 668 360 552 379Z" fill="url(#dacPcb)" stroke="#a9b9d8" strokeWidth="3" filter="url(#shadow)"/><rect x="560" y="325" width="50" height="31" rx="2" fill="#151c29" stroke="#c4ccd5" strokeWidth="2" transform="rotate(-9 585 340)"/><text x="536" y="372" fill="#f1f4fb" fontSize="12" fontWeight="800" transform="rotate(-9 536 372)">DAC PCM5102A</text>
  </g>
  <g {...select('midi')} className={'board-part '+(selected==='midi'?'chosen':'')} role="button" tabIndex={0} aria-label="Sélectionner le clavier MIDI USB">
   <path d="M665 154 791 133 816 165 690 186Z" fill="#293640" stroke="#9aa7ad" strokeWidth="2" filter="url(#shadow)"/><path d="M679 158 787 140 804 161 696 179Z" fill="#edf0ed"/><path d="M699 157 704 174 M714 155 719 171 M729 152 734 169 M744 150 749 166 M759 147 764 164 M774 145 779 161" stroke="#27333b" strokeWidth="3"/><text x="708" y="125" fill="#dce6ed" fontSize="12" fontWeight="700">CLAVIER MIDI USB</text>
  </g>
  <g {...select('jack')} className={'board-part '+(selected==='jack'?'chosen':'')} role="button" tabIndex={0} aria-label="Sélectionner la sortie audio ligne">
   <path d="M744 379 802 370 823 397 765 406Z" fill="#26374b" stroke="#97a9bd" strokeWidth="2" filter="url(#shadow)"/><circle cx="782" cy="390" r="12" fill="#151d26" stroke="#ced4d6" strokeWidth="3"/><circle cx="782" cy="390" r="5" fill="#080d12"/><text x="746" y="427" fill="#e6edf0" fontSize="11" fontWeight="700">JACK L/R/GND</text>
  </g>
  <g fill="#e5edf2" fontSize="11" fontWeight="700"><text x="421" y="244">BCLK · 21</text><text x="421" y="258">LRCLK · 20</text><text x="421" y="272">TX · 7</text><text x="421" y="286">3V3</text><text x="421" y="300">GND</text></g>
 </svg>;
}

function SchematicDrawing(){
 return <svg className="electrical-schematic" viewBox="0 0 960 520" role="img" aria-labelledby="schematic-title">
  <title id="schematic-title">Schéma de câblage minimal du synthétiseur Arduino</title>
  <defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9Z" fill="#76d4c1"/></marker></defs>
  <rect x="48" y="185" width="185" height="116" rx="14" className="schematic-device midi"/><text x="75" y="225" className="schematic-title">CLAVIER MIDI USB</text><text x="75" y="252" className="schematic-sub">Port USB Host · notes + vélocité</text>
  <rect x="335" y="147" width="260" height="190" rx="16" className="schematic-device mcu"/><text x="368" y="189" className="schematic-title">TEENSY 4.1</text><text x="368" y="216" className="schematic-sub">Arduino IDE + Teensyduino</text><text x="368" y="253" className="schematic-code">Banque additive de sinusoïdes</text><text x="368" y="280" className="schematic-sub">MIDI → DSP → I²S</text>
  <rect x="699" y="185" width="205" height="116" rx="14" className="schematic-device dac"/><text x="729" y="225" className="schematic-title">DAC PCM5102A</text><text x="729" y="252" className="schematic-sub">I²S → sortie ligne L/R</text>
  <rect x="699" y="390" width="205" height="78" rx="14" className="schematic-device jack"/><text x="729" y="423" className="schematic-title">JACK 3,5 mm</text><text x="729" y="446" className="schematic-sub">Vers une entrée ligne</text>
  <path d="M233 243 H335" className="schematic-wire usb" markerEnd="url(#arrow)"/><text x="246" y="226" className="schematic-net">USB Host</text>
  <path d="M595 210 H699" className="schematic-wire i2s" markerEnd="url(#arrow)"/><path d="M595 240 H699" className="schematic-wire i2s" markerEnd="url(#arrow)"/><path d="M595 270 H699" className="schematic-wire i2s" markerEnd="url(#arrow)"/><text x="604" y="192" className="schematic-net">BCLK 21 · LRCLK 20 · TX 7</text>
  <path d="M802 301 V390" className="schematic-wire audio" markerEnd="url(#arrow)"/><text x="814" y="350" className="schematic-net">L/R/GND</text>
  <path d="M363 355 H571" className="schematic-wire ground"/><text x="403" y="383" className="schematic-net">Masse commune · alimentation USB basse tension</text>
  <text x="51" y="111" className="schematic-note">Aucun générateur, filtre ou enveloppe analogique ajouté par partiel : le calcul reste dans un seul microcontrôleur.</text>
  <text x="51" y="493" className="schematic-warning">Prototype : brochage du breakout à contrôler et audio embarqué à comparer avant tout montage définitif.</text>
 </svg>;
}

export function ElectronicsStudio({patch,analysis,onExportFirmware,onExportBrief}:{patch:Patch;analysis:Analysis|null;onExportFirmware:()=>void;onExportBrief:()=>void}){
 const [zoom,setZoom]=useState(1),[selected,setSelected]=useState<PartId>('teensy'),[wiring,setWiring]=useState(true),[view,setView]=useState<StudioView>('circuit'),[filter,setFilter]=useState('');
 const counts=useMemo(()=>patch.nodes.reduce<Record<string,number>>((out,node)=>{out[node.type]=(out[node.type]??0)+1;return out},{}),[patch.nodes]);
 const unsupported=useMemo(()=>patch.nodes.filter(node=>!dspTypes.has(node.type)),[patch.nodes]);
 const firmware=useMemo(()=>buildTeensySketch(patch,analysis),[patch,analysis]);
 const groups=useMemo(()=>Array.from(new Set(hardwareParts.map(p=>p.category))),[]);
 const visibleParts=hardwareParts.filter(part=>(part.name+' '+part.category+' '+part.role).toLowerCase().includes(filter.toLowerCase()));
 const selectedPart=hardwareParts.find(part=>part.id===selected)??hardwareParts[0];
 const measuredModes=analysis?.partials.length??firmware.partialCount;
 const rootFrequency=analysis?.f0??(patch.nodes.find(n=>n.type==='oscillator')?.parameters.frequency??null);
 const patchName=patch.name.trim()||'Projet sans nom';
 const patchPreview=Object.entries(counts).slice(0,5);

 return <section className="electronics-studio" aria-label="Atelier matériel dérivé du patch">
  <div className="electronics-workspace-top">
   <div className="electronics-workspace-switch"><span className="electronics-workspace-mark"><Activity size={15}/></span><button className="active">CONSTRUIRE</button><button onClick={()=>setView('firmware')}>FIRMWARE</button></div>
   <div className="electronics-project-title"><Box size={15}/><span>{patchName}</span><small>PATCH SYNCHRONISÉ</small></div>
   <div className="electronics-workspace-actions"><button onClick={onExportBrief}><Clipboard size={14}/> Brief</button><button className="firmware-download" onClick={onExportFirmware}><Download size={14}/> Code .ino</button></div>
  </div>

  <div className="electronics-warning" role="note"><AlertTriangle size={17}/><div><b>Maquette proposée depuis les mesures — prototype à vérifier</b><span>Le code ci-dessous reprend les fréquences, amplitudes, phases et décroissances identifiées. Il n’a pas encore été compilé ni testé sur une carte physique; le rendu n’est donc pas présenté comme identique.</span></div></div>

  <div className="electronics-workspace">
   <aside className="electronics-palette" aria-label="Composants du montage">
    <div className="palette-heading"><b>Composants</b><span>{hardwareParts.length}</span></div>
    <label className="palette-search"><Search size={14}/><input aria-label="Rechercher un composant physique" value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Rechercher un composant"/></label>
    <div className="palette-list">{groups.map(group=>{
     const items=visibleParts.filter(part=>part.category===group);
     return items.length>0?<section key={group} className="palette-group"><div className="palette-group-title">{group.toUpperCase()} <span>{items.length}</span><ChevronDown size={12}/></div>{items.map((part,index)=><button key={part.name+'-'+index} className={'palette-part '+(selected===part.id?'selected':'')} onClick={()=>setSelected(part.id)}><span className="palette-part-icon">{part.id==='midi'||part.id==='usb-host'?<Usb size={16}/>:part.id==='dac'||part.id==='jack'||part.id==='line-cable'?<AudioWaveform size={16}/>:part.id==='breadboard'||part.id==='wires'?<Cable size={16}/>:<Cpu size={16}/>}</span><span><b>{part.name}</b><small>{part.role}</small></span><Plus size={13}/></button>)}</section>:null;
    })}</div>
    <div className="palette-footnote"><Info size={13}/> Le patch est exécuté par le microcontrôleur; le nombre de blocs DSP n’ajoute pas de composants physiques.</div>
   </aside>

   <main className="electronics-editor">
    <div className="electronics-editor-toolbar">
     <div className="editor-view-tabs" role="tablist" aria-label="Vues du montage">
      <button role="tab" aria-selected={view==='circuit'} className={view==='circuit'?'active':''} onClick={()=>setView('circuit')}><Box size={14}/> 3D Circuit</button>
      <button role="tab" aria-selected={view==='schematic'} className={view==='schematic'?'active':''} onClick={()=>setView('schematic')}><Cable size={14}/> Schéma</button>
      <button role="tab" aria-selected={view==='firmware'} className={view==='firmware'?'active':''} onClick={()=>setView('firmware')}><Code2 size={14}/> Code Arduino</button>
     </div>
     {view==='circuit'&&<div className="breadboard-controls"><button aria-label="Réduire le zoom" onClick={()=>setZoom(v=>Math.max(.75,v-.1))}><Minus size={14}/></button><span>{Math.round(zoom*100)} %</span><button aria-label="Augmenter le zoom" onClick={()=>setZoom(v=>Math.min(1.35,v+.1))}><Plus size={14}/></button><button aria-label="Réinitialiser la vue" onClick={()=>{setZoom(1);setWiring(true)}}><RotateCcw size={14}/></button></div>}
    </div>

    {view==='circuit'&&<>
     <div className="electronics-canvas-caption"><div><b>Montage 3D · synthétiseur mono</b><small>Vue éditable du plan · 830 points · câblage indicatif</small></div><span className="canvas-running-dot"><i/> {firmware.partialCount} modes sinusoïdaux logiciels</span></div>
     <div className="breadboard-viewport"><CircuitDrawing zoom={zoom} selected={selected} wiring={wiring} onSelect={setSelected}/></div>
     <div className="breadboard-legend"><button className={wiring?'active':''} onClick={()=>setWiring(v=>!v)}><span className="wire-toggle"/>{wiring?'Masquer':'Afficher'} les liaisons</button><span><i className="legend-midi"/>MIDI/USB</span><span><i className="legend-i2s"/>I²S</span><span><i className="legend-power"/>Alimentation</span></div>
    </>}
    {view==='schematic'&&<div className="schematic-viewport"><SchematicDrawing/></div>}
    {view==='firmware'&&<div className="firmware-editor">
     <div className="firmware-filebar"><span><FileCode2 size={15}/> resonant_teensy.ino</span><span>Teensy 4.1 · Audio · USBHost_t36</span><div><button onClick={()=>void navigator.clipboard?.writeText(firmware.code)}><Clipboard size={13}/> Copier</button><button className="firmware-download" onClick={onExportFirmware}><Download size={13}/> Télécharger</button></div></div>
     <pre aria-label="Sketch Arduino généré"><code>{firmware.code}</code></pre>
     <div className="firmware-limitations"><b>Le code actuellement généré :</b><span>additionne jusqu’à 24 sinusoïdes à partir des modes mesurés, avec transposition MIDI, enveloppe d’attaque et décroissance par mode.</span>{firmware.limitations.map((item,index)=><span key={index}>• {item}</span>)}</div>
    </div>}
   </main>

   <aside className="electronics-assistant" aria-label="Analyse et construction">
    <div className="assistant-header"><div className="assistant-avatar"><Activity size={17}/></div><div><b>Résonant · Studio</b><small>Montage calculé depuis le modèle</small></div><span className="assistant-online"/></div>
    <div className="assistant-content">
     <div className="assistant-intro"><span className="assistant-tag"><Check size={12}/> RÉSULTATS DU MODÈLE</span><p>La liste de modes sert à programmer une seule banque additive. Les oscillateurs sont du code Arduino, pas des modules séparés sur la breadboard.</p></div>
     <div className="assistant-selected-part"><div><Component size={14}/><b>{selectedPart.name}</b></div><p>{selectedPart.detail}</p>{selectedPart.link&&<a href={selectedPart.link} target="_blank" rel="noreferrer">Données fabricant <ExternalLink size={11}/></a>}</div>
     <div className="analysis-summary"><div><small>Fondamentale</small><b>{rootFrequency?rootFrequency.toFixed(2)+' Hz':'—'}</b></div><div><small>Modes utilisés</small><b>{measuredModes}</b></div><div><small>Attaque mesurée</small><b>{analysis?(analysis.attack*1000).toFixed(2)+' ms':'Patch'}</b></div><div><small>Échantillonnage source</small><b>{(patch.sample_rate/1000).toFixed(1)} kHz</b></div></div>
     <div className="assistant-section-title">MONTAGE MINIMAL <span>2 modules actifs</span></div>
     <div className="minimal-chain"><span><Cpu size={14}/> Teensy</span><i/><span><AudioWaveform size={14}/> DAC I²S</span><i/><span><Volume2 size={14}/> Sortie ligne</span></div>
     <div className="assistant-section-title">LE PATCH SE TRADUIT EN DSP <span>{patch.nodes.length} nœuds</span></div>
     <div className="assistant-dsp-list">{patchPreview.map(([type,count])=><div key={type}><span>{dspNames[type]??type}</span><b>× {count}</b><small>{type==='oscillator'?'Sinusoïdes calculées dans le code':type==='noise'?'Pas encore porté dans le sketch':'Traitement logiciel sur Teensy'}</small></div>)}{Object.keys(counts).length>patchPreview.length&&<span className="extra-types">+ {Object.keys(counts).length-patchPreview.length} types</span>}</div>
     {unsupported.length>0&&<p className="assistant-alert">Types inconnus au profil matériel : {unsupported.map(n=>n.type).join(', ')}.</p>}
     <div className="assistant-callout"><b>Importer dans Tinkered</b><p>Le site Tinkered accepte un firmware existant. Télécharge le sketch et le brief ci-dessous, puis joins-les à un nouveau projet Tinkered. Cette page ne transmet aucun patch automatiquement.</p><div><a href="https://app.tinkered.ai/" target="_blank" rel="noreferrer">Ouvrir Tinkered <ExternalLink size={13}/></a><button onClick={onExportBrief}><Download size={13}/> Brief + mesures</button></div></div>
    </div>
    <div className="assistant-input-note"><Info size={13}/> Export soumis à connexion au compte Resonant Lab.</div>
   </aside>
  </div>

  <section className="electronics-bom"><div className="bom-heading"><div><div className="eyebrow">NOMENCLATURE PRÉVISIONNELLE</div><h3>Matériel à réunir</h3></div><span>{hardwareParts.length} lignes · architecture sobre</span></div><div className="bom-table-wrap"><table><thead><tr><th>Qté</th><th>Composant réel</th><th>Rôle</th><th>Fiche</th></tr></thead><tbody>{hardwareParts.map((part,index)=><tr key={part.name+'-'+index}><td>{part.qty}</td><td><b>{part.name}</b></td><td>{part.role}</td><td>{part.link?<a href={part.link} target="_blank" rel="noreferrer" aria-label={'Documentation de '+part.name}><ExternalLink size={14}/></a>:<span>—</span>}</td></tr>)}</tbody></table></div></section>

  <section className="electronics-wiring"><div><Cpu size={19}/><b>Chaîne de signal et brochage</b></div><ol><li><Usb size={15}/>Clavier MIDI USB → port USB Host de la Teensy 4.1</li><li><Cpu size={15}/>Teensy → addition logicielle des sinusoïdes et application des enveloppes mesurées</li><li><span className="i2s-mark">I²S</span>Teensy pin 21 BCLK, pin 20 LRCLK, pin 7 TX → DAC PCM5102A</li><li><Volume2 size={15}/>DAC L/R/GND → breakout jack 3,5 mm → entrée ligne externe</li></ol><details className="wiring-map"><summary>Liaisons principales à câbler</summary><div className="bom-table-wrap"><table><thead><tr><th>Origine</th><th>Destination</th><th>Condition</th></tr></thead><tbody><tr><td>Teensy pin 21 · BCLK</td><td>DAC BCK</td><td>Horloge bit I²S</td></tr><tr><td>Teensy pin 20 · LRCLK</td><td>DAC LRCK</td><td>Horloge de trame I²S</td></tr><tr><td>Teensy pin 7 · TX</td><td>DAC DIN</td><td>Données I²S</td></tr><tr><td>Teensy 3V3 / GND</td><td>DAC VCC / GND</td><td>Seulement avec un breakout compatible 3,3 V; masse commune</td></tr><tr><td>DAC LOUT / ROUT / GND</td><td>Jack L / R / GND</td><td>Le code duplique le son mono en stéréo</td></tr></tbody></table></div><p>Les marquages et straps changent selon le breakout. Vérifier sa documentation; ne pas câbler directement le boîtier TSSOP du DAC sur la breadboard.</p></details></section>
  <div className="electronics-safety"><b>Montage sûr :</b> la Teensy 4.1 n’accepte pas 5 V sur ses broches logiques. Garder l’alimentation en basse tension USB; jamais de secteur ni de sortie d’amplificateur sur la breadboard. Un clavier USB gourmand peut demander un hub alimenté.</div>
  <details className="electronics-references"><summary>Pourquoi l’ADSR du projet d’exemple n’est pas copié tel quel</summary><p>La forme d’une enveloppe analogique dépend de ses composants et de la charge. Ici, l’attaque et la décroissance mesurées sont traitées dans le firmware. Le relâchement MIDI reste un réglage provisoire si l’analyse ne le mesure pas.</p><a href="https://www.craigstuntz.com/posts/2024-01-31-building-a-synthesizer-8.html" target="_blank" rel="noreferrer">Lire l’article de référence <ExternalLink size={13}/></a></details>
 </section>;
}
