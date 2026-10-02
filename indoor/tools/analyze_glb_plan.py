"""Extract GLB POSITION vertices and render an equal-scale top-down diagnostic."""
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


COMPONENT = {5120: (np.int8, 1), 5121: (np.uint8, 1), 5122: (np.int16, 2),
             5123: (np.uint16, 2), 5125: (np.uint32, 4), 5126: (np.float32, 4)}
WIDTH = 1400
HEIGHT = 1000
MARGIN = 90


def read_glb(path):
    data = path.read_bytes()
    magic, version, declared = struct.unpack_from('<4sII', data, 0)
    if magic != b'glTF' or version != 2 or declared != len(data):
        raise ValueError(f'Not a valid GLB v2: {path}')
    offset = 12
    gltf = None
    bins = []
    while offset < len(data):
        size, kind = struct.unpack_from('<I4s', data, offset)
        offset += 8
        chunk = data[offset:offset+size]
        offset += size
        if kind == b'JSON':
            gltf = json.loads(chunk.decode('utf-8'))
        elif kind == b'BIN\0':
            bins.append(chunk)
    return gltf, bins


def accessor_array(gltf, bins, index):
    accessor = gltf['accessors'][index]
    view = gltf['bufferViews'][accessor['bufferView']]
    dtype, width = COMPONENT[accessor['componentType']]
    components = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[accessor['type']]
    start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    stride = view.get('byteStride', components * width)
    count = accessor['count']
    raw = bins[view.get('buffer', 0)]
    if stride == components * width:
        return np.frombuffer(raw, dtype=dtype, count=count*components, offset=start).reshape(count, components)
    return np.vstack([np.frombuffer(raw, dtype=dtype, count=components, offset=start+i*stride)
                      for i in range(count)])


def positions(path):
    gltf, bins = read_glb(path)
    arrays = []
    for mesh in gltf.get('meshes', []):
        for primitive in mesh.get('primitives', []):
            index = primitive.get('attributes', {}).get('POSITION')
            if index is not None:
                arrays.append(accessor_array(gltf, bins, index).astype(np.float64))
    return np.vstack(arrays)


def render(points, output):
    xz = points[:, [0, 2]]
    mins = xz.min(axis=0)
    maxs = xz.max(axis=0)
    span = maxs - mins
    scale = min((WIDTH-2*MARGIN)/span[0], (HEIGHT-2*MARGIN)/span[1])
    pixels = np.rint((xz-mins)*scale).astype(int)
    pixels[:, 0] += MARGIN
    pixels[:, 1] = HEIGHT-MARGIN-pixels[:, 1]
    y = points[:, 1]
    y01 = np.clip((y-y.min()) / max(1e-9, y.max()-y.min()), 0, 1)
    density = np.zeros((HEIGHT, WIDTH), dtype=np.uint16)
    height_sum = np.zeros((HEIGHT, WIDTH), dtype=np.float64)
    np.add.at(density, (pixels[:, 1], pixels[:, 0]), 1)
    np.add.at(height_sum, (pixels[:, 1], pixels[:, 0]), y01)
    occupied = density > 0
    average = np.zeros_like(height_sum)
    average[occupied] = height_sum[occupied] / density[occupied]
    strength = np.clip(np.log1p(density)/np.log(8), 0, 1)
    rgb = np.full((HEIGHT, WIDTH, 3), 250, dtype=np.uint8)
    # Low vertices (floor) blue-green; high vertices (walls/ceiling) orange-red.
    rgb[..., 0] = np.where(occupied, (40 + 190*average)*strength + 250*(1-strength), 250).astype(np.uint8)
    rgb[..., 1] = np.where(occupied, (155 - 60*average)*strength + 250*(1-strength), 250).astype(np.uint8)
    rgb[..., 2] = np.where(occupied, (190 - 120*average)*strength + 250*(1-strength), 250).astype(np.uint8)
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((MARGIN, MARGIN, WIDTH-MARGIN, HEIGHT-MARGIN), outline=(60,60,60), width=2)
    draw.text((MARGIN, 24), f'{output.stem}   X span {span[0]:.3f} m   Z span {span[1]:.3f} m   equal scale', fill=(10,10,10))
    draw.text((MARGIN, HEIGHT-42), f'X {mins[0]:.2f} .. {maxs[0]:.2f} m', fill=(10,10,10))
    draw.text((WIDTH-330, HEIGHT-42), f'Z {mins[1]:.2f} .. {maxs[1]:.2f} m', fill=(10,10,10))
    image.save(output)


def main():
    source = Path(sys.argv[1])
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else source.with_suffix('.topdown.png')
    output.parent.mkdir(parents=True, exist_ok=True)
    pts = positions(source)
    render(pts, output)
    result = {
        'file': str(source), 'vertices': int(len(pts)),
        'bbox_min': pts.min(axis=0).tolist(), 'bbox_max': pts.max(axis=0).tolist(),
        'bbox_size': (pts.max(axis=0)-pts.min(axis=0)).tolist(),
        'vertical_quantiles': {str(q): float(np.quantile(pts[:,1], q)) for q in [0,.01,.05,.1,.25,.5,.75,.9,.99,1]},
        'topdown': str(output),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
