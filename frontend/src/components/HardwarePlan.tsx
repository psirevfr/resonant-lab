import type {Patch} from '../types';
import {audioHardware} from '../hardwareAudio';

export function HardwarePlan({patch}:{patch:Patch}){
 return <details className="audio-detail"><summary>Plan de montage</summary><table><thead><tr><th>Module</th><th>Composants</th><th>Liaison</th></tr></thead><tbody>{patch.nodes.map(node=>{const h=audioHardware(node);return <tr key={node.id}><td>{node.label||node.type}</td><td>{h.parts}{h.frequency&&' · '+h.frequency.toFixed(1)+' Hz'}</td><td>{h.wiring}</td></tr>})}</tbody></table></details>;
}
