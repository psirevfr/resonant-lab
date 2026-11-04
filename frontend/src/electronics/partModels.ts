import {extraDefinition,setting} from '../componentExtras';
import * as THREE from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {pins,pinOffset,type Part} from '../circuitProject';
import {isBoard} from '../physicalLayout';

const metal=()=>new THREE.MeshStandardMaterial({color:'#c6cbcb',metalness:.82,roughness:.26});
const material=(color:string,roughness=.6,metalness=.05)=>new THREE.MeshStandardMaterial({color,roughness,metalness});
export const digitColors=['#151412','#67412b','#c83731','#e78527','#e4c849','#3b8b47','#3274b2','#9a5da9','#969a99','#ece9da'];
export function resistorBands(value:number){if(!Number.isFinite(value)||value<=0)return ['#888','#888','#888','#888','#67412b'];let exponent=Math.floor(Math.log10(value))-2,n=Math.round(value/10**exponent);if(n===1000){n=100;exponent++}return [...String(n).padStart(3,'0')].map(c=>digitColors[+c]).concat(exponent===-2?'#aeb4b7':exponent===-1?'#c9a356':digitColors[exponent]??'#888','#67412b')}
function box(parent:THREE.Object3D,size:number[],position:number[],color:string,round=0){const mesh=new THREE.Mesh(round?new RoundedBoxGeometry(size[0],size[1],size[2],2,round):new THREE.BoxGeometry(size[0],size[1],size[2]),material(color));mesh.position.set(position[0],position[1],position[2]);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh}
function cylinder(parent:THREE.Object3D,r:number,height:number,position:number[],mat:THREE.Material){const m=new THREE.Mesh(new THREE.CylinderGeometry(r,r,height,20),mat);m.position.set(position[0],position[1],position[2]);m.castShadow=true;parent.add(m);return m}
function lead(parent:THREE.Object3D,points:number[][],radius=.3){const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p as [number,number,number])));const m=new THREE.Mesh(new THREE.TubeGeometry(curve,16,radius,6,false),metal());m.castShadow=true;parent.add(m)}
function decal(parent:THREE.Object3D,w:number,h:number,y:number,draw:(c:CanvasRenderingContext2D)=>void,resolution=1024){const canvas=document.createElement('canvas');canvas.width=resolution;canvas.height=Math.round(resolution*h/w);const c=canvas.getContext('2d')!;c.scale(canvas.width/w,canvas.height/h);c.translate(w/2,h/2);draw(c);const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=4;const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-1}));m.rotation.x=-Math.PI/2;m.position.y=y;parent.add(m);return m}
function board(parent:THREE.Group,part:Part){
 const full=part.type==='breadboard830',w=full?165.1:31,h=full?54.6:43,top=full?8.5:5;
 box(parent,[w,top,h],[0,top/2,0],'#dddcd4',.9);box(parent,[w-.6,.6,h-.6],[0,top-.2,0],'#f6f5ed',.3);
 box(parent,[w-6,.18,2.5],[0,top+.12,0],'#b9bbb3');
 // All sockets correspond to actual business pins; the two instanced meshes
 // keep 830 contacts inexpensive without using downloaded model assets.
 const names=pins(part),rim=new THREE.InstancedMesh(new THREE.BoxGeometry(1.25,.15,1.25),material('#b7b9b2'),names.length),holes=new THREE.InstancedMesh(new THREE.BoxGeometry(.85,.18,.85),material('#292c28'),names.length),dummy=new THREE.Object3D();
 names.forEach((pin,i)=>{const [x,z]=pinOffset(part,pin);dummy.position.set(x,top+.1,z);dummy.updateMatrix();rim.setMatrixAt(i,dummy.matrix);dummy.position.y=top+.16;dummy.updateMatrix();holes.setMatrixAt(i,dummy.matrix)});holes.userData.pinNames=names;rim.userData.pinNames=names;parent.add(rim,holes);
 decal(parent,w-.8,h-.8,top+.28,c=>{c.lineWidth=.18;c.font='1.5px monospace';c.textAlign='center';c.textBaseline='middle';const count=full?63:10;for(let n=1;n<=count;n++){if(n!==1&&n%5!==0&&n!==count)continue;const [x]=pinOffset(part,'a'+n);c.fillStyle='#767b71';c.fillText(String(n),x,full?-18.0:-13.7);c.fillText(String(n),x,full?18.0:13.7)}for(const row of 'abcdefghij'){const [,z]=pinOffset(part,row+'1');c.fillStyle='#74796e';c.fillText(row.toUpperCase(),-w/2+1.9,z);c.fillText(row.toUpperCase(),w/2-1.9,z)}if(full){for(const [z,color,label] of [[-26,'#c34d44','+'],[-19.8,'#436f9d','−'],[19.8,'#c34d44','+'],[26,'#436f9d','−']] as const){c.strokeStyle=color;c.fillStyle=color;c.beginPath();c.moveTo(-77,z);c.lineTo(77,z);c.stroke();c.fillText(label,-80,z)}c.font='1.1px monospace';c.fillStyle='#909388';c.fillText('830 · 2.54 mm',0,.1);if(part.railSplit){c.clearRect(-1.5,-27,3,9);c.clearRect(-1.5,19,3,9)}}},2048);
 // Small moulded side tabs make the board silhouette recognisable.
 for(const x of [-w/2,w/2])for(const z of [-12,12])box(parent,[1.3,1.2,4],[x,3,z],'#d5d6cc',.2);
}
function header(parent:THREE.Group,count:number,x:number,z:number,pitch=2.54){box(parent,[count*pitch,8.5,2.6],[x+(count-1)*pitch/2,5.5,z],'#20221f',.25);for(let i=0;i<count;i++){box(parent,[1.1,.1,1.1],[x+i*pitch,9.8,z],'#090b0b');box(parent,[.45,2,.45],[x+i*pitch,1,z],'#bba46d')}}
function pcb(parent:THREE.Group,part:Part){const kind=part.type;
 const uno=kind==='uno',teensy=kind==='teensy41',w=uno?68.6:teensy?61:43.2,h=uno?53.4:teensy?17.8:35.6,color=uno?'#167b83':teensy?'#277a53':'#246b81';
 box(parent,[w,1.6,h],[0,1.8,0],color,.8);
 decal(parent,w-1,h-1,2.63,c=>{c.strokeStyle=uno?'#3d9ca0':'#489574';c.lineWidth=.18;for(let i=0;i<18;i++){const x=-w*.4+i*w*.045;c.beginPath();c.moveTo(x,-h*.35);c.lineTo(x+2,-h*.12);c.lineTo(x+5,h*.35);c.stroke()}c.fillStyle='#dce8de';c.font='bold '+(uno?'4':'2.6')+'px sans-serif';c.textAlign='center';c.fillText(uno?'UNO':teensy?'TEENSY 4.1':'AUDIO SHIELD',uno?-9:0,uno?1:0);c.font='1.3px monospace';c.fillText(uno?'ATmega328P · REV3':teensy?'USB HOST · i.MX RT1062':'SGTL5000 · Rev D2',0,uno?-4:3);if(uno){c.font='1.1px monospace';for(const pin of pins(part)){const [x,z]=pinOffset(part,pin);c.save();c.translate(x,z+(z<0?3.8:-3.8));c.rotate(Math.PI/2);c.fillText(pin.replace('GND2','GND').replace('GND3','GND'),0,0);c.restore()}c.fillText('POWER',-10,19.3);c.fillText('ANALOG IN',20,19.3)}},1024);
 for(const [x,z] of [[-w/2+3,-h/2+3],[w/2-3,-h/2+3],[-w/2+3,h/2-3],[w/2-3,h/2-3]]){const ring=new THREE.Mesh(new THREE.RingGeometry(1.2,1.9,20),metal());ring.rotation.x=-Math.PI/2;ring.position.set(x,2.7,z);parent.add(ring);cylinder(parent,1.15,1.7,[x,1.8,z],material('#161916'))}
 if(uno){
  header(parent,10,-17.4,-23.4);header(parent,8,11.2,-23.4);header(parent,8,-16,23.4);header(parent,6,15.2,23.4);
  box(parent,[35.6,3.7,7.6],[9,4.5,9],'#202423',.4);for(let i=0;i<14;i++)for(const z of [4.4,13.6])box(parent,[.5,1.6,1.6],[-7.5+i*2.54,3.3,z],'#b6beb9');
  decal(parent,32,6,6.4,c=>{c.fillStyle='#868c85';c.textAlign='center';c.font='1.2px monospace';c.fillText('ATMEGA328P',8,1)});
  const usb=box(parent,[16,12,12],[-28,8.5,-12],'#c0c5c3',.4);(usb.material as THREE.MeshStandardMaterial).metalness=.85;box(parent,[.15,8.8,8.5],[-36.1,8.7,-12],'#252b2a',.8);box(parent,[.2,3,6],[-36.2,7.2,-12],'#babdb6');
  const jack=cylinder(parent,4.8,12,[-29,7.4,15],material('#181b19'));jack.rotation.z=Math.PI/2;const opening=cylinder(parent,3.1,.4,[-35.3,7.4,15],material('#060706'));opening.rotation.z=Math.PI/2;
  for(const z of [9,19]){cylinder(parent,2.8,10,[-15,7.6,z],material('#252d29'));cylinder(parent,2.65,.25,[-15,12.7,z],metal());box(parent,[3,.12,.3],[-15,12.9,z],'#777f79')}
  box(parent,[7.5,1.5,7.5],[-13,3.4,-10],'#222825');box(parent,[4,2,3],[-24,3.8,-21],'#c1c4bd');cylinder(parent,1.1,.6,[-24,5.1,-21],material('#b63832'));
  for(let i=0;i<12;i++){const x=-5+i*2.7,z=-11+(i%3)*3.5;box(parent,[1.8,.9,.9],[x,3.2,z],i%2?'#ccc7ae':'#252a26')}
  box(parent,[2.2,1.1,1.2],[26,3.3,-16],'#b1ad42');
 }else{
  header(parent,teensy?24:14,-w/2+2.5,-h/2+1.6);header(parent,teensy?24:14,-w/2+2.5,h/2-1.6);
  box(parent,[teensy?10:7,1.5,teensy?10:7],[0,3.3,0],'#222a25');
  const port=box(parent,[7,3.5,6],[-w/2+2,4.2,0],'#c6cbc8',.4);(port.material as THREE.MeshStandardMaterial).metalness=.85;box(parent,[.2,2,4],[-w/2-1.6,4.2,0],'#151b18');
  if(teensy){box(parent,[13,2.8,13],[w/2-7,3.9,0],'#b6bdb9');for(let i=0;i<5;i++)cylinder(parent,.6,.2,[-15+i*2.54,2.8,2.5],material('#c9b363'))}
  else{box(parent,[12,5,11],[w/2-5,4.9,7],'#1b201e');const jack=cylinder(parent,2,.4,[w/2+1.2,5,7],material('#0a0c0a'));jack.rotation.z=Math.PI/2;box(parent,[13,2,13],[-4,3.7,-4],'#9fa9a4')}
 }
}
function extraModel(group:THREE.Group,part:Part){
 const type=part.type;
 const legs=(height=3)=>{for(const pin of pins(part)){const [x,z]=pinOffset(part,pin);lead(group,[[x*.65,height,z*.65],[x,height*.4,z],[x,0,z]],.25)}};
 const text=(label:string,w:number,h:number,y:number,color='#d9dfce')=>decal(group,w,h,y,c=>{c.fillStyle=color;c.font='bold '+Math.min(2,w/Math.max(1,label.length)*1.4)+'px monospace';c.textAlign='center';c.fillText(label,0,.6)});
 if(type==='potentiometer'){box(group,[6.6,5,7],[0,4.5,0],'#226cb6',.5);legs(2.5);cylinder(group,2.5,1,[0,7.4,0],material('#d6dfd6'));const slot=box(group,[3.4,.16,.55],[0,8,0],'#32413e');slot.rotation.y=(setting(part,'position')-.5)*Math.PI*4/3;text('103',5,2.5,7.95,'#243948')}
 else if(type==='inductor'){class Helix extends THREE.Curve<THREE.Vector3>{constructor(){super()}getPoint(t:number){return new THREE.Vector3((t-.5)*9,4+Math.sin(t*Math.PI*16)*2.8,Math.cos(t*Math.PI*16)*2.8)}}group.add(new THREE.Mesh(new THREE.TubeGeometry(new Helix(),160,.4,8,false),material('#c88a42',.3,.65)));for(const sign of [-1,1])lead(group,[[sign*4.5,4,2.8],[sign*6,3,0],[sign*7.62,0,0]])}
 else if(type==='electrolytic'){const mat=material('#254f72',.38);cylinder(group,3,11,[0,7,0],mat);cylinder(group,2.85,.2,[0,12.6,0],metal());box(group,[3.5,.1,.18],[0,12.75,0],'#707c7b');box(group,[.18,.1,3.5],[0,12.75,0],'#707c7b');box(group,[1.2,8,.2],[1.6,7,2.7],'#b3bec8');for(let y=4;y<=10;y+=2)box(group,[.7,.15,.05],[1.6,y,2.85],'#1c3348');legs(2)}
 else if(type==='diode'){const body=cylinder(group,.95,3.8,[0,3.4,0],new THREE.MeshPhysicalMaterial({color:'#d48943',transparent:true,opacity:.86,roughness:.2,clearcoat:1}));body.rotation.z=Math.PI/2;const band=cylinder(group,.98,.55,[1.15,3.4,0],material('#272b27'));band.rotation.z=Math.PI/2;for(const sign of [-1,1])lead(group,[[sign*1.9,3.4,0],[sign*4,2.8,0],[sign*5.08,0,0]],.23)}
 else if(type==='button'){box(group,[6.5,2.5,6],[0,3.2,0],'#252a27',.3);box(group,[6.2,.5,5.7],[0,4.7,0],'#b5bcb4',.2);cylinder(group,1.7,setting(part,'closed')?1:2,[0,setting(part,'closed')?5.2:5.7,0],material('#303b33'));legs(2.5)}
 else if(type==='switch'){box(group,[8,4,5],[0,4,0],'#aeb5ae',.4);const lever=new THREE.Group();lever.position.y=6;lever.rotation.z=setting(part,'position')?-.45:.45;cylinder(lever,.8,5,[0,2.5,0],metal());cylinder(lever,1.2,2,[0,5,0],material('#2e3530'));group.add(lever);legs(2)}
 else if(type==='ldr'){cylinder(group,3.1,1,[0,4.1,0],material('#ba9c65'));legs(3.7);decal(group,5.8,5.8,4.7,c=>{c.strokeStyle='#915a35';c.lineWidth=.35;c.beginPath();c.moveTo(-2.3,-2);for(let i=0;i<7;i++)c.lineTo(i%2?2.2:-2.2,-1.8+i*.6);c.stroke()})}
 else if(type==='ntc'){const bead=new THREE.Mesh(new THREE.SphereGeometry(1.8,18,12),material('#4c3a24',.3));bead.position.y=3.7;group.add(bead);legs(3.5)}
 else if(['npn','nmos','tmp36'].includes(type)){box(group,[4.7,4.5,3.6],[0,4.6,0],'#232a26',.7);legs(2.8);text(type==='npn'?'3904':type==='nmos'?'BS170':'TMP36',4.3,2.7,6.9)}
 else if(type==='opamp'){box(group,[9.6,3.6,6.2],[0,4.5,0],'#252a26',.5);for(const pin of pins(part)){const [x,z]=pinOffset(part,pin);lead(group,[[x,4,Math.sign(z)*2.8],[x,3.4,z],[x,0,z]],.25)}text('LM358',8.5,5,6.4);cylinder(group,.5,.1,[-3.5,6.4,-2.1],material('#b6bea7'))}
 else if(type==='header'){box(group,[10,2.5,2.5],[0,2,0],'#252a23',.2);for(const pin of pins(part)){const [x,z]=pinOffset(part,pin);box(group,[.6,7,.6],[x,3.5,z],'#cfb26c')}}
 else if(type==='buzzer'){cylinder(group,8,9,[0,5.5,0],material('#202923'));cylinder(group,1.6,.25,[0,10.2,0],material('#030804'));text('+',3,2,10.25);legs(2)}
 else if(type==='ultrasonic'){box(group,[45,1.6,20],[0,2,0],'#277d86',.5);for(const x of [-11,11]){const metalBody=cylinder(group,8,12,[x,10,0],metal());metalBody.rotation.x=Math.PI/2;const face=cylinder(group,6.7,.2,[x,10,6.2],material('#3d443e'));face.rotation.x=Math.PI/2;for(let i=-5;i<=5;i+=2)box(group,[11,.22,.2],[x,10+i,6.4],'#a0aaa1')}for(const pin of pins(part)){const [x,z]=pinOffset(part,pin);box(group,[.6,5,.6],[x,2.5,z],'#cfb26c')}text('HC-SR04',24,4,2.9)}
 else if(type==='dht22'){box(group,[15,22,7],[0,14,0],'#e5e7de',1);for(let i=0;i<9;i++)box(group,[11,.6,.15],[0,6+i*2,3.6],'#778679');legs(4);text('DHT22',12,5,25.1,'#596451')}
 else if(type==='oled'){box(group,[26,1.6,27],[0,2,0],'#2d6b89',.5);box(group,[22,.8,17],[0,3.2,1],'#080d11',.4);for(const pin of pins(part)){const [x,z]=pinOffset(part,pin);cylinder(group,.6,1,[x,2.8,z],material('#b3a15c'));lead(group,[[x,2.8,z],[x,0,z]],.25)}text('OLED I2C',20,4,2.9)}
 else if(type==='servo'){box(group,[23,21,12],[0,11,0],'#2c62a8',1);box(group,[30,2,12],[0,17,0],'#3069a9',.4);cylinder(group,3,3,[6,23,0],material('#d2d7c9'));box(group,[21,1.2,3],[6,25,0],'#e9e8d9',.6);for(const [i,pin] of pins(part).entries()){const [x,z]=pinOffset(part,pin);const points=[[0,4,6],[x,2,10],[x,.4,z]];const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p as [number,number,number])));group.add(new THREE.Mesh(new THREE.TubeGeometry(curve,12,.45,6,false),material(['#393127','#cb4d35','#d7a34d'][i])))}text('SG90',14,5,21.6)}
 else if(type==='motor'){const can=cylinder(group,8.5,24,[0,9.5,0],metal());can.rotation.z=Math.PI/2;const shaft=cylinder(group,1.1,9,[16,9.5,0],metal());shaft.rotation.z=Math.PI/2;for(const pin of pins(part)){const [x,z]=pinOffset(part,pin);lead(group,[[-12,8,z],[x,3,z],[x,0,z]],.35)}for(let i=0;i<3;i++)box(group,[4,.2,3],[i*5-5,18.1,0],'#3b4641')}
}
export function buildPartModel(part:Part){
 const group=new THREE.Group();group.userData.part=part.id;
 if(isBoard(part))board(group,part);
 else if(['uno','teensy41','audioShield'].includes(part.type))pcb(group,part);
 else if(extraDefinition(part.type))extraModel(group,part);
 else if(part.type==='resistor'){
  const body=cylinder(group,1.25,6.5,[0,4.2,0],material('#79a8ba',.5));body.rotation.z=Math.PI/2;
  resistorBands(part.value).forEach((color,i)=>{const ring=cylinder(group,1.27,.36,[-2.3+i*1.02+(i===4?.4:0),4.2,0],material(color,.45));ring.rotation.z=Math.PI/2});
  for(const sign of [-1,1])lead(group,[[sign*3.25,4.2,0],[sign*5.7,4.2,0],[sign*7.62,2.5,0],[sign*7.62,0,0]],.29);
 }else if(part.type==='capacitor'){
  box(group,[7.2,8.5,4.5],[0,6.7,0],'#bd3c2e',.4);for(const x of [-2.54,2.54])lead(group,[[x,2.8,0],[x,0,0]],.25);
  decal(group,6.8,4.2,11.01,c=>{c.font='bold 1.2px monospace';c.fillStyle='#e5d1bd';c.textAlign='center';c.fillText('FILM',0,-.5);c.font='1px monospace';c.fillText((part.value*1e6).toPrecision(2)+' µF',0,1)});
 }else if(part.type==='led'){
  const resin=new THREE.MeshPhysicalMaterial({color:'#d9422c',roughness:.2,metalness:0,transparent:true,opacity:.8,clearcoat:1});cylinder(group,2.5,4.5,[0,6.5,0],resin);const dome=new THREE.Mesh(new THREE.SphereGeometry(2.5,24,12,0,Math.PI*2,0,Math.PI/2),resin);dome.position.y=8.7;group.add(dome);cylinder(group,2.9,.8,[0,4.4,0],resin);for(const x of [-1.27,1.27])lead(group,[[x,5.6,0],[x,0,0]],.25);box(group,[1.4,1.5,1],[.7,5.8,0],'#aeb4a5');
 }else if(part.type==='voltage'){
  box(group,[29,17,23],[0,8.5,0],'#b4b6ae',1);box(group,[25,.4,19],[0,17.15,0],'#323b35',.6);decal(group,18,8,17.4,c=>{c.fillStyle='#16231d';c.fillRect(-9,-4,18,8);c.font='bold 3.3px monospace';c.fillStyle='#a8dfbd';c.textAlign='center';c.fillText(part.value.toFixed(2)+'V',0,1)});for(const [i,pin] of pins(part).entries()){const [x,z]=pinOffset(part,pin);cylinder(group,1.7,2,[x,1,z],material(i?'#262c28':'#c84637'));cylinder(group,.75,.3,[x,2.1,z],metal())}
 }else{
  box(group,[6,.6,5],[0,.3,0],'#c5b777',.4);cylinder(group,.8,2,[0,1.2,0],metal());
 }
 // A connector marker is visible only while wiring/hovering. It is not a
 // decorative sphere obscuring the real component body in the normal view.
 return group;
}
