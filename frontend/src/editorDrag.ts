type Drop = {anchor: string; after: boolean; column?: number};
type Target = {key: string; element: HTMLElement; rect: DOMRect};

const blockSelector='[data-layout-block],[data-editor-kind]';
const keyFor=(element:HTMLElement)=>element.dataset.layoutBlock??element.dataset.editorKind??'';

function targets(container:HTMLElement):Target[]{
 const blocks=Array.from(container.children).filter((node):node is HTMLElement=>node instanceof HTMLElement&&node.matches(blockSelector));
 return blocks.flatMap(element=>{
  // Native blocks use display:contents, so use their first and last visible child.
  const boxes=element.dataset.layoutBlock
   ? [element.getBoundingClientRect()]
   : Array.from(element.children,child=>child.getBoundingClientRect());
  const visible=boxes.filter(rect=>rect.width>0&&rect.height>3);
  if(!visible.length)return [];
  const top=Math.min(...visible.map(r=>r.top)),bottom=Math.max(...visible.map(r=>r.bottom));
  const left=Math.min(...visible.map(r=>r.left)),right=Math.max(...visible.map(r=>r.right));
  return [{key:keyFor(element),element,rect:new DOMRect(left,top,right-left,bottom-top)}];
 });
}

export function createEditorDrag(canEdit:()=>boolean,send:(move:{id:string;anchor:string;after:boolean;column?:number})=>void){
 const guide=document.createElement('div');
 guide.className='editor-drop-guide';
 guide.setAttribute('aria-hidden','true');
 let active:{element:HTMLElement;capture:Element;origin:DOMRect;container:HTMLElement;pointer:number;x:number;y:number;drop:Drop|null;moved:boolean}|null=null;
 let suppressClick=false;
 let clickTimer=0;

 function start(event:PointerEvent){
  if(!canEdit()||event.button!==0||!(event.target instanceof Element))return;
  if(event.pointerType==='touch'&&!event.target.closest('[data-editor-grip]'))return;
  const element=event.target.closest<HTMLElement>(blockSelector),container=element?.parentElement;
  if(!element||!container||active)return;
  const origin=targets(container).find(target=>target.element===element)?.rect;
  if(!origin)return;
  active={element,capture:event.target,origin,container,pointer:event.pointerId,x:event.clientX,y:event.clientY,drop:null,moved:false};
  event.target.setPointerCapture(event.pointerId);
  event.preventDefault();
  event.stopImmediatePropagation();
 }
 function move(event:PointerEvent){
  if(!active||event.pointerId!==active.pointer)return;
  if(!canEdit()){cancel();return;}
  if(!active.moved&&Math.hypot(event.clientX-active.x,event.clientY-active.y)<6)return;
  const {container,element,origin}=active;
  if(!active.moved){active.moved=true;element.setAttribute('data-editor-dragging','');document.body.append(guide);}
  const grid=container.getBoundingClientRect();
  const available=targets(container);
  const nearest=available.reduce<Target|undefined>((best,target)=>{
   const distance=({rect}:Target)=>Math.min(Math.abs(event.clientY-rect.top),Math.abs(event.clientY-rect.bottom))
    + Math.max(0,rect.left-event.clientX,event.clientX-rect.right)*.35;
   return !best||distance(target)<distance(best)?target:best;
  },undefined);
  if(!nearest||event.clientX<grid.left-10||event.clientX>grid.right+10){
   active.drop=null;guide.hidden=true;return;
  }
  const after=nearest.element!==element&&Math.abs(event.clientY-nearest.rect.bottom)<Math.abs(event.clientY-nearest.rect.top);
  const column=container.classList.contains('site-layout-grid')&&getComputedStyle(container).display==='grid'
   ? Math.round((origin.left+event.clientX-active.x-grid.left-parseFloat(getComputedStyle(container).paddingLeft))/(grid.width/12))
   : undefined;
  active.drop={anchor:nearest.key,after,column};
  guide.hidden=false;
  guide.style.left=nearest.rect.left+'px';
  guide.style.width=nearest.rect.width+'px';
  guide.style.top=(after?nearest.rect.bottom:nearest.rect.top)+'px';
  event.preventDefault();
  event.stopImmediatePropagation();
 }
 function cancel(){
  if(active?.capture.hasPointerCapture(active.pointer))active.capture.releasePointerCapture(active.pointer);
  active?.element.removeAttribute('data-editor-dragging');
  guide.remove();
  active=null;
 }
 function finish(event:PointerEvent){
  if(!active||event.pointerId!==active.pointer)return;
  const {drop,element,moved}=active;
  cancel();
  if(!moved)return;
  event.preventDefault();event.stopImmediatePropagation();
  suppressClick=true;
  clearTimeout(clickTimer);clickTimer=window.setTimeout(()=>suppressClick=false,350);
  if(event.type==='pointerup'&&drop&&canEdit())send({id:keyFor(element),...drop});
 }
 function click(event:MouseEvent){
  if(suppressClick){suppressClick=false;event.preventDefault();event.stopImmediatePropagation();}
 }
 function keydown(event:KeyboardEvent){if(event.key==='Escape')cancel();}
 document.addEventListener('pointerdown',start,true);
 window.addEventListener('pointermove',move,true);
 window.addEventListener('pointerup',finish,true);
 window.addEventListener('pointercancel',finish,true);
 window.addEventListener('blur',cancel);
 document.addEventListener('click',click,true);
 document.addEventListener('keydown',keydown,true);
 return ()=>{
  cancel();clearTimeout(clickTimer);
  document.removeEventListener('pointerdown',start,true);
  window.removeEventListener('pointermove',move,true);
  window.removeEventListener('pointerup',finish,true);
  window.removeEventListener('pointercancel',finish,true);
  window.removeEventListener('blur',cancel);
  document.removeEventListener('click',click,true);
  document.removeEventListener('keydown',keydown,true);
 };
}
