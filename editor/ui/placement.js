'use strict';

// Positions stay in the document's twelve-column grid. A vertical insertion
// makes room for the moved block while leaving unaffected horizontal lanes.
function relocateBlock(blocks, block, anchor, after, column){
 const x=Number.isInteger(column)?Math.max(0,Math.min(12-block.w,column)):block.x;
 let y=anchor.y+(after?anchor.h:0);
 if(anchor===block&&block.x===x)return;
 const lane=blocks.filter(peer=>peer!==block&&peer.x<x+block.w&&peer.x+peer.w>x);
 // A block spanning the insertion line keeps its full height.
 for(const peer of [...lane].sort((a,b)=>a.y-b.y)){
  if(peer.y<y&&peer.y+peer.h>y)y=peer.y+peer.h;
 }
 const obstructed=lane.some(peer=>peer.y<y+block.h&&peer.y+peer.h>y);
 const shifting=obstructed?blocks.filter(peer=>peer!==block&&peer.y>=y):[];
 if(y>239||shifting.some(peer=>peer.y+block.h>239))throw Error('Ce bloc dépasse la hauteur de la page.');
 for(const peer of shifting)peer.y+=block.h;
 Object.assign(block,{x,y});
}
