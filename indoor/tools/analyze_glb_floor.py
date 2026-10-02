"""Inspect near-horizontal lower faces in a GLB scan."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('glb_plan', Path(__file__).with_name('analyze_glb_plan.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def inspect(path):
    gltf, bins = module.read_glb(path)
    records=[]
    all_centers=[]
    for mi, mesh in enumerate(gltf.get('meshes', [])):
        for pi, primitive in enumerate(mesh.get('primitives', [])):
            if primitive.get('mode',4)!=4 or 'indices' not in primitive:
                continue
            verts=module.accessor_array(gltf,bins,primitive['attributes']['POSITION']).astype(np.float64)
            indices=module.accessor_array(gltf,bins,primitive['indices']).astype(np.int64).reshape(-1,3)
            tri=verts[indices]
            cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
            length=np.linalg.norm(cross,axis=1)
            normal=np.zeros_like(cross)
            valid=length>1e-9
            normal[valid]=cross[valid]/length[valid,None]
            centers=tri.mean(axis=1)
            lower=centers[:,1] < np.quantile(centers[:,1],.35)
            horizontal=np.abs(normal[:,1])>.9
            mask=lower&horizontal
            selected=centers[mask]
            all_centers.append(selected)
            selected_indices=indices[mask]
            selected_areas=length[mask]/2
            parent={int(v):int(v) for v in np.unique(selected_indices)}
            def find(v):
                while parent[v]!=v:
                    parent[v]=parent[parent[v]]
                    v=parent[v]
                return v
            def union(a,b):
                ra,rb=find(int(a)),find(int(b))
                if ra!=rb: parent[rb]=ra
            for tri_indices in selected_indices:
                union(tri_indices[0],tri_indices[1]);union(tri_indices[1],tri_indices[2])
            components={}
            for face_index,tri_indices in enumerate(selected_indices):
                root=find(int(tri_indices[0]))
                item=components.setdefault(root,{'centers':[],'area':0.0})
                item['centers'].append(selected[face_index]);item['area']+=float(selected_areas[face_index])
            top=[]
            for item in sorted(components.values(),key=lambda x:x['area'],reverse=True)[:5]:
                c=np.vstack(item['centers'])
                top.append({'faces':len(c),'area':item['area'],'bbox_min':c.min(axis=0).tolist(),
                    'bbox_max':c.max(axis=0).tolist(),'bbox_size':np.ptp(c,axis=0).tolist()})
            records.append({'mesh':mi,'primitive':pi,'triangles':int(len(tri)),
                'selected_horizontal_lower':int(len(selected)),
                'selected_bbox_min':selected.min(axis=0).tolist() if len(selected) else None,
                'selected_bbox_max':selected.max(axis=0).tolist() if len(selected) else None,
                'largest_components':top})
    centers=np.vstack(all_centers)
    return {'file':str(path),'horizontal_lower_centers':int(len(centers)),
        'bbox_min':centers.min(axis=0).tolist(),'bbox_max':centers.max(axis=0).tolist(),
        'bbox_size':np.ptp(centers,axis=0).tolist(),
        'robust_x_01_99':np.quantile(centers[:,0],[.01,.99]).tolist(),
        'robust_z_01_99':np.quantile(centers[:,2],[.01,.99]).tolist(),
        'meshes':records}


for arg in sys.argv[1:]:
    print(json.dumps(inspect(Path(arg)),indent=2))
