const fs=require('node:fs');
const file='indoor/web/data/navigation/areas-v1.json',data=JSON.parse(fs.readFileSync(file,'utf8'));
data.version='areas-v2-scope-20261002';
data.trackingPolicy={enabled:true,version:'scope-v1-20261002',
  evidence:'User-approved tracking scope, 2026-10-02. Existing geometry reused; no new wall/door dimensions measured.',
  standard:{closed:true,mode:'corridor_core_stair_transition',excluded:'classroom interiors and outdoor areas',scopeStatus:'defined_not_field_validated'},
  floors:{
    '1':{closed:true,mode:'main_entrance_common',mainEntrance:{svg_rect:[634,590,696,700],portal:[[634,700],[696,700]]},
      excluded:'rest area, administrative and outdoor areas; main entrance dimensions diagram-derived'},
    '2':{closed:true,mode:'common_and_registered_extension',excluded:'classroom interiors; study/TDM destinations use main-corridor approach'},
    '3':{closed:true,mode:'common_and_registered_extension',excluded:'room interiors; IT hall connection provisional'},
    '5':{closed:true,mode:'corridor_core_stair_transition',excluded:'outdoor exits and outdoor tracking'}},
  stairs:{mode:'entry_then_vertical_state_no_planar_pdr',
    coreEntryDepthM:3.61,coreEntryEvidence:'1.17 main half-width + existing 2.44 stair-start depth; connector vicinity only, not surveyed door polygon',
    requirePressureOrConfirmedEntry:true,landingAloneDoesNotConfirmFloor:true,
    floorConfirmation:'explicit_exit_with_pressure_candidate_or_verified_floor_beacon',
    pressurePerFloorHpa:0.44,pressureCalibration:'provisional_requires_field_validation'}};
data.floors['1'].distanceMetric=structuredClone(data.floors['4'].distanceMetric);
data.floors['1'].distanceMetric.status='common_geometry_reused_user_confirmation_not_1f_survey';
data.floors['1'].note='Main-entrance strip and common corridor only; rest/outdoor tracking excluded. Common length reused, not separately surveyed on 1F.';
fs.writeFileSync(file,JSON.stringify(data,null,2)+'\n');
console.log('Updated explicit tracking scope; diagram geometry retained.');
