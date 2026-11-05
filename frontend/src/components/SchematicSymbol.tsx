import {setting} from '../componentExtras';
import type {Part} from '../circuitProject';
import {symbolLayout} from '../schematicLayout';

/** Original SVG symbols; no CircuitJS source or artwork is incorporated. */
export default function SchematicSymbol({part}:{part:Part}){
 const l=symbolLayout({...part,schematicRotation:0}),t=part.type;let drawing;
 if(t==='junction')drawing=<circle cx="0" cy="0" r="4" fill="currentColor" stroke="none"/>;
 else if(t==='ground')drawing=<path d="M32 0v28m-24 0h48M16 36h32M24 44h16"/>;
 else if(['resistor','ldr','ntc'].includes(t))drawing=<><path d="M0 64h36M92 64h36"/><rect x="36" y="54" width="56" height="20"/>{t==='ldr'&&<path d="m46 22 18 18m-7 0h7v-7m5-15 18 18m-7 0h7v-7"/>}{t==='ntc'&&<path d="m34 84 61-40h8"/>}</>;
 else if(t==='potentiometer')drawing=<><path d="M0 80h36M92 80h36M64 0v57m-6-6 6 6 6-6"/><rect x="36" y="70" width="56" height="20"/></>;
 else if(t==='capacitor'||t==='electrolytic')drawing=<><path d="M64 0v55M40 55h48M40 73h48M64 73v55"/>{t==='electrolytic'&&<path d="M91 39v12m-6-6h12"/>}</>;
 else if(t==='inductor')drawing=<path d="M0 64h24c0-28 20-28 20 0c0-28 20-28 20 0c0-28 20-28 20 0c0-28 20-28 20 0h24"/>;
 else if(t==='voltage')drawing=<><path d="M64 0v40M64 88v40"/><circle cx="64" cy="64" r="24"/><path d="M58 53h12M64 47v12M58 76h12"/></>;
 else if(t==='diode'||t==='led')drawing=<><path d="M0 64h44M84 64h44M44 48l32 16-32 16ZM80 46v36"/>{t==='led'&&<path d="m80 32 14-14m-7 0h7v7m-1 14 14-14m-7 0h7v7"/>}</>;
 else if(t==='npn')drawing=<><circle cx="67" cy="64" r="32"/><path d="M0 64h52M52 42v44M52 51l38-24h38V16M52 77l38 24h38v11m-48-23 8 10-13-2"/></>;
 else if(t==='nmos')drawing=<><circle cx="68" cy="64" r="32"/><path d="M0 64h44M44 40v48M53 38v52M53 45h37V16h38M53 83h37v29h38M90 45v38"/></>;
 else if(t==='button')drawing=<><path d="M0 32h28v64H0M128 32h-28v64h28M28 64h18M82 64h18M64 21v18M52 21h24"/><circle cx="46" cy="64" r="3"/><circle cx="82" cy="64" r="3"/><path d={setting(part,'closed')?'M49 64h30':'m49 62 29-17'}/></>;
 else if(t==='switch')drawing=<><path d="M0 64h40M86 32h42M86 96h42"/><circle cx="42" cy="64" r="3"/><circle cx="84" cy="32" r="3"/><circle cx="84" cy="96" r="3"/><path d={setting(part,'position')?'M45 65 81 94':'M45 63 81 34'}/></>;
 else drawing=<><rect x="24" y="16" width={l.width-48} height={l.height-32}/>{l.terminals.map(pin=><g key={pin.id}><path d={`M${pin.x} ${pin.y}h${pin.side==='left'?24:-24}`}/><text x={pin.side==='left'?30:l.width-30} y={pin.y-4} textAnchor={pin.side==='left'?'start':'end'} fill="currentColor" stroke="none" fontSize="10">{pin.id}</text></g>)}<text x={l.width/2} y={l.height/2} textAnchor="middle" fill="currentColor" stroke="none" fontSize="12">{t==='opamp'?'LM358 · A/B':t==='tmp36'?'TMP36':t==='uno'?'ARDUINO UNO':part.label.slice(0,16)}</text></>;
 const actual=symbolLayout(part);
 return <svg className="schematic-symbol" width={actual.width} height={actual.height} viewBox={`0 0 ${actual.width} ${actual.height}`} aria-hidden="true"><g transform={`translate(${actual.width/2} ${actual.height/2}) rotate(${actual.rotation}) translate(${-l.width/2} ${-l.height/2})`} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{drawing}</g></svg>;
}
