"""Schema for the versioned presentation document. Never accept executable markup."""
import re

LAYOUT_FILE = 'frontend/src/siteLayout.json'
KINDS = {'inventory','compact','status','metrics','transfer','knobs','reference','graph','player','keyboard','signals','settings','hardware','workshop','text','image','link'}
PLOTS = {'wave','env','fft','auto','spectrogram','measured-envelope','optimization','global','bode-gain','bode-phase','impulse'}
IDENTIFIER = re.compile(r'[a-z][a-z0-9-]{0,47}')
HEX = re.compile(r'#[0-9a-fA-F]{6}')


def validate_layout(layout):
    def require(ok):
        if not ok:
            raise ValueError('Mise en page invalide.')
    def text(value, limit):
        return isinstance(value,str) and len(value)<=limit and not any(ord(c)<32 and c!='\n' for c in value)
    def ident(value):
        return isinstance(value,str) and IDENTIFIER.fullmatch(value)
    require(type(layout) is dict and set(layout)=={'version','pages','bank','plots'}
            and type(layout['version']) is int and layout['version']==1)
    pages,bank,plots = (layout[key] for key in ('pages','bank','plots'))
    require(type(pages) is list and 2<=len(pages)<=24 and type(bank) is list and len(bank)<=100
            and type(plots) is dict and set(plots)<=PLOTS)
    ids={}
    for page in pages:
        require(type(page) is dict and set(page)<= {'id','parent','name','custom','blocks'}
                and {'id','parent','name','blocks'}<=set(page))
        pid=page['id']
        require(ident(pid) and pid not in ids and text(page['name'],60) and
                (page['parent'] is None or ident(page['parent'])) and type(page.get('custom',False)) is bool
                and type(page['blocks']) is list and len(page['blocks'])<=40)
        ids[pid]=page
    require(list(ids)[:1]==['analyse'] and 'atelier' in ids and all(ids[key]['parent'] is None for key in ('analyse','atelier')))
    for page in pages:
        parent=page['parent']; visited={page['id']}
        while parent is not None:
            require(parent in ids and parent not in visited and len(visited)<5)
            visited.add(parent); parent=ids[parent]['parent']
    unique=set()
    for block in [*bank,*(b for page in pages for b in page['blocks'])]:
        require(type(block) is dict and {'id','kind','x','y','w','h'}<=set(block)
                and set(block)<={'id','kind','x','y','w','h','text','target'})
        require(ident(block['id']) and block['id'] not in unique and isinstance(block['kind'],str) and block['kind'] in KINDS)
        unique.add(block['id'])
        x,y,w,h=(block[k] for k in ('x','y','w','h'))
        require(all(type(v) is int for v in (x,y,w,h)) and 0<=x<=11 and 0<=y<=239 and 1<=w<=12-x and 1<=h<=12)
        require(text(block.get('text',''),400) and text(block.get('target',''),240))
        target=block.get('target','')
        if target and block['kind']=='image':
            require(bool(re.fullmatch(r'/(?:favicon\.svg|assets/[a-zA-Z0-9_.-]+\.(?:png|jpg|jpeg|svg|webp))',target)))
        if target and block['kind']=='link':
            require(ident(target) or (target.startswith('#') and ident(target[1:])))
    for style in plots.values():
        axes = ('title','x','xUnit','y','yUnit','y2','y2Unit')
        require(type(style) is dict and set(style)<=set(axes)|{'legend','color','traces'})
        require(all(text(style[key],100) for key in axes if key in style))
        require('legend' not in style or type(style['legend']) is bool)
        require('color' not in style or (isinstance(style['color'],str) and HEX.fullmatch(style['color'])))
        traces=style.get('traces',[])
        require(type(traces) is list and len(traces)<=3)
        for trace in traces:
            require(type(trace) is dict and set(trace)<={'name','color'} and text(trace.get('name',''),100))
            require('color' not in trace or (isinstance(trace['color'],str) and HEX.fullmatch(trace['color'])))
    return layout
