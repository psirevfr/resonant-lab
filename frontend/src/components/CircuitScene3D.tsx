import {useEffect,useRef,useState} from 'react';
import {Minus,Plus,RotateCcw,Tags} from 'lucide-react';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

export type CircuitPartId='midi'|'teensy'|'audio-shield'|'line-cable'|'breadboard'|'wires'|'usb-host'|'usb-data';

type CircuitScene3DProps={selected:CircuitPartId;wiring:boolean;onSelect:(part:CircuitPartId)=>void};
type SceneController={zoom:(factor:number)=>void;reset:()=>void;fit:()=>void};

const color={green:'#48a978',greenDark:'#1b513b',blue:'#3974a8',blueDark:'#1c3550',black:'#111619',metal:'#aeb7ba',gold:'#d7b45b',wireYellow:'#e8c64d',wireBlue:'#58b8d3',wirePink:'#dd78ad',red:'#d84b42',ground:'#313b40',white:'#e9e8df'};

function makeLabel(text:string,tint='#e8eee9'){
 const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;
 const context=canvas.getContext('2d');
 if(context){context.clearRect(0,0,canvas.width,canvas.height);context.font='700 42px system-ui, sans-serif';context.textAlign='center';context.textBaseline='middle';context.shadowColor='#000';context.shadowBlur=10;context.fillStyle=tint;context.fillText(text,256,64,490);}
 const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
 const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,transparent:true,depthTest:false}));
 sprite.scale.set(Math.max(11,Math.min(31,text.length*1.15)),5.5,1);sprite.userData.labelTexture=texture;
 return sprite;
}

function createBreadboard(scene:THREE.Scene,material:(hex:string,roughness?:number,metalness?:number)=>THREE.MeshStandardMaterial){
 const board=new THREE.Group();board.userData.partId='breadboard';
 const outline=new THREE.Mesh(new THREE.BoxGeometry(168,4.5,63),new THREE.MeshBasicMaterial({color:'#b8ed91',transparent:true,opacity:.2,side:THREE.BackSide}));outline.visible=false;board.add(outline);board.userData.outline=outline;
 const base=new THREE.Mesh(new THREE.BoxGeometry(166,4,61),material('#deded6',.82));base.position.y=2;base.castShadow=true;base.receiveShadow=true;board.add(base);
 const top=new THREE.Mesh(new THREE.BoxGeometry(164,.38,59),material('#f1f0e9',.9));top.position.y=4.12;board.add(top);
 const groove=new THREE.Mesh(new THREE.BoxGeometry(157,.12,4),material('#c4c5bd',.9));groove.position.set(0,4.36,0);board.add(groove);
 const redRail=material('#cb5148',.65),blueRail=material('#547da2',.65);
 for(const z of [-26,26]){
  const redLine=new THREE.Mesh(new THREE.BoxGeometry(156,.08,.32),redRail);redLine.position.set(0,4.36,z-1);board.add(redLine);
  const blueLine=new THREE.Mesh(new THREE.BoxGeometry(156,.08,.32),blueRail);blueLine.position.set(0,4.36,z+1);board.add(blueLine);
 }
 const holeGeo=new THREE.CylinderGeometry(.68,.68,.28,8),holeMat=new THREE.MeshStandardMaterial({color:'#303431',roughness:.58});
 const holes=new THREE.InstancedMesh(holeGeo,holeMat,830);const dummy=new THREE.Object3D();let count=0;
 for(let colIndex=0;colIndex<63;colIndex++){
  const x=-75+colIndex*2.42;
  for(const z of [-18,-15,-12,-9,-6,6,9,12,15,18]){dummy.position.set(x,4.33,z);dummy.updateMatrix();holes.setMatrixAt(count++,dummy.matrix);}
 }
 for(let colIndex=0;colIndex<50;colIndex++){
  const x=-61+colIndex*2.48;
  for(const z of [-27.7,-24.4,24.4,27.7]){dummy.position.set(x,4.33,z);dummy.updateMatrix();holes.setMatrixAt(count++,dummy.matrix);}
 }
 holes.instanceMatrix.needsUpdate=true;board.add(holes);
 const indices=material('#6c706b',.9);
 for(let n=0;n<13;n++){
  const label=makeLabel(String(n*5+1),'#686e6a');label.scale.set(3,1.2,1);label.position.set(-75+n*12.1,4.55,-21.5);board.add(label);
 }
 const mark=makeLabel('A–E     F–J','#8b8e88');mark.scale.set(16,1.8,1);mark.position.set(-67,4.55,0);board.add(mark);
 scene.add(board);return board;
}

function addPart(scene:THREE.Scene,id:CircuitPartId,position:THREE.Vector3){
 const group=new THREE.Group();group.userData.partId=id;group.position.copy(position);scene.add(group);return group;
}

function box(parent:THREE.Object3D,geometry:THREE.BoxGeometry,material:THREE.Material,position:THREE.Vector3){
 const mesh=new THREE.Mesh(geometry,material);mesh.position.copy(position);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;
}

function createTeensy(scene:THREE.Scene,mat:(hex:string,roughness?:number,metalness?:number)=>THREE.MeshStandardMaterial){
 const group=addPart(scene,'teensy',new THREE.Vector3(-36,6.1,0));
 const pcb=box(group,new THREE.BoxGeometry(61,1.5,19),mat(color.green,.56,.12),new THREE.Vector3(0,0,0));
 const outline=new THREE.Mesh(new THREE.BoxGeometry(63,2.1,21),new THREE.MeshBasicMaterial({color:'#b8ed91',transparent:true,opacity:.24,side:THREE.BackSide}));outline.visible=false;group.add(outline);group.userData.outline=outline;
 const chipMat=mat('#171d20',.47,.35),silver=mat('#aeb8b6',.32,.7),pinMat=mat('#d7b45b',.35,.72),header=mat('#151b1d',.72);
 box(group,new THREE.BoxGeometry(17,1.3,11),chipMat,new THREE.Vector3(1,.95,-.5));
 box(group,new THREE.BoxGeometry(7,1.1,5),chipMat,new THREE.Vector3(-19,.9,3));
 box(group,new THREE.BoxGeometry(5,1.15,3.8),chipMat,new THREE.Vector3(14,.9,-5));
 for(const z of [-8.4,8.4]){
  box(group,new THREE.BoxGeometry(58,.9,1.8),header,new THREE.Vector3(0,1.1,z));
  for(let index=0;index<24;index++){
   const pin=new THREE.Mesh(new THREE.CylinderGeometry(.28,.28,3.5,6),pinMat);pin.position.set(-28.5+index*2.48,-1.95,z);group.add(pin);
  }
 }
 const hostConnector=box(group,new THREE.BoxGeometry(8,5,10),silver,new THREE.Vector3(-29,2.5,0));hostConnector.userData.pickId='usb-host';
 const programmingPort=box(group,new THREE.BoxGeometry(4,2.6,4),silver,new THREE.Vector3(28,1.5,5));programmingPort.userData.pickId='usb-data';
 for(let index=0;index<4;index++)box(group,new THREE.BoxGeometry(2.5,.75,1.8),mat(index%2?'#bfc6c0':'#d3bd82',.45,.2),new THREE.Vector3(-12+index*7,1,5.5));
 const label=makeLabel('TEENSY 4.1 · USB HOST','#d7f2df');label.position.set(0,6.3,-13);group.add(label);group.userData.labels=[label];
 return group;
}

function createAudioShield(scene:THREE.Scene,mat:(hex:string,roughness?:number,metalness?:number)=>THREE.MeshStandardMaterial){
 const group=addPart(scene,'audio-shield',new THREE.Vector3(-36,9.4,0));
 const pcb=box(group,new THREE.BoxGeometry(43,1.5,31),mat(color.blue,.58,.18),new THREE.Vector3(0,0,0));
 const outline=new THREE.Mesh(new THREE.BoxGeometry(45,2.1,33),new THREE.MeshBasicMaterial({color:'#b8ed91',transparent:true,opacity:.24,side:THREE.BackSide}));outline.visible=false;group.add(outline);group.userData.outline=outline;
 const black=mat('#171c20',.45,.32),pin=mat(color.gold,.35,.72),housing=mat('#111719',.75),silver=mat('#aeb8b6',.32,.7);
 box(group,new THREE.BoxGeometry(13,1.4,10),black,new THREE.Vector3(-5,1.05,-4));
 box(group,new THREE.BoxGeometry(8,1.1,5),black,new THREE.Vector3(8,.92,-6));
 box(group,new THREE.BoxGeometry(11,.85,9),mat('#414c50',.4,.52),new THREE.Vector3(-13,.9,5));
 for(const z of [-8.4,8.4]){
  box(group,new THREE.BoxGeometry(35,.85,1.5),housing,new THREE.Vector3(0,-1.05,z));
  for(let index=0;index<14;index++){const p=new THREE.Mesh(new THREE.CylinderGeometry(.27,.27,3.6,6),pin);p.position.set(-16+index*2.45,-1.25,z);group.add(p);}
 }
 const headphoneJack=new THREE.Mesh(new THREE.CylinderGeometry(4,4,7,24),silver);headphoneJack.rotation.x=Math.PI/2;headphoneJack.position.set(14,2.8,14.2);headphoneJack.userData.pickId='line-cable';group.add(headphoneJack);
 const jackOpening=new THREE.Mesh(new THREE.CylinderGeometry(2.1,2.1,.18,20),mat('#14191d',.45,.12));jackOpening.rotation.x=Math.PI/2;jackOpening.position.set(14,2.8,17.65);jackOpening.userData.pickId='line-cable';group.add(jackOpening);
 const label=makeLabel('AUDIO SHIELD · SGTL5000','#dbe8ff');label.position.set(-2,6.2,-19);group.add(label);group.userData.labels=[label];pcb.userData.pickId='audio-shield';return group;
}

function createMidiKeyboard(scene:THREE.Scene,mat:(hex:string,roughness?:number,metalness?:number)=>THREE.MeshStandardMaterial){
 const group=addPart(scene,'midi',new THREE.Vector3(-112,9,-3));
 const outline=new THREE.Mesh(new THREE.BoxGeometry(57,7,22),new THREE.MeshBasicMaterial({color:'#b8ed91',transparent:true,opacity:.24,side:THREE.BackSide}));outline.visible=false;group.add(outline);group.userData.outline=outline;
 box(group,new THREE.BoxGeometry(54,4,18),mat('#252b2e',.68,.12),new THREE.Vector3(0,0,0));
 for(let index=0;index<14;index++)box(group,new THREE.BoxGeometry(3.35,.55,9),mat('#e9e9e4',.72),new THREE.Vector3(-24+index*3.7,2.25,2));
 for(let index=0;index<9;index++)if(index%7!==2&&index%7!==6)box(group,new THREE.BoxGeometry(2.1,.7,5),mat('#16191a',.56),new THREE.Vector3(-22.2+index*3.7,2.65,-1.2));
 const label=makeLabel('CLAVIER MIDI USB','#f0e2cc');label.position.set(0,10,-16);group.add(label);group.userData.labels=[label];return group;
}

function createAudioCable(scene:THREE.Scene,mat:(hex:string,roughness?:number,metalness?:number)=>THREE.MeshStandardMaterial){
 const group=addPart(scene,'line-cable',new THREE.Vector3(-22,11,43));
 const outline=new THREE.Mesh(new THREE.BoxGeometry(18,9,21),new THREE.MeshBasicMaterial({color:'#b8ed91',transparent:true,opacity:.24,side:THREE.BackSide}));outline.visible=false;group.add(outline);group.userData.outline=outline;
 const barrel=new THREE.Mesh(new THREE.CylinderGeometry(1.45,1.45,12,14),mat('#252d31',.56,.16));barrel.rotation.x=Math.PI/2;barrel.position.set(0,0,0);group.add(barrel);
 const tip=new THREE.Mesh(new THREE.CylinderGeometry(1.1,1.1,5,14),mat('#b7c0c3',.28,.75));tip.rotation.x=Math.PI/2;tip.position.set(0,0,8.2);group.add(tip);
 const ring=new THREE.Mesh(new THREE.CylinderGeometry(1.5,1.5,.8,14),mat('#1b2023',.55,.2));ring.rotation.x=Math.PI/2;ring.position.set(0,0,5.1);group.add(ring);
 const label=makeLabel('CÂBLE AUDIO 3,5 mm','#d9e3e7');label.position.set(2,6,8);group.add(label);group.userData.labels=[label];return group;
}

function wire(scene:THREE.Scene,points:THREE.Vector3[],hex:string,radius=.46){
 const curve=new THREE.CatmullRomCurve3(points);const geometry=new THREE.TubeGeometry(curve,32,radius,7,false);const material=new THREE.MeshStandardMaterial({color:hex,roughness:.42,metalness:.2});
 const mesh=new THREE.Mesh(geometry,material);mesh.castShadow=true;mesh.userData.isWire=true;scene.add(mesh);return mesh;
}

function buildScene(scene:THREE.Scene){
 const materials=new Map<string,THREE.MeshStandardMaterial>();
 const mat=(hex:string,roughness=.55,metalness=.08)=>{const key=`${hex}:${roughness}:${metalness}`;let value=materials.get(key);if(!value){value=new THREE.MeshStandardMaterial({color:hex,roughness,metalness});materials.set(key,value);}return value;};
 scene.background=new THREE.Color('#111416');scene.fog=new THREE.Fog('#111416',240,470);
 scene.add(new THREE.HemisphereLight('#e6efff','#45504e',2.2));
 const keyLight=new THREE.DirectionalLight('#fff2dc',3.1);keyLight.position.set(-75,150,110);scene.add(keyLight);
 const fillLight=new THREE.DirectionalLight('#9ecbe0',1.2);fillLight.position.set(90,80,-90);scene.add(fillLight);
 const board=createBreadboard(scene,mat);
 const teensy=createTeensy(scene,mat),audioShield=createAudioShield(scene,mat),midi=createMidiKeyboard(scene,mat),audioCable=createAudioCable(scene,mat);
 const wires=new THREE.Group();wires.userData.isWireGroup=true;scene.add(wires);
 const cablePoints=(from:THREE.Vector3,to:THREE.Vector3,height:number)=>[from,new THREE.Vector3(from.x+(to.x-from.x)*.3,height,from.z),new THREE.Vector3(from.x+(to.x-from.x)*.72,height,to.z),to];
 const shieldJack=new THREE.Vector3(-22,12.2,17.7),audioPlug=new THREE.Vector3(-22,11,36.5);
 wires.add(wire(scene,cablePoints(shieldJack,audioPlug,22),'#252c30',.8));
 const midiCable=wire(scene,[new THREE.Vector3(-85,11,-3),new THREE.Vector3(-79,22,-6),new THREE.Vector3(-74,26,-4),new THREE.Vector3(-65,9,0)],'#e0a15e',.8);wires.add(midiCable);
 const programmingCable=wire(scene,[new THREE.Vector3(-8,7.7,5),new THREE.Vector3(-4,16,19),new THREE.Vector3(6,21,31),new THREE.Vector3(17,21,41)],'#a7afb1',.6);wires.add(programmingCable);
 const pcLabel=makeLabel('USB PROGRAMMATION','#b9c2c3');pcLabel.position.set(25,22,44);scene.add(pcLabel);
 const groundPlane=new THREE.Mesh(new THREE.PlaneGeometry(460,320),new THREE.MeshStandardMaterial({color:'#171a1b',roughness:1}));groundPlane.rotation.x=-Math.PI/2;groundPlane.position.y=-.4;scene.add(groundPlane);
 const grid=new THREE.GridHelper(360,36,'#343a3b','#202526');grid.position.y=-.25;scene.add(grid);
 const allGroups=[board,teensy,audioShield,midi,audioCable];
 const labels:THREE.Sprite[]=[];scene.traverse(object=>{if(object instanceof THREE.Sprite)labels.push(object);});
 const groupById:Partial<Record<CircuitPartId,THREE.Group>>={breadboard:board,teensy,'audio-shield':audioShield,midi,'line-cable':audioCable};
 const dispose=()=>{
  scene.traverse(object=>{
   const candidate=object as THREE.Mesh;
   if(candidate.geometry)candidate.geometry.dispose();
   if(candidate.material){const assigned=Array.isArray(candidate.material)?candidate.material:[candidate.material];for(const item of assigned){const material=item as THREE.Material & {map?:THREE.Texture};material.map?.dispose();material.dispose();}}
   if(object instanceof THREE.Sprite){(object.material as THREE.SpriteMaterial).map?.dispose();object.material.dispose();}
  });
 };
 return {allGroups,wires,labels,groupById,materials,dispose};
}

export default function CircuitScene3D({selected,wiring,onSelect}:CircuitScene3DProps){
 const hostRef=useRef<HTMLDivElement|null>(null),controllerRef=useRef<SceneController|null>(null),selectRef=useRef(onSelect),modelRef=useRef<ReturnType<typeof buildScene>|null>(null),renderRef=useRef<()=>void>(()=>{});
 const [labelsVisible,setLabelsVisible]=useState(true),[renderError,setRenderError]=useState('');
 selectRef.current=onSelect;

 useEffect(()=>{
  const host=hostRef.current;if(!host)return;
  let renderer:THREE.WebGLRenderer;
  try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});}
  catch{setRenderError('WebGL est indisponible dans ce navigateur. La vue 3D nécessite une accélération graphique activée.');return;}
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));renderer.setClearColor('#111416');renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
 renderer.domElement.className='circuit-webgl-canvas';renderer.domElement.setAttribute('aria-label','Montage 3D interactif : clavier MIDI USB, Teensy 4.1, Audio Shield empilé, breadboard et sortie audio');renderer.domElement.setAttribute('role','img');host.appendChild(renderer.domElement);
  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(42,1,.1,800);camera.position.set(113,102,132);
  const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(-13,5,0);controls.enableDamping=false;controls.enablePan=true;controls.enableZoom=true;controls.minDistance=90;controls.maxDistance=380;controls.maxPolarAngle=Math.PI*.49;controls.minPolarAngle=.06;controls.saveState();
  const built=buildScene(scene);modelRef.current=built;let width=0,height=0;let disposed=false;
  const render=()=>{if(disposed)return;renderer.render(scene,camera);};
  renderRef.current=render;
  const resize=()=>{const boxRect=host.getBoundingClientRect();const nextWidth=Math.max(1,Math.floor(boxRect.width)),nextHeight=Math.max(1,Math.floor(boxRect.height));if(nextWidth===width&&nextHeight===height)return;width=nextWidth;height=nextHeight;camera.aspect=width/height;camera.updateProjectionMatrix();renderer.setSize(width,height,false);render();};
  controls.addEventListener('change',render);
  const observer=new ResizeObserver(resize);observer.observe(host);resize();
  const pointerStart={x:0,y:0};
  const onPointerDown=(event:PointerEvent)=>{pointerStart.x=event.clientX;pointerStart.y=event.clientY;};
  const onPointerUp=(event:PointerEvent)=>{
   if(Math.hypot(event.clientX-pointerStart.x,event.clientY-pointerStart.y)>5)return;
   const rect=renderer.domElement.getBoundingClientRect();const pointer=new THREE.Vector2(((event.clientX-rect.left)/rect.width)*2-1,-((event.clientY-rect.top)/rect.height)*2+1);const raycaster=new THREE.Raycaster();raycaster.setFromCamera(pointer,camera);
   const hits=raycaster.intersectObjects(built.allGroups,true);
   const findPart=(object:THREE.Object3D|undefined):THREE.Object3D|undefined=>!object?undefined:object.userData.pickId||object.userData.partId?object:findPart(object.parent??undefined);
   const found=findPart(hits[0]?.object);
   const part=(found?.userData.pickId??found?.userData.partId) as CircuitPartId|undefined;if(part)selectRef.current(part);
  };
  renderer.domElement.addEventListener('pointerdown',onPointerDown);renderer.domElement.addEventListener('pointerup',onPointerUp);
  controllerRef.current={
   zoom:(factor)=>{const direction=camera.position.clone().sub(controls.target).multiplyScalar(factor);camera.position.copy(controls.target).add(direction);controls.update();},
   reset:()=>{controls.reset();render();},
   fit:()=>{controls.target.set(-13,5,0);camera.position.set(113,102,132);controls.update();render();}
  };
  return ()=>{
   disposed=true;observer.disconnect();controls.removeEventListener('change',render);controls.dispose();renderer.domElement.removeEventListener('pointerdown',onPointerDown);renderer.domElement.removeEventListener('pointerup',onPointerUp);renderer.dispose();built.dispose();renderer.domElement.remove();controllerRef.current=null;modelRef.current=null;renderRef.current=()=>{};
  };
 },[]);

 useEffect(()=>{
  const model=modelRef.current;if(!model)return;
  const parentId=selected==='usb-host'||selected==='usb-data'?'teensy':selected==='wires'?'audio-shield':selected;
  for(const [id,group] of Object.entries(model.groupById)){
   const outline=group?.userData.outline as THREE.Mesh|undefined;
   if(outline)outline.visible=id===parentId;
  }
  renderRef.current();
 },[selected]);

 useEffect(()=>{
  const model=modelRef.current;if(!model)return;
  model.wires.visible=wiring;renderRef.current();
 },[wiring]);

 useEffect(()=>{
  const model=modelRef.current;if(!model)return;
  for(const label of model.labels)label.visible=labelsVisible;
  renderRef.current();
 },[labelsVisible]);

 return <div className="circuit-scene-shell">
  <div ref={hostRef} className="circuit-scene-host" />
  {renderError&&<div className="circuit-webgl-error" role="status">{renderError}</div>}
  {!renderError&&<>
   <div className="circuit-scene-hint">Glisser pour tourner · clic droit pour déplacer · molette pour zoomer</div>
   <div className="circuit-scene-controls" aria-label="Commandes de la vue 3D">
    <button aria-label="Zoom arrière" onClick={()=>controllerRef.current?.zoom(1.18)}><Minus size={15}/></button>
    <button aria-label="Zoom avant" onClick={()=>controllerRef.current?.zoom(.85)}><Plus size={15}/></button>
    <button aria-label="Cadrer le montage" onClick={()=>controllerRef.current?.fit()}><span>CADRER</span></button>
    <button aria-label="Réinitialiser la caméra" onClick={()=>controllerRef.current?.reset()}><RotateCcw size={14}/></button>
    <button className={labelsVisible?'is-active':''} aria-pressed={labelsVisible} aria-label="Afficher ou masquer les étiquettes" onClick={()=>setLabelsVisible(value=>!value)}><Tags size={14}/><span>Labels</span></button>
   </div>
   <div className="circuit-scene-status"><i/> 3D · 2 blocs actifs · firmware calculé</div>
  </>}
  <p className="circuit-scene-description">Maquette 3D manipulable du montage proposé. Les dimensions sont illustratives ; le schéma et la nomenclature restent les références de câblage.</p>
 </div>;
}
