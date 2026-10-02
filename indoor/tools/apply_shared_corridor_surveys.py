"""Apply confirmed common-corridor and 3F-extension survey distances.

The evacuation-plan drawings remain schematic.  Physical motion uses the
piecewise meter mapping written to areas-v1.json.
"""
from pathlib import Path
import json, re, shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "indoor/data/analysis/shared-survey-apply-20260922"
BEFORE = OUT / "before"

def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

def save(rel, value):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def preserve(rel):
    src, dst = ROOT / rel, BEFORE / rel
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return dst

right_m = 48.68545341491699
core_m = 2.975348
left_m = 47.3473772
# The legacy start x=70.804 is the core center.  Convert that exact surveyed
# center-to-right distance to meters instead of retaining the old 3.016m core.
legacy_step_m = (right_m + core_m / 2) / 70.804
map_breaks = [3.363100346020758, 69.424, 72.184, 135.407]
meter_breaks = [0, right_m, right_m + core_m, right_m + core_m + left_m]

common = {
    "version": "common-corridor-glb-20260922",
    "applies_to_floors": [2,3,4,5,6,7,8,9,10],
    "excluded_floors": [1],
    "right_core_to_stair_entry_m": right_m,
    "core_wall_center_width_m": core_m,
    "left_core_to_corridor_end_m": left_m,
    "core_left_to_core_right_and_both_corridors_m": meter_breaks[-1],
    "map_breaks": map_breaks,
    "meter_breaks": meter_breaks,
    "meters_per_legacy_unit": legacy_step_m,
    "right_end_note": "3F 50.8837m reaches the scan end wall; 48.6855m remains the corridor-to-stair-entry distance, so stair depth is not added twice.",
    "display_note": "2D/3D room drawings remain schematic; positioning motion uses this physical piecewise metric.",
}
save("indoor/web/data/maps/common-corridor-survey.json", common)

# Record the same source in every measured-floor map without changing room
# proportions that were never surveyed door by door.
for floor in range(2, 11):
    rel = f"indoor/web/data/maps/floor-{floor:02d}.json"
    data = load(rel)
    data["common_corridor_survey"] = common
    save(rel, data)

# 3F GLB geometry.  The left IT-hall interior is still provisional, while its
# exterior span follows the surveyed adjacent corridor/free-space footprint.
m3 = load("indoor/data/analysis/scan-geometry-20260921/3f-extension-measurements.json")["measurements"]
x_scale = 135.407 / 1240
y_scale = 7.9 / 110
free_left = 1146.0
free_right = free_left + m3["free_wall_reference_length_m"] / x_scale
free_near = 585.0
free_far = free_near - m3["free_wall_reference_width_m"] / y_scale
corridor_left = 1146.0
corridor_right = corridor_left + m3["branch_wall_face_width_m"] / x_scale
corridor_near = free_far
corridor_far = corridor_near - m3["branch_straight_length_m"] / y_scale
survey3 = {
    "version": "3f-extension-glb-20260922",
    "source": "3f-right-corridor.glb",
    "straight_length_m": m3["branch_straight_length_m"],
    "corridor_width_m": m3["branch_wall_face_width_m"],
    "front_space_length_m": m3["free_wall_reference_length_m"],
    "front_space_depth_m": m3["free_wall_reference_width_m"],
    "svg_free_left": free_left,
    "svg_free_right": free_right,
    "svg_free_far_y": free_far,
    "svg_free_near_y": free_near,
    "svg_corridor_left": corridor_left,
    "svg_corridor_right": corridor_right,
    "svg_corridor_far_y": corridor_far,
    "svg_corridor_near_y": corridor_near,
    "it_hall_interior_surveyed": False,
    "room_interiors_surveyed": False,
}
save("indoor/web/data/maps/floor-03-survey.json", survey3)

floor3 = load("indoor/web/data/maps/floor-03.json")
ext = floor3["floor3_extension"]
ext["survey"] = survey3
ext["measurement_source"] = "2026-09-21 3F GLB wall-face analysis"
ext["extension_corridor_length"] = m3["branch_straight_length_m"]
ext["extension_corridor_width"] = m3["branch_wall_face_width_m"]
ext["front_free_space_width"] = m3["free_wall_reference_length_m"]
ext["front_free_space_depth"] = m3["free_wall_reference_width_m"]
ext["status"] = "glb-survey-applied-20260922"
save("indoor/web/data/maps/floor-03.json", floor3)

nav = load("indoor/web/data/navigation/areas-v1.json")
metric = {
    "mapBreaks": map_breaks,
    "meterBreaks": meter_breaks,
    "metersPerLegacyUnit": legacy_step_m,
    "calibrationSteps": 81,
    "status": "shared_glb_survey_20260922",
    "source": "data/maps/common-corridor-survey.json",
}
for floor in range(2, 11):
    f = nav["floors"].setdefault(str(floor), {"areas": [], "portals": [], "walls": []})
    f.setdefault("areas", [])
    f.setdefault("portals", [])
    f.setdefault("walls", [])
    f["distanceMetric"] = metric

# Rebuild floor 3 from the preserved pre-survey navigation source.  Reading
# the already transformed live areas would compound y scaling on every run.
base_nav = load("indoor/data/analysis/2f-survey-apply-20260922/before/indoor/web/data/navigation/areas-v1.json")
f3 = base_nav["floors"]["3"]
f3["distanceMetric"] = metric
nav["floors"]["3"] = f3

def map_y(y):
    if y >= 585:
        return y
    if y >= 455:
        return free_near + (y - 585) * (free_near - free_far) / 130
    return corridor_near + (y - 455) * (corridor_near - corridor_far) / 370

for area in f3["areas"]:
    if "svg_rect" not in area:
        continue
    x1, y1, x2, y2 = area["svg_rect"]
    if area["id"] == "free":
        x1, x2 = free_left, free_right
    elif area["id"] == "extension":
        x1, x2 = corridor_left, corridor_right
        area["status"] = "glb-wall-reference-approximate"
    area["svg_rect"] = [x1, map_y(y1), x2, map_y(y2)]

for portal in f3["portals"]:
    if "svg_line" not in portal:
        continue
    points = portal["svg_line"]
    if portal["id"] == "free_extension":
        points = [[corridor_left, 455], [corridor_right, 455]]
    portal["svg_line"] = [[x, map_y(y)] for x, y in points]

f3["extensionMotionMetric"] = {
    "legacyStepMeters": legacy_step_m,
    "xMetersPerUnit": x_scale / (69.424 / 578),
    "yMetersPerUnit": 1,
    "note": "3F surveyed extension motion; y is physical meters and the corridor width uses the GLB wall-face span.",
}
f3["survey"] = survey3
f3["note"] = "3F extension GLB distance applied; IT-hall interior and individual room doors remain provisional."
save("indoor/web/data/navigation/areas-v1.json", nav)

# Rebuild the 3F SVG from the preserved pre-change source so repeated runs do
# not stack transforms.
html = preserve("indoor/web/pages/floors/floor-03.html").read_text(encoding="utf-8")

def transform_group(text, cls, transform):
    start = text.index('<g class="' + cls + '"')
    pos = text.index('>', start) + 1
    depth = 1
    for match in re.finditer(r'<g\b[^>]*>|</g>', text[pos:]):
        depth += -1 if match.group().startswith('</') else 1
        if depth == 0:
            end = pos + match.start()
            return text[:pos] + f'<g transform="{transform}">' + text[pos:end] + '</g>' + text[end:]
    raise ValueError(cls)

free_sx = (free_right - 1146) / (1300 - 1146)
free_sy = (free_near - free_far) / (585 - 455)
html = transform_group(html, "extension-room free-space",
    f"translate({1146 * (1-free_sx)} {free_near - 585*free_sy}) scale({free_sx} {free_sy})")

corridor_sx = (corridor_right - 1146) / (1192 - 1146)
corridor_sy = (corridor_near - corridor_far) / (455 - 85)
corridor_tx = 1146 * (1-corridor_sx)
corridor_ty = corridor_near - 455*corridor_sy
html = transform_group(html, "extension-corridor",
    f"translate({corridor_tx} {corridor_ty}) scale({corridor_sx} {corridor_sy})")
html = transform_group(html, "extension-room it-hall",
    f"translate(0 {corridor_ty}) scale(1 {corridor_sy})")
html = transform_group(html, "extension-room it-hall-lower",
    f"translate(0 {free_near - 585*free_sy}) scale(1 {free_sy})")

room_left, room_right = corridor_right + 6, free_right
room_sx = (room_right - room_left) / (1300 - 1198)
room_tx = room_left - 1198*room_sx
html = transform_group(html, "extension-room room-3104",
    f"translate({room_tx} {corridor_ty}) scale({room_sx} {corridor_sy})")

center_x = (corridor_left + corridor_right) / 2
html = html.replace('M680 732H1214V590H1172V515H1169V105',
    f'M680 732H1214V590H{center_x}V{free_far}H{center_x}V{corridor_far+20}')
html = re.sub(r'<g class="dimension-note">.*?</g>',
    '<g class="dimension-note"><text x="500" y="900">증축 직선 약 25.24m · 폭 약 2.06m</text><text x="500" y="923">전면공간 약 14.28m × 6.79m</text><text x="500" y="946">IT홀 내부·문별 좌표는 미측정</text></g>',
    html, count=1)
html = html.replace(
    '이 2D에서 3203 입구 폭, IT홀 문 위치, 3104-1·2 분할이 맞는지 먼저 검토합니다. 승인 후에만 3D 벽·문·계단 모델로 변환합니다.',
    '증축 직선과 전면공간 외곽은 새 GLB 실측을 반영했습니다. IT홀 내부, 3104-1·2 방 내부와 문별 좌표는 미측정 상태로 유지합니다.')
(ROOT / "indoor/web/pages/floors/floor-03.html").write_text(html, encoding="utf-8")

print(json.dumps({"common": common, "floor3": survey3}, ensure_ascii=False, indent=2))
