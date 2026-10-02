const fs=require('fs'),path=require('path');
const rows=[];
for(const pdr of ['fixed','weinberg','adaptive_linear','adaptive_quadratic'])
 for(const ble of [false,true])
  for(const magnetic of ['off','v2_norm','v2_norm_mv','grid_norm','grid_norm_mv'])
   rows.push({pdr,ble,magnetic,status:pdr.startsWith('adaptive')?'stride-only-evaluated-not-full-runtime':magnetic.startsWith('grid')?'offline-grid-and-right-runtime-only':'runtime-options-connected-not-all-combinations-evaluated'});
const report={nominal:64,unique:rows.length,explanation:'4 app modes encode magnetic on/off and BLE on/off. Four magnetic variants only matter in the two magnetic-on modes. Per stride: two magnetic-off configurations + two BLE settings times four magnetic variants =10. Four strides =>40, not64 independent configurations.',
 apAxis:'AP off/qualified-anchor policy would double theoretical 40 to80 only with usable AP logs; not executed',
 ronin:'Separate velocity frontend; 11 raw inferences executed. Not yet part of40 full-fusion configurations.',rows};
const out=path.resolve(__dirname,'../data/analysis/radio-fix-20260923');fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'experiment-matrix.json'),JSON.stringify(report,null,2)+'\n');console.log('40 unique classical configurations; 64 nominal includes duplicate magnetic-off settings.');
