import {contactGroup,pins,validateProject,type CircuitProject,type Pin} from './circuitProject';
import {extraDefinition,setting} from './componentExtras';
export type CircuitTrace={engine:string;revision:number;time:number[];signals:Record<string,number[]>;labels:Record<string,string>;raw_points:number};
export function compileCircuit(input:CircuitProject,excitation:'dc'|'step'='dc',duration=.005){
 const p=validateProject(input);if(!Number.isFinite(duration)||duration<1e-6||duration>.1)throw Error('Durée : 1 µs à 100 ms.');
 const parent=new Map<string,string>();
 function root(k:string):string{if(!parent.has(k))parent.set(k,k);const r=parent.get(k)!;if(r!==k)parent.set(k,root(r));return parent.get(k)!}
 const union=(a:string,b:string)=>parent.set(root(a),root(b)),key=(e:Pin)=>e.component+':'+e.pin;
 const grounds=p.parts.filter(a=>a.type==='ground');if(!grounds.length)throw Error('Ajoutez une masse de référence.');for(const g of grounds)union(g.id+':0','ground');
 const bounds:Record<string,[number,number]>={resistor:[1,1e7],potentiometer:[10,2e6],capacitor:[1e-12,1e-3],electrolytic:[1e-9,.01],inductor:[1e-6,1],voltage:[-24,24],ldr:[1000,1e6],ntc:[1000,1e6],tmp36:[-40,125]};
 for(const part of p.parts){const extra=extraDefinition(part.type);if(['uno','teensy41','audioShield'].includes(part.type)||extra?.model===null)throw Error(part.label+' : ce module ou processeur n’est pas émulé. Sa présence ne permet pas de simuler son protocole ou son comportement.');if(part.type==='breadboard'||part.type==='breadboard830')for(const pin of pins(part))union(part.id+':'+pin,part.id+':bus:'+contactGroup(pin,part.railSplit));if(part.type==='button'){union(part.id+':1a',part.id+':1b');union(part.id+':2a',part.id+':2b')}const range=bounds[part.type];if(range&&(part.value<range[0]||part.value>range[1]))throw Error('Valeur hors limites : '+part.label)}
 const touched=new Set<string>();for(const part of p.parts)if(part.mount)for(const [pin,contact] of Object.entries(part.mount.pins)){union(part.id+':'+pin,part.mount.board+':'+contact);touched.add(part.id+':'+pin)}for(const w of p.wires){union(key(w.from),key(w.to));touched.add(key(w.from));touched.add(key(w.to))}
 const touchedRoots=new Set([...touched].map(root)),nodes=new Map<string,string>([[root('ground'),'0']]),labels:Record<string,string>={},links=new Map<string,Set<string>>(),elements:string[]=[];let hasSource=false;
 const node=(id:string,pin:string,label:string)=>{const r=root(id+':'+pin);if(!nodes.has(r))nodes.set(r,'n'+nodes.size);const n=nodes.get(r)!;labels[n]=(labels[n]?labels[n]+' / ':'')+label+' · '+pin;return n};
 p.parts.forEach((part,index)=>{
  if(['ground','breadboard','breadboard830','header'].includes(part.type))return;
  const endpoints=pins(part),required=endpoints.filter(pin=>!(part.type==='potentiometer'&&pin==='W')&&!(part.type==='tmp36'&&pin==='OUT')&&!(part.type==='button'&&['1b','2b'].includes(pin))&&!(part.type==='opamp'&&['1','7'].includes(pin)));
  if(required.some(pin=>!touchedRoots.has(root(part.id+':'+pin))))throw Error('Raccordez toutes les broches de '+part.label+'.');
  const ns=endpoints.map(pin=>node(part.id,pin,part.label)),n=Object.fromEntries(endpoints.map((pin,i)=>[pin,ns[i]])),[a,b]=ns;
  // Ground reachability is a structural diagnostic, not a claim that every
  // active-device input is a conducting resistor.
  for(const x of ns){if(!links.has(x))links.set(x,new Set());for(const y of ns)links.get(x)!.add(y)}
  const resistor=(name:string,a:string,b:string,value:number)=>elements.push(`R${index}${name} ${a} ${b} ${value}`);
  if(part.type==='resistor')resistor('',a,b,part.value);
  else if(['capacitor','electrolytic'].includes(part.type))elements.push(`C${index} ${a} ${b} ${part.value} IC=0`);
  else if(part.type==='voltage'){if(a===b&&part.value!==0)throw Error('Court-circuit d’une alimentation idéale.');hasSource=true;elements.push(`V${index} ${a} ${b} `+(excitation==='dc'?`DC ${part.value}`:`PULSE(0 ${part.value} 0 1n 1n ${duration*2} ${duration*4})`))}
  else if(part.type==='led')elements.push(`D${index} ${a} ${b} LED_RED`);
  else if(part.type==='diode')elements.push(`D${index} ${a} ${b} SIGNAL_EDU`);
  else if(part.type==='inductor'){elements.push(`L${index} ${a} li${index} ${part.value} IC=0`);resistor('coil','li'+index,b,setting(part,'resistance'))}
  else if(part.type==='potentiometer'){const position=setting(part,'position');resistor('top',n['1'],'pw'+index,Math.max(.001,part.value*(1-position)));resistor('bottom','pw'+index,n['3'],Math.max(.001,part.value*position));resistor('wiper','pw'+index,n.W,1)}
  else if(part.type==='button')resistor('contact',n['1a'],n['2a'],setting(part,'closed')===1?.1:1e9);
  else if(part.type==='switch'){resistor('left',n.C,n['1'],setting(part,'position')===0?.1:1e9);resistor('right',n.C,n['2'],setting(part,'position')===1?.1:1e9)}
  else if(part.type==='ldr')resistor('',a,b,Math.max(100,Math.min(1e7,part.value*(setting(part,'lux')/10)**(-setting(part,'gamma')))));
  else if(part.type==='ntc')resistor('',a,b,part.value*Math.exp(setting(part,'beta')*(1/(setting(part,'temperature')+273.15)-1/298.15)));
  else if(part.type==='npn')elements.push(`Q${index} ${n.C} ${n.B} ${n.E} NPN_EDU`);
  else if(part.type==='nmos')elements.push(`M${index} ${n.D} ${n.G} ${n.S} ${n.S} NMOS_EDU L=1u W=1u`);
  else if(part.type==='tmp36'){elements.push(`B${index} t${index} ${n.GND} V=max(0,min(${.5+part.value*.01},v(${n['V+']},${n.GND})-0.05))`);resistor('out','t'+index,n.OUT,1)}
  else if(part.type==='opamp'){for(const [out,inv,non,label] of [['1','2','3','A'],['7','6','5','B']]){elements.push(`B${index}${label} op${index}${label} ${n['4']} V=max(0,min(max(v(${n['8']},${n['4']})-1.5,0),100000*v(${n[non]},${n[inv]})))`);resistor(label,'op'+index+label,n[out],10)}}
 });
 if(!hasSource)throw Error('Ajoutez une alimentation.');const reached=new Set(['0']),pending=['0'];while(pending.length)for(const n of links.get(pending.pop()!)??[])if(!reached.has(n)){reached.add(n);pending.push(n)}if([...nodes.values()].some(n=>!reached.has(n)))throw Error('Réseau flottant : raccordez le sous-circuit à la masse.');const names=[...nodes.values()].filter(n=>n!=='0');if(!names.length||names.length>24)throw Error('Simulation limitée à 24 réseaux mesurés.');
 const netlist=['Resonant local circuit',...elements,'.model LED_RED D(IS=1e-20 N=2 RS=10)','.model SIGNAL_EDU D(IS=2e-9 N=1.8 RS=.6 CJO=4p TT=4n)','.model NPN_EDU NPN(IS=1e-14 BF=100 VAF=100 CJE=4p CJC=3p)','.model NMOS_EDU NMOS(LEVEL=1 VTO=2 KP=.05 LAMBDA=.02 RD=1 RS=1)','.control','set wr_singlescale','set wr_vecnames',`tran ${duration/500} ${duration} uic`,'wrdata /trace.dat '+names.map(n=>`v(${n})`).join(' '),'quit','.endc','.end',''].join('\n');return {netlist,names,labels,revision:p.revision};
}
export async function runWasm(create:(options:Record<string,unknown>)=>Promise<any>,input:ReturnType<typeof compileCircuit>):Promise<CircuitTrace>{
 const m=await create({noInitialRun:true,print:()=>{},printErr:()=>{}});
 // This port queries Linux /proc to size output buffers. MEMFS has no host
 // memory information: declare a conservative virtual budget, never user RAM.
 m.FS.writeFile('/proc/meminfo','MemTotal: 262144 kB\nMemFree: 65536 kB\nMemAvailable: 65536 kB\nBuffers: 0 kB\nCached: 0 kB\n');m.FS.writeFile('/circuit.cir',input.netlist);
 const args=['ngspice','-b','/circuit.cir'],argv=m.stackAlloc((args.length+1)*4);args.forEach((s,i)=>{const p=m.stackAlloc(s.length+1);m.stringToUTF8(s,p,s.length+1);m.HEAPU32[argv/4+i]=p});m.HEAPU32[argv/4+args.length]=0;
 try{m._main(args.length,argv)}catch(e){if((e as {status?:number}).status!==0)throw Error('ngspice WebAssembly n’a pas résolu ce circuit.')}
 let text:string;try{text=m.FS.readFile('/trace.dat',{encoding:'utf8'})}catch{throw Error('Aucune trace issue du solveur.')}if(text.length>4_000_000)throw Error('Trace trop volumineuse.');const lines=text.trim().split('\n');const rows=lines.slice(1).map(line=>line.trim().split(/\s+/).map(Number));if(!rows.length||rows.length>4000||rows.some(r=>r.length!==input.names.length+1||!r.every(Number.isFinite)))throw Error('Trace numérique invalide.');const chosen=rows.length<=513?rows:Array.from({length:513},(_,i)=>rows[Math.round(i*(rows.length-1)/512)]);return {engine:'ngspice 46 · WebAssembly local',revision:input.revision,time:chosen.map(r=>r[0]),signals:Object.fromEntries(input.names.map((n,i)=>[n,chosen.map(r=>r[i+1])])),labels:input.labels,raw_points:rows.length};
}
