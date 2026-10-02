(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.IndoorNavigation = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  // A sidecar over the original plans, not a replacement for the rendering data.
  // Match the *drawn* core as well as the two ends; the plan is not uniform scale.
  const svgXs = [70,690,711,732,1310], mapXs = [135.407,72.184,70.804,69.424,0];
  function interpolate(value, from, to) {
    let i = from.length - 2;
    for (let j=0; j<from.length-1; j++) {
      if (value <= Math.max(from[j],from[j+1]) && value >= Math.min(from[j],from[j+1])) { i=j; break; }
    }
    if (value < Math.min(...from)) i = from[0] < from[1] ? 0 : from.length-2;
    if (value > Math.max(...from)) i = from[0] < from[1] ? from.length-2 : 0;
    return to[i]+(value-from[i])/(from[i+1]-from[i])*(to[i+1]-to[i]);
  }
  function svgToMap(x, y) {
    const dy = y < 700 ? 1.17 + (700 - y) * 7.9 / 110
      : y > 764 ? -1.17 - (y - 764) * 9.2 / 250 : (732 - y) * 2.34 / 64;
    return { x: interpolate(x,svgXs,mapXs), y: dy };
  }
  function mapToSvg(x, y) {
    return { x: interpolate(x,mapXs,svgXs),
      y: y > 1.17 ? 700 - (y - 1.17) * 110 / 7.9
        : y < -1.17 ? 764 + (-1.17 - y) * 250 / 9.2 : 732 - y * 64 / 2.34 };
  }
  function compile(data, floor) {
    const extra = data.floors[String(floor)] || {};
    // A floor may refine a common area after a local survey. The matching id
    // replaces the generic area instead of leaving two overlapping zones.
    const byId=new Map(data.common.map(a=>[a.id,a]));
    for(const area of extra.areas || [])byId.set(area.id,area);
    const areas = [...byId.values()].map(a => {
      if (!a.svg_rect) return { ...a };
      const p = svgToMap(a.svg_rect[0], a.svg_rect[1]);
      const q = svgToMap(a.svg_rect[2], a.svg_rect[3]);
      return { ...a, rect: [Math.min(p.x, q.x), Math.min(p.y, q.y), Math.max(p.x, q.x), Math.max(p.y, q.y)] };
    });
    return { floor: Number(floor), version: data.version, areas, distanceMetric:extra.distanceMetric || null,
      walls: (extra.walls || []).map(w => ({...w, line: w.svg_line.map(p => svgToMap(...p))})),
      portals: (extra.portals || []).map(p=>({...p,line:p.line || p.svg_line.map(v=>svgToMap(...v))})),
      commonIds:data.common.map(a=>a.id), note: extra.note || "공통 복도 외 미확인" };
  }
  function contains(rect, p) {
    return p.x >= rect[0] && p.x <= rect[2] && p.y >= rect[1] && p.y <= rect[3];
  }
  function areaAt(map, p) { return map.areas.find(a => contains(a.rect, p)) || null; }
  const cross = (a, b, c) => (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
  function intersects(a, b, c, d) {
    if (Math.hypot(b.x-a.x,b.y-a.y) < 1e-9) return false;
    const eps = 1e-9;
    const on = (p,q,r) => Math.abs(cross(p,q,r)) < eps && r.x >= Math.min(p.x,q.x)-eps && r.x <= Math.max(p.x,q.x)+eps && r.y >= Math.min(p.y,q.y)-eps && r.y <= Math.max(p.y,q.y)+eps;
    return (cross(a,b,c)*cross(a,b,d) < -eps && cross(c,d,a)*cross(c,d,b) < -eps)
      || on(a,b,c) || on(a,b,d) || on(c,d,a) || on(c,d,b);
  }
  function transition(map, from, to) {
    if (![from.x,from.y,to.x,to.y].every(Number.isFinite)) return { allowed:false, reason:"invalid_coordinate", weight:0 };
    const wall = map.walls.find(w => w.hard && intersects(from,to,...w.line));
    if (wall) return { allowed:false, reason:wall.id, weight:0 };
    // Check the entire segment: endpoints alone would allow tunnelling through gaps.
    const steps = Math.max(1, Math.ceil(Math.hypot(to.x-from.x,to.y-from.y)/0.25));
    let previousArea=null, uncertain=false;
    for (let i=0; i<=steps; i++) {
      const p = { x:from.x+(to.x-from.x)*i/steps, y:from.y+(to.y-from.y)*i/steps };
      const area=areaAt(map,p);
      if (!area) return { allowed:true, reason:"unverified_area", weight:0.75 };
      if (previousArea && previousArea.id!==area.id) {
        const common=map.commonIds.includes(area.id)&&map.commonIds.includes(previousArea.id);
        const portal=map.portals.some(portal=>portal.between.includes(area.id)&&portal.between.includes(previousArea.id)
          && intersects(from,to,...portal.line));
        if (!common && !portal) uncertain=true;
      }
      previousArea=area;
    }
    if (uncertain) return {allowed:true,reason:"unverified_connection",weight:0.75};
    return { allowed:true, reason:"mapped_area", weight:1 };
  }
  // Local proposals only: never seed a distant room from a zone label.
  function branchMoves(map, from, length, heading) {
    const area=areaAt(map,from);
    if(!area)return [];
    const angle=(heading-355)*Math.PI/180, motion={x:-Math.cos(angle),y:-Math.sin(angle)};
    return map.portals.filter(p=>p.between.includes(area.id)).flatMap(portal=>{
      const target=map.areas.find(a=>a.id===portal.between.find(id=>id!==area.id));
      if(!target)return [];
      const [a,b]=portal.line,dx=b.x-a.x,dy=b.y-a.y,den=dx*dx+dy*dy;
      if(!den)return [];
      const t=Math.max(0,Math.min(1,((from.x-a.x)*dx+(from.y-a.y)*dy)/den));
      const q={x:a.x+t*dx,y:a.y+t*dy};
      if(Math.hypot(q.x-from.x,q.y-from.y)>length*2)return [];
      const center={x:(target.rect[0]+target.rect[2])/2,y:(target.rect[1]+target.rect[3])/2};
      let nx=-dy/Math.sqrt(den),ny=dx/Math.sqrt(den);
      if(nx*(center.x-q.x)+ny*(center.y-q.y)<0){nx=-nx;ny=-ny;}
      const dot=nx*motion.x+ny*motion.y;
      if(dot<.25)return []; // A phone pointing away does not activate this branch.
      const goal={x:q.x+nx*length,y:q.y+ny*length};
      const distance=Math.hypot(goal.x-from.x,goal.y-from.y),step=Math.min(length,distance);
      const to={x:from.x+(goal.x-from.x)*step/distance,y:from.y+(goal.y-from.y)*step/distance};
      const verdict=transition(map,from,to),end=areaAt(map,to);
      if(!verdict.allowed||verdict.reason!=="mapped_area"||!end||![area.id,target.id].includes(end.id))return [];
      return [{to,portal:portal.id,target:target.id,weight:.2+.5*dot}];
    });
  }
  function advanceDistance(map,x,legacyDelta) {
    const m=map.distanceMetric;
    if(!m)return x+legacyDelta;
    const edge=m.mapBreaks[2];
    if(x>edge){
      if(x+legacyDelta>=edge)return x+legacyDelta;
      return advanceDistance(map,edge,legacyDelta+(x-edge));
    }
    const meters=interpolate(x,m.mapBreaks,m.meterBreaks);
    const target=meters+legacyDelta*m.metersPerLegacyUnit;
    if(target>m.meterBreaks[2])return edge+(target-m.meterBreaks[2])/m.metersPerLegacyUnit;
    return interpolate(target,m.meterBreaks,m.mapBreaks);
  }
  function metricDistance(map,x) {
    const m=map.distanceMetric;
    if(!m)return x;
    const edge=m.mapBreaks[2];
    if(x>edge)return m.meterBreaks[2]+(x-edge)*m.metersPerLegacyUnit;
    return interpolate(x,m.mapBreaks,m.meterBreaks);
  }
  return {svgToMap,mapToSvg,compile,contains,areaAt,intersects,transition,branchMoves,advanceDistance,metricDistance};
});
