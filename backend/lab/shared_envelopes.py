"""Share decay control across similar partials without hiding generators."""
import numpy as np
from .schema import Block
from .identify import link
from .instrument import phase_wrap
from .graph import validate


def share_envelopes(patch,groups):
    p=patch.model_copy(deep=True)
    # Sharing across a nonlinear processor would change the architecture. Only
    # direct branches of the same sum with matching attack/onset are eligible.
    families={}
    for node in p.nodes:
        if node.type!='modal':continue
        edges=[e for e in p.edges if e.source==node.id]
        if len(edges)!=1:continue
        target=next(n for n in p.nodes if n.id==edges[0].target)
        if target.type!='sum':continue
        v=node.parameters
        families.setdefault((target.id,v['attack'],v['onset']),[]).append(node)
    changed=False
    for (target,attack,onset),nodes in families.items():
        ordered=sorted(nodes,key=lambda n:n.parameters['tau'])
        for indexes in np.array_split(np.arange(len(ordered)),min(groups,len(ordered))):
            if len(indexes)<3:continue # 2 sources + shared sum/env would save nothing
            cluster=[ordered[i] for i in indexes]
            weights=np.array([n.parameters['amplitude']**2 for n in cluster])+1e-15
            tau=float(np.exp(np.average(np.log([n.parameters['tau'] for n in cluster]),weights=weights)))
            stem=f'shared-{len(p.nodes)}';sid=stem+'-sum';eid=stem+'-env'
            if any(n.id in (sid,eid) for n in p.nodes):continue
            ids={n.id for n in cluster};p.edges=[e for e in p.edges if e.source not in ids]
            for n in cluster:
                v=n.parameters
                n.type='oscillator';n.parameters={k:v[k] for k in ('frequency','amplitude','phase')}
                n.parameters['phase']=phase_wrap(v['phase']-2*np.pi*v['frequency']*onset)
                n.label=(n.label+' · sinus')[:160]
                n.reason='Oscillateur indépendant ; décroissance commandée par une enveloppe commune explicitement câblée.'
                p.edges.append(link(n.id,sid))
            p.nodes.extend([Block(id=sid,type='sum',label='Partiels à décroissance proche'),Block(id=eid,type='envelope',label='Enveloppe partagée',parameters={'attack':attack,'onset':onset,'tau':tau},reason=f'Enveloppe commune à {len(cluster)} sinus explicites. Décroissance moyenne géométrique pondérée ; candidat accepté seulement après mesure du signal complet.')])
            p.edges.extend([link(sid,eid),link(eid,target)]);changed=True
    if not changed:return None
    p.name=f'Compact · enveloppes partagées ({groups} groupes)'
    validate(p);return p
