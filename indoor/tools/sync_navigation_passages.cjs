// Regenerate only named passage records from the existing shared floor data.
const fs=require('fs'),path=require('path');
const target=path.resolve(__dirname,'../web/data/navigation/areas-v1.json');
const data=JSON.parse(fs.readFileSync(target,'utf8'));
const load=f=>JSON.parse(fs.readFileSync(path.resolve(__dirname,`../web/data/maps/floor-${String(f).padStart(2,'0')}.json`),'utf8'));
const base=load(4),restroom=base.facilities.find(f=>f.id==='4F_RESTROOM');
for(const floor of [2,3,4,6,7,8,9,10]){
 const source=load(floor),end=source.floor6_right_end;
 const x=end?end.passage_center_x:restroom.passage_center_map_x,width=end?end.passage_width:restroom.passage_width,depth=end?end.passage_depth:restroom.passage_depth;
 if(![x,width,depth].every(Number.isFinite)||width<=0||depth<=0)throw Error('Invalid passage source');
 const entry=data.floors[floor] ||= {areas:[],portals:[],walls:[]};
 entry.areas=entry.areas.filter(a=>a.id!=='side_passage');entry.portals=entry.portals.filter(p=>p.id!=='main_side_passage');
 entry.areas.push({id:'side_passage',label:end?`${end.room_id} 끝방 통로`:'사이드 화장실 통로',rect:[x-width/2,-1.17-depth,x+width/2,-1.17],motion_axis:'y',
  status:'shared-plan-geometry-not-new-survey',source:`data/maps/floor-${String(end?floor:4).padStart(2,'0')}.json`,source_version:end?source.version:base.version,
  end_status:'interior-door-and-room-not-modeled',
  ...([2,3].includes(floor)?{display_svg_rect:[1252,764,1282,874],display_note:'Existing floor SVG is nonuniform; display bounds are separate from shared map coordinates.'}:{})});
 entry.portals.push({id:'main_side_passage',between:['main_right','side_passage'],line:[{x:x-width/2,y:-1.17},{x:x+width/2,y:-1.17}],evidence:'shared-floor-map-and-user-connection',
  ...([2,3].includes(floor)?{display_svg_line:[[1252,764],[1282,764]]}:{})});
}
fs.writeFileSync(target,JSON.stringify(data,null,2)+'\n');
console.log('Synced 8 passage areas and portals; stairs and room interiors unchanged.');
