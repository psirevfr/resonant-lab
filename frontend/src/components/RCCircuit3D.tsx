import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

function label(text:string,color='#e6f0e9'){
 const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;const ctx=canvas.getContext('2d');
 if(ctx){ctx.clearRect(0,0,512,128);ctx.font='bold 48px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=color;ctx.shadowColor='#000';ctx.shadowBlur=9;ctx.fillText(text,256,64,490)}
 const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
 const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,transparent:true,depthTest:false}));sprite.scale.set(24,6,1);
 sprite.userData.setText=(next:string)=>{if(!ctx)return;ctx.clearRect(0,0,512,128);ctx.font='bold 48px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=color;ctx.shadowColor='#000';ctx.shadowBlur=9;ctx.fillText(next,256,64,490);texture.needsUpdate=true};
 return sprite;
}

export function RCCircuit3D({resistance,capacitance}:{resistance:number;capacitance:number}){
 const hostRef=useRef<HTMLDivElement|null>(null),valueRef=useRef({resistance,capacitance});const [webglUnavailable,setWebglUnavailable]=useState(false);valueRef.current={resistance,capacitance};
 useEffect(()=>{
  const host=hostRef.current;if(!host)return;let renderer:THREE.WebGLRenderer;
  try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'})}catch{setWebglUnavailable(true);return}
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));renderer.setSize(host.clientWidth,host.clientHeight);renderer.outputColorSpace=THREE.SRGBColorSpace;host.appendChild(renderer.domElement);
  const scene=new THREE.Scene();scene.background=new THREE.Color('#101719');
  const camera=new THREE.PerspectiveCamera(38,host.clientWidth/host.clientHeight,.1,1000);camera.position.set(150,115,175);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.target.set(0,8,0);controls.minDistance=90;controls.maxDistance=390;
  scene.add(new THREE.HemisphereLight('#e5f0ff','#48504a',2));const light=new THREE.DirectionalLight('#fff1d1',3);light.position.set(-80,140,90);scene.add(light);
  const mat=(color:string,roughness=.65,metalness=.05)=>new THREE.MeshStandardMaterial({color,roughness,metalness});
  const board=new THREE.Mesh(new THREE.BoxGeometry(160,5,82),mat('#e4e5dd'));board.position.y=3;board.receiveShadow=true;board.castShadow=true;scene.add(board);
  const railMat=mat('#d34f49');for(const z of [-32,32]){const rail=new THREE.Mesh(new THREE.BoxGeometry(150,.35,.5),railMat);rail.position.set(0,5.7,z);scene.add(rail)}
  const rowMat=mat('#333936');for(let x=-68;x<=68;x+=5.7){for(const z of [-20,-14,-8,8,14,20]){const hole=new THREE.Mesh(new THREE.CylinderGeometry(.8,.8,.3,8),rowMat);hole.position.set(x,5.7,z);scene.add(hole)}}
  // Resistor body and leads; the text label follows the same project values as the schematic.
  const resistor=new THREE.Mesh(new THREE.CylinderGeometry(3,3,22,18),mat('#d8b783'));resistor.rotation.z=Math.PI/2;resistor.position.set(-25,9,-8);scene.add(resistor);
  for(const x of [-42,-8]){const lead=new THREE.Mesh(new THREE.CylinderGeometry(.45,.45,15,8),mat('#c4c9c3',.32,.7));lead.rotation.z=Math.PI/2;lead.position.set(x,7,-8);scene.add(lead)}
  for(const x of [-31,-25,-19]){const band=new THREE.Mesh(new THREE.CylinderGeometry(3.05,3.05,1.25,18),mat(x===-31?'#7a422d':x===-25?'#7b4d27':'#d1b34d'));band.rotation.z=Math.PI/2;band.position.set(x,9,-8);scene.add(band)}
  const capacitor=new THREE.Mesh(new THREE.CylinderGeometry(5,5,13,24),mat('#9b6652'));capacitor.position.set(30,13,8);scene.add(capacitor);
  for(const x of [28,32]){const lead=new THREE.Mesh(new THREE.CylinderGeometry(.45,.45,13,8),mat('#c4c9c3',.32,.7));lead.position.set(x,5,8);scene.add(lead)}
  const wireMat=(c:string)=>new THREE.MeshStandardMaterial({color:c,roughness:.4,metalness:.15});
  const addWire=(points:THREE.Vector3[],color:string)=>{const curve=new THREE.CatmullRomCurve3(points);const mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,24,.7,8,false),wireMat(color));scene.add(mesh)};
  addWire([new THREE.Vector3(-65,8,-8),new THREE.Vector3(-54,22,-8),new THREE.Vector3(-42,8,-8)],'#e1a353');
  addWire([new THREE.Vector3(-8,8,-8),new THREE.Vector3(10,20,-8),new THREE.Vector3(28,8,8)],'#62b8c9');
  addWire([new THREE.Vector3(32,7,8),new THREE.Vector3(43,19,20),new THREE.Vector3(55,7,20)],'#4b5152');
  const resistorLabel=label('R1 · 1 kΩ','#f7dfb6');resistorLabel.position.set(-25,28,-9);scene.add(resistorLabel);
  const capacitorLabel=label('C1 · 1 µF','#f2d6c6');capacitorLabel.position.set(30,30,8);scene.add(capacitorLabel);
  const sourceLabel=label('ÉCHELON 0 → 5 V','#f0c47b');sourceLabel.position.set(-62,26,-22);scene.add(sourceLabel);
  let raf=0,lastR='',lastC='';const render=()=>{controls.update();resistorLabel.position.set(-25,28,-9);capacitorLabel.position.set(30,30,8);sourceLabel.position.set(-62,26,-22);
   // Keep parameter labels in sync with the editable project without rebuilding the scene.
   const rText=`R1 · ${valueRef.current.resistance} Ω`,cText=`C1 · ${valueRef.current.capacitance} F`;
   if(rText!==lastR){resistorLabel.userData.setText(rText);lastR=rText}if(cText!==lastC){capacitorLabel.userData.setText(cText);lastC=cText}
   renderer.render(scene,camera);raf=requestAnimationFrame(render)};render();
  const resize=new ResizeObserver(()=>{if(!host.clientWidth||!host.clientHeight)return;camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();renderer.setSize(host.clientWidth,host.clientHeight)});resize.observe(host);
  return()=>{cancelAnimationFrame(raf);resize.disconnect();controls.dispose();scene.traverse(o=>{const m=o as THREE.Mesh;if(m.geometry)m.geometry.dispose();if(m.material){const mats=Array.isArray(m.material)?m.material:[m.material];for(const x of mats){const material=x as THREE.Material&{map?:THREE.Texture};material.map?.dispose();material.dispose()}}if(o instanceof THREE.Sprite){const material=o.material as THREE.SpriteMaterial;material.map?.dispose();material.dispose()}});renderer.dispose();renderer.domElement.remove()};
 },[]);
 return webglUnavailable?<div className="rc-loading" role="status">WebGL indisponible. Le schéma 2D et la simulation restent accessibles.</div>:<div className="rc-scene" ref={hostRef} aria-label={`Montage 3D RC, résistance ${resistance} ohms, condensateur ${capacitance} farads`} role="img"/>;
}
