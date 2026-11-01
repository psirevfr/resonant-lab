import {lazy,Suspense,useMemo,useState} from 'react';
import {Activity,AlertTriangle,AudioWaveform,Box,Cable,Check,ChevronDown,Clipboard,Code2,Component,Cpu,Download,ExternalLink,FileCode2,Info,Plus,Search,Usb,Volume2} from 'lucide-react';
import type {Analysis,Patch} from '../types';
import {buildTeensySketch} from '../firmware/teensySketch';
import type {CircuitPartId} from './CircuitScene3D';

type PartId=CircuitPartId;
type StudioView='circuit'|'schematic'|'firmware';
type HardwarePart={id:PartId;category:string;qty:string;name:string;role:string;detail:string;link?:string};

const CircuitScene3D=lazy(()=>import('./CircuitScene3D'));

const hardwareParts:HardwarePart[]=[
 {id:'teensy',category:'Calculateur',qty:'1',name:'Teensy 4.1 · Arduino IDE',role:'Génère et additionne les sinusoïdes en logiciel.',detail:'Microcontrôleur programmable avec Arduino IDE et Teensyduino. Le DSP du patch tourne dans le code; aucun module analogique par partiel.',link:'https://www.pjrc.com/store/teensy41.html'},
 {id:'midi',category:'Entrée MIDI',qty:'1',name:'Clavier MIDI USB class-compliant',role:'Envoie les notes et vélocités au port USB Host.',detail:'Connexion directe au port USB Host de la Teensy. En cas de courant insuffisant, utiliser un hub USB alimenté.',link:'https://www.pjrc.com/teensy/td_midi.html'},
 {id:'usb-host',category:'Entrée MIDI',qty:'1',name:'Câble USB Host pour Teensy',role:'Relie la prise USB-A femelle aux pastilles Host.',detail:'Câblage distinct du câble USB de programmation. Isoler correctement les conducteurs et vérifier le brochage PJRC.',link:'https://www.pjrc.com/store/cable_usb_host_t36.html'},
 {id:'audio-shield',category:'Sortie audio',qty:'1',name:'Teensy Audio Shield Rev D2 · SGTL5000',role:'Regroupe DAC, codec et prises casque/ligne sur une seule carte.',detail:'Version Rev D/D2 compatible Teensy 4.0/4.1. Elle s’empile sur la Teensy : pas de DAC ni de jack séparé à ajouter.',link:'https://www.pjrc.com/store/teensy3_audio.html'},
 {id:'breadboard',category:'Support',qty:'1',name:'Breadboard sans soudure · 830 points',role:'Supporte les cartes et les connexions temporaires.',detail:'La Teensy 4.1 est une grande carte; vérifier son support mécanique et les rails d’alimentation avant placement.'},
 {id:'wires',category:'Support',qty:'1 jeu',name:'Fils Dupont · montage sur breadboard',role:'Fixent et raccordent les cartes à la platine.',detail:'L’I²S passe directement par le shield empilé. Aucun faisceau I²S séparé n’est nécessaire.'},
 {id:'usb-data',category:'Programmation',qty:'1',name:'Câble micro-USB de données',role:'Téléverse le sketch depuis l’ordinateur.',detail:'Le câble de programmation USB est différent de l’entrée clavier branchée sur le port USB Host.'},
 {id:'line-cable',category:'Sortie audio',qty:'1',name:'Câble audio 3,5 mm',role:'Relie la sortie casque/ligne à un casque ou une entrée audio.',detail:'Commencer avec un faible volume. La sortie casque amplifiée doit être réglée prudemment si elle attaque une entrée ligne.'}
];

const dspTypes=new Set(['oscillator','modal','noise','input','impulse','sum','multiply','gain','output','envelope','adsr','saturation','asymmetric_saturation','delay','lowpass','highpass','bandpass','notch','peak_eq','lowpass1','resonator']);
const dspNames:Record<string,string>={oscillator:'Sinusoïdes',modal:'Modes modaux',noise:'Bruit',input:'Entrée',impulse:'Impact',sum:'Somme',multiply:'VCA',gain:'Gain',output:'Sortie',envelope:'Enveloppe',adsr:'ADSR',saturation:'Saturation',asymmetric_saturation:'Saturation suréchantillonnée',delay:'Délai',lowpass:'Passe-bas',highpass:'Passe-haut',bandpass:'Passe-bande',notch:'Coupe-bande',peak_eq:'Égaliseur',lowpass1:'Passe-bas simple',resonator:'Résonateur'};
function SchematicDrawing(){
 return <svg className="electrical-schematic" viewBox="0 0 960 520" role="img" aria-labelledby="schematic-title">
  <title id="schematic-title">Schéma de câblage minimal du synthétiseur Arduino</title>
  <defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9Z" fill="#76d4c1"/></marker></defs>
  <rect x="48" y="185" width="185" height="116" rx="14" className="schematic-device midi"/><text x="75" y="225" className="schematic-title">CLAVIER MIDI USB</text><text x="75" y="252" className="schematic-sub">Port USB Host · notes + vélocité</text>
  <rect x="335" y="147" width="300" height="190" rx="16" className="schematic-device mcu"/><text x="365" y="185" className="schematic-title">TEENSY 4.1</text><text x="365" y="211" className="schematic-sub">Arduino IDE + Teensyduino · DSP mono</text><rect x="362" y="231" width="245" height="78" rx="10" className="schematic-device dac"/><text x="380" y="261" className="schematic-title">AUDIO SHIELD REV D2</text><text x="380" y="286" className="schematic-sub">SGTL5000 · empilé · casque / sortie ligne</text>
  <rect x="705" y="204" width="199" height="104" rx="14" className="schematic-device jack"/><text x="735" y="244" className="schematic-title">SORTIE AUDIO</text><text x="735" y="271" className="schematic-sub">Jack 3,5 mm · vers casque/entrée</text>
  <path d="M233 243 H335" className="schematic-wire usb" markerEnd="url(#arrow)"/><text x="246" y="226" className="schematic-net">USB Host · MIDI</text>
  <path d="M635 255 H705" className="schematic-wire audio" markerEnd="url(#arrow)"/><text x="646" y="235" className="schematic-net">Codec intégré</text>
  <path d="M363 355 H571" className="schematic-wire ground"/><text x="403" y="383" className="schematic-net">Shield empilé · I²S + contrôle I²C internes</text>
  <text x="51" y="111" className="schematic-note">Deux cartes actives : toutes les sinusoïdes et enveloppes restent dans le firmware.</text>
  <text x="51" y="493" className="schematic-warning">Prototype : brochage du breakout à contrôler et audio embarqué à comparer avant tout montage définitif.</text>
 </svg>;
}

export function ElectronicsStudio({patch,analysis,onExportFirmware,onExportBrief}:{patch:Patch;analysis:Analysis|null;onExportFirmware:()=>void;onExportBrief:()=>void}){
 const [selected,setSelected]=useState<PartId>('teensy'),[wiring,setWiring]=useState(true),[view,setView]=useState<StudioView>('circuit'),[filter,setFilter]=useState('');
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
    <div className="palette-heading"><b>Composants</b><span>2 modules actifs</span></div>
    <label className="palette-search"><Search size={14}/><input aria-label="Rechercher un composant physique" value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Rechercher un composant"/></label>
    <div className="palette-list">{groups.map(group=>{
     const items=visibleParts.filter(part=>part.category===group);
     return items.length>0?<section key={group} className="palette-group"><div className="palette-group-title">{group.toUpperCase()} <span>{items.length}</span><ChevronDown size={12}/></div>{items.map((part,index)=><button key={part.name+'-'+index} className={'palette-part '+(selected===part.id?'selected':'')} onClick={()=>setSelected(part.id)}><span className="palette-part-icon">{part.id==='midi'||part.id==='usb-host'?<Usb size={16}/>:part.id==='audio-shield'||part.id==='line-cable'?<AudioWaveform size={16}/>:part.id==='breadboard'||part.id==='wires'?<Cable size={16}/>:<Cpu size={16}/>}</span><span><b>{part.name}</b><small>{part.role}</small></span><Plus size={13}/></button>)}</section>:null;
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
    </div>

    {view==='circuit'&&<>
     <div className="electronics-canvas-caption"><div><b>Montage 3D · synthétiseur MIDI</b><small>Glisse pour tourner, clic droit pour déplacer, molette ou boutons pour zoomer</small></div><span className="canvas-running-dot"><i/> {firmware.partialCount} modes sinusoïdaux logiciels</span></div>
     <Suspense fallback={<div className="circuit-scene-loading" role="status">Chargement de la scène 3D…</div>}><CircuitScene3D selected={selected} wiring={wiring} onSelect={setSelected}/></Suspense>
     <div className="breadboard-legend"><button className={wiring?'active':''} onClick={()=>setWiring(v=>!v)}><span className="wire-toggle"/>{wiring?'Masquer':'Afficher'} les liaisons</button><span><i className="legend-midi"/>MIDI/USB</span><span><i className="legend-i2s"/>I²S</span><span><i className="legend-power"/>Alimentation</span></div>
     <details className="electronics-serial-panel"><summary><span>Console de conception</span><small>aperçu du câblage · aucune carte connectée</small><b>Ouvrir</b></summary><div className="serial-log"><code><i>USB MIDI</i> Clavier → USB Host Teensy 4.1</code><code><i>I²S / I²C</i> Teensy → Audio Shield Rev D2 · connexion empilée</code><code><i>AUDIO</i> Jack casque/ligne intégré · {firmware.partialCount} partiels dans le firmware</code></div></details>
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
     <div className="minimal-chain"><span><Cpu size={14}/> Teensy</span><i/><span><AudioWaveform size={14}/> Audio Shield · DAC intégré</span><i/><span><Volume2 size={14}/> Sortie audio</span></div>
     <div className="assistant-section-title">LE PATCH SE TRADUIT EN DSP <span>{patch.nodes.length} nœuds</span></div>
     <div className="assistant-dsp-list">{patchPreview.map(([type,count])=><div key={type}><span>{dspNames[type]??type}</span><b>× {count}</b><small>{type==='oscillator'?'Sinusoïdes calculées dans le code':type==='noise'?'Pas encore porté dans le sketch':'Traitement logiciel sur Teensy'}</small></div>)}{Object.keys(counts).length>patchPreview.length&&<span className="extra-types">+ {Object.keys(counts).length-patchPreview.length} types</span>}</div>
     {unsupported.length>0&&<p className="assistant-alert">Types inconnus au profil matériel : {unsupported.map(n=>n.type).join(', ')}.</p>}
     <div className="assistant-callout"><b>Importer dans Tinkered</b><p>Le site Tinkered accepte un firmware existant. Télécharge le sketch et le brief ci-dessous, puis joins-les à un nouveau projet Tinkered. Cette page ne transmet aucun patch automatiquement.</p><div><a href="https://app.tinkered.ai/" target="_blank" rel="noreferrer">Ouvrir Tinkered <ExternalLink size={13}/></a><button onClick={onExportBrief}><Download size={13}/> Brief + mesures</button></div></div>
    </div>
    <div className="assistant-input-note"><Info size={13}/> Export soumis à connexion au compte Resonant Lab.</div>
   </aside>
  </div>

  <section className="electronics-bom"><div className="bom-heading"><div><div className="eyebrow">NOMENCLATURE PRÉVISIONNELLE</div><h3>Matériel à réunir</h3></div><span>2 cartes actives · {hardwareParts.length-2} éléments périphériques</span></div><div className="bom-table-wrap"><table><thead><tr><th>Qté</th><th>Composant réel</th><th>Rôle</th><th>Fiche</th></tr></thead><tbody>{hardwareParts.map((part,index)=><tr key={part.name+'-'+index}><td>{part.qty}</td><td><b>{part.name}</b></td><td>{part.role}</td><td>{part.link?<a href={part.link} target="_blank" rel="noreferrer" aria-label={'Documentation de '+part.name}><ExternalLink size={14}/></a>:<span>—</span>}</td></tr>)}</tbody></table></div></section>

  <section className="electronics-wiring"><div><Cpu size={19}/><b>Chaîne de signal et brochage</b></div><ol><li><Usb size={15}/>Clavier MIDI USB → câble USB Host des pastilles Teensy 4.1</li><li><Cpu size={15}/>Teensy → addition des sinusoïdes et enveloppes dans le firmware Arduino</li><li><span className="i2s-mark">I²S</span>Audio Shield Rev D/D2 empilé : données pin 7, BCLK 21, LRCLK 20, MCLK 23</li><li><Volume2 size={15}/>Sortie casque 3,5 mm ou broches Line-Out du shield → équipement audio</li></ol><details className="wiring-map"><summary>Liaisons principales à câbler</summary><div className="bom-table-wrap"><table><thead><tr><th>Origine</th><th>Destination</th><th>Condition</th></tr></thead><tbody><tr><td>Teensy pin 7 · TX</td><td>Audio Shield · DIN</td><td>Connexion I²S via les headers empilés</td></tr><tr><td>Teensy pin 21 · BCLK</td><td>Audio Shield · BCLK</td><td>Connexion I²S via les headers empilés</td></tr><tr><td>Teensy pin 20 · LRCLK</td><td>Audio Shield · LRCLK</td><td>Connexion I²S via les headers empilés</td></tr><tr><td>Teensy pin 23 · MCLK</td><td>Audio Shield · MCLK</td><td>Connexion I²S via les headers empilés</td></tr><tr><td>Teensy pins 18/19 · I²C</td><td>Audio Shield · SDA/SCL</td><td>Commande du codec SGTL5000 par AudioControlSGTL5000</td></tr></tbody></table></div><p>Prendre la version Rev D ou D2 pour Teensy 4.x. Le câble jack est intégré au shield; utiliser un volume prudent si on branche la sortie casque sur une entrée ligne.</p></details></section>
  <div className="electronics-safety"><b>Montage sûr :</b> la Teensy 4.1 n’accepte pas 5 V sur ses broches logiques. Garder l’alimentation en basse tension USB; jamais de secteur ni de sortie d’amplificateur sur la breadboard. Un clavier USB gourmand peut demander un hub alimenté.</div>
  <details className="electronics-references"><summary>Pourquoi l’ADSR du projet d’exemple n’est pas copié tel quel</summary><p>La forme d’une enveloppe analogique dépend de ses composants et de la charge. Ici, l’attaque et la décroissance mesurées sont traitées dans le firmware. Le relâchement MIDI reste un réglage provisoire si l’analyse ne le mesure pas.</p><a href="https://www.craigstuntz.com/posts/2024-01-31-building-a-synthesizer-8.html" target="_blank" rel="noreferrer">Lire l’article de référence <ExternalLink size={13}/></a></details>
 </section>;
}
