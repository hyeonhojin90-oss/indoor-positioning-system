import json
import struct
import sys
from pathlib import Path


path = Path(sys.argv[1])
data = path.read_bytes()
magic, version, length = struct.unpack_from("<4sII", data, 0)

offset = 12
gltf = None
chunks = []
while offset < len(data):
    chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
    offset += 8
    chunk = data[offset : offset + chunk_length]
    offset += chunk_length
    chunks.append((chunk_type.decode("ascii"), chunk_length))
    if chunk_type == b"JSON":
        gltf = json.loads(chunk.decode("utf-8"))

mins = []
maxs = []
for accessor in gltf.get("accessors", []):
    if accessor.get("type") == "VEC3" and "min" in accessor and "max" in accessor:
        mins.append(accessor["min"])
        maxs.append(accessor["max"])

print("file", path.name, "bytes", len(data))
print("magic", magic.decode("ascii"), "version", version, "length", length)
print("chunks", chunks)
print(
    "counts",
    {
        "scenes": len(gltf.get("scenes", [])),
        "nodes": len(gltf.get("nodes", [])),
        "meshes": len(gltf.get("meshes", [])),
        "materials": len(gltf.get("materials", [])),
        "accessors": len(gltf.get("accessors", [])),
    },
)

if mins:
    mn = [min(value[index] for value in mins) for index in range(3)]
    mx = [max(value[index] for value in maxs) for index in range(3)]
    print("bbox_min", mn)
    print("bbox_max", mx)
    print("bbox_size", [round(mx[index] - mn[index], 3) for index in range(3)])
else:
    print("bbox", "not found")
