"""Portable, escaped graph and numeric exports."""
from html import escape
from .schema import Patch
from .blocks import REGISTRY

def graph_svg(patch: Patch):
    minx=min(n.position.get('x',0) for n in patch.nodes)-30; miny=min(n.position.get('y',0) for n in patch.nodes)-30
    width=max(n.position.get('x',0) for n in patch.nodes)-minx+250; height=max(n.position.get('y',0) for n in patch.nodes)-miny+130
    nodes={n.id:n for n in patch.nodes}
    items=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{minx} {miny} {width} {height}"><rect x="{minx}" y="{miny}" width="{width}" height="{height}" fill="#111820"/><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#aac67b"/></marker></defs>']
    for e in patch.edges:
        a,b=nodes[e.source],nodes[e.target]; x=a.position.get('x',0)+200; y=a.position.get('y',0)+35; u=b.position.get('x',0); v=b.position.get('y',0)+35
        items.append(f'<path d="M{x},{y} C{x+60},{y} {u-60},{v} {u},{v}" stroke="#aac67b" fill="none" stroke-width="2" marker-end="url(#arrow)"/>')
    for n in patch.nodes:
        x=n.position.get('x',0); y=n.position.get('y',0)
        desc=', '.join(f'{k}={v:.4g}' for k,v in n.parameters.items())
        items.append(f'<g><rect x="{x}" y="{y}" width="200" height="80" rx="8" fill="#202c37" stroke="#809668"/><text x="{x+12}" y="{y+26}" fill="#edf5e7" font-family="sans-serif" font-size="14">{escape((n.label or REGISTRY[n.type].label)[:27])}</text><text x="{x+12}" y="{y+51}" fill="#b4c2cc" font-family="monospace" font-size="11">{escape(desc[:27])}</text></g>')
    return ''.join(items)+'</svg>'
