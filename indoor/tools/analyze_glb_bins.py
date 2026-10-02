"""Print 2 m top-down occupancy slices for an inspected GLB."""
import importlib.util
import sys
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('glb_plan', Path(__file__).with_name('analyze_glb_plan.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

for name in sys.argv[1:]:
    points = module.positions(Path(name))
    print(f'\n{name}')
    for z in np.arange(np.floor(points[:,2].min()), np.ceil(points[:,2].max()), 2):
        sample = points[(points[:,2]>=z)&(points[:,2]<z+2)]
        if len(sample) <= 50:
            continue
        q05, q50, q95 = np.quantile(sample[:,0], [.05,.5,.95])
        print(f'z {z:6.1f}..{z+2:5.1f} n={len(sample):6d} '
              f'x05={q05:7.2f} x50={q50:7.2f} x95={q95:7.2f} range={np.ptp(sample[:,0]):7.2f}')
