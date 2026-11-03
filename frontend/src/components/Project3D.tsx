import {useEffect,useRef} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {definitions,pins,pinOffset,pinPoint,type CircuitProject,type Pin} from '../circuitProject';

export default function Project3D({project,selected,onSelect,onPin,onMove,onUnavailable}:{project:CircuitProject;selected:string;onSelect:(id:string)=>void;onPin:(pin:Pin)=>void;onMove:(id:string,x:number,z:number)=>void;onUnavailable:()=>void}){
 const host=useRef<HTMLDivElement>(null),cameraState=useRef<{position:THREE.Vector3;target:THREE.Vector3}|null>(null),actions=useRef({onSelect,onPin,onMove,onUnavailable});actions.current={onSelect,onPin,onMove,onUnavailable};
 useEffect(()=>{
  const el=host.current;if(!el)return;let renderer:THREE.WebGLRenderer;
  try{renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'low-power'})}catch{actions.current.onUnavailable();return}
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));el.appendChild(renderer.domElement);
  const scene=new THREE.Scene();scene.background=new THREE.Color('#111719');const camera=new THREE.PerspectiveCamera(42,1,.1,1500);camera.position.set(100,155,200);
  const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,0,20);controls.minDistance=45;controls.maxDistance=650;controls.enableDamping=true;
  if(cameraState.current){camera.position.copy(cameraState.current.position);controls.target.copy(cameraState.current.target)}else if(project.parts.length){const bounds=new THREE.Box3();for(const p of project.parts)bounds.expandByPoint(new THREE.Vector3(p.px,5,p.z));bounds.expandByScalar(45);const center=bounds.getCenter(new THREE.Vector3()),size=bounds.getSize(new THREE.Vector3()),distance=Math.max(120,Math.max(size.x,size.z)*1.7);controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(.4,.65,.8).normalize().multiplyScalar(distance));camera.far=Math.max(1500,distance*5);controls.maxDistance=Math.max(650,distance*3)}
  scene.add(new THREE.HemisphereLight('#ecf5ff','#314138',2.6));const light=new THREE.DirectionalLight('#fff4dd',3);light.position.set(-80,160,80);scene.add(light);scene.add(new THREE.GridHelper(600,60,'#34463f','#202b29'));
  const picks:THREE.Object3D[]=[],groups=new Map<string,THREE.Group>();
  const mat=(color:string)=>new THREE.MeshStandardMaterial({color,roughness:.62,metalness:.12});
  function box(group:THREE.Group,x:number,y:number,z:number,color:string){const mesh=new THREE.Mesh(new THREE.BoxGeometry(x,y,z),mat(color));group.add(mesh);picks.push(mesh);return mesh}
  function label(group:THREE.Group,text:string){const canvas=document.createElement('canvas');canvas.width=512;canvas.height=96;const ctx=canvas.getContext('2d');if(ctx){ctx.font='600 30px system-ui';ctx.fillStyle='#e8eee8';ctx.textAlign='center';ctx.fillText(text.slice(0,44),256,52,500)}const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false}));sprite.scale.set(42,8,1);sprite.position.y=20;group.add(sprite)}
  for(const part of project.parts){const group=new THREE.Group();group.position.set(part.px,5,part.z);group.rotation.y=-part.rotation*Math.PI/180;group.userData.id=part.id;scene.add(group);groups.set(part.id,group);
   if(part.type==='breadboard'){box(group,68,5,78,'#e6e4da');const groove=box(group,64,.4,3,'#a2aaa1');groove.position.y=2.7}
   else if(part.type==='resistor'){const body=new THREE.Mesh(new THREE.CylinderGeometry(3.5,3.5,19,16),mat('#c9a976'));body.rotation.z=Math.PI/2;group.add(body);picks.push(body);for(const x of [-5,0,5]){const band=box(group,1,7.1,7.1,x===5?'#ae8b32':'#584029');band.position.x=x}}
   else if(part.type==='capacitor'){const body=new THREE.Mesh(new THREE.CylinderGeometry(6,6,14,20),mat('#4f7e9c'));body.position.y=5;group.add(body);picks.push(body)}
   else if(part.type==='led'){const body=new THREE.Mesh(new THREE.SphereGeometry(5,20,16),new THREE.MeshStandardMaterial({color:'#bd493d',transparent:true,opacity:.9,roughness:.3}));body.position.y=6;group.add(body);picks.push(body)}
   else if(part.type==='voltage'){box(group,26,13,24,'#43576a');label(group,part.label+' · '+part.value+' V')}
   else if(part.type==='uno'){box(group,40,3,60,'#287b79');const chip=box(group,12,3,27,'#182121');chip.position.y=4}
   else box(group,8,2,8,'#a7b4a2');
   if(part.type!=='voltage')label(group,part.label+(definitions[part.type].unit?' · '+part.value+' '+definitions[part.type].unit:''));
   for(const pin of pins(part)){const [x,z]=pinOffset(part,pin);const marker=new THREE.Mesh(new THREE.SphereGeometry(part.type==='breadboard'?.8:1.7,8,6),mat(part.id===selected?'#b5ec87':'#d3b763'));marker.position.set(x,part.type==='breadboard'?3:1,z);marker.userData.pin={component:part.id,pin};group.add(marker);picks.push(marker)}
   if(part.id===selected){const bounds=new THREE.BoxHelper(group,0xb5ec87);scene.add(bounds)}
  }
  for(const wire of project.wires){const a=project.parts.find(p=>p.id===wire.from.component),b=project.parts.find(p=>p.id===wire.to.component);if(!a||!b)continue;const [ax,az]=pinPoint(a,wire.from.pin),[bx,bz]=pinPoint(b,wire.to.pin);const curve=new THREE.CatmullRomCurve3([new THREE.Vector3(ax,8,az),new THREE.Vector3(ax,18,az),new THREE.Vector3(bx,18,bz),new THREE.Vector3(bx,8,bz)]);scene.add(new THREE.Mesh(new THREE.TubeGeometry(curve,20,.7,6,false),mat('#6db9bc')))}
  const ray=new THREE.Raycaster(),pointer=new THREE.Vector2(),plane=new THREE.Plane(new THREE.Vector3(0,1,0),-5);let drag:{id:string;offset:THREE.Vector3}|null=null;
  const point=(e:PointerEvent)=>{const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera)};
  const down=(e:PointerEvent)=>{point(e);const hit=ray.intersectObjects(picks,false)[0];if(!hit)return;let obj:THREE.Object3D| null=hit.object;if(obj.userData.pin){actions.current.onPin(obj.userData.pin);return}while(obj&&!obj.userData.id)obj=obj.parent;if(!obj)return;if(e.shiftKey){const pos=ray.ray.intersectPlane(plane,new THREE.Vector3());if(pos){drag={id:obj.userData.id,offset:pos.clone().sub(obj.position)};controls.enabled=false;renderer.domElement.setPointerCapture(e.pointerId)}}else actions.current.onSelect(obj.userData.id)};
  const move=(e:PointerEvent)=>{if(!drag)return;point(e);const pos=ray.ray.intersectPlane(plane,new THREE.Vector3());const group=groups.get(drag.id);if(pos&&group){pos.sub(drag.offset);group.position.x=Math.round(pos.x/2.5)*2.5;group.position.z=Math.round(pos.z/2.5)*2.5;requestDraw()}};
  const up=()=>{if(drag){const group=groups.get(drag.id)!,id=drag.id;drag=null;actions.current.onMove(id,group.position.x,group.position.z);actions.current.onSelect(id)}controls.enabled=true};
  const cancel=()=>{drag=null;controls.enabled=true;for(const part of project.parts)groups.get(part.id)?.position.set(part.px,5,part.z);requestDraw()};
  renderer.domElement.addEventListener('pointerdown',down);renderer.domElement.addEventListener('pointermove',move);renderer.domElement.addEventListener('pointerup',up);renderer.domElement.addEventListener('pointercancel',cancel);renderer.domElement.addEventListener('lostpointercapture',cancel);
  let frame=0;const draw=()=>{frame=0;controls.update();renderer.render(scene,camera)},requestDraw=()=>{if(!frame)frame=requestAnimationFrame(draw)};controls.addEventListener('change',requestDraw);const size=()=>{if(!el.clientWidth||!el.clientHeight)return;renderer.setSize(el.clientWidth,el.clientHeight);camera.aspect=el.clientWidth/el.clientHeight;camera.updateProjectionMatrix();requestDraw()};const observer=new ResizeObserver(size);observer.observe(el);size();
  return()=>{cameraState.current={position:camera.position.clone(),target:controls.target.clone()};cancelAnimationFrame(frame);observer.disconnect();controls.dispose();scene.traverse(obj=>{const mesh=obj as THREE.Mesh;if(mesh.geometry)mesh.geometry.dispose();if(mesh.material)for(const m of Array.isArray(mesh.material)?mesh.material:[mesh.material]){(m as THREE.MeshStandardMaterial).map?.dispose();m.dispose()}});renderer.dispose();renderer.domElement.remove()};
 },[project.parts,project.wires,selected]);
 return <div className="project-three" ref={host} role="img" aria-label="Montage 3D interactif. Sélection par clic ; déplacement Maj et glisser, ou propriétés de position. Cliquez deux broches pour les relier."/>;
}
