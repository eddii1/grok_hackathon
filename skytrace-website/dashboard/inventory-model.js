(function(root){
  function compare(baseline, scan){
    const current=new Map(scan.items.map(item=>[item.id,item]));
    const known=new Set(baseline.items.map(item=>item.id));
    const results=baseline.items.map(before=>{
      const after=current.get(before.id);
      const covered=scan.coveredZones.includes(before.zone);
      let status=!after?(covered?'missing':'unverified'):after.zone!==before.zone||after.position!==before.position?'moved':'unchanged';
      return {id:before.id,name:before.name,before,after:after||null,status};
    });
    for(const item of scan.items)if(!known.has(item.id))results.push({id:item.id,name:item.name,before:null,after:item,status:'added'});
    return results;
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={compare};
  else root.InventoryModel={compare};
})(typeof window!=='undefined'?window:globalThis);
