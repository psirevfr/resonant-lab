"""Validated DAG execution. The displayed patch is the executable model."""
from collections import deque
import numpy as np
from .schema import Patch
from .blocks import REGISTRY, parameters, process

MAX_RENDER_WORK = 100_000_000  # samples × blocks

def validate(patch: Patch):
    nodes = {n.id:n for n in patch.nodes}
    if len(nodes) != len(patch.nodes): raise ValueError('Identifiants de blocs dupliqués.')
    if sum(n.type == 'output' for n in patch.nodes) != 1: raise ValueError('Le graphe doit avoir exactement une sortie.')
    incoming = {k:[] for k in nodes}; outgoing = {k:[] for k in nodes}
    edge_ids = set(); pairs = set()
    for edge in patch.edges:
        if edge.id in edge_ids or (edge.source,edge.target) in pairs: raise ValueError('Connexion dupliquée.')
        edge_ids.add(edge.id); pairs.add((edge.source,edge.target))
        if edge.source not in nodes or edge.target not in nodes: raise ValueError('Connexion vers un bloc inexistant.')
        if nodes[edge.source].type == 'output': raise ValueError('La sortie ne peut pas avoir de connexion sortante.')
        incoming[edge.target].append(edge.source); outgoing[edge.source].append(edge.target)
    for node in patch.nodes:
        parameters(node.type,node.parameters,patch.sample_rate)
        count = REGISTRY[node.type].inputs
        if (count >= 0 and len(incoming[node.id]) != count) or (count == -1 and not incoming[node.id]):
            raise ValueError(f'{node.label or node.type} : nombre d’entrées incorrect ({len(incoming[node.id])}).')
    degrees = {k:len(v) for k,v in incoming.items()}; queue = deque(k for k,v in degrees.items() if v==0); order=[]
    while queue:
        k = queue.popleft(); order.append(k)
        for target in outgoing[k]:
            degrees[target]-=1
            if degrees[target]==0: queue.append(target)
    if len(order) != len(nodes): raise ValueError('Boucle détectée : seuls les graphes sans cycle sont pris en charge.')
    output = next(k for k,n in nodes.items() if n.type=='output')
    active=set()
    def visit(k):
        if k in active: return
        active.add(k)
        for source in incoming[k]: visit(source)
    visit(output)
    return nodes,incoming,outgoing,[k for k in order if k in active],output

def render(patch: Patch, external: np.ndarray | None = None) -> np.ndarray:
    nodes,inc,out,order,output = validate(patch)
    n = round(patch.sample_rate*patch.duration)
    if n*sum(8 if nodes[k].type=='asymmetric_saturation' else 1 for k in order)>MAX_RENDER_WORK:
        raise ValueError('Rendu trop volumineux : réduire la durée ou le nombre de blocs (100 millions échantillons×blocs).')
    buffers={}; uses={k:sum(t in order for t in out[k]) for k in order}
    for key in order:
        node=nodes[key]; p=parameters(node.type,node.parameters,patch.sample_rate)
        if node.type=='input' and external is not None:
            if len(external)!=n: raise ValueError('Longueur de l’entrée externe incorrecte.')
            y=np.asarray(external,dtype=float)
        else: y=process(node.type,p,[buffers[s] for s in inc[key]],patch.sample_rate,n)
        if not np.isfinite(y).all() or np.max(np.abs(y))>1e8: raise ValueError('Signal divergent : vérifier les gains et résonances.')
        buffers[key]=y
        for source in inc[key]:
            uses[source]-=1
            if uses[source]==0: del buffers[source]
    return buffers[output]
