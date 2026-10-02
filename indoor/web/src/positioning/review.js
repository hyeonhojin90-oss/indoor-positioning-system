(async function () {
  "use strict";
  const $=id=>document.getElementById(id), Nav=window.IndoorNavigation;
  const examples={
    2:[
      {label:"메인복도 → 2107 → M-space",points:[[1049,732],[1049,640],[1049,560],[1049,250]]},
      {label:"기둥·TDM 옆 진입구 → 책상공간",points:[[1169,732],[1169,642],[1138,642]]},
      {label:"기둥·TDM 옆 진입구 → 증축부",points:[[1169,732],[1169,640],[1169,550],[1169,200]]},
      {label:"2107 → 책상공간 직접 통과 (차단 확인)",points:[[1050,640],[1120,640]]},
      {label:"메인복도 → 기둥 왼쪽 → 책상공간",points:[[1104,732],[1104,692],[1104,650]]}
    ],
    3:[
      {label:"메인복도 → 자유공간 → 증축부 복도",points:[[1210,732],[1210,640],[1210,540],[1169,490],[1169,200]]},
      {label:"자유공간 → IT홀 층내 계단 (회전부 초안)",points:[[1200,565],[1120,565],[1100,530],[1065,530],[1065,420]]}
    ]
  };
  let data,map,svg,layer,trace,clicks=[],loadId=0;
  function node(tag,attrs,parent) {
    const n=document.createElementNS("http://www.w3.org/2000/svg",tag);
    Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));parent.append(n);return n;
  }
  function check(points) {
    trace.replaceChildren();clicks=[];
    node("polyline",{points:points.map(p=>p.join(",")).join(" "),class:"nav-trace"},trace);
    points.forEach(p=>node("circle",{cx:p[0],cy:p[1],r:6,class:"nav-dot"},trace));
    const verdicts=points.slice(1).map((p,i)=>Nav.transition(map,Nav.svgToMap(...points[i]),Nav.svgToMap(...p)));
    const blocked=verdicts.find(v=>!v.allowed),unknown=verdicts.some(v=>v.reason.startsWith("unverified"));
    const explanation=blocked?.reason==='outside_tracking_scope'?'현재 측위 범위를 벗어납니다. 실제 벽 판정은 아닙니다.':
      blocked?.reason==='unregistered_connection'?'등록된 진입 연결을 지나지 않습니다.': '확인된 벽을 가로지르는 구간입니다.';
    $("status").textContent=blocked ? `통과 제한: ${blocked.reason} · ${explanation}`
      : unknown ? "미확인 영역 포함 · 강제로 막지 않습니다. 현장 연결 확인이 필요합니다."
        : "표시된 영역을 따라 연결됩니다. 실제 폭·가구·문 위치까지 검증했다는 뜻은 아닙니다.";
    return {blocked:!!blocked,unknown};
  }
  async function loadFloor() {
    const id=++loadId,floor=Number($("floor").value);
    $("status").textContent="지도를 불러오는 중입니다.";
    const response=await fetch(`pages/floors/floor-0${floor}.html`);
    if (!response.ok) throw new Error(`지도 HTTP ${response.status}`);
    const doc=new DOMParser().parseFromString(await response.text(),"text/html");
    if (id!==loadId) return;
    svg=doc.querySelector("svg");if(!svg)throw new Error("원본 지도 SVG 없음");
    $("plan").replaceChildren(svg);map=Nav.compile(data,floor);
    // Sample paths must use the registered survey frame, not old drawing
    // pixels which can extend past its measured depth after a GLB update.
    const area=id=>map.areas.find(a=>a.id===id),center=id=>{
      const r=area(id).rect;return [(r[0]+r[2])/2,(r[1]+r[3])/2];
    };
    const pixels=points=>points.map(p=>{const q=Nav.mapToSvg(...p);return [q.x,q.y];});
    const [ex,ey]=center('extension');
    if(floor===2){
      const [ox,oy]=center('open_2107'),[mx,my]=center('mspace');
      examples[2][0].points=pixels([[ox,0],[ox,oy],[mx,oy],[mx,my]]);
      examples[2][2].points=pixels([[ex,0],[ex,center('entry')[1]],[ex,ey]]);
    }else{
      const [ix,iy]=center('entry'),fy=center('free')[1];
      examples[3][0].points=pixels([[ix,0],[ix,iy],[ix,fy],[ex,fy],[ex,ey]]);
      examples[3][1].label='IT홀 구도면 직선 연결 (현 측위 범위 밖 확인)';
    }
    layer=node("g",{"data-navigation-overlay":"true"},svg);
    for (const a of map.areas) {
      const rect=a.display_svg_rect || a.svg_rect || (()=>{const p=Nav.mapToSvg(a.rect[2],a.rect[3]),q=Nav.mapToSvg(a.rect[0],a.rect[1]);return[p.x,p.y,q.x,q.y];})();
      const r=node("rect",{x:rect[0],y:rect[1],width:rect[2]-rect[0],height:rect[3]-rect[1],class:`nav-area ${a.status ? "unverified" : ""}`},layer);
      node("title",{},r).textContent=a.label;
    }
    for(const p of map.portals) {
      const line=p.display_svg_line || p.svg_line || p.line.map(v=>{const q=Nav.mapToSvg(v.x,v.y);return [q.x,q.y];});
      node("line",{x1:line[0][0],y1:line[0][1],x2:line[1][0],y2:line[1][1],class:"nav-portal"},layer);
    }
    for(const w of map.walls) node("line",{x1:w.svg_line[0][0],y1:w.svg_line[0][1],x2:w.svg_line[1][0],y2:w.svg_line[1][1],class:"nav-wall"},layer);
    trace=node("g",{"data-test-trace":"true"},svg);
    layer.style.display=$("overlay").checked ? "" : "none";
    $("route").replaceChildren(...examples[floor].map((e,i)=>{const o=document.createElement("option");o.value=i;o.textContent=e.label;return o;}));
    $("notes").textContent=map.note;
    svg.addEventListener("click",event=>{
      const matrix=svg.getScreenCTM();if(!matrix)return;
      const p=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());
      clicks.push([p.x,p.y]);
      if(clicks.length===2)check(clicks);
      else {trace.replaceChildren();node("circle",{cx:p.x,cy:p.y,r:6,class:"nav-dot"},trace);$("status").textContent="시작점을 찍었습니다. 도착점을 찍어 직선 통과 여부를 확인하세요.";}
    });
    check(examples[floor][0].points);
    window.navigationReview={floor,map,check,examples:examples[floor]};
  }
  try {
    const response=await fetch("data/navigation/areas-v1.json");if(!response.ok)throw new Error(`영역 HTTP ${response.status}`);
    data=await response.json();
    const requested=new URLSearchParams(location.search).get("floor");if(["2","3"].includes(requested))$("floor").value=requested;
    await loadFloor();
    $("floor").addEventListener("change",()=>loadFloor().catch(e=>{$("status").textContent=e.message;}));
    $("showRoute").addEventListener("click",()=>check(examples[$("floor").value][Number($("route").value)].points));
    $("clear").addEventListener("click",()=>{trace.replaceChildren();clicks=[];$("status").textContent="지도에서 시작점과 도착점을 차례로 찍으세요.";});
    $("overlay").addEventListener("change",()=>{layer.style.display=$("overlay").checked?"":"none";});
  } catch(error) {$("status").textContent=`불러오기 실패: ${error.message}`;console.error(error);}
})();
