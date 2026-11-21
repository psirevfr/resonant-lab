export type EditorCommand='escape'|'delete'|'undo'|'redo';
type Key=Pick<KeyboardEvent,'key'|'ctrlKey'|'metaKey'|'altKey'|'shiftKey'|'isComposing'|'defaultPrevented'>;
export type EditorContext={inside:boolean;editable:boolean;blocked:boolean};

/** Editing commands belong to the focused editor, never a modal or text input. */
export function editorCommand(event:Key,context:EditorContext):EditorCommand|null{
 if(!context.inside||context.editable||context.blocked||event.isComposing||event.defaultPrevented)return null;
 if(event.key==='Escape')return 'escape';
 if(event.ctrlKey||event.metaKey)return event.key.toLowerCase()==='z'?(event.shiftKey?'redo':'undo'):null;
 return !event.altKey&&['Delete','Backspace'].includes(event.key)?'delete':null;
}

export function editorContext(root:HTMLElement|null,target:EventTarget|null):EditorContext{
 const element=target instanceof Element?target:null;
 return {
  inside:!!root&&!!element&&root.contains(element),
  editable:!!element?.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"])'),
  blocked:!!root?.ownerDocument.querySelector('dialog[open],[role="dialog"][aria-modal="true"],.guided-tour')||!!element?.closest('[role="dialog"],dialog')
 };
}
