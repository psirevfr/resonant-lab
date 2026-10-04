"""Small DSP parity fixtures, no recordings or user data."""
import json
from pathlib import Path
from lab.blocks import catalog
from lab.schema import Block,Patch
from lab.identify import link
from lab.graph import render

base=Block(id='source',type='oscillator',parameters={'frequency':731,'amplitude':.31,'phase':.2})
patches=[]
for kind,params in [('output',{}),('modal',{'frequency':371,'phase':.7,'amplitude':.2,'onset':.003,'attack':.001,'tau':.14}),('lowpass',{'fc':1800,'q':1.2}),('highpass',{'fc':1100}),('bandpass',{}),('notch',{}),('peak_eq',{'db':12}),('lowpass1',{}),('resonator',{'frequency':400,'tau':.2}),('envelope',{'onset':.003}),('adsr',{'gate':.02,'attack':.03,'release':.015}),('delay',{'seconds':.003}),('saturation',{'drive':6}),('asymmetric_saturation',{'drive':12,'bias':.8,'level':.3,'mix':.8}),('gain',{'gain':0})]:
 nodes=[base.model_copy(deep=True)];edges=[]
 if kind=='modal':nodes[0].type=kind;nodes[0].parameters=params;parent='source'
 elif kind=='output':parent='source'
 else:nodes.append(Block(id='process',type=kind,parameters=params));edges.append(link('source','process'));parent='process'
 nodes.append(Block(id='out',type='output'));edges.append(link(parent,'out'))
 p=Patch(nodes=nodes,edges=edges,duration=.05)
 patches.append({'name':kind,'patch':p.model_dump(),'samples':render(p).tolist()})
path=Path('frontend/tests/fixtures/dsp.json');path.parent.mkdir(exist_ok=True);path.write_text(json.dumps({'catalog':catalog(),'patches':patches}))
