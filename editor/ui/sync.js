'use strict';

function mergePresentation(base, local, disk){
 if(same(local,base))return disk;
 if(same(disk,base)||same(local,disk))return local;

 const isObject=value=>value&&typeof value==='object'&&!Array.isArray(value);
 const objects=[local,disk].every(isObject)&&(base===undefined||isObject(base));
 if(objects){
  const original=base??{};
  const keys=new Set([...Object.keys(original),...Object.keys(local),...Object.keys(disk)]);
  return Object.fromEntries([...keys].flatMap(key=>{
   const value=mergePresentation(original[key],local[key],disk[key]);
   return value===undefined?[]:[[key,value]];
  }));
 }
 const keyed=[base,local,disk].every(list=>Array.isArray(list)&&list.every(item=>item&&typeof item.id==='string'));
 if(keyed){
  const ids=list=>list.map(item=>item.id);
  const baseOrder=ids(base),localOrder=ids(local),diskOrder=ids(disk);
  const shared=new Set(baseOrder.filter(id=>localOrder.includes(id)&&diskOrder.includes(id)));
  const changed=!same(baseOrder.filter(id=>shared.has(id)),localOrder.filter(id=>shared.has(id)));
  const keys=new Set(changed?[...localOrder,...diskOrder]:[...diskOrder,...localOrder]);
  const indexed=[base,local,disk].map(rows=>new Map(rows.map(row=>[row.id,row])));
  return [...keys].flatMap(id=>{
   const value=mergePresentation(...indexed.map(rows=>rows.get(id)));
   return value===undefined?[]:[value];
  });
 }
 return local;
}
