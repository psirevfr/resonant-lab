"""Explicit oscillator/envelope graphs and bounded note transposition.

The reference waveform is never stored in the instrument. Every key is rendered
from the graph. One note cannot establish timbre fidelity across a piano keyboard.
"""
import numpy as np
from .schema import Patch,Block,Edge
from .blocks import parameters,REGISTRY
from .graph import validate
from .identify import link


def phase_wrap(value):return float((value+np.pi)%(2*np.pi)-np.pi)


def first_envelope(patch,source):
    """First exponential envelope on every downstream path, if unambiguous.

    Transparent here means a known signal-processing stage, not a bypass:
    its DSP still executes. Delays and other time controls have no inferred onset.
    """
    nodes={n.id:n for n in patch.nodes};memo={};visiting=set()
    traversable={'sum','gain','lowpass','lowpass1','highpass','bandpass','notch','peak_eq','resonator','saturation','asymmetric_saturation'}
    def walk(key):
        if key in memo:return memo[key]
        if key in visiting or key not in nodes:return {None}
        node=nodes[key]
        if node.type=='envelope':return {key}
        if node.type not in traversable:return {None}
        visiting.add(key)
        children=[e.target for e in patch.edges if e.source==key]
        found=set().union(*(walk(k) for k in children)) if children else {None}
        visiting.remove(key);memo[key]=found;return found
    children=[e.target for e in patch.edges if e.source==source]
    found=set().union(*(walk(k) for k in children)) if children else {None}
    return nodes[next(iter(found))] if len(found)==1 and None not in found else None


def expand_modes(patch):
    validate(patch)
    if physical_count(patch)>128:raise ValueError("Dépliage limité à 128 modules ; simplifiez le modèle avant.")
    p=patch.model_copy(deep=True)
    ids={n.id for n in p.nodes}
    for n in list(p.nodes):
        if n.type!='modal':continue
        v=parameters('modal',n.parameters,p.sample_rate)
        eid=n.id+'-env'
        if len(eid)>80 or eid in ids:raise ValueError('Identifiant incompatible avec le dépliage des modes.')
        ids.add(eid)
        n.type='oscillator';n.parameters={'frequency':v['frequency'],'amplitude':v['amplitude'],'phase':phase_wrap(v['phase']-2*np.pi*v['frequency']*v['onset'])}
        n.label=((n.label or n.id)+' · sinus')[:160]
        n.reason=(n.reason+' Oscillateur explicite ; la phase à t=0 compense le début de son enveloppe.')[:4000]
        env=Block(id=eid,type='envelope',label=f'Enveloppe · {n.id}',parameters={k:v[k] for k in ('attack','tau','onset')},position={'x':n.position.get('x',0)+240,'y':n.position.get('y',0)},reason='Attaque, décroissance et début du mode original, rendus explicitement par ce VCA à enveloppe exponentielle. Aucun ADSR implicite.')
        p.nodes.append(env)
        for e in p.edges:
            if e.source==n.id:e.source=eid;e.id=f'{eid}-{e.target}'
        p.edges.append(link(n.id,eid))
    validate(p);return p


def collapse_modes(patch):
    """Invert only exclusive oscillator → exponential-envelope pairs."""
    p=patch.model_copy(deep=True)
    # Invert explicit oscillator banks sharing a sum → envelope, when every
    # source is exclusive to that bank. This preserves subsequent simplification.
    for env in list(p.nodes):
        if env.type!='envelope':continue
        parent=next((n for n in p.nodes if any(e.source==n.id and e.target==env.id for e in p.edges)),None)
        if parent is None or parent.type!='sum' or sum(e.source==parent.id for e in p.edges)!=1:continue
        sources=[n for n in p.nodes if any(e.source==n.id and e.target==parent.id for e in p.edges)]
        if not sources or any(n.type!='oscillator' or sum(e.source==n.id for e in p.edges)!=1 for n in sources):continue
        w=parameters('envelope',env.parameters,p.sample_rate)
        for osc in sources:
            v=parameters('oscillator',osc.parameters,p.sample_rate)
            osc.type='modal';osc.parameters={**v,**w,'phase':phase_wrap(v['phase']+2*np.pi*v['frequency']*w['onset'])}
        p.nodes.remove(env)
        p.edges=[Edge(id=f'{parent.id}-{e.target}',source=parent.id,target=e.target) if e.source==env.id else e for e in p.edges if e.target!=env.id]
    for osc in list(p.nodes):
        if osc.type!='oscillator':continue
        outgoing=[e for e in p.edges if e.source==osc.id]
        if len(outgoing)!=1:continue
        env=next(n for n in p.nodes if n.id==outgoing[0].target)
        if env.type!='envelope':continue
        v=parameters('oscillator',osc.parameters,p.sample_rate);w=parameters('envelope',env.parameters,p.sample_rate)
        osc.type='modal';osc.parameters={**v,**w,'phase':phase_wrap(v['phase']+2*np.pi*v['frequency']*w['onset'])}
        p.nodes.remove(env)
        p.edges=[Edge(id=f'{osc.id}-{e.target}',source=osc.id,target=e.target) if e.source==env.id else e for e in p.edges if e.target!=env.id]
    validate(p);return p


def physical_count(patch):
    # A modal source includes one oscillator AND one amplitude envelope.
    return len(patch.nodes)+sum(n.type=='modal' for n in patch.nodes)


def prepare(patch):
    p=expand_modes(patch)
    ids={n.id:n.type for n in p.nodes}
    reserved={'keyboard-velocity':'gain','keyboard-adsr':'adsr'}
    if set(ids)&set(reserved):
        if not all(ids.get(k)==v for k,v in reserved.items()):raise ValueError('Modules de contrôle MIDI incomplets ou incompatibles.')
        return p
    if len(p.nodes)>126:raise ValueError('Préparation MIDI limitée à 128 modules.')
    out=next(n.id for n in p.nodes if n.type=='output');parent=next(e.source for e in p.edges if e.target==out)
    p.edges=[e for e in p.edges if e.target!=out]
    p.nodes.extend([
      Block(id='keyboard-velocity',type='gain',label='MIDI · vélocité / VCA',parameters={'gain':1},reason='Vélocité MIDI/127 : gain de sortie explicite. Ne prétend pas identifier le changement de timbre dû à la force de frappe.'),
      Block(id='keyboard-adsr',type='adsr',label='MIDI · gate / relâchement',parameters={'attack':0,'decay':.001,'sustain':1,'gate':60,'release':.2},reason='ADSR explicite pour le relâchement de touche. L’attaque et la décroissance du piano restent dans les enveloppes des branches. Le clavier applique la même durée de relâchement à la réception du note-off.')])
    p.edges.extend([link(parent,'keyboard-velocity'),link('keyboard-velocity','keyboard-adsr'),link('keyboard-adsr',out)])
    validate(p);return p


def transpose(patch,note,reference_note,velocity=127,gate=60,track_filters=True):
    p=prepare(patch);ratio=2**((note-reference_note)/12);muted=[]
    # Noise colour is not pitch-transposed. Descendants of noise up to mixes
    # are marked; their filtering represents the hammer/texture rather than pitch.
    noise_path={n.id for n in p.nodes if n.type in ('noise','white_noise','pink_noise')}
    for _ in p.nodes:
        added={e.target for e in p.edges if e.source in noise_path}
        if added<=noise_path:break
        noise_path|=added
    for n in p.nodes:
        v=parameters(n.type,n.parameters,p.sample_rate);n.parameters=v
        if n.type in ('oscillator','saw','triangle','pulse','pulse_train','relaxation','resonator','comb'):
            old=v['frequency'];new=old*ratio
            if new>=min(47000,p.sample_rate*.49):
                if 'amplitude' in v:v['amplitude']=0;muted.append(n.id)
                new=min(47000,p.sample_rate*.49)
            new=max(20 if n.type=='comb' else 1,new)
            if n.type=='oscillator':
                env=first_envelope(p,n.id)
                onset=parameters('envelope',env.parameters,p.sample_rate)['onset'] if env else 0
                v['phase']=phase_wrap(v['phase']-2*np.pi*(new-old)*onset)
            v['frequency']=float(max(1,new))
        if track_filters and 'fc' in v and n.id not in noise_path:
            v['fc']=float(np.clip(v['fc']*ratio,5,min(47000,p.sample_rate*.45)))
    next(n for n in p.nodes if n.id=='keyboard-velocity').parameters['gain']=velocity/127
    next(n for n in p.nodes if n.id=='keyboard-adsr').parameters['gate']=gate
    p.name=f'{patch.name[:150]} · MIDI {note}'
    validate(p);return p,muted
